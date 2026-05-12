"""中国工商银行 (ICBC) 交易流水 PDF OCR 解析器

ICBC PDF 是扫描件/图片型，须经 OCR 提取文字。
使用「表格线检测 + 网格分割 + 表头识别」方案：
  1. PDF 渲染为高分辨率图像
  2. OpenCV 形态学操作检测水平/垂直线
  3. 投影法提取线条坐标，构建表格网格
  4. 低阈值 OCR 表头行，自动识别每列的语义
  5. 数据行 OCR → 按网格+表头映射分配到具体单元格
  6. 同行单元格合并为一条交易记录
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

# Header keyword → internal column name
_HEADER_MAP: Dict[str, str] = {
    "日期": "date",
    "交易类型": "type",
    "凭证种类": "type",  # merged with 交易类型
    "凭证号": "ref",
    "对方账号": "ref",  # alternate ref (流水号) — merged with 凭证号
    "对方户名": "counterparty",
    "摘要": "purpose",
    "借方发生额": "amount_out",
    "贷方发生额": "amount_in",
    "余额": "balance",
}


class ICBCParser:
    """中国工商银行 OCR 流水解析器 (table-line grid + header detection)"""

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
            return []

        grid_rows = self._build_grid(h_coords, v_coords)
        col_map = self._detect_header_columns(img, h_coords, v_coords)

        blocks = self._ocr_page_data(img)
        cell_grid = self._assign_blocks(blocks, grid_rows)
        return self._grid_to_transactions(cell_grid, col_map)

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

    # ── header detection ──────────────────────────────────────────

    def _detect_header_columns(
        self, img: np.ndarray, h_coords: List[int], v_coords: List[int]
    ) -> Dict[int, str]:
        """Group header-row OCR text by grid column, then match keywords.

        The header row often has text split across multiple OCR blocks within
        the same cell (e.g. "交易类" + "型" → "交易类型").  We first bucket
        all OCR blocks into grid columns, concatenate, then match.
        """
        if len(h_coords) < 3 or len(v_coords) < 2:
            return {}

        gray = np.array(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).convert("L"))
        _, img_bin = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)

        ocr_result, _ = self._ocr(img_bin)
        if not ocr_result:
            return {}

        # Scan candidate header rows (rows 1-3), pick the one with most
        # keyword matches after per-column concatenation.
        best_score, best_map = 0, {}

        for row_idx in range(1, min(len(h_coords) - 1, 4)):
            hy0, hy1 = h_coords[row_idx], h_coords[row_idx + 1]
            # Collect text blocks per grid column within this row
            col_texts: Dict[int, List[str]] = {
                ci: [] for ci in range(len(v_coords) - 1)
            }
            for box, text, _ in ocr_result:
                yc = (box[0][1] + box[2][1]) / 2
                if not (hy0 <= yc <= hy1):
                    continue
                x0, x1 = int(box[0][0]), int(box[2][0])
                for ci in range(len(v_coords) - 1):
                    if x0 < v_coords[ci + 1] and x1 > v_coords[ci]:
                        col_texts[ci].append(text)
                        break

            # Match keywords against concatenated per-column text
            col_map: Dict[int, str] = {}
            for ci, texts in col_texts.items():
                joined = "".join(texts)
                for keyword, semantic in _HEADER_MAP.items():
                    if keyword in joined:
                        if ci not in col_map:
                            col_map[ci] = semantic

            score = len(col_map)
            if score > best_score:
                best_score, best_map = score, col_map

        return best_map

    # ── data OCR ──────────────────────────────────────────────────

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
            blocks.append(
                {
                    "text": text,
                    "x0": box[0][0],
                    "y0": box[0][1],
                    "x1": box[2][0],
                    "y1": box[2][1],
                    "cx": (box[0][0] + box[2][0]) / 2,
                    "cy": (box[0][1] + box[2][1]) / 2,
                }
            )
        return blocks

    # ── cell assignment ───────────────────────────────────────────

    @staticmethod
    def _assign_blocks(blocks: list, grid_rows: list):
        result = [[{"texts": []} for _ in row] for row in grid_rows]

        for b in blocks:
            best_cell = None
            best_overlap = 0

            for ri, row in enumerate(grid_rows):
                for ci, (cx0, cy0, cx1, cy1) in enumerate(row):
                    ix0 = max(b["x0"], cx0)
                    iy0 = max(b["y0"], cy0)
                    ix1 = min(b["x1"], cx1)
                    iy1 = min(b["y1"], cy1)
                    overlap_w = max(0, ix1 - ix0)
                    overlap_h = max(0, iy1 - iy0)
                    overlap = overlap_w * overlap_h
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_cell = (ri, ci)

            if best_cell and best_overlap > 0:
                result[best_cell[0]][best_cell[1]]["texts"].append(b["text"])
            else:
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

    def _grid_to_transactions(
        self, cell_grid, col_map: Dict[int, str]
    ) -> List[Transaction]:
        transactions = []

        for row in cell_grid:
            if len(row) < 10:
                continue

            # Build col-keyed dict from grid row using col_map
            cols: Dict[str, str] = {}
            for ci, cell in enumerate(row):
                semantic = col_map.get(ci)
                if semantic:
                    text = "".join(cell["texts"])
                    if semantic in cols:
                        cols[semantic] += text
                    else:
                        cols[semantic] = text

            # Check for date
            date_text = cols.get("date", "")
            m = re.search(r"(\d{4}-\d{2}-\d{2})", date_text)
            if not m:
                continue  # skip header / empty rows
            date_str = m.group(1)

            try:
                tx_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            tx = self._cols_to_transaction(tx_date, cols)
            if tx:
                transactions.append(tx)

        return transactions

    @staticmethod
    def _cols_to_transaction(tx_date, cols: Dict[str, str]) -> Optional[Transaction]:
        amount_out = ICBCParser._parse_amount(cols.get("amount_out", ""))
        amount_in = ICBCParser._parse_amount(cols.get("amount_in", ""))

        if amount_in > 0:
            amount, direction = amount_in, "income"
        elif amount_out > 0:
            amount, direction = amount_out, "expense"
        else:
            amount, direction = Decimal("0"), "expense"

        counterparty = cols.get("counterparty", "").strip() or None
        purpose = cols.get("purpose", "").strip()
        type_text = cols.get("type", "").strip()
        if type_text and type_text not in purpose:
            description = f"{type_text} | {purpose}" if purpose else type_text
        else:
            description = purpose or "银行交易"

        ref_no = cols.get("ref", "").strip().replace("|", "") or None
        if ref_no:
            ref_no = re.sub(r"[^\d*]+$", "", ref_no)

        balance_str = cols.get("balance", "").strip()

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
    def _parse_amount(text: str) -> Decimal:
        text = text.strip().replace(",", "").replace(" ", "")
        m = re.search(r"[\d,]+\.?\d*", text)
        if m:
            return Decimal(m.group().replace(",", ""))
        return Decimal("0")
