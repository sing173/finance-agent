"""SubjectService — 科目导入/新增/查询 DB 纯 CRUD 行为 (DB source of truth)."""
import json
import os
import sqlite3
from unittest.mock import MagicMock

import pytest
from finance_agent_backend import db as _db
from finance_agent_backend.models import Subject
from finance_agent_backend.services.subject_service import SubjectService


@pytest.fixture(autouse=True)
def _reset_subjects_globals():
    _db._conn = None
    _db._db_path = None
    import finance_agent_backend.subject_matcher as _sm
    _sm._subjects_cache = None
    _sm._default_rule_matcher = None
    yield
    _db._conn = None
    _db._db_path = None
    import finance_agent_backend.subject_matcher as __sm
    __sm._subjects_cache = None


@pytest.fixture(autouse=True)
def _reset_db_state():
    from finance_agent_backend import db as _db
    _db.close_db()
    _db._conn = None
    _db._db_path = None
    yield
    _db.close_db()
    _db._conn = None
    _db._db_path = None


@pytest.fixture
def svc(tmp_db_path, monkeypatch):
    empty_json = os.path.join(os.path.dirname(tmp_db_path), "nonexistent.json")
    import finance_agent_backend.db as _db_mod
    import finance_agent_backend.paths as _paths
    monkeypatch.setattr(_paths, "get_config_path", lambda name="": empty_json)
    path = str(tmp_db_path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    _db.init_db(conn)
    _db._conn = conn
    _db._db_path = path
    return SubjectService()


class TestAddSubject:
    def test_add_success(self, svc):
        r = svc.add_subject({"code": "101", "name": "库存现金", "direction": "借"})
        print("ADDR", r)
        assert r["success"] is True

    def test_add_persists_in_db(self, svc):
        svc.add_subject({"code": "101", "name": "库存现金"})
        rows = _db.get_db().execute(
            "SELECT code, name, direction FROM subjects WHERE code=?", ("101",)
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["name"] == "库存现金"

    def test_add_duplicate_code_fails(self, svc):
        svc.add_subject({"code": "101", "name": "库存现金"})
        r = svc.add_subject({"code": "101", "name": "库存现金-2"})
        assert r["success"] is False
        assert "已存在" in r["error"]


class TestGetInfo:
    def test_get_info_after_add(self, svc):
        svc.add_subject({"code": "101", "name": "库存现金"})
        info = svc.get_info()
        assert info["success"] is True
        assert info["count"] == 1
        assert info["loaded"] is True
        assert info["subjects"][0]["code"] == "101"
        assert info["subjects"][0]["name"] == "库存现金"


class TestImportFromXlsx:
    def test_import_writes_db_and_returns_count(self, svc, monkeypatch):
        fake_subjects = {
            "1001": Subject(code="1001", name="库存现金", category="流动资产", direction="借", aux_category="", is_cash=True, enabled=True, full_name="库存现金"),
            "1002": Subject(code="1002", name="银行存款", category="流动资产", direction="借", aux_category="", is_cash=True, enabled=True, full_name="银行存款"),
        }
        mock_loader = MagicMock()
        mock_loader.load.return_value = fake_subjects
        monkeypatch.setattr(
            "finance_agent_backend.tools.subject_loader.SubjectLoader",
            lambda: mock_loader,
        )
        r = svc.import_from_xlsx("fake.xlsx")
        assert r["success"] is True
        assert r["count"] == 2
        assert "path" not in r

        rows = _db.get_db().execute("SELECT code, name FROM subjects ORDER BY code").fetchall()
        assert [(r["code"], r["name"]) for r in rows] == [("1001", "库存现金"), ("1002", "银行存款")]


class TestGetSubjectsCache:
    def test_get_subjects_reads_from_db(self, svc):
        svc.add_subject({"code": "101", "name": "库存现金"})
        import finance_agent_backend.subject_matcher as sm
        sm._subjects_cache = None
        result = sm.get_subjects()
        assert "101" in result
        assert result["101"]["name"] == "库存现金"
