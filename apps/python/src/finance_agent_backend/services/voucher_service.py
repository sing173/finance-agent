"""VoucherService — 凭证全生命周期的业务编排。

preview → save_draft → load_draft → list_drafts → delete_draft → export
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from finance_agent_backend.models import PipelineEntry
from finance_agent_backend.repo import (
    ExportLog,
    ExportLogRepository,
    VoucherDraftRepository,
)
from finance_agent_backend.repo.account_mapping_repo import AccountMappingRepository
from finance_agent_backend.account_registry import AccountRegistry


class VoucherService:
    """凭证 Service — 自 wire conn / repo / composer 依赖。"""

    def __init__(self, db_path: str | None = None):
        from finance_agent_backend import db as _db

        # 让 db.get_db() 解析路径并创建连接
        self._conn = _db.get_db(db_path=db_path)
        # 从 db 模块获取实际使用的数据库路径
        self._db_path = _db._db_path
        _db.init_db(self._conn)
        self._draft_repo = VoucherDraftRepository(self._conn)
        account_repo = AccountMappingRepository(self._conn)
        self._account_registry = AccountRegistry(account_repo)

    def preview(self, transactions: list[dict], subject_mapping: dict | None) -> dict:
        """交易列表 → 凭证预览（含科目匹配 + 同类合并）。"""
        from finance_agent_backend.models import Transaction
        from finance_agent_backend.repo.subject_history_repo import SubjectHistoryRepo
        from finance_agent_backend.voucher_composer import VoucherComposer

        if not transactions:
            return {"success": False, "error": "缺少 transactions 参数"}

        txn_objects = [Transaction.from_dict(t) for t in transactions]
        history_repo = SubjectHistoryRepo(self._db_path)
        composer = VoucherComposer(repo=history_repo)
        vouchers = composer.compose(txn_objects, subject_mapping, self._account_registry)

        for v in vouchers:
            v["entries"] = [e.asdict() for e in v["entries"]]

        warnings = []
        for v in vouchers:
            unmatched = [
                e for e in v["entries"]
                if e.get("match_source") == "unmatched" and e.get("direction") != "bank"
            ]
            if unmatched:
                warnings.append(f"凭证#{v['voucher_no']}: {len(unmatched)} 条分录科目未匹配")

        return {"success": True, "vouchers": vouchers, "warnings": warnings}

    def save_draft(self, name: str, period: str, entries: list[dict]) -> dict:
        """保存凭证草稿到 SQLite。"""
        if not entries:
            return {"success": False, "error": "缺少 entries 参数"}

        draft_id = self._draft_repo.create(name, period)
        pipeline_entries = [PipelineEntry.from_dict(e) for e in entries]
        self._draft_repo.insert_entries(draft_id, pipeline_entries)
        self._conn.commit()
        return {"success": True, "draft_id": draft_id}

    def load_draft(self, draft_id: str) -> dict:
        """加载凭证草稿。"""
        if not draft_id:
            return {"success": False, "error": "缺少 draft_id 参数"}

        draft = self._draft_repo.get(draft_id)
        if not draft:
            return {"success": False, "error": f"草稿 {draft_id} 不存在"}

        entries = self._draft_repo.get_entries(draft_id)
        return {
            "success": True,
            "draft": {
                "id": draft.id,
                "name": draft.name,
                "period": draft.period,
                "status": draft.status,
                "created_at": draft.created_at,
                "updated_at": draft.updated_at,
                "entries": [e.asdict() for e in entries],
            },
        }

    def list_drafts(self) -> dict:
        """列出所有草稿。"""
        return {"success": True, "drafts": self._draft_repo.list_all()}

    def delete_draft(self, draft_id: str) -> dict:
        """删除草稿（CASCADE 删除关联分录）。"""
        if not draft_id:
            return {"success": False, "error": "缺少 draft_id 参数"}

        self._draft_repo.delete(draft_id)
        self._conn.commit()
        return {"success": True}

    def export(
        self,
        draft_id: str,
        output_path: str = "voucher.xlsx",
        period: str = "",
        source_files: list | None = None,
    ) -> dict:
        """确认导出：生成 Excel + 写入审计日志 + 写入历史库。"""
        from finance_agent_backend.repo.subject_history_repo import SubjectHistoryRepo
        from finance_agent_backend.tools import excel_builder

        if not draft_id:
            return {"success": False, "error": "缺少 draft_id 参数"}

        source_files = source_files or []
        entries = self._draft_repo.get_entries(draft_id)
        if not entries:
            return {"success": False, "error": "草稿无分录数据"}

        entry_dicts = [e.asdict() for e in entries]
        txns_count = sum(1 for e in entries if e.direction != "bank")
        voucher_count = len({e.voucher_no for e in entries})

        builder = excel_builder.ExcelBuilder()
        builder.build_voucher_from_entries(
            entries=entry_dicts, output_path=output_path, period=period,
        )

        sources: dict[str, int] = {}
        for e in entries:
            src = e.match_source or "unmatched"
            sources[src] = sources.get(src, 0) + 1

        now = datetime.now(timezone.utc).isoformat()
        export_repo = ExportLogRepository(self._conn)
        export_repo.insert(ExportLog(
            exported_at=now,
            period=period,
            file_path=output_path,
            voucher_count=voucher_count,
            entry_count=len(entries),
            transaction_count=txns_count,
            source_files=json.dumps(source_files),
            match_stats=json.dumps(sources),
            draft_id=draft_id,
        ))

        history_repo = SubjectHistoryRepo(self._db_path)
        for e in entries:
            if e.is_manual:
                history_repo.insert(
                    summary=e.original_summary or e.summary,
                    direction=e.direction,
                    subject_code=e.subject_code,
                    subject_name=e.subject_name or "",
                    counterparty=e.counterparty or "",
                    voucher_id=draft_id,
                    conn=self._conn,
                )

        self._draft_repo.mark_exported(draft_id)
        self._conn.commit()

        return {
            "success": True,
            "file_path": output_path,
            "voucher_count": voucher_count,
            "entry_count": len(entries),
            "transaction_count": txns_count,
        }
