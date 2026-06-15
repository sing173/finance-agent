"""Tests for services/ — 4 个 Service 类的核心路径覆盖。"""
import json
import os
import sqlite3
import tempfile
from datetime import date
from decimal import Decimal

import pytest

from finance_agent_backend.models import Transaction


# ═══════════════════════════════════════════════════════════════════
# AccountRegistryService
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def test_config(tmp_path):
    """创建独立的测试 account_mapping.json。"""
    config = {
        "accounts": [
            {"id": "t1", "matchType": "suffix", "pattern": "1234",
             "bank": "测试银行", "bankCode": "TEST",
             "subjectCode": "10001", "subjectName": "现金"},
        ],
        "defaultBankSubjectCode": "10002",
    }
    path = str(tmp_path / "account_mapping_test.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f)
    return path


class TestAccountRegistryService:
    """AccountRegistryService — config_path 隔离测试。"""

    def test_list_all(self, test_config):
        from finance_agent_backend.services import AccountRegistryService

        svc = AccountRegistryService(config_path=test_config)
        result = svc.list_all()
        assert result["success"] is True
        assert len(result["accounts"]) == 1
        assert result["accounts"][0]["bankCode"] == "TEST"

    def test_match_found(self, test_config):
        from finance_agent_backend.services import AccountRegistryService

        svc = AccountRegistryService(config_path=test_config)
        result = svc.match("99991234")
        assert result["success"] is True
        assert result["entry"]["bankCode"] == "TEST"

    def test_match_not_found(self, test_config):
        from finance_agent_backend.services import AccountRegistryService

        svc = AccountRegistryService(config_path=test_config)
        result = svc.match("0000")
        assert result["success"] is True
        assert result["entry"] is None

    def test_add_and_delete(self, test_config):
        from finance_agent_backend.services import AccountRegistryService
        from finance_agent_backend.account_registry import AccountEntry

        svc = AccountRegistryService(config_path=test_config)
        entry = AccountEntry(
            id="", matchType="exact", pattern="5678",
            bank="新银行", bankCode="NEW",
            subjectCode="10002", subjectName="银行存款",
        )
        add_result = svc.add(entry)
        assert add_result["success"] is True
        assert add_result["id"]

        # 验证持久化到测试文件
        with open(test_config, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["accounts"]) == 2

        # 删除
        del_result = svc.delete(add_result["id"])
        assert del_result["success"] is True

        with open(test_config, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["accounts"]) == 1

    def test_config_path_none_uses_cache(self):
        """config_path=None 时使用模块级缓存。"""
        from finance_agent_backend.services import AccountRegistryService

        svc = AccountRegistryService()
        assert svc._use_cache is True

    def test_config_path_provided_bypasses_cache(self, test_config):
        """config_path 指定时绕过缓存。"""
        from finance_agent_backend.services import AccountRegistryService

        svc = AccountRegistryService(config_path=test_config)
        assert svc._use_cache is False


# ═══════════════════════════════════════════════════════════════════
# VoucherService
# ═══════════════════════════════════════════════════════════════════


class TestVoucherService:
    """VoucherService — 凭证全链路。"""

    def test_preview_basic(self, tmp_db):
        from finance_agent_backend.services import VoucherService

        svc = VoucherService(db_path=tmp_db)
        txns = [
            {"date": "2024-01-15", "description": "支付物业费",
             "amount": 1200, "currency": "CNY", "direction": "expense",
             "counterparty": "物业公司", "account_number": "1234"},
        ]
        result = svc.preview(txns, subject_mapping=None)
        assert result["success"] is True
        assert len(result["vouchers"]) >= 1

    def test_preview_empty_transactions(self, tmp_db):
        from finance_agent_backend.services import VoucherService

        svc = VoucherService(db_path=tmp_db)
        result = svc.preview([], subject_mapping=None)
        assert result["success"] is False

    def test_save_and_load_draft(self, tmp_db):
        from finance_agent_backend.services import VoucherService

        svc = VoucherService(db_path=tmp_db)
        entries = [{
            "entry_seq": 1, "voucher_no": 1, "date": "2024-01-15",
            "summary": "测试", "subject_code": "50602", "subject_name": "管理费用",
            "debit_amount": 100.0, "credit_amount": None,
            "direction": "expense", "counterparty": "测试方",
            "match_source": "rule", "rule_id": "",
            "original_summary": "测试", "original_amount": 100.0,
            "is_manual": False, "aux_category": "", "aux_category_name": "",
        }]
        save_result = svc.save_draft("测试草稿", "202401", entries)
        assert save_result["success"] is True
        draft_id = save_result["draft_id"]

        load_result = svc.load_draft(draft_id)
        assert load_result["success"] is True
        assert load_result["draft"]["name"] == "测试草稿"
        assert len(load_result["draft"]["entries"]) == 1

    def test_list_drafts(self, tmp_db):
        from finance_agent_backend.services import VoucherService

        svc = VoucherService(db_path=tmp_db)
        result = svc.list_drafts()
        assert result["success"] is True
        assert isinstance(result["drafts"], list)

    def test_delete_draft(self, tmp_db):
        from finance_agent_backend.services import VoucherService

        svc = VoucherService(db_path=tmp_db)
        entries = [{
            "entry_seq": 1, "voucher_no": 1, "date": "2024-01-15",
            "summary": "删", "subject_code": "50602", "subject_name": "管理费用",
            "debit_amount": 50.0, "credit_amount": None,
            "direction": "expense", "counterparty": "",
            "match_source": "unmatched", "rule_id": "",
            "original_summary": "删", "original_amount": 50.0,
            "is_manual": False, "aux_category": "", "aux_category_name": "",
        }]
        save = svc.save_draft("待删", "202401", entries)
        draft_id = save["draft_id"]

        del_result = svc.delete_draft(draft_id)
        assert del_result["success"] is True

        load_result = svc.load_draft(draft_id)
        assert load_result["success"] is False

    def test_load_nonexistent_draft(self, tmp_db):
        from finance_agent_backend.services import VoucherService

        svc = VoucherService(db_path=tmp_db)
        result = svc.load_draft("nonexistent")
        assert result["success"] is False

    def test_save_draft_empty_entries(self, tmp_db):
        from finance_agent_backend.services import VoucherService

        svc = VoucherService(db_path=tmp_db)
        result = svc.save_draft("空", "202401", [])
        assert result["success"] is False

    def test_export(self, tmp_db, tmp_path):
        from finance_agent_backend.services import VoucherService

        svc = VoucherService(db_path=tmp_db)
        entries = [{
            "entry_seq": 1, "voucher_no": 1, "date": "2024-01-15",
            "summary": "导出测试", "subject_code": "50602", "subject_name": "管理费用",
            "debit_amount": 200.0, "credit_amount": None,
            "direction": "expense", "counterparty": "测试",
            "match_source": "rule", "rule_id": "",
            "original_summary": "导出测试", "original_amount": 200.0,
            "is_manual": False, "aux_category": "", "aux_category_name": "",
        }]
        save = svc.save_draft("导出草稿", "202401", entries)
        draft_id = save["draft_id"]

        output_path = str(tmp_path / "export.xlsx")
        export_result = svc.export(
            draft_id=draft_id,
            output_path=output_path,
            period="202401",
        )
        assert export_result["success"] is True
        assert os.path.exists(output_path)
        assert export_result["entry_count"] == 1


# ═══════════════════════════════════════════════════════════════════
# SubjectService
# ═══════════════════════════════════════════════════════════════════


class TestSubjectService:

    def test_get_info(self):
        from finance_agent_backend.services import SubjectService

        svc = SubjectService()
        result = svc.get_info()
        assert result["success"] is True
        assert result["loaded"] is True
        assert result["count"] > 0

    def test_get_subject_codes(self):
        from finance_agent_backend.services import SubjectService

        svc = SubjectService()
        codes = svc.get_subject_codes()
        assert isinstance(codes, set)
        assert len(codes) > 0
        assert "5060203" in codes  # 管理费用_物业管理费


# ═══════════════════════════════════════════════════════════════════
# ParseService
# ═══════════════════════════════════════════════════════════════════


class TestParseService:

    def test_detect_supported_banks(self):
        from finance_agent_backend.services import ParseService

        svc = ParseService()
        banks = svc.detect_supported_banks()
        assert len(banks) >= 3
        codes = [b["code"] for b in banks]
        assert "ICBC" in codes
        assert "CMB" in codes

    def test_detect_banks_empty(self):
        from finance_agent_backend.services import ParseService

        svc = ParseService()
        results = svc.detect_banks([])
        assert results == []

    def test_detect_banks_nonexistent(self):
        from finance_agent_backend.services import ParseService

        svc = ParseService()
        results = svc.detect_banks(["/nonexistent/file.pdf"])
        assert len(results) == 1
        assert results[0]["status"] == "failed"

    def test_generate_excel(self, tmp_path):
        from finance_agent_backend.services import ParseService

        svc = ParseService()
        txns = [{
            "date": "2024-01-15", "description": "测试", "amount": 100,
            "currency": "CNY", "direction": "income",
        }]
        output_path = str(tmp_path / "test.xlsx")
        result_path = svc.generate_excel(txns, output_path)
        assert os.path.exists(result_path)
