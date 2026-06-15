"""科目匹配引擎 (Issue #32).

三层架构：
  L1 RuleMatcher   — JSON 规则匹配（priority 排序 + 联合条件）
  L2 HistoryMatcher — TF-IDF 历史库相似度匹配（需 SubjectHistoryRepo）
  L3 兜底           — 返回 unmatched

用法::

    # 简洁模式（向后兼容）
    from finance_agent_backend.subject_matcher import match
    result = match("支付物业管理费", "expense", "启胜物业")

    # 组合模式（可替换策略）
    from finance_agent_backend.subject_matcher import SubjectMatcher, RuleMatcher
    matcher = SubjectMatcher(repo=repo)
    result = matcher.match("支付物业管理费", "expense", "启胜物业")
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class MatchResult:
    """单次匹配结果。"""
    subject_code: str = ''
    subject_name: str = ''
    source: str = 'unmatched'    # 'rule' | 'history' | 'manual' | 'unmatched'
    rule_id: str = ''
    aux_category: str = ''
    aux_category_name: str = ''


# ── subjects.json 模块级缓存 ──────────────────────────────

_subjects_cache: dict | None = None


def get_subjects() -> dict:
    """获取 subjects.json 内容（模块级缓存，首次加载后复用）。"""
    global _subjects_cache
    if _subjects_cache is None:
        try:
            from finance_agent_backend.paths import get_config_path
            path = get_config_path('subjects.json')
            with open(path, 'r', encoding='utf-8') as f:
                _subjects_cache = json.load(f)
        except Exception:
            _subjects_cache = {}
    return _subjects_cache


def invalidate_subjects() -> None:
    """使 subjects 缓存失效（import_subjects 后调用）。"""
    global _subjects_cache
    _subjects_cache = None
    invalidate_rule_matcher()


def invalidate_rule_matcher() -> None:
    """使默认 RuleMatcher 单例失效（subjects/规则变更后调用）。"""
    global _default_rule_matcher
    _default_rule_matcher = None


# ── L1: 规则匹配器 ──────────────────────────────────────────


class RuleMatcher:
    """JSON 规则匹配策略。

    构造函数一次性加载规则，match() 只做查询，无 I/O。
    可替换为任何实现相同接口的对象（如远程规则服务）。
    """

    def __init__(self, rules: dict | str | None = None):
        """初始化规则匹配器。

        参数:
            rules: dict（已加载的规则）、str（文件路径）、或 None（默认内置配置）
        """
        self._rules = self._load(rules)
        self._subjects = self._load_subjects()
        self._validate(self._rules, self._subjects)

    @staticmethod
    def _load(rules: dict | str | None) -> dict:
        if isinstance(rules, dict):
            return rules
        if isinstance(rules, str):
            try:
                with open(rules, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                import logging
                logging.getLogger("bridge").warning("规则文件加载失败: %s", e)
                return {"version": 0}
        # 默认内置配置
        try:
            from finance_agent_backend.paths import get_config_path
            path = get_config_path('subject_mapping.json')
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            import logging
            logging.getLogger("bridge").warning("内置规则文件加载失败: %s", e)
            return {"version": 0}

    @staticmethod
    def _validate(rules_data: dict, subjects: dict) -> None:
        """校验规则配置，log warning 但不阻断加载。"""
        import logging
        log = logging.getLogger("bridge")
        seen_ids: set[str] = set()

        for direction in ('expense', 'income'):
            direction_rules = rules_data.get(direction, {})
            rule_list = direction_rules.get("rules", [])

            for i, rule in enumerate(rule_list):
                rule_id = rule.get("id", f"{direction}[{i}]")

                if not rule.get("id"):
                    log.warning("规则缺少 id: %s[%d]", direction, i)
                elif rule["id"] in seen_ids:
                    log.warning("规则 id 重复: %s", rule["id"])
                else:
                    seen_ids.add(rule_id)

                match_def = rule.get("match", {})
                if not match_def.get("keywords"):
                    log.warning("规则 %s 缺少 match.keywords", rule_id)

                code = rule.get("subject_code", "")
                if not code:
                    log.warning("规则 %s 缺少 subject_code", rule_id)
                elif subjects and code not in subjects:
                    log.warning("规则 %s 的 subject_code '%s' 不在科目表中", rule_id, code)

    @staticmethod
    def _load_subjects() -> dict:
        """加载 subjects.json（委托模块级缓存）。"""
        return get_subjects()

    def get_aux_category(self, subject_code: str) -> tuple[str, str]:
        """从 subjects.json 查找 aux_category 和 aux_category_name。"""
        subj = self._subjects.get(subject_code, {})
        return subj.get('aux_category', ''), subj.get('aux_category_name', '')

    def match(self, summary: str, direction: str, counterparty: str = '') -> MatchResult:
        """按 priority 升序尝试规则，首个命中即停。"""
        direction_rules = self._rules.get(direction, {})
        rules_list = direction_rules.get("rules", [])

        for rule in sorted(rules_list, key=lambda r: r.get("priority", 999)):
            if self._matches(rule, summary, counterparty):
                code = rule.get("subject_code", "")
                aux_cat, aux_cat_name = self.get_aux_category(code)
                return MatchResult(
                    subject_code=code,
                    subject_name=rule.get("subject_name", ""),
                    source="rule",
                    rule_id=rule.get("id", ""),
                    aux_category=aux_cat,
                    aux_category_name=aux_cat_name,
                )
        return MatchResult()

    @staticmethod
    def _matches(rule: dict, summary: str, counterparty: str) -> bool:
        match_def = rule.get("match", {})
        keywords = match_def.get("keywords", [])
        if not any(kw in summary for kw in keywords):
            return False
        # exclude_keywords: 任一命中即排除
        exclude = match_def.get("exclude_keywords", [])
        if exclude and any(kw in summary for kw in exclude):
            return False
        # require_keywords: 必须全部命中才通过
        require = match_def.get("require_keywords", [])
        if require and not all(kw in summary for kw in require):
            return False
        pattern = match_def.get("counterparty_pattern")
        if pattern and pattern not in counterparty:
            return False
        return True


# ── L2: 历史匹配器 ──────────────────────────────────────────


class HistoryMatcher:
    """TF-IDF 历史库相似度匹配策略。

    封装 SubjectHistoryRepo，提供统一 match() 接口。
    可替换为任何实现相同接口的对象（如远程 ML 服务）。
    """

    def __init__(self, repo):
        self._repo = repo

    def match(self, summary: str, direction: str) -> MatchResult | None:
        """返回 MatchResult 或 None（未命中）。"""
        if self._repo is None:
            return None
        return self._repo.find_similar(summary, direction)


# ── 编排层 ──────────────────────────────────────────────────


class SubjectMatcher:
    """科目匹配编排器 — L1 → L2 → L3 串联。

    调用方只需 ``matcher.match(summary, direction, counterparty)``，
    无需了解三层内部结构。
    """

    def __init__(
        self,
        rule_matcher: RuleMatcher | None = None,
        history_matcher: HistoryMatcher | None = None,
    ):
        self._rules = rule_matcher or RuleMatcher()
        self._history = history_matcher

    def match(
        self,
        summary: str,
        direction: str,
        counterparty: str = '',
    ) -> MatchResult:
        """L1 规则 → L2 历史 → L3 兜底。"""
        # L1
        result = self._rules.match(summary, direction, counterparty)
        if result.source == 'rule':
            return result

        # L2
        if self._history:
            hist = self._history.match(summary, direction)
            if hist is not None:
                # L2 结果补充 aux_category
                aux_cat, aux_cat_name = self._rules.get_aux_category(hist.subject_code)
                if not hist.aux_category:
                    hist.aux_category = aux_cat
                if not hist.aux_category_name:
                    hist.aux_category_name = aux_cat_name
                return hist

        # L3
        return MatchResult()


# ── 向后兼容的便捷函数 ───────────────────────────────────────


_default_rule_matcher: RuleMatcher | None = None


def match(
    summary: str,
    direction: str,
    counterparty: str = '',
    rules: str | dict | None = None,
    repo: object | None = None,
) -> MatchResult:
    """L1→L2→L3 三层串联匹配（向后兼容 API）。

    参数:
        summary: 交易摘要
        direction: 'expense' | 'income'
        counterparty: 对方户名
        rules: 规则来源 — dict、文件路径、或 None（默认内置）
        repo: SubjectHistoryRepo 实例（L2 历史匹配）

    返回:
        MatchResult，未命中时 source='unmatched'
    """
    global _default_rule_matcher
    if rules is None:
        if _default_rule_matcher is None:
            _default_rule_matcher = RuleMatcher()
        rule_matcher = _default_rule_matcher
    else:
        rule_matcher = RuleMatcher(rules)
    history_matcher = HistoryMatcher(repo) if repo else None
    matcher = SubjectMatcher(rule_matcher=rule_matcher, history_matcher=history_matcher)
    return matcher.match(summary, direction, counterparty)
