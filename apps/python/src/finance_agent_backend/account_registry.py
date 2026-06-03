"""Account registry — load account→subject mappings from account_mapping.json.

Phase 0: match_by_account() only. Phase 1 will add CRUD methods.
"""
import json
import os
from typing import List, Optional

from finance_agent_backend.models import AccountEntry
from finance_agent_backend.paths import get_config_path


# ---------------------------------------------------------------------------
# Repository — 数据访问层（JSON 读写）
# ---------------------------------------------------------------------------

class AccountMappingRepository:
    """负责 account_mapping.json 的加载和持久化。

    不持有业务逻辑，只做 JSON ↔ AccountEntry 的转换。
    Phase 3 可替换为 SQLite 实现，上层 AccountRegistry 无需改动。
    """

    def __init__(self, config_path: str):
        self._config_path = config_path

    def load(self) -> List[AccountEntry]:
        """从 JSON 文件加载所有账号-科目映射。"""
        with open(self._config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        entries = []
        for item in data.get('accounts', []):
            entries.append(AccountEntry(
                id=item.get('id', ''),
                matchType=item.get('matchType', 'suffix'),
                pattern=item.get('pattern', ''),
                bank=item.get('bank', ''),
                bankCode=item.get('bankCode', ''),
                subjectCode=item.get('subjectCode', ''),
                subjectName=item.get('subjectName', ''),
            ))
        return entries

    def save(self, entries: List[AccountEntry], default_bank_subject_code: str = "10002") -> None:
        """将条目列表持久化到 JSON 文件。"""
        data = {
            "accounts": [
                {
                    "id": e.id,
                    "matchType": e.matchType,
                    "pattern": e.pattern,
                    "bank": e.bank,
                    "bankCode": e.bankCode,
                    "subjectCode": e.subjectCode,
                    "subjectName": e.subjectName,
                }
                for e in entries
            ],
            "defaultBankSubjectCode": default_bank_subject_code,
        }
        with open(self._config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Service layer — 内存 CRUD + match
# ---------------------------------------------------------------------------

class AccountRegistry:
    """Loads and queries account→subject mappings from account_mapping.json."""

    def __init__(self, entries: List[AccountEntry], subject_codes: Optional[set] = None):
        """纯内存服务层，接收已加载的条目列表。

        *entries* 来自 AccountMappingRepository.load()。
        *subject_codes* 用于 add() 的 subjectCode 校验，可选。
        """
        self._entries: List[AccountEntry] = list(entries)
        self._subject_codes: set = subject_codes or set()

    # ------------------------------------------------------------------ #
    #  Query
    # ------------------------------------------------------------------ #

    def list_all(self) -> List[AccountEntry]:
        """Return all entries (used by tests, Phase 1 CRUD UI)."""
        return list(self._entries)

    def match_by_account(self, account_number: str) -> Optional[AccountEntry]:
        """Match *account_number* against registered entries.

        Priority: exact > suffix. Returns first hit or None.
        """
        # 1) exact matches
        for entry in self._entries:
            if entry.matchType == 'exact' and entry.pattern == account_number:
                return entry

        # 2) suffix matches
        for entry in self._entries:
            if entry.matchType == 'suffix' and account_number.endswith(entry.pattern):
                return entry

        return None

    # ------------------------------------------------------------------ #
    #  CRUD (Phase 1)
    # ------------------------------------------------------------------ #

    def add(self, entry: AccountEntry) -> None:
        """新增条目，自动生成 id（若为空）。"""
        import time
        if not entry.bankCode:
            raise ValueError("bankCode 不能为空")
        if self._subject_codes and entry.subjectCode not in self._subject_codes:
            raise ValueError(f"subjectCode {entry.subjectCode} 不存在于科目表")
        if not entry.id:
            entry.id = str(int(time.time() * 1000))
        self._entries.append(entry)

    def update(self, entry: AccountEntry) -> None:
        """更新已有条目（按 id 匹配）。"""
        for i, e in enumerate(self._entries):
            if e.id == entry.id:
                self._entries[i] = entry
                return
        raise ValueError(f"条目 id={entry.id} 不存在")

    def delete(self, entry_id: str) -> None:
        """删除条目（按 id）。"""
        self._entries = [e for e in self._entries if e.id != entry_id]


# ------------------------------------------------------------------ #
#  Singleton accessor (DEPRECATED — use dependency injection instead)
# ------------------------------------------------------------------ #
# NOTE: get_registry() is kept for backward compatibility with bridge.py
# and any external callers. New code should use:
#   repo = AccountMappingRepository(path)
#   registry = AccountRegistry(repo.load(), subject_codes)
# ------------------------------------------------------------------ #

_registry: Optional[AccountRegistry] = None


def get_registry() -> AccountRegistry:
    """[DEPRECATED] Return the singleton AccountRegistry.

    New code should inject AccountRegistry directly instead of calling
    this global accessor, to avoid hidden state and improve testability.
    """
    global _registry
    if _registry is None:
        repo = AccountMappingRepository(_default_config_path())
        _registry = AccountRegistry(repo.load())
    return _registry


def _default_config_path() -> str:
    """account_mapping.json 默认路径（委托 paths 模块）。"""
    return get_config_path('account_mapping.json')