#!/usr/bin/env python3
"""
finance-agent Python Bridge
JSON-RPC 2.0 服务器，通过 stdio 与 Electron 通信
同步版本 — 简单、可靠、兼容所有 Python 3.11+
"""

import json
import sys
import os
import logging
import time
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

# 方法注册表
METHODS = {}  # type: dict

def register_method(name: str):
    """装饰器：注册 RPC 方法"""
    def decorator(func):
        METHODS[name] = func
        return func
    return decorator


@register_method("health")
def handle_health(params: dict) -> dict:
    import sys
    return {
        "status": "ok",
        "version": "0.2.0",
        "python_version": sys.version,
    }


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


@register_method("generate_voucher_excel")
def handle_generate_voucher_excel(params: dict) -> dict:
    """将银行流水按金蝶精斗云凭证导入模板格式导出 Excel。

    params:
        transactions  (list, required): 流水列表，格式同 generate_excel
        output_path   (str,  optional): 输出文件路径，默认 voucher.xlsx
        subject_mapping (dict, optional): 关键字映射配置；为空时读取内置默认配置
        account_mapping (dict, optional): 账号映射配置；为空时读取内置默认配置
        period        (str,  optional): 期间名称，用于 Sheet 名，如 '2026年第3期'
    """
    transactions_data = params.get("transactions")
    output_path = params.get("output_path", "voucher.xlsx")
    subject_mapping = params.get("subject_mapping")   # None = 读默认配置
    account_mapping = params.get("account_mapping")   # None = 读默认配置
    period = params.get("period", "")

    if not transactions_data:
        return {"success": False, "error": "缺少 transactions 参数"}

    try:
        transactions = [Transaction.from_dict(t) for t in transactions_data]

        # 加载内置科目（config/subjects.json）
        subjects = _load_built_in_subjects()

        builder = _excel_builder.ExcelBuilder()
        voucher_path = builder.build_voucher(
            transactions=transactions,
            subjects=subjects,
            subject_mapping=subject_mapping,
            account_mapping=account_mapping,
            output_path=output_path,
            period=period,
        )
        return {"success": True, "excel_path": voucher_path}
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
        transactions = [t.to_dict() for t in result.transactions]
        return {
            "success": True, "transactions": transactions,
            "bank": result.bank,
            "statementDate": result.statement_date.isoformat() if result.statement_date else None,
            "openingBalance": float(result.opening_balance) if result.opening_balance else None,
            "closingBalance": float(result.closing_balance) if result.closing_balance else None,
            "confidence": result.confidence, "errors": result.errors, "warnings": result.warnings,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_config_dir() -> str:
    """获取 config 目录的绝对路径。打包后用 sys._MEIPASS，开发用 _project_root。"""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = _project_root
    return os.path.join(base, 'finance_agent_backend', 'config')


def _load_built_in_subjects() -> dict:
    """从内置 config/subjects.json 加载科目字典。"""
    config_dir = _get_config_dir()
    subjects_path = os.path.join(config_dir, 'subjects.json')
    if not os.path.exists(subjects_path):
        return {}

    with open(subjects_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    from finance_agent_backend.models import Subject
    subjects: dict = {}
    for code, info in data.items():
        subjects[code] = Subject(
            code=info.get('code', code),
            name=info.get('name', ''),
            category=info.get('category', ''),
            direction=info.get('direction', '借'),
            aux_category=info.get('aux_category', ''),
            is_cash=info.get('is_cash', False),
            enabled=info.get('enabled', True),
            full_name=info.get('full_name', info.get('name', '')),
        )
    return subjects


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

        config_dir = _get_config_dir()
        subjects_json_path = os.path.join(config_dir, 'subjects.json')
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
    config_dir = _get_config_dir()
    subjects_path = os.path.join(config_dir, 'subjects.json')
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
    """动态返回当前支持的银行列表（中文名，供 UI 下拉选择）。"""
    from finance_agent_backend import parser_router
    return {"success": True, "banks": list(parser_router.BANK_CODE_TO_NAME.values())}


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

            # PDF: three-level routing detection
            bank_code, doc_type = parser_router.detect_bank_from_pdf(fp)
            bank_name = parser_router.BANK_CODE_TO_NAME.get(bank_code, bank_code)
            results.append({
                "filePath": fp,
                "bank": bank_name,
                "bankCode": bank_code,
                "docType": doc_type,
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


@register_method("account_registry.list")
def handle_account_registry_list(params: dict) -> dict:
    """列出所有账号-科目映射。"""
    try:
        from finance_agent_backend.account_registry import (
            AccountMappingRepository,
            _default_config_path,
        )
        repo = AccountMappingRepository(_default_config_path())
        entries = repo.load()
        return {
            "success": True,
            "accounts": [
                {
                    "id": e.id,
                    "matchType": e.matchType,
                    "pattern": e.pattern,
                    "bank": e.bank,
                    "bankCode": e.bankCode,
                    "subjectCode": e.subjectCode,
                    "subjectName": e.subjectName,
                }
                for e in entries
            ],
        }
    except Exception as e:
        _log.error("account_registry.list 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


def _get_subject_codes() -> set:
    """加载 subjects.json 的科目代码集合，用于 add() 校验。"""
    try:
        from finance_agent_backend.account_registry import _default_config_path
        import json

        # subjects.json 与 account_mapping.json 同目录
        config_dir = os.path.dirname(_default_config_path())
        subjects_path = os.path.join(config_dir, "subjects.json")

        if not os.path.exists(subjects_path):
            return set()

        with open(subjects_path, "r", encoding="utf-8") as f:
            subjects = json.load(f)
        return set(subjects.keys())
    except Exception:
        return set()


@register_method("account_registry.match")
def handle_account_registry_match(params: dict) -> dict:
    """根据账号匹配映射条目。"""
    account_number = params.get("accountNumber")
    if not account_number:
        return {"success": False, "error": "缺少 accountNumber 参数"}

    try:
        from finance_agent_backend.account_registry import (
            AccountMappingRepository,
            AccountRegistry,
            _default_config_path,
        )
        repo = AccountMappingRepository(_default_config_path())
        registry = AccountRegistry(repo.load())
        entry = registry.match_by_account(account_number)

        if entry:
            return {
                "success": True,
                "entry": {
                    "id": entry.id,
                    "matchType": entry.matchType,
                    "pattern": entry.pattern,
                    "bank": entry.bank,
                    "bankCode": entry.bankCode,
                    "subjectCode": entry.subjectCode,
                    "subjectName": entry.subjectName,
                },
            }
        else:
            return {"success": True, "entry": None}
    except Exception as e:
        _log.error("account_registry.match 异常: %s", traceback.format_exc())
        return {"success": False, "error": str(e)}


@register_method("account_registry.add")
def handle_account_registry_add(params: dict) -> dict:
    """新增账号-科目映射（校验 bankCode 必填 + subjectCode 存在性）。"""
    try:
        from finance_agent_backend.account_registry import (
            AccountMappingRepository,
            AccountRegistry,
            AccountEntry,
            _default_config_path,
        )

        # 参数校验
        bankCode = params.get("bankCode", "")
        if not bankCode:
            return {"success": False, "error": "bankCode 不能为空"}

        subjectCode = params.get("subjectCode", "")

        # 加载现有条目 + 科目表
        repo = AccountMappingRepository(_default_config_path())
        entries = repo.load()
        subject_codes = _get_subject_codes()

        # 构建新条目
        entry = AccountEntry(
            id="",  # auto-generated
            matchType=params.get("matchType", "suffix"),
            pattern=params.get("pattern", ""),
            bank=params.get("bank", ""),
            bankCode=bankCode,
            subjectCode=subjectCode,
            subjectName=params.get("subjectName", ""),
        )

        # 使用 AccountRegistry 的 add 方法（会校验 + 自动生成 id）
        registry = AccountRegistry(entries, subject_codes=subject_codes)
        registry.add(entry)

        # 持久化
        repo.save(registry.list_all(), "10002")

        return {
            "success": True,
            "id": entry.id,
            "entry": {
                "id": entry.id,
                "matchType": entry.matchType,
                "pattern": entry.pattern,
                "bank": entry.bank,
                "bankCode": entry.bankCode,
                "subjectCode": entry.subjectCode,
                "subjectName": entry.subjectName,
            },
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
        from finance_agent_backend.account_registry import (
            AccountMappingRepository,
            AccountRegistry,
            AccountEntry,
            _default_config_path,
        )

        repo = AccountMappingRepository(_default_config_path())
        entries = repo.load()
        subject_codes = _get_subject_codes()
        registry = AccountRegistry(entries, subject_codes=subject_codes)

        entry = AccountEntry(
            id=entry_id,
            matchType=params.get("matchType", "suffix"),
            pattern=params.get("pattern", ""),
            bank=params.get("bank", ""),
            bankCode=params.get("bankCode", ""),
            subjectCode=params.get("subjectCode", ""),
            subjectName=params.get("subjectName", ""),
        )

        registry.update(entry)
        repo.save(registry.list_all(), "10002")

        return {"success": True}
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
        from finance_agent_backend.account_registry import (
            AccountMappingRepository,
            AccountRegistry,
            _default_config_path,
        )

        repo = AccountMappingRepository(_default_config_path())
        entries = repo.load()
        registry = AccountRegistry(entries)

        registry.delete(entry_id)
        repo.save(registry.list_all(), "10002")

        return {"success": True}
    except Exception as e:
        _log.error("account_registry.delete 异常: %s", traceback.format_exc())
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

