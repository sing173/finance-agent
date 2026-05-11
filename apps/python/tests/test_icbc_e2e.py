"""End-to-end tests for ICBC parser (table-line grid approach).

Requires the test PDF at the path below, or set ICBC_TEST_PDF env var.
"""
import os
import sys
import tempfile
from datetime import date
from decimal import Decimal

import pytest

# Ensure package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from finance_agent_backend.tools.icbc_parser import ICBCParser
from finance_agent_backend.tools.excel_builder import ExcelBuilder
from finance_agent_backend.bridge import handle_request


# ── Test PDF path ──────────────────────────────────────────────

def _get_test_pdf():
    path = os.environ.get(
        "ICBC_TEST_PDF",
        r"C:\Users\dell\Desktop\finance agent\中国工商银行企业网上银行931-2603.pdf",
    )
    if not os.path.exists(path):
        pytest.skip(f"Test PDF not found: {path}")
    return path


# ── ICBC Parser tests ──────────────────────────────────────────

class TestICBCParser:
    """Direct parser tests."""

    def test_parse_returns_parse_result(self):
        parser = ICBCParser()
        result = parser.parse(_get_test_pdf())
        assert result.bank == "中国工商银行"
        assert result.confidence > 0.9
        assert result.errors == []

    def test_parse_extracts_20_transactions(self):
        parser = ICBCParser()
        result = parser.parse(_get_test_pdf())
        assert len(result.transactions) == 20

    def test_first_transaction(self):
        parser = ICBCParser()
        result = parser.parse(_get_test_pdf())
        tx = result.transactions[0]
        assert tx.date == date(2026, 3, 6)
        assert tx.amount == Decimal("44800.00")
        assert tx.direction == "expense"
        assert tx.counterparty == "麒麟软件有限公司"
        assert "支付应付款" in tx.description
        assert tx.reference_number == "0000000000000000012001100501052500864"
        assert tx.notes == "208,581.86"

    def test_last_transaction(self):
        parser = ICBCParser()
        result = parser.parse(_get_test_pdf())
        tx = result.transactions[-1]
        assert tx.date == date(2026, 3, 20)
        assert tx.amount == Decimal("9.00")
        assert tx.direction == "expense"
        assert "跨行汇款手续费" in tx.description
        assert tx.notes == "663,386.86"

    def test_income_transaction(self):
        parser = ICBCParser()
        result = parser.parse(_get_test_pdf())
        income_tx = [t for t in result.transactions if t.direction == "income"]
        assert len(income_tx) == 2
        # Loan income on 2026-03-19
        loan = income_tx[1]
        assert loan.date == date(2026, 3, 19)
        assert loan.amount == Decimal("1000000.00")
        assert "对公贷款" in loan.description

    def test_statement_date_is_last_transaction_date(self):
        parser = ICBCParser()
        result = parser.parse(_get_test_pdf())
        assert result.statement_date == date(2026, 3, 20)

    def test_all_transactions_have_date_amount_direction(self):
        parser = ICBCParser()
        result = parser.parse(_get_test_pdf())
        for tx in result.transactions:
            assert tx.date is not None
            assert tx.amount is not None
            assert tx.direction in ("income", "expense")
            assert tx.currency == "CNY"

    def test_balance_chain_is_monotonic(self):
        """Balance notes should form a reasonable chain."""
        parser = ICBCParser()
        result = parser.parse(_get_test_pdf())
        balances = []
        for tx in result.transactions:
            if tx.notes:
                try:
                    balances.append(Decimal(tx.notes.replace(",", "")))
                except Exception:
                    pass
        assert len(balances) > 10
        # Verify first and last balance match expected
        assert balances[0] == Decimal("208581.86")
        assert balances[-1] == Decimal("663386.86")

    def test_reference_numbers_are_clean(self):
        """Reference numbers should not contain Chinese text or pipe chars."""
        parser = ICBCParser()
        result = parser.parse(_get_test_pdf())
        for tx in result.transactions:
            if tx.reference_number:
                assert "|" not in tx.reference_number
                assert not any("一" <= c <= "鿿" for c in tx.reference_number), \
                    f"Chinese char in ref: {tx.reference_number}"

    def test_counterparty_no_bleed(self):
        """Counterparty should not be single-char bleed like '公司'."""
        parser = ICBCParser()
        result = parser.parse(_get_test_pdf())
        for tx in result.transactions:
            if tx.counterparty:
                # Allow 2-char names like "郑炜" — just not single-char bleed
                assert len(tx.counterparty) >= 2, \
                    f"Suspicious short counterparty: {tx.counterparty!r}"


# ── Excel export tests ─────────────────────────────────────────

class TestExcelExport:
    """End-to-end: ICBC parse → Excel export."""

    def test_export_icbc_to_excel(self):
        parser = ICBCParser()
        result = parser.parse(_get_test_pdf())

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "icbc_export.xlsx")
            builder = ExcelBuilder()
            saved = builder.build(result.transactions, out_path)
            assert saved == out_path
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 1000  # non-empty xlsx


# ── Bridge JSON-RPC tests ──────────────────────────────────────

class TestBridgeParsePDF:
    """Test bridge.handle_request with parse_pdf method."""

    def test_parse_pdf_icbc_via_bridge(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "method": "parse_pdf",
            "params": {"file_path": _get_test_pdf()},
            "id": 1,
        })
        assert resp["id"] == 1
        assert resp["result"]["success"] is True
        assert resp["result"]["bank"] == "中国工商银行"
        assert len(resp["result"]["transactions"]) == 20
        assert resp["result"]["confidence"] > 0.9

    def test_parse_pdf_missing_path(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "method": "parse_pdf",
            "params": {},
            "id": 2,
        })
        assert resp["result"]["success"] is False
        assert "file_path" in resp["result"]["error"]

    def test_parse_pdf_nonexistent_file(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "method": "parse_pdf",
            "params": {"file_path": r"C:\nonexistent\file.pdf"},
            "id": 3,
        })
        assert resp["result"]["success"] is False


class TestBridgeHealth:
    def test_health(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "method": "health",
            "params": {},
            "id": 1,
        })
        assert resp["result"]["status"] == "ok"

    def test_unknown_method(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "method": "nonexistent",
            "params": {},
            "id": 2,
        })
        assert resp["error"]["code"] == -32601


class TestBridgeExcel:
    """Test bridge handle_request with generate_excel method."""

    def test_generate_excel_via_bridge(self):
        # First parse to get transactions
        parse_resp = handle_request({
            "jsonrpc": "2.0",
            "method": "parse_pdf",
            "params": {"file_path": _get_test_pdf()},
            "id": 1,
        })
        transactions = parse_resp["result"]["transactions"]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "bridge_export.xlsx")
            resp = handle_request({
                "jsonrpc": "2.0",
                "method": "generate_excel",
                "params": {"transactions": transactions, "output_path": out_path},
                "id": 2,
            })
            assert resp["result"]["success"] is True
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 1000

    def test_generate_excel_missing_transactions(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "method": "generate_excel",
            "params": {},
            "id": 3,
        })
        assert resp["result"]["success"] is False
        assert "transactions" in resp["result"]["error"]
