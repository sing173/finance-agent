"""Tests for db.py — SQLite infrastructure (Issue #31).

Tests verify behavior through public interface: init_db(), get_db(), close_db().
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from finance_agent_backend import db


@pytest.fixture
def tmp_db_path(tmp_path):
    """临时数据库文件，pytest 自动清理。"""
    path = str(tmp_path / "test.db")
    return path


@pytest.fixture(autouse=True)
def reset_db_module():
    """每个测试前重置 db 模块状态。"""
    db.close_db()
    db._conn = None
    db._db_path = None
    yield
    db.close_db()
    db._conn = None
    db._db_path = None


class TestInitDB:
    """建表幂等 — 核心行为。"""

    def test_creates_all_five_tables(self, tmp_db_path):
        """首次 init_db 创建全部 5 张表。"""
        conn = sqlite3.connect(tmp_db_path)
        db.init_db(conn)

        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [t[0] for t in tables]

        assert 'subject_history' in names
        assert 'voucher_draft' in names
        assert 'voucher_draft_entry' in names
        assert 'export_log' in names
        assert 'schema_version' in names

    def test_idempotent(self, tmp_db_path):
        """再次调用 init_db 不报错（幂等）。"""
        conn = sqlite3.connect(tmp_db_path)
        db.init_db(conn)
        # Second call must not raise
        db.init_db(conn)

        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        assert len(tables) >= 5

    def test_wal_mode(self, tmp_db_path):
        """get_db() 应设置 WAL 模式。"""
        db._db_path = tmp_db_path
        conn = db.get_db()
        db.init_db(conn)

        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal.lower() == 'wal'
        db.close_db()

    def test_schema_version_recorded(self, tmp_db_path):
        """init_db 写入 schema_version 表。"""
        conn = sqlite3.connect(tmp_db_path)
        db.init_db(conn)

        rows = conn.execute("SELECT version, applied_at FROM schema_version").fetchall()
        assert len(rows) >= 1
        assert rows[0][0] == 1  # version
        assert rows[0][1]       # applied_at timestamp non-empty


class TestWriteRead:
    """写入 + 查询 — 基本数据路径。"""

    def test_insert_and_select(self, tmp_db_path):
        conn = sqlite3.connect(tmp_db_path)
        db.init_db(conn)

        conn.execute(
            "INSERT INTO subject_history (summary, summary_hash, subject_code, subject_name, direction, confirmed_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ('支付物业费', 'abc123', '5060203', '管理费用_物业管理费', 'expense', '2026-05-25T10:00:00'),
        )
        conn.commit()

        row = conn.execute("SELECT subject_code, subject_name FROM subject_history WHERE summary_hash=?", ('abc123',)).fetchone()
        assert row == ('5060203', '管理费用_物业管理费')

    def test_unique_constraint(self, tmp_db_path):
        """UNIQUE(summary_hash, subject_code, direction) 防重复。"""
        conn = sqlite3.connect(tmp_db_path)
        db.init_db(conn)

        conn.execute(
            "INSERT OR IGNORE INTO subject_history (summary, summary_hash, subject_code, subject_name, direction, confirmed_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ('支付物业费', 'abc123', '5060203', '管理费用_物业管理费', 'expense', '2026-05-25T10:00:00'),
        )
        # Duplicate insert with same (hash, code, direction) → ignored
        conn.execute(
            "INSERT OR IGNORE INTO subject_history (summary, summary_hash, subject_code, subject_name, direction, confirmed_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ('支付物业费 duplicate', 'abc123', '5060203', '管理费用_物业管理费', 'expense', '2026-05-25T11:00:00'),
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM subject_history WHERE summary_hash=?", ('abc123',)).fetchone()[0]
        assert count == 1


class TestGetDB:
    """get_db() / close_db() 连接管理。"""

    def test_get_db_creates_connection(self, tmp_db_path):
        db._db_path = tmp_db_path
        conn = db.get_db()
        assert isinstance(conn, sqlite3.Connection)
        db.close_db()

    def test_get_db_singleton(self, tmp_db_path):
        """两次 get_db 返回同一连接。"""
        db._db_path = tmp_db_path
        c1 = db.get_db()
        c2 = db.get_db()
        assert c1 is c2
        db.close_db()


class TestDBHealthRPC:
    """db.health JSON-RPC 方法。"""

    def test_returns_all_tables(self, tmp_db_path):
        from finance_agent_backend.bridge import handle_request

        # 绕过 get_db 单例——直接给 init_db 传入临时连接
        conn = sqlite3.connect(tmp_db_path)
        db.init_db(conn)
        conn.close()

        # 偷梁换柱——让 get_db 返回我们的临时库
        db._db_path = tmp_db_path
        conn = db.get_db()
        db.init_db(conn)

        response = handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "db.health",
            "params": {},
        })
        db.close_db()

        assert response.get("id") == 1
        result = response.get("result", {})
        assert result.get("status") == "ok"
        tables = result.get("tables", [])
        assert "subject_history" in tables
        assert "voucher_draft" in tables
        assert "voucher_draft_entry" in tables
        assert "export_log" in tables
        assert "schema_version" in tables
        assert len(tables) == 6  # 5 张业务表 + sqlite_sequence (AUTOINCREMENT)

    def test_health_auto_init_db(self):
        """首次调用 get_db 时自动创建数据库，health 返回 ok。"""
        from finance_agent_backend.bridge import handle_request

        # 重置
        db._conn = None
        db._db_path = None

        response = handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "db.health",
            "params": {},
        })

        result = response.get("result", {})
        # get_db() 自动创建连接 → health 永远返回 ok
        assert result.get("status") == "ok"
        assert len(result.get("tables", [])) >= 6

        # 清理：删除自动创建的 db 文件
        if db._db_path and os.path.exists(db._db_path):
            try:
                os.unlink(db._db_path)
            except OSError:
                pass
        db.close_db()