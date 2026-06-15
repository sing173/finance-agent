"""Tests for voucher export RPCs (Issue #36).

Tests: voucher.export, voucher.load_draft, voucher.list_drafts, voucher.delete_draft.
"""
import os, sys, sqlite3


import pytest
from finance_agent_backend.db import init_db



@pytest.fixture
def draft_id(tmp_db):
    """Pre-seed a draft with 2 entries for integration tests."""
    import uuid
    did = str(uuid.uuid4())[:8]
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO voucher_draft (id, name, period, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (did, "测试草稿", "2026年第3期", "2026-05-01T00:00:00", "2026-05-01T00:00:00"),
    )
    for i, (code, name, debit, credit, manual) in enumerate([
        ("5060203", "管理费用_物业管理费", 2400.0, None, 0),
        ("1000201", "银行存款-工行基本户", None, 2400.0, 0),
    ]):
        conn.execute(
            """INSERT INTO voucher_draft_entry
               (draft_id, entry_seq, voucher_no, date, summary, subject_code, subject_name,
                debit_amount, credit_amount, direction, match_source, is_manual)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (did, i+1, 1, "2026-03-01", f"摘要{i+1}", code, name,
             debit, credit, "expense", "rule", manual),
        )
    conn.commit()
    conn.close()
    return did


@pytest.fixture
def export_path(tmp_path):
    """临时导出路径（pytest 自动清理）。"""
    return str(tmp_path / "voucher.xlsx")


class TestLoadDraft:
    def test_load_existing_draft(self, tmp_db, draft_id):
        from finance_agent_backend.bridge import handle_request
        from finance_agent_backend import db as _db

        _db.close_db()
        _db._conn = None

        response = handle_request({
            "jsonrpc": "2.0", "id": 1,
            "method": "voucher.load_draft",
            "params": {"draft_id": draft_id, "db_path": tmp_db},
        })
        result = response["result"]
        assert result["success"] is True
        assert result["draft"]["name"] == "测试草稿"
        assert len(result["draft"]["entries"]) == 2
        _db.close_db()

    def test_load_nonexistent_draft(self, tmp_db):
        from finance_agent_backend.bridge import handle_request
        from finance_agent_backend import db as _db

        _db.close_db()
        _db._conn = None

        response = handle_request({
            "jsonrpc": "2.0", "id": 2,
            "method": "voucher.load_draft",
            "params": {"draft_id": "nonexistent", "db_path": tmp_db},
        })
        result = response["result"]
        assert result["success"] is False
        _db.close_db()


class TestListDrafts:
    def test_list_drafts(self, tmp_db, draft_id):
        from finance_agent_backend.bridge import handle_request
        from finance_agent_backend import db as _db

        _db.close_db()
        _db._conn = None

        response = handle_request({
            "jsonrpc": "2.0", "id": 3,
            "method": "voucher.list_drafts",
            "params": {"db_path": tmp_db},
        })
        result = response["result"]
        assert result["success"] is True
        assert len(result["drafts"]) >= 1
        assert result["drafts"][0]["name"] == "测试草稿"
        _db.close_db()

    def test_list_drafts_empty(self, tmp_db):
        from finance_agent_backend.bridge import handle_request
        from finance_agent_backend import db as _db

        _db.close_db()
        _db._conn = None

        response = handle_request({
            "jsonrpc": "2.0", "id": 4,
            "method": "voucher.list_drafts",
            "params": {"db_path": tmp_db},
        })
        result = response["result"]
        assert result["success"] is True
        assert result["drafts"] == []
        _db.close_db()


class TestDeleteDraft:
    def test_delete_draft(self, tmp_db, draft_id):
        from finance_agent_backend.bridge import handle_request
        from finance_agent_backend import db as _db

        _db.close_db()
        _db._conn = None

        response = handle_request({
            "jsonrpc": "2.0", "id": 5,
            "method": "voucher.delete_draft",
            "params": {"draft_id": draft_id, "db_path": tmp_db},
        })
        result = response["result"]
        assert result["success"] is True

        # Verify DB cleaned
        conn = sqlite3.connect(tmp_db)
        n_drafts = conn.execute("SELECT COUNT(*) FROM voucher_draft").fetchone()[0]
        n_entries = conn.execute("SELECT COUNT(*) FROM voucher_draft_entry").fetchone()[0]
        conn.close()
        assert n_drafts == 0
        assert n_entries == 0  # CASCADE
        _db.close_db()


class TestExport:
    def test_export_marks_draft_exported(self, tmp_db, draft_id, export_path):
        from finance_agent_backend.bridge import handle_request
        from finance_agent_backend import db as _db

        _db.close_db()
        _db._conn = None

        response = handle_request({
            "jsonrpc": "2.0", "id": 6,
            "method": "voucher.export",
            "params": {
                "draft_id": draft_id,
                "period": "2026年第3期",
                "output_path": export_path,
                "source_files": ["test.pdf"],
                "db_path": tmp_db,
            },
        })
        result = response["result"]
        assert result["success"] is True
        assert result["file_path"] == export_path
        assert os.path.exists(export_path)

        # Draft status → exported
        conn = sqlite3.connect(tmp_db)
        status = conn.execute("SELECT status FROM voucher_draft WHERE id=?", (draft_id,)).fetchone()
        conn.close()
        assert status[0] == "exported"
        _db.close_db()

    def test_export_writes_audit_log(self, tmp_db, draft_id, export_path):
        from finance_agent_backend.bridge import handle_request
        from finance_agent_backend import db as _db

        _db.close_db()
        _db._conn = None

        handle_request({
            "jsonrpc": "2.0", "id": 7,
            "method": "voucher.export",
            "params": {
                "draft_id": draft_id,
                "period": "2026年第3期",
                "output_path": export_path,
                "source_files": ["test.pdf"],
                "db_path": tmp_db,
            },
        })

        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        log = conn.execute("SELECT * FROM export_log").fetchone()
        conn.close()
        assert log is not None
        assert log["draft_id"] == draft_id
        _db.close_db()

    def test_export_writes_subject_history_for_manual(self, tmp_db, export_path):
        """Only is_manual=true entries → subject_history."""
        import uuid
        from finance_agent_backend.bridge import handle_request
        from finance_agent_backend import db as _db

        # Create draft with 1 manual + 1 auto entry
        did = str(uuid.uuid4())[:8]
        conn = sqlite3.connect(tmp_db)
        conn.execute(
            "INSERT INTO voucher_draft (id, name, period, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (did, "手动测试", "2026-Q3", "2026-05-01T00:00:00", "2026-05-01T00:00:00"),
        )
        conn.execute(
            """INSERT INTO voucher_draft_entry
               (draft_id, entry_seq, voucher_no, date, summary, subject_code, subject_name,
                debit_amount, credit_amount, direction, match_source, is_manual, counterparty)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (did, 1, 1, "2026-03-01", "手动修正摘要", "5060203", "管理费用", 100.0, None, "expense", "manual", 1, "启胜物业"),
        )
        conn.execute(
            """INSERT INTO voucher_draft_entry
               (draft_id, entry_seq, voucher_no, date, summary, subject_code, subject_name,
                debit_amount, credit_amount, direction, match_source, is_manual)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (did, 2, 1, "2026-03-01", "自动匹配摘要", "1000201", "银行存款", None, 100.0, "expense", "rule", 0),
        )
        conn.commit()
        conn.close()

        _db.close_db()
        _db._conn = None

        handle_request({
            "jsonrpc": "2.0", "id": 8,
            "method": "voucher.export",
            "params": {
                "draft_id": did,
                "period": "2026-Q3",
                "output_path": export_path,
                "source_files": [],
                "db_path": tmp_db,
            },
        })

        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM subject_history").fetchall()
        conn.close()
        assert len(rows) == 1  # Only the manual entry
        assert rows[0]["subject_code"] == "5060203"
        _db.close_db()