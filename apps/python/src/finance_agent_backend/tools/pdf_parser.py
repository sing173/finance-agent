"""Bank statement PDF parser using PyMuPDF"""
import fitz  # PyMuPDF
import re
import html
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
        # fitz.open() 底层 mupdf C 库在 Windows 上不处理 Unicode 路径
        # 先以二进制读入内存，再以字节流方式打开，绕过路径编码问题
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        doc = fitz.open("pdf", pdf_bytes)
        transactions = []

        # 自动识别银行（如果未指定）
        if not bank:
            bank = self._detect_bank(doc)

        # 按页解析 - 使用 HTML 提取以正确获取中文
        for page_num in range(len(doc)):
            page = doc[page_num]
            # 使用 HTML 方式提取文本，避免 Windows 中文字体提取乱码问题
            html_text = page.get_text("html")
            text = self._html_to_text(html_text)
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
            # 使用 HTML 提取避免中文字体问题
            html_text = doc[i].get_text("html")
            sample_text += self._html_to_text(html_text)

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
                        remaining = line.replace(date_match.group(0), '').replace(amount_match.group(0), '').strip()
                        if not remaining:
                            remaining = '银行交易'

                        # 根据方向符号(+/-)分割剩余文本
                        # 格式通常是：描述(多个空格)金额(多个空格)对方户名
                        # 或者是：描述(多个空格)对方户名(多个空格)金额(已被移除)
                        # 金额已被移除，所以剩余的是：描述 对方户名
                        # 策略：取最后1-2个单词作为对方户名，其余作为描述
                        parts = remaining.split()
                        if len(parts) >= 2:
                            # 对方户名通常是单个词或两个词（如 "Bank of China"）
                            # 尝试：如果最后两个词可以组成有意义的名称（首字母大写），则取最后2个
                            # 否则取最后1个
                            if len(parts) >= 3 and parts[-2][0].isupper() and parts[-1][0].isupper():
                                counterparty = parts[-2] + ' ' + parts[-1]
                                desc = ' '.join(parts[:-2])
                            else:
                                counterparty = parts[-1]
                                desc = ' '.join(parts[:-1])
                        else:
                            desc = remaining
                            counterparty = None

                        if not desc:
                            desc = '银行交易'

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

    def _html_to_text(self, html_text: str) -> str:
        """将 PyMuPDF 的 HTML 输出转换为纯文本"""
        import re
        # 提取所有 span 标签中的文本
        spans = re.findall(r'<span[^>]*>([^<]+)</span>', html_text)
        # HTML 实体解码
        decoded = [html.unescape(s) for s in spans]
        # 合并并清理多余空格
        return '\n'.join(decoded)
