"""招商银行 (CMB) 交易流水 PDF 解析器

CMB PDF 列式表格格式，每字段独占一行：
    Date (YYYY-MM-DD)
    Currency (CNY)
    Amount (带逗号分隔，可含负号)
    Balance
    Transaction Type (1-2行)
    Counter Party (1-3行)


表头在每页顶部重复：Date \n Currency \n Transaction \n Amount \n Balance \n Transaction Type \n Counter Party
"""
import fitz
import re
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from ..models import Transaction, ParseResult
from .shared_utils import BANK_CMB


class CMBParser:
    """招商银行 PDF 银行流水解析器"""

    BANK_NAME = BANK_CMB

    def __init__(self):
        self.confidence = 1.0

    def parse(self, file_path: str) -> ParseResult:
        """解析招商银行 PDF 流水，传入文件路径"""
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        doc = fitz.open('pdf', pdf_bytes)

        transactions = []
        errors = []
        warnings = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text('text')

            try:
                page_transactions = self._parse_page(text)
                transactions.extend(page_transactions)
            except Exception as e:
                errors.append(f'Page {page_num + 1}: {e}')
                self.confidence -= 0.01

        doc.close()

        # 最后一笔交易日期作为账单日期
        statement_date = transactions[-1].date if transactions else None

        return ParseResult(
            transactions=transactions,
            bank=self.BANK_NAME,
            statement_date=statement_date,
            opening_balance=None,
            closing_balance=None,
            confidence=self.confidence,
            errors=errors,
            warnings=warnings,
        )

    def _parse_page(self, text: str) -> List[Transaction]:
        """解析单页文本，提取交易记录"""
        transactions = []
        lines = text.split('\n')

        # 找到表头后的数据起始位置
        # 表头包含: Date \n Currency \n Transaction \n Amount \n Balance \n Transaction Type \n Counter Party
        data_start = self._find_header_end(lines)

        i = data_start
        while i < len(lines):
            line = lines[i].strip()

            # 跳过空行和页脚（温馨提示、验证码提示等）
            if not line or line.startswith('温馨提示') or 'Verification Code' in line:
                i += 1
                continue

            # 判定是否为新交易行的起点：YYYY-MM-DD
            date_match = re.match(r'^(\d{4}-\d{2}-\d{2})$', line)
            if not date_match:
                i += 1
                continue

            # --- 解析一笔交易（固定字段 + 可变行） ---
            tx_date = datetime.strptime(date_match.group(1), '%Y-%m-%d').date()

            # 下一行：币种（固定 CNV，跳过）
            i += 1
            if i >= len(lines):
                break

            # 金额行（可能有逗号和负号）
            i += 1
            if i >= len(lines):
                break
            amount_str = lines[i].strip()
            # 去除千位分隔符
            clean_amount = amount_str.replace(',', '')
            try:
                amount = Decimal(clean_amount)
            except Exception:
                errors.append(f'Invalid amount: {amount_str}')
                i += 1
                continue

            direction = 'income' if amount > 0 else 'expense'

            # 余额行（跳过）
            i += 1
            if i >= len(lines):
                break

            # --- 可变行：交易类型 + 对方信息 ---
            # 读取剩余行直到下一个日期行空行或页尾
            i += 1
            desc_parts = []
            while i < len(lines):
                line = lines[i].strip()
                # 遇到下一个日期行或空行或页脚，停止收集
                if re.match(r'^\d{4}-\d{2}-\d{2}$', line) or not line:
                    break
                # 跳过仍属于表头的行
                if line in ('Date', 'Currency', 'Transaction', 'Amount', 'Balance',
                            'Transaction Type', 'Counter Party', 'CNY'):
                    i += 1
                    continue
                desc_parts.append(line)
                i += 1

            # desc_parts 结构：第0行=交易类型（如"转账"），后续行=对方名称/账号
            # 摘要只用对方信息部分，不拼交易类型前缀
            transaction_type = desc_parts[0] if desc_parts else ''
            info_parts = desc_parts[1:] if len(desc_parts) > 1 else desc_parts
            description = ' '.join(info_parts) if info_parts else transaction_type

            # 提取对方户名：取最后 1-2 行
            counterparty = None
            if len(info_parts) >= 2:
                counterparty = ' '.join(info_parts[-2:])
            elif len(info_parts) == 1:
                counterparty = info_parts[0]

            transaction = Transaction(
                date=tx_date,
                description=description,
                amount=abs(amount),
                currency='CNY',
                direction=direction,
                counterparty=counterparty,
                reference_number=None,
                notes=None,
            )
            transactions.append(transaction)

        return transactions

    def _find_header_end(self, lines: List[str]) -> int:
        """找到表头结束位置（'Counter Party' 行之后）"""
        for i in range(len(lines) - 5):
            window = [l.strip() for l in lines[i:i + 7]]
            # 查找表头特征序列：Date, Currency, Transaction/Amount, Amount/Balance, ...
            if window[0] == 'Date' and window[1] == 'Currency':
                # 表头在 index i，跳过表头行数
                # Date, Currency, Transaction, Amount, Balance, Transaction Type, Counter Party
                found_counter_party = False
                for j in range(i, min(i + 10, len(lines))):
                    if lines[j].strip() == 'Counter Party':
                        found_counter_party = True
                        return j + 1
                if found_counter_party:
                    return i + 7  # fallback: 跳 7 行
                return i + 7
        return 0  # 未找到表头，从头开始
