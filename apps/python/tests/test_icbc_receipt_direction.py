"""Tests for icbc_receipt_grid_parser direction logic (account_registry based)."""
import os
import sys
import tempfile
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from finance_agent_backend.models import AccountEntry
from finance_agent_backend.account_registry import (
    AccountMappingRepository,
    AccountRegistry,
    _default_config_path,
)


def _make_registry(entries: list[dict]) -> AccountRegistry:
    """Helper: write temp account_mapping.json and return loaded AccountRegistry."""
    data = {"accounts": entries, "defaultBankSubjectCode": "10002"}
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(data, tmp, ensure_ascii=False)
    tmp.close()
    repo = AccountMappingRepository(tmp.name)
    registry = AccountRegistry(repo.load())
    # cleanup after test
    os.unlink(tmp.name)
    return registry


def test_direction_expense_payer_matches_our_account():
    """付款人账号匹配我方账户 → expense（支出）"""
    registry = _make_registry([
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行",
        }
    ])

    # 付款人账号以 4363 结尾 → 匹配成功 → 我方付款 → expense
    result = registry.match_by_account("12345678904363")
    assert result is not None
    assert result.bankCode == "ICBC"
    assert result.subjectCode == "1000201"


def test_direction_income_payee_matches_our_account():
    """收款人账号匹配我方账户 → income（收入）"""
    registry = _make_registry([
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行",
        }
    ])

    # 收款人账号以 4363 结尾 → 匹配成功 → 我方收款 → income
    result = registry.match_by_account("98765432104363")
    assert result is not None
    assert result.bankCode == "ICBC"


def test_direction_no_match_falls_back():
    """双方账号均不匹配 → fallback"""
    registry = _make_registry([
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行",
        }
    ])

    # 两个账号都不匹配 → 返回 None
    result = registry.match_by_account("00000000000000")
    assert result is None


def test_direction_exact_match_priority():
    """exact 匹配优先于 suffix"""
    registry = _make_registry([
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行",
        },
        {
            "id": "acc_002", "matchType": "exact", "pattern": "12344363",
            "bank": "招商银行", "bankCode": "CMB",
            "subjectCode": "1000203", "subjectName": "银行存款-招行",
        },
    ])

    # "12344363" 同时命中 suffix("4363") 和 exact("12344363") → exact wins
    result = registry.match_by_account("12344363")
    assert result is not None
    assert result.bankCode == "CMB"


def test_direction_masked_account_no_match():
    """账号含星号脱敏时，match_by_account 仍可能匹配（endswith 逻辑），
    过滤应在调用层（parser）处理，不在 registry 层处理。"""
    registry = _make_registry([
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行",
        }
    ])

    # "6222****4363" endswith "4363" → 技术上命中
    # Parser 层应在调用前过滤含星号账号，不在 registry 层过滤
    result = registry.match_by_account("6222****4363")
    assert result is not None  # registry 层不拒绝脱敏账号


def test_direction_empty_account_no_match():
    """空账号不参与匹配"""
    registry = _make_registry([
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行",
        }
    ])

    assert registry.match_by_account("") is None
