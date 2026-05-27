"""凭证组装 + 预览 (Issue #34).

同类合并规则 + 借贷方向推导 + preview/save_draft JSON-RPC。
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from finance_agent_backend.models import Transaction
from finance_agent_backend.db import init_db
from finance_agent_backend.subject_matcher import match as match_subject


class VoucherComposer:
    """凭证组装——将交易列表转为凭证分录（同类合并 + 借贷方向推导）。"""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        self._history_repo = None  # lazy-init in compose()

    def compose(
        self,
        transactions: list[Transaction],
        subject_mapping: dict,
        account_registry=None,  # AccountRegistry | None
    ) -> list[dict]:
        """将交易组装为凭证列表。

        合并规则: 相同银行账号+相同对方科目+相同方向 → 一张凭证。
        银行科目从 Transaction.account_number 查 account_registry 解析。
        对方科目通过 subject_mapping 规则匹配。
        """
        from finance_agent_backend.account_registry import AccountRegistry
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        if account_registry is None:
            registry = AccountRegistry([])
        else:
            registry = account_registry

        # L2 历史仓库 — 按需初始化
        if self._history_repo is None and self._db_path:
            try:
                conn = sqlite3.connect(self._db_path)
                init_db(conn)
                conn.close()
                self._history_repo = SubjectHistoryRepo(self._db_path)
            except Exception:
                self._history_repo = None

        # 分组 + 匹配（含 L1→L2→L3 串联），同时缓存匹配结果避免重复调用
        groups: dict[tuple[str, str, str, str], list[Transaction]] = {}
        match_cache: dict[int, tuple[str, str, str]] = {}  # id(txn) → (code, name, source)

        for txn in transactions:
            result = match_subject(
                txn.description, txn.direction, txn.counterparty or '',
                rules=subject_mapping,
                repo=self._history_repo,
            )
            counter_code = result.subject_code or '__unmatched__'
            counter_name = result.subject_name or ''
            match_cache[id(txn)] = (counter_code, counter_name, result.source)

            acct = txn.account_number or ''
            bank_entry = registry.match_by_account(acct)
            bank_code = bank_entry.subjectCode if bank_entry else '10002'

            # 对方账号(reference_number)有值时参与分组, 无值视为通配
            counterparty_acct = txn.reference_number or ''

            if counter_code == '__unmatched__':
                # 未匹配时每条独立, 用 id(txn) 确保 key 唯一(转 str 塞入第4位)
                key = (acct, counter_code, txn.direction, str(id(txn)))
            else:
                key = (acct, counter_code, txn.direction, counterparty_acct)
            groups.setdefault(key, []).append(txn)

        vouchers = []
        voucher_no = 0
        for (acct, counter_code, direction, _), group_txns in groups.items():
            voucher_no += 1
            entries = []
            total = Decimal('0')
            for txn in group_txns:
                total += txn.amount
            amount = float(total)

            bank_entry = registry.match_by_account(acct)
            bank_code = bank_entry.subjectCode if bank_entry else '10002'
            bank_name = bank_entry.subjectName if bank_entry else '银行存款'

            if direction == 'expense':
                # 借 对方科目, 贷 银行科目（汇总）
                for txn in group_txns:
                    code, name, source = match_cache[id(txn)]
                    entries.append(self._entry(
                        len(entries) + 1, voucher_no, txn,
                        code, name,
                        float(txn.amount), None, source, '',
                    ))
                entries.append(self._bank_entry(
                    len(entries) + 1, voucher_no, group_txns[0].date,
                    None, amount, bank_code, bank_name,
                ))
            else:  # income
                # 借 银行科目（汇总）, 贷 对方科目
                entries.append(self._bank_entry(
                    1, voucher_no, group_txns[0].date,
                    amount, None, bank_code, bank_name,
                ))
                for txn in group_txns:
                    code, name, source = match_cache[id(txn)]
                    entries.append(self._entry(
                        len(entries) + 1, voucher_no, txn,
                        code, name,
                        None, float(txn.amount), source, '',
                    ))

            vouchers.append({
                "voucher_no": voucher_no,
                "date": str(group_txns[0].date),
                "direction": direction,
                "bank_subject_code": bank_code,
                "counterpart_subject_code": counter_code,
                "entries": entries,
            })

        return vouchers

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