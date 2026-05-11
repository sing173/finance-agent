"""中国工商银行 (ICBC) 交易流水 PDF OCR 解析器

ICBC PDF 是扫描件/图片型，须经 OCR 提取文字。
OCR 产出平铺文本块带坐标，此解析器按空间布局（y-band + x-column）
将文本块重组为结构化交易记录。

ICBC 表格列布局（200 DPI 参考坐标）:
  日期:     x  83-190
  凭证类型: x 200-260
  流水号:   x 415-880
  对方户名: x 880-985  (多行)
  摘要:     x 985-1100
  借方金额: x 1098-1210
  贷方金额: x 1255-1380
  余额:     x 1420-1560
"""
import re
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from ..models import Transaction, ParseResult


class ICBCParser:
    """中国工商银行 OCR 流水解析器"""

    BANK_NAME = "中国工商银行"

    # 列边界 (x 坐标, 200 DPI)
    COL_DATE = (80, 190)
    COL_TYPE = (190, 280)
    COL_REF = (400, 880)
    COL_COUNTERPARTY = (880, 985)
    COL_PURPOSE = (985, 1095)
    COL_AMOUNT_OUT = (1095, 1225)
    COL_AMOUNT_IN = (1225, 1400)
    COL_BALANCE = (1400, 1600)

    def __init__(self):
        self.confidence = 1.0

    def parse(self, ocr_result: dict) -> ParseResult:
        """从 OCR 结果解析交易记录。

        ocr_result 格式: {"pages": [...], "total_pages": N, "full_text": "..."}
        每个 page: {"page": N, "blocks": [{"text":..., "confidence":..., "box":...}], ...}
        """
        transactions = []
        errors = []
        warnings = []

        for page in ocr_result.get("pages", []):
            try:
                page_tx = self._parse_page(page["blocks"])
                transactions.extend(page_tx)
            except Exception as e:
                errors.append(f"Page {page['page'] + 1}: {e}")
                self.confidence -= 0.02

        statement_date = transactions[-1].date if transactions else None

        return ParseResult(
            transactions=transactions,
            bank=self.BANK_NAME,
            statement_date=statement_date,
            confidence=self.confidence,
            errors=errors,
            warnings=warnings,
        )

    def _parse_page(self, blocks: list[dict]) -> List[Transaction]:
        """解析单页的 OCR 文本块 -> 交易记录列表

        策略：每笔交易由一个日期前缀块 (YYYY-MM-) 锚定。
        块分配到最近的「上方」日期前缀。

        特殊情况：counterparty/description 的换行文本在下一笔日期上方，
        须按就近原则分配——如果块到下方日期的距离 < 到上方日期距离的 0.6 倍，
        则分配到下方。
        """
        sorted_blocks = sorted(blocks, key=lambda b: (b["box"][0][1], b["box"][0][0]))

        # Step 1: 找到所有日期前缀及其 y-center
        date_items = []  # list of (i, yc, block)
        for i, b in enumerate(sorted_blocks):
            if self._is_date_prefix(b):
                yc = (b["box"][0][1] + b["box"][2][1]) / 2
                date_items.append((i, yc, b))

        if not date_items:
            return []

        # Step 2: 分配每个块到日期组。
        # 规则：块在两个日期之间时，默认分配到上方日期；
        # 仅当块 y-center 在下一日期 y-center 的 15px 以内时，分配到下方日期。
        GROW_DIST = 15  # 距下一日期的"归属范围"

        for i, b in enumerate(sorted_blocks):
            if self._is_date_prefix(b) or self._is_header_block(b):
                continue

            b_yc = (b["box"][0][1] + b["box"][2][1]) / 2

            best_gi = -1
            for gi in range(len(date_items)):
                date_yc = date_items[gi][1]
                if b_yc < date_yc:
                    if gi > 0:
                        # 距下方日期足够近 → 分配给它；否则分配上方
                        if date_yc - b_yc <= GROW_DIST:
                            best_gi = gi
                        else:
                            best_gi = gi - 1
                    else:
                        best_gi = -1
                    break
            if best_gi == -1 and b_yc >= date_items[0][1]:
                best_gi = len(date_items) - 1

            if best_gi >= 0:
                groups[best_gi].append(b)

        # Step 3: 每个日期 + 其分配的块组成一个交易
        transactions = []
        for (_, _, date_b), group_blocks in zip(date_items, groups):
            row_blocks = [date_b] + group_blocks
            try:
                tx = self._parse_row(row_blocks)
                if tx:
                    transactions.append(tx)
            except Exception:
                self.confidence -= 0.005

        return transactions

    @staticmethod
    def _is_header_block(b: dict) -> bool:
        """识别页眉/标题块（非数据行的块）"""
        text = b["text"].strip()
        # 银行名、网点号、币种、账号、户名等
        return bool(re.match(
            r"^(中国工商银行|网点号|币种|账号|户名|下一页|打印|返回|\d+年\d+月)",
            text
        ))

    def _is_date_prefix(self, block: dict) -> bool:
        """检查是否为日期前缀，如 '2026-03-'"""
        text = block["text"].strip()
        box = block["box"]
        x0 = box[0][0]
        return (
            re.match(r"^\d{4}-\d{2}-$", text)
            and x0 < self.COL_DATE[1]
        )

    def _parse_row(self, blocks: list[dict]) -> Optional[Transaction]:
        """解析一组属于同一交易的文本块"""
        cols = {
            "date": [],
            "type": [],
            "ref": [],
            "counterparty": [],
            "purpose": [],
            "amount_out": [],
            "amount_in": [],
            "balance": [],
        }

        for b in blocks:
            text = b["text"].strip()
            if not text:
                continue
            x0 = b["box"][0][0]

            col = self._classify_column(x0)
            if col:
                cols[col].append((b["box"][0][1], text))

        # 按 y 坐标排序每列，然后拼接文本
        for key in cols:
            cols[key].sort(key=lambda item: item[0])
            cols[key] = "".join(item[1] for item in cols[key])

        # --- 拼接日期 ---
        # date 列包含: YYYY-MM- 前缀块 + DD 后缀块
        date_text = cols["date"].strip()
        # 如果已经是完整日期，直接使用
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_text):
            date_str = date_text
        else:
            # 分离前缀和日部分
            prefix_m = re.match(r"^(\d{4}-\d{2}-)", date_text)
            day_m = re.search(r"(\d{2})$", date_text)
            if prefix_m and day_m:
                date_str = prefix_m.group(1) + day_m.group(1)
            else:
                # date_text 可能只有前缀，搜索 blocks 里 y 接近的纯数字块
                date_try = date_text
                for b in blocks:
                    text = b["text"].strip()
                    x0 = b["box"][0][0]
                    if (x0 < 130 and re.match(r"^\d{2}$", text)):
                        date_try += text
                        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_try):
                            break
                date_str = date_try

        try:
            tx_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

        # --- 金额 ---
        amount_out = self._parse_amount(cols["amount_out"])
        amount_in = self._parse_amount(cols["amount_in"])

        if amount_in > 0:
            amount = amount_in
            direction = "income"
        elif amount_out > 0:
            amount = amount_out
            direction = "expense"
        else:
            amount = Decimal("0")
            direction = "expense"

        # --- 对方户名 (拼接多行) ---
        counterparty = cols["counterparty"].strip() or None

        # --- 摘要 (拼接多行) ---
        description = cols["purpose"].strip() or cols["type"].strip() or "银行交易"

        # 如果 type 列有值且不是描述的一部分，加到描述前面
        type_text = cols["type"].strip()
        if type_text and type_text not in description:
            description = f"{type_text} | {description}" if description else type_text

        # --- 流水号 ---
        ref_no = cols["ref"].strip() or None
        # 清理流水号中的非数字非星号字符
        if ref_no:
            ref_no = ref_no.replace(" ", "")

        # --- 余额 ---
        balance_str = cols["balance"].strip()

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

    def _classify_column(self, x: int) -> Optional[str]:
        """根据 x 坐标分类到列"""
        if self.COL_DATE[0] <= x <= self.COL_DATE[1]:
            return "date"
        if self.COL_TYPE[0] <= x <= self.COL_TYPE[1]:
            return "type"
        if self.COL_REF[0] <= x <= self.COL_REF[1]:
            return "ref"
        if self.COL_COUNTERPARTY[0] <= x <= self.COL_COUNTERPARTY[1]:
            return "counterparty"
        if self.COL_PURPOSE[0] <= x <= self.COL_PURPOSE[1]:
            return "purpose"
        if self.COL_AMOUNT_OUT[0] <= x <= self.COL_AMOUNT_OUT[1]:
            return "amount_out"
        if self.COL_AMOUNT_IN[0] <= x <= self.COL_AMOUNT_IN[1]:
            return "amount_in"
        if self.COL_BALANCE[0] <= x <= self.COL_BALANCE[1]:
            return "balance"
        return None

    @staticmethod
    def _parse_amount(text: str) -> Decimal:
        """解析金额字符串"""
        text = text.strip().replace(",", "").replace(" ", "")
        # 匹配数字（含小数点）
        m = re.search(r"[\d,]+\.?\d*", text)
        if m:
            return Decimal(m.group().replace(",", ""))
        return Decimal("0")
