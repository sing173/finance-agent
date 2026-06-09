"""Tracer bullet: 验证 RuleMatcher 的 exclude_keywords 支持（Issue #46 第 4 点）。

RED 阶段：测试应 FAIL，因为 _matches() 尚未实现 exclude_keywords。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from finance_agent_backend.subject_matcher import RuleMatcher


def test_exclude_keywords_blocks_match():
    """摘要含 exclude 关键词时，规则不命中。"""
    matcher = RuleMatcher()
    # rule_e028: keywords=["押金","保证金"], exclude_keywords=["退","收到"]
    # "收到押金" 含"收到" → 应被排除
    result = matcher.match("收到押金", "expense")
    assert result.source == "unmatched", (
        f"期望 unmatched（被 exclude_keywords 排除），实际 source={result.source}, "
        f"code={result.subject_code}, rule_id={result.rule_id}"
    )


def test_exclude_keywords_allows_normal():
    """摘要不含 exclude 关键词时，规则正常命中。"""
    matcher = RuleMatcher()
    # "支付押金" 不含"退"或"收到" → 应命中 rule_e028
    result = matcher.match("支付押金", "expense")
    assert result.source == "rule"
    assert result.subject_code == "1022104"
    assert result.rule_id == "rule_e028"
