"""AccountRegistryService — 账号-科目映射的 CRUD 业务编排。"""
from __future__ import annotations

from finance_agent_backend.account_registry import (
    AccountEntry,
    AccountMappingRepository,
    AccountRegistry,
    DEFAULT_BANK_SUBJECT_CODE,
    get_account_entries,
    invalidate_account_entries,
)
from finance_agent_backend.paths import get_config_path


class AccountRegistryService:
    """封装 AccountRegistry + AccountMappingRepository 的 CRUD 操作。"""

    def __init__(self, config_path: str | None = None):
        self._config_path = config_path or get_config_path('account_mapping.json')
        self._use_cache = config_path is None

    def _open(self, with_subject_codes: bool = False) -> tuple[AccountRegistry, AccountMappingRepository]:
        """构造 registry + repo 对。"""
        repo = AccountMappingRepository(self._config_path)
        if self._use_cache:
            entries = get_account_entries()
        else:
            entries = repo.load()
        subject_codes = None
        if with_subject_codes:
            from finance_agent_backend.services.subject_service import SubjectService
            subject_codes = SubjectService().get_subject_codes()
        registry = AccountRegistry(entries, subject_codes=subject_codes)
        return registry, repo

    @staticmethod
    def _serialize(entry: AccountEntry) -> dict:
        return {
            "id": entry.id,
            "matchType": entry.matchType,
            "pattern": entry.pattern,
            "bank": entry.bank,
            "bankCode": entry.bankCode,
            "subjectCode": entry.subjectCode,
            "subjectName": entry.subjectName,
        }

    def list_all(self) -> dict:
        registry, _ = self._open()
        return {
            "success": True,
            "accounts": [self._serialize(e) for e in registry.list_all()],
        }

    def match(self, account_number: str) -> dict:
        registry, _ = self._open()
        entry = registry.match_by_account(account_number)
        return {
            "success": True,
            "entry": self._serialize(entry) if entry else None,
        }

    def add(self, entry: AccountEntry) -> dict:
        registry, repo = self._open(with_subject_codes=True)
        registry.add(entry)
        repo.save(registry.list_all())
        return {
            "success": True,
            "id": entry.id,
            "entry": self._serialize(entry),
        }

    def update(self, entry: AccountEntry) -> dict:
        registry, repo = self._open(with_subject_codes=True)
        registry.update(entry)
        repo.save(registry.list_all())
        return {"success": True, "entry": self._serialize(entry)}

    def delete(self, entry_id: str) -> dict:
        registry, repo = self._open()
        registry.delete(entry_id)
        repo.save(registry.list_all())
        return {"success": True}
