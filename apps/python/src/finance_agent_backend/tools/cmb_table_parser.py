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
from .shared_utils import (
    BANK_CMB, parse_date_yyyymmdd, parse_amount,
    extract_all_spans, cluster_by_y,
    find_table_region, partition_spans,
    find_nearby_number,
)


class CMBTableParser:
    """招商银行 账务明细清单（水平表格格式）解析器"""

    BANK_NAME = BANK_CMB

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
        all_spans = extract_all_spans(page)
        doc.close()

        # 步骤 4: 按 y 坐标将页面分为表头 / 表格 / 页脚三个区域
        header_spans, table_spans, footer_spans = _partition_spans_cmb(all_spans)
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
        rows = cluster_by_y(spans, gap=2.5)
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

        tx_date = parse_date_yyyymmdd(date_str)
        if not tx_date:
            return None
        amount = parse_amount(amount_str)
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
        balance = parse_amount(balance_str) if balance_str else None

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
# CMB-specific wrappers around shared_utils (thin, bank-specific config only)
# ═══════════════════════════════════════════════════════════════

def _partition_spans_cmb(spans: list) -> Tuple[list, list, list]:
    """CMB table partitioning: column titles match '交易日期'/'Date'/'日期'."""
    COL_TITLES = ['交易日期', 'Date', '日期']
    return partition_spans(spans, COL_TITLES, require_all=False)


def _parse_header_metadata(header_spans: list) -> Dict[str, Any]:
    """Extract account metadata from CMB header spans."""
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
        meta['opening_balance'] = parse_amount(meta.pop(CMBTableParser.OPENING_BALANCE_KEY))
    if 'period' in meta:
        parts = meta['period'].split()
        if len(parts) >= 1:
            meta['period_start'] = parts[0]
        if len(parts) >= 2:
            meta['period_end'] = parts[1]
    return meta


def _extract_closing_balance(footer_spans: list) -> Optional[Decimal]:
    """Extract CMB closing balance from footer spans."""
    keyword = CMBTableParser.CLOSING_BALANCE_KEY
    sorted_spans = sorted(footer_spans, key=lambda s: (s['y0'], s['x0']))
    for i, s in enumerate(sorted_spans):
        if keyword in s['text']:
            m = re.search(r'(\d[\d,]*\.\d{2})', s['text'])
            if m:
                return parse_amount(m.group(1))
            return find_nearby_number(sorted_spans, i)
    return None
