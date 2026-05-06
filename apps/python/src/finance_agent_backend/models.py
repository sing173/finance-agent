"""Data models for finance-agent backend"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional


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
class ReconcileResult:
    matched: List[dict]
    bank_unreconciled: List[Transaction]
    ledger_unreconciled: List[Transaction]
    suspicious: List[dict]
    total_bank: int = 0
    total_ledger: int = 0
    match_rate: float = 0.0
