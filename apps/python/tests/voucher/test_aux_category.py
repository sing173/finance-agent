"""Tracer bullet: 验证 MatchResult 透传 aux_category（Issue #46 第 3 点）。

RED 阶段：测试应 FAIL，因为 MatchResult 尚未有 aux_category 字段。
"""
import sys
import os


from finance_agent_backend.subject_matcher import RuleMatcher


def test_aux_category_present_in_match_result(seeded_subjects_db):
    """匹配到 50602xx 科目时，aux_category 应为 "04"，aux_category_name 来自 subjects 表。"""
    matcher = RuleMatcher()
    result = matcher.match("报销", "expense")
    assert result.source == "rule"
    assert hasattr(result, 'aux_category'), "MatchResult 缺少 aux_category 字段"
    assert result.aux_category == "04", (
        f"期望 aux_category='04'，实际 '{result.aux_category}'"
    )
    assert result.aux_category_name == "公共部门", (
        f"期望 aux_category_name='公共部门'，实际 '{result.aux_category_name}'"
    )


def test_aux_category_empty_for_non_50602(seeded_subjects_db):
    """匹配到非 50602xx 科目（如 5030102 营业外收入）时，aux_category 应为空。"""
    matcher = RuleMatcher()
    result = matcher.match("收到政府补贴", "income")
    assert result.source == "rule"
    assert result.aux_category == ""
    assert result.aux_category_name == ""
