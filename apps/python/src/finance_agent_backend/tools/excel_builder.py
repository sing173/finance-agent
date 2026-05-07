"""Excel builder for reconciliation results using openpyxl"""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from typing import List
from decimal import Decimal

from ..models import Transaction, ReconcileResult


class ExcelBuilder:
    """对账结果 Excel 生成器"""

    def build(self, result: ReconcileResult, output_path: str) -> str:
        """生成 5 个工作表"""
        wb = openpyxl.Workbook()

        # 删除默认 Sheet
        wb.remove(wb.active)

        # 1. 对账摘要
        ws_summary = wb.create_sheet('对账摘要')
        self._write_summary(ws_summary, result)

        # 2. 已匹配
        ws_matched = wb.create_sheet('已匹配')
        self._write_transactions(
            ws_matched,
            [m['bank'] for m in result.matched],
            fill=PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid'),
        )

        # 3. 银行未达
        ws_bank_unreconciled = wb.create_sheet('银行未达')
        self._write_transactions(
            ws_bank_unreconciled,
            result.bank_unreconciled,
            fill=PatternFill(start_color='FFEB9C', end_color='FFEB9C', fill_type='solid'),
        )

        # 4. 台账未达
        ws_ledger_unreconciled = wb.create_sheet('台账未达')
        self._write_transactions(
            ws_ledger_unreconciled,
            result.ledger_unreconciled,
            fill=PatternFill(start_color='FFEB9C', end_color='FFEB9C', fill_type='solid'),
        )

        # 5. 可疑匹配
        ws_suspicious = wb.create_sheet('可疑匹配')
        self._write_transactions(
            ws_suspicious,
            [s['bank'] for s in result.suspicious],
            fill=PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid'),
        )

        # 自动调整列宽
        for ws in [ws_summary, ws_matched, ws_bank_unreconciled, ws_ledger_unreconciled, ws_suspicious]:
            self._auto_width(ws)

        # 保存
        wb.save(output_path)
        return output_path

    def _write_summary(self, ws, result: ReconcileResult):
        """写入摘要统计"""
        ws['A1'] = '对账结果摘要'
        ws['A1'].font = Font(bold=True, size=14)
        ws.merge_cells('A1:B1')

        total = len(result.matched) + len(result.bank_unreconciled) + len(result.ledger_unreconciled)

        ws['A3'] = '总交易数'
        ws['B3'] = total

        ws['A4'] = '已匹配'
        ws['B4'] = len(result.matched)

        ws['A5'] = '银行未达'
        ws['B5'] = len(result.bank_unreconciled)

        ws['A6'] = '台账未达'
        ws['B6'] = len(result.ledger_unreconciled)

        ws['A7'] = '可疑匹配'
        ws['B7'] = len(result.suspicious)

        ws['A8'] = '匹配率'
        ws['B8'] = f'{result.match_rate * 100:.1f}%'

        # 标题列样式
        for row in range(3, 9):
            ws.cell(row=row, column=1).font = Font(bold=True)

    def _write_transactions(self, ws, transactions: List[Transaction], fill=None):
        """写入交易列表"""
        headers = ['日期', '描述', '金额', '币种', '方向', '对方户名', '流水号']

        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
            cell.alignment = Alignment(horizontal='center')

        for row, t in enumerate(transactions, start=2):
            ws.cell(row=row, column=1, value=t.date.isoformat())
            ws.cell(row=row, column=2, value=t.description)
            ws.cell(row=row, column=3, value=float(t.amount))
            ws.cell(row=row, column=4, value=t.currency)
            ws.cell(row=row, column=5, value=t.direction)
            ws.cell(row=row, column=6, value=t.counterparty)
            ws.cell(row=row, column=7, value=t.reference_number)

            if fill:
                for col in range(1, 8):
                    ws.cell(row=row, column=col).fill = fill

        # 冻结首行
        ws.freeze_panes = 'A2'

    def _auto_width(self, ws):
        """自动调整列宽"""
        for col in ws.columns:
            # 使用 column 属性而非 column_letter 避免 MergedCell 问题
            column_letter = get_column_letter(col[0].column)
            max_length = 0
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
