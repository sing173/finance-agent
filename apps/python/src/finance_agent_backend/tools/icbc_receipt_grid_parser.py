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
from .shared_utils import BANK_ICBC, parse_date_chinese, parse_timestamp_date, parse_amount_lenient


class ICBCReceiptGridParser:
    """中国工商银行 OCR 回单解析器 (icbc_parser grid方案)"""

    BANK_NAME = BANK_ICBC

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
        blocks.sort(key=lambda b: (b["cy"], b["cx"]))  # 使用中心点排序
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
                result[best_cell[0]][best_cell[1]]["texts"].append(
                    {"text": b["text"], "cx": b["cx"]}
                )

        return result

    # ── stage 6: flatten cells + split receipts ─────────────────

    @staticmethod
    def _flatten_cells(cell_grid, h_coords, v_coords):
        """将 cell_grid 扁平化为 [{row, col, text, y0, x0, cx, cy}, ...]"""
        cells = []
        for ri, row in enumerate(cell_grid):
            for ci, cell in enumerate(row):
                if not cell["texts"]:
                    continue
                # Sort text fragments within cell by x-center to avoid order reversal
                cell["texts"].sort(key=lambda t: t["cx"])
                text = "".join(t["text"] for t in cell["texts"]).strip()
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

    # ── stage 7: cells → fields (固定坐标) ────────────────────────

    def _cells_to_fields(self, rec_cells: List[dict]) -> Dict[str, str]:
        """按固定网格坐标提取回单字段。

        回单布局固定，每回单 11 行 (type A, 标题在第0行) 或 12 行 (type B, 第0行=提示)。

        账户信息3行 (左右两栏):
          户名行(off=0):  [1]户名 [3]付款人户名 [5]户名 [6+7]收款人户名
          账号行(off=1):  [0]付款人 [1]账号 [3]付款人账号 [4]收款人 [5]账号 [6]收款人账号
          开户行(off=2):  [1]开户银行 [3]付款人开户行 [5]开户银行 [6+7]收款人开户行

        后续行:
          off=3 金额:     [1]金额 [3]金额值 [5]金额(大写) [6+7]大写金额
          off=4 摘要:     [1]摘要 [3]摘要值 [5+6]业务种类
          off=5 用途:     [1]用途 [3]用途值
          off=6 流水:     [1]交易流水号 [3]流水号 [5]时间戳 [7]时间戳值
          off=7 备注:     [1]印章(忽略) [3]备注
          off=8 验证码:   [3]验证码
          off=9 记账:     [1]记账网点 [3]柜员 [4]网点号 [6]记账日期 [7]日期值
        """
        grid: Dict[int, Dict[int, str]] = {}
        for c in rec_cells:
            grid.setdefault(c["row"], {})[c["col"]] = c["text"]

        # 找到"户名"行作为基准 (col 1 包含"户名")
        base_row = None
        for r in sorted(grid.keys()):
            if 1 in grid[r] and '户名' in grid[r][1]:
                base_row = r
                break
        if base_row is None:
            return {}

        def cell(offset: int, col: int) -> str:
            r = base_row + offset
            return grid.get(r, {}).get(col, "").strip()

        fields: Dict[str, str] = {}

        # ── 账户信息 ──
        fields["payer_name"] = cell(0, 3)

        # 收款人户名: col6 + col7 是同一个宽单元格
        # col7 是主文本, col6 是换行/溢出片段, 合并时 col7 在前
        fields["payee_name"] = cell(0, 7) + cell(0, 6)

        fields["payer_account"] = cell(1, 3)
        fields["payee_account"] = cell(1, 6)

        fields["payer_bank"] = cell(2, 3)
        fields["payee_bank"] = cell(2, 7) + cell(2, 6)

        # ── 金额 ──
        fields["amount_text"] = cell(3, 3)
        amount_cn = cell(3, 7) or cell(3, 6)
        # 过滤 OCR 残字: 纯"分"/"角"/"柒分"等
        if amount_cn and len(amount_cn) <= 2 and not amount_cn.startswith("人民币"):
            amount_cn = cell(3, 7)  # retry col 7 only
        fields["amount_cn"] = amount_cn

        # ── 摘要 + 业务种类 ──
        fields["purpose"] = cell(4, 3)
        biz_type_raw = cell(4, 5)
        biz_type_extra = cell(4, 6)
        prefix = "业务（产品）种类"
        if biz_type_raw.startswith(prefix):
            fields["business_type"] = biz_type_raw[len(prefix):]
        elif prefix in biz_type_raw:
            fields["business_type"] = biz_type_raw.replace(prefix, "")
        elif biz_type_raw:
            fields["business_type"] = biz_type_raw
        # 如果 col 5 只有 "业务（产品）种类" 而值在 col 6
        if not fields.get("business_type") and biz_type_extra:
            fields["business_type"] = biz_type_extra

        # ── 用途 ──
        fields["usage"] = cell(5, 3)

        # ── 交易流水号 + 时间戳 ──
        fields["ref_no"] = cell(6, 3)
        fields["timestamp"] = cell(6, 7)

        # ── 备注 ──
        fields["notes"] = cell(7, 3)

        # ── 验证码 ──
        verify_raw = cell(8, 3)
        if "验证码" in verify_raw:
            m = re.search(r'[A-Za-z0-9+/=]{20,}', verify_raw)
            if m:
                fields["verify_code"] = m.group()

        # ── 记账信息 ──
        teller_raw = cell(9, 3)
        if "记账柜员" in teller_raw:
            fields["teller"] = teller_raw
        fields["accounting_date"] = cell(9, 7)

        # ── 回单号 (标题行 = base_row - 1) ──
        title_row = base_row - 1
        if title_row in grid:
            title_text = grid[title_row].get(3, "")
            m = re.search(r'\d{4}-\d{4}-\d{4}-\d{4}', title_text)
            if m:
                fields["receipt_no"] = m.group()

        return fields

    # ── stage 8: fields → Transaction ────────────────────────────

    def _fields_to_transaction(self, fields: Dict[str, str]) -> Optional[Transaction]:
        # date: 从记账日期提取, fallback 时间戳
        date_str = fields.get("accounting_date", "")
        tx_date = self._parse_date(date_str)
        if not tx_date:
            ts = fields.get("timestamp", "")
            tx_date = self._parse_timestamp_date(ts)
        if not tx_date:
            return None

        # amount
        amount_text = fields.get("amount_text", "")
        amount = self._parse_amount(amount_text)

        # direction: 付款人包含"中锦" → 我方付款 → expense
        payer_name = fields.get("payer_name", "")
        payee_name = fields.get("payee_name", "")
        is_mine = "中锦" in payer_name

        if is_mine:
            direction = "expense"
            counterparty = payee_name or None
            # 追加收款人账号
            payee_acct = fields.get("payee_account", "")
            if counterparty and payee_acct and "*" not in payee_acct:
                counterparty = f"{counterparty}（{payee_acct}）"
        else:
            direction = "income"
            counterparty = payer_name or None
            payer_acct = fields.get("payer_account", "")
            if counterparty and payer_acct and "*" not in payer_acct:
                counterparty = f"{counterparty}（{payer_acct}）"

        # description: 摘要 + 用途 + 业务种类 (去重)
        parts = []
        for k in ("purpose", "usage", "business_type"):
            v = fields.get(k, "").strip()
            if v and v not in parts:
                parts.append(v)
        description = " | ".join(parts) or "银行回单"

        # ref_no
        ref_no = fields.get("ref_no") or None

        # notes: 去掉 "备注：" 前缀，保留原始内容
        notes_raw = fields.get("notes", "")
        notes = notes_raw.removeprefix("备注：") if notes_raw else None

        return Transaction(
            date=tx_date,
            description=description,
            amount=amount,
            currency="CNY",
            direction=direction,
            counterparty=counterparty,
            reference_number=ref_no,
            notes=notes,
        )

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _parse_date(text: str) -> Optional:
        return parse_date_chinese(text)

    @staticmethod
    def _parse_timestamp_date(ts: str) -> Optional:
        return parse_timestamp_date(ts)

    @staticmethod
    def _parse_amount(text: str) -> Decimal:
        return parse_amount_lenient(text)
