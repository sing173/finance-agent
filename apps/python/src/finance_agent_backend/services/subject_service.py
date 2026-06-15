"""SubjectService — 科目表加载 + 导入的业务编排。"""
from __future__ import annotations

import json
import os

from finance_agent_backend.paths import get_config_path
from finance_agent_backend.subject_matcher import get_subjects, invalidate_subjects


class SubjectService:
    """封装 subjects.json 的查询和导入。"""

    def get_info(self) -> dict:
        """查询科目表信息（返回完整列表供 UI 使用）。"""
        subjects_path = get_config_path('subjects.json')
        if not os.path.exists(subjects_path):
            return {"success": True, "count": 0, "loaded": False, "subjects": []}

        subjects_data = get_subjects()
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

    def import_from_xlsx(self, xlsx_path: str) -> dict:
        """从科目 xlsx 导入并保存为 subjects.json。"""
        from finance_agent_backend.tools import subject_loader

        loader = subject_loader.SubjectLoader()
        subjects = loader.load(xlsx_path)

        data = {}
        for code, subj in subjects.items():
            data[code] = {
                'code': subj.code,
                'name': subj.name,
                'category': subj.category,
                'direction': subj.direction,
                'aux_category': subj.aux_category,
                'is_cash': subj.is_cash,
                'enabled': subj.enabled,
                'full_name': subj.full_name,
            }

        subjects_json_path = get_config_path('subjects.json')
        with open(subjects_json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        invalidate_subjects()

        return {
            "success": True,
            "count": len(subjects),
            "path": subjects_json_path,
        }

    def get_subject_codes(self) -> set:
        """获取科目代码集合（用于校验）。"""
        return set(get_subjects().keys())
