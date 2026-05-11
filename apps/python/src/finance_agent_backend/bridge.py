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
from finance_agent_backend.tools import excel_builder as _excel_builder
from finance_agent_backend.tools import pdf_ocr as _pdf_ocr
from finance_agent_backend.tools import icbc_parser as _icbc_parser
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
    """通过 PDF 文本识别银行。扫描件无文字时回退到快速 OCR。"""
    import fitz
    try:
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        doc = fitz.open('pdf', pdf_bytes)
        sample = ''
        for i in range(min(3, len(doc))):
            sample += doc[i].get_text('text')

        # If no text at all, likely a scanned PDF — try OCR on page 0
        if not sample.strip():
            from PIL import Image
            import cv2
            import numpy as np
            from rapidocr_onnxruntime import RapidOCR
            pix = doc[0].get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img_np = np.array(img.convert("L"))
            _, img_bin = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            engine = RapidOCR()
            ocr_result, _ = engine(img_bin)
            if ocr_result:
                sample = "".join(text for _, text, _ in ocr_result)
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
        if '工商' in (bank or ''):
            parser = _icbc_parser.ICBCParser()
            result = parser.parse(file_path)
        elif bank == '招商银行' or '招商' in (bank or ''):
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
                "notes": t.notes,
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
