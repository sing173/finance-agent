"""招商银行回单 PDF 解析器 — 竖式 key-value 布局，嵌入式文字。

每页 1-2 张回单，以"出 账 回 单"或"入 账 回 单"标题（14号字）开头，
下方是左(key: x~53)右(key: x~240)两列 key-value 布局。
"""

import re
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

import fitz

from finance_agent_backend.models import ParseResult, Transaction


class CMBReceiptParser:
    """招商银行回单解析器。"""

    BANK_NAME = "招商银行"

    FIELD_MAP = {
        "交易日期": "trade_date",
        "交易金额(小写)": "amount_raw",
        "交易金额（小写）": "amount_raw",
        "交易摘要": "summary",
        "业务类型": "business_type",
        "业务编号": "business_no",
        "交易流水": "transaction_id",
        "相关编号": "related_no",
        "客户编号": "client_no",
        "付款账号": "payer_account",
        "付款人": "payer_name",
        "付款开户行": "payer_bank",
        "收款账号": "payee_account",
        "收款人": "payee_name",
        "收款开户行": "payee_bank",
        "回单编号": "receipt_no",
        "收费时段": "fee_period",
        "业务参考号": "business_ref",
    }

    def __init__(self):
        self.confidence = 1.0

    def parse(self, file_path: str) -> ParseResult:
        errors: List[str] = []

        try:
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()
            doc = fitz.open("pdf", pdf_bytes)
        except Exception as e:
            return ParseResult(
                transactions=[], bank=self.BANK_NAME,
                confidence=0, errors=[f"PDF打开失败: {e}"],
            )

        if doc.page_count == 0:
            doc.close()
            return ParseResult(
                transactions=[], bank=self.BANK_NAME,
                confidence=0, errors=["PDF无页面"],
            )

        has_text = any(
            doc[i].get_text("text").strip()
            for i in range(min(3, doc.page_count))
        )
        if not has_text:
            doc.close()
            return ParseResult(
                transactions=[], bank=self.BANK_NAME,
                confidence=0, errors=["扫描件回单暂不支持，请使用带嵌入式文字的PDF"],
            )

        all_transactions: List[Transaction] = []

        for page_num in range(doc.page_count):
            page = doc[page_num]
            spans = _extract_all_spans(page)
            if not spans:
                continue

            receipts = _split_receipts(spans)
            for receipt_spans in receipts:
                fields = _extract_fields(receipt_spans)
                txn = _build_transaction(fields)
                if txn:
                    all_transactions.append(txn)
                else:
                    self.confidence = max(0, self.confidence - 0.02)
                    errors.append(f"第{page_num + 1}页: 无法从回单提取交易数据")

        doc.close()

        all_transactions.sort(key=lambda t: t.date)

        return ParseResult(
            transactions=all_transactions,
            bank=self.BANK_NAME,
            statement_date=all_transactions[-1].date if all_transactions else None,
            confidence=self.confidence if all_transactions else 0,
            errors=errors,
        )


def _extract_all_spans(page: fitz.Page) -> List[dict]:
    spans = []
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                spans.append({
                    "x0": span["bbox"][0],
                    "y0": span["bbox"][1],
                    "x1": span["bbox"][2],
                    "y1": span["bbox"][3],
                    "text": text,
                    "size": span["size"],
                })
    return spans


def _split_receipts(spans: List[dict]) -> List[List[dict]]:
    """按回单标题（14号字的"出/入账回单"）将 spans 分组为各张回单。"""
    title_indices = []
    for i, s in enumerate(spans):
        if 12 <= s["size"] <= 16:
            compact = s["text"].replace(" ", "")
            if "出账回单" in compact or "入账回单" in compact:
                title_indices.append(i)

    if not title_indices:
        return [spans]

    receipts = []
    for idx, title_i in enumerate(title_indices):
        title_y = spans[title_i]["y0"]
        next_y = (
            spans[title_indices[idx + 1]]["y0"]
            if idx + 1 < len(title_indices)
            else float("inf")
        )
        receipt_spans = [
            s for s in spans
            if s["y0"] >= title_y - 5 and s["y0"] < next_y - 5
        ]
        if receipt_spans:
            receipts.append(receipt_spans)

    return receipts


def _extract_fields(spans: List[dict]) -> Dict[str, str]:
    fields: Dict[str, str] = {}

    for s in spans:
        text = s["text"]
        if "出账回单" in text.replace(" ", ""):
            fields["_receipt_type"] = "expense"
        elif "入账回单" in text.replace(" ", ""):
            fields["_receipt_type"] = "income"

        if "：" in text:
            key, value = text.split("：", 1)
            key = key.strip()
            value = value.strip()
            if key in CMBReceiptParser.FIELD_MAP:
                fields[CMBReceiptParser.FIELD_MAP[key]] = value
        elif ":" in text:
            key, value = text.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key in CMBReceiptParser.FIELD_MAP:
                fields[CMBReceiptParser.FIELD_MAP[key]] = value

    return fields


def _parse_date_cn(text: str) -> Optional[date]:
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{4})(\d{2})(\d{2})", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _parse_amount_cny(text: str) -> Optional[Decimal]:
    m = re.search(r"CNY\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if not m:
        m = re.search(r"([\d,]+\.\d{2})", text)
    if m:
        return Decimal(m.group(1).replace(",", ""))
    return None


def _build_transaction(fields: Dict[str, str]) -> Optional[Transaction]:
    date_str = fields.get("trade_date", "")
    trade_date = _parse_date_cn(date_str) if date_str else None

    amount_str = fields.get("amount_raw", "")
    amount = _parse_amount_cny(amount_str) if amount_str else None

    if not trade_date or not amount:
        return None

    receipt_type = fields.get("_receipt_type", "expense")

    if receipt_type == "expense":
        direction = "expense"
        account_name = fields.get("payer_name", "")
        account_number = fields.get("payer_account", "")
        counterparty = fields.get("payee_name", "")
        counterparty_account = fields.get("payee_account", "")
    else:
        direction = "income"
        account_name = fields.get("payee_name", "")
        account_number = fields.get("payee_account", "")
        counterparty = fields.get("payer_name", "")
        counterparty_account = fields.get("payer_account", "")

    summary = fields.get("summary", "")
    business_type = fields.get("business_type", "")

    if summary and summary not in ("收费",):
        description = summary
    elif business_type:
        description = business_type
    elif summary:
        description = summary
    else:
        description = "支出交易" if direction == "expense" else "收入交易"

    reference_number = fields.get("receipt_no", "") or None

    notes_parts = []
    transaction_id = fields.get("transaction_id", "")
    if transaction_id:
        notes_parts.append(f"流水:{transaction_id}")
    business_no = fields.get("business_no", "")
    if business_no and business_no != transaction_id:
        notes_parts.append(f"业务编号:{business_no}")
    notes = "; ".join(notes_parts) if notes_parts else None

    return Transaction(
        date=trade_date,
        description=description,
        amount=amount,
        currency="CNY",
        direction=direction,
        counterparty=counterparty or None,
        reference_number=reference_number,
        notes=notes,
        account_number=account_number or None,
        account_name=account_name or None,
    )
