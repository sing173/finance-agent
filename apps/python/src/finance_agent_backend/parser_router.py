"""Parser router — file-extension-aware dispatch to the correct parser.

Replaces the 110-line routing chain inside bridge.py's handle_parse_pdf.
All heavy parser modules are imported lazily; only the needed one loads.
"""
from __future__ import annotations

import os
import time
import fitz  # lightweight enough to import eagerly

from finance_agent_backend.models import Transaction, ParseResult

# ---------------------------------------------------------------------------
# Bank / doc-type detection
# ---------------------------------------------------------------------------

BANK_KEYWORDS = {
    '招商银行': ['招商银行', 'China Merchants Bank'],
    '工商银行': ['工商银行', 'ICBC'],
    '中国银行': ['中国银行', 'Bank of China'],
    '建设银行': ['建设银行', 'China Construction Bank'],
    '广发银行': ['广发银行', '广东发展银行', 'CGB'],
}


def detect_bank_from_pdf(file_path: str) -> tuple[str, str]:
    """Detect bank name and document type from a PDF's embedded text.

    Returns (bank, doc_type).  Falls back to ('未知银行', 'unknown') on error.
    """
    def _classify(sample: str) -> tuple[str, str]:
        bank = '未知银行'
        for name, kws in BANK_KEYWORDS.items():
            if any(kw in sample for kw in kws):
                bank = name
                break

        doc_type = 'unknown'
        sample_no_space = sample.replace(' ', '')
        if ('出账回单' in sample_no_space or '入账回单' in sample_no_space
                or '电子回单' in sample or '网上银行电子回单' in sample):
            doc_type = 'receipt'
        elif ('交易流水' in sample or '明细清单' in sample
                or '对账单' in sample):
            doc_type = 'statement'
        elif '日期' in sample and '金额' in sample and '余额' in sample:
            doc_type = 'statement'

        return bank, doc_type

    try:
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        doc = fitz.open('pdf', pdf_bytes)
        sample = ''
        for i in range(min(3, len(doc))):
            sample += doc[i].get_text('text')
        doc.close()

        if sample.strip():
            return _classify(sample)
        return '未知银行', 'unknown'
    except Exception:
        return '未知银行', 'unknown'


def detect_cmb_pdf_type(file_path: str) -> str:
    """Return 'table' (账务明细清单) or 'column' (old columnar format)."""
    TABLE_TITLES = ['账务明细清单', 'Statement Of Account',
                    'Statement of Account', 'STATEMENT OF ACCOUNT']
    try:
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        doc = fitz.open('pdf', pdf_bytes)
        text = doc[0].get_text('text')
        doc.close()
        for title in TABLE_TITLES:
            if title in text:
                return 'table'
    except Exception:
        pass
    return 'column'


# ---------------------------------------------------------------------------
# ParseResult → dict serialisation
# ---------------------------------------------------------------------------

def _serialize_result(result: ParseResult) -> dict:
    """Convert a ParseResult dataclass to a JSON-safe dict."""
    return {
        "success": True,
        "transactions": [_serialize_txn(t) for t in result.transactions],
        "bank": result.bank,
        "statementDate": result.statement_date.isoformat() if result.statement_date else None,
        "openingBalance": float(result.opening_balance) if result.opening_balance else None,
        "closingBalance": float(result.closing_balance) if result.closing_balance else None,
        "confidence": result.confidence,
        "errors": result.errors,
        "warnings": result.warnings,
    }


def _serialize_txn(t: Transaction) -> dict:
    return {
        "date": t.date.isoformat(),
        "description": t.description,
        "amount": float(t.amount),
        "currency": t.currency,
        "direction": t.direction,
        "counterparty": t.counterparty,
        "reference_number": t.reference_number,
        "notes": t.notes,
        "account_number": t.account_number,
        "account_name": t.account_name,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def route(file_path: str, bank: str | None = None) -> dict:
    """Route *file_path* to the correct parser and return a JSON-safe dict.

    Dispatches on file extension:
    - ``.xlsx``  → CMB Excel parser
    - ``.csv``   → ICBC CSV parser
    - ``.pdf``   → bank-detection → bank-specific PDF parser → generic fallback

    The *bank* parameter (if provided) skips bank detection for PDF files.
    """
    # --- xlsx (CMB Excel) ---
    if file_path.lower().endswith('.xlsx'):
        return _do_parse_cmb_excel(file_path)

    # --- csv (ICBC CSV) ---
    if file_path.lower().endswith('.csv'):
        return _do_parse_icbc_csv(file_path)

    # --- pdf ---
    return _do_parse_pdf(file_path, bank=bank)


# ---------------------------------------------------------------------------
# Format-specific handlers (lazy-import their parser modules)
# ---------------------------------------------------------------------------

def _do_parse_cmb_excel(file_path: str) -> dict:
    from finance_agent_backend.tools import cmb_excel_parser
    try:
        parser = cmb_excel_parser.CMBExcelParser()
        result = parser.parse(file_path)
        return _serialize_result(result)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _do_parse_icbc_csv(file_path: str) -> dict:
    from finance_agent_backend.tools import icbc_csv_parser
    try:
        parser = icbc_csv_parser.ICBCCSVParser()
        result = parser.parse(file_path)
        return _serialize_result(result)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _do_parse_pdf(file_path: str, bank: str | None = None) -> dict:
    from finance_agent_backend.tools import (
        icbc_receipt_grid_parser,
        icbc_parser,
        cmb_receipt_parser,
        cmb_table_parser,
        cmb_parser,
        gfb_table_parser,
        pdf_parser,
    )

    if not bank:
        bank, doc_type = detect_bank_from_pdf(file_path)
    else:
        doc_type = 'unknown'

    # Routing strategy (mirrors original handle_parse_pdf logic):
    #   receipt / unknown / ICBC-not-clear -> try receipt grid first
    #   ICBC clear statement -> ICBCParser
    #   CMB -> CMBTableParser / CMBParser (by subtype)
    #   GFB -> GFBTableParser
    #   unknown -> generic BankStatementParser

    result: ParseResult | None = None  # must be initialised before use

    def _has_result(r):
        return r is not None and r.transactions

    try_receipt_first = (
        doc_type == 'receipt'
        or bank == '未知银行'
        or ('工商' in (bank or '') and doc_type != 'statement')
    )
    if try_receipt_first:
        t0 = time.time()
        try:
            result = icbc_receipt_grid_parser.ICBCReceiptGridParser().parse(file_path)
        except Exception:
            result = None
        _log_route('ICBC 回单网格', result, t0)

    if not _has_result(result):
        if '工商' in (bank or '') or bank == '未知银行':
            t0 = time.time()
            try:
                result = icbc_parser.ICBCParser().parse(file_path)
            except Exception:
                result = None
            _log_route('ICBC 流水', result, t0)

    if not _has_result(result):
        if '招商' in (bank or ''):
            if doc_type == 'receipt':
                t0 = time.time()
                try:
                    result = cmb_receipt_parser.CMBReceiptParser().parse(file_path)
                except Exception:
                    result = None
                label = '招行回单'
            else:
                cmb_type = detect_cmb_pdf_type(file_path)
                p = (cmb_table_parser.CMBTableParser()
                     if cmb_type == 'table'
                     else cmb_parser.CMBParser())
                t0 = time.time()
                try:
                    result = p.parse(file_path)
                except Exception:
                    result = None
                label = f'招行({cmb_type})'
            _log_route(label, result, t0)

    if not _has_result(result):
        if '广发' in (bank or ''):
            t0 = time.time()
            try:
                result = gfb_table_parser.GFBTableParser().parse(file_path)
            except Exception:
                result = None
            _log_route('广发', result, t0)

    if not _has_result(result):
        t0 = time.time()
        try:
            result = pdf_parser.BankStatementParser().parse(file_path, bank)
        except Exception:
            result = None
        _log_route('通用', result, t0)

    if result is None:
        return {"success": False, "error": "解析失败：所有解析器均无法处理该文件"}

    return _serialize_result(result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_route(label: str, result: ParseResult | None, t0: float,
               logger=None) -> None:
    """Log routing decision. Accepts an optional logger; falls back to print."""
    count = len(result.transactions) if result else 0
    elapsed = time.time() - t0
    msg = f"{label}: {count} 条, {elapsed:.1f}s"
    if logger:
        try:
            logger.info("%s: %d 条, 耗时 %.1fs", label, count, elapsed)
            return
        except Exception:
            pass
    print(f"[router] {msg}")
