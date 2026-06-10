"""Tracer bullet: 验证 L2 HistoryMatcher 返回的 MatchResult 会被 SubjectMatcher 补全 aux_category（Issue #46 第 3 点补漏）。"""
import sys
import os
import tempfile
import atexit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from finance_agent_backend.subject_matcher import SubjectMatcher, RuleMatcher, MatchResult


class FakeHistoryMatcher:
    """模拟 L2 返回不含 aux_category 的 MatchResult。"""
    def match(self, summary, direction):
        return MatchResult(
            subject_code="5060211",
            subject_name="管理费用_福利费",
            source="history",
            rule_id="",
            # aux_category 为空，模拟 L2 原始行为
            aux_category="",
            aux_category_name="",
        )


def test_l2_aux_category_filled_by_subject_matcher():
    """SubjectMatcher L2 返回路径应补全 aux_category。"""
    rule_matcher = RuleMatcher()
    fake_l2 = FakeHistoryMatcher()
    matcher = SubjectMatcher(rule_matcher=rule_matcher, history_matcher=fake_l2)

    result = matcher.match("任意摘要不含L1关键字", "expense")
    assert result.source == "history", f"期望 history，实际 {result.source}"
    assert result.subject_code == "5060211"
    # L2 路径的 SubjectMatcher 应补全 aux_category
    assert result.aux_category == "04", (
        f"L2 路径 aux_category 应为 '04'，实际 '{result.aux_category}'"
    )
    assert result.aux_category_name == "公共部门", (
        f"L2 路径 aux_category_name 应为 '公共部门'，实际 '{result.aux_category_name}'"
    )


def test_l2_preserves_existing_aux_category():
    """如果 L2 本身已有 aux_category，不应被覆盖。"""
    class FakeHistoryWithAux:
        def match(self, summary, direction):
            return MatchResult(
                subject_code="5060203",
                subject_name="管理费用_物业管理费",
                source="history",
                aux_category="99",
                aux_category_name="自定义",
            )

    matcher = SubjectMatcher(
        rule_matcher=RuleMatcher(),
        history_matcher=FakeHistoryWithAux(),
    )
    result = matcher.match("任意摘要", "expense")
    assert result.aux_category == "99", "L2 已有 aux_category 不应被覆盖"
    assert result.aux_category_name == "自定义"
