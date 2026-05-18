"""工商银行 (ICBC) CSV 对账流水解析器

处理工商银行导出的对账流水 CSV 文件（Tab/逗号分隔混合格式）。

CSV 格式特点：
- 文件编码：GBK
- 分隔符：逗号（字段值内可能含 Tab 字符）
- 第 1 行：[HISTORYDETAIL] 标记
- 第 2 行：列名（凭证号, 本方账号, 对方账号, 交易时间, 起息日, 借/贷, ...）
- 第 3 行起：数据行

列映射：
- 起息日 → date
- 借/贷 → direction（借=expense, 贷=income）
- 借方发生额 → debit_amount
- 贷方发生额 → credit_amount
- 对方单位名称 → counterparty
- 摘要 → description
- 余额 → balance
"""
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Dict, Any

from ..models import Transaction, ParseResult
from .shared_utils import BANK_ICBC, parse_date_iso, parse_amount


class ICBCCSVParser:
    """工商银行 CSV 对账流水解析器"""

    BANK_NAME = BANK_ICBC

    # CSV 列名
    COLUMNS = [
        '凭证号', '本方账号', '对方账号', '交易时间', '起息日', '借/贷',
        '借方发生额', '贷方发生额', '对方行号', '摘要', '附言', '用途',
        '对方单位名称', '余额'
    ]

    def __init__(self):
        self.confidence = 1.0

    def parse(self, file_path: str) -> ParseResult:
        """解析 ICBC CSV 对账流水"""
        rows = self._read_csv(file_path)
        if not rows:
            return ParseResult(
                transactions=[], bank=self.BANK_NAME,
                confidence=0, errors=['No data found in CSV']
            )

        transactions, errors = self._parse_rows(rows)
        transactions.sort(key=lambda t: t.date)

        # 提取账户信息
        account_no = rows[0].get('本方账号', '') if rows else ''

        # 期初/期末余额
        opening_balance = None
        closing_balance = None
        if rows:
            bal = self._parse_amount(rows[0].get('余额', ''))
            if bal is not None:
                opening_balance = bal
            bal = self._parse_amount(rows[-1].get('余额', ''))
            if bal is not None:
                closing_balance = bal

        # 账单日期
        statement_date = transactions[-1].date if transactions else None

        return ParseResult(
            transactions=transactions,
            bank=self.BANK_NAME,
            statement_date=statement_date,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            confidence=self.confidence,
            errors=errors,
            warnings=[],
        )

    def _read_csv(self, file_path: str) -> List[Dict[str, str]]:
        """读取 CSV 文件，返回清理后的行列表"""
        rows = []
        with open(file_path, 'r', encoding='gbk') as f:
            reader = csv.DictReader(f, fieldnames=self.COLUMNS)
            for row in reader:
                # 跳过标题行
                if row['凭证号'] == '[HISTORYDETAIL]' or row['凭证号'] == '凭证号':
                    continue
                # 清理字段值（去除 Tab、空白等）
                cleaned = {k: self._clean(v) for k, v in row.items()}
                rows.append(cleaned)
        return rows

    @staticmethod
    def _parse_date(text: str) -> Optional[datetime.date]:
        return parse_date_iso(text)

    @staticmethod
    def _parse_amount(text: str) -> Optional[Decimal]:
        return parse_amount(text)

    def _parse_rows(self, rows: List[Dict[str, str]]) -> tuple[List[Transaction], List[str]]:
        """解析所有数据行"""
        transactions = []
        errors = []

        for i, row in enumerate(rows):
            try:
                tx = self._row_to_transaction(row)
                if tx:
                    transactions.append(tx)
            except Exception as e:
                errors.append(f'Row {i}: {e}')
                self.confidence -= 0.01

        return transactions, errors

    def _row_to_transaction(self, row: Dict[str, str]) -> Optional[Transaction]:
        """将一行 CSV 数据转换为 Transaction 对象"""
        date_str = row.get('起息日', '').strip()
        if not date_str:
            return None

        tx_date = self._parse_date(date_str)
        if not tx_date:
            return None

        direction = row.get('借/贷', '').strip()
        debit = self._parse_amount(row.get('借方发生额', ''))
        credit = self._parse_amount(row.get('贷方发生额', ''))

        if direction == '借':
            amount = debit if debit else Decimal('0')
            dir_ = 'expense'
        elif direction == '贷':
            amount = credit if credit else Decimal('0')
            dir_ = 'income'
        else:
            return None  # 无效的借贷标志

        # 构建描述
        desc_parts = []
        summary = row.get('摘要', '').strip()
        if summary:
            desc_parts.append(summary)

        remark = row.get('附言', '').strip()
        if remark:
            desc_parts.append(f'附言:{remark}')

        description = ' | '.join(desc_parts) if desc_parts else '银行交易'

        # 对方户名
        counterparty = row.get('对方单位名称', '').strip() or None

        # 余额
        balance = self._parse_amount(row.get('余额', ''))

        # 对方账号（作为参考号）
        ref_no = row.get('对方账号', '').strip() or None

        # 本方账号（作为 account_number）
        account_no = row.get('本方账号', '').strip() or None

        return Transaction(
            date=tx_date,
            description=description,
            amount=amount,
            currency='CNY',
            direction=dir_,
            counterparty=counterparty,
            reference_number=ref_no,
            notes=f'余额:{balance}' if balance else None,
            account_number=account_no,
        )

    @staticmethod
    def _clean(val: str) -> str:
        """清理字段值"""
        if not val:
            return ''
        return val.strip().replace('\t', '').replace('\r', '').replace('\n', '')

