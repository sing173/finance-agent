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


class TestUpdateSubject:
    def test_update_nonexistent_returns_failure(self, svc):
        """修复回归: rowcount 检测不存在的 code。"""
        r = svc.update_subject({"code": "9999", "name": "不存在"})
        assert r["success"] is False
        assert "9999" in r["error"]

    def test_update_existing_persists_changes(self, svc):
        svc.add_subject({"code": "101", "name": "库存现金"})
        r = svc.update_subject({"code": "101", "name": "库存现金-更新", "category": "资产"})
        assert r["success"] is True
        rows = _db.get_db().execute(
            "SELECT name, category FROM subjects WHERE code=?", ("101",)
        ).fetchall()
        assert rows[0]["name"] == "库存现金-更新"
        assert rows[0]["category"] == "资产"


class TestDeleteSubject:
    def test_delete_nonexistent_returns_failure(self, svc):
        """修复回归: rowcount 检测不存在的 code。"""
        r = svc.delete_subject({"code": "9999"})
        assert r["success"] is False
        assert "9999" in r["error"]

    def test_delete_existing_removes_row(self, svc):
        svc.add_subject({"code": "101", "name": "库存现金"})
        r = svc.delete_subject({"code": "101"})
        assert r["success"] is True
        rows = _db.get_db().execute(
            "SELECT * FROM subjects WHERE code=?", ("101",)
        ).fetchall()
        assert len(rows) == 0


class TestSubjectBridgeRpc:
    """新增科目管理的三个 JSON-RPC 入口返回正确的 {success, error} 形态。"""

    def test_add_update_delete_roundtrip(self, tmp_db, monkeypatch):
        """tracer bullet: 通过 rpc_call 走完整 add→update→delete 链路。"""
        from finance_agent_backend import db as _db
        import finance_agent_backend.subject_matcher as _sm

        path = str(tmp_db)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        _db.init_db(conn)
        _db._conn = conn
        _db._db_path = path
        _sm._subjects_cache = None

        try:
            from tests.conftest import rpc_call

            add_r = rpc_call("add_subject", {"code": "101", "name": "库存现金", "category": "资产"})
            assert add_r.get("success") is True
            assert add_r["code"] == "101"

            update_r = rpc_call("update_subject", {"code": "101", "name": "库存现金-新"})
            assert update_r.get("success") is True

            delete_r = rpc_call("delete_subject", {"code": "101"})
            assert delete_r.get("success") is True
        finally:
            _db.close_db()
            _db._conn = None
            _db._db_path = None
            _sm._subjects_cache = None

    def test_add_subject_persists_aux_fields(self, tmp_db, monkeypatch):
        """新增科目时 aux_category / aux_category_name 正确写入 DB。"""
        from finance_agent_backend import db as _db
        import finance_agent_backend.subject_matcher as _sm

        path = str(tmp_db)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        _db.init_db(conn)
        _db._conn = conn
        _db._db_path = path
        _sm._subjects_cache = None

        try:
            from tests.conftest import rpc_call

            r = rpc_call("add_subject", {
                "code": "2202",
                "name": "应付账款",
                "aux_category": "04",
                "aux_category_name": "公共部门",
            })
            assert r.get("success") is True

            row = conn.execute(
                "SELECT aux_category, aux_category_name FROM subjects WHERE code=?",
                ("2202",),
            ).fetchone()
            assert row["aux_category"] == "04"
            assert row["aux_category_name"] == "公共部门"
        finally:
            _db.close_db()
            _db._conn = None
            _db._db_path = None
            _sm._subjects_cache = None

    def test_update_delete_nonexistent_code_via_rpc(self, tmp_db, monkeypatch):
        """通过 RPC 验证 rowcount 修复：操作不存在的 code 返回 success=False。"""
        from finance_agent_backend import db as _db
        import finance_agent_backend.subject_matcher as _sm

        path = str(tmp_db)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        _db.init_db(conn)
        _db._conn = conn
        _db._db_path = path
        _sm._subjects_cache = None

        try:
            from tests.conftest import rpc_call

            upd = rpc_call("update_subject", {"code": "9999", "name": "X"})
            assert upd.get("success") is False
            assert "9999" in upd.get("error", "")

            dele = rpc_call("delete_subject", {"code": "8888"})
            assert dele.get("success") is False
            assert "8888" in dele.get("error", "")
        finally:
            _db.close_db()
            _db._conn = None
            _db._db_path = None
            _sm._subjects_cache = None

    def test_update_partial_fields_preserves_aux(self, tmp_db, monkeypatch):
        """前端只传 name 时，aux_category / aux_category_name 不应被清空。"""
        from finance_agent_backend import db as _db
        import finance_agent_backend.subject_matcher as _sm

        path = str(tmp_db)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        _db.init_db(conn)
        _db._conn = conn
        _db._db_path = path
        _sm._subjects_cache = None

        try:
            from tests.conftest import rpc_call

            rpc_call("add_subject", {
                "code": "2202",
                "name": "应付账款",
                "aux_category": "04",
                "aux_category_name": "公共部门",
            })

            rpc_call("update_subject", {"code": "2202", "name": "应付账款-新"})

            row = conn.execute(
                "SELECT name, aux_category, aux_category_name FROM subjects WHERE code=?",
                ("2202",),
            ).fetchone()
            assert row["name"] == "应付账款-新"
            assert row["aux_category"] == "04"
            assert row["aux_category_name"] == "公共部门"
        finally:
            _db.close_db()
            _db._conn = None
            _db._db_path = None
            _sm._subjects_cache = None

    def test_explicit_empty_clears_field(self, tmp_db, monkeypatch):
        """显式传入空串时应清空字段，而非保留原值。"""
        from finance_agent_backend import db as _db
        import finance_agent_backend.subject_matcher as _sm

        path = str(tmp_db)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        _db.init_db(conn)
        _db._conn = conn
        _db._db_path = path
        _sm._subjects_cache = None

        try:
            from tests.conftest import rpc_call

            rpc_call("add_subject", {
                "code": "2202",
                "name": "应付账款",
                "aux_category": "04",
                "aux_category_name": "公共部门",
            })

            # 显式传空串清空辅助核算字段
            rpc_call("update_subject", {
                "code": "2202",
                "aux_category": "",
                "aux_category_name": "",
            })

            row = conn.execute(
                "SELECT aux_category, aux_category_name FROM subjects WHERE code=?",
                ("2202",),
            ).fetchone()
            assert row["aux_category"] == ""
            assert row["aux_category_name"] == ""
        finally:
            _db.close_db()
            _db._conn = None
            _db._db_path = None
            _sm._subjects_cache = None
