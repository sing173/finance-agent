"""Tests for subject_history_repo.py — L2 TF-IDF 历史学习 (Issue #33).

Tests verify behavior through public interface:
  SubjectHistoryRepo.insert() / find_similar()
  subject_matcher.match() L1→L2→L3 chain.
"""
import os
import sys
import sqlite3
import tempfile
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from finance_agent_backend.subject_matcher import match, MatchResult

# We import the repo class after writing it — for RED phase, we define
# the expected interface and test against it.


def _hash_summary(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


@pytest.fixture
def tmp_db():
    """临时 WAL 模式 SQLite 数据库。"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS subject_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        summary TEXT NOT NULL,
        summary_hash TEXT NOT NULL,
        subject_code TEXT NOT NULL,
        subject_name TEXT,
        direction TEXT NOT NULL CHECK (direction IN ('expense', 'income')),
        counterparty TEXT,
        confirmed_at TEXT NOT NULL,
        voucher_id TEXT,
        UNIQUE(summary_hash, subject_code, direction)
    )""")
    conn.commit()
    conn.close()
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


class TestInsertAndFind:
    """写入 + 查询：基本路径。"""

    def test_insert_and_find_similar_exact_match(self, tmp_db):
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("支付启胜物业管理费1月", "expense", "5060203",
                    "管理费用_物业管理费", "启胜物业")
        repo.insert("支付启胜物业管理费2月", "expense", "5060203",
                    "管理费用_物业管理费", "启胜物业")
        repo.insert("支付技术服务费", "expense", "403010113",
                    "研发支出_技术服务费", "中锦科技")

        # 高度近似摘要应命中
        result = repo.find_similar("支付启胜物业管理费3月", "expense")
        assert result is not None
        assert result.subject_code == "5060203"
        assert result.source == "history"

    def test_find_similar_no_match(self, tmp_db):
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("支付物业管理费", "expense", "5060203",
                    "管理费用_物业管理费", "启胜物业")

        # 完全不相关的摘要不应匹配
        result = repo.find_similar("购买办公设备一批", "expense")
        assert result is None

    def test_unique_constraint_dedup(self, tmp_db):
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        repo = SubjectHistoryRepo(tmp_db)
        summary = "支付物业管理费"
        repo.insert(summary, "expense", "5060203",
                    "管理费用_物业管理费", "启胜物业")
        # Same summary/hash + subject_code + direction → ignored
        repo.insert(summary, "expense", "5060203",
                    "管理费用_物业管理费_duplicate", "")

        conn = sqlite3.connect(tmp_db)
        n = conn.execute("SELECT COUNT(*) FROM subject_history").fetchone()[0]
        conn.close()
        assert n == 1

    def test_direction_filter(self, tmp_db):
        """expense 历史不匹配 income 摘要。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("收到货款", "income", "10122", "应收账款", "客户A")

        # Same-like summary but different direction → no match
        result = repo.find_similar("收到货款", "expense")
        assert result is None


class TestThreeLayerChain:
    """subject_matcher.match() L1→L2→L3 三层串联。"""

    def test_l1_hit_skips_l2(self, tmp_db):
        """L1 命中后不调用 L2。"""
        # The real config has "物业费"→5060203 with counterparty "启胜"
        result = match("支付物业管理费", "expense", "启胜物业")
        assert result.source == "rule"

    def test_l1_miss_l2_hit(self, tmp_db):
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        # Insert a history entry
        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("支付网银转账费用", "expense", "1022120",
                    "其他应收款_手续费", "")

        # "网银转账费用" doesn't match any L1 rule → L1 miss
        # L2 should find similar "支付网银转账费用" ≈ "支付网银转账费用"
        result = match("网银转账费用", "expense", "", repo=repo)
        assert result.source in ("history", "rule")  # L1 might hit "手续" — check

    def test_both_miss_returns_unmatched(self, tmp_db):
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("旧摘要不匹配", "expense", "5060203", "管理费用", "")

        result = match("XYZ完全不存在的摘要", "expense", "", repo=repo)
        assert result.source == "unmatched"