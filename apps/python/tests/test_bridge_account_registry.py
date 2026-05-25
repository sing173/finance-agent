"""Tests for bridge.py account_registry JSON-RPC methods (Issue #29)."""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from finance_agent_backend.bridge import handle_request


@pytest.fixture
def temp_accounts_file():
    """Create a temporary account_mapping.json for testing."""
    data = {
        "accounts": [
            {
                "id": "acc_001",
                "matchType": "suffix",
                "pattern": "4363",
                "bank": "工商银行",
                "bankCode": "ICBC",
                "subjectCode": "1000201",
                "subjectName": "银行存款-工行基本户",
            },
            {
                "id": "acc_002",
                "matchType": "suffix",
                "pattern": "0288",
                "bank": "招商银行",
                "bankCode": "CMB",
                "subjectCode": "1000203",
                "subjectName": "银行存款-招商银行（0288）",
            },
        ],
        "defaultBankSubjectCode": "10002",
    }
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(data, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    return tmp.name


@pytest.fixture
def handler(temp_accounts_file):
    """Create bridge handler with temp config."""
    # Monkey-patch _default_config_path to use temp file
    import finance_agent_backend.account_registry as reg_module
    original = reg_module._default_config_path
    reg_module._default_config_path = lambda: temp_accounts_file

    # Create handler (get_registry will use patched path)
    def handler(method, params):
        request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        response = handle_request(request)
        return response.get("result")

    yield handler

    # Cleanup
    reg_module._default_config_path = original
    os.unlink(temp_accounts_file)


def test_account_registry_list(handler):
    """account_registry.list 返回所有映射条目。"""
    result = handler("account_registry.list", {})
    assert result is not None
    assert "accounts" in result
    assert len(result["accounts"]) == 2
    assert result["accounts"][0]["bankCode"] == "ICBC"
    assert result["accounts"][1]["bankCode"] == "CMB"


def test_account_registry_match_found(handler):
    """account_registry.match 根据账号匹配返回结果。"""
    result = handler("account_registry.match", {"accountNumber": "12345678904363"})
    assert result is not None
    assert result["success"] is True
    assert result["entry"] is not None
    assert result["entry"]["bankCode"] == "ICBC"
    assert result["entry"]["subjectCode"] == "1000201"


def test_account_registry_match_not_found(handler):
    """account_registry.match 无匹配返回 entry=None。"""
    result = handler("account_registry.match", {"accountNumber": "0000000000"})
    assert result is not None
    assert result["success"] is True
    assert result["entry"] is None


def test_account_registry_add(handler):
    """account_registry.add 新增条目并返回成功。"""
    result = handler(
        "account_registry.add",
        {
            "matchType": "suffix",
            "pattern": "7931",
            "bank": "工商银行",
            "bankCode": "ICBC",
            "subjectCode": "1000205",
            "subjectName": "银行存款-工商银行（7931）",
        },
    )
    assert result is not None
    assert result["success"] is True
    assert "id" in result
    assert result["entry"]["bankCode"] == "ICBC"


def test_account_registry_add_validation_bankcode(handler):
    """account_registry.add bankCode 为空时返回错误。"""
    result = handler(
        "account_registry.add",
        {
            "matchType": "suffix",
            "pattern": "7931",
            "bank": "工商银行",
            "bankCode": "",
            "subjectCode": "1000205",
            "subjectName": "测试",
        },
    )
    assert result is not None
    assert result.get("success") is False
    assert "bankCode" in result.get("error", "")


def test_account_registry_update(handler):
    """account_registry.update 更新已有条目。"""
    result = handler(
        "account_registry.update",
        {
            "id": "acc_001",
            "matchType": "exact",
            "pattern": "4363",
            "bank": "工商银行",
            "bankCode": "ICBC",
            "subjectCode": "1000201",
            "subjectName": "银行存款-工行基本户（已更新）",
        },
    )
    assert result is not None
    assert result["success"] is True

    # 验证更新结果
    list_result = handler("account_registry.list", {})
    updated = next(e for e in list_result["accounts"] if e["id"] == "acc_001")
    assert updated["subjectName"] == "银行存款-工行基本户（已更新）"


def test_account_registry_delete(handler):
    """account_registry.delete 删除指定条目。"""
    result = handler("account_registry.delete", {"id": "acc_001"})
    assert result is not None
    assert result["success"] is True

    # 验证删除结果
    list_result = handler("account_registry.list", {})
    assert len(list_result["accounts"]) == 1
    assert list_result["accounts"][0]["id"] == "acc_002"
