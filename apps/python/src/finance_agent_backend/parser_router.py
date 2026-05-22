"""解析路由器 — 根据文件扩展名将文件分发到对应的解析器。

替代 bridge.py 中 handle_parse_pdf 原有的 110 行路由链。
所有重型解析器模块均延迟导入，仅加载当前需要的解析器。
"""
from __future__ import annotations

import os
import re
import time
import fitz  # 足够轻量，可直接导入

from finance_agent_backend.models import Transaction, ParseResult

# ---------------------------------------------------------------------------
# 银行代码与中文名称双向映射
# ---------------------------------------------------------------------------

BANK_CODE_TO_NAME: dict[str, str] = {
    'ICBC': '工商银行',
    'CMB': '招商银行',
    'GFB': '广发银行',
}
BANK_NAME_TO_CODE: dict[str, str] = {v: k for k, v in BANK_CODE_TO_NAME.items()}


# ---------------------------------------------------------------------------
# PDF 结构特征匹配器（Level 1 嵌入式文本检测）
# ---------------------------------------------------------------------------

# 每个条目: ((关键字...), (bankCode, docType), mode)
#   mode='all'  — 所有关键字必须同时出现（带表头的表格格式）
#   mode='any'  — 任一关键字命中即可（仅标题，如回单）

# docType 统一用中文：'流水' | '回单' | 'unknown'
PDF_STRUCTURE_MATCHERS: list[tuple[tuple[str, ...], tuple[str, str], str]] = [
    # 招行 — 表格格式流水（账务明细清单 + 借贷金额列）
    (('账务明细清单', '借方/贷方金额'), ('CMB', '流水'), 'all'),
    (('Date', 'Currency', 'Counter Party'), ('CMB', '流水'), 'all'),
    # 招行 — 回单（仅有标题，无列）
    (('出账回单', '入账回单'), ('CMB', '回单'), 'any'),
    # 广发 — 表格格式流水（使用本期支出/本期收入而非交易金额）
    (('交易日期', '交易类型', '本期支出'), ('GFB', '流水'), 'all'),
]


def _match_pdf_structure(
    text: str,
    matchers: list[tuple[tuple[str, ...], tuple[str, str], str]] | None = None,
) -> tuple[str, str] | None:
    """将嵌入式 PDF 文本与结构签名进行匹配。

    首个命中时返回 (bankCode, docType)，否则返回 None。
    匹配前会压缩空白字符，消除 PDF 渲染导致的字间空格。
    """
    if matchers is None:
        matchers = PDF_STRUCTURE_MATCHERS

    # PDF 渲染可能产生字间空格（如"出 账 回 单"），压缩空白后匹配
    compact = re.sub(r'\s+', '', text)

    for keywords, result, mode in matchers:
        if mode == 'all':
            if all(re.sub(r'\s+', '', kw) in compact for kw in keywords):
                return result
        elif mode == 'any':
            if any(re.sub(r'\s+', '', kw) in compact for kw in keywords):
                return result

    return None


# ---------------------------------------------------------------------------
# 解析器注册表 — bankCode → dispatch list
# ---------------------------------------------------------------------------
# Each bank entry is a list of dispatch entries tried in order:
#   (module_name, class_name)           — simple parser, try and move on
#   dict                                 — sub-typed entry (e.g. CMB statement:
#                                        'table' / 'column' via _detect_cmb_pdf_subtype)
# An 'unknown' key in the list handles the case where docType could not be
# determined from the file content.  Banks without an 'unknown' entry fall
# through to _try_unknown_bank_parsers() which tries every bank's 'unknown'.

PARSER_REGISTRY: dict[str, list] = {
    'ICBC': [
        ('icbc_receipt_grid_parser', 'ICBCReceiptGridParser'),  # receipt
        ('icbc_parser', 'ICBCParser'),                            # statement
    ],
    'CMB': [
        ('cmb_receipt_parser', 'CMBReceiptParser'),              # receipt
        {'table': ('cmb_table_parser', 'CMBTableParser'),         # statement – sub-typed
         'column': ('cmb_parser', 'CMBParser')},
    ],
    'GFB': [
        ('gfb_table_parser', 'GFBTableParser'),                   # statement
    ],
}


# RapidOCR 单例 — 避免每次检测重复加载 ONNX 模型（~50MB）
_ocr_instance = None


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_instance = RapidOCR()
    return _ocr_instance


def detect_bank_from_pdf(file_path: str) -> tuple[str, str]:
    """通过三级路由检测银行。返回 (bankCode, docType)，docType 为中文。

    Level 1: fitz 提取嵌入式文本 → _match_pdf_structure()
    Level 2: OCR 首页 → 正则提取账号 → registry.match_by_account()
    均失败时回退到 ('未知银行', '流水')。
    """
    from finance_agent_backend.account_registry import (
        AccountMappingRepository,
        AccountRegistry,
        _default_config_path,
    )

    repo = AccountMappingRepository(_default_config_path())
    registry = AccountRegistry(repo.load())  # 函数级实例，每次调用新建

    try:
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        doc = fitz.open('pdf', pdf_bytes)
        try:
            sample = ''
            for i in range(min(3, len(doc))):
                sample += doc[i].get_text('text')

            # Level 1: 在嵌入式文本上做结构匹配
            if sample.strip():
                result = _match_pdf_structure(sample)
                if result:
                    return result
                return '未知银行', '流水'

            # Level 2: 扫描件 OCR + 账号匹配（复用 doc，避免重读 PDF）
            result = _detect_bank_by_ocr_account(doc, registry)
            if result:
                return result
            return '未知银行', '流水'
        finally:
            doc.close()
    except Exception:
        return '未知银行', 'unknown'


def _detect_bank_by_ocr_account(doc, registry) -> tuple[str, str] | None:
    """Level 2: OCR 识别首页，提取账号，匹配 registry。

    复用传入的 fitz doc，不重复读 PDF。
    RapidOCR 实例通过模块级单例复用。
    registry 由调用方传入，不依赖全局单例。
    返回 (bankCode, '回单') 或 None。
    """
    try:
        import re
        from PIL import Image
        import numpy as np

        page = doc[0]
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        img_np = np.array(img)

        ocr = _get_ocr()
        result = ocr(img_np)
        if not result or not result[0]:
            return None

        text = ''.join(str(item[1]) for item in result[0] if item[1])

        candidates = re.findall(r'\d{12,19}', text)

        for acct in candidates:
            entry = registry.match_by_account(acct)
            if entry:
                return (entry.bankCode, '回单')

        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# ParseResult → dict 序列化
# ---------------------------------------------------------------------------

def _serialize_result(result: ParseResult) -> dict:
    """将 ParseResult 数据类转换为 JSON 可序列化字典。"""
    return {
        "success": True,
        "transactions": [_serialize_txn(t) for t in result.transactions],
        "bank": result.bank,
        "statementDate": result.statement_date.isoformat() if result.statement_date else None,
        "openingBalance": float(result.opening_balance) if result.opening_balance else None,
        "closingBalance": float(result.closing_balance) if result.closing_balance else None,
        "confidence": result.confidence,
        "errors": result.errors,
        "warnings": result.warnings,
    }


def _serialize_txn(t: Transaction) -> dict:
    return {
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
    }


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def route(file_path: str, bank: str | None = None, doc_type: str | None = None) -> dict:
    """将 *file_path* 路由到对应解析器，返回 JSON 可序列化字典。

    按扩展名分发:
    - ``.xlsx``  → 招行 Excel 解析器
    - ``.csv``   → 工行 CSV 解析器
    - ``.pdf``   → 银行检测 → 银行专用 PDF 解析器 → 通用回退

    *bank* 参数（非空）则跳过 PDF 文件的银行检测。
    *doc_type* 参数（非空）指定文档类型（'statement' / 'receipt'），与 *bank* 配合使用。
    """
    # --- xlsx (招行 Excel) ---
    if file_path.lower().endswith('.xlsx'):
        return _do_parse_cmb_excel(file_path)

    # --- csv (工行 CSV) ---
    if file_path.lower().endswith('.csv'):
        return _do_parse_icbc_csv(file_path)

    # --- pdf ---
    return _do_parse_pdf(file_path, bank=bank, doc_type=doc_type)


# ---------------------------------------------------------------------------
# 格式专用处理器（延迟导入对应解析器模块）
# ---------------------------------------------------------------------------

def _do_parse_cmb_excel(file_path: str) -> dict:
    from finance_agent_backend.tools import cmb_excel_parser
    try:
        parser = cmb_excel_parser.CMBExcelParser()
        result = parser.parse(file_path)
        return _serialize_result(result)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _do_parse_icbc_csv(file_path: str) -> dict:
    from finance_agent_backend.tools import icbc_csv_parser
    try:
        parser = icbc_csv_parser.ICBCCSVParser()
        result = parser.parse(file_path)
        return _serialize_result(result)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _do_parse_pdf(file_path: str, bank: str | None = None,
                  doc_type: str | None = None) -> dict:
    """解析 PDF 文件，使用 PARSER_REGISTRY 分发。

    - *bank* 非空 → 外部指定，转为 bankCode，跳过检测
    - *bank* 空 → 通过三级路由自动检测
    - *doc_type* 非空 → 外部指定文档类型（'statement'/'receipt'）

    强制验证: bankCode 必须属于 PARSER_REGISTRY，否则拒绝解析，
    要求用户在界面上手动选择银行和文件类型。
    """

    def _has_result(r):
        return r is not None and r.transactions

    # ── 解析 bankCode + docType ──────────────────────────────────
    if bank:
        bank_code = BANK_NAME_TO_CODE.get(bank, bank)
        if not doc_type:
            doc_type = '流水'
    else:
        if doc_type:
            bank_code = '未知银行'
        else:
            bank_code, doc_type = detect_bank_from_pdf(file_path)

    # ── 强制验证：bankCode 必须在注册表中 ────────────────────────
    if bank_code not in PARSER_REGISTRY:
        return {
            "success": False,
            "error": f"无法识别银行类型（{bank_code}），请在界面上手动选择银行和文件类型",
        }

    # ── 通过 PARSER_REGISTRY 分发 ───────────────────────────────
    result = _dispatch_registry_parser(file_path, bank_code, doc_type)

    if not _has_result(result):
        return {
            "success": False,
            "error": f"解析失败：{bank_code}（{doc_type}）解析器未返回数据，请尝试其他文件类型或联系开发者",
        }

    return _serialize_result(result)


def _dispatch_registry_parser(
    file_path: str, bank_code: str, doc_type: str
) -> ParseResult | None:
    """查询 PARSER_REGISTRY 并实例化对应解析器。

    按注册表顺序逐个尝试，首个返回数据的即停。
    doc_type 仅用于日志标签，不做硬过滤（允许 receipt 失败后回退到 statement）。
    """
    registry = PARSER_REGISTRY[bank_code]

    for entry in registry:
        t0 = time.time()
        try:
            if isinstance(entry, dict):
                # sub-typed entry (CMB statement: 'table' / 'column')
                subtype = _detect_cmb_pdf_subtype(file_path)
                key = subtype if subtype in entry else list(entry.keys())[0]
                result = _try_parser(*entry[key], file_path)
            elif isinstance(entry, tuple) and len(entry) == 2:
                result = _try_parser(*entry, file_path)
            else:
                result = None
        except Exception:
            result = None

        # 日志标签
        if isinstance(entry, dict):
            label = ','.join(f'{k}={v[1]}' for k, v in entry.items())
        elif isinstance(entry, tuple) and len(entry) == 2:
            label = entry[1]
        else:
            label = '?'
        _log_route(f'{bank_code}({doc_type}):{label}', result, t0)

        if result and result.transactions:
            return result

    return None


def _try_parser(module_name: str, class_name: str, file_path: str) -> ParseResult | None:
    """延迟导入解析器模块并调用其 parse() 方法。"""
    mod = __import__(
        f'finance_agent_backend.tools.{module_name}',
        fromlist=[class_name],
    )
    cls = getattr(mod, class_name)
    parser = cls()
    return parser.parse(file_path)


def _detect_cmb_pdf_subtype(file_path: str) -> str:
    """返回 'table'（账务明细清单）或 'column'（旧式竖排格式）。

    私有辅助函数 — 仅在招行流水分发时调用。
    """
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


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _log_route(label: str, result: ParseResult | None, t0: float,
               logger=None) -> None:
    """记录路由决策日志。接受可选 logger，失败时回退到 print。"""
    count = len(result.transactions) if result else 0
    elapsed = time.time() - t0
    msg = f"{label}: {count} 条, {elapsed:.1f}s"
    if logger:
        try:
            logger.info("%s: %d 条, 耗时 %.1fs", label, count, elapsed)
            return
        except Exception:
            pass
    print(f"[router] {msg}")
