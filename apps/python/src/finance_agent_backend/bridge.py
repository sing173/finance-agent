#!/usr/bin/env python3
"""
finance-agent Python Bridge
JSON-RPC 2.0 服务器，通过 stdio 与 Electron 通信
同步版本 — 简单、可靠、兼容所有 Python 3.11+
"""

import json
import sys
import os
import uuid
import logging
import time
import traceback
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from pathlib import Path


def _setup_logging(log_dir: Path) -> logging.Logger:
    """配置日志：写入文件，10MB × 3 个文件轮转。"""
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("bridge")
    logger.setLevel(logging.INFO)

    handler = RotatingFileHandler(
        log_dir / 'bridge.log',
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8',
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
    ))
    logger.handlers.clear()
    logger.addHandler(handler)

    return logger


# 开发环境: logs/ 在 repo root；打包环境: %APPDATA%/FinanceAssistant/logs/
# 必须在所有 import 之前初始化，确保 import 阶段的错误也能写入日志
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if getattr(sys, 'frozen', False):
    _log = _setup_logging(Path(os.environ.get('APPDATA', Path.home().as_posix())) / 'FinanceAssistant' / 'logs')
else:
    _log = _setup_logging(Path(_project_root) / '..' / '..' / '..' / 'logs')

from finance_agent_backend.tools import excel_builder as _excel_builder
from finance_agent_backend.tools import subject_loader as _subject_loader
from finance_agent_backend.models import Transaction
from finance_agent_backend.paths import get_config_path, get_db_path

# 方法注册表
METHODS = {}  # type: dict

def register_method(name: str):
    """装饰器：注册 RPC 方法"""
    def decorator(func):
        METHODS[name] = func
        return func
    return decorator



@register_method("parse_pdf")
def handle_parse_pdf(params: dict) -> dict:
    """解析 PDF 银行流水或 ICBC CSV 对账流水"""
    file_path = params.get("filePath")
    bank = params.get("bank")
    doc_type = params.get("docType")

    if not file_path:
        return {"success": False, "error": "缺少 filePath 参数"}

    try:
        from finance_agent_backend import parser_router
        _log.info("parse_pdf 开始: %s", file_path)
        result = parser_router.route(file_path, bank=bank, doc_type=doc_type)
        _log.info("解析完成: %s", result)
        return result
    except Exception as e:
        _log.error("parse_pdf 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


@register_method("generate_excel")
def handle_generate_excel(params: dict) -> dict:
    """导出交易列表到 Excel"""
    transactions_data = params.get("transactions")
    output_path = params.get("output_path", "bank_statement.xlsx")

    if not transactions_data:
        return {"success": False, "error": "缺少 transactions 参数"}

    try:
        transactions = [Transaction.from_dict(t) for t in transactions_data]

        builder = _excel_builder.ExcelBuilder()
        excel_path = builder.build(transactions, output_path)
        return {"success": True, "excel_path": excel_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("parse_csv")
def handle_parse_csv(params: dict) -> dict:
    """[DEPRECATED] 使用 parse_pdf 代替。保留此方法仅做向后兼容。"""
    _log.warning("parse_csv 已废弃，请使用 parse_pdf")
    file_path = params.get("filePath")
    if not file_path:
        return {"success": False, "error": "缺少 filePath 参数"}
    return _parse_icbc_csv(file_path)

def _parse_icbc_csv(file_path: str) -> dict:
    """解析工行 CSV 对账流水，返回与 parse_pdf 兼容的结果 (lazy import)"""
    try:
        from finance_agent_backend.tools import icbc_csv_parser
        parser = icbc_csv_parser.ICBCCSVParser()
        result = parser.parse(file_path)
        return result.to_dict()
    except Exception as e:
        return {"success": False, "error": str(e)}





@register_method("import_subjects")
def handle_import_subjects(params: dict) -> dict:
    """从科目 xlsx 导入并保存为内置 subjects.json。

    params:
        xlsx_path (str, required): 科目 xlsx 文件路径

    返回:
        success: 是否成功
        count: 导入的科目数量
        path: 保存的 JSON 路径
    """
    xlsx_path = params.get("xlsx_path", "")
    if not xlsx_path:
        return {"success": False, "error": "缺少 xlsx_path 参数"}

    try:
        loader = _subject_loader.SubjectLoader()
        subjects = loader.load(xlsx_path)

        # 序列化为 JSON
        data = {}
        for code, subj in subjects.items():
            data[code] = {
                'code': subj.code,
                'name': subj.name,
                'category': subj.category,
                'direction': subj.direction,
                'aux_category': subj.aux_category,
                'is_cash': subj.is_cash,
                'enabled': subj.enabled,
                'full_name': subj.full_name,
            }

        subjects_json_path = get_config_path('subjects.json')
        with open(subjects_json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "count": len(subjects),
            "path": subjects_json_path,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("get_subjects_info")
def handle_get_subjects_info(params: dict) -> dict:
    """查询内置科目表信息（返回完整列表供 UI 使用）。"""
    subjects_path = get_config_path('subjects.json')
    if not os.path.exists(subjects_path):
        return {"success": True, "count": 0, "loaded": False, "subjects": []}
    try:
        with open(subjects_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        subjects = []
        for code, info in data.items():
            subjects.append({
                "code": code,
                "name": info.get('name', ''),
                "category": info.get('category', ''),
                "direction": info.get('direction', '借'),
                "is_cash": info.get('is_cash', False),
                "enabled": info.get('enabled', True),
                "full_name": info.get('full_name', info.get('name', '')),
            })
        return {"success": True, "count": len(subjects), "loaded": True, "subjects": subjects}
    except Exception as e:
        return {"success": False, "count": 0, "loaded": False, "error": str(e), "subjects": []}


@register_method("detect_supported_banks")
def handle_detect_supported_banks(params: dict) -> dict:
    """返回当前支持的银行列表（code + 中文名，供 UI 下拉选择）。"""
    from finance_agent_backend import parser_router
    banks = [
        {"code": code, "name": name}
        for code, name in parser_router.BANK_CODE_TO_NAME.items()
    ]
    return {"success": True, "banks": banks}


@register_method("detect_banks")
def handle_detect_banks(params: dict) -> dict:
    """批量检测文件银行类型。CSV/Excel 固定返回，PDF 走三级路由。"""
    from finance_agent_backend import parser_router
    file_paths = params.get("filePaths", [])
    results = []
    for fp in file_paths:
        if not os.path.exists(fp):
            results.append({
                "filePath": fp,
                "bank": "未知银行",
                "bankCode": "UNKNOWN",
                "docType": "unknown",
                "status": "failed",
            })
            continue

        ext = os.path.splitext(fp)[1].lower()
        try:
            # CSV / Excel: fixed mapping, no detection needed
            if ext == '.csv':
                results.append({
                    "filePath": fp, "bank": "工商银行", "bankCode": "ICBC",
                    "docType": "流水", "status": "ok",
                })
                continue
            if ext == '.xlsx':
                results.append({
                    "filePath": fp, "bank": "招商银行", "bankCode": "CMB",
                    "docType": "流水", "status": "ok",
                })
                continue

            # PDF: three-level routing detection (returns dict)
            info = parser_router.detect_bank_from_pdf(fp)
            results.append({
                "filePath": fp,
                "bank": info["bank"],
                "bankCode": info["bankCode"],
                "docType": info["docType"],
                "status": "ok",
            })
        except Exception:
            results.append({
                "filePath": fp,
                "bank": "未知银行",
                "bankCode": "UNKNOWN",
                "docType": "unknown",
                "status": "failed",
            })
    return {"success": True, "results": results}


# ---------------------------------------------------------------------------
# Account Registry CRUD (Issue #29: FR-1)
# ---------------------------------------------------------------------------


def _open_account_registry(with_subject_codes: bool = False):
    """工厂函数：获取 AccountRegistry + AccountMappingRepository 对。

    消除 5 个 handler 中的重复样板：import、repo.load()、subject_codes 加载。
    """
    from finance_agent_backend.account_registry import (
        AccountMappingRepository,
        AccountRegistry,
        _default_config_path,
    )
    repo = AccountMappingRepository(_default_config_path())
    entries = repo.load()
    subject_codes = _get_subject_codes() if with_subject_codes else None
    registry = AccountRegistry(entries, subject_codes=subject_codes)
    return registry, repo


def _get_subject_codes() -> set:
    """加载 subjects.json 的科目代码集合，用于 add() 校验。"""
    try:
        import json
        subjects_path = get_config_path('subjects.json')

        if not os.path.exists(subjects_path):
            return set()

        with open(subjects_path, "r", encoding="utf-8") as f:
            subjects = json.load(f)
        return set(subjects.keys())
    except Exception:
        return set()


def _serialize_account_entry(e) -> dict:
    """AccountEntry → JSON-RPC 字典（5 个 handler 共享）。"""
    return {
        "id": e.id,
        "matchType": e.matchType,
        "pattern": e.pattern,
        "bank": e.bank,
        "bankCode": e.bankCode,
        "subjectCode": e.subjectCode,
        "subjectName": e.subjectName,
    }


@register_method("account_registry.list")
def handle_account_registry_list(params: dict) -> dict:
    """列出所有账号-科目映射。"""
    try:
        registry, _ = _open_account_registry()
        return {
            "success": True,
            "accounts": [_serialize_account_entry(e) for e in registry.list_all()],
        }
    except Exception as e:
        _log.error("account_registry.list 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


@register_method("account_registry.match")
def handle_account_registry_match(params: dict) -> dict:
    """根据账号匹配映射条目。"""
    account_number = params.get("accountNumber")
    if not account_number:
        return {"success": False, "error": "缺少 accountNumber 参数"}

    try:
        registry, _ = _open_account_registry()
        entry = registry.match_by_account(account_number)
        return {
            "success": True,
            "entry": _serialize_account_entry(entry) if entry else None,
        }
    except Exception as e:
        _log.error("account_registry.match 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


@register_method("account_registry.add")
def handle_account_registry_add(params: dict) -> dict:
    """新增账号-科目映射（校验 bankCode 必填 + subjectCode 存在性）。"""
    try:
        from finance_agent_backend.account_registry import AccountEntry

        bankCode = params.get("bankCode", "")
        if not bankCode:
            return {"success": False, "error": "bankCode 不能为空"}

        entry = AccountEntry(
            id="",
            matchType=params.get("matchType", "suffix"),
            pattern=params.get("pattern", ""),
            bank=params.get("bank", ""),
            bankCode=bankCode,
            subjectCode=params.get("subjectCode", ""),
            subjectName=params.get("subjectName", ""),
        )

        registry, repo = _open_account_registry(with_subject_codes=True)
        registry.add(entry)
        repo.save(registry.list_all(), "10002")

        return {
            "success": True,
            "id": entry.id,
            "entry": _serialize_account_entry(entry),
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        _log.error("account_registry.add 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


@register_method("account_registry.update")
def handle_account_registry_update(params: dict) -> dict:
    """更新已有账号-科目映射。"""
    entry_id = params.get("id")
    if not entry_id:
        return {"success": False, "error": "缺少 id 参数"}

    try:
        from finance_agent_backend.account_registry import AccountEntry

        entry = AccountEntry(
            id=entry_id,
            matchType=params.get("matchType", "suffix"),
            pattern=params.get("pattern", ""),
            bank=params.get("bank", ""),
            bankCode=params.get("bankCode", ""),
            subjectCode=params.get("subjectCode", ""),
            subjectName=params.get("subjectName", ""),
        )

        registry, repo = _open_account_registry(with_subject_codes=True)
        registry.update(entry)
        repo.save(registry.list_all(), "10002")

        return {"success": True, "entry": _serialize_account_entry(entry)}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        _log.error("account_registry.update 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


@register_method("account_registry.delete")
def handle_account_registry_delete(params: dict) -> dict:
    """删除账号-科目映射。"""
    entry_id = params.get("id")
    if not entry_id:
        return {"success": False, "error": "缺少 id 参数"}

    try:
        registry, repo = _open_account_registry()
        registry.delete(entry_id)
        repo.save(registry.list_all(), "10002")

        return {"success": True}
    except Exception as e:
        _log.error("account_registry.delete 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


@register_method("db.health")
def handle_db_health(params: dict) -> dict:
    """验证数据库状态，返回所有表名。"""
    try:
        from finance_agent_backend import db as _db
        conn = _db.get_db()
        _db.init_db(conn)
        tables = [
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        return {"status": "ok", "tables": tables}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@register_method("voucher.preview")
def handle_voucher_preview(params: dict) -> dict:
    """交易列表 → 凭证预览（含科目匹配 + 同类合并）。"""
    try:
        from finance_agent_backend.voucher_composer import VoucherComposer
        from finance_agent_backend.models import Transaction
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo
        from finance_agent_backend import db as _db

        transactions_data = params.get("transactions", [])
        subject_mapping = params.get("subject_mapping")
        db_path = params.get("db_path") or get_db_path()

        if not transactions_data:
            return {"success": False, "error": "缺少 transactions 参数"}

        transactions = [Transaction.from_dict(t) for t in transactions_data]

        # 加载账号注册表供银行科目匹配
        from finance_agent_backend.account_registry import AccountMappingRepository, AccountRegistry, _default_config_path
        account_registry = None
        try:
            acc_repo = AccountMappingRepository(_default_config_path())
            account_registry = AccountRegistry(acc_repo.load())
        except Exception:
            pass

        repo = SubjectHistoryRepo(db_path)
        composer = VoucherComposer(repo=repo)
        vouchers = composer.compose(transactions, subject_mapping, account_registry)

        warnings = []
        for v in vouchers:
            unmatched = [e for e in v["entries"] if e.get("match_source") == "unmatched" and e.get("direction") != "bank"]
            if unmatched:
                warnings.append(f"凭证#{v['voucher_no']}: {len(unmatched)} 条分录科目未匹配")

        return {
            "success": True,
            "vouchers": vouchers,
            "warnings": warnings,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("voucher.save_draft")
def handle_voucher_save_draft(params: dict) -> dict:
    """保存凭证草稿到 SQLite。"""
    try:
        from finance_agent_backend import db as _db

        name = params.get("name", "")
        period = params.get("period", "")
        entries = params.get("entries", [])

        if not entries:
            return {"success": False, "error": "缺少 entries 参数"}

        # 测试时可通过 db_path 参数覆盖
        db_path = params.get("db_path")
        conn = _db.get_db(db_path=db_path)
        _db.init_db(conn)

        draft_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            "INSERT INTO voucher_draft (id, name, period, status, created_at, updated_at) VALUES (?, ?, ?, 'draft', ?, ?)",
            (draft_id, name, period, now, now),
        )

        for e in entries:
            conn.execute(
                """INSERT INTO voucher_draft_entry
                   (draft_id, entry_seq, voucher_no, date, summary, subject_code, subject_name,
                    debit_amount, credit_amount, direction, counterparty, match_source,
                    original_summary, original_amount, is_manual,
                    aux_category, aux_category_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    draft_id,
                    e.get("entry_seq", 1),
                    e.get("voucher_no", 1),
                    e.get("date", ""),
                    e.get("summary", ""),
                    e.get("subject_code", ""),
                    e.get("subject_name", ""),
                    e.get("debit_amount"),
                    e.get("credit_amount"),
                    e.get("direction", ""),
                    e.get("counterparty", ""),
                    e.get("match_source", "unmatched"),
                    e.get("original_summary", ""),
                    e.get("original_amount", 0),
                    1 if e.get("is_manual") else 0,
                    e.get("aux_category", ""),
                    e.get("aux_category_name", ""),
                ),
            )

        conn.commit()
        return {"success": True, "draft_id": draft_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("voucher.load_draft")
def handle_voucher_load_draft(params: dict) -> dict:
    """加载凭证草稿。"""
    try:
        from finance_agent_backend import db as _db

        draft_id = params.get("draft_id")
        if not draft_id:
            return {"success": False, "error": "缺少 draft_id 参数"}

        db_path = params.get("db_path")
        conn = _db.get_db(db_path=db_path)
        _db.init_db(conn)

        draft = conn.execute(
            "SELECT id, name, period, status, created_at, updated_at FROM voucher_draft WHERE id = ?",
            (draft_id,),
        ).fetchone()

        if not draft:
            return {"success": False, "error": f"草稿 {draft_id} 不存在"}

        entry_rows = conn.execute(
            """SELECT entry_seq, voucher_no, date, summary, subject_code, subject_name,
                      debit_amount, credit_amount, direction, counterparty, match_source,
                      original_summary, original_amount, is_manual,
                      aux_category, aux_category_name
               FROM voucher_draft_entry WHERE draft_id = ? ORDER BY voucher_no, entry_seq""",
            (draft_id,),
        ).fetchall()

        return {
            "success": True,
            "draft": {
                "id": draft["id"],
                "name": draft["name"],
                "period": draft["period"],
                "status": draft["status"],
                "created_at": draft["created_at"],
                "updated_at": draft["updated_at"],
                "entries": [dict(r) for r in entry_rows],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("voucher.list_drafts")
def handle_voucher_list_drafts(params: dict) -> dict:
    """列出所有草稿。"""
    try:
        from finance_agent_backend import db as _db

        db_path = params.get("db_path")
        conn = _db.get_db(db_path=db_path)
        _db.init_db(conn)

        rows = conn.execute(
            """SELECT d.id, d.name, d.period, d.status, d.created_at, d.updated_at,
                      COUNT(e.id) as entry_count
               FROM voucher_draft d
               LEFT JOIN voucher_draft_entry e ON e.draft_id = d.id
               GROUP BY d.id ORDER BY d.updated_at DESC"""
        ).fetchall()

        return {"success": True, "drafts": [dict(r) for r in rows]}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("voucher.delete_draft")
def handle_voucher_delete_draft(params: dict) -> dict:
    """删除草稿（CASCADE 删除关联分录）。"""
    try:
        from finance_agent_backend import db as _db

        draft_id = params.get("draft_id")
        if not draft_id:
            return {"success": False, "error": "缺少 draft_id 参数"}

        db_path = params.get("db_path")
        conn = _db.get_db(db_path=db_path)
        _db.init_db(conn)

        conn.execute("DELETE FROM voucher_draft WHERE id = ?", (draft_id,))
        conn.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("voucher.export")
def handle_voucher_export(params: dict) -> dict:
    """确认导出：生成 Excel + 写入审计日志 + 写入历史库。"""
    try:
        import json
        from finance_agent_backend import db as _db
        from finance_agent_backend.tools import excel_builder
        from finance_agent_backend.subject_history_repo import SubjectHistoryRepo

        draft_id = params.get("draft_id")
        output_path = params.get("output_path", "voucher.xlsx")
        period = params.get("period", "")
        source_files = params.get("source_files", [])
        if not draft_id:
            return {"success": False, "error": "缺少 draft_id 参数"}

        db_path = params.get("db_path")
        conn = _db.get_db(db_path=db_path)
        _db.init_db(conn)

        # Load draft entries
        entry_rows = conn.execute(
            """SELECT * FROM voucher_draft_entry WHERE draft_id = ? ORDER BY voucher_no, entry_seq""",
            (draft_id,),
        ).fetchall()

        if not entry_rows:
            return {"success": False, "error": "草稿无分录数据"}

        # 直接从 DB 分录导出 Excel，与预览完全一致
        entry_dicts = []
        for r in entry_rows:
            entry_dicts.append({
                "entry_seq": r["entry_seq"],
                "voucher_no": r["voucher_no"],
                "date": r["date"],
                "summary": r["summary"],
                "subject_code": r["subject_code"],
                "subject_name": r["subject_name"],
                "debit_amount": r["debit_amount"],
                "credit_amount": r["credit_amount"],
                "direction": r["direction"],
                "counterparty": r["counterparty"],
                "original_amount": r["original_amount"],
                "aux_category": r["aux_category"],
                "aux_category_name": r["aux_category_name"],
            })

        txns_count = sum(1 for r in entry_rows if r["direction"] != "bank")
        voucher_count = len({r["voucher_no"] for r in entry_rows})

        if entry_dicts:
            builder = excel_builder.ExcelBuilder()
            builder.build_voucher_from_entries(
                entries=entry_dicts,
                output_path=output_path,
                period=period,
            )

        # Stats
        sources = {}
        for r in entry_rows:
            src = r["match_source"] or "unmatched"
            sources[src] = sources.get(src, 0) + 1

        # Write export_log
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO export_log (exported_at, period, file_path, voucher_count, entry_count,
                       transaction_count, source_files, match_stats, draft_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (now, period, output_path,
             voucher_count, len(entry_rows), txns_count,
             json.dumps(source_files), json.dumps(sources), draft_id),
        )
        conn.commit()

        # Write subject_history (manual entries only)
        repo = SubjectHistoryRepo(db_path or get_db_path())
        for r in entry_rows:
            if r["is_manual"]:
                repo.insert(
                    summary=r["original_summary"] or r["summary"],
                    direction=r["direction"],
                    subject_code=r["subject_code"],
                    subject_name=r["subject_name"] or "",
                    counterparty=r["counterparty"] or "",
                    voucher_id=draft_id,
                    conn=conn,
                )

        # Mark draft as exported
        conn.execute(
            "UPDATE voucher_draft SET status = 'exported', updated_at = ? WHERE id = ?",
            (now, draft_id),
        )
        conn.commit()

        return {
            "success": True,
            "file_path": output_path,
            "voucher_count": voucher_count,
            "entry_count": len(entry_rows),
            "transaction_count": txns_count,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def handle_request(request: dict) -> dict:
    method = request.get("method")
    params = request.get("params", {})
    req_id = request.get("id")

    if method in METHODS:
        try:
            result = METHODS[method](params)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(e)},
            }
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"},
        }


def main():
    """主循环：逐行读取 stdin，解析 JSON-RPC，写入 stdout"""
    # 强制 UTF-8：PyInstaller 打包后 PYTHONIOENCODING 可能不被 C bootloader 遵循
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")

    _log.info("Bridge 启动: Python %s", sys.version.split()[0])
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
        else:
            response = handle_request(request)

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

