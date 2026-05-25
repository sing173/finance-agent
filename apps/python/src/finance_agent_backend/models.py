"""Data models for finance-agent backend"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Literal


@dataclass
class Transaction:
    date: date
    description: str
    amount: Decimal
    currency: str = 'CNY'
    direction: Literal['income', 'expense'] = 'expense'
    counterparty: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'date': self.date.isoformat(),
            'description': self.description,
            'amount': float(self.amount),
            'currency': self.currency,
            'direction': self.direction,
            'counterparty': self.counterparty,
            'reference_number': self.reference_number,
            'notes': self.notes,
            'account_number': self.account_number,
            'account_name': self.account_name,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'Transaction':
        return cls(
            date=datetime.strptime(d['date'], '%Y-%m-%d').date(),
            description=d.get('description', ''),
            amount=Decimal(str(d.get('amount', 0))),
            currency=d.get('currency', 'CNY'),
            direction=d.get('direction', 'expense'),
            counterparty=d.get('counterparty'),
            reference_number=d.get('reference_number'),
            notes=d.get('notes'),
            account_number=d.get('account_number'),
            account_name=d.get('account_name'),
        )


@dataclass
class ParseResult:
    transactions: List[Transaction]
    bank: str
    statement_date: Optional[date] = None
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    confidence: float = 1.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """序列化为 JSON-RPC 兼容字典（camelCase 字段名）。"""
        return {
            "success": True,
            "transactions": [t.to_dict() for t in self.transactions],
            "bank": self.bank,
            "statementDate": self.statement_date.isoformat() if self.statement_date else None,
            "openingBalance": float(self.opening_balance) if self.opening_balance else None,
            "closingBalance": float(self.closing_balance) if self.closing_balance else None,
            "confidence": self.confidence,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class Subject:
    """会计科目"""
    code: str                    # 科目编码，如 '1000201'
    name: str                    # 科目名称，如 '工商银行（4363）'
    category: str = ''           # 类别，如 '流动资产'
    direction: str = '借'         # 余额方向：借 / 贷
    aux_category: str = ''       # 辅助核算类别，如 '客户'、'供应商'
    is_cash: bool = False        # 是否现金科目
    enabled: bool = True         # 是否启用
    full_name: str = ''          # 完整层级名称，如 '银行存款_工商银行（4363）'，由 SubjectLoader 填充


@dataclass
class VoucherEntry:
    """凭证分录（对应凭证导入模板的一行）"""
    date: date                                        # A: 日期
    voucher_word: str = '记'                           # B: 凭证字
    voucher_no: int = 1                               # C: 凭证号
    attachment_count: int = 0                         # D: 附件数
    entry_seq: int = 1                                # E: 分录序号
    summary: str = ''                                 # F: 摘要
    subject_code: str = ''                            # G: 科目代码
    subject_name: str = ''                            # H: 科目名称
    debit_amount: Optional[Decimal] = None            # I: 借方金额
    credit_amount: Optional[Decimal] = None           # J: 贷方金额
    customer: str = ''                                # K: 客户
    supplier: str = ''                                # L: 供应商
    employee: str = ''                                # M: 职员
    project: str = ''                                 # N: 项目
    department: str = ''                              # O: 部门（当前留空）
    inventory: str = ''                               # P: 存货
    custom_aux_category: str = ''                     # Q: 自定义辅助核算类别
    custom_aux_code: str = ''                         # R: 自定义辅助核算编码
    custom_aux_category1: str = ''                    # S: 自定义辅助核算类别1
    custom_aux_code1: str = ''                        # T: 自定义辅助核算编码1
    quantity: Optional[Decimal] = None                # U: 数量
    unit_price: Optional[Decimal] = None              # V: 单价
    original_amount: Optional[Decimal] = None         # W: 原币金额
    currency: str = 'RMB'                             # X: 币别
    exchange_rate: Decimal = field(default_factory=lambda: Decimal('1.0'))  # Y: 汇率


@dataclass
class AccountEntry:
    """账号-科目映射条目"""
    id: str                          # 自动生成（时间戳）
    matchType: str                   # 'suffix' | 'exact'
    pattern: str                     # 匹配用的账号片段
    bank: str                        # 银行中文名
    bankCode: str                    # ICBC / CMB / GFB
    subjectCode: str                 # 会计科目代码
    subjectName: str                 # 科目全名
