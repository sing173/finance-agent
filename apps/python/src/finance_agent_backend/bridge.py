#!/usr/bin/env python3
"""
finance-agent Python Bridge
JSON-RPC 2.0 服务器，通过 stdio 与 Electron 通信
同步版本 — 简单、可靠、兼容所有 Python 3.11+

架构：本文件只做 JSON-RPC 解码/编码/错误包装，业务编排委托给 services/ 层。
"""

import json
import sys
import os
import logging
import traceback
from logging.handlers import RotatingFileHandler
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


_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if getattr(sys, 'frozen', False):
    _log = _setup_logging(Path(os.environ.get('APPDATA', Path.home().as_posix())) / 'FinanceAssistant' / 'logs')
else:
    _log = _setup_logging(Path(_project_root) / '..' / '..' / '..' / 'logs')

# 方法注册表
METHODS = {}  # type: dict


def register_method(name: str):
    """装饰器：注册 RPC 方法"""
    def decorator(func):
        METHODS[name] = func
        return func
    return decorator


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

@register_method("parse_pdf")
def handle_parse_pdf(params: dict) -> dict:
    file_path = params.get("filePath")
    if not file_path:
        return {"success": False, "error": "缺少 filePath 参数"}
    try:
        from finance_agent_backend.services import ParseService
        _log.info("parse_pdf 开始: %s", file_path)
        result = ParseService().parse(file_path, bank=params.get("bank"), doc_type=params.get("docType"))
        _log.info("解析完成: %s", result)
        return result
    except Exception as e:
        _log.error("parse_pdf 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


@register_method("generate_excel")
def handle_generate_excel(params: dict) -> dict:
    transactions_data = params.get("transactions")
    output_path = params.get("output_path", "bank_statement.xlsx")
    if not transactions_data:
        return {"success": False, "error": "缺少 transactions 参数"}
    try:
        from finance_agent_backend.services import ParseService
        excel_path = ParseService().generate_excel(transactions_data, output_path)
        return {"success": True, "excel_path": excel_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("detect_banks")
def handle_detect_banks(params: dict) -> dict:
    try:
        from finance_agent_backend.services import ParseService
        file_paths = params.get("filePaths", [])
        results = ParseService().detect_banks(file_paths)
        return {"success": True, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("detect_supported_banks")
def handle_detect_supported_banks(params: dict) -> dict:
    from finance_agent_backend.services import ParseService
    banks = ParseService().detect_supported_banks()
    return {"success": True, "banks": banks}


# ---------------------------------------------------------------------------
# 科目
# ---------------------------------------------------------------------------

@register_method("import_subjects")
def handle_import_subjects(params: dict) -> dict:
    xlsx_path = params.get("xlsx_path", "")
    if not xlsx_path:
        return {"success": False, "error": "缺少 xlsx_path 参数"}
    try:
        from finance_agent_backend.services import SubjectService
        return SubjectService().import_from_xlsx(xlsx_path)
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("get_subjects_info")
def handle_get_subjects_info(params: dict) -> dict:
    try:
        from finance_agent_backend.services import SubjectService
        return SubjectService().get_info()
    except Exception as e:
        return {"success": False, "count": 0, "loaded": False, "error": str(e), "subjects": []}


# ---------------------------------------------------------------------------
# 账号映射
# ---------------------------------------------------------------------------

@register_method("account_registry.list")
def handle_account_registry_list(params: dict) -> dict:
    try:
        from finance_agent_backend.services import AccountRegistryService
        return AccountRegistryService().list_all()
    except Exception as e:
        _log.error("account_registry.list 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


@register_method("account_registry.match")
def handle_account_registry_match(params: dict) -> dict:
    account_number = params.get("accountNumber")
    if not account_number:
        return {"success": False, "error": "缺少 accountNumber 参数"}
    try:
        from finance_agent_backend.services import AccountRegistryService
        return AccountRegistryService().match(account_number)
    except Exception as e:
        _log.error("account_registry.match 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


@register_method("account_registry.add")
def handle_account_registry_add(params: dict) -> dict:
    try:
        from finance_agent_backend.account_registry import AccountEntry
        from finance_agent_backend.services import AccountRegistryService

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
        return AccountRegistryService().add(entry)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        _log.error("account_registry.add 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


@register_method("account_registry.update")
def handle_account_registry_update(params: dict) -> dict:
    entry_id = params.get("id")
    if not entry_id:
        return {"success": False, "error": "缺少 id 参数"}
    try:
        from finance_agent_backend.account_registry import AccountEntry
        from finance_agent_backend.services import AccountRegistryService

        entry = AccountEntry(
            id=entry_id,
            matchType=params.get("matchType", "suffix"),
            pattern=params.get("pattern", ""),
            bank=params.get("bank", ""),
            bankCode=params.get("bankCode", ""),
            subjectCode=params.get("subjectCode", ""),
            subjectName=params.get("subjectName", ""),
        )
        return AccountRegistryService().update(entry)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        _log.error("account_registry.update 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


@register_method("account_registry.delete")
def handle_account_registry_delete(params: dict) -> dict:
    entry_id = params.get("id")
    if not entry_id:
        return {"success": False, "error": "缺少 id 参数"}
    try:
        from finance_agent_backend.services import AccountRegistryService
        return AccountRegistryService().delete(entry_id)
    except Exception as e:
        _log.error("account_registry.delete 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 凭证
# ---------------------------------------------------------------------------

@register_method("voucher.preview")
def handle_voucher_preview(params: dict) -> dict:
    try:
        from finance_agent_backend.services import VoucherService
        transactions = params.get("transactions", [])
        subject_mapping = params.get("subject_mapping")
        db_path = params.get("db_path")
        return VoucherService(db_path=db_path).preview(transactions, subject_mapping)
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("voucher.save_draft")
def handle_voucher_save_draft(params: dict) -> dict:
    try:
        from finance_agent_backend.services import VoucherService
        return VoucherService(db_path=params.get("db_path")).save_draft(
            name=params.get("name", ""),
            period=params.get("period", ""),
            entries=params.get("entries", []),
        )
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("voucher.load_draft")
def handle_voucher_load_draft(params: dict) -> dict:
    try:
        from finance_agent_backend.services import VoucherService
        return VoucherService(db_path=params.get("db_path")).load_draft(
            draft_id=params.get("draft_id"),
        )
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("voucher.list_drafts")
def handle_voucher_list_drafts(params: dict) -> dict:
    try:
        from finance_agent_backend.services import VoucherService
        return VoucherService(db_path=params.get("db_path")).list_drafts()
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("voucher.delete_draft")
def handle_voucher_delete_draft(params: dict) -> dict:
    try:
        from finance_agent_backend.services import VoucherService
        return VoucherService(db_path=params.get("db_path")).delete_draft(
            draft_id=params.get("draft_id"),
        )
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("voucher.export")
def handle_voucher_export(params: dict) -> dict:
    try:
        from finance_agent_backend.services import VoucherService
        return VoucherService(db_path=params.get("db_path")).export(
            draft_id=params.get("draft_id"),
            output_path=params.get("output_path", "voucher.xlsx"),
            period=params.get("period", ""),
            source_files=params.get("source_files", []),
        )
    except Exception as e:
        _log.error("voucher.export 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 基础设施
# ---------------------------------------------------------------------------

@register_method("db.health")
def handle_db_health(params: dict) -> dict:
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


# ---------------------------------------------------------------------------
# JSON-RPC 传输层
# ---------------------------------------------------------------------------

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
