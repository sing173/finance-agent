"""Data models for finance-agent backend"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict


@dataclass
class Transaction:
    date: date
    description: str
    amount: Decimal
    currency: str = 'CNY'
    direction: str = 'expense'  # 'income' or 'expense'
    counterparty: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None


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
