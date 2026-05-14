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
from finance_agent_backend.tools import cmb_table_parser as _cmb_table_parser
from finance_agent_backend.tools import gfb_table_parser as _gfb_table_parser
from finance_agent_backend.tools import excel_builder as _excel_builder
from finance_agent_backend.tools import pdf_ocr as _pdf_ocr
from finance_agent_backend.tools import icbc_parser as _icbc_parser
from finance_agent_backend.tools import icbc_receipt_grid_parser as _icbc_receipt_parser
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


def _detect_bank_from_pdf(file_path: str) -> tuple:
    """检测银行和文档类型。返回 (bank_name, doc_type)。

    逻辑:
      1. 提取 PDF 嵌入文字
      2. 有文字 → 关键字匹配银行名和文档类型
      3. 无文字(扫描件) → 返回 unknown，由路由层先试 receipt 再回退 statement
         （不在检测阶段 OCR，避免与解析器重复加载 ONNX 模型）
    """
    import fitz

    BANK_KEYWORDS = {
        '招商银行': ['招商银行', 'China Merchants Bank'],
        '工商银行': ['工商银行', 'ICBC'],
        '中国银行': ['中国银行', 'Bank of China'],
        '建设银行': ['建设银行', 'China Construction Bank'],
        '广发银行': ['广发银行', '广东发展银行', 'CGB'],
    }

    def _classify(sample: str) -> tuple:
        bank = '未知银行'
        for name, kws in BANK_KEYWORDS.items():
            if any(kw in sample for kw in kws):
                bank = name
                break

        doc_type = 'unknown'
        if '出账回单' in sample or '入账回单' in sample or '电子回单' in sample or '网上银行电子回单' in sample:
            doc_type = 'receipt'
        elif '交易流水' in sample or '明细清单' in sample or '对账单' in sample:
            doc_type = 'statement'
        elif '日期' in sample and '金额' in sample and '余额' in sample:
            doc_type = 'statement'

        return (bank, doc_type)

    try:
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        doc = fitz.open('pdf', pdf_bytes)
        sample = ''
        for i in range(min(3, len(doc))):
            sample += doc[i].get_text('text')
        doc.close()

        # 有嵌入文字 → 关键字匹配
        if sample.strip():
            return _classify(sample)

        # 扫描件 → 不单独 OCR，让解析器完成全部工作
        return ('未知银行', 'unknown')
    except Exception:
        return ('未知银行', 'unknown')


@register_method("parse_pdf")
def handle_parse_pdf(params: dict) -> dict:
    """解析 PDF 银行流水"""
    file_path = params.get("file_path")
    bank = params.get("bank")

    if not file_path:
        return {"success": False, "error": "缺少 file_path 参数"}

    try:
        # 自动检测银行类型和文档类型
        if not bank:
            bank, doc_type = _detect_bank_from_pdf(file_path)
        else:
            doc_type = 'unknown'

        # 路由策略:
        #   receipt / 未知银行 / 工商但不明确 → 先试回单网格解析器(自带验证，失败返回空)
        #   工商明确流水 → ICBCParser
        #   招商 → CMBTableParser (对账单) / CMBParser (旧列式流水)
        #   广发 → GFBTableParser
        result = None
        try_receipt_first = (
            doc_type == 'receipt'
            or bank == '未知银行'
            or ('工商' in (bank or '') and doc_type != 'statement')
        )
        if try_receipt_first:
            parser = _icbc_receipt_parser.ICBCReceiptGridParser()
            result = parser.parse(file_path)

        if result is None or not result.transactions:
            if '工商' in (bank or '') or bank == '未知银行':
                parser = _icbc_parser.ICBCParser()
                result = parser.parse(file_path)
        if result is None or not result.transactions:
            if '招商' in (bank or ''):
                parser = (_cmb_table_parser.CMBTableParser()
                          if _detect_cmb_pdf_type(file_path) == 'table'
                          else _cmb_parser.CMBParser())
                result = parser.parse(file_path)
        if result is None or not result.transactions:
            if '广发' in (bank or ''):
                parser = _gfb_table_parser.GFBTableParser()
                result = parser.parse(file_path)
        if result is None or not result.transactions:
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
                "notes": t.notes,
                "account_number": t.account_number,
                "account_name": t.account_name,
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


def _detect_cmb_pdf_type(file_path: str) -> str:
    """检测招行 PDF 类型: 'table' (账务明细清单) 或 'column' (旧列式流水)。"""
    import fitz
    TABLE_TITLES = ['账务明细清单', 'Statement Of Account',
                    'Statement of Account', 'STATEMENT OF ACCOUNT']
    try:
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        doc = fitz.open('pdf', pdf_bytes)
        text = doc[0].get_text('text')
        doc.close()
        for title in TABLE_TITLES:
            if title in text:
                return 'table'
    except Exception:
        pass
    return 'column'


@register_method("generate_excel")
def handle_generate_excel(params: dict) -> dict:
    """导出交易列表到 Excel"""
    transactions_data = params.get("transactions")
    output_path = params.get("output_path", "bank_statement.xlsx")

    if not transactions_data:
        return {"success": False, "error": "缺少 transactions 参数"}

    try:
        from datetime import datetime
        from decimal import Decimal
        transactions = []
        for t in transactions_data:
            transactions.append(Transaction(
                date=datetime.strptime(t['date'], '%Y-%m-%d').date(),
                description=t.get('description', ''),
                amount=Decimal(str(t.get('amount', 0))),
                currency=t.get('currency', 'CNY'),
                direction=t.get('direction', 'expense'),
                counterparty=t.get('counterparty'),
                reference_number=t.get('reference_number'),
            ))

        builder = _excel_builder.ExcelBuilder()
        excel_path = builder.build(transactions, output_path)
        return {"success": True, "excel_path": excel_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_method("ocr_pdf")
def handle_ocr_pdf(params: dict) -> dict:
    """OCR 识别 PDF（扫描件/图片型 PDF）"""
    file_path = params.get("file_path")
    pages = params.get("pages")  # optional list of page numbers
    dpi = params.get("dpi", 200)

    if not file_path:
        return {"success": False, "error": "缺少 file_path 参数"}

    try:
        ocr = _pdf_ocr.PDFOCR(dpi=dpi)
        result = ocr.extract(file_path, pages=pages)
        return {"success": True, **result}
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
