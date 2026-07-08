"""pytest 全局配置 — OCR marker + 共享 fixtures + 全局 teardown。

共享 fixtures: tmp_db, tmp_db_path, make_txn, rpc_call, MINIMAL_RULES
全局 autouse: db 单例重置 + 4 个缓存 teardown
"""
import sqlite3
from datetime import date
from decimal import Decimal

import pytest


# ═══════════════════════════════════════════════════════════════════
# OCR marker
# ═══════════════════════════════════════════════════════════════════

@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    config.addinivalue_line("markers", "ocr: 需要 OCR（扫描件/回单解析），默认跳过")


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    """默认 -m 'not ocr'。显式 -m ocr 时只跑 OCR。"""
    if config.getoption("-m"):
        return
    skip_ocr = pytest.mark.skip(reason="默认跳过 OCR 测试，加 -m ocr 显式运行")
    for item in items:
        if "ocr" in item.keywords:
            item.add_marker(skip_ocr)


# ═══════════════════════════════════════════════════════════════════
# 全局 autouse fixtures — 测试隔离
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _reset_global_state():
    """每个测试前后重置所有模块级单例和缓存。"""
    from finance_agent_backend import db as _db

    # setup
    _db.close_db()
    _db._conn = None
    _db._db_path = None

    yield

    # teardown
    _db.close_db()
    _db._conn = None
    _db._db_path = None

    # 清理类级 / 模块级缓存
    from finance_agent_backend.repo.subject_history_repo import SubjectHistoryRepo
    SubjectHistoryRepo._cache.clear()

    import finance_agent_backend.subject_matcher as _sm
    _sm._subjects_cache = None
    _sm._default_rule_matcher = None

    import finance_agent_backend.account_registry as _ar
    _ar._entries_cache = None


# ═══════════════════════════════════════════════════════════════════
# 共享 fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_db(tmp_path):
    """临时 WAL 模式 SQLite 数据库，初始化 schema（pytest 自动清理）。"""
    from finance_agent_backend.db import init_db

    path = str(tmp_path / "test.db")
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    init_db(conn)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def tmp_db_path(tmp_path):
    """仅返回临时路径，不初始化 schema。"""
    return str(tmp_path / "test.db")


@pytest.fixture
def seeded_subjects_db(tmp_path):
    """隔离的、已回填 subjects.json 默认科目的 DB，并指向模块单例。

    供依赖默认科目表（如 50602xx 管理费用 → aux_category_name='公共部门'）的
    匹配测试使用，避免触碰真实 data.db 单例。
    """
    from finance_agent_backend import db as _db
    import finance_agent_backend.subject_matcher as _sm

    path = str(tmp_path / "seeded.db")
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    _db.init_db(conn)  # subjects 表为空 → 回填 subjects.json（含 aux_category_name）
    _db._conn = conn
    _db._db_path = path
    _sm._subjects_cache = None
    _sm._default_rule_matcher = None
    return path


# ═══════════════════════════════════════════════════════════════════
# 共享 helpers
# ═══════════════════════════════════════════════════════════════════

def make_txn(
    dt: str = "2024-01-15",
    desc: str = "测试交易",
    amount: float = 500.0,
    direction: str = "expense",
    counterparty: str = "",
    acct: str = "",
    ref: str = "",
):
    """构造测试用 Transaction。"""
    from finance_agent_backend.models import Transaction

    return Transaction(
        date=date.fromisoformat(dt),
        description=desc,
        amount=Decimal(str(amount)),
        direction=direction,
        counterparty=counterparty,
        account_number=acct,
        reference_number=ref,
    )


def rpc_call(method: str, params: dict | None = None) -> dict:
    """JSON-RPC 调用 shorthand。"""
    from finance_agent_backend.bridge import handle_request

    response = handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    })
    return response.get("result", response.get("error", {}))


# ═══════════════════════════════════════════════════════════════════
# 共享测试常量
# ═══════════════════════════════════════════════════════════════════

MINIMAL_RULES = {
    "version": 2,
    "expense": {
        "default_subject_code": "",
        "rules": [
            {"id": "rule_001", "priority": 1,
             "match": {"keywords": ["物业费", "物管费", "物业管理费"], "counterparty_pattern": "启胜"},
             "subject_code": "5060203", "subject_name": "管理费用_物业管理费"},
            {"id": "rule_002", "priority": 2,
             "match": {"keywords": ["服务费", "技术服务费"], "counterparty_pattern": "科技"},
             "subject_code": "403010113", "subject_name": "研发支出_技术服务费"},
            {"id": "rule_003", "priority": 3,
             "match": {"keywords": ["手续费", "汇款手续费"]},
             "subject_code": "1022120", "subject_name": "其他应收款_手续费"},
            {"id": "rule_004", "priority": 4,
             "match": {"keywords": ["物业"]},
             "subject_code": "5060299", "subject_name": "管理费用_其他物业"},
        ],
    },
    "income": {
        "default_subject_code": "",
        "rules": [
            {"id": "rule_101", "priority": 1,
             "match": {"keywords": ["收款", "回款", "货款"]},
             "subject_code": "10122", "subject_name": "应收账款"},
        ],
    },
}

SIMPLE_SUBJECT_MAPPING = MINIMAL_RULES
