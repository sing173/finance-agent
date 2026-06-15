"""Tracer bullet: 验证 VoucherEntryFactory._entry() 输出包含 aux_category（Issue #46 第 3 点）。

RED 阶段：测试应 FAIL，因为 _entry() 尚未输出 aux_category。
"""
import sys
import os


from finance_agent_backend.voucher_composer import VoucherEntryFactory, VoucherGroup, GroupedTxn
from finance_agent_backend.models import Transaction
from datetime import date


def _make_txn(description="报销", amount=100.0, direction="expense"):
    return Transaction(
        date=date(2024, 1, 1),
        description=description,
        amount=amount,
        direction=direction,
        account_number="6222000000000000",
        counterparty="测试对方",
        reference_number="REF001",
    )


def test_entry_includes_aux_category():
    """_entry() 输出应包含 aux_category 和 aux_category_name。"""
    txn = _make_txn()
    group = VoucherGroup(
        account_number="6222000000000000",
        direction="expense",
        counterparty_account="REF001",
        counter_code="50602",
        bank_code="1000201",
        bank_name="工行",
        txns=[GroupedTxn(txn=txn, counter_code="50602", counter_name="管理费用",
                         match_source="rule", match_rule_id="rule_e032",
                         aux_category="04", aux_category_name="公共部门")],
    )
    entries = VoucherEntryFactory.build(group, 1)
    # 第 0 条是对方科目分录（借），第 1 条是银行分录（贷）
    entry = entries[0]
    assert entry.aux_category == "04", (
        f"期望 aux_category='04'，实际 '{entry.aux_category}'"
    )
    assert entry.aux_category_name == "公共部门", (
        f"期望 aux_category_name='公共部门'，实际 '{entry.aux_category_name}'"
    )


def test_bank_entry_does_not_have_aux_category():
    """_bank_entry() 输出 aux_category 应为空。"""
    txn = _make_txn()
    group = VoucherGroup(
        account_number="6222000000000000",
        direction="expense",
        counterparty_account="REF001",
        counter_code="50602",
        bank_code="1000201",
        bank_name="工行",
        txns=[GroupedTxn(txn=txn, counter_code="50602", counter_name="管理费用",
                         match_source="rule", match_rule_id="rule_e032",
                         aux_category="04", aux_category_name="公共部门")],
    )
    entries = VoucherEntryFactory.build(group, 1)
    bank_entry = entries[-1]  # 最后一条是银行分录
    assert bank_entry.aux_category == ""
    assert bank_entry.aux_category_name == ""
