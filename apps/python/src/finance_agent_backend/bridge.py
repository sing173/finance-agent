#!/usr/bin/env python3
"""
finance-agent Python Bridge
JSON-RPC 2.0 服务器，通过 stdio 与 Electron 通信
同步版本 — 简单、可靠、兼容所有 Python 3.11+
"""

import json
import sys
import os

# 确保项目根目录在 sys.path 中，支持直接运行和模块运行
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from finance_agent_backend.tools import pdf_parser as _pdf_parser
from finance_agent_backend.tools import cmb_parser as _cmb_parser
from finance_agent_backend.tools import reconciler as _reconciler
from finance_agent_backend.tools import excel_builder as _excel_builder
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


def _detect_bank_from_pdf(file_path: str) -> str:
    """通过 PDF 文本识别银行"""
    import fitz
    try:
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        doc = fitz.open('pdf', pdf_bytes)
        sample = ''
        for i in range(min(3, len(doc))):
            sample += doc[i].get_text('text')
        doc.close()

        if '招商银行' in sample or 'China Merchants Bank' in sample:
            return '招商银行'
        for name in ['中国银行', '工商银行', '建设银行']:
            if name in sample:
                return name
    except Exception:
        pass
    return '未知银行'


@register_method("parse_pdf")
def handle_parse_pdf(params: dict) -> dict:
    """解析 PDF 银行流水"""
    file_path = params.get("file_path")
    bank = params.get("bank")

    if not file_path:
        return {"success": False, "error": "缺少 file_path 参数"}

    try:
        # 自动检测银行类型
        if not bank:
            bank = _detect_bank_from_pdf(file_path)

        # 根据银行类型选择解析器
        if bank == '招商银行' or '招商' in (bank or ''):
            parser = _cmb_parser.CMBParser()
            result = parser.parse(file_path)
        else:
            parser = _pdf_parser.BankStatementParser()
            result = parser.parse(file_path, bank)

        transactions = []
        for t in result.transactions:
            transactions.append({
                "date": t.date.isoformat(),
                "description": t.description,
                "amount": float(t.amount),
                "currency": t.currency,
                "direction": t.direction,
                "counterparty": t.counterparty,
                "reference_number": t.reference_number,
            })

        return {
            "success": True,
            "transactions": transactions,
            "bank": result.bank,
            "statement_date": result.statement_date.isoformat() if result.statement_date else None,
            "confidence": result.confidence,
            "errors": result.errors,
            "warnings": result.warnings,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("reconcile")
def handle_reconcile(params: dict) -> dict:
    """执行对账"""
    pdf_path = params.get("pdf_path")
    ledger_path = params.get("ledger_path", "")
    output_path = params.get("output_path", "reconcile_result.xlsx")

    if not pdf_path:
        return {"success": False, "error": "缺少 pdf_path 参数"}

    try:
        # 解析 PDF - 自动检测银行并选择对应解析器
        bank = _detect_bank_from_pdf(pdf_path)
        if bank == '招商银行':
            parser = _cmb_parser.CMBParser()
            parse_result = parser.parse(pdf_path)
        else:
            parser = _pdf_parser.BankStatementParser()
            parse_result = parser.parse(pdf_path, bank)

        # 从 ledger_path 读取台账交易
        ledger_transactions: list[Transaction] = []
        if ledger_path and os.path.exists(ledger_path):
            with open(ledger_path, 'r', encoding='utf-8') as f:
                ledger_data = json.load(f)
            for t in ledger_data.get('transactions', []):
                from datetime import datetime
                from decimal import Decimal
                ledger_transactions.append(Transaction(
                    date=datetime.strptime(t['date'], '%Y-%m-%d').date(),
                    description=t['description'],
                    amount=Decimal(str(t['amount'])),
                    counterparty=t.get('counterparty'),
                ))

        # 执行对账
        reconciler = _reconciler.Reconciler()
        reconcile_result = reconciler.reconcile(
            parse_result.transactions, ledger_transactions
        )

        # 生成 Excel
        builder = _excel_builder.ExcelBuilder()
        excel_path = builder.build(reconcile_result, output_path)

        return {
            "success": True,
            "matched_count": len(reconcile_result.matched),
            "unreconciled_bank": len(reconcile_result.bank_unreconciled),
            "unreconciled_ledger": len(reconcile_result.ledger_unreconciled),
            "suspicious_count": len(reconcile_result.suspicious),
            "excel_path": excel_path,
            "match_rate": reconcile_result.match_rate,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("generate_excel")
def handle_generate_excel(params: dict) -> dict:
    """生成对账结果 Excel"""
    reconcile_data = params.get("reconcile_result")
    output_path = params.get("output_path", "reconcile_result.xlsx")

    if not reconcile_data:
        return {"success": False, "error": "缺少 reconcile_result 参数"}

    try:
        # 从字典重建 ReconcileResult（简化版）
        from finance_agent_backend.models import ReconcileResult
        result = ReconcileResult(
            matched=reconcile_data.get("matched", []),
            bank_unreconciled=[
                Transaction(**t) if isinstance(t, dict) else t
                for t in reconcile_data.get("bank_unreconciled", [])
            ],
            ledger_unreconciled=[
                Transaction(**t) if isinstance(t, dict) else t
                for t in reconcile_data.get("ledger_unreconciled", [])
            ],
            suspicious=reconcile_data.get("suspicious", []),
        )

        builder = _excel_builder.ExcelBuilder()
        excel_path = builder.build(result, output_path)

        return {"success": True, "excel_path": excel_path}
    except Exception as e:
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
