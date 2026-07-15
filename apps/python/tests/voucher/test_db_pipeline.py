"""Tracer bullet: 验证 aux_category 在 save_draft → load_draft → export 全链路不丢失（Issue #46 补漏）。"""
import sys
import os
import tempfile
import atexit


from finance_agent_backend.subject_matcher import RuleMatcher


def _cleanup_db(db_path):
    """延迟删除，避免 SQLite WAL 文件锁。"""
    def _do():
        try:
            from finance_agent_backend import db as _db
            _db.close_db()
            os.unlink(db_path)
        except Exception:
            pass
    atexit.register(_do)


def test_aux_category_save_load_roundtrip(seeded_subjects_db):
    """匹配结果 → save_draft → load_draft，aux_category 应保留。"""
    from finance_agent_backend.bridge import handle_voucher_save_draft, handle_voucher_load_draft

    # Step 1: 匹配获取 aux_category
    matcher = RuleMatcher()
    result = matcher.match("报销", "expense")
    assert result.aux_category == "04", f"匹配 aux_category 应为 04，实际 {result.aux_category}"

    # Step 2: 构造 entry dict（模拟 VoucherEntryFactory 输出）
    entry = {
        "entry_seq": 1, "voucher_no": 1,
        "date": "2024-01-15", "summary": "支付报销款",
        "subject_code": result.subject_code, "subject_name": result.subject_name,
        "debit_amount": 100.0, "credit_amount": None,
        "direction": "expense", "counterparty": "测试",
        "match_source": result.source, "rule_id": result.rule_id,
        "original_summary": "支付报销款", "original_amount": 100.0, "is_manual": False,
        "aux_category": result.aux_category, "aux_category_name": result.aux_category_name,
    }

    # Step 3: save_draft
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    _cleanup_db(db_path)
    save_result = handle_voucher_save_draft({
        "db_path": db_path, "name": "test", "period": "202401", "entries": [entry]
    })
    assert save_result["success"] is True, f"save_draft 失败: {save_result}"
    draft_id = save_result["draft_id"]

    # Step 4: load_draft
    load_result = handle_voucher_load_draft({"db_path": db_path, "draft_id": draft_id})
    assert load_result["success"] is True
    loaded = load_result["draft"]["entries"]
    assert len(loaded) == 1
    assert loaded[0]["aux_category"] == "04", (
        f"load_draft aux_category 应为 '04'，实际 '{loaded[0].get('aux_category')}'"
    )
    assert loaded[0]["aux_category_name"] == "公共部门", (
        f"load_draft aux_category_name 应为 '公共部门'，实际 '{loaded[0].get('aux_category_name')}'"
    )


def test_aux_category_db_schema():
    """DB schema v3 应包含 aux_category 列。"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    _cleanup_db(db_path)
    try:
        from finance_agent_backend import db as _db
        conn = _db.get_db(db_path=db_path)
        _db.init_db(conn)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(voucher_draft_entry)").fetchall()]
        assert 'aux_category' in cols, "voucher_draft_entry 缺少 aux_category 列"
        assert 'aux_category_name' in cols, "voucher_draft_entry 缺少 aux_category_name 列"
        # 验证 schema_version = 3
        ver = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
        assert ver[0] >= 3, f"schema_version 应 >= 3，实际 {ver[0]}"
    finally:
        pass  # cleanup via atexit
