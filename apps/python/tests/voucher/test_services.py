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
    """创建独立的测试 SQLite DB。"""
    from finance_agent_backend import db as _db
    from finance_agent_backend.repo.account_mapping_repo import AccountMappingRepository
    from finance_agent_backend.models import AccountEntry

    db_path = str(tmp_path / "test.db")
    conn = _db.get_db(db_path=db_path)
    # 直接建表，不跑迁移
    conn.execute("""CREATE TABLE IF NOT EXISTS account_mapping (
        id              TEXT PRIMARY KEY,
        matchType       TEXT NOT NULL,
        pattern         TEXT NOT NULL,
        bank            TEXT NOT NULL,
        bankCode        TEXT NOT NULL,
        subjectCode     TEXT NOT NULL,
        subjectName     TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS schema_version (
        version   INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )""")
    conn.execute("INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                 (5, "2024-01-01T00:00:00+00:00"))

    # 插入测试数据
    repo = AccountMappingRepository(conn)
    entry = AccountEntry(
        id="t1", matchType="suffix", pattern="1234",
        bank="测试银行", bankCode="TEST",
        subjectCode="10001", subjectName="现金",
    )
    repo.save(entry)
    conn.commit()

    return db_path


class TestAccountRegistryService:
    """AccountRegistryService — db_path 隔离测试。"""

    def test_list_all(self, test_config):
        from finance_agent_backend.services import AccountRegistryService

        svc = AccountRegistryService(db_path=test_config)
        result = svc.list_all()
        assert result["success"] is True
        assert len(result["accounts"]) == 1
        assert result["accounts"][0]["bankCode"] == "TEST"

    def test_match_found(self, test_config):
        from finance_agent_backend.services import AccountRegistryService

        svc = AccountRegistryService(db_path=test_config)
        result = svc.match("99991234")
        assert result["success"] is True
        assert result["entry"]["bankCode"] == "TEST"

    def test_match_not_found(self, test_config):
        from finance_agent_backend.services import AccountRegistryService

        svc = AccountRegistryService(db_path=test_config)
        result = svc.match("0000")
        assert result["success"] is True
        assert result["entry"] is None

    def test_add_and_delete(self, test_config):
        from finance_agent_backend.services import AccountRegistryService
        from finance_agent_backend.account_registry import AccountEntry
        from finance_agent_backend.repo.account_mapping_repo import AccountMappingRepository
        from finance_agent_backend import db as _db

        svc = AccountRegistryService(db_path=test_config)
        entry = AccountEntry(
            id="", matchType="exact", pattern="5678",
            bank="新银行", bankCode="NEW",
            subjectCode="10002", subjectName="银行存款",
        )
        add_result = svc.add(entry)
        assert add_result["success"] is True
        assert add_result["id"]

        # 验证持久化到测试 DB
        conn = _db.get_db(db_path=test_config)
        repo = AccountMappingRepository(conn)
        assert len(repo.find_all()) == 2

        # 删除
        del_result = svc.delete(add_result["id"])
        assert del_result["success"] is True

        assert len(repo.find_all()) == 1


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

    def test_export_writes_history_for_manual_only(self, tmp_db, tmp_path):
        """导出时仅 is_manual=True 分录写入 subject_history。"""
        from finance_agent_backend.services import VoucherService
        from finance_agent_backend.repo.subject_history_repo import SubjectHistoryRepo

        svc = VoucherService(db_path=tmp_db)
        entries = [
            {
                "entry_seq": 1, "voucher_no": 1, "date": "2024-01-15",
                "summary": "手动修正", "subject_code": "5060203", "subject_name": "物业管理费",
                "debit_amount": 100.0, "credit_amount": None,
                "direction": "expense", "counterparty": "启胜物业",
                "match_source": "manual", "rule_id": "",
                "original_summary": "手动修正", "original_amount": 100.0,
                "is_manual": True, "aux_category": "", "aux_category_name": "",
            },
            {
                "entry_seq": 2, "voucher_no": 1, "date": "2024-01-15",
                "summary": "自动匹配", "subject_code": "1022120", "subject_name": "手续费",
                "debit_amount": 50.0, "credit_amount": None,
                "direction": "expense", "counterparty": "银行",
                "match_source": "rule", "rule_id": "rule_003",
                "original_summary": "自动匹配", "original_amount": 50.0,
                "is_manual": False, "aux_category": "", "aux_category_name": "",
            },
        ]
        save = svc.save_draft("历史测试", "202401", entries)
        draft_id = save["draft_id"]

        output_path = str(tmp_path / "history_export.xlsx")
        svc.export(draft_id=draft_id, output_path=output_path, period="202401")

        # 验证 subject_history 只有 manual 分录
        repo = SubjectHistoryRepo(tmp_db)
        match = repo.find_similar("手动修正", "expense")
        assert match is not None
        assert match.subject_code == "5060203"

        # 自动匹配的分录不应写入历史
        no_match = repo.find_similar("自动匹配", "expense")
        assert no_match is None


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

    def test_import_from_xlsx(self, tmp_path, monkeypatch):
        """import_from_xlsx 写入 DB 并失效缓存。"""
        from finance_agent_backend.models import Subject
        from finance_agent_backend.services import SubjectService
        from finance_agent_backend import db as _db
        from finance_agent_backend import subject_matcher as _sm

        mock_subjects = {
            "10001": Subject(code="10001", name="现金", category="资产",
                             direction="借", full_name="现金"),
            "5060203": Subject(code="5060203", name="物业管理费", category="费用",
                               direction="借", aux_category="04", full_name="管理费用_物业管理费"),
        }

        class FakeLoader:
            def load(self, path):
                return mock_subjects

        monkeypatch.setattr(
            "finance_agent_backend.tools.subject_loader.SubjectLoader",
            FakeLoader,
        )
        # 指向不存在的 subjects.json，避免 _migrate_v6 回填默认科目干扰行数断言
        import finance_agent_backend.paths as _paths
        monkeypatch.setattr(_paths, "get_config_path", lambda name="": str(tmp_path / "nonexistent.json"))

        db_path = str(tmp_path / "test.db")
        _db._conn = _db.get_db(db_path=db_path)
        _db.init_db(_db._conn)
        _db._conn.row_factory = sqlite3.Row

        _sm._subjects_cache = {"old": True}

        svc = SubjectService()
        result = svc.import_from_xlsx("dummy.xlsx")
        assert result["success"] is True
        assert result["count"] == 2

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT code, name, aux_category FROM subjects ORDER BY code").fetchall()
        assert len(rows) == 2
        assert rows[0]["code"] == "10001"
        assert rows[1]["code"] == "5060203"
        assert rows[1]["aux_category"] == "04"

        assert _sm._subjects_cache is None


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

    def test_parse_csv(self):
        """ParseService.parse 解析 ICBC CSV 文件。"""
        from finance_agent_backend.services import ParseService

        csv_path = os.path.join(
            os.path.dirname(__file__), "..", "fixtures", "icbc_statement.csv"
        )
        if not os.path.exists(csv_path):
            pytest.skip("ICBC CSV fixture 不存在")

        svc = ParseService()
        result = svc.parse(csv_path)
        assert result["success"] is True
        assert result["bank"] in ("中国工商银行", "工商银行")
        assert len(result["transactions"]) > 0
