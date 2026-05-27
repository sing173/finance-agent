"""L2 TF-IDF 历史学习仓库 (Issue #33).

SQLite 读写 + 中文 2-gram TF-IDF 余弦相似度匹配。
仅用户手动修正确认后写入，自动匹配不记录。
"""
from __future__ import annotations

import hashlib
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone

from finance_agent_backend.subject_matcher import MatchResult


class SubjectHistoryRepo:
    """subject_history 表读写封装。"""

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def insert(
        self,
        summary: str,
        direction: str,
        subject_code: str,
        subject_name: str,
        counterparty: str = '',
        voucher_id: str = '',
    ) -> None:
        """写入一条手动修正记录（UNIQUE 约束去重）。"""
        conn = self._connect()
        try:
            conn.execute(
                """INSERT OR IGNORE INTO subject_history
                   (summary, summary_hash, subject_code, subject_name,
                    direction, counterparty, confirmed_at, voucher_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    summary,
                    _hash_summary(summary),
                    subject_code,
                    subject_name,
                    direction,
                    counterparty,
                    datetime.now(timezone.utc).isoformat(),
                    voucher_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def find_similar(
        self,
        summary: str,
        direction: str,
        threshold: float = 0.75,
    ) -> MatchResult | None:
        """TF-IDF 余弦相似度 ≥ threshold 则返回最佳匹配科目。

        参数:
            summary: 待匹配摘要
            direction: 'expense' / 'income'（不同方向不交叉匹配）
            threshold: 余弦相似度阈值（默认 0.75）
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT summary, subject_code, subject_name
                   FROM subject_history
                   WHERE direction = ?
                   ORDER BY confirmed_at DESC
                   LIMIT 200""",
                (direction,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return None

        query_tokens = _tokenize(summary)
        best_score = 0.0
        best_row = None

        for row in rows:
            doc_tokens = _tokenize(row["summary"])
            score = _cosine_similarity(query_tokens, doc_tokens)
            if score > best_score:
                best_score = score
                best_row = row

        if best_row and best_score >= threshold:
            return MatchResult(
                subject_code=best_row["subject_code"],
                subject_name=best_row["subject_name"] or "",
                source="history",
            )

        return None


# ── TF-IDF 工具函数 ────────────────────────────────────────────


def _hash_summary(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _tokenize(text: str) -> Counter[str]:
    """中文 2-gram 字符切片分词（不需要 jieba）。"""
    # 保留中文、字母、数字
    cleaned = ''.join(c for c in text if c.isalnum() or '一' <= c <= '鿿')
    if len(cleaned) < 2:
        return Counter({cleaned: 1}) if cleaned else Counter()
    return Counter(cleaned[i:i+2] for i in range(len(cleaned) - 1))


def _cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    """两个 Counter 向量的余弦相似度。

    返回 [0.0, 1.0] 范围内的值。空向量 → 0.0。
    """
    if not a or not b:
        return 0.0

    # 公共项的 dot product
    common = set(a.keys()) & set(b.keys())
    dot = sum(a[k] * b[k] for k in common)

    # 各自的 L2 范数
    norm_a = math.sqrt(sum(v ** 2 for v in a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)