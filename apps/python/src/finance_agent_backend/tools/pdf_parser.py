"""Bank statement PDF parser using PyMuPDF"""
import fitz  # PyMuPDF
import re
from datetime import datetime
from typing import List, Optional
from decimal import Decimal

from ..models import Transaction, ParseResult


class BankStatementParser:
    """银行流水解析器"""

    SUPPORTED_BANKS = ['中国银行', '招商银行', '工商银行', '建设银行']

    def __init__(self):
        self.confidence = 1.0

    def parse(self, file_path: str, bank: Optional[str] = None) -> ParseResult:
        """解析 PDF 银行流水"""
        doc = fitz.open(file_path)
        transactions = []

        # 自动识别银行（如果未指定）
        if not bank:
            bank = self._detect_bank(doc)

        # 按页解析
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            page_transactions = self._parse_page(text, bank)
            transactions.extend(page_transactions)

        doc.close()

        # 提取账单日期（最后一笔交易日期）
        statement_date = transactions[-1].date if transactions else None

        return ParseResult(
            transactions=transactions,
            bank=bank,
            statement_date=statement_date,
            opening_balance=None,
            closing_balance=None,
            confidence=self.confidence,
            errors=[],
            warnings=[],
        )

    def _detect_bank(self, doc) -> str:
        """通过前 3 页文本识别银行"""
        sample_text = ''
        for i in range(min(3, len(doc))):
            sample_text += doc[i].get_text()

        for bank in self.SUPPORTED_BANKS:
            if bank in sample_text:
                return bank
        return '未知银行'

    def _parse_page(self, text: str, bank: str) -> List[Transaction]:
        """解析单页文本，提取交易记录"""
        transactions = []
        lines = text.split('\n')

        # 通用正则：匹配日期 + 金额 + 描述
        # 支持格式：2024-01-01, 2024/01/01, 20240101
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{4}/\d{2}/\d{2})',
            r'(\d{8})',
        ]

        amount_pattern = r'([\+\-]?\d+\.\d{2})'

        for line in lines:
            for dp in date_patterns:
                date_match = re.search(dp, line)
                amount_match = re.search(amount_pattern, line)
                if date_match and amount_match:
                    date_str = date_match.group(1)
                    amount_str = amount_match.group(1)

                    # 标准化日期
                    try:
                        if '-' in date_str:
                            tx_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        elif '/' in date_str:
                            tx_date = datetime.strptime(date_str, '%Y/%m/%d').date()
                        else:
                            tx_date = datetime.strptime(date_str, '%Y%m%d').date()

                        amount = Decimal(amount_str)
                        direction = 'income' if amount > 0 else 'expense'

                        # 提取描述（去除日期和金额后的剩余文本）
                        desc = line.replace(date_match.group(0), '').replace(amount_match.group(0), '').strip()
                        if not desc:
                            desc = '银行交易'

                        counterparty = self._extract_counterparty(desc)

                        transaction = Transaction(
                            date=tx_date,
                            description=desc,
                            amount=abs(amount),
                            currency='CNY',
                            direction=direction,
                            counterparty=counterparty,
                            reference_number=None,
                            notes=None,
                        )
                        transactions.append(transaction)
                    except Exception:
                        self.confidence -= 0.01
                    break

        return transactions

    def _extract_counterparty(self, description: str) -> Optional[str]:
        """从描述中提取对方户名（简化实现）"""
        if not description:
            return None
        return description[:50] if len(description) > 50 else description
