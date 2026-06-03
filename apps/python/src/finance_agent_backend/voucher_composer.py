"""凭证组装 + 预览 (Issue #34).

同类合并规则 + 借贷方向推导 + preview/save_draft JSON-RPC。

架构: compose() 编排 → VoucherGrouper 分组+预匹配 → VoucherEntryFactory 分录
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from finance_agent_backend.models import Transaction
from finance_agent_backend.subject_matcher import match as match_subject


# ── 数据结构 ──────────────────────────────────────────────────


@dataclass
class GroupedTxn:
    """带有预计算匹配结果的交易。"""
    txn: Transaction
    counter_code: str
    counter_name: str
    match_source: str
    match_rule_id: str = ''


@dataclass
class VoucherGroup:
    """同一张凭证下的交易组（相同银行账号 + 对方科目 + 方向）。"""
    account_number: str
    direction: str
    counterparty_account: str
    counter_code: str = ''        # 对方科目代码（来自分组 key）
    bank_code: str = ''
    bank_name: str = ''
    txns: list[GroupedTxn] = field(default_factory=list)


# ── 分组器 ──────────────────────────────────────────────────


class VoucherGrouper:
    """将交易列表按合并规则分组，并在分组时预计算科目匹配结果。

    消除 compose() 中对同一笔交易调用 3 次 match_subject() 的问题。
    """

    def __init__(self, repo=None, account_registry=None):
        self._repo = repo
        self._registry = account_registry

    def group(self, transactions: list[Transaction], subject_mapping: dict) -> list[VoucherGroup]:
        """分组 + 预匹配，返回 VoucherGroup 列表。"""
        from finance_agent_backend.account_registry import AccountRegistry

        registry = self._registry or AccountRegistry([])

        raw: dict[tuple, list[GroupedTxn]] = {}

        for txn in transactions:
            # 预计算对方科目匹配（仅一次）
            result = match_subject(
                txn.description, txn.direction,
                txn.counterparty or '', rules=subject_mapping,
                repo=self._repo,
            )
            counter_code = result.subject_code or '__unmatched__'

            acct = txn.account_number or ''
            counterparty_acct = txn.reference_number or ''

            if counter_code == '__unmatched__':
                # 未匹配时每条独立，用 id(txn) 确保 key 唯一（用户需逐条手工审）
                key = (acct, counter_code, txn.direction, str(id(txn)))
            else:
                key = (acct, counter_code, txn.direction, counterparty_acct)
            raw.setdefault(key, []).append(GroupedTxn(
                txn=txn,
                counter_code=counter_code,
                counter_name=result.subject_name or '',
                match_source=result.source,
                match_rule_id=result.rule_id,
            ))

        # 构建 VoucherGroup，预解析银行科目
        groups: list[VoucherGroup] = []
        for (acct, counter_code, direction, cpty_acct), gtxns in raw.items():
            bank_entry = registry.match_by_account(acct)
            bank_code = bank_entry.subjectCode if bank_entry else '10002'
            bank_name = bank_entry.subjectName if bank_entry else '银行存款'

            groups.append(VoucherGroup(
                account_number=acct,
                direction=direction,
                counterparty_account=cpty_acct,
                counter_code=counter_code,
                bank_code=bank_code,
                bank_name=bank_name,
                txns=gtxns,
            ))
        return groups


# ── 分录工厂 ──────────────────────────────────────────────────


class VoucherEntryFactory:
    """将 VoucherGroup 转换为凭证分录列表。

    纯函数：给定 group + voucher_no，输出 dict 列表。
    不涉及匹配逻辑，只做方向推导和格式转换。
    """

    @staticmethod
    def build(group: VoucherGroup, voucher_no: int) -> list[dict]:
        entries: list[dict] = []
        total = float(sum(Decimal(str(t.txn.amount)) for t in group.txns))

        if group.direction == 'expense':
            # 借 对方科目, 贷 银行科目（汇总）
            for gt in group.txns:
                entries.append(VoucherEntryFactory._entry(
                    len(entries) + 1, voucher_no, gt.txn,
                    gt.counter_code or '', gt.counter_name,
                    float(gt.txn.amount), None, gt.match_source,
                ))
            entries.append(VoucherEntryFactory._bank_entry(
                len(entries) + 1, voucher_no, group.txns[0].txn.date,
                None, total, group.bank_code, group.bank_name,
            ))
        else:
            # income: 借 银行科目（汇总）, 贷 对方科目
            entries.append(VoucherEntryFactory._bank_entry(
                1, voucher_no, group.txns[0].txn.date,
                total, None, group.bank_code, group.bank_name,
            ))
            for gt in group.txns:
                entries.append(VoucherEntryFactory._entry(
                    len(entries) + 1, voucher_no, gt.txn,
                    gt.counter_code or '', gt.counter_name,
                    None, float(gt.txn.amount), gt.match_source,
                ))

        return entries

    @staticmethod
    def _entry(seq, vno, txn, code, name, debit, credit, source, rule_id=''):
        return {
            "entry_seq": seq, "voucher_no": vno,
            "date": str(txn.date), "summary": txn.description,
            "subject_code": code, "subject_name": name,
            "debit_amount": debit, "credit_amount": credit,
            "direction": txn.direction,
            "counterparty": txn.counterparty or '',
            "match_source": source,
            "original_summary": txn.description,
            "original_amount": float(txn.amount),
            "is_manual": False,
        }

    @staticmethod
    def _bank_entry(seq, vno, dt, debit, credit, code, name):
        return {
            "entry_seq": seq, "voucher_no": vno,
            "date": str(dt), "summary": "银行科目",
            "subject_code": code, "subject_name": name,
            "debit_amount": debit, "credit_amount": credit,
            "direction": "bank",
            "counterparty": "",
            "match_source": "auto",
            "original_summary": "",
            "original_amount": 0.0,
            "is_manual": False,
        }


# ── 主类：编排层 ──────────────────────────────────────────────


class VoucherComposer:
    """凭证组装——编排 grouper + factory，生成凭证列表。"""

    def __init__(self, repo=None):
        self._repo = repo

    def compose(
        self,
        transactions: list[Transaction],
        subject_mapping: dict,
        account_registry=None,
    ) -> list[dict]:
        """将交易组装为凭证列表。

        compose() 仅做编排：grouper 负责分组+预匹配，factory 负责分录格式。
        """
        grouper = VoucherGrouper(repo=self._repo, account_registry=account_registry)
        groups = grouper.group(transactions, subject_mapping)

        vouchers = []
        for voucher_no, group in enumerate(groups, start=1):
            vouchers.append({
                "voucher_no": voucher_no,
                "date": str(group.txns[0].txn.date),
                "direction": group.direction,
                "bank_subject_code": group.bank_code,
                "counterpart_subject_code": group.counter_code,
                "entries": VoucherEntryFactory.build(group, voucher_no),
            })
        return vouchers
