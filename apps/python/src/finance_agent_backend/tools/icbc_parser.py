"""中国工商银行 (ICBC) 交易流水 PDF OCR 解析器

ICBC PDF 是扫描件/图片型，须经 OCR 提取文字。
使用「表格线检测 + 网格分割」方案：
  1. PDF 渲染为高分辨率图像
  2. OpenCV 形态学操作检测水平/垂直线
  3. 投影法提取线条坐标，构建表格网格
  4. OCR 文字块按网格分配到具体单元格
  5. 同行的单元格合并为一条交易记录
"""
import re
from datetime import datetime
from decimal import Decimal
from itertools import groupby
from typing import List, Optional

import cv2
import fitz
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from ..models import Transaction, ParseResult

# Grid column indices → semantic meaning (300 DPI, 10 detected columns)
_COL_DATE = 0
_COL_TYPE = 1
_COL_REF = (3, 4)  # 凭证号/流水号 spans two grid cols
_COL_COUNTERPARTY = 5
_COL_PURPOSE = 6
_COL_AMOUNT_OUT = 7
_COL_AMOUNT_IN = 8
_COL_BALANCE = 9


class ICBCParser:
    """中国工商银行 OCR 流水解析器 (table-line grid approach)"""

    BANK_NAME = "中国工商银行"

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
        transactions = []
        errors = []

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
        h_coords, v_coords = self._detect_table_lines(img)
        if len(h_coords) < 3 or len(v_coords) < 3:
            return []  # no table on this page
        grid_rows = self._build_grid(h_coords, v_coords)
        blocks = self._ocr_page(img)
        cell_grid = self._assign_blocks(blocks, grid_rows)
        return self._grid_to_transactions(cell_grid)

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

    @staticmethod
    def _detect_table_lines(img: np.ndarray):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1))
        h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)

        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80))
        v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

        return (
            ICBCParser._extract_positions(h_lines, axis=1),
            ICBCParser._extract_positions(v_lines, axis=0),
        )

    @staticmethod
    def _extract_positions(line_img: np.ndarray, axis: int) -> List[int]:
        projection = np.sum(line_img, axis=axis) / 255.0
        threshold = max(np.max(projection) * 0.15, 10)
        positions = np.where(projection > threshold)[0]
        if len(positions) == 0:
            return []

        grouped = []
        for k, g in groupby(enumerate(positions), lambda x: x[0] - x[1]):
            group = list(g)
            grouped.append(int(np.mean([x[1] for x in group])))

        merged = []
        for pos in grouped:
            if not merged or pos - merged[-1] > 5:
                merged.append(pos)
            else:
                merged[-1] = int((merged[-1] + pos) / 2)
        return merged

    @staticmethod
    def _build_grid(h_lines_y: List[int], v_lines_x: List[int]):
        rows = []
        for i in range(len(h_lines_y) - 1):
            y0, y1 = h_lines_y[i], h_lines_y[i + 1]
            if y1 - y0 < 8:
                continue
            cells = []
            for j in range(len(v_lines_x) - 1):
                x0, x1 = v_lines_x[j], v_lines_x[j + 1]
                if x1 - x0 < 5:
                    continue
                cells.append((x0, y0, x1, y1))
            rows.append(cells)
        return rows

    # ── OCR ───────────────────────────────────────────────────────

    def _ocr_page(self, img: np.ndarray) -> list:
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        img_np = np.array(pil_img.convert("L"))
        _, img_bin = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        ocr_result, _ = self._ocr(img_bin)
        if not ocr_result:
            return []

        blocks = []
        for box, text, _confidence in ocr_result:
            blocks.append({
                "text": text,
                "cx": (box[0][0] + box[2][0]) / 2,
                "cy": (box[0][1] + box[2][1]) / 2,
            })
        return blocks

    # ── cell assignment ───────────────────────────────────────────

    @staticmethod
    def _assign_blocks(blocks: list, grid_rows: list):
        result = [[{"texts": []} for _ in row] for row in grid_rows]

        for b in blocks:
            best_ri = min(
                range(len(grid_rows)),
                key=lambda ri: abs(
                    (grid_rows[ri][0][1] + grid_rows[ri][0][3]) / 2 - b["cy"]
                ),
            )
            row = grid_rows[best_ri]
            best_ci = min(
                range(len(row)),
                key=lambda ci: abs((row[ci][0] + row[ci][2]) / 2 - b["cx"]),
            )
            result[best_ri][best_ci]["texts"].append(b["text"])
        return result

    # ── grid → transactions ───────────────────────────────────────

    def _grid_to_transactions(self, cell_grid) -> List[Transaction]:
        transactions = []
        for row in cell_grid:
            if len(row) < 10:
                continue

            date_text = "".join(row[_COL_DATE]["texts"])
            if not re.search(r"\d{4}-\d{2}-\d{2}", date_text):
                continue  # skip header / empty rows

            tx = self._row_to_transaction(row)
            if tx:
                transactions.append(tx)

        return transactions

    def _row_to_transaction(self, row) -> Optional[Transaction]:
        date_str = self._extract_date(row)
        if not date_str:
            return None
        try:
            tx_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

        amount_out = self._parse_amount(row[_COL_AMOUNT_OUT]["texts"])
        amount_in = self._parse_amount(row[_COL_AMOUNT_IN]["texts"])

        if amount_in > 0:
            amount, direction = amount_in, "income"
        elif amount_out > 0:
            amount, direction = amount_out, "expense"
        else:
            amount, direction = Decimal("0"), "expense"

        counterparty = "".join(row[_COL_COUNTERPARTY]["texts"]).strip() or None
        description = "".join(row[_COL_PURPOSE]["texts"]).strip() or "银行交易"
        type_text = "".join(row[_COL_TYPE]["texts"]).strip()
        if type_text and type_text not in description:
            description = f"{type_text} | {description}"

        ref_texts = []
        for ci in _COL_REF:
            ref_texts.extend(row[ci]["texts"])
        ref_no = "".join(ref_texts).strip().replace("|", "") or None
        # Remove trailing non-digit/non-asterisk garbage (OCR bleed from other cells)
        if ref_no:
            ref_no = re.sub(r"[^\d*]+$", "", ref_no)

        balance_str = "".join(row[_COL_BALANCE]["texts"]).strip()

        return Transaction(
            date=tx_date,
            description=description,
            amount=amount,
            currency="CNY",
            direction=direction,
            counterparty=counterparty,
            reference_number=ref_no,
            notes=balance_str if balance_str else None,
        )

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _extract_date(row) -> Optional[str]:
        joined = "".join(row[_COL_DATE]["texts"])
        m = re.search(r"(\d{4}-\d{2}-\d{2})", joined)
        return m.group(1) if m else None

    @staticmethod
    def _parse_amount(texts: list) -> Decimal:
        text = "".join(texts).strip().replace(",", "").replace(" ", "")
        m = re.search(r"[\d,]+\.?\d*", text)
        if m:
            return Decimal(m.group().replace(",", ""))
        return Decimal("0")
