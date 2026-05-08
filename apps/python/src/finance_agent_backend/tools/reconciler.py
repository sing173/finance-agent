"""Reconciliation algorithm with 4-stage matching"""
from rapidfuzz import fuzz, utils
from datetime import date
from typing import List, Dict, Optional
from decimal import Decimal

from ..models import Transaction, ReconcileResult


class Reconciler:
    """四阶段对账算法"""

    def __init__(self):
        self.stage_weights = {
            'exact': 1.0,
            'rule': 0.95,
            'fuzzy': 0.85,
            'unreconciled': 0.0,
        }

    def reconcile(
        self,
        bank_transactions: List[Transaction],
        ledger_transactions: List[Transaction],
    ) -> ReconcileResult:
        """执行四阶段对账"""
        matched = []
        bank_unreconciled = list(bank_transactions)
        ledger_unreconciled = list(ledger_transactions)
        suspicious = []

        # 阶段 1：精确匹配
        self._exact_match(bank_unreconciled, ledger_unreconciled, matched)

        # 阶段 2：规则匹配
        self._rule_match(bank_unreconciled, ledger_unreconciled, matched, suspicious)

        # 阶段 3：模糊匹配
        self._fuzzy_match(bank_unreconciled, ledger_unreconciled, matched, suspicious)

        # 阶段 4：未达分类（剩余的即为未达账）

        return ReconcileResult(
            matched=matched,
            bank_unreconciled=bank_unreconciled,
            ledger_unreconciled=ledger_unreconciled,
            suspicious=suspicious,
            total_bank=len(bank_transactions),
            total_ledger=len(ledger_transactions),
            match_rate=(
                len(matched) / len(bank_transactions)
                if bank_transactions else 0.0
            ),
        )

    def _exact_match(self, bank_list, ledger_list, matched):
        """精确匹配：金额相同（±0.01，考虑方向）+ 日期差 ≤ 3 天 + 户名相似度 ≥ 90"""
        for bank_tx in list(bank_list):
            for ledger_tx in list(ledger_list):
                # 标准化金额（考虑方向：income为正，expense为负）
                bank_signed_amount = bank_tx.amount if bank_tx.direction == 'income' else -bank_tx.amount
                ledger_signed_amount = ledger_tx.amount

                if (
                    abs(bank_signed_amount - ledger_signed_amount) <= Decimal('0.01')
                    and abs((bank_tx.date - ledger_tx.date).days) <= 3
                    and fuzz.ratio(
                        bank_tx.description or '',
                        ledger_tx.description or '',
                    ) >= 90
                ):
                    matched.append({
                        'bank': bank_tx,
                        'ledger': ledger_tx,
                        'method': 'exact',
                        'score': 1.0,
                    })
                    bank_list.remove(bank_tx)
                    ledger_list.remove(ledger_tx)
                    break

    def _rule_match(self, bank_list, ledger_list, matched, suspicious):
        """规则匹配：预定义映射规则（如"支付宝"→"支付宝备付金"）"""
        rules = [
            {'pattern': '支付宝', 'replace': '支付宝备付金'},
            {'pattern': '微信', 'replace': '微信支付科技有限公司'},
        ]

        # 应用规则到银行交易
        for rule in rules:
            for bank_tx in bank_list:
                if bank_tx.counterparty and rule['pattern'] in bank_tx.counterparty:
                    bank_tx.counterparty = rule['replace']

        # 重新执行精确匹配
        self._exact_match(bank_list, ledger_list, matched)

    def _fuzzy_match(self, bank_list, ledger_list, matched, suspicious):
        """模糊匹配：剩余交易按综合相似度匹配（阈值 0.85）"""
        for bank_tx in list(bank_list):
            best_match = None
            best_score = 0.85  # 阈值

            for ledger_tx in list(ledger_list):
                score = fuzz.ratio(
                    bank_tx.description or '',
                    ledger_tx.description or '',
                )
                if score > best_score:
                    best_score = score
                    best_match = ledger_tx

            if best_match:
                matched.append({
                    'bank': bank_tx,
                    'ledger': best_match,
                    'method': 'fuzzy',
                    'score': best_score / 100.0,
                })
                bank_list.remove(bank_tx)
                ledger_list.remove(best_match)
            else:
                # 相似度 0.80-0.85 的归入可疑
                max_score = 0
                for ledger_tx in ledger_list:
                    s = fuzz.ratio(bank_tx.description or '', ledger_tx.description or '')
                    max_score = max(max_score, s)
                if 80 <= max_score < 85:
                    suspicious.append({
                        'bank': bank_tx,
                        'score': max_score / 100.0,
                    })
