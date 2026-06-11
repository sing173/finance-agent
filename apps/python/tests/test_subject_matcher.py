"""Tests for subject_matcher.py — L1 JSON 规则匹配引擎 (Issue #32).

Tests verify behavior through public interface: match() + RuleMatcher + HistoryMatcher + SubjectMatcher.
"""
import json
import sys
import os
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from finance_agent_backend.subject_matcher import match, MatchResult, RuleMatcher, HistoryMatcher, SubjectMatcher


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
def rules_file(tmp_path):
    """临时规则 JSON 文件（pytest 自动清理）。"""
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(MINIMAL_RULES, ensure_ascii=False), encoding='utf-8')
    return str(path)


@pytest.fixture
def tmp_db(tmp_path):
    """临时 WAL 模式 SQLite 数据库（pytest 自动清理）。"""
    path = str(tmp_path / "test.db")
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    from finance_agent_backend.db import init_db
    init_db(conn)
    conn.commit()
    conn.close()
    return path


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


# ── RuleMatcher 独立测试（L1 策略）──────────────────────────────


class TestRuleMatcher:
    """RuleMatcher 独立单元测试 — 不涉及 L2/L3。"""

    def test_match_hit(self):
        m = RuleMatcher(MINIMAL_RULES)
        r = m.match("支付物业管理费", "expense", "启胜物业")
        assert r.subject_code == "5060203"
        assert r.source == "rule"
        assert r.rule_id == "rule_001"

    def test_match_miss(self):
        m = RuleMatcher(MINIMAL_RULES)
        r = m.match("购买办公设备", "expense", "")
        assert r.source == "unmatched"
        assert r.subject_code == ""

    def test_match_counterparty_filter(self):
        m = RuleMatcher(MINIMAL_RULES)
        # 关键字命中但 counterparty 不匹配 → 跳过
        r = m.match("支付物业管理费", "expense", "万科物业")
        assert r.rule_id == "rule_004"  # 无 counterparty_pattern 的兜底规则命中

    def test_match_from_file(self, rules_file):
        """从文件路径加载规则。"""
        m = RuleMatcher(rules_file)
        r = m.match("支付物业管理费", "expense", "启胜物业")
        assert r.subject_code == "5060203"

    def test_match_default_config_loads(self):
        """无参调用加载内置配置。"""
        m = RuleMatcher()
        r = m.match("支付物业管理费", "expense", "启胜物业")
        assert r.source == "rule"

    def test_match_priority_order(self):
        """短关键字被长关键字覆盖（priority 1 < 4）。"""
        m = RuleMatcher(MINIMAL_RULES)
        r = m.match("支付物业管理费", "expense", "启胜物业")
        assert r.rule_id == "rule_001"  # priority 1，先命中

    def test_match_direction_isolation(self):
        """income 规则不应匹配 expense 摘要。"""
        m = RuleMatcher(MINIMAL_RULES)
        r = m.match("客户回款", "income", "")
        assert r.subject_code == "10122"
        # 同摘要在 expense 方向不应命中 income 规则
        r2 = m.match("客户回款", "expense", "")
        assert r2.source == "unmatched"


class TestHistoryMatcher:
    """HistoryMatcher 独立单元测试（L2 策略）。"""

    def test_match_hit(self, tmp_db):
        """有历史数据时返回匹配。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo
        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("支付AWS云主机托管服务费", "expense", "9990001",
                    "管理费用_办公费", "阿里云计算")
        m = HistoryMatcher(repo)
        r = m.match("支付AWS云主机托管服务费", "expense")
        assert r is not None
        assert r.subject_code == "9990001"

    def test_match_miss(self, tmp_db):
        """无历史数据时返回 None。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo
        repo = SubjectHistoryRepo(tmp_db)
        m = HistoryMatcher(repo)
        r = m.match("完全不存在的摘要", "expense")
        assert r is None

    def test_match_none_repo(self):
        """repo=None 时安全返回 None。"""
        m = HistoryMatcher(None)
        r = m.match("任意摘要", "expense")
        assert r is None

    def test_match_direction_filter(self, tmp_db):
        """不同方向不交叉匹配。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo
        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("收到货款", "income", "10122", "应收账款", "")
        m = HistoryMatcher(repo)
        # income 方向命中
        r = m.match("收到货款", "income")
        assert r is not None
        # expense 方向不命中
        r2 = m.match("收到货款", "expense")
        assert r2 is None


class TestSubjectMatcher:
    """SubjectMatcher 编排层测试 — L1→L2→L3 串联。"""

    def test_l1_hit_skips_l2(self, tmp_db):
        """L1 命中时 L2 不被调用。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo
        repo = SubjectHistoryRepo(tmp_db)
        # 插入一条 L2 会误匹配的数据
        repo.insert("支付物业管理费", "expense", "9999999",
                    "错误科目", "")
        m = SubjectMatcher(rule_matcher=RuleMatcher(MINIMAL_RULES), history_matcher=HistoryMatcher(repo))
        r = m.match("支付物业管理费", "expense", "启胜物业")
        # L1 rule_001 命中，不应走 L2
        assert r.source == "rule"
        assert r.subject_code == "5060203"
        assert r.rule_id == "rule_001"

    def test_l1_miss_l2_hit(self, tmp_db):
        """L1 未命中时降级到 L2。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo
        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("支付AWS云主机托管服务费", "expense", "5060201",
                    "管理费用_办公费", "阿里云计算")
        m = SubjectMatcher(history_matcher=HistoryMatcher(repo))
        r = m.match("支付AWS云主机托管服务费", "expense", "阿里云计算")
        assert r.source == "history"
        assert r.subject_code == "5060201"

    def test_both_miss_returns_unmatched(self):
        """L1+L2 都未命中 → unmatched。"""
        m = SubjectMatcher()
        r = m.match("XYZ完全不存在的摘要", "expense")
        assert r.source == "unmatched"
        assert r.subject_code == ""

    def test_swap_rule_matcher(self):
        """可替换 RuleMatcher — 传入自定义规则。"""
        custom_rules = {
            "version": 1,
            "expense": {
                "rules": [
                    {"id": "custom", "priority": 1,
                     "match": {"keywords": ["自定义"]},
                     "subject_code": "99999", "subject_name": "自定义科目"}
                ]
            },
            "income": {"rules": []}
        }
        m = SubjectMatcher(rule_matcher=RuleMatcher(custom_rules))
        r = m.match("支付自定义费用", "expense")
        assert r.subject_code == "99999"
        assert r.source == "rule"

    def test_no_history_matcher_falls_through(self):
        """无 HistoryMatcher 时 L1 miss → 直接 L3 unmatched。"""
        m = SubjectMatcher(rule_matcher=RuleMatcher(MINIMAL_RULES))
        r = m.match("支付AWS云主机托管服务费", "expense", "阿里云计算")
        assert r.source == "unmatched"