"""中国工商银行 (ICBC) 回单 PDF OCR 解析器

ICBC 回单 PDF 是扫描件/图片型，须经 OCR 提取文字。
使用「回单边界检测 + 标签锚定 + 空间近邻提取」方案：
  1. PDF 渲染为高分辨率图像
  2. RapidOCR 全页文字识别
  3. 检测"中国工商银行"锚点 → 分割回单区域
  4. 每个回单区域内 → 标签关键词匹配
  5. label → value 空间近邻提取
  6. 每个回单映射为一条 Transaction
"""
import re
from datetime import datetime
from decimal import Decimal
from itertools import groupby
from typing import Dict, List, Optional, Tuple

import cv2
import fitz
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from ..models import Transaction, ParseResult


class ICBCReceiptParser:
    """中国工商银行 OCR 回单解析器 (form-based label anchoring)"""

    BANK_NAME = "中国工商银行"

    # ── label definitions ────────────────────────────────────────
    # (keyword, target_field, inline_separator, value_regex)
    _LABEL_DEFS: List[Tuple[str, str, str, Optional[str]]] = [
        ("付款人", "payer", None, r"[^\d]{2,}"),  # must contain non-digit (name, not account#)
        ("收款人", "payee", None, r"[^\d]{2,}"),
        ("金额(大写)", "amount_cn", None, None),
        ("金额", "amount_text", None, r"￥?\s*[\d,]+\.?\d*"),
        ("摘要", "purpose", None, None),
        ("用途", "usage", None, None),
        ("交易流水号", "ref_no", None, r"\d{6,}"),
        ("电子回单号码", "receipt_no", "：", r"\d{4}-\d{4}-\d{4}-\d{4}"),
        ("时间戳", "timestamp", None, r"\d{4}-\d{2}-\d{2}[-.]"),
        ("验证码", "verify_code", "：", None),
        ("记账日期", "date", None, r"\d{4}[年-]\d{1,2}[月-]\d{1,2}"),
        ("打印日期", "print_date", "：", None),
        ("附言", "postscript", "：", None),
        ("备注", "notes", "：", None),
    ]

    # Keywords that appear as separate (non-value) labels in the form
    _NON_VALUE_KEYWORDS = {
        "付款人", "收款人", "付款账号", "收款账号", "付款", "收款",
        "金额", "金额(大写)", "金额（大写）", "摘要", "用途",
        "交易流水号", "电子回单号码", "时间戳", "验证码",
        "记账日期", "打印日期", "记账网点", "记账柜员",
        "开户银行", "业务", "附言", "备注", "重要提示",
        "中国工商银行", "网上银行电子回单", "电子回单", "专",
        "人", "户", "名", "账", "号",
    }

    def __init__(self, dpi: int = 300):
        self.dpi = dpi
        self._ocr_engine = None

    @property
    def _ocr(self) -> RapidOCR:
        if self._ocr_engine is None:
            self._ocr_engine = RapidOCR()
        return self._ocr_engine

    # ── public API ────────────────────────────────────────────────

    def parse(self, file_path: str) -> ParseResult:
        transactions: List[Transaction] = []
        errors: List[str] = []

        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
        doc = fitz.open("pdf", pdf_bytes)

        for page_num in range(len(doc)):
            try:
                page_tx = self._parse_page(doc, page_num)
                transactions.extend(page_tx)
            except Exception as e:
                errors.append(f"Page {page_num + 1}: {e}")

        doc.close()
        statement_date = transactions[-1].date if transactions else None
        confidence = max(0.0, 1.0 - 0.02 * len(errors))
        return ParseResult(
            transactions=transactions,
            bank=self.BANK_NAME,
            statement_date=statement_date,
            confidence=confidence,
            errors=errors,
            warnings=[],
        )

    # ── page pipeline ─────────────────────────────────────────────

    def _parse_page(self, doc, page_num: int) -> List[Transaction]:
        img = self._render_page(doc, page_num)
        blocks = self._ocr_page_data(img)
        if not blocks:
            return []

        receipts = self._split_receipts(blocks)
        transactions = []
        for rec_blocks in receipts:
            fields = self._extract_fields(rec_blocks)
            tx = self._fields_to_transaction(fields)
            if tx:
                transactions.append(tx)
        return transactions

    # ── stage 1: render (same as icbc_parser) ─────────────────────

    @staticmethod
    def _render_page(doc, page_num: int, dpi: int = 300) -> np.ndarray:
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        return img

    # ── stage 2: OCR (same as icbc_parser) ────────────────────────

    def _ocr_page_data(self, img: np.ndarray) -> list:
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        img_np = np.array(pil_img.convert("L"))
        _, img_bin = cv2.threshold(
            img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        ocr_result, _ = self._ocr(img_bin)
        if not ocr_result:
            return []

        blocks = []
        for box, text, _confidence in ocr_result:
            blocks.append({
                "text": text,
                "x0": box[0][0], "y0": box[0][1],
                "x1": box[2][0], "y1": box[2][1],
                "cx": (box[0][0] + box[2][0]) / 2,
                "cy": (box[0][1] + box[2][1]) / 2,
            })
        blocks.sort(key=lambda b: (b["y0"], b["x0"]))
        return blocks

    # ── stage 3: receipt splitting ────────────────────────────────

    _HEADER_TITLE_KEYWORD = "网上银行电子回单"
    _HEADER_ICBC_KEYWORD = "中国工商银行"
    _FOOTER_KEYWORD = "重要提示"

    def _split_receipts(self, blocks: list) -> List[List[dict]]:
        """Detect receipt regions using title-area keywords as anchors.

        Each receipt title contains "网上银行电子回单" (fallback: "电子回单号码"),
        which never appears inside form fields. The receipt starts at the
        "中国工商银行" block just above the title and ends before the next
        title or the "重要提示" footer.
        """
        # Find title-anchor blocks — unambiguous, never in form fields
        header_indices = [
            i for i, b in enumerate(blocks)
            if self._HEADER_TITLE_KEYWORD in b["text"]
        ]
        if len(header_indices) < 1:
            header_indices = [
                i for i, b in enumerate(blocks)
                if "电子回单号码" in b["text"]
            ]

        if not header_indices:
            return []

        footer_indices = [
            i for i, b in enumerate(blocks)
            if self._FOOTER_KEYWORD in b["text"]
        ]

        receipts = []
        for idx, hi in enumerate(header_indices):
            # Walk backward to include "中国工商银行" block above title
            start = hi
            for back in range(hi - 1, max(hi - 4, -1), -1):
                if (self._HEADER_ICBC_KEYWORD in blocks[back]["text"]
                        and blocks[hi]["y0"] - blocks[back]["y0"] < 50):
                    start = back
                    break

            # End = next title block - 1, or next footer - 1, or end of page
            end_candidates = []
            if idx + 1 < len(header_indices):
                end_candidates.append(header_indices[idx + 1])
            for fi in footer_indices:
                if fi > hi:
                    end_candidates.append(fi)
                    break
            end = min(end_candidates) - 1 if end_candidates else len(blocks) - 1
            if end > start:
                receipts.append(blocks[start:end + 1])
        return receipts

    # ── stage 4: field extraction ─────────────────────────────────

    _LEFT_COL_MAX_X = 1150  # blocks with cx < this are in left column

    def _extract_fields(self, rec_blocks: List[dict]) -> Dict[str, str]:
        """Extract labeled fields from a single receipt region.

        Strategy:
        1. Merge nearby blocks that form known label keywords
        2. For each label, find value: inline or right-neighbor (validated by pattern)
        3. Fall back to position-based extraction for payer/payee
        """
        fields: Dict[str, str] = {}

        # Pre-merge split-label characters
        merged = self._merge_label_blocks(rec_blocks)

        # --- pass 1: inline extraction (label + value in same block) ---
        for b in merged:
            for keyword, field_name, sep, value_re in self._LABEL_DEFS:
                if field_name in fields:
                    continue
                if keyword not in b["text"]:
                    continue
                val = self._extract_inline_value(b["text"], keyword)
                if val and self._validate_value(val, value_re):
                    fields[field_name] = val

        # --- pass 2: spatial extraction (value right of label) ---
        for keyword, field_name, sep, value_re in self._LABEL_DEFS:
            if field_name in fields:
                continue
            label_blocks = [
                b for b in merged if keyword in b["text"]
            ]
            if not label_blocks:
                continue
            label_b = label_blocks[0]
            val = self._extract_right_value(label_b, merged, value_re)
            if val:
                fields[field_name] = val

        # --- pass 3: position-based payer/payee (preferred over spatial) ---
        pos_payer, pos_payee = self._extract_parties_by_position(merged)
        if pos_payer:
            fields["payer"] = pos_payer
        if pos_payee:
            fields["payee"] = pos_payee

        return fields

    @staticmethod
    def _validate_value(value: str, pattern: Optional[str]) -> bool:
        if not value or not value.strip():
            return False
        if pattern is None:
            return len(value.strip()) >= 1
        return bool(re.search(pattern, value))

    def _merge_label_blocks(self, blocks: List[dict]) -> List[dict]:
        """Merge OCR blocks that form known label keywords.

        For labels split across adjacent blocks (e.g. "付"+"款"+"人" →
        "付款人"), merge them into a single block with combined text.
        A y-gap up to 65px is tolerated because form-label characters
        can span two lines in the OCR output.
        """
        if len(blocks) < 2:
            return blocks

        sorted_blocks = sorted(blocks, key=lambda b: (b["y0"], b["x0"]))
        merged = []
        consumed: set = set()

        for i, b in enumerate(sorted_blocks):
            if i in consumed:
                continue
            combined = b.copy()
            consumed.add(i)

            for j in range(i + 1, len(sorted_blocks)):
                if j in consumed:
                    continue
                b2 = sorted_blocks[j]
                # y within 65px
                if abs(b2["y0"] - combined["y0"]) > 65:
                    break
                # x: must be near the current block (within 120px left or right)
                dist = min(
                    abs(b2["x0"] - combined["x1"]),
                    abs(b2["x1"] - combined["x0"]),
                    abs(b2["cx"] - combined["cx"]),
                )
                if dist > 120:
                    continue  # too far, skip but don't break (later blocks may be closer)
                # Only merge short blocks (label fragments), not value text
                if len(combined["text"]) > 12 or len(b2["text"]) > 12:
                    continue
                cand_text = combined["text"] + b2["text"]
                is_label = any(
                    kw in cand_text
                    for kw, _, _, _ in self._LABEL_DEFS
                )
                for kw in self._NON_VALUE_KEYWORDS:
                    if kw in cand_text and kw not in combined["text"] and kw not in b2["text"]:
                        is_label = True
                        break
                if is_label:
                    combined["text"] = cand_text
                    combined["x1"] = max(combined["x1"], b2["x1"])
                    combined["y1"] = max(combined["y1"], b2["y1"])
                    combined["cx"] = (combined["x0"] + combined["x1"]) / 2
                    combined["cy"] = (combined["y0"] + combined["y1"]) / 2
                    consumed.add(j)
                # Even if not a label, keep looking (split labels may have filler between)

            merged.append(combined)
        return merged

    @staticmethod
    def _extract_inline_value(text: str, keyword: str) -> str:
        """Extract value from text that contains label+value like '金额：￥0.22元'."""
        # Find keyword position
        idx = text.find(keyword)
        if idx < 0:
            return ""
        after = text[idx + len(keyword):]
        # Strip leading separators
        after = re.sub(r"^[：:)\s]+", "", after).strip()
        # Remove trailing punctuation that's part of the label
        after = after.rstrip("，,。.")
        return after

    def _extract_right_value(
        self, label_block: dict, all_blocks: List[dict], value_re: Optional[str]
    ) -> str:
        """Find the value block to the right of a label block.

        Only picks blocks that (a) are within 500px to the right,
        (b) are NOT themselves known label keywords,
        (c) optionally match the value regex.
        """
        candidates = []
        for b in all_blocks:
            if b is label_block:
                continue
            # Must be to the right and roughly same y
            dx = b["x0"] - label_block["x1"]
            dy = abs(b["cy"] - label_block["cy"])
            if not (-10 < dx < 500):
                continue
            if dy > 40:
                continue
            # Exclude known label keywords
            if self._is_label_block(b):
                continue
            candidates.append((dx, dy, b))

        if not candidates:
            return ""

        # Pick nearest (by dx) that passes validation
        candidates.sort(key=lambda x: x[0])
        for _, _, b in candidates:
            val = b["text"].strip()
            if self._validate_value(val, value_re):
                return val
        # No fallback when validation regex is specified
        return ""

    def _is_label_block(self, block: dict) -> bool:
        """Check if a block's text is a known label keyword or noise."""
        text = block["text"].strip()
        if len(text) > 20:
            return False
        for kw in self._NON_VALUE_KEYWORDS:
            if text == kw or (len(text) <= 4 and text in kw):
                return True
        # Also filter blocks that are clearly label-like (contain label keywords)
        noise_patterns = ["业务", "产品", "种类", "摘要", "用途", "金额",
                          "验证码", "记账", "打印", "专用章", "回单"]
        for np_pat in noise_patterns:
            if np_pat in text and len(text) <= 8:
                return True
        return False

    _COMPANY_RE = re.compile(r"有限公司|股份有限公司|有限责任|集团")
    _BANK_RE = re.compile(r"银行|支行|分行|分理处|营业室")
    _NOISE_RE = re.compile(r"业务|产品|种类|摘要|用途|记账|打印|验证码|回单号码|电子回单|重要提示|附言|备注")

    def _extract_parties_by_position(
        self, blocks: List[dict]
    ) -> Tuple[str, str]:
        """Extract payer/payee using 2-column layout position.

        Left column (cx < _LEFT_COL_MAX_X) → payer
        Right column → payee

        Prefers actual company names (有限公司/集团) over bank names.
        Within each column, prefers the top-most (smallest y) match.
        """
        left_candidates: List[Tuple[float, str]] = []  # (y0, name)
        right_candidates: List[Tuple[float, str]] = []

        for b in blocks:
            text = b["text"].strip()
            if len(text) < 4 or len(text) > 80:
                continue
            if self._NOISE_RE.search(text):
                continue
            if not self._COMPANY_RE.search(text) and not self._BANK_RE.search(text):
                continue
            entry = (b["y0"], text)
            if b["cx"] < self._LEFT_COL_MAX_X:
                left_candidates.append(entry)
            else:
                right_candidates.append(entry)

        def pick_best(candidates: List[Tuple[float, str]]) -> str:
            if not candidates:
                return ""
            # Prefer company names over bank names
            companies = [(y, t) for y, t in candidates if self._COMPANY_RE.search(t)]
            if companies:
                # Pick top-most company name
                companies.sort(key=lambda x: x[0])
                return companies[0][1]
            # Fall back to bank name
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

        return pick_best(left_candidates), pick_best(right_candidates)

    # ── stage 5: fields → Transaction ─────────────────────────────

    @staticmethod
    def _fields_to_transaction(fields: Dict[str, str]) -> Optional[Transaction]:
        """Map extracted receipt fields to a Transaction object."""
        # --- date ---
        date_str = fields.get("date", "")
        tx_date = ICBCReceiptParser._parse_date(date_str)
        if not tx_date:
            ts = fields.get("timestamp", "")
            tx_date = ICBCReceiptParser._parse_timestamp_date(ts)
        if not tx_date:
            return None

        # --- amount ---
        amount_text = fields.get("amount_text", "")
        amount = ICBCReceiptParser._parse_amount(amount_text)

        # --- counterparty ---
        payer = fields.get("payer", "").strip()
        payee = fields.get("payee", "").strip()
        counterparty = payee if payee else (payer if payer else None)
        # Reject account numbers as counterparty
        if counterparty and re.match(r"^[\d*]+\s*$", counterparty):
            counterparty = None

        # --- description ---
        purpose = fields.get("purpose", "").strip()
        usage = fields.get("usage", "").strip()
        # Clean up: remove label text that leaked into purpose value
        for noise in ["业务（产品）种类", "业务(产品)种类", "业务种类", "跨行收报",
                       "跨行发报", "对公收费", "网银互联", "利息入账", "用途",
                       "交易流水号", "时间戳", "记账日期", "摘要",
                       "产品名称", "费用名称", "应收金额", "实收金额",
                       "业务委托日期", "业务类型", "普通汇兑", "普通贷记",
                       "电子回单", "专用章", "专后章", "专居章"]:
            purpose = purpose.replace(noise, "")
        purpose = purpose.strip()
        # Remove amount text that leaked into purpose
        purpose = re.sub(r"￥[\d,]+\.?\d*元?\s*", "", purpose).strip()
        # Remove trailing numbers (流水号 leaked in)
        purpose = re.sub(r"\s*\|\s*\d{5,}$", "", purpose).strip()
        desc_parts = [p for p in [purpose, usage] if p]
        description = " | ".join(desc_parts) if desc_parts else "银行回单"

        # --- reference number ---
        ref_no = fields.get("ref_no", "").strip()
        # Clean: remove label text that leaked in
        for noise in ["时间戳", "交易流水号", "记账日期", "备注", "附言",
                       "业务种类", "业务类型", "打印日期"]:
            ref_no = ref_no.replace(noise, "")
        ref_no = ref_no.strip() or None

        # --- notes ---
        note_parts = []
        notes_val = fields.get("notes", "").strip()
        if notes_val:
            note_parts.append(f"备注:{notes_val}")
        postscript = fields.get("postscript", "").strip()
        if postscript:
            note_parts.append(f"附言:{postscript}")
        if payer:
            note_parts.append(f"付款人:{payer}")
        if payee and not counterparty:
            note_parts.append(f"收款人:{payee}")
        receipt_no = fields.get("receipt_no", "").strip()
        if receipt_no:
            note_parts.append(f"回单号:{receipt_no}")
        amount_cn = fields.get("amount_cn", "").strip()
        if amount_cn:
            note_parts.append(f"大写:{amount_cn}")
        combined_notes = " | ".join(note_parts) if note_parts else None

        return Transaction(
            date=tx_date,
            description=description,
            amount=amount,
            currency="CNY",
            direction="expense",
            counterparty=counterparty,
            reference_number=ref_no,
            notes=combined_notes,
        )

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _parse_date(text: str) -> Optional:
        """Parse Chinese date format: 2026年03月26日 or 2026-03-26"""
        if not text:
            return None
        m = re.search(r"(\d{4})[年-](\d{1,2})[月-](\d{1,2})", text)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
            except ValueError:
                pass
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
            except ValueError:
                pass
        return None

    @staticmethod
    def _parse_timestamp_date(ts: str) -> Optional:
        """Parse timestamp like 2026-03-26-19.33.30.354123 → date"""
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", ts)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
            except ValueError:
                pass
        return None

    @staticmethod
    def _parse_amount(text: str) -> Decimal:
        """Parse amount from text like '￥0.22元' or '10,261.00'"""
        if not text:
            return Decimal("0")
        # Remove ￥ and 元
        text = text.replace("￥", "").replace("元", "").strip()
        # Remove commas and spaces
        text = text.replace(",", "").replace("，", "").replace(" ", "")
        m = re.search(r"[\d,]+\.?\d*", text)
        if m:
            return Decimal(m.group().replace(",", ""))
        return Decimal("0")
