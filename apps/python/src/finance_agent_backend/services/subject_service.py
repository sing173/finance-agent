"""SubjectService — 科目查询、导入、新增（DB 权威数据源 + subjects.json 同步）。"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from finance_agent_backend.paths import get_config_path
from finance_agent_backend.subject_matcher import get_subjects, invalidate_subjects


class SubjectService:
    """封装科目数据的查询、导入和新增。"""

    def get_info(self) -> dict:
        """查询科目表信息（返回完整列表供 UI 使用）。"""
        subjects_path = get_config_path('subjects.json')
        if not os.path.exists(subjects_path):
            # JSON 文件不存在时回退读 DB
            return self._load_from_db()

        # get_subjects() 已优先读 DB，此处直接用
        subjects_data = get_subjects()
        if not subjects_data:
            return {"success": True, "count": 0, "loaded": False, "subjects": []}

        subjects = []
        for code, info in subjects_data.items():
            subjects.append({
                "code": code,
                "name": info.get('name', ''),
                "category": info.get('category', ''),
                "direction": info.get('direction', '借'),
                "is_cash": info.get('is_cash', False),
                "enabled": info.get('enabled', True),
                "full_name": info.get('full_name', info.get('name', '')),
            })
        return {"success": True, "count": len(subjects), "loaded": True, "subjects": subjects}

    def _load_from_db(self) -> dict:
        """直接从 DB subjects 表读取（JSON 文件不存在时兜底）。"""
        try:
            from finance_agent_backend.db import get_db
            conn = get_db()
            rows = conn.execute(
                "SELECT code, name, category, direction, is_cash, enabled, full_name FROM subjects"
            ).fetchall()
            subjects = [
                {
                    "code": r['code'],
                    "name": r['name'],
                    "category": r['category'],
                    "direction": r['direction'],
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

    def _write_subjects_json(self, data: dict) -> None:
        """将完整科目字典原子写入 subjects.json，保持与 DB 一致。"""
        subjects_json_path = get_config_path('subjects.json')
        os.makedirs(os.path.dirname(subjects_json_path), exist_ok=True)
        tmp_path = subjects_json_path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, subjects_json_path)

    def import_from_xlsx(self, xlsx_path: str) -> dict:
        """从科目 xlsx 导入，写入 DB（upsert）并同步 subjects.json。"""
        from finance_agent_backend.tools import subject_loader

        loader = subject_loader.SubjectLoader()
        subjects = loader.load(xlsx_path)

        now = datetime.now(timezone.utc).isoformat()

        # 写入 DB（upsert，code 唯一）
        try:
            from finance_agent_backend.db import get_db
            conn = get_db()
            for code, subj in subjects.items():
                conn.execute(
                    """INSERT INTO subjects
                       (code, name, full_name, category, direction,
                        aux_category, is_cash, enabled, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(code) DO UPDATE SET
                           name        = excluded.name,
                           full_name   = excluded.full_name,
                           category    = excluded.category,
                           direction   = excluded.direction,
                           aux_category = excluded.aux_category,
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
                        1 if subj.is_cash else 0,
                        1 if subj.enabled else 0,
                        now,
                    ),
                )
            conn.commit()
        except Exception as e:
            return {"success": False, "error": f"写入 DB 失败: {e}"}

        # 同步 subjects.json
        data = {}
        for code, subj in subjects.items():
            data[code] = {
                'code':           subj.code,
                'name':           subj.name,
                'full_name':      subj.full_name,
                'category':       subj.category,
                'direction':      subj.direction,
                'aux_category':   subj.aux_category,
                'is_cash':        subj.is_cash,
                'enabled':        subj.enabled,
            }
        try:
            self._write_subjects_json(data)
        except Exception as e:
            return {"success": False, "error": f"写入 subjects.json 失败: {e}"}

        invalidate_subjects()

        return {
            "success": True,
            "count": len(subjects),
            "path": get_config_path('subjects.json'),
        }

    def add_subject(self, params: dict) -> dict:
        """新增单条科目，写入 DB 并同步 subjects.json。"""
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
        now = datetime.now(timezone.utc).isoformat()

        # 校验唯一性
        existing = self.get_subject_codes()
        if code in existing:
            return {"success": False, "error": f"科目代码 '{code}' 已存在"}

        # 写入 DB
        try:
            from finance_agent_backend.db import get_db
            conn = get_db()
            conn.execute(
                """INSERT INTO subjects
                   (code, name, full_name, category, direction,
                    aux_category, is_cash, enabled, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (code, name, full_name, category, direction,
                 aux_category, is_cash, enabled, now),
            )
            conn.commit()
        except Exception as e:
            return {"success": False, "error": f"写入 DB 失败: {e}"}

        # 同步 subjects.json（全量刷新）
        try:
            all_data = get_subjects()
            all_data[code] = {
                'code':           code,
                'name':           name,
                'full_name':      full_name,
                'category':       category,
                'direction':      direction,
                'aux_category':   aux_category,
                'is_cash':        bool(is_cash),
                'enabled':        bool(enabled),
            }
            self._write_subjects_json(all_data)
        except Exception as e:
            return {"success": False, "error": f"写入 subjects.json 失败: {e}"}

        invalidate_subjects()

        return {
            "success": True,
            "code": code,
            "name": name,
        }

    def get_subject_codes(self) -> set:
        """获取现有科目代码集合（用于校验重复）。"""
        return set(get_subjects().keys())
