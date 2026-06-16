"""AccountRegistryService — 账号-科目映射的 CRUD 业务编排。"""
from __future__ import annotations

from finance_agent_backend.account_registry import AccountRegistry
from finance_agent_backend.models import AccountEntry
from finance_agent_backend.paths import get_db_path
from finance_agent_backend.repo.account_mapping_repo import AccountMappingRepository


class AccountRegistryService:
    """封装 AccountRegistry + AccountMappingRepository 的 CRUD 操作。"""

    def __init__(self, db_path: str | None = None):
        from finance_agent_backend import db as _db

        self._db_path = db_path or get_db_path()
        self._conn = _db.get_db(db_path=db_path)
        _db.init_db(self._conn)
        self._repo = AccountMappingRepository(self._conn)

    def _get_registry(self, with_subject_codes: bool = False) -> AccountRegistry:
        """构造 AccountRegistry 实例。"""
        subject_codes = None
        if with_subject_codes:
            from finance_agent_backend.services.subject_service import SubjectService
            subject_codes = SubjectService().get_subject_codes()
        return AccountRegistry(self._repo, subject_codes=subject_codes)

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
        registry = self._get_registry()
        return {
            "success": True,
            "accounts": [self._serialize(e) for e in registry.list_all()],
        }

    def match(self, account_number: str) -> dict:
        registry = self._get_registry()
        entry = registry.match_by_account(account_number)
        return {
            "success": True,
            "entry": self._serialize(entry) if entry else None,
        }

    def add(self, entry: AccountEntry) -> dict:
        registry = self._get_registry(with_subject_codes=True)
        saved = registry.add(entry)
        self._conn.commit()
        return {
            "success": True,
            "id": saved.id,
            "entry": self._serialize(saved),
        }

    def update(self, entry: AccountEntry) -> dict:
        registry = self._get_registry(with_subject_codes=True)
        saved = registry.update(entry)
        self._conn.commit()
        return {"success": True, "entry": self._serialize(saved)}

    def delete(self, entry_id: str) -> dict:
        registry = self._get_registry()
        registry.delete(entry_id)
        self._conn.commit()
        return {"success": True}
