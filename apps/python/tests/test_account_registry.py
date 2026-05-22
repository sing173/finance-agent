"""Tests for account_registry — Phase 0 match_by_account() + Phase 1 CRUD."""
import json
import os
import tempfile

import pytest

# Ensure the package is importable
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from finance_agent_backend.account_registry import AccountRegistry, AccountMappingRepository
from finance_agent_backend.models import AccountEntry


def _make_v2_json(entries: list[dict], default_code: str = "10002") -> str:
    """Write a temporary v2 account_mapping.json and return its path."""
    data = {
        "accounts": entries,
        "defaultBankSubjectCode": default_code,
    }
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(data, tmp, ensure_ascii=False)
    tmp.close()
    return tmp.name


def _make_repo(entries: list[dict], default_code: str = "10002") -> tuple[str, AccountMappingRepository]:
    """Write a temp account_mapping.json, return (path, repo)."""
    path = _make_v2_json(entries, default_code)
    repo = AccountMappingRepository(path)
    return path, repo


def _make_registry(entries: list[dict], subject_codes: list[str] | None = None) -> tuple[str, AccountRegistry]:
    """Write a temp account_mapping.json, load via Repository, return (path, registry)."""
    path = _make_v2_json(entries)
    repo = AccountMappingRepository(path)
    subject_set = set(subject_codes) if subject_codes else None
    registry = AccountRegistry(repo.load(), subject_codes=subject_set)
    return path, registry


def _make_registry_from_file(path: str, subjects_path: str | None = None) -> AccountRegistry:
    """Load registry from an existing file path."""
    repo = AccountMappingRepository(path)
    subject_set = None
    if subjects_path:
        with open(subjects_path, 'r', encoding='utf-8') as f:
            import json as _json
            subject_set = set(_json.load(f).keys())
    return AccountRegistry(repo.load(), subject_codes=subject_set)


def _make_subjects_json(codes: list[str]) -> str:
    """Write a minimal subjects.json with given codes and return path."""
    data = {c: {"code": c, "name": f"科目{c}", "category": "测试", "direction": "借", "aux_category": "", "is_cash": False, "enabled": True, "full_name": f"科目{c}"} for c in codes}
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(data, tmp, ensure_ascii=False)
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def test_load_v2_format():
    """加载 v2 account_mapping.json → 正确解析为 AccountEntry 列表。"""
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
    all_entries = repo.load()
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
    reg = AccountRegistry(repo.load())
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
    reg = AccountRegistry(repo.load())
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
    reg = AccountRegistry(repo.load())
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
    reg = AccountRegistry(repo.load())
    # "12344363" matches exact pattern AND suffix 4363 — exact wins
    result = reg.match_by_account("12344363")
    assert result is not None
    assert result.bankCode == "CMB"


# ---------------------------------------------------------------------------
# AccountMappingRepository — 数据访问层
# ---------------------------------------------------------------------------

from finance_agent_backend.account_registry import AccountMappingRepository


def test_repository_load():
    """Repository.load() 从 JSON 文件读取 AccountEntry 列表。"""
    path = _make_v2_json([
        {"id": "acc_001", "matchType": "suffix", "pattern": "4363",
         "bank": "工商银行", "bankCode": "ICBC",
         "subjectCode": "1000201", "subjectName": "银行存款-工行"},
    ])
    try:
        repo = AccountMappingRepository(path)
        entries = repo.load()
        assert len(entries) == 1
        assert entries[0].bankCode == "ICBC"
    finally:
        os.unlink(path)


def test_repository_load_empty():
    """Repository.load() 空文件返回空列表。"""
    path = _make_v2_json([])
    try:
        repo = AccountMappingRepository(path)
        entries = repo.load()
        assert entries == []
    finally:
        os.unlink(path)


def test_repository_save():
    """Repository.save() 写入 JSON，重新 load 内容一致。"""
    path = _make_v2_json([])
    try:
        repo = AccountMappingRepository(path)
        entries = [
            AccountEntry(id="acc_001", matchType="suffix", pattern="4363",
                         bank="工商银行", bankCode="ICBC",
                         subjectCode="1000201", subjectName="银行存款-工行"),
        ]
        repo.save(entries, "10002")

        repo2 = AccountMappingRepository(path)
        loaded = repo2.load()
        assert len(loaded) == 1
        assert loaded[0].subjectName == "银行存款-工行"
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Phase 1 CRUD — add()
# ---------------------------------------------------------------------------

def test_update_entry():
    """update() 按 id 更新条目。"""
    path = _make_v2_json([
        {"id": "acc_001", "matchType": "suffix", "pattern": "4363",
         "bank": "工商银行", "bankCode": "ICBC",
         "subjectCode": "1000201", "subjectName": "银行存款-工行"},
    ])
    try:
        repo = AccountMappingRepository(path)
        reg = AccountRegistry(repo.load())
        reg.update(AccountEntry(
            id="acc_001", matchType="exact", pattern="4363",
            bank="工商银行", bankCode="ICBC",
            subjectCode="1000201", subjectName="银行存款-工行基本户",
        ))
        repo.save(reg.list_all(), "10002")
        reg2 = AccountRegistry(repo.load())
        entries = reg2.list_all()
        assert len(entries) == 1
        assert entries[0].matchType == "exact"
        assert entries[0].subjectName == "银行存款-工行基本户"
    finally:
        os.unlink(path)


def test_save_persistence():
    """save() 写入 JSON，重新加载内容一致。"""
    path = _make_v2_json([
        {"id": "acc_001", "matchType": "suffix", "pattern": "4363",
         "bank": "工商银行", "bankCode": "ICBC",
         "subjectCode": "1000201", "subjectName": "银行存款-工行"},
    ])
    try:
        repo = AccountMappingRepository(path)
        reg = AccountRegistry(repo.load())
        # 修改一条
        reg.update(AccountEntry(
            id="acc_001", matchType="exact", pattern="4363",
            bank="工商银行", bankCode="ICBC",
            subjectCode="1000201", subjectName="银行存款-工行基本户",
        ))
        repo.save(reg.list_all(), "10002")

        # 重新加载验证
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        assert len(raw['accounts']) == 1
        assert raw['accounts'][0]['matchType'] == 'exact'
        assert raw['accounts'][0]['subjectName'] == "银行存款-工行基本户"
        assert raw['defaultBankSubjectCode'] == "10002"
    finally:
        os.unlink(path)


def test_delete_entry():
    """delete() 按 id 删除条目。"""
    path = _make_v2_json([
        {"id": "acc_001", "matchType": "suffix", "pattern": "4363",
         "bank": "工商银行", "bankCode": "ICBC",
         "subjectCode": "1000201", "subjectName": "银行存款-工行"},
        {"id": "acc_002", "matchType": "suffix", "pattern": "0288",
         "bank": "招商银行", "bankCode": "CMB",
         "subjectCode": "1000203", "subjectName": "银行存款-招行"},
    ])
    try:
        repo = AccountMappingRepository(path)
        reg = AccountRegistry(repo.load())
        reg.delete("acc_001")
        repo.save(reg.list_all(), "10002")
        reg2 = AccountRegistry(repo.load())
        entries = reg2.list_all()
        assert len(entries) == 1
        assert entries[0].id == "acc_002"
    finally:
        os.unlink(path)


def test_delete_entry_not_found():
    """delete() id 不存在时静默不报错。"""
    path = _make_v2_json([
        {"id": "acc_001", "matchType": "suffix", "pattern": "4363",
         "bank": "工商银行", "bankCode": "ICBC",
         "subjectCode": "1000201", "subjectName": "银行存款-工行"},
    ])
    try:
        repo = AccountMappingRepository(path)
        reg = AccountRegistry(repo.load())
        reg.delete("acc_999")  # 不报错
        assert len(reg.list_all()) == 1
    finally:
        os.unlink(path)


def test_update_entry_not_found():
    """update() id 不存在时抛 ValueError。"""
    path = _make_v2_json([
        {"id": "acc_001", "matchType": "suffix", "pattern": "4363",
         "bank": "工商银行", "bankCode": "ICBC",
         "subjectCode": "1000201", "subjectName": "银行存款-工行"},
    ])
    try:
        repo = AccountMappingRepository(path)
        reg = AccountRegistry(repo.load())
        with pytest.raises(ValueError, match="不存在"):
            reg.update(AccountEntry(
                id="acc_999", matchType="suffix", pattern="9999",
                bank="工商银行", bankCode="ICBC",
                subjectCode="1000201", subjectName="测试",
            ))
    finally:
        os.unlink(path)


def test_add_entry_subjectcode_validation():
    """add() subjectCode 不存在于 subjects.json 时抛 ValueError。"""
    path = _make_v2_json([])
    subjects_path = _make_subjects_json(["1000201"])  # 只含 1000201
    try:
        repo = AccountMappingRepository(path)
        import json as _json
        with open(subjects_path, "r", encoding="utf-8") as _f:
            _subject_set = set(_json.load(_f).keys())
        reg = AccountRegistry(repo.load(), subject_codes=_subject_set)
        with pytest.raises(ValueError, match="subjectCode"):
            reg.add(AccountEntry(
                id="", matchType="suffix", pattern="4363",
                bank="工商银行", bankCode="ICBC",
                subjectCode="9999999", subjectName="不存在的科目",
            ))
    finally:
        os.unlink(path)
        os.unlink(subjects_path)


def test_add_entry_bankcode_required():
    """add() bankCode 为空时抛 ValueError。"""
    path = _make_v2_json([])
    try:
        repo = AccountMappingRepository(path)
        reg = AccountRegistry(repo.load())
        with pytest.raises(ValueError, match="bankCode"):
            reg.add(AccountEntry(
                id="", matchType="suffix", pattern="4363",
                bank="工商银行", bankCode="",
                subjectCode="1000201", subjectName="银行存款-工行",
            ))
    finally:
        os.unlink(path)


def test_add_entry():
    """add() bankCode 为空时抛 ValueError。"""
    path = _make_v2_json([])
    try:
        repo = AccountMappingRepository(path)
        reg = AccountRegistry(repo.load())
        with pytest.raises(ValueError, match="bankCode"):
            reg.add(AccountEntry(
                id="", matchType="suffix", pattern="4363",
                bank="工商银行", bankCode="",
                subjectCode="1000201", subjectName="银行存款-工行",
            ))
    finally:
        os.unlink(path)
    """add() 新增条目，自动生成 id，保存后可 list_all 查到。"""
    path = _make_v2_json([])
    subjects_path = _make_subjects_json(["1000201"])
    try:
        repo = AccountMappingRepository(path)
        reg = AccountRegistry(repo.load())
        reg.add(AccountEntry(
            id="", matchType="suffix", pattern="4363",
            bank="工商银行", bankCode="ICBC",
            subjectCode="1000201", subjectName="银行存款-工行",
        ))
        repo.save(reg.list_all(), "10002")
        # 重新加载验证持久化
        reg2 = AccountRegistry(repo.load())
        all_entries = reg2.list_all()
        assert len(all_entries) == 1
        assert all_entries[0].bankCode == "ICBC"
        assert all_entries[0].subjectCode == "1000201"
        assert all_entries[0].id != ""  # id 自动生成
    finally:
        os.unlink(path)
        os.unlink(subjects_path)

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
    reg = AccountRegistry(repo.load())
    result = reg.match_by_account("0000000000")
    assert result is None