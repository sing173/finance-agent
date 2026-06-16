"""Tests for account_registry — Phase 0 match_by_account() + Phase 1 CRUD."""
import sqlite3
import tempfile

import pytest

import sys

from finance_agent_backend.account_registry import AccountRegistry
from finance_agent_backend.models import AccountEntry
from finance_agent_backend.repo.account_mapping_repo import AccountMappingRepository
from finance_agent_backend import db as _db


def _make_db(entries: list[dict]) -> tuple[str, sqlite3.Connection]:
    """Create a temp SQLite DB with account_mapping table, return (path, conn)."""
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = tmp.name
    tmp.close()

    conn = _db.get_db(db_path=db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS account_mapping (
        id              TEXT PRIMARY KEY,
        matchType       TEXT NOT NULL,
        pattern         TEXT NOT NULL,
        bank            TEXT NOT NULL,
        bankCode        TEXT NOT NULL,
        subjectCode     TEXT NOT NULL,
        subjectName     TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS schema_version (
        version   INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )""")
    conn.execute("INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                 (5, "2024-01-01T00:00:00+00:00"))
    conn.commit()

    repo = AccountMappingRepository(conn)
    for entry_dict in entries:
        entry = AccountEntry(**entry_dict)
        repo.save(entry)

    conn.commit()
    return db_path, conn


def _make_repo(entries: list[dict]) -> tuple[str, AccountMappingRepository]:
    """Create a temp DB with entries, return (path, repo)."""
    db_path, conn = _make_db(entries)
    repo = AccountMappingRepository(conn)
    return db_path, repo


def _make_registry(entries: list[dict], subject_codes: list[str] | None = None) -> tuple[str, AccountRegistry]:
    """Create a temp DB with entries, return (path, registry)."""
    db_path, conn = _make_db(entries)
    repo = AccountMappingRepository(conn)
    subject_set = set(subject_codes) if subject_codes else None
    registry = AccountRegistry(repo, subject_codes=subject_set)
    return db_path, registry


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def test_load_v2_format():
    """加载 account_mapping 表 → 正确解析为 AccountEntry 列表。"""
    entries = [
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行基本户",
        },
        {
            "id": "acc_002", "matchType": "suffix", "pattern": "0288",
            "bank": "招商银行", "bankCode": "CMB",
            "subjectCode": "1000203", "subjectName": "银行存款-招商银行（0288）",
        },
    ]
    _, repo = _make_repo(entries)
    all_entries = repo.find_all()
    assert len(all_entries) == 2
    assert all_entries[0].id == "acc_001"
    assert all_entries[1].bankCode == "CMB"


# ---------------------------------------------------------------------------
# match_by_account — exact
# ---------------------------------------------------------------------------

def test_match_by_account_exact():
    """exact 匹配：完整账号等于 pattern → 命中。"""
    entries = [
        {
            "id": "acc_001", "matchType": "exact", "pattern": "6217001234567890",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行基本户",
        },
    ]
    _, repo = _make_repo(entries)
    reg = AccountRegistry(repo)
    result = reg.match_by_account("6217001234567890")
    assert result is not None
    assert result.bankCode == "ICBC"
    assert result.subjectCode == "1000201"


def test_match_by_account_exact_no_partial():
    """exact 匹配：部分匹配不命中，须完全相等。"""
    entries = [
        {
            "id": "acc_001", "matchType": "exact", "pattern": "6217001234567890",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行基本户",
        },
    ]
    _, repo = _make_repo(entries)
    reg = AccountRegistry(repo)
    result = reg.match_by_account("6217001234567890_extra")
    assert result is None


# ---------------------------------------------------------------------------
# match_by_account — suffix
# ---------------------------------------------------------------------------

def test_match_by_account_suffix():
    """suffix 匹配：账号以 pattern 结尾 → 命中。"""
    entries = [
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行基本户",
        },
    ]
    _, repo = _make_repo(entries)
    reg = AccountRegistry(repo)
    result = reg.match_by_account("12345678904363")
    assert result is not None
    assert result.bankCode == "ICBC"


def test_match_by_account_suffix_exact_priority():
    """优先级: exact 命中先于 suffix 命中。"""
    entries = [
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行",
        },
        {
            "id": "acc_002", "matchType": "exact", "pattern": "12344363",
            "bank": "招商银行", "bankCode": "CMB",
            "subjectCode": "1000203", "subjectName": "银行存款-招行",
        },
    ]
    _, repo = _make_repo(entries)
    reg = AccountRegistry(repo)
    result = reg.match_by_account("12344363")
    assert result is not None
    assert result.bankCode == "CMB"


# ---------------------------------------------------------------------------
# AccountMappingRepository — 数据访问层
# ---------------------------------------------------------------------------


def test_repository_load():
    """Repository.find_all() 从 DB 读取 AccountEntry 列表。"""
    _, repo = _make_repo([
        {"id": "acc_001", "matchType": "suffix", "pattern": "4363",
         "bank": "工商银行", "bankCode": "ICBC",
         "subjectCode": "1000201", "subjectName": "银行存款-工行"},
    ])
    entries = repo.find_all()
    assert len(entries) == 1
    assert entries[0].bankCode == "ICBC"


def test_repository_load_empty():
    """Repository.find_all() 空表返回空列表。"""
    _, repo = _make_repo([])
    entries = repo.find_all()
    assert entries == []


def test_repository_save():
    """Repository.save() 写入 DB，重新 find_all 内容一致。"""
    _, conn = _make_db([])
    repo = AccountMappingRepository(conn)
    entry = AccountEntry(id="acc_001", matchType="suffix", pattern="4363",
                         bank="工商银行", bankCode="ICBC",
                         subjectCode="1000201", subjectName="银行存款-工行")
    repo.save(entry)
    conn.commit()

    repo2 = AccountMappingRepository(conn)
    loaded = repo2.find_all()
    assert len(loaded) == 1
    assert loaded[0].subjectName == "银行存款-工行"


# ---------------------------------------------------------------------------
# Phase 1 CRUD — add()
# ---------------------------------------------------------------------------

def test_update_entry():
    """update() 按 id 更新条目。"""
    _, conn = _make_db([
        {"id": "acc_001", "matchType": "suffix", "pattern": "4363",
         "bank": "工商银行", "bankCode": "ICBC",
         "subjectCode": "1000201", "subjectName": "银行存款-工行"},
    ])
    repo = AccountMappingRepository(conn)
    reg = AccountRegistry(repo)
    reg.update(AccountEntry(
        id="acc_001", matchType="exact", pattern="4363",
        bank="工商银行", bankCode="ICBC",
        subjectCode="1000201", subjectName="银行存款-工行基本户",
    ))
    conn.commit()
    reg2 = AccountRegistry(repo)
    entries = reg2.list_all()
    assert len(entries) == 1
    assert entries[0].matchType == "exact"
    assert entries[0].subjectName == "银行存款-工行基本户"


def test_save_persistence():
    """save() 写入 DB，重新加载内容一致。"""
    _, conn = _make_db([
        {"id": "acc_001", "matchType": "suffix", "pattern": "4363",
         "bank": "工商银行", "bankCode": "ICBC",
         "subjectCode": "1000201", "subjectName": "银行存款-工行"},
    ])
    repo = AccountMappingRepository(conn)
    reg = AccountRegistry(repo)
    reg.update(AccountEntry(
        id="acc_001", matchType="exact", pattern="4363",
        bank="工商银行", bankCode="ICBC",
        subjectCode="1000201", subjectName="银行存款-工行基本户",
    ))
    conn.commit()

    repo2 = AccountMappingRepository(conn)
    loaded = repo2.find_all()
    assert len(loaded) == 1
    assert loaded[0].matchType == "exact"
    assert loaded[0].subjectName == "银行存款-工行基本户"


def test_delete_entry():
    """delete() 按 id 删除条目。"""
    _, conn = _make_db([
        {"id": "acc_001", "matchType": "suffix", "pattern": "4363",
         "bank": "工商银行", "bankCode": "ICBC",
         "subjectCode": "1000201", "subjectName": "银行存款-工行"},
        {"id": "acc_002", "matchType": "suffix", "pattern": "0288",
         "bank": "招商银行", "bankCode": "CMB",
         "subjectCode": "1000203", "subjectName": "银行存款-招行"},
    ])
    repo = AccountMappingRepository(conn)
    reg = AccountRegistry(repo)
    reg.delete("acc_001")
    conn.commit()
    reg2 = AccountRegistry(repo)
    entries = reg2.list_all()
    assert len(entries) == 1
    assert entries[0].id == "acc_002"


def test_delete_entry_not_found():
    """delete() id 不存在时静默不报错。"""
    _, repo = _make_repo([
        {"id": "acc_001", "matchType": "suffix", "pattern": "4363",
         "bank": "工商银行", "bankCode": "ICBC",
         "subjectCode": "1000201", "subjectName": "银行存款-工行"},
    ])
    reg = AccountRegistry(repo)
    reg.delete("acc_999")
    assert len(reg.list_all()) == 1


def test_update_entry_not_found():
    """update() id 不存在时抛 ValueError。"""
    _, repo = _make_repo([
        {"id": "acc_001", "matchType": "suffix", "pattern": "4363",
         "bank": "工商银行", "bankCode": "ICBC",
         "subjectCode": "1000201", "subjectName": "银行存款-工行"},
    ])
    reg = AccountRegistry(repo)
    with pytest.raises(ValueError, match="不存在"):
        reg.update(AccountEntry(
            id="acc_999", matchType="suffix", pattern="9999",
            bank="工商银行", bankCode="ICBC",
            subjectCode="1000201", subjectName="测试",
        ))


def test_add_entry_subjectcode_validation():
    """add() subjectCode 不存在于 subject_codes 时抛 ValueError。"""
    _, repo = _make_repo([])
    reg = AccountRegistry(repo, subject_codes={"1000201"})
    with pytest.raises(ValueError, match="subjectCode"):
        reg.add(AccountEntry(
            id="", matchType="suffix", pattern="4363",
            bank="工商银行", bankCode="ICBC",
            subjectCode="9999999", subjectName="不存在的科目",
        ))


def test_add_entry_bankcode_required():
    """add() bankCode 为空时抛 ValueError。"""
    _, repo = _make_repo([])
    reg = AccountRegistry(repo)
    with pytest.raises(ValueError, match="bankCode"):
        reg.add(AccountEntry(
            id="", matchType="suffix", pattern="4363",
            bank="工商银行", bankCode="",
            subjectCode="1000201", subjectName="银行存款-工行",
        ))


def test_add_entry():
    """add() 新增条目，自动生成 id，保存后可 list_all 查到。"""
    _, conn = _make_db([])
    repo = AccountMappingRepository(conn)
    reg = AccountRegistry(repo)
    reg.add(AccountEntry(
        id="", matchType="suffix", pattern="4363",
        bank="工商银行", bankCode="ICBC",
        subjectCode="1000201", subjectName="银行存款-工行",
    ))
    conn.commit()
    reg2 = AccountRegistry(repo)
    all_entries = reg2.list_all()
    assert len(all_entries) == 1
    assert all_entries[0].bankCode == "ICBC"
    assert all_entries[0].subjectCode == "1000201"
    assert all_entries[0].id != ""

def test_match_by_account_no_match():
    """无匹配 → 返回 None。"""
    entries = [
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行",
        },
    ]
    _, repo = _make_repo(entries)
    reg = AccountRegistry(repo)
    result = reg.match_by_account("0000000000")
    assert result is None


def test_match_masked_account():
    """脱敏账号（含*）仍能通过 suffix 匹配 — 过滤在 parser 层处理。"""
    entries = [
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行",
        },
    ]
    _, repo = _make_repo(entries)
    reg = AccountRegistry(repo)
    result = reg.match_by_account("6222****4363")
    assert result is not None
    assert result.bankCode == "ICBC"


def test_match_empty_account():
    """空账号不参与匹配。"""
    entries = [
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行",
        },
    ]
    _, repo = _make_repo(entries)
    reg = AccountRegistry(repo)
    assert reg.match_by_account("") is None


# ---------------------------------------------------------------------------
# Bridge JSON-RPC — account_registry.*
# ---------------------------------------------------------------------------

from finance_agent_backend.bridge import handle_request


@pytest.fixture
def temp_db():
    """Create a temporary SQLite DB with 2 entries, yield db_path."""
    entries = [
        {
            "id": "acc_001", "matchType": "suffix", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行基本户",
        },
        {
            "id": "acc_002", "matchType": "suffix", "pattern": "0288",
            "bank": "招商银行", "bankCode": "CMB",
            "subjectCode": "1000203", "subjectName": "银行存款-招商银行（0288）",
        },
    ]
    db_path, _conn = _make_db(entries)
    yield db_path


def _rpc(method, params=None, db_path=None):
    """Shorthand: send JSON-RPC request, return result dict."""
    p = dict(params or {})
    if db_path:
        p["db_path"] = db_path
    response = handle_request({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": p,
    })
    return response.get("result", {})


class TestBridgeAccountRegistry:
    """account_registry.list / match / add / update / delete via bridge RPC.

    所有 RPC 调用传 db_path 指向临时 DB，不操作真实数据库。
    """

    def test_list(self, temp_db):
        result = _rpc("account_registry.list", db_path=temp_db)
        assert "accounts" in result
        assert len(result["accounts"]) == 2
        assert result["accounts"][0]["bankCode"] == "ICBC"

    def test_match_found(self, temp_db):
        result = _rpc("account_registry.match",
                       {"accountNumber": "12345678904363"}, db_path=temp_db)
        assert result["success"] is True
        assert result["entry"]["bankCode"] == "ICBC"

    def test_match_not_found(self, temp_db):
        result = _rpc("account_registry.match",
                       {"accountNumber": "0000000000"}, db_path=temp_db)
        assert result["success"] is True
        assert result["entry"] is None

    def test_add(self, temp_db):
        result = _rpc("account_registry.add", {
            "matchType": "suffix", "pattern": "7931",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000205", "subjectName": "银行存款-工商银行（7931）",
        }, db_path=temp_db)
        assert result["success"] is True
        assert "id" in result
        assert result["entry"]["bankCode"] == "ICBC"

    def test_add_validation_bankcode(self, temp_db):
        result = _rpc("account_registry.add", {
            "matchType": "suffix", "pattern": "7931",
            "bank": "工商银行", "bankCode": "",
            "subjectCode": "1000205", "subjectName": "测试",
        }, db_path=temp_db)
        assert result.get("success") is False
        assert "bankCode" in result.get("error", "")

    def test_update(self, temp_db):
        result = _rpc("account_registry.update", {
            "id": "acc_001", "matchType": "exact", "pattern": "4363",
            "bank": "工商银行", "bankCode": "ICBC",
            "subjectCode": "1000201", "subjectName": "银行存款-工行基本户（已更新）",
        }, db_path=temp_db)
        assert result["success"] is True
        list_result = _rpc("account_registry.list", db_path=temp_db)
        updated = next(e for e in list_result["accounts"] if e["id"] == "acc_001")
        assert updated["subjectName"] == "银行存款-工行基本户（已更新）"

    def test_delete(self, temp_db):
        result = _rpc("account_registry.delete",
                       {"id": "acc_001"}, db_path=temp_db)
        assert result["success"] is True
        list_result = _rpc("account_registry.list", db_path=temp_db)
        assert len(list_result["accounts"]) == 1
        assert list_result["accounts"][0]["id"] == "acc_002"
