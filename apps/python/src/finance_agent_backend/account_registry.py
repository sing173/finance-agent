"""Account registry — account→subject matching service."""
import time
from typing import List, Optional

from finance_agent_backend.models import AccountEntry
from finance_agent_backend.repo.account_mapping_repo import AccountMappingRepository

DEFAULT_BANK_SUBJECT_CODE = '10002'


# ---------------------------------------------------------------------------
# Service layer — 内存 CRUD + match
# ---------------------------------------------------------------------------

class AccountRegistry:
    """账号-科目匹配服务。使用 repo 进行持久化。"""

    def __init__(self, repo: AccountMappingRepository, subject_codes: Optional[set] = None):
        """接收 repo 实例，首次查询时加载并缓存条目列表。

        *subject_codes* 用于 add() 的 subjectCode 校验，可选。
        """
        self._repo = repo
        self._subject_codes: set = subject_codes or set()
        self._entries_cache: List[AccountEntry] | None = None

    def _get_entries(self) -> List[AccountEntry]:
        """懒加载并缓存条目列表。"""
        if self._entries_cache is None:
            self._entries_cache = self._repo.find_all()
        return self._entries_cache

    # ------------------------------------------------------------------ #
    #  Query
    # ------------------------------------------------------------------ #

    def list_all(self) -> List[AccountEntry]:
        """Return all entries (used by tests, Phase 1 CRUD UI)."""
        return self._get_entries()

    def match_by_account(self, account_number: str) -> Optional[AccountEntry]:
        """Match *account_number* against registered entries.

        Priority: exact > suffix. Returns first hit or None.
        """
        entries = self._get_entries()
        # 1) exact matches
        for entry in entries:
            if entry.matchType == 'exact' and entry.pattern == account_number:
                return entry

        # 2) suffix matches
        for entry in entries:
            if entry.matchType == 'suffix' and account_number.endswith(entry.pattern):
                return entry

        return None

    # ------------------------------------------------------------------ #
    #  CRUD (Phase 1)
    # ------------------------------------------------------------------ #

    def add(self, entry: AccountEntry) -> AccountEntry:
        """新增条目，自动生成 id（若为空）。"""
        if not entry.bankCode:
            raise ValueError("bankCode 不能为空")
        if self._subject_codes and entry.subjectCode not in self._subject_codes:
            raise ValueError(f"subjectCode {entry.subjectCode} 不存在于科目表")
        if not entry.id:
            entry.id = str(int(time.time() * 1000))
        saved = self._repo.save(entry)
        self._entries_cache = None
        return saved

    def update(self, entry: AccountEntry) -> AccountEntry:
        """更新已有条目（按 id 匹配）。"""
        existing = self._repo.find_by_id(entry.id)
        if not existing:
            raise ValueError(f"条目 id={entry.id} 不存在")
        saved = self._repo.save(entry)
        self._entries_cache = None
        return saved

    def delete(self, entry_id: str) -> None:
        """删除条目（按 id）。"""
        self._repo.delete(entry_id)
        self._entries_cache = None