"""广发银行 (GFB) 活期对公对账单 PDF 解析器

处理广发银行"活期对公对账单"—— 水平表格格式，7列布局：

    | 交易日期 | 交易类型 | 票据号码 | 本期支出 | 本期收入 | 交易对手信息 | 余额 |

与招行 CMBTableParser 的差异：
- "本期支出" 和 "本期收入" 是**独立两列**，不是正负号区分
- 金额语义：支出=expense，收入=income（两列互斥，只填一个）
- 表头关键字不同（行所号/币别/户名 vs 开户银行/货币/账户名称）
- 上期余额放在表头区（非页脚）
- 本期余额放在页脚区
- 标题关键字：广发银行活期对公对账单
"""
import fitz
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Dict, Any, Tuple

from ..models import Transaction, ParseResult


class GFBTableParser:
    """广发银行 活期对公对账单（水平表格格式）解析器"""

    BANK_NAME = '广发银行'

    # 表格列 x 坐标分区（基于 span 实测位置调整）
    # 每个列区间内不重叠：date[15,63] biz_type[65,113] bill_no[113,178]
    # expense[178,270] income[270,385] counterparty[385,520] balance[520,555]
    COLUMNS = {
        'date':         (15, 63),   # 交易日期（实测 22.8）
        'biz_type':     (65, 113),  # 交易类型（实测 67.9）
        'bill_no':      (113, 178), # 票据号码（实测 112.9）
        'expense':      (178, 270), # 本期支出（实测 262.2 / 177.7→bill_no 边界区）
        'income':       (270, 385), # 本期收入（实测 270.4）
        'counterparty': (385, 520), # 交易对手信息（实测 383.5）
        'balance':      (520, 555), # 余额（实测 523.3 / 529.5）
    }

    # 表头 key → meta key 映射
    HEADER_KEYS = {
        '行所号': 'bank_branch',
        '币别': 'currency',
        '账号': 'account_no',
        '户名': 'account_name',
    }

    OPENING_BALANCE_KEY = '上期余额'
    CLOSING_BALANCE_KEY = '本期余额'

    def __init__(self, tolerance: int = 20):
        self.tolerance = tolerance
        self.confidence = 1.0

    # ─── 公共入口 ──────────────────────────────────────────

    def parse(self, file_path: str) -> ParseResult:
        """解析广发银行 PDF 对账单主入口

        算法流程：
        1. 读取 PDF 文件为二进制字节
        2. 使用 PyMuPDF 打开文档，取第 1 页
        3. 提取所有 text span（含 x0, y0, x1, y1 坐标）
        4. 按 y 坐标将页面分为：表头区 / 表格区 / 页脚区
        5. 从表头区提取账户元数据（行所号、币别、账号、户名、上期余额等）
        6. 从页脚区提取本期余额
        7. 从表格区解析每行数据 → Transaction 列表
        8. 按日期排序后返回 ParseResult

        与 CMBTableParser 的关键差异：
        - 表头关键字不同（行所号/币别/户名 vs 开户银行/货币/账户名称）
        - 上期余额在表头区（非页脚）
        - 本期余额在页脚区
        - 金额分两列：本期支出 / 本期收入（互斥，不是正负号区分）
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
        # 步骤 5: 解析表头元数据（传入 self 以使用子类 HEADER_KEYS）
        meta = _parse_header_metadata(self, header_spans, table_spans)
        opening_balance = meta.get('opening_balance')
        # 步骤 6: 从页脚提取本期余额
        closing_balance = _extract_closing_balance(self, footer_spans)
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

        算法步骤（GFB 特有逻辑）：
        1. 将行内各 span 按 x 坐标分类到对应列（_classify_spans）
        2. 提取并验证日期字段（必填）
        3. GFB 特有：分别提取"本期支出"和"本期收入"两列
        4. 根据两列金额判断交易方向：
           - 本期支出 > 0 → expense
           - 本期收入 > 0 → income
           - 两列均为空 → 跳过该行
        5. 拼接描述：交易类型 | 票据号
        6. 提取对方信息和余额
        7. 返回 Transaction 对象

        注：GFB 的金额列不是正负号区分，而是两列互斥
        """
        cols = self._classify_spans(row_spans)
        date_str = cols.get('date', '').strip()
        if not date_str:
            return None

        tx_date = _parse_date(date_str)
        if not tx_date:
            return None

        # GFB 特有：本期支出 / 本期收入 是独立两列
        expense_str = cols.get('expense', '').strip()
        income_str = cols.get('income', '').strip()

        expense = _parse_amount(expense_str) if expense_str else Decimal('0')
        income = _parse_amount(income_str) if income_str else Decimal('0')

        if expense is None or income is None:
            return None

        if expense > 0:
            amount, direction = expense, 'expense'
        elif income > 0:
            amount, direction = income, 'income'
        else:
            return None  # 两列均为空

        biz_type = cols.get('biz_type', '').strip()
        bill_no = cols.get('bill_no', '').strip()
        counterparty = cols.get('counterparty', '').strip() or None
        balance_str = cols.get('balance', '').strip()
        balance = _parse_amount(balance_str) if balance_str else None

        desc = biz_type if biz_type else '银行交易'
        if bill_no:
            desc = f'{desc} | 票据号:{bill_no}'

        return Transaction(
            date=tx_date, description=desc, amount=amount,
            currency='CNY', direction=direction,
            counterparty=counterparty,
            reference_number=bill_no or None,
            notes=f'余额:{balance}' if balance else None,
        )

    # ─── 列分类 ────────────────────────────────────────────

    def _classify_spans(self, row_spans: list) -> Dict[str, str]:
        """将一行内的所有 span 按 x 坐标分类到对应列

        GFB 特有处理：
        1. 过滤掉已知列标签文本（防止表头行被误分类为数据行）
           - 包括中文标签（交易日期、交易类型、票据号码等）
           - 包括英文标签（Date、Business Type、Bill No. 等）
           - 包括余额标签（上期余额、上页余额）
        2. 遍历行内每个 span，调用 _find_column() 根据 x0 坐标判断所属列
        3. 同一列可能有多个 span，拼接为空格分隔的字符串
        4. 返回 {列名: 拼接后文本} 的字典
        """
        _LABELS = {
            '交易日期', '交易类型', '票据号码',
            '本期支出', '本期收入', '交易对手信息', '余额',
            'Date', 'Business Type', 'Bill No.', 'Description',
            'Debit/Credit Amount', 'Balance', 'Counterparty',
            '上期余额', '上页余额',
        }
        cols: Dict[str, list] = {}
        for span in row_spans:
            txt = span['text'].strip()
            if txt in _LABELS:
                continue
            col = self._find_column(span['x0'])
            if col:
                cols.setdefault(col, []).append(txt)
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
    """将 spans 按 y 坐标分为表头 / 表格 / 页脚三个区域。

    通过"交易日期"或"Date"列标题动态定位表格区。
    """
    table_start, table_end = _find_table_region(spans)
    header = [s for s in spans if s['y0'] < table_start - 5]
    table  = [s for s in spans if table_start - 5 <= s['y0'] <= table_end + 5]
    footer = [s for s in spans if s['y0'] > table_end + 5]
    return header, table, footer


def _find_table_region(spans: list) -> Tuple[float, float]:
    """通过**表格列标题**精确定位表格区域的 y 范围。

    同时包含 "交易日期" 和 "类型" 两个关键字，避免误匹配账户信息区的日期。
    """
    COL_TITLES = ['交易日期', '交易类型']
    y_list = [s['y0'] for s in spans
              if all(k in s['text'] for k in COL_TITLES)]
    if not y_list:
        y_list2 = [s['y0'] for s in spans if '交易日期' in s['text']]
        if y_list2:
            return min(y_list2) - 5, max(s['y1'] for s in spans)
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


def _parse_header_metadata(parser, header_spans: list,
                           table_spans: list = None) -> Dict[str, Any]:
    """从表头区域提取账户信息，使用子类提供的 HEADER_KEYS 映射。

    table_spans: 表格区 spans（用于在表格头部行中查找上期余额等字段）。
    """
    meta: Dict[str, Any] = {}
    sorted_spans = sorted(header_spans, key=lambda s: (s['y0'], s['x0']))
    pending_key = None

    for s in sorted_spans:
        text = s['text'].strip()
        if not text:
            continue

        if pending_key:
            mapped_key = _lookup_header_key(parser, pending_key)
            if mapped_key:
                meta[mapped_key] = text
            pending_key = None
            continue

        m = re.match(r'^(.+?)[:：](.*)$', text)
        if m:
            raw_key = _normalize_key(m.group(1).strip())
            val = m.group(2).strip()
            if val:
                mapped_key = _lookup_header_key(parser, raw_key)
                if mapped_key:
                    meta[mapped_key] = val
            else:
                if _lookup_header_key(parser, raw_key):
                    pending_key = raw_key
            continue

    # 若表头区未找到上期余额，在表格区中搜索
    if parser.OPENING_BALANCE_KEY not in meta and table_spans:
        ob_val = _find_balance_in_spans(
            table_spans, parser.OPENING_BALANCE_KEY)
        if ob_val is not None:
            meta['opening_balance'] = ob_val

    # 解析余额字段
    if parser.OPENING_BALANCE_KEY in meta:
        meta['opening_balance'] = _parse_amount(meta.pop(parser.OPENING_BALANCE_KEY))

    # 解析账单期间
    if 'period' in meta:
        parts = meta['period'].split()
        if len(parts) >= 1:
            meta['period_start'] = parts[0]
        if len(parts) >= 2:
            meta['period_end'] = parts[1]

    return meta


def _find_balance_in_spans(spans: list, keyword: str) -> Optional[str]:
    """在 spans 中搜索关键字及其关联数值 span。"""
    sorted_spans = sorted(spans, key=lambda s: (s['y0'], s['x0']))
    for i, s in enumerate(sorted_spans):
        if keyword in s['text']:
            m = re.search(r'(\d[\d,]*\.\d{2})', s['text'])
            if m:
                return m.group(1)
            return _find_nearby_value(sorted_spans, i)
    return None


def _find_nearby_value(spans: list, ref_index: int,
                       max_distance: int = 5) -> Optional[str]:
    """在参考 span 附近查找数值文本（返回原始字符串）。"""
    ref_y = spans[ref_index]['y0']
    for offset in range(1, max_distance + 1):
        for idx in (ref_index + offset, ref_index - offset):
            if 0 <= idx < len(spans):
                s = spans[idx]
                if abs(s['y0'] - ref_y) < 3:
                    text = s['text'].strip()
                    if re.match(r'^-?\d[\d,]*\.\d{2}$', text):
                        return text
    return None


def _normalize_key(key: str) -> str:
    """规范化 key：统一冒号、移除 NBSP、合并空格。"""
    key = key.replace('\xa0', ' ').replace(' ', '')
    key = key.replace('：', '').replace(':', '')
    return key


def _lookup_header_key(parser, raw_key: str) -> Optional[str]:
    """在 HEADER_KEYS 中查找 key（支持含 NBSP 的变体）。"""
    norm = _normalize_key(raw_key)
    for k, v in parser.HEADER_KEYS.items():
        if _normalize_key(k) == norm:
            return v
    return None


def _extract_closing_balance(parser, footer_spans: list) -> Optional[Decimal]:
    """从页脚区域提取本期余额。"""
    keyword = parser.CLOSING_BALANCE_KEY
    sorted_spans = sorted(footer_spans, key=lambda s: (s['y0'], s['x0']))
    for i, s in enumerate(sorted_spans):
        if keyword in s['text']:
            m = re.search(r'(\d[\d,]*\.\d{2})', s['text'])
            if m:
                return _parse_amount(m.group(1))
            return _find_nearby_number(sorted_spans, i)
    return None


def _find_nearby_number(spans: list, ref_index: int, max_distance: int = 5) -> Optional[Decimal]:
    """在参考 span 附近（同 y 行优先，距离最近次之）查找数值。"""
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


# ═══════════════════════════════════════════════════════════════
# 日期 / 金额 工具函数
# ═══════════════════════════════════════════════════════════════

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
