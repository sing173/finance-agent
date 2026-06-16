"""账号-科目映射 Repository — account_mapping 表 CRUD"""
from __future__ import annotations

import sqlite3

from finance_agent_backend.models import AccountEntry
from .base import BaseRepository


class AccountMappingRepository:
    """account_mapping 表的 Repository。

    使用 BaseRepository 自动生成 SQL，新增字段只需修改 AccountEntry dataclass。
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._repo = BaseRepository(conn, "account_mapping", AccountEntry, pk="id")

    def find_all(self) -> list[AccountEntry]:
        """获取所有账号-科目映射。"""
        return self._repo.find_all()

    def save(self, entry: AccountEntry) -> AccountEntry:
        """新增或更新条目。"""
        return self._repo.save(entry)

    def delete(self, entry_id: str) -> None:
        """按 id 删除条目。"""
        self._repo.delete_by_pk(entry_id)

    def find_by_id(self, entry_id: str) -> AccountEntry | None:
        """按 id 查找条目。"""
        return self._repo.find_by_pk(entry_id)
