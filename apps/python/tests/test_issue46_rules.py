"""Issue #46: 新增科目映射规则 tracer bullet 测试。"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from finance_agent_backend.subject_matcher import RuleMatcher, MatchResult


def test_baoxiao_expense_match():
    """摘要含"报销"、direction=expense → 管理费用(50602)"""
    matcher = RuleMatcher()
    result = matcher.match("报销", "expense")
    assert isinstance(result, MatchResult)
    assert result.subject_code == "50602", f"期望 50602，实际 {result.subject_code}"
    assert result.subject_name == "管理费用", f"期望 管理费用，实际 {result.subject_name}"
    assert result.source == "rule"
    assert result.rule_id == "rule_e032"


def test_dianxin_expense_match():
    """摘要含"电信"、direction=expense → 管理费用_电讯费(5060216)"""
    matcher = RuleMatcher()
    result = matcher.match("电信费", "expense")
    assert isinstance(result, MatchResult)
    assert result.subject_code == "5060216", f"期望 5060216，实际 {result.subject_code}"
    assert result.subject_name == "管理费用_电讯费", f"期望 管理费用_电讯费，实际 {result.subject_name}"
    assert result.source == "rule"
    assert result.rule_id == "rule_e033"


def test_tuanxian_expense_match():
    """摘要含"团险"、direction=expense → 管理费用_福利费(5060211)"""
    matcher = RuleMatcher()
    result = matcher.match("团险保费", "expense")
    assert isinstance(result, MatchResult)
    assert result.subject_code == "5060211", f"期望 5060211，实际 {result.subject_code}"
    assert result.subject_name == "管理费用_福利费", f"期望 管理费用_福利费，实际 {result.subject_name}"
    assert result.source == "rule"
    assert result.rule_id == "rule_e034"


def test_zhengwei_expense_match():
    """摘要含"郑炜"、direction=expense → 管理费用_房租(5060202)"""
    matcher = RuleMatcher()
    result = matcher.match("支付郑炜", "expense")
    assert isinstance(result, MatchResult)
    assert result.subject_code == "5060202", f"期望 5060202，实际 {result.subject_code}"
    assert result.subject_name == "管理费用_房租", f"期望 管理费用_房租，实际 {result.subject_name}"
    assert result.source == "rule"
    assert result.rule_id == "rule_e035"


def test_baozhengjin_expense_match():
    """摘要含"保证金"、direction=expense → 其他应收款_押金(1022104)"""
    matcher = RuleMatcher()
    result = matcher.match("支付保证金", "expense")
    assert isinstance(result, MatchResult)
    assert result.subject_code == "1022104", f"期望 1022104，实际 {result.subject_code}"
    assert result.subject_name == "其他应收款_押金", f"期望 其他应收款_押金，实际 {result.subject_name}"
    assert result.source == "rule"
    assert result.rule_id == "rule_e028"


def test_tuiyaojin_income_match():
    """摘要含"退押金"、direction=income → 其他应收款_押金(1022104)"""
    matcher = RuleMatcher()
    result = matcher.match("收到退押金", "income")
    assert isinstance(result, MatchResult)
    assert result.subject_code == "1022104", f"期望 1022104，实际 {result.subject_code}"
    assert result.subject_name == "其他应收款_押金", f"期望 其他应收款_押金，实际 {result.subject_name}"
    assert result.source == "rule"
    assert result.rule_id == "rule_i007"


def test_tuibaozhengjin_income_match():
    """摘要含"收到退保证金"、direction=income → 其他应收款_押金(1022104)"""
    matcher = RuleMatcher()
    result = matcher.match("收到退保证金", "income")
    assert isinstance(result, MatchResult)
    assert result.subject_code == "1022104", f"期望 1022104，实际 {result.subject_code}"
    assert result.subject_name == "其他应收款_押金", f"期望 其他应收款_押金，实际 {result.subject_name}"
    assert result.source == "rule"
    assert result.rule_id == "rule_i007"


def test_shouxufei_income_match():
    """摘要含"手续费"、direction=income → 其他应收款_手续费(1022120)"""
    matcher = RuleMatcher()
    result = matcher.match("退回手续费", "income")
    assert isinstance(result, MatchResult)
    assert result.subject_code == "1022120", f"期望 1022120，实际 {result.subject_code}"
    assert result.subject_name == "其他应收款_手续费", f"期望 其他应收款_手续费，实际 {result.subject_name}"
    assert result.source == "rule"
    assert result.rule_id == "rule_i008"


def test_dailixi_income_match():
    """摘要含"小企业短期普通贷款利息收入"、direction=income → 其他应收款_其他(1022103)"""
    matcher = RuleMatcher()
    result = matcher.match("小企业短期普通贷款利息收入", "income")
    assert isinstance(result, MatchResult)
    assert result.subject_code == "1022103", f"期望 1022103，实际 {result.subject_code}"
    assert result.subject_name == "其他应收款_其他", f"期望 其他应收款_其他，实际 {result.subject_name}"
    assert result.source == "rule"
    assert result.rule_id == "rule_i009"


# ── 回归测试：现有规则不受影响 ───────────────────────────────────


def test_existing_wuye_expense():
    """现有规则：物业费 + counterparty 启胜"""
    matcher = RuleMatcher()
    result = matcher.match("支付物业管理费", "expense", "启胜物业")
    assert result.subject_code == "5060203"
    assert result.subject_name == "管理费用_物业管理费"
    assert result.source == "rule"
    assert result.rule_id == "rule_e001"


def test_existing_shouqian_expense():
    """现有规则：收款(收入方向)"""
    matcher = RuleMatcher()
    result = matcher.match("收到货款", "income")
    assert result.subject_code == "10122"
    assert result.subject_name == "应收账款"
    assert result.source == "rule"
    assert result.rule_id == "rule_i001"


def test_existing_unmatched():
    """不匹配任何规则 → unmatched"""
    matcher = RuleMatcher()
    result = matcher.match("未知交易类型", "expense")
    assert result.source == "unmatched"
    assert result.subject_code == ""
