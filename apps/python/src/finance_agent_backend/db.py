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

from .paths import get_db_path

# ---------------------------------------------------------------------------
# 模块级单例
# ---------------------------------------------------------------------------

_conn: sqlite3.Connection | None = None
_db_path: str | None = None



def get_db(db_path: str | None = None) -> sqlite3.Connection:
    """获取数据库连接。

    - 无参调用：返回模块级单例（生产环境默认路径，首次自动建表）。
    - 传入 db_path：返回该路径的新连接（测试隔离 / 多数据库场景）。
      调用方负责 close()。
    """
    if db_path is not None:
        # 测试或多数据库场景：每次创建独立连接
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    # 生产单例路径
    global _conn, _db_path
    if _conn is not None:
        return _conn

    _db_path = get_db_path()
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
        match_source    TEXT CHECK (match_source IN ('rule', 'history', 'manual', 'unmatched', 'auto')),
        original_summary TEXT,
        original_amount  REAL,
        is_manual       INTEGER DEFAULT 0,
        rule_id         TEXT DEFAULT '',
        aux_category    TEXT DEFAULT '',
        aux_category_name TEXT DEFAULT ''
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

CURRENT_SCHEMA_VERSION = 4


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """v2 迁移: 重建 voucher_draft_entry 表，放宽 match_source CHECK 约束允许 'auto'。"""
    conn.execute("""CREATE TABLE IF NOT EXISTS voucher_draft_entry_v2 (
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
        match_source    TEXT CHECK (match_source IN ('rule', 'history', 'manual', 'unmatched', 'auto')),
        original_summary TEXT,
        original_amount  REAL,
        is_manual       INTEGER DEFAULT 0,
        aux_category    TEXT DEFAULT '',
        aux_category_name TEXT DEFAULT ''
    )""")
    # 迁移数据
    old_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='voucher_draft_entry'"
    ).fetchone()
    if old_exists:
        conn.execute(
            """INSERT OR IGNORE INTO voucher_draft_entry_v2
               (id, draft_id, entry_seq, voucher_no, date, summary, subject_code, subject_name,
                debit_amount, credit_amount, direction, counterparty, match_source,
                original_summary, original_amount, is_manual, aux_category, aux_category_name)
               SELECT id, draft_id, entry_seq, voucher_no, date, summary, subject_code, subject_name,
                      debit_amount, credit_amount, direction, counterparty, match_source,
                      original_summary, original_amount, is_manual, aux_category, aux_category_name
               FROM voucher_draft_entry"""
        )
        conn.execute("DROP TABLE voucher_draft_entry")
        conn.execute("ALTER TABLE voucher_draft_entry_v2 RENAME TO voucher_draft_entry")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_draft_entry ON voucher_draft_entry(draft_id)")
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
        (2, datetime.now(timezone.utc).isoformat()),
    )


def _migrate_v3(conn: sqlite3.Connection) -> None:
    """v3 迁移: 添加 aux_category / aux_category_name 列。"""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(voucher_draft_entry)").fetchall()]
    if 'aux_category' not in cols:
        conn.execute("ALTER TABLE voucher_draft_entry ADD COLUMN aux_category TEXT DEFAULT ''")
    if 'aux_category_name' not in cols:
        conn.execute("ALTER TABLE voucher_draft_entry ADD COLUMN aux_category_name TEXT DEFAULT ''")
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
        (3, datetime.now(timezone.utc).isoformat()),
    )


def _migrate_v4(conn: sqlite3.Connection) -> None:
    """v4 迁移: 添加 rule_id 列。"""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(voucher_draft_entry)").fetchall()]
    if 'rule_id' not in cols:
        conn.execute("ALTER TABLE voucher_draft_entry ADD COLUMN rule_id TEXT DEFAULT ''")
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
        (4, datetime.now(timezone.utc).isoformat()),
    )


def init_db(conn: sqlite3.Connection) -> None:
    """幂等建表 + schema 迁移。可安全多次调用。"""
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)

    # ── schema 迁移 ──
    existing = conn.execute(
        "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1",
    ).fetchone()
    current = existing[0] if existing else 0

    if current < 1:
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (1, datetime.now(timezone.utc).isoformat()),
        )

    if current < 2:
        # v2: 放宽 match_source CHECK 约束，允许 'auto'
        _migrate_v2(conn)

    if current < 3:
        # v3: 添加 aux_category / aux_category_name 列
        _migrate_v3(conn)

    if current < 4:
        # v4: 添加 rule_id 列
        _migrate_v4(conn)

    conn.commit()