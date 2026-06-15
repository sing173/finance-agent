"""Tests for RuleMatcher._validate() — 规则加载时校验。"""
import logging

import pytest

from finance_agent_backend.subject_matcher import RuleMatcher


class TestValidate:
    """_validate() 静态方法 — 校验规则配置。"""

    def test_valid_rules_no_warnings(self, caplog):
        """合法规则不产生 warning。"""
        rules = {
            "expense": {"rules": [
                {"id": "r1", "priority": 1, "match": {"keywords": ["测试"]},
                 "subject_code": "50602", "subject_name": "管理费用"},
            ]},
        }
        with caplog.at_level(logging.WARNING, logger="bridge"):
            RuleMatcher._validate(rules, {"50602": {"name": "管理费用"}})
        assert len(caplog.records) == 0

    def test_missing_id(self, caplog):
        """规则缺少 id → warning。"""
        rules = {
            "expense": {"rules": [
                {"priority": 1, "match": {"keywords": ["测试"]}, "subject_code": "50602"},
            ]},
        }
        with caplog.at_level(logging.WARNING, logger="bridge"):
            RuleMatcher._validate(rules, {})
        assert any("缺少 id" in r.message for r in caplog.records)

    def test_duplicate_id(self, caplog):
        """重复 id → warning。"""
        rules = {
            "expense": {"rules": [
                {"id": "dup", "priority": 1, "match": {"keywords": ["a"]}, "subject_code": "100"},
                {"id": "dup", "priority": 2, "match": {"keywords": ["b"]}, "subject_code": "200"},
            ]},
        }
        with caplog.at_level(logging.WARNING, logger="bridge"):
            RuleMatcher._validate(rules, {})
        assert any("重复" in r.message for r in caplog.records)

    def test_missing_keywords(self, caplog):
        """match.keywords 为空 → warning。"""
        rules = {
            "expense": {"rules": [
                {"id": "r1", "priority": 1, "match": {}, "subject_code": "50602"},
            ]},
        }
        with caplog.at_level(logging.WARNING, logger="bridge"):
            RuleMatcher._validate(rules, {})
        assert any("keywords" in r.message for r in caplog.records)

    def test_missing_subject_code(self, caplog):
        """缺少 subject_code → warning。"""
        rules = {
            "expense": {"rules": [
                {"id": "r1", "priority": 1, "match": {"keywords": ["测试"]}},
            ]},
        }
        with caplog.at_level(logging.WARNING, logger="bridge"):
            RuleMatcher._validate(rules, {})
        assert any("subject_code" in r.message for r in caplog.records)

    def test_subject_code_not_in_subjects(self, caplog):
        """subject_code 不在 subjects.json 中 → warning。"""
        rules = {
            "expense": {"rules": [
                {"id": "r1", "priority": 1, "match": {"keywords": ["测试"]},
                 "subject_code": "99999", "subject_name": "不存在的科目"},
            ]},
        }
        subjects = {"50602": {"name": "管理费用"}}
        with caplog.at_level(logging.WARNING, logger="bridge"):
            RuleMatcher._validate(rules, subjects)
        assert any("不在科目表" in r.message for r in caplog.records)

    def test_empty_subjects_skips_validation(self, caplog):
        """subjects 为空时跳过科目校验。"""
        rules = {
            "expense": {"rules": [
                {"id": "r1", "priority": 1, "match": {"keywords": ["测试"]},
                 "subject_code": "99999", "subject_name": "任意"},
            ]},
        }
        with caplog.at_level(logging.WARNING, logger="bridge"):
            RuleMatcher._validate(rules, {})
        assert not any("不在科目表" in r.message for r in caplog.records)

    def test_income_rules_also_validated(self, caplog):
        """income 方向的规则同样校验。"""
        rules = {
            "income": {"rules": [
                {"priority": 1, "match": {"keywords": ["收款"]}, "subject_code": "10122"},
            ]},
        }
        with caplog.at_level(logging.WARNING, logger="bridge"):
            RuleMatcher._validate(rules, {})
        assert any("缺少 id" in r.message for r in caplog.records)

    def test_validate_called_during_init(self, caplog):
        """RuleMatcher 构造时自动调用 _validate。"""
        rules = {
            "expense": {"rules": [
                {"id": "dup", "priority": 1, "match": {"keywords": ["a"]}, "subject_code": "100"},
                {"id": "dup", "priority": 2, "match": {"keywords": ["b"]}, "subject_code": "200"},
            ]},
        }
        with caplog.at_level(logging.WARNING, logger="bridge"):
            RuleMatcher(rules)
        assert any("重复" in r.message for r in caplog.records)
