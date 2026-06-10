"""Tracer bullet: 验证 _bank_entry() 使用原交易摘要（Issue #46 第 5 点）。

RED 阶段：测试应 FAIL，因为 _bank_entry() 写死 "银行科目"。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from finance_agent_backend.voucher_composer import VoucherEntryFactory, VoucherGroup, GroupedTxn
from finance_agent_backend.models import Transaction
from datetime import date


def _make_txn(description="支付物业管理费", amount=500.0):
    return Transaction(
        date=date(2024, 1, 15),
        description=description,
        amount=amount,
        direction="expense",
        account_number="6222000000000000",
        counterparty="启胜物业",
        reference_number="REF001",
    )


def test_bank_entry_uses_original_summary():
    """_bank_entry() 应使用原交易摘要，而非写死 '银行科目'。"""
    txn = _make_txn(description="支付启胜物业1月份物业费")
    group = VoucherGroup(
        account_number="6222000000000000",
        direction="expense",
        counterparty_account="REF001",
        counter_code="5060203",
        bank_code="1000201",
        bank_name="工行",
        txns=[GroupedTxn(txn=txn, counter_code="5060203", counter_name="管理费用_物业管理费",
                         match_source="rule", match_rule_id="rule_e001")],
    )
    entries = VoucherEntryFactory.build(group, 1)
    bank_entry = entries[-1]
    assert bank_entry["summary"] == "支付启胜物业1月份物业费", (
        f"期望原交易摘要，实际 '{bank_entry['summary']}'"
    )


def test_bank_entry_income_uses_original_summary():
    """income 方向的 _bank_entry() 也应使用原交易摘要。"""
    txn = _make_txn(description="收到客户货款")
    txn.direction = "income"
    txn.amount = 1000.0
    group = VoucherGroup(
        account_number="6222000000000000",
        direction="income",
        counterparty_account="REF001",
        counter_code="10122",
        bank_code="1000201",
        bank_name="工行",
        txns=[GroupedTxn(txn=txn, counter_code="10122", counter_name="应收账款",
                         match_source="rule", match_rule_id="rule_i001")],
    )
    entries = VoucherEntryFactory.build(group, 1)
    bank_entry = entries[0]  # income 方向银行分录在第 0 位
    assert bank_entry["summary"] == "收到客户货款", (
        f"期望原交易摘要，实际 '{bank_entry['summary']}'"
    )
