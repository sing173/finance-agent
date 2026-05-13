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
from finance_agent_backend.tools import subject_loader as _subject_loader
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
                notes=t.get('notes'),
            ))

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
    except Exception as e:
        return {"success": False, "error": str(e)}



def _get_config_dir() -> str:
    """获取 config 目录的绝对路径。"""
    return os.path.join(_project_root, 'finance_agent_backend', 'config')


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
    """查询内置科目表信息。"""
    config_dir = _get_config_dir()
    subjects_path = os.path.join(config_dir, 'subjects.json')
    if not os.path.exists(subjects_path):
        return {"success": True, "count": 0, "loaded": False}
    try:
        with open(subjects_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {"success": True, "count": len(data), "loaded": True}
    except Exception as e:
        return {"success": False, "count": 0, "loaded": False, "error": str(e)}


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
