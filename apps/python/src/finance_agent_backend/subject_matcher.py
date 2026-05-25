"""L1 JSON 规则匹配引擎 (Issue #32).

纯配置驱动的交易摘要→科目匹配。按 priority 升序尝试，首个命中即停。

用法::

    from finance_agent_backend.subject_matcher import match
    result = match("支付物业管理费", "expense", "启胜物业")
    # → MatchResult(subject_code="5060203", source="rule", ...)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class MatchResult:
    subject_code: str = ''        # 科目代码，未命中为空
    subject_name: str = ''
    source: str = 'unmatched'    # 'rule' | 'history' | 'manual' | 'unmatched'
    rule_id: str = ''


# ── 规则加载 ──────────────────────────────────────────────────


def _default_rules_path() -> str:
    import finance_agent_backend
    backend_dir = os.path.dirname(os.path.abspath(finance_agent_backend.__file__))
    return os.path.join(backend_dir, 'config', 'subject_mapping.json')


def _load_rules(path: str) -> dict:
    """加载规则文件。读取失败返回空结构。"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"version": 0, "expense": {"rules": []}, "income": {"rules": []}}


# ── 匹配逻辑 ──────────────────────────────────────────────────


def _match_rule(rule: dict, summary: str, counterparty: str) -> bool:
    """单条规则是否匹配摘要/对方户名。"""
    match_def = rule.get("match", {})

    # 关键字：任一命中
    keywords = match_def.get("keywords", [])
    if not any(kw in summary for kw in keywords):
        return False

    # counterparty_pattern（可选）：存在时对方户名须包含
    pattern = match_def.get("counterparty_pattern")
    if pattern and pattern not in counterparty:
        return False

    return True


def match(
    summary: str,
    direction: str,
    counterparty: str = '',
    rules: str | dict | None = None,
) -> MatchResult:
    """将交易摘要匹配到会计科目（L1 JSON 规则）。

    参数:
        summary: 交易摘要（如 "支付物业管理费"）
        direction: 交易方向 'expense' | 'income'
        counterparty: 对方户名（可选，用于联合规则）
        rules: 规则来源 — 文件路径(str)、规则 dict、或 None(默认配置文件)

    返回:
        MatchResult，未命中时 source='unmatched'
    """
    if isinstance(rules, dict):
        data = rules
    elif isinstance(rules, str):
        data = _load_rules(rules)
    else:
        data = _load_rules(_default_rules_path())

    direction_rules = data.get(direction, {})
    rules = direction_rules.get("rules", [])

    # 按 priority 升序排序
    sorted_rules = sorted(rules, key=lambda r: r.get("priority", 999))

    for rule in sorted_rules:
        if _match_rule(rule, summary, counterparty):
            return MatchResult(
                subject_code=rule.get("subject_code", ""),
                subject_name=rule.get("subject_name", ""),
                source="rule",
                rule_id=rule.get("id", ""),
            )

    return MatchResult()