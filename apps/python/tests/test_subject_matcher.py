"""Tests for subject_matcher.py — L1 JSON 规则匹配引擎 (Issue #32).

Tests verify behavior through public interface: match().
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from finance_agent_backend.subject_matcher import match, MatchResult


# ── 最小测试配置 ──────────────────────────────────────────────

MINIMAL_RULES = {
    "version": 2,
    "expense": {
        "default_subject_code": "",
        "rules": [
            {
                "id": "rule_001",
                "priority": 1,
                "match": {
                    "keywords": ["物业费", "物管费", "物业管理费"],
                    "counterparty_pattern": "启胜"
                },
                "subject_code": "5060203",
                "subject_name": "管理费用_物业管理费"
            },
            {
                "id": "rule_002",
                "priority": 2,
                "match": {
                    "keywords": ["服务费", "技术服务费"],
                    "counterparty_pattern": "科技"
                },
                "subject_code": "403010113",
                "subject_name": "研发支出_技术服务费"
            },
            {
                "id": "rule_003",
                "priority": 3,
                "match": {
                    "keywords": ["手续费", "汇款手续费"]
                },
                "subject_code": "1022120",
                "subject_name": "其他应收款_手续费"
            },
            {
                "id": "rule_004",
                "priority": 4,
                "match": {
                    "keywords": ["物业"]
                },
                "subject_code": "5060299",
                "subject_name": "管理费用_其他物业"
            }
        ]
    },
    "income": {
        "default_subject_code": "",
        "rules": [
            {
                "id": "rule_101",
                "priority": 1,
                "match": {
                    "keywords": ["收款", "回款", "货款"]
                },
                "subject_code": "10122",
                "subject_name": "应收账款"
            }
        ]
    }
}


@pytest.fixture
def rules_file():
    fd, path = tempfile.mkstemp(suffix='.json')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(MINIMAL_RULES, f, ensure_ascii=False)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


# ── 测试 ──────────────────────────────────────────────────────

class TestPureKeywordMatch:
    """纯关键字匹配（无 counterparty_pattern）。"""

    def test_keyword_hit(self):
        result = match("支付汇款手续费", "expense", "", rules=MINIMAL_RULES)
        assert result.subject_code == "1022120"
        assert result.subject_name == "其他应收款_手续费"
        assert result.source == "rule"
        assert result.rule_id == "rule_003"

    def test_keyword_any_hit(self):
        """keywords 列表中任一命中即触发 — 但联合规则 rejected by counterparty。"""
        result = match("银行扣款 服务费用", "expense", "", rules=MINIMAL_RULES)
        # "服务费用" contains "服务费" → rule_002 keyword hit
        # But counterparty_pattern="科技" not in counterparty="" → skip
        # "服务费用" does NOT contain "手续费" "物业" → unmatched
        assert result.source == "unmatched"

    def test_no_match_returns_unmatched(self):
        result = match("购买办公设备", "expense", "", rules=MINIMAL_RULES)
        assert result.source == "unmatched"
        assert result.subject_code == ""


class TestJointRule:
    """联合规则：关键字 + counterparty_pattern。"""

    def test_joint_rule_hit(self):
        result = match("支付物业管理费", "expense", "启胜物业公司", rules=MINIMAL_RULES)
        assert result.subject_code == "5060203"
        assert result.source == "rule"
        assert result.rule_id == "rule_001"

    def test_joint_rule_counterparty_mismatch(self):
        """关键字命中但 counterparty 不匹配 → 跳过。"""
        result = match("支付物业管理费", "expense", "万科物业", rules=MINIMAL_RULES)
        # rule_001 关键字命中但 counterparty 不匹配 → 跳过
        # rule_004 "物业" 命中，无 counterparty → hit
        assert result.subject_code == "5060299"
        assert result.source == "rule"
        assert result.rule_id == "rule_004"

    def test_joint_rule_service_tech(self):
        result = match("技术服务费支付", "expense", "中锦科技", rules=MINIMAL_RULES)
        assert result.subject_code == "403010113"
        assert result.rule_id == "rule_002"


class TestPriority:
    """优先级：priority 数字小 = 高优先级。"""

    def test_long_keyword_over_short(self):
        """"物业管理费" 同时匹配 rule_001(物管费) 和 rule_004(物业)。
        priority 1 < 4 → rule_001 先命中。"""
        result = match("支付物业管理费", "expense", "启胜物业", rules=MINIMAL_RULES)
        assert result.rule_id == "rule_001"
        assert result.subject_code == "5060203"

    def test_short_keyword_when_no_long_match(self):
        """只有短关键字命中时走短关键字规则。"""
        result = match("缴纳物业费", "expense", "万科物业", rules=MINIMAL_RULES)
        # rule_001: "物业费" 命中但 counterparty 无 "启胜" → 跳过
        # rule_004: "物业" 命中，无 counterparty → hit
        assert result.rule_id == "rule_004"


class TestDirection:
    """方向分组：expense 规则不匹配 income 摘要。"""

    def test_income_keyword(self):
        result = match("客户回款", "income", "", rules=MINIMAL_RULES)
        assert result.subject_code == "10122"
        assert result.source == "rule"

    def test_expense_rule_not_applied_to_income(self):
        """收入方向的"收款"不应匹配支出规则。"""
        result = match("收款", "income", "", rules=MINIMAL_RULES)
        assert result.source == "rule"
        assert result.rule_id == "rule_101"


class TestRealConfig:
    """使用真实 subject_mapping.json v2 配置。"""

    def test_real_config_loads(self):
        """默认配置可加载并匹配。"""
        result = match("支付物业管理费", "expense", "启胜物业")
        assert result.source == "rule"
        assert result.subject_code == "5060203"

    def test_real_config_no_match(self):
        result = match("XYZ完全不存在的摘要", "expense")
        assert result.source == "unmatched"

    def test_real_config_service_fee_with_counterparty(self):
        result = match("技术服务费支付", "expense", "中锦科技")
        assert result.source == "rule"
        assert result.subject_code == "403010113"