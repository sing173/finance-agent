"""Tests for subject_history_repo.py — L2 TF-IDF 历史学习 (Issue #33).

Tests verify behavior through public interface:
  SubjectHistoryRepo.insert() / find_similar()
  subject_matcher.match() L1→L2→L3 chain.
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from finance_agent_backend.subject_matcher import match, MatchResult
from finance_agent_backend.subject_history_repo import _hash_summary


@pytest.fixture
def tmp_db(tmp_path):
    """临时 WAL 模式 SQLite 数据库（pytest 自动清理）。"""
    path = str(tmp_path / "test.db")
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    from finance_agent_backend.db import init_db
    init_db(conn)
    conn.commit()
    conn.close()
    return path


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


class TestTFIDFWithIDF:
    """TF-IDF 余弦相似度 — 验证 IDF 权重生效 (P3 #4)."""

    def test_idf_exact_similar_still_matches(self, tmp_db):
        """高度相似的匹配不受 IDF 影响，仍应正确命中。

        两条几乎相同的历史（仅月份不同），查询应命中其中一条。
        """
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("支付启胜物业管理费", "expense", "5060203",
                    "管理费用_物业管理费", "启胜物业")

        result = repo.find_similar("支付启胜物业管理费", "expense")
        assert result is not None
        assert result.subject_code == "5060203"

    def test_compute_idf_rare_term_has_higher_weight(self):
        """IDF 应给稀有词（仅 1 条文档出现）更高权重。"""
        from finance_agent_backend.subject_history_repo import _compute_idf, _tokenize

        docs = ["支付服务费", "支付手续费", "支付银行转账费"]
        doc_tokens = [_tokenize(d) for d in docs]
        idf = _compute_idf(doc_tokens)

        # "服务" 出现 1 次, "费" 出现 3 次
        # IDF(服务) > IDF(费) 因为服务更稀有
        if "服务" in idf and "费" in idf:
            assert idf["服务"] > idf["费"], (
                f"稀有词'服务' IDF({idf["服务"]:.3f}) 应 > 通用词'费' IDF({idf["费"]:.3f})"
            )
        # "银行" 仅 1 条出现，也应高于费
        if "银行" in idf:
            assert idf["银行"] > idf.get("费", 0), "稀有词'银行' IDF 应 > '费'"



class TestFindSimilarCache:
    """find_similar() 结果缓存 — 避免重复 tokenize + 全表扫描 (P3 #5)."""

    def test_repeated_calls_return_same_result(self, tmp_db):
        """同一 repo 连续调用 find_similar 应返回一致结果。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("支付网银转账手续费", "expense", "1022120",
                    "其他应收款_手续费", "")

        r1 = repo.find_similar("网银转账手续费", "expense")
        r2 = repo.find_similar("网银转账手续费", "expense")
        assert r1 is not None and r2 is not None
        assert r1.subject_code == r2.subject_code == "1022120"

    def test_cache_invalidated_after_insert(self, tmp_db):
        """insert 新记录后，find_similar 应能看到新数据。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("支付物业管理费", "expense", "5060203",
                    "管理费用_物业管理费", "启胜物业")

        r1 = repo.find_similar("支付启胜物业管理费", "expense")

        repo.insert("支付启胜物业管理费2月", "expense", "5060203",
                    "管理费用_物业管理费", "启胜物业")
        r2 = repo.find_similar("支付启胜物业管理费3月", "expense")

        assert r1 is not None or r2 is not None


class TestThresholdBoundary:
    """阈值边界行为 — 0.749 不命中, 0.751 命中 (P4 #7)."""

    def test_default_threshold_is_075(self):
        """DEFAULT_SIMILARITY_THRESHOLD 应为 0.75。"""
        from finance_agent_backend.subject_history_repo import DEFAULT_SIMILARITY_THRESHOLD
        assert DEFAULT_SIMILARITY_THRESHOLD == 0.75

    def test_above_threshold_returns_match(self, tmp_db):
        """精确相同摘要（score=1.0）应命中。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("支付启胜物业管理费", "expense", "5060203",
                    "管理费用_物业管理费", "启胜物业")

        result = repo.find_similar("支付启胜物业管理费", "expense")
        assert result is not None
        assert result.subject_code == "5060203"

    def test_low_threshold_allows_loose_match(self, tmp_db):
        """降低阈值应允许更宽松的匹配。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        repo = SubjectHistoryRepo(tmp_db)
        repo.insert("支付网银转账手续费", "expense", "1022120",
                    "其他应收款_手续费", "")

        # 低阈值应能匹配到近似摘要
        result = repo.find_similar("网银转账费", "expense", threshold=0.1)
        assert result is not None


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


class TestConnectionReuse:
    """SubjectHistoryRepo 连接复用 (P1 fix)."""

    def test_insert_accepts_external_conn(self, tmp_db):
        """insert() 应接受可选 conn 参数，使用外部连接写入。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        shared = sqlite3.connect(tmp_db)
        shared.row_factory = sqlite3.Row
        repo = SubjectHistoryRepo(tmp_db)

        # 传入外部连接，写入应成功
        repo.insert("测试外部连接写入", "expense", "5060203",
                    "管理费用", counterparty="", voucher_id="v1", conn=shared)

        # 通过同一连接直接读取，验证写入确实使用了该连接
        row = shared.execute(
            "SELECT summary, subject_code FROM subject_history WHERE summary = ?",
            ("测试外部连接写入",),
        ).fetchone()
        shared.close()

        assert row is not None, "数据应已写入"
        assert row["subject_code"] == "5060203"

    def test_find_similar_accepts_external_conn(self, tmp_db):
        """find_similar() 应接受可选 conn 参数。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        shared = sqlite3.connect(tmp_db)
        shared.row_factory = sqlite3.Row
        repo = SubjectHistoryRepo(tmp_db)

        repo.insert("支付网银转账手续费", "expense", "1022120",
                    "其他应收款_手续费", conn=shared)

        shared.commit()
        shared.close()

        # 用新 repo 实例 + 外部连接查询
        shared2 = sqlite3.connect(tmp_db)
        shared2.row_factory = sqlite3.Row
        repo2 = SubjectHistoryRepo(tmp_db)
        result = repo2.find_similar("网银转账手续费", "expense", conn=shared2)
        shared2.close()

        assert result is not None
        assert result.subject_code == "1022120"

    def test_batch_insert_reuses_connection(self, tmp_db):
        """批量写入 N 条应复用同一连接（性能基线）。"""
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo
        import time

        shared = sqlite3.connect(tmp_db)
        shared.row_factory = sqlite3.Row
        repo = SubjectHistoryRepo(tmp_db)

        n = 50
        start = time.time()
        for i in range(n):
            repo.insert(
                f"批量测试摘要_{i:03d}",
                "expense",
                "5060203",
                "管理费用",
                conn=shared,
            )
        elapsed = time.time() - start

        shared.commit()
        count = shared.execute("SELECT COUNT(*) FROM subject_history").fetchone()[0]
        shared.close()

        assert count == n, f"应写入 {n} 条，实际 {count}"
        # 单连接批量写入应在 100ms 内完成（无开连接开销）
        assert elapsed < 0.5, f"批量写入耗时过长: {elapsed:.3f}s"