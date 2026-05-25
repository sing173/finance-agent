"""SQLite 运行时数据库 — WAL 模式、建表、连接管理 (Issue #31).

用法::

    from finance_agent_backend.db import init_db, get_db, close_db

    conn = get_db()
    init_db(conn)          # 幂等建表 + schema 迁移
    conn.execute("INSERT ...")
    conn.commit()
    close_db()

存储路径:
  开发环境: 项目根 logs/ 同级
  打包环境: %APPDATA%/FinanceAssistant/data.db

注意: 当前 stdio JSON-RPC 单线程，不需要连接池或 thread-safety。
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# 模块级单例
# ---------------------------------------------------------------------------

_conn: sqlite3.Connection | None = None
_db_path: str | None = None


def _default_db_path() -> str:
    """推导默认数据库路径。"""
    if getattr(sys, 'frozen', False):
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        return os.path.join(base, 'FinanceAssistant', 'data.db')
    else:
        # 开发环境：与 bridge.py 同级目录
        import finance_agent_backend
        backend_dir = os.path.dirname(os.path.abspath(finance_agent_backend.__file__))
        return os.path.join(os.path.dirname(backend_dir), 'data.db')


def get_db(db_path: str | None = None) -> sqlite3.Connection:
    """获取数据库连接（模块级单例）。首次调用自动建表。"""
    global _conn, _db_path

    if _conn is not None:
        return _conn

    _db_path = db_path or _default_db_path()
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)

    _conn = sqlite3.connect(_db_path)
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    _conn.row_factory = sqlite3.Row

    return _conn


def close_db() -> None:
    """关闭数据库连接。"""
    global _conn, _db_path
    if _conn is not None:
        _conn.close()
        _conn = None
        _db_path = None


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_STATEMENTS: list[str] = [
    # ── 历史学习库 ──
    """CREATE TABLE IF NOT EXISTS subject_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        summary         TEXT    NOT NULL,
        summary_hash    TEXT    NOT NULL,
        subject_code    TEXT    NOT NULL,
        subject_name    TEXT,
        direction       TEXT    NOT NULL CHECK (direction IN ('expense', 'income')),
        counterparty    TEXT,
        confirmed_at    TEXT    NOT NULL,
        voucher_id      TEXT,
        UNIQUE(summary_hash, subject_code, direction)
    )""",
    """CREATE INDEX IF NOT EXISTS idx_history_code_dir
        ON subject_history(subject_code, direction)""",
    """CREATE INDEX IF NOT EXISTS idx_history_hash
        ON subject_history(summary_hash)""",

    # ── 凭证草稿 ──
    """CREATE TABLE IF NOT EXISTS voucher_draft (
        id              TEXT PRIMARY KEY,
        name            TEXT,
        period          TEXT,
        status          TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'confirmed', 'exported')),
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    )""",

    # ── 草稿分录明细 ──
    """CREATE TABLE IF NOT EXISTS voucher_draft_entry (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        draft_id        TEXT NOT NULL REFERENCES voucher_draft(id) ON DELETE CASCADE,
        entry_seq       INTEGER NOT NULL,
        voucher_no      INTEGER NOT NULL,
        date            TEXT NOT NULL,
        summary         TEXT NOT NULL,
        subject_code    TEXT NOT NULL,
        subject_name    TEXT,
        debit_amount    REAL,
        credit_amount   REAL,
        direction       TEXT,
        counterparty    TEXT,
        match_source    TEXT CHECK (match_source IN ('rule', 'history', 'manual', 'unmatched')),
        original_summary TEXT,
        original_amount  REAL,
        is_manual       INTEGER DEFAULT 0
    )""",
    """CREATE INDEX IF NOT EXISTS idx_draft_entry
        ON voucher_draft_entry(draft_id)""",

    # ── 导出审计日志 ──
    """CREATE TABLE IF NOT EXISTS export_log (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        exported_at       TEXT NOT NULL,
        period            TEXT,
        file_path         TEXT NOT NULL,
        voucher_count     INTEGER,
        entry_count       INTEGER,
        transaction_count INTEGER,
        source_files      TEXT,
        match_stats       TEXT,
        draft_id          TEXT
    )""",

    # ── Schema 版本管理 ──
    """CREATE TABLE IF NOT EXISTS schema_version (
        version   INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )""",
]

CURRENT_SCHEMA_VERSION = 1


def init_db(conn: sqlite3.Connection) -> None:
    """幂等建表 + schema 迁移。可安全多次调用。"""
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)

    # 写入 schema version（首次）
    existing = conn.execute(
        "SELECT version FROM schema_version WHERE version = ?",
        (CURRENT_SCHEMA_VERSION,),
    ).fetchone()

    if existing is None:
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (CURRENT_SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
        )

    conn.commit()