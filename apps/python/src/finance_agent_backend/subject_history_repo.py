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

from finance_agent_backend.db import init_db
from finance_agent_backend.subject_matcher import MatchResult

# L2 余弦相似度阈值：≥ 此值视为匹配
DEFAULT_SIMILARITY_THRESHOLD = 0.75


class SubjectHistoryRepo:
    """subject_history 表读写封装。"""

    # 类级缓存：(db_path, direction) → (rows, doc_tokens_list, idf)
    # insert() 写入后自动失效。
    _cache: dict[tuple[str, str], tuple] = {}

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        init_db(conn)  # 确保 subject_history 等表已建（幂等）
        return conn

    def insert(
        self,
        summary: str,
        direction: str,
        subject_code: str,
        subject_name: str,
        counterparty: str = '',
        voucher_id: str = '',
        conn=None,
    ) -> None:
        """写入一条手动修正记录（UNIQUE 约束去重）。

        参数:
            conn: 外部 sqlite3.Connection（可选）。传入时复用该连接，
                  不传入时自动打开新连接（原有行为不变）。
        """
        close_after = False
        if conn is None:
            conn = self._connect()
            close_after = True
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
            # 使对应 (db_path, direction) 的缓存失效
            SubjectHistoryRepo._cache.pop((self._db_path, direction), None)
        finally:
            if close_after:
                conn.close()

    def find_similar(
        self,
        summary: str,
        direction: str,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        conn=None,
    ) -> MatchResult | None:
        """TF-IDF 余弦相似度 ≥ threshold 则返回最佳匹配科目。

        参数:
            summary: 待匹配摘要
            direction: 'expense' / 'income'（不同方向不交叉匹配）
            threshold: 余弦相似度阈值（默认 DEFAULT_SIMILARITY_THRESHOLD=0.75）
            conn: 外部 sqlite3.Connection（可选）。传入时复用该连接。
        """
        close_after = False
        if conn is None:
            conn = self._connect()
            close_after = True
        try:
            rows = conn.execute(
                """SELECT summary, subject_code, subject_name
                   FROM subject_history
                   WHERE direction = ?
                   ORDER BY confirmed_at DESC""",
                (direction,),
            ).fetchall()
        finally:
            if close_after:
                conn.close()

        if not rows:
            return None

        # 检查缓存：(db_path, direction) → (rows, doc_tokens_list, idf)
        cache_key = (self._db_path, direction)
        cached = SubjectHistoryRepo._cache.get(cache_key)
        if cached is not None:
            cached_rows, doc_tokens_list, idf = cached
            rows = cached_rows  # 用缓存中的 rows（与当前查询结果一致）
        else:
            doc_tokens_list = [_tokenize(row["summary"]) for row in rows]
            idf = _compute_idf(doc_tokens_list)
            SubjectHistoryRepo._cache[cache_key] = (rows, doc_tokens_list, idf)
        query_vec = _compute_tfidf(_tokenize(summary), idf)

        best_score = 0.0
        best_row = None

        for row, doc_tokens in zip(rows, doc_tokens_list):
            doc_vec = _compute_tfidf(doc_tokens, idf)
            score = _cosine_similarity(query_vec, doc_vec)
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
    cleaned = ''.join(c for c in text if c.isalnum() or '一' <= c <= '鿿')
    if len(cleaned) < 2:
        return Counter({cleaned: 1}) if cleaned else Counter()
    return Counter(cleaned[i:i+2] for i in range(len(cleaned) - 1))


def _compute_idf(doc_tokens_list: list[Counter[str]]) -> dict[str, float]:
    """计算逆文档频率 IDF: log(N / df) + 1（平滑处理）。

    N = 文档总数，df = 包含该词的文档数。
    +1 平滑确保即使 df=N（词在所有文档中都出现）时 IDF > 0，
    且单文档场景（N=1）不会导致所有 IDF=0。
    """
    n = len(doc_tokens_list)
    if n == 0:
        return {}
    df: dict[str, int] = {}
    for tokens in doc_tokens_list:
        for term in tokens:
            df[term] = df.get(term, 0) + 1
    return {term: math.log(n / count) + 1.0 for term, count in df.items()}


def _compute_tfidf(tokens: Counter[str], idf: dict[str, float]) -> dict[str, float]:
    """将词频 Counter 转为 TF-IDF 向量（dict）。"""
    total = sum(tokens.values())
    if total == 0:
        return {}
    return {term: (count / total) * idf.get(term, 0.0) for term, count in tokens.items()}


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """两个 TF-IDF 向量的余弦相似度。

    输入应为 _compute_tfidf 返回的 dict（已含 TF-IDF 权重）。
    返回 [0.0, 1.0]，空向量 → 0.0。
    """
    if not a or not b:
        return 0.0

    common = set(a.keys()) & set(b.keys())
    dot = sum(a[k] * b[k] for k in common)

    norm_a = math.sqrt(sum(v ** 2 for v in a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)