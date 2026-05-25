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

    def compose(
        self,
        transactions: list[Transaction],
        subject_mapping: dict,
        account_registry_entries: list | None = None,
    ) -> list[dict]:
        """将交易组装为凭证列表。

        合并规则: 相同对方科目+相同方向+相同银行科目 → 一张凭证。
        银行科目从 Transaction.account_number 查 account_registry。
        """
        # 按 (bank_subject, counterpart_subject, direction) 分组
        groups: dict[tuple[str, str, str], list[Transaction]] = {}

        for txn in transactions:
            result = match_subject(txn.description, txn.direction, txn.counterparty or '', rules=subject_mapping)
            counter_code = result.subject_code or '__unmatched__'
            counterpart_name = result.subject_name or ''

            bank_code = self._resolve_bank_subject(txn, account_registry_entries)
            bank_name = bank_code  # simplified

            key = (bank_code, counter_code, txn.direction)
            groups.setdefault(key, []).append(txn)

        vouchers = []
        voucher_no = 0
        for (bank_code, counter_code, direction), group_txns in groups.items():
            voucher_no += 1
            entries = []
            total = Decimal('0')
            for txn in group_txns:
                total += txn.amount
            amount = float(total)

            if direction == 'expense':
                # 借 对方科目, 贷 银行科目
                for txn in group_txns:
                    result = match_subject(txn.description, txn.direction, txn.counterparty or '', rules=subject_mapping)
                    entries.append(self._entry(
                        len(entries) + 1, voucher_no, txn,
                        result.subject_code or '', result.subject_name or '',
                        float(txn.amount), None, result.source, '',
                    ))
                entries.append(self._bank_entry(
                    len(entries) + 1, voucher_no, txn.date,
                    None, amount, bank_code, bank_code,
                ))
            else:  # income
                # 借 银行科目, 贷 对方科目
                entries.append(self._bank_entry(
                    1, voucher_no, group_txns[0].date,
                    amount, None, bank_code, bank_code,
                ))
                for txn in group_txns:
                    result = match_subject(txn.description, txn.direction, txn.counterparty or '', rules=subject_mapping)
                    entries.append(self._entry(
                        len(entries) + 1, voucher_no, txn,
                        result.subject_code or '', result.subject_name or '',
                        None, float(txn.amount), result.source, '',
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
            "match_source": "unmatched",
            "original_summary": "",
            "original_amount": 0.0,
            "is_manual": False,
        }

    @staticmethod
    def _resolve_bank_subject(txn: Transaction, entries: list | None) -> str:
        """根据交易中的账号号码匹配银行科目。
        简化实现: 从 account_mapping.json entries 中按 suffix 匹配。
        """
        if not entries:
            return '10002'  # 默认银行存款

        acct = txn.account_number or ''
        # suffix match
        for e in entries:
            if e.get('matchType') == 'suffix' and acct.endswith(e.get('pattern', '')):
                return e.get('subjectCode', '10002')

        return '10002'