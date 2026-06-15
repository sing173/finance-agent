"""凭证草稿 Repository — 接管 bridge.py 中凭证相关的 SQL"""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from finance_agent_backend.models import PipelineEntry
from .base import BaseRepository


@dataclass
class VoucherDraft:
    id: str
    name: str = ""
    period: str = ""
    status: str = "draft"
    created_at: str = ""
    updated_at: str = ""


class VoucherDraftRepository:
    """凭证草稿 + 分录明细的 Repository。

    所有 INSERT / SELECT 字段列表由 dataclass 自动生成，
    新增字段只需修改 VoucherDraft / PipelineEntry。
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._draft = BaseRepository(conn, "voucher_draft", VoucherDraft, pk="id")
        self._entry = BaseRepository(
            conn,
            "voucher_draft_entry",
            PipelineEntry,
            pk="id",
            insert_exclude=["id"],
        )

    # ── Draft ──

    def create(self, name: str, period: str) -> str:
        draft_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        self._draft.insert(
            VoucherDraft(
                id=draft_id,
                name=name,
                period=period,
                created_at=now,
                updated_at=now,
            )
        )
        return draft_id

    def get(self, draft_id: str) -> VoucherDraft | None:
        return self._draft.find_by_pk(draft_id)

    def list_all(self) -> list[dict]:
        """含 entry_count 的列表（唯一需手写的 JOIN SQL）。"""
        rows = self.conn.execute(
            """SELECT d.id, d.name, d.period, d.status, d.created_at, d.updated_at,
                      COUNT(e.id) as entry_count
               FROM voucher_draft d
               LEFT JOIN voucher_draft_entry e ON e.draft_id = d.id
               GROUP BY d.id ORDER BY d.updated_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, draft_id: str) -> None:
        self._draft.delete_by_pk(draft_id)  # CASCADE 自动清理 entries

    def mark_exported(self, draft_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE voucher_draft SET status = 'exported', updated_at = ? WHERE id = ?",
            (now, draft_id),
        )

    # ── Entries ──

    def insert_entries(self, draft_id: str, entries: list[PipelineEntry]) -> None:
        self._entry.insert_many(entries, extra={"draft_id": draft_id})

    def get_entries(self, draft_id: str) -> list[PipelineEntry]:
        return self._entry.select(
            where="draft_id = ?",
            params=(draft_id,),
            order_by="voucher_no, entry_seq",
        )
