"""Tests for parser_router — 快速测试 (无 OCR) + OCR 测试 (--ocr 标记).

默认 `pytest` 只跑快速测试。加 `-m ocr` 跑 OCR 测试。
用法:
    pytest tests/test_parser_router.py -v          # 快速
    pytest tests/test_parser_router.py -v -m ocr   # 仅 OCR
    pytest tests/ -v                               # 全部（含 OCR）
"""
import os
import sys
import time


import pytest
from finance_agent_backend.parser_router import detect_bank_from_pdf, route

# ── Fixture paths ──────────────────────────────────────────────────

BASE = os.path.join(os.path.dirname(__file__), "..", "fixtures")

FIXTURE = {
    "icbc_csv":     os.path.join(BASE, "icbc_statement.csv"),
    "cmb_xlsx":     os.path.join(BASE, "cmb_statement.xlsx"),
    "cmb_pdf":      os.path.join(BASE, "cmb_statement.pdf"),
    "gfb_pdf":      os.path.join(BASE, "gfb_statement.pdf"),
    "icbc_scanned":  os.path.join(BASE, "icbc_statement_scanned.pdf"),
    "cmb_receipt":  os.path.join(BASE, "cmb_receipt.pdf"),
    "icbc_receipt": os.path.join(BASE, "icbc_receipt.pdf"),
}

ocr = pytest.mark.ocr


def _skip_if_missing(*paths):
    for p in paths:
        if not os.path.exists(p):
            pytest.skip(f"文件不存在: {p}")


def _timed(label, func, *args, **kwargs):
    t0 = time.time()
    result = func(*args, **kwargs)
    elapsed = time.time() - t0
    print(f"\n  [{label}] 耗时: {elapsed:.2f}s")
    return result


# ═══════════════════════════════════════════════════════════════════
# detect_bank_from_pdf — 快速 (嵌入式 PDF，无 OCR)
# ═══════════════════════════════════════════════════════════════════

class TestDetectBank:
    def test_cmb_statement(self):
        _skip_if_missing(FIXTURE["cmb_pdf"])
        info = _timed("CMB statement", detect_bank_from_pdf, FIXTURE["cmb_pdf"])
        assert info['bankCode'] == 'CMB'
        assert info['docType'] == '流水'

    def test_gfb_statement(self):
        _skip_if_missing(FIXTURE["gfb_pdf"])
        info = _timed("GFB statement", detect_bank_from_pdf, FIXTURE["gfb_pdf"])
        assert info['bankCode'] == 'GFB'
        assert info['docType'] == '流水'

    def test_cmb_receipt(self):
        _skip_if_missing(FIXTURE["cmb_receipt"])
        info = _timed("CMB receipt", detect_bank_from_pdf, FIXTURE["cmb_receipt"])
        assert info['bankCode'] == 'CMB'
        assert info['docType'] == '回单'


# ═══════════════════════════════════════════════════════════════════
# detect_bank_from_pdf — OCR (扫描件)
# ═══════════════════════════════════════════════════════════════════

class TestDetectBankOCR:
    @ocr
    def test_icbc_scanned(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        info = _timed("ICBC scanned", detect_bank_from_pdf, FIXTURE["icbc_scanned"])
        assert info['bankCode'] == 'ICBC'
        assert info['docType'] == '流水'

    @ocr
    def test_icbc_receipt(self):
        _skip_if_missing(FIXTURE["icbc_receipt"])
        info = _timed("ICBC receipt", detect_bank_from_pdf, FIXTURE["icbc_receipt"])
        assert info['bankCode'] == 'ICBC'
        assert info['docType'] == '回单'

    @ocr
    def test_ocr_reuse_speedup(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        t0 = time.time()
        detect_bank_from_pdf(FIXTURE["icbc_scanned"])
        first = time.time() - t0
        t0 = time.time()
        detect_bank_from_pdf(FIXTURE["icbc_scanned"])
        second = time.time() - t0
        print(f"\n  首次: {first:.1f}s, 二次: {second:.1f}s (x{first/second:.1f})")
        assert second <= first * 1.2


# ═══════════════════════════════════════════════════════════════════
# route — 快速 (CSV / Excel / 嵌入式 PDF)
# ═══════════════════════════════════════════════════════════════════

class TestRouteCSV:
    def test_icbc_csv(self):
        _skip_if_missing(FIXTURE["icbc_csv"])
        r = _timed("ICBC CSV", route, FIXTURE["icbc_csv"])
        assert r["success"] is True
        assert r["bank"] == "中国工商银行"
        assert len(r["transactions"]) >= 30
        assert r["confidence"] >= 0.9


class TestRouteExcel:
    def test_cmb_xlsx(self):
        _skip_if_missing(FIXTURE["cmb_xlsx"])
        r = _timed("CMB Excel", route, FIXTURE["cmb_xlsx"])
        assert r["success"] is True
        assert r["bank"] == "招商银行"
        assert len(r["transactions"]) >= 1


class TestRoutePDF:
    def test_cmb_statement(self):
        _skip_if_missing(FIXTURE["cmb_pdf"])
        r = _timed("CMB statement", route, FIXTURE["cmb_pdf"])
        assert r["success"] is True
        assert "招商银行" in r["bank"]
        assert len(r["transactions"]) >= 1

    def test_gfb_statement(self):
        _skip_if_missing(FIXTURE["gfb_pdf"])
        r = _timed("GFB statement", route, FIXTURE["gfb_pdf"])
        assert r["success"] is True
        assert "广发银行" in r["bank"]
        assert len(r["transactions"]) >= 1

    def test_cmb_receipt(self):
        _skip_if_missing(FIXTURE["cmb_receipt"])
        r = _timed("CMB receipt", route, FIXTURE["cmb_receipt"])
        assert r["success"] is True
        assert "招商银行" in r["bank"]
        assert len(r["transactions"]) >= 3


class TestRouteManualOverride:
    def test_bank_override(self):
        _skip_if_missing(FIXTURE["cmb_pdf"])
        r = _timed("CMB bank override", route, FIXTURE["cmb_pdf"], bank="招商银行")
        assert r["success"] is True
        assert len(r["transactions"]) >= 1

    @ocr
    def test_bank_doctype_override(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        r = _timed("ICBC bank+docType override", route, FIXTURE["icbc_scanned"],
                   bank="工商银行", doc_type="流水")
        assert r["success"] is True
        assert r["bank"] == "中国工商银行"
        assert len(r["transactions"]) >= 10


# ═══════════════════════════════════════════════════════════════════
# route — OCR (扫描件)
# ═══════════════════════════════════════════════════════════════════

class TestRouteOCR:
    @ocr
    def test_icbc_scanned(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        r = _timed("ICBC scanned", route, FIXTURE["icbc_scanned"])
        assert r["success"] is True
        assert r["bank"] == "中国工商银行"
        assert len(r["transactions"]) >= 10
        assert r["confidence"] >= 0.9

    @ocr
    def test_icbc_receipt(self):
        _skip_if_missing(FIXTURE["icbc_receipt"])
        r = _timed("ICBC receipt", route, FIXTURE["icbc_receipt"])
        assert r["success"] is True
        assert "工商银行" in r["bank"]
        assert len(r["transactions"]) >= 1


# ═══════════════════════════════════════════════════════════════════
# ICBC Parser 详细验证 — OCR
# ═══════════════════════════════════════════════════════════════════

from finance_agent_backend.tools.icbc_parser import ICBCParser
from datetime import date
from decimal import Decimal


class TestICBCParser:
    @ocr
    def test_parse_result(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        r = ICBCParser().parse(FIXTURE["icbc_scanned"])
        assert r.bank == "中国工商银行"
        assert r.confidence > 0.9
        assert r.errors == []

    @ocr
    def test_count(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        assert len(ICBCParser().parse(FIXTURE["icbc_scanned"]).transactions) == 20

    @ocr
    def test_first_transaction(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        tx = ICBCParser().parse(FIXTURE["icbc_scanned"]).transactions[0]
        assert tx.date == date(2026, 3, 5)
        assert tx.amount == Decimal("799.00")
        assert tx.direction == "expense"
        assert tx.counterparty == "中国电信股份有限公司广州分公司"

    @ocr
    def test_last_transaction(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        tx = ICBCParser().parse(FIXTURE["icbc_scanned"]).transactions[-1]
        assert tx.date == date(2026, 3, 30)
        assert tx.amount == Decimal("22655.00")

    @ocr
    def test_income_count(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        txns = ICBCParser().parse(FIXTURE["icbc_scanned"]).transactions
        income = [t for t in txns if t.direction == "income"]
        assert len(income) == 5
        assert income[2].date == date(2026, 3, 17)
        assert income[2].amount == Decimal("17143.00")
        assert "采购结算单" in income[2].description

    @ocr
    def test_statement_date(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        r = ICBCParser().parse(FIXTURE["icbc_scanned"])
        assert r.statement_date == date(2026, 3, 30)

    @ocr
    def test_all_fields(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        for tx in ICBCParser().parse(FIXTURE["icbc_scanned"]).transactions:
            assert tx.date is not None
            assert tx.amount is not None
            assert tx.direction in ("income", "expense")

    @ocr
    def test_balance_chain(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        balances = []
        for tx in ICBCParser().parse(FIXTURE["icbc_scanned"]).transactions:
            if tx.notes:
                try: balances.append(Decimal(tx.notes.replace(",", "")))
                except Exception: pass
        assert len(balances) > 10
        assert balances[0] == Decimal("14255.94")
        assert balances[-1] == Decimal("20334.82")

    @ocr
    def test_refs_clean(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        for tx in ICBCParser().parse(FIXTURE["icbc_scanned"]).transactions:
            if tx.reference_number:
                assert "|" not in tx.reference_number

    @ocr
    def test_counterparty_no_bleed(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        for tx in ICBCParser().parse(FIXTURE["icbc_scanned"]).transactions:
            if tx.counterparty:
                assert len(tx.counterparty) >= 2


# ═══════════════════════════════════════════════════════════════════
# Bridge JSON-RPC 回归
# ═══════════════════════════════════════════════════════════════════

from finance_agent_backend.bridge import handle_request


class TestBridge:
    def test_unknown_method(self):
        r = handle_request({"jsonrpc": "2.0", "method": "nonexistent", "params": {}, "id": 2})
        assert r["error"]["code"] == -32601

    def test_parse_pdf_missing_path(self):
        r = handle_request({"jsonrpc": "2.0", "method": "parse_pdf", "params": {}, "id": 3})
        assert r["result"]["success"] is False
        assert "filePath" in r["result"]["error"]

    def test_parse_pdf_nonexistent(self):
        r = handle_request({"jsonrpc": "2.0", "method": "parse_pdf",
                            "params": {"filePath": r"C:\nonexistent\file.pdf"}, "id": 4})
        assert r["result"]["success"] is False

    def test_generate_excel_missing_txns(self):
        r = handle_request({"jsonrpc": "2.0", "method": "generate_excel", "params": {}, "id": 5})
        assert r["result"]["success"] is False
        assert "transactions" in r["result"]["error"]

    @ocr
    def test_parse_pdf_icbc(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        r = handle_request({"jsonrpc": "2.0", "method": "parse_pdf",
                            "params": {"filePath": FIXTURE["icbc_scanned"]}, "id": 1})
        assert r["result"]["success"] is True
        assert r["result"]["bank"] == "中国工商银行"
        assert len(r["result"]["transactions"]) == 20

    @ocr
    def test_generate_excel(self):
        _skip_if_missing(FIXTURE["icbc_scanned"])
        pr = handle_request({"jsonrpc": "2.0", "method": "parse_pdf",
                              "params": {"filePath": FIXTURE["icbc_scanned"]}, "id": 1})
        import tempfile as _tmp
        with _tmp.TemporaryDirectory() as d:
            out = os.path.join(d, "export.xlsx")
            r = handle_request({"jsonrpc": "2.0", "method": "generate_excel",
                                "params": {"transactions": pr["result"]["transactions"],
                                           "output_path": out}, "id": 2})
            assert r["result"]["success"] is True
            assert os.path.exists(out)
            assert os.path.getsize(out) > 1000


# ═══════════════════════════════════════════════════════════════════
# CMB openingBalance 回归
# ═══════════════════════════════════════════════════════════════════

def test_cmb_opening_balance_is_number():
    _skip_if_missing(FIXTURE["cmb_pdf"])
    r = route(FIXTURE["cmb_pdf"])
    assert r["success"] is True
    assert r["openingBalance"] is not None
    assert isinstance(r["openingBalance"], (int, float)), \
        f"openingBalance type={type(r['openingBalance'])}"
    assert r["openingBalance"] > 0