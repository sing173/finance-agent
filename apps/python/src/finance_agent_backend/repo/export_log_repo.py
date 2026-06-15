"""导出审计日志 Repository"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .base import BaseRepository


@dataclass
class ExportLog:
    id: int | None = None
    exported_at: str = ""
    period: str = ""
    file_path: str = ""
    voucher_count: int | None = None
    entry_count: int | None = None
    transaction_count: int | None = None
    source_files: str = ""
    match_stats: str = ""
    draft_id: str = ""


class ExportLogRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._base = BaseRepository(
            conn, "export_log", ExportLog, pk="id", insert_exclude=["id"]
        )

    def insert(self, log: ExportLog) -> None:
        self._base.insert(log)
