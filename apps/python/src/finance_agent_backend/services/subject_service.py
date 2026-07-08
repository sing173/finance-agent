"""SubjectService — 科目查询、导入、新增（DB 权威数据源）。"""
from __future__ import annotations

from datetime import datetime, timezone

from finance_agent_backend.subject_matcher import get_subjects, invalidate_subjects


class SubjectService:
    """封装科目数据的查询、导入和新增（纯 DB）。"""

    def get_info(self) -> dict:
        """查询科目表信息（返回完整列表供 UI 使用）。"""
        return self._load_from_db()

    def _load_from_db(self) -> dict:
        """直接从 DB subjects 表读取。"""
        try:
            from finance_agent_backend.db import get_db
            conn = get_db()
            rows = conn.execute(
                "SELECT code, name, category, direction, aux_category, aux_category_name, is_cash, enabled, full_name FROM subjects"
            ).fetchall()
            subjects = [
                {
                    "code": r['code'],
                    "name": r['name'],
                    "category": r['category'],
                    "direction": r['direction'],
                    "aux_category": r['aux_category'],
                    "aux_category_name": r['aux_category_name'],
                    "is_cash": bool(r['is_cash']),
                    "enabled": bool(r['enabled']),
                    "full_name": r['full_name'],
                }
                for r in rows
            ]
            loaded = bool(rows)
            return {"success": True, "count": len(subjects), "loaded": loaded, "subjects": subjects}
        except Exception:
            return {"success": True, "count": 0, "loaded": False, "subjects": []}

    def import_from_xlsx(self, xlsx_path: str) -> dict:
        """从科目 xlsx 导入，写入 DB（upsert）。"""
        from finance_agent_backend.tools import subject_loader

        loader = subject_loader.SubjectLoader()
        subjects = loader.load(xlsx_path)

        now = datetime.now(timezone.utc).isoformat()

        try:
            from finance_agent_backend.db import get_db
            conn = get_db()
            for code, subj in subjects.items():
                conn.execute(
                    """INSERT INTO subjects
                       (code, name, full_name, category, direction,
                        aux_category, aux_category_name, is_cash, enabled, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(code) DO UPDATE SET
                           name        = excluded.name,
                           full_name   = excluded.full_name,
                           category    = excluded.category,
                           direction   = excluded.direction,
                           aux_category = excluded.aux_category,
                           aux_category_name = excluded.aux_category_name,
                           is_cash     = excluded.is_cash,
                           enabled     = excluded.enabled,
                           updated_at  = excluded.updated_at""",
                    (
                        subj.code,
                        subj.name,
                        subj.full_name,
                        subj.category,
                        subj.direction,
                        subj.aux_category or '',
                        subj.aux_category_name or '',
                        1 if subj.is_cash else 0,
                        1 if subj.enabled else 0,
                        now,
                    ),
                )
            conn.commit()
        except Exception as e:
            return {"success": False, "error": f"写入 DB 失败: {e}"}

        invalidate_subjects()

        return {
            "success": True,
            "count": len(subjects),
        }

    def add_subject(self, params: dict) -> dict:
        """新增单条科目，写入 DB。"""
        code = params.get("code", "").strip()
        name = params.get("name", "").strip()
        if not code or not name:
            return {"success": False, "error": "code 和 name 均为必填"}

        full_name   = params.get("full_name", name).strip()
        category    = params.get("category", "").strip()
        direction   = params.get("direction", "借")
        is_cash     = 1 if params.get("is_cash") else 0
        enabled     = 1 if params.get("enabled", True) else 0
        aux_category = params.get("aux_category", "").strip()
        aux_category_name = params.get("aux_category_name", "").strip()
        now = datetime.now(timezone.utc).isoformat()

        existing = self.get_subject_codes()
        if code in existing:
            return {"success": False, "error": f"科目代码 '{code}' 已存在"}

        try:
            from finance_agent_backend.db import get_db
            conn = get_db()
            conn.execute(
                """INSERT INTO subjects
                   (code, name, full_name, category, direction,
                    aux_category, aux_category_name, is_cash, enabled, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (code, name, full_name, category, direction,
                 aux_category, aux_category_name, is_cash, enabled, now),
            )
            conn.commit()
        except Exception as e:
            return {"success": False, "error": f"写入 DB 失败: {e}"}

        invalidate_subjects()

        return {
            "success": True,
            "code": code,
            "name": name,
        }

    def get_subject_codes(self) -> set:
        """获取现有科目代码集合（用于校验重复）。"""
        return set(get_subjects().keys())
