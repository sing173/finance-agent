"""BaseStatementParser — 工具类基类，为所有 bank statement / receipt parser 提供通用工具方法。

设计原则（工具类 + 子类自由实现）：
  - 基类只提供辅助工具，不强制 Template Method
  - parse() 完全由子类自行实现
  - 适用于 PDF parser、CSV parser、Excel parser 等各种格式
  - 重型依赖（OCR / openpyxl）由子类自行 import，基类保持零额外依赖
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import fitz

from ..models import ParseResult, Transaction


class BaseStatementParser:
    """Base class providing shared utility methods for bank statement parsers.

    Subclasses should:
    1. Set BANK_NAME at class level.
    2. Implement parse(file_path, ...) returning a ParseResult.
    3. Use _read_pdf_bytes() and _build_result() as needed.
    """

    BANK_NAME: str = ""

    # ------------------------------------------------------------------
    # PDF I/O
    # ------------------------------------------------------------------

    @staticmethod
    def _read_pdf_bytes(file_path: str) -> bytes:
        """Read a PDF file as raw bytes. Bypasses Windows Unicode path issues
        in mupdf."""
        with open(file_path, 'rb') as f:
            return f.read()

    @staticmethod
    def _open_pdf(file_path: str) -> fitz.Document:
        """Open a PDF via bytes (Unicode-safe on Windows)."""
        return fitz.open('pdf', BaseStatementParser._read_pdf_bytes(file_path))

    # ------------------------------------------------------------------
    # ParseResult / Transaction builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_result(
        *,
        bank: str | None = None,
        transactions: List[Transaction] | None = None,
        statement_date: date | None = None,
        opening_balance: Decimal | None = None,
        closing_balance: Decimal | None = None,
        confidence: float = 1.0,
        errors: List[str] | None = None,
        warnings: List[str] | None = None,
    ) -> ParseResult:
        """Build a ParseResult with defaults sourced from BANK_NAME / empty lists."""
        return ParseResult(
            transactions=transactions or [],
            bank=bank or '',
            statement_date=statement_date,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            confidence=confidence,
            errors=errors or [],
            warnings=warnings or [],
        )

    @staticmethod
    def _build_transaction(
        date: date,
        description: str,
        amount: Decimal,
        *,
        currency: str = 'CNY',
        direction: str = 'expense',
        counterparty: str | None = None,
        reference_number: str | None = None,
        notes: str | None = None,
        account_number: str | None = None,
        account_name: str | None = None,
    ) -> Transaction:
        """Build a Transaction with common defaults."""
        return Transaction(
            date=date,
            description=description,
            amount=amount,
            currency=currency,
            direction=direction,
            counterparty=counterparty,
            reference_number=reference_number,
            notes=notes,
            account_number=account_number,
            account_name=account_name,
        )

    # ------------------------------------------------------------------
    # Date / amount parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(text: str) -> Optional[date]:
        """Parse YYYY-MM-DD / YYYYMMDD / YYYY年M月D日."""
        text = text.strip()
        for fmt in ('%Y-%m-%d', '%Y%m%d'):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})', text)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        return None

    @staticmethod
    def _parse_amount(text: str) -> Optional[Decimal]:
        """Parse an amount string to Decimal. Returns None on failure."""
        text = text.strip().replace(',', '').replace(' ', '')
        try:
            return Decimal(text)
        except (InvalidOperation, Exception):
            return None

    @staticmethod
    def _parse_amount_lenient(text: str) -> Decimal:
        """Parse amount with ￥/元 stripping. Returns Decimal('0') on failure."""
        if not text:
            return Decimal('0')
        text = text.replace('￥', '').replace('元', '').strip()
        text = text.replace(',', '').replace('，', '').replace(' ', '')
        m = re.search(r'[\d,]+\.?\d*', text)
        if m:
            return Decimal(m.group().replace(',', ''))
        return Decimal('0')
