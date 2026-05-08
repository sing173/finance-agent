"""Excel builder for bank statement transactions using openpyxl"""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from typing import List

from ..models import Transaction


class ExcelBuilder:
    """交易流水 Excel 导出器"""

    def build(self, transactions: List[Transaction], output_path: str) -> str:
        """导出交易列表到 Excel"""
        wb = openpyxl.Workbook()

        # 交易明细
        ws = wb.active
        ws.title = '交易明细'
        ws['A1'] = '银行流水明细'
        ws['A1'].font = Font(bold=True, size=14)
        ws.merge_cells('A1:G1')

        # 统计
        income_count = sum(1 for t in transactions if t.direction == 'income')
        expense_count = sum(1 for t in transactions if t.direction == 'expense')
        total_income = sum(t.amount for t in transactions if t.direction == 'income')
        total_expense = sum(t.amount for t in transactions if t.direction == 'expense')

        stats = [
            ('总交易数', len(transactions)),
            ('收入笔数', income_count),
            ('支出笔数', expense_count),
            ('收入合计', float(total_income)),
            ('支出合计', float(total_expense)),
        ]
        ws['A3'] = '统计摘要'
        ws['A3'].font = Font(bold=True, size=12)
        for i, (label, value) in enumerate(stats, start=4):
            ws.cell(row=i, column=1, value=label).font = Font(bold=True)
            ws.cell(row=i, column=2, value=value)

        # 交易列表
        data_start = len(stats) + 5
        headers = ['日期', '描述', '金额', '币种', '方向', '对方户名', '流水号']
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=data_start, column=col, value=header)
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
            cell.alignment = Alignment(horizontal='center')

        for row, t in enumerate(transactions, start=data_start + 1):
            ws.cell(row=row, column=1, value=t.date.isoformat())
            ws.cell(row=row, column=2, value=t.description)
            ws.cell(row=row, column=3, value=float(t.amount))
            ws.cell(row=row, column=4, value=t.currency)
            ws.cell(row=row, column=5, value=t.direction)
            ws.cell(row=row, column=6, value=t.counterparty)
            ws.cell(row=row, column=7, value=t.reference_number)

        ws.freeze_panes = f'A{data_start + 1}'
        self._auto_width(ws)
        wb.save(output_path)
        return output_path

    def _auto_width(self, ws):
        """自动调整列宽"""
        for col in ws.columns:
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
