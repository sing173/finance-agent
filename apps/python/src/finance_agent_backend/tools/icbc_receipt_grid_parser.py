"""中国工商银行 (ICBC) 回单 PDF OCR 解析器 — 网格线方案

核心思路（复用 icbc_parser 的网格方案）：
  1. PDF 渲染 + OpenCV 检测 H/V 线（80x1 / 1x80 kernel）
  2. 投影法提取线条坐标 → 构建网格（23行×8列）
  3. RapidOCR 全页识别 → 按重叠面积分配到网格单元格
  4. 同行相邻单元格合并为完整字段
  5. 固定列映射提取各字段（标签在col1, 值在col3/5/7）
  6. 回单行按"标题行 + 数据行 + 标题行 + 数据行"动态切分

关键发现：
  - 第0/1页表格线坐标完全一致 → 所有页共用同一网格
  - 每页2个回单，中间有空行间隔
  - Col 1=标签, Col 3=值左, Col 5=值右, Col 7=时间戳/验证码
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


class ICBCReceiptGridParser:
    """中国工商银行 OCR 回单解析器 (icbc_parser grid方案)"""

    BANK_NAME = "中国工商银行"

    # ── 固定列映射（基于第0页调试结论）────────────────────────
    # col 0-7 对应 V coords: [307, 391, 617, 629, 1246, 1327, 1565, 1792, 2185]
    # 0=[307,391]    1=[391,617]  2=[617,629]  3=[629,1246]
    # 4=[1246,1327]  5=[1327,1565] 6=[1565,1792] 7=[1792,2185]
    #
    # 标签区: col 1 (x=391~617)
    # 值区:   col 3 (x=629~1246) 和 col 5 (x=1327~1565)
    # 右侧:   col 7 (x=1792~2185) — 验证码/时间戳/打印日期
    # 间隔列: col 0/2/4/6  ← 包含一些辅助信息

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
        h_coords, v_coords = self._detect_table_lines(img)

        # 必须有足够的行列才能构建网格
        if len(h_coords) < 10 or len(v_coords) < 5:
            return []

        grid_rows = self._build_grid(h_coords, v_coords)
        blocks = self._ocr_page_data(img)
        cell_grid = self._assign_blocks(blocks, grid_rows)

        # 从网格提取字段，再切分为回单
        all_cells = self._flatten_cells(cell_grid, h_coords, v_coords)
        receipts = self._split_receipts(all_cells)

        transactions = []
        for receipt_cells in receipts:
            fields = self._cells_to_fields(receipt_cells)
            tx = self._fields_to_transaction(fields)
            if tx:
                transactions.append(tx)
        return transactions

    # ── stage 1: render ──────────────────────────────────────────

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

    # ── stage 2: detect table lines ──────────────────────────────

    @staticmethod
    def _detect_table_lines(img: np.ndarray):
        """用 80×1 水平核 + 1×80 垂直核 检测表格线"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1))
        h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)

        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80))
        v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

        return (
            ICBCReceiptGridParser._extract_positions(h_lines, axis=1),
            ICBCReceiptGridParser._extract_positions(v_lines, axis=0),
        )

    @staticmethod
    def _extract_positions(line_img: np.ndarray, axis: int) -> List[int]:
        """投影法提取线条坐标"""
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

    # ── stage 3: build grid ──────────────────────────────────────

    @staticmethod
    def _build_grid(h_lines_y: List[int], v_lines_x: List[int]):
        """构建网格：每行每列的交叉区域为一个单元格"""
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

    # ── stage 4: OCR ─────────────────────────────────────────────

    def _ocr_page_data(self, img: np.ndarray) -> list:
        """全页 OCR，返回按 y 排序的文本块列表"""
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

    # ── stage 5: assign blocks to grid cells ─────────────────────

    @staticmethod
    def _assign_blocks(blocks: list, grid_rows: list):
        """按重叠面积将 OCR 块分配到网格单元格"""
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

        return result

    # ── stage 6: flatten cells + split receipts ─────────────────

    @staticmethod
    def _flatten_cells(cell_grid, h_coords, v_coords):
        """将 cell_grid 扁平化为 [{row, col, text, y0, x0, cx, cy}, ...]"""
        cells = []
        for ri, row in enumerate(cell_grid):
            for ci, cell in enumerate(row):
                text = "".join(cell["texts"]).strip()
                if not text:
                    continue
                cx0, cy0, cx1, cy1 = v_coords[ci], h_coords[ri], v_coords[ci+1], h_coords[ri+1]
                cells.append({
                    "row": ri, "col": ci,
                    "text": text,
                    "y0": cy0, "y1": cy1,
                    "x0": cx0, "x1": cx1,
                    "cx": (cx0 + cx1) / 2, "cy": (cy0 + cy1) / 2,
                })
        return cells

    def _split_receipts(self, cells: list) -> List[List[dict]]:
        """从扁平化单元格切分回单。

        策略:
          1. 找所有含"网上银行电子回单"或"电子回单号码"的行
          2. 合并连续/接近的标题行（间距≤3行视为同一回单的多行表头）
          3. 对每组标题行，向上查找最近的"中国工商银行"（最多2行距离）
          4. 用该银行名行作为回单起点，下一组起点前一行作为终点
        """
        # 找标题行索引
        title_rows = sorted(set(
            c["row"] for c in cells
            if "网上银行电子回单" in c["text"] or "电子回单号码" in c["text"]
        ))

        if not title_rows:
            return []

        # 合并连续的标题行（间距≤3行视为同一回单的多行表头）
        merged_title_groups = []
        current_group = [title_rows[0]]
        for tr in title_rows[1:]:
            if tr - current_group[-1] <= 3:
                current_group.append(tr)
            else:
                merged_title_groups.append(current_group)
                current_group = [tr]
        merged_title_groups.append(current_group)

        # 对每组标题行，找对应的银行名行作为回单起点
        start_rows = []
        for group in merged_title_groups:
            first_title_row = group[0]
            # 向上查找"中国工商银行"，最多2行距离
            bank_row = None
            for c in cells:
                if c["row"] < first_title_row and "中国工商银行" in c["text"]:
                    if first_title_row - c["row"] <= 2:
                        bank_row = c["row"]
                        break
            if bank_row is not None:
                start_rows.append(bank_row)
            else:
                # 没找到银行名，用标题组第一行
                start_rows.append(first_title_row)

        start_rows = sorted(set(start_rows))
        if not start_rows:
            return []

        # 切分回单
        receipts = []
        for idx, sr in enumerate(start_rows):
            if idx + 1 < len(start_rows):
                end_row = start_rows[idx + 1] - 1
            else:
                end_row = max(c["row"] for c in cells)
            rec_cells = [c for c in cells if sr <= c["row"] <= end_row]
            if rec_cells:
                receipts.append(rec_cells)

        return receipts

    # ── stage 7: cells → fields ─────────────────────────────────

    def _cells_to_fields(self, rec_cells: List[dict]) -> Dict[str, str]:
        """从回单单元格列表提取字段。

        核心列映射（基于调试结论）:
          col 1 (x=391~617): 标签区（付款人/收款人/金额等）
          col 3 (x=629~1246): 值区左（账户名/账号/金额等）
          col 5 (x=1327~1565): 值区右（摘要/大写金额等）
          col 6 (x=1565~1792): 值区右2（付款人户名/收款人账号等）
          col 7 (x=1792~2185): 时间戳/验证码/打印日期
        """
        import sys
        print("DEBUG: _cells_to_fields called", file=sys.stderr)
        fields: Dict[str, str] = {}

        # 构建按 row → cell 的映射
        row_cells: Dict[int, Dict[int, dict]] = {}
        for c in rec_cells:
            ri = c["row"]
            if ri not in row_cells:
                row_cells[ri] = {}
            row_cells[ri][c["col"]] = c

        # 优先从 col 0/1 提取标签行
        label_cells = sorted(
            [c for c in rec_cells if c["col"] in (0, 1)],
            key=lambda c: (c["row"], c["col"])
        )

        # 将标签与值配对
        for lc in label_cells:
            label_text = lc["text"].strip()
            ri = lc["row"]
            # 匹配标签关键词
            field_name = self._label_to_field(label_text)
            if not field_name:
                continue

            # 优先从同 row 的 col 3/5/6 取值
            val = ""
            if ri in row_cells:
                value_cols = [3, 5, 6]
                if field_name in ("payer", "payee", "payer_account", "payee_account"):
                    value_cols = [6, 3, 5]

                for col in value_cols:
                    if col in row_cells[ri]:
                        candidate = row_cells[ri][col]["text"].strip()
                        # 对于金额类字段，优先取有数字的
                        if field_name in ("amount_text", "amount_cn"):
                            if any(c.isdigit() for c in candidate):
                                val = candidate
                                break
                        # 跳过标签文本
                        elif candidate != label_text and len(candidate) > 1:
                            # 跳过常见 OCR 误识别片段
                            ocr_garbage = {'号账', '户', '账号', '户名', '付款人', '收款人', '开户银行'}
                            if candidate in ocr_garbage:
                                continue
                            # 对于 payer/payee，跳过纯数字和掩码账号
                            if field_name in ("payer", "payee", "payer_account", "payee_account"):
                                if candidate.isdigit() or '*' in candidate:
                                    continue
                            val = candidate
                            break

            # 特殊布局：付款人/收款人在 col 0/4，名字在上一行 col 6/3
            if not val and field_name in ("payer", "payee"):
                if lc["col"] == 0 and field_name == "payer":  # 付款人 at col 0
                    prev_ri = ri - 1
                    if prev_ri in row_cells:
                        for col in [6, 3, 5]:
                            if col in row_cells[prev_ri]:
                                candidate = row_cells[prev_ri][col]["text"].strip()
                                if candidate and len(candidate) > 1 and not candidate.isdigit() and '*' not in candidate:
                                    val = candidate
                                    break
                elif lc["col"] == 4 and field_name == "payee":  # 收款人 at col 4
                    prev_ri = ri - 1
                    if prev_ri in row_cells:
                        for col in [3, 6, 5]:
                            if col in row_cells[prev_ri]:
                                candidate = row_cells[prev_ri][col]["text"].strip()
                                if candidate and len(candidate) > 1 and not candidate.isdigit() and '*' not in candidate:
                                    val = candidate
                                    break

            fields[field_name] = val

        # col 7 单独处理（验证码/时间戳/打印日期）
        for c in rec_cells:
            if c["col"] == 7:
                text = c["text"].strip()
                if "验证码" in text:
                    m = re.search(r'[A-Za-z0-9+/=]{20,}', text)
                    if m:
                        fields["verify_code"] = m.group()
                elif re.match(r'\d{4}-\d{2}-\d{2}', text):
                    fields["timestamp"] = text

        # col 0 补充：回单号
        for c in rec_cells:
            if c["col"] == 0:
                m = re.search(r'\d{4}-\d{4}-\d{4}-\d{4}', c["text"])
                if m:
                    fields["receipt_no"] = m.group()
                    break

        return fields

    # ── 标签 → 字段名映射 ───────────────────────────────────────

    @staticmethod
    def _label_to_field(label_text: str) -> Optional[str]:
        """将标签文本映射到字段名"""
        mapping = {
            "账户名称": "account_name",
            "户名": "account_name",
            "账户账号": "account_number",
            "开户银行": "bank_name",
            "金额": "amount_text",
            "金额(大写)": "amount_cn",
            "付款人": "payer",
            "付款账号": "payer_account",
            "收款人": "payee",
            "收款账号": "payee_account",
            "摘要": "purpose",
            "用途": "usage",
            "交易流水号": "ref_no",
            "记账日期": "date",
            "打印日期": "print_date",
            "备注": "notes",
            "附言": "postscript",
            "时间戳": "timestamp",
            "验证码": "verify_code",
        }
        for key, field in mapping.items():
            if key in label_text:
                return field
        return None

    # ── stage 8: fields → Transaction ────────────────────────────

    def _fields_to_transaction(self, fields: Dict[str, str]) -> Optional[Transaction]:
        # date
        date_str = fields.get("date", "")
        tx_date = self._parse_date(date_str)
        if not tx_date:
            ts = fields.get("timestamp", "")
            tx_date = self._parse_timestamp_date(ts)
        if not tx_date:
            return None

        # amount
        amount_text = fields.get("amount_text", "")
        amount = self._parse_amount(amount_text)

        # direction: if we have both payee and payer, use payee as default (incoming)
        # for expense (debit/outgoing), counterparty = payee
        # for income (credit/incoming), counterparty = payer
        # We'll determine direction after we check the fields
        payer = fields.get("payer", "").strip()
        payee = fields.get("payee", "").strip()

        # counterparty
        counterparty = None
        # 不排除银行名称（工商银行/农业银行等），因为收/付款方可能是银行
        if payee:
            counterparty = payee
        elif payer:
            counterparty = payer

        # description
        purpose = fields.get("purpose", "")
        usage = fields.get("usage", "")
        desc_parts = [p for p in [purpose, usage] if p and len(p) > 1]
        description = " | ".join(desc_parts) if desc_parts else "银行回单"

        # ref_no
        ref_no = fields.get("ref_no", "").strip() or None

        # notes
        note_parts = []
        for key in ["notes", "postscript", "receipt_no"]:
            v = fields.get(key, "").strip()
            if v:
                note_parts.append(f"{key}:{v}")
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
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", ts)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
            except ValueError:
                pass
        return None

    @staticmethod
    def _parse_amount(text: str) -> Decimal:
        if not text:
            return Decimal("0")
        text = text.replace("￥", "").replace("元", "").strip()
        text = text.replace(",", "").replace("，", "").replace(" ", "")
        m = re.search(r"[\d,]+\.?\d*", text)
        if m:
            return Decimal(m.group().replace(",", ""))
        return Decimal("0")
