"""招商银行 (CMB) 账户明细清单 PDF 解析器

处理招商银行"账务明细清单"（Account Statement）—— 水平表格格式，7列布局：

    | 日期 | 业务类型 | 票据号 | 摘要 | 借方/贷方金额 | 余额 | 对方户名 |

与 cmb_parser.py 中处理的垂直/逐行格式不同，本解析器针对的是
招商银行企业网银导出的标准对账单 PDF（带中英文双语表头）。

解析策略：
- 使用 PyMuPDF get_text('dict') 获取每个 text span 的精确位置 (x, y)
- 按 y 坐标聚类成数据行
- 每行内按 x 坐标将 span 映射到对应列
- 从表头/页脚区域提取账户信息和期初/期末余额
"""
import fitz
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Dict, Any, Tuple

from ..models import Transaction, ParseResult


class CMBTableParser:
    """招商银行 账务明细清单（水平表格格式）解析器"""

    BANK_NAME = '招商银行'

    COLUMNS = {
        'date':          (33, 60),
        'business_type': (60, 130),
        'bill_no':       (130, 160),
        'description':   (160, 320),
        'amount':        (320, 380),
        'balance':       (380, 420),
        'counterparty':  (420, 550),
    }

    HEADER_KEYS = {
        '账号': 'account_no',
        '账户名称': 'account_name',
        '货币': 'currency',
        '开户银行': 'bank_branch',
        '账单所属期间': 'period',
        '上页余额': 'opening_balance',
    }

    OPENING_BALANCE_KEY = '上页余额'
    CLOSING_BALANCE_KEY = '期末余额'

    def __init__(self, tolerance: int = 20):
        self.tolerance = tolerance
        self.confidence = 1.0

    # ─── 公共入口 ──────────────────────────────────────────

    def parse(self, file_path: str) -> ParseResult:
        """解析招行 PDF 对账单主入口

        算法流程：
        1. 读取 PDF 文件为二进制字节
        2. 使用 PyMuPDF 打开文档，取第 1 页
        3. 提取所有 text span（含 x0, y0, x1, y1 坐标）
        4. 按 y 坐标将页面分为：表头区 / 表格区 / 页脚区
        5. 从表头区提取账户元数据（账号、户名、期初余额等）
        6. 从页脚区提取期末余额
        7. 从表格区解析每行数据 → Transaction 列表
        8. 按日期排序后返回 ParseResult
        """
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        doc = fitz.open('pdf', pdf_bytes)

        if len(doc) == 0:
            doc.close()
            return ParseResult(transactions=[], bank=self.BANK_NAME,
                               confidence=0, errors=['Empty PDF'])

        page = doc[0]
        all_spans = _extract_all_spans(page)
        doc.close()

        # 步骤 4: 按 y 坐标将页面分为表头 / 表格 / 页脚三个区域
        header_spans, table_spans, footer_spans = _partition_spans(all_spans)
        # 步骤 5: 解析表头元数据
        meta = _parse_header_metadata(header_spans)
        opening_balance = meta.get('opening_balance')
        # 步骤 6: 从页脚提取期末余额
        closing_balance = _extract_closing_balance(footer_spans)
        # 步骤 7: 解析表格数据行
        transactions, errors = self._parse_table_rows(table_spans)

        statement_date = transactions[-1].date if transactions else None
        return ParseResult(
            transactions=transactions, bank=self.BANK_NAME,
            statement_date=statement_date,
            opening_balance=opening_balance, closing_balance=closing_balance,
            confidence=self.confidence, errors=errors, warnings=[],
        )

    # ─── 表格行解析 ────────────────────────────────────────

    def _parse_table_rows(self, spans: list) -> Tuple[List[Transaction], List[str]]:
        """解析表格区域的所有数据行

        算法步骤：
        1. 将所有 span 按 (y0, x0) 排序，保证同一行内按 x 坐标有序
        2. 按 y 坐标聚类：相邻 span 的 y0 差 ≤ gap(2.5pt) 视为同一行
        3. 对每一行调用 _row_to_transaction() 转换为 Transaction 对象
        4. 最后按日期升序排序
        """
        spans = sorted(spans, key=lambda s: (s['y0'], s['x0']))
        rows = _cluster_by_y(spans, gap=2.5)
        transactions, errors = [], []
        for row_spans in rows:
            try:
                tx = self._row_to_transaction(row_spans)
                if tx:
                    transactions.append(tx)
            except Exception as e:
                errors.append(str(e))
                self.confidence -= 0.01
        transactions.sort(key=lambda t: t.date)
        return transactions, errors

    def _row_to_transaction(self, row_spans: list) -> Optional[Transaction]:
        """将一行 spans 转换为 Transaction 对象

        算法步骤：
        1. 将行内各 span 按 x 坐标分类到对应列（_classify_spans）
        2. 提取并验证日期字段（必填，格式 YYYYMMDD 或 YYYY-MM-DD）
        3. 提取并验证金额字段（必填，支持千分位逗号）
        4. 根据金额正负判断 direction：正=income，负=expense
        5. 拼接描述信息：业务类型 | 票据号 | 摘要
        6. 提取对方户名和余额
        7. 返回 Transaction 对象
        """
        cols = self._classify_spans(row_spans)
        date_str = cols.get('date', '').strip()
        amount_str = cols.get('amount', '').strip()
        if not date_str or not amount_str:
            return None

        tx_date = _parse_date(date_str)
        if not tx_date:
            return None
        amount = _parse_amount(amount_str)
        if amount is None:
            return None

        # 拼接描述：业务类型 | 票据号 | 摘要
        desc_parts = []
        for key in ('business_type', 'bill_no', 'description'):
            v = cols.get(key, '').strip()
            if v:
                desc_parts.append(f'票据号:{v}' if key == 'bill_no' else v)
        full_desc = ' | '.join(desc_parts) if desc_parts else '银行交易'

        counterparty = cols.get('counterparty', '').strip() or None
        balance_str = cols.get('balance', '').strip()
        balance = _parse_amount(balance_str) if balance_str else None

        return Transaction(
            date=tx_date, description=full_desc, amount=abs(amount),
            currency='CNY', direction='income' if amount > 0 else 'expense',
            counterparty=counterparty,
            reference_number=cols.get('bill_no', '').strip() or None,
            notes=f'余额:{balance}' if balance else None,
        )

    # ─── 列分类 ────────────────────────────────────────────

    def _classify_spans(self, row_spans: list) -> Dict[str, str]:
        """将一行内的所有 span 按 x 坐标分类到对应列

        算法步骤：
        1. 遍历行内每个 span
        2. 调用 _find_column() 根据 x0 坐标判断属于哪一列
        3. 同一列可能有多个 span（如长文本拆分为多段），拼接为空格分隔的字符串
        4. 返回 {列名: 拼接后文本} 的字典
        """
        cols: Dict[str, list] = {}
        for span in row_spans:
            col = self._find_column(span['x0'])
            if col:
                cols.setdefault(col, []).append(span['text'].strip())
        return {k: ' '.join(v) for k, v in cols.items()}

    def _find_column(self, x: float) -> Optional[str]:
        """根据 x 坐标找到最近的列名

        算法步骤：
        1. 遍历 COLUMNS 中定义的每个列区间 [x_min, x_max]
        2. 若 x 落在区间内，直接返回该列名
        3. 若都不在区间内，计算 x 到各列区间中心的距离
        4. 若最小距离 < tolerance*2，返回最近列名；否则返回 None
        """
        best_col, best_dist = None, float('inf')
        for col_name, (x_min, x_max) in self.COLUMNS.items():
            if x_min <= x <= x_max:
                return col_name
            mid = (x_min + x_max) / 2
            if abs(x - mid) < best_dist:
                best_dist = abs(x - mid)
                best_col = col_name
        return best_col if best_dist < self.tolerance * 2 else None


# ═══════════════════════════════════════════════════════════════
# 通用 Span 提取 / 区域划分 / 聚类 / 元数据解析
# ═══════════════════════════════════════════════════════════════

def _extract_all_spans(page: fitz.Page) -> List[dict]:
    """从 PDF 页面提取所有文本 span

    使用 PyMuPDF get_text('dict') 获取结构化文本数据，
    遍历所有 block → line → span，提取每个 span 的：
    - 坐标：x0, y0, x1, y1（左上右下）
    - 内容：text（文本）
    - 属性：size（字号）
    """
    td = page.get_text('dict')
    spans = []
    for block in td.get('blocks', []):
        if 'lines' not in block:
            continue
        for line in block['lines']:
            for span in line['spans']:
                text = span['text'].strip()
                if not text:
                    continue
                spans.append({
                    'x0': span['bbox'][0], 'y0': span['bbox'][1],
                    'x1': span['bbox'][2], 'y1': span['bbox'][3],
                    'text': text, 'size': span.get('size', 0),
                })
    return spans


def _partition_spans(spans: list) -> Tuple[list, list, list]:
    """将页面所有 span 按 y 坐标分为三个区域

    算法步骤：
    1. 调用 _find_table_region() 定位表格区的 y 范围
    2. 表头区：y0 < 表格起始 y - 5pt（表格上方区域）
    3. 表格区：表格起始 y - 5pt ≤ y0 ≤ 表格结束 y + 5pt
    4. 页脚区：y0 > 表格结束 y + 5pt（表格下方区域）

    返回：(header_spans, table_spans, footer_spans)
    """
    table_start, table_end = _find_table_region(spans)
    header = [s for s in spans if s['y0'] < table_start - 5]
    table  = [s for s in spans if table_start - 5 <= s['y0'] <= table_end + 5]
    footer = [s for s in spans if s['y0'] > table_end + 5]
    return header, table, footer


def _find_table_region(spans: list) -> Tuple[float, float]:
    """通过列标题精确定位表格区域的 y 范围

    算法步骤：
    1. 搜索包含列标题关键词（"交易日期"、"Date"、"日期"）的 span
    2. 若找到，取最小 y0 作为表格起始，起始 y + 40pt 作为结束
    3. 若未找到，返回默认范围 (105.0, 165.0)

    返回：(table_start_y, table_end_y)
    """
    COL_TITLES = ['交易日期', 'Date', '日期']
    y_list = [s['y0'] for s in spans
              if any(k in s['text'] for k in COL_TITLES)]
    if not y_list:
        return 105.0, 165.0
    return min(y_list) - 5, max(s['y1'] for s in spans)


def _cluster_by_y(spans: list, gap: float = 2.0) -> List[list]:
    """按 y 坐标将 span 聚类为行

    算法步骤：
    1. 按 y0 升序排序所有 span
    2. 遍历排序后的 span，相邻两个 span 的 y0 差 ≤ gap(2pt) 视为同一行
    3. 超过 gap 则开始新的一行
    4. 返回行的列表，每行是该行内 span 的列表

    参数：
        gap: 判定同一行的最大 y 坐标差（单位：pt）

    返回：[row1_spans, row2_spans, ...]
    """
    if not spans:
        return []
    sorted_spans = sorted(spans, key=lambda s: s['y0'])
    clusters, current, current_y = [], [sorted_spans[0]], sorted_spans[0]['y0']
    for s in sorted_spans[1:]:
        if s['y0'] - current_y > gap:
            clusters.append(current)
            current, current_y = [s], s['y0']
        else:
            current.append(s)
            current_y = max(current_y, s['y0'])
    clusters.append(current)
    return clusters


def _parse_header_metadata(header_spans: list) -> Dict[str, Any]:
    """从表头区域提取账户元数据

    算法步骤：
    1. 按 (y0, x0) 排序所有表头 span
    2. 遍历 span，匹配 "key: value" 或 "key："+换行+"value" 格式
    3. 使用 HEADER_KEYS 映射将原始 key 转为标准字段名
    4. 解析期初余额（上页余额）为 Decimal
    5. 解析账单期间（按空格分割起止日期）

    返回：{account_no, account_name, currency, bank_branch, period, opening_balance}
    """
    meta: Dict[str, Any] = {}
    sorted_spans = sorted(header_spans, key=lambda s: (s['y0'], s['x0']))
    pending_key = None

    for s in sorted_spans:
        text = s['text'].strip()
        if not text:
            continue

        if pending_key:
            if pending_key in CMBTableParser.HEADER_KEYS:
                meta[CMBTableParser.HEADER_KEYS[pending_key]] = text
            pending_key = None
            continue

        m = re.match(r'^(.+?):(.*)$', text)
        if m:
            raw_key = m.group(1).strip()
            val = m.group(2).strip()
            if val:
                if raw_key in CMBTableParser.HEADER_KEYS:
                    meta[CMBTableParser.HEADER_KEYS[raw_key]] = val
            else:
                if raw_key in CMBTableParser.HEADER_KEYS:
                    pending_key = raw_key
            continue

    if CMBTableParser.OPENING_BALANCE_KEY in meta:
        meta['opening_balance'] = _parse_amount(meta.pop(CMBTableParser.OPENING_BALANCE_KEY))
    if 'period' in meta:
        parts = meta['period'].split()
        if len(parts) >= 1:
            meta['period_start'] = parts[0]
        if len(parts) >= 2:
            meta['period_end'] = parts[1]
    return meta


def _extract_closing_balance(footer_spans: list) -> Optional[Decimal]:
    """从页脚区域提取期末余额

    算法步骤：
    1. 按 (y0, x0) 排序页脚 span
    2. 查找包含 "期末余额" 关键词的 span
    3. 若该 span 内包含金额（正则匹配金额格式），直接提取
    4. 否则在附近 ±5 个 span 范围内搜索同 y 坐标的金额文本
    5. 返回 Decimal 余额值或 None
    """
    keyword = CMBTableParser.CLOSING_BALANCE_KEY
    sorted_spans = sorted(footer_spans, key=lambda s: (s['y0'], s['x0']))
    for i, s in enumerate(sorted_spans):
        if keyword in s['text']:
            m = re.search(r'(\d[\d,]*\.\d{2})', s['text'])
            if m:
                return _parse_amount(m.group(1))
            return _find_nearby_number(sorted_spans, i)
    return None


def _find_nearby_number(spans: list, ref_index: int, max_distance: int = 5) -> Optional[Decimal]:
    """在参考 span 附近搜索金额数值

    算法步骤：
    1. 以 ref_index 位置的 y0 为基准
    2. 向两侧扩展搜索 ±max_distance 个 span
    3. 优先匹配 y 坐标差 < 3pt 的 span（同行优先）
    4. 匹配格式为金额的文本（如 -1,234.56）
    5. 返回距离最近的金额值（按 span 索引差排序）

    参数：
        ref_index: 参考 span 在列表中的索引
        max_distance: 最大搜索距离（span 数量）

    返回：Decimal 金额值或 None
    """
    ref_y = spans[ref_index]['y0']
    candidates = []
    for offset in range(1, max_distance + 1):
        for idx in (ref_index + offset, ref_index - offset):
            if 0 <= idx < len(spans):
                s = spans[idx]
                if abs(s['y0'] - ref_y) < 3:
                    text = s['text'].strip()
                    if re.match(r'^-?\d[\d,]*\.\d{2}$', text):
                        candidates.append((abs(idx - ref_index), _parse_amount(text)))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
    return None


def _parse_date(text: str) -> Optional[datetime.date]:
    """解析日期字符串为 date 对象

    支持的格式：
    - YYYYMMDD（无分隔符，如 "20260321"）
    - YYYY-MM-DD（横线分隔，如 "2026-03-21"）

    返回：date 对象或 None
    """
    text = text.strip()
    m = re.match(r'^(\d{4})(\d{2})(\d{2})$', text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
    return None


def _parse_amount(text: str) -> Optional[Decimal]:
    """解析金额字符串为 Decimal

    处理逻辑：
    1. 去除首尾空白、逗号千分位、空格
    2. 移除首部加号（正数可能带 + 号）
    3. 用 Decimal 精确解析，避免浮点误差
    4. 解析失败返回 None
    """
    text = text.strip().replace(',', '').replace(' ', '')
    text = re.sub(r'^\+', '', text)
    try:
        return Decimal(text)
    except InvalidOperation:
        return None
