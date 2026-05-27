"""v0.3.0 凭证全链路集成测试 — Issue #31-#36 回归。

覆盖：detect → parse → preview → save_draft → load_draft → export → audit_log
每步通过 bridge.handle_request() 串联，模拟完整用户流程。
"""
import os, sys, json, tempfile, uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from finance_agent_backend.bridge import handle_request
from finance_agent_backend import db as _db

# ── 真实测试文件 ──────────────────────────────────────────────

BASE = os.path.join(os.path.dirname(__file__), "fixtures")
REAL_CMB_PDF = os.path.join(BASE, "cmb_statement.pdf")

# ── 辅助 ──────────────────────────────────────────────────────

@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def export_dir():
    d = tempfile.mkdtemp()
    yield d
    for f in os.listdir(d):
        try:
            os.unlink(os.path.join(d, f))
        except OSError:
            pass
    try:
        os.rmdir(d)
    except OSError:
        pass


def _reset_db(db_path):
    """重置 db 模块单例，指向测试数据库。"""
    _db.reset_db(db_path)


def _call(method: str, params: dict):
    response = handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    })
    result = response.get("result", response.get("error", {}))
    if not result.get("success") and "error" in result:
        return result  # error returns are valid test data
    return result


# ── 主流程 ────────────────────────────────────────────────────

def test_voucher_full_pipeline(tmp_db, export_dir):
    """完整流程：真实 CMB PDF → 导出 Excel → 审计日志。"""

    # 跳过条件：真实文件不存在
    if not os.path.exists(REAL_CMB_PDF):
        pytest.skip(f"真实文件不存在: {REAL_CMB_PDF}")

    _reset_db(tmp_db)

    # ══ Phase 1: 识别银行 ═══════════════════════════════════
    print("\n[1/7] detect_banks...")
    detect = _call("detect_banks", {"filePaths": [REAL_CMB_PDF]})
    assert detect["success"] is True
    assert len(detect["results"]) == 1
    bank = detect["results"][0]["bank"]
    doc_type = detect["results"][0]["docType"]
    print(f"  [OK] 检测到: {bank} · {doc_type}")

    # ══ Phase 2: 解析 PDF ═══════════════════════════════════
    print("[2/7] parse_pdf...")
    parse = _call("parse_pdf", {"filePath": REAL_CMB_PDF, "bank": bank, "docType": doc_type})
    assert parse["success"] is True
    assert len(parse["transactions"]) >= 1
    print(f"  [OK] 解析成功: {len(parse['transactions'])} 笔交易")

    # ══ Phase 3: 凭证预览 ═══════════════════════════════════
    print("[3/7] voucher.preview...")
    preview = _call("voucher.preview", {
        "transactions": parse["transactions"],
    })
    assert preview["success"] is True
    vouchers = preview["vouchers"]
    print(f"  [OK] 生成 {len(vouchers)} 张凭证")
    for v in vouchers:
        n_entries = len(v["entries"])
        n_unmatched = sum(1 for e in v["entries"] if e.get("match_source") == "unmatched")
        print(f"    凭证#{v['voucher_no']}: {n_entries} 条分录, {n_unmatched} 未匹配")

    # Flatten all entries across vouchers
    all_entries = []
    for v in vouchers:
        for e in v["entries"]:
            if e.get("direction") != "bank":
                all_entries.append(e)

    if not all_entries:
        pytest.skip("无可导出的非银行分录")

    # ══ Phase 4: 保存草稿 ═══════════════════════════════════
    print("[4/7] voucher.save_draft...")
    draft = _call("voucher.save_draft", {
        "db_path": tmp_db,
        "name": "全链路测试草稿",
        "period": "2026年测试期",
        "entries": all_entries,
    })
    assert draft["success"] is True
    draft_id = draft["draft_id"]
    print(f"  [OK] 草稿 ID: {draft_id}")

    # ══ Phase 5: 列出草稿 ═══════════════════════════════════
    print("[5/7] voucher.list_drafts...")
    drafts_list = _call("voucher.list_drafts", {"db_path": tmp_db})
    assert drafts_list["success"] is True
    ids = [d["id"] for d in drafts_list["drafts"]]
    assert draft_id in ids
    print(f"  [OK] 草稿列表中包含: {len(drafts_list['drafts'])} 个")

    # ══ Phase 6: 加载草稿 ═══════════════════════════════════
    print("[6/7] voucher.load_draft...")
    loaded = _call("voucher.load_draft", {"draft_id": draft_id, "db_path": tmp_db})
    assert loaded["success"] is True
    assert loaded["draft"]["name"] == "全链路测试草稿"
    assert len(loaded["draft"]["entries"]) == len(all_entries)
    print(f"  [OK] 加载成功: {loaded['draft']['name']} · {len(loaded['draft']['entries'])} 条分录")

    # ══ Phase 7: 导出 ═══════════════════════════════════════
    print("[7/7] voucher.export...")
    export_path = os.path.join(export_dir, "full_pipeline_test.xlsx")
    exported = _call("voucher.export", {
        "draft_id": draft_id,
        "period": "2026年测试期",
        "output_path": export_path,
        "source_files": ["cmb-03.pdf"],
        "db_path": tmp_db,
    })

    # 导出时 db 模块可能被重连——重置
    _db.close_db()
    _db._conn = None
    _db._db_path = tmp_db

    assert exported["success"] is True
    assert exported["file_path"] == export_path
    assert os.path.exists(export_path)
    size = os.path.getsize(export_path)
    assert size > 1000
    print(f"  [OK] Excel 导出: {size} 字节")

    # 审计日志
    conn = _db.get_db(db_path=tmp_db)
    _db.init_db(conn)
    logs = conn.execute("SELECT * FROM export_log ORDER BY id DESC LIMIT 1").fetchall()
    assert len(logs) >= 1
    log = dict(logs[0])
    assert log["draft_id"] == draft_id
    assert log["period"] == "2026年测试期"
    print(f"  [OK] 审计日志: 分录 {log['entry_count']}, 交易 {log['transaction_count']}")

    # 草稿状态变为 exported
    conn = _db.get_db(db_path=tmp_db)
    status = conn.execute("SELECT status FROM voucher_draft WHERE id = ?", (draft_id,)).fetchone()
    conn.close()
    assert status[0] == "exported"

    print(f"\n[PASS] 全链路通过: detect → parse → preview({len(vouchers)}张) → draft → export → audit_log")