"""Tests for voucher_composer.py — 凭证组装 + preview RPC (Issue #34).

Tests verify: compose (merging + direction), voucher.preview RPC,
voucher.save_draft RPC.
"""
import os
import sys
import json
import sqlite3
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from finance_agent_backend.models import Transaction
from finance_agent_backend.db import init_db


# ── 辅助 ──────────────────────────────────────────────────────

def _make_txn(
    dt: str, desc: str, amount: float, direction: str,
    counterparty: str = '', acct: str = '', ref: str = '',
) -> Transaction:
    return Transaction(
        date=date.fromisoformat(dt),
        description=desc,
        amount=Decimal(str(amount)),
        direction=direction,  # type: ignore
        counterparty=counterparty,
        account_number=acct,
        reference_number=ref,
    )


SAMPLE_TXNS = [
    _make_txn("2026-03-01", "支付启胜物业费1月", 1200.00, "expense",
              counterparty="启胜物业", acct="622202****1234", ref="9550880004679001037"),
    _make_txn("2026-03-01", "支付启胜物业费2月", 1200.00, "expense",
              counterparty="启胜物业", acct="622202****1234", ref="9550880004679001037"),
    _make_txn("2026-03-15", "收到客户货款", 50000.00, "income",
              counterparty="客户A", acct="622202****1234", ref="P003"),
]

# Minified subject_mapping + account_mapping for preview
SIMPLE_SUBJECT_MAPPING = {
    "version": 2,
    "expense": {
        "default_subject_code": "",
        "rules": [
            {"id": "r1", "priority": 1, "match": {"keywords": ["物业", "物管"]},
             "subject_code": "5060203", "subject_name": "管理费用_物业管理费"},
        ],
    },
    "income": {
        "default_subject_code": "",
        "rules": [
            {"id": "r2", "priority": 1, "match": {"keywords": ["收款", "货款"]},
             "subject_code": "10122", "subject_name": "应收账款"},
        ],
    },
}


@pytest.fixture
def tmp_db(tmp_path):
    """临时数据库（pytest 自动清理），初始化 schema。"""
    path = str(tmp_path / "test.db")
    conn = sqlite3.connect(path)
    init_db(conn)
    conn.close()
    return path


# ── 测试 ──────────────────────────────────────────────────────

class TestCompose:
    """VoucherComposer.compose() — 同类合并 + 借贷方向。"""

    def test_basic_compose(self):
        from finance_agent_backend.voucher_composer import VoucherComposer

        composer = VoucherComposer()
        result = composer.compose(SAMPLE_TXNS, SIMPLE_SUBJECT_MAPPING)

        # 2 笔物业费（同对方科目+同方向）→ 1 张凭证
        # 1 笔货款收入 → 1 张凭证
        assert len(result) == 2

    def test_merge_same_counterparty(self):
        from finance_agent_backend.voucher_composer import VoucherComposer

        composer = VoucherComposer()
        result = composer.compose(SAMPLE_TXNS, SIMPLE_SUBJECT_MAPPING)

        # 凭证 #1: 物业费（expense → 2 entries + 1 bank entry）
        voucher1 = result[0]
        # expense: 借 对方科目, 贷 银行科目
        assert voucher1["voucher_no"] == 1
        entries = voucher1["entries"]
        assert len(entries) == 3  # 2. 物业费分录 + 1 bank 分录
        assert entries[0]["subject_code"] == "5060203"

    def test_direction_expense_debit_counterpart(self):
        """支出→借方对方科目，贷方银行科目。"""
        from finance_agent_backend.voucher_composer import VoucherComposer

        composer = VoucherComposer()
        result = composer.compose(SAMPLE_TXNS, SIMPLE_SUBJECT_MAPPING)

        voucher1 = result[0]  # expense
        entries = voucher1["entries"]
        # 分录 1 & 2: 借 对方科目
        assert entries[0]["debit_amount"] is not None
        assert entries[0]["credit_amount"] is None
        # 最后一条: 贷 银行科目
        bank_entry = entries[-1]
        assert bank_entry["credit_amount"] is not None
        assert bank_entry["debit_amount"] is None

    def test_direction_income_credit_counterpart(self):
        """收入→贷方对方科目，借方银行科目。"""
        from finance_agent_backend.voucher_composer import VoucherComposer

        composer = VoucherComposer()
        result = composer.compose(SAMPLE_TXNS, SIMPLE_SUBJECT_MAPPING)

        voucher2 = result[1]  # income
        entries = voucher2["entries"]
        # 分录 1: 借 银行科目
        assert entries[0]["debit_amount"] is not None
        # 分录 2: 贷 对方科目
        assert entries[1]["credit_amount"] is not None

    def test_totals_balance(self):
        """借方合计 = 贷方合计。"""
        from finance_agent_backend.voucher_composer import VoucherComposer

        composer = VoucherComposer()
        result = composer.compose(SAMPLE_TXNS, SIMPLE_SUBJECT_MAPPING)

        for voucher in result:
            total_debit = sum(
                e.get("debit_amount") or 0 for e in voucher["entries"]
            )
            total_credit = sum(
                e.get("credit_amount") or 0 for e in voucher["entries"]
            )
            assert abs(total_debit - total_credit) < 0.01, (
                f"Voucher {voucher['voucher_no']}: debit={total_debit}, credit={total_credit}"
            )
            assert total_debit > 0  # non-trivial voucher

    def test_no_merge_different_counterparty_account(self):
        """不同对方账号的相同科目不合并。"""
        from finance_agent_backend.voucher_composer import VoucherComposer

        txns = [
            _make_txn("2026-03-20", "支付应付账款", 35000.00, "expense",
                      counterparty="供应商A", acct="622202****1234", ref="ACC001"),
            _make_txn("2026-03-20", "支付应付账款", 45500.00, "expense",
                      counterparty="供应商B", acct="622202****1234", ref="ACC002"),
        ]
        mapping = {
            "version": 2,
            "expense": {
                "rules": [
                    {"id": "r1", "priority": 1, "match": {"keywords": ["应付账款"]},
                     "subject_code": "20201", "subject_name": "应付账款"},
                ],
            },
        }
        composer = VoucherComposer()
        result = composer.compose(txns, mapping)
        # 不同对方账号 → 各一张凭证
        assert len(result) == 2

    def test_merge_same_counterparty_account(self):
        """相同对方账号（含无值视为通配）相同科目合并。"""
        from finance_agent_backend.voucher_composer import VoucherComposer

        txns = [
            _make_txn("2026-03-20", "支付应付账款", 35000.00, "expense",
                      counterparty="供应商A", acct="622202****1234", ref="ACC001"),
            _make_txn("2026-03-20", "支付应付账款", 45500.00, "expense",
                      counterparty="供应商A", acct="622202****1234", ref="ACC001"),
        ]
        mapping = {
            "version": 2,
            "expense": {
                "rules": [
                    {"id": "r1", "priority": 1, "match": {"keywords": ["应付账款"]},
                     "subject_code": "20201", "subject_name": "应付账款"},
                ],
            },
        }
        composer = VoucherComposer()
        result = composer.compose(txns, mapping)
        # 相同对方账号 → 合并为一张凭证
        assert len(result) == 1
        assert len(result[0]["entries"]) == 3  # 2 对方分录 + 1 银行分录


class TestUnmatchedIndependent:
    """多条 unmatched 交易各自独立成凭证，不合并（P0 回归修复）。"""

    def test_unmatched_transactions_not_merged(self):
        from finance_agent_backend.voucher_composer import VoucherComposer

        txns = [
            _make_txn("2026-04-01", "支付AWS云主机托管服务费", 1200.00, "expense",
                      counterparty="阿里云计算", acct="622202****1234", ref=""),
            _make_txn("2026-04-02", "购买办公设备一批", 3500.00, "expense",
                      counterparty="戴尔科技", acct="622202****1234", ref=""),
            _make_txn("2026-04-03", "支付法律顾问费", 5000.00, "expense",
                      counterparty="律师事务所", acct="622202****1234", ref=""),
        ]
        # 空规则：所有交易均无法匹配 → __unmatched__
        mapping = {"version": 2, "expense": {"rules": []}, "income": {"rules": []}}
        composer = VoucherComposer()
        result = composer.compose(txns, mapping)
        # 每条 unmatched 应独立成凭证
        assert len(result) == 3, f"expected 3 independent vouchers, got {len(result)}"
        for v in result:
            # 每张凭证只有 1 条对方分录 + 1 条银行分录
            non_bank = [e for e in v["entries"] if e.get("direction") != "bank"]
            assert len(non_bank) == 1, f"voucher should have exactly 1 non-bank entry, got {len(non_bank)}"

    def test_unmatched_same_account_different_descriptions_independent(self):
        """相同账号+相同方向的多条 unmatched 交易各独立成凭证。"""
        from finance_agent_backend.voucher_composer import VoucherComposer

        txns = [
            _make_txn("2026-04-01", "未知交易A", 100.00, "expense",
                      counterparty="对手A", acct="622202****1234", ref=""),
            _make_txn("2026-04-01", "未知交易B", 200.00, "expense",
                      counterparty="对手B", acct="622202****1234", ref=""),
        ]
        mapping = {"version": 2, "expense": {"rules": []}, "income": {"rules": []}}
        composer = VoucherComposer()
        result = composer.compose(txns, mapping)
        # 即使账号相同，unmatched 也各自独立
        assert len(result) == 2, f"unmatched with same account should still be independent, got {len(result)}"


class TestPreviewRPC:
    """voucher.preview JSON-RPC 方法。"""

    def test_preview_returns_vouchers(self):
        from finance_agent_backend.bridge import handle_request

        # Register composer handler (bridge already loads it)
        # We call handle_request directly with voucher.preview
        response = handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "voucher.preview",
            "params": {
                "transactions": [t.to_dict() for t in SAMPLE_TXNS],
                "subject_mapping": SIMPLE_SUBJECT_MAPPING,
            },
        })
        result = response.get("result", {})
        assert result.get("success") is True
        vouchers = result.get("vouchers", [])
        assert len(vouchers) == 2
        assert "warnings" in result


class TestSaveDraftRPC:
    """voucher.save_draft JSON-RPC 方法。"""

    def test_save_draft(self, tmp_db):
        from finance_agent_backend.bridge import handle_request
        from finance_agent_backend import db as _db

        # Reset singleton so db_path param is used
        _db.close_db()
        _db._conn = None
        _db._db_path = None

        response = handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "voucher.save_draft",
            "params": {
                "name": "2026年3月凭证",
                "period": "2026年第3期",
                "db_path": tmp_db,
                "entries": [
                    {
                        "entry_seq": 1, "voucher_no": 1,
                        "date": "2026-03-01", "summary": "支付物业费",
                        "subject_code": "5060203", "subject_name": "管理费用_物业管理费",
                        "debit_amount": 2400.0, "credit_amount": None,
                        "direction": "expense", "match_source": "rule",
                        "original_summary": "支付启胜物业费1月", "is_manual": False,
                    },
                    {
                        "entry_seq": 2, "voucher_no": 1,
                        "date": "2026-03-01", "summary": "银行科目",
                        "subject_code": "1000201", "subject_name": "银行存款-工行基本户",
                        "debit_amount": None, "credit_amount": 2400.0,
                        "direction": "expense", "match_source": "unmatched",
                        "original_summary": "", "is_manual": False,
                    },
                ],
            },
        })
        result = response.get("result", {})
        assert result.get("success") is True
        assert result.get("draft_id")

        # Verify DB has entries
        conn = sqlite3.connect(tmp_db)
        drafts = conn.execute("SELECT * FROM voucher_draft").fetchall()
        entries = conn.execute("SELECT * FROM voucher_draft_entry").fetchall()
        conn.close()
        assert len(drafts) == 1
        assert len(entries) == 2