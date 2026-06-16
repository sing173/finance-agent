"""TDD 回归测试 — BaseRepository 必须走 from_db_row 做类型转换（修复 #1）。

DB 存 INTEGER，dataclass 标注 bool。BaseRepository.find_all() 不能直接用
model_cls(**row) 跳过 from_db_row()，否则 is_manual 等 bool 字段保留为 int。
"""
import sys
import os
import tempfile
import atexit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from finance_agent_backend.models import PipelineEntry
from finance_agent_backend.repo.voucher_draft_repo import VoucherDraftRepository


def _cleanup_db(db_path):
    """延迟删除，避免 SQLite WAL 文件锁。"""
    def _do():
        try:
            from finance_agent_backend import db as _db
            _db.close_db()
            if os.path.exists(db_path):
                os.unlink(db_path)
        except Exception:
            pass
    atexit.register(_do)


def test_voucher_repo_returns_bool_is_manual():
    """DB 存 is_manual=1 (int)，get_entries() 返回的 PipelineEntry.is_manual 应为 bool True。"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    _cleanup_db(db_path)
    from finance_agent_backend import db as _db
    conn = _db.get_db(db_path=db_path)
    _db.init_db(conn)
    repo = VoucherDraftRepository(conn)
    entry = PipelineEntry(
        entry_seq=1, voucher_no=1, date='2024-01-15',
        summary='test', subject_code='50602', subject_name='管理费用',
        debit_amount=100.0, credit_amount=None,
        direction='expense', counterparty='测试方',
        match_source='rule', rule_id='rule_e032',
        original_summary='test', original_amount=100.0,
        is_manual=True,
    )
    draft_id = repo.create('test_draft', '202401')
    repo.insert_entries(draft_id, [entry])

    entries = repo.get_entries(draft_id)
    assert len(entries) == 1
    loaded = entries[0]

    assert isinstance(loaded.is_manual, bool), (
        f"is_manual 应为 bool，实际 {type(loaded.is_manual).__name__}"
    )
    assert loaded.is_manual is True, f"期望 True，实际 {loaded.is_manual}"


def test_voucher_repo_returns_bool_is_manual_false():
    """DB 存 is_manual=0 (int)，get_entries() 返回的 PipelineEntry.is_manual 应为 bool False。"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    _cleanup_db(db_path)
    from finance_agent_backend import db as _db
    conn = _db.get_db(db_path=db_path)
    _db.init_db(conn)
    repo = VoucherDraftRepository(conn)
    entry = PipelineEntry(
        entry_seq=1, voucher_no=1, date='2024-01-15',
        summary='test', subject_code='50602', subject_name='管理费用',
        debit_amount=100.0, credit_amount=None,
        direction='expense', counterparty='测试方',
        match_source='rule', rule_id='rule_e032',
        original_summary='test', original_amount=100.0,
        is_manual=False,
    )
    draft_id = repo.create('test_draft', '202401')
    repo.insert_entries(draft_id, [entry])

    entries = repo.get_entries(draft_id)
    loaded = entries[0]
    assert isinstance(loaded.is_manual, bool)
    assert loaded.is_manual is False
