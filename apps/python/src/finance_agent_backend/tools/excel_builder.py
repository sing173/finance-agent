"""Excel builder for bank statement transactions using openpyxl"""
import calendar
import json
import os
import sys
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from ..models import Subject, Transaction, VoucherEntry


class ExcelBuilder:
    """交易流水 Excel 导出器"""

    # ------------------------------------------------------------------ #
    #  原有方法：导出原始流水明细                                             #
    # ------------------------------------------------------------------ #

    def build(self, transactions: List[Transaction], output_path: str) -> str:
        """导出交易列表到 Excel（原始流水明细格式）"""
        wb = openpyxl.Workbook()

        # 交易明细
        ws = wb.active
        ws.title = '交易明细'
        ws['A1'] = '银行流水明细'
        ws['A1'].font = Font(bold=True, size=14)
        ws.merge_cells('A1:I1')

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
        headers = ['日期', '描述', '金额', '币种', '方向', '对方户名', '流水号', '本方帐号', '本方户名']
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
            ws.cell(row=row, column=8, value=t.account_number)
            ws.cell(row=row, column=9, value=t.account_name)

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

    # ------------------------------------------------------------------ #
    #  新增方法：按金蝶精斗云凭证导入模板格式导出                               #
    # ------------------------------------------------------------------ #

    def build_voucher(
        self,
        transactions: List[Transaction],
        subjects: Dict[str, Subject],
        subject_mapping: Optional[dict] = None,
        account_mapping: Optional[dict] = None,
        output_path: str = 'voucher.xlsx',
        period: str = '',
    ) -> str:
        """按金蝶精斗云凭证导入模板格式导出 Excel。

        Args:
            transactions:     银行流水列表
            subjects:         SubjectLoader.load() 返回的科目字典
            subject_mapping:  关键字→科目代码映射配置（dict），为 None 时自动读取默认配置文件
            account_mapping:  账号后缀→银行科目代码映射配置（dict），为 None 时自动读取默认配置文件
            output_path:      输出文件路径
            period:           期间名称，用于 Sheet 名，如 '2026年第3期'

        Returns:
            实际写入的文件路径
        """
        if subject_mapping is None:
            subject_mapping = self._load_default_config('subject_mapping.json')
        if account_mapping is None:
            account_mapping = self._load_default_config('account_mapping.json')

        # 生成所有凭证分录
        all_entries: List[VoucherEntry] = []
        for voucher_no, t in enumerate(transactions, start=1):
            bank_code = self._match_bank_subject_code(t, account_mapping)
            counter_code = self._match_subject_code(t.description, t.direction, subject_mapping)

            bank_subject = subjects.get(bank_code)
            counter_subject = subjects.get(counter_code)

            # 每笔流水按自己的月份取该月最后一天作为凭证日期
            voucher_date = self._get_period_end_date(t.date)

            entries = self._transaction_to_entries(
                t, voucher_no, voucher_date, bank_subject, counter_subject,
                bank_code, counter_code, subjects,
            )
            all_entries.extend(entries)

        # 写入 Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        sheet_name = f'凭证列表#{period}' if period else '凭证列表'
        ws.title = sheet_name

        self._write_voucher_sheet(ws, all_entries)

        wb.save(output_path)
        return output_path

    # ------------------------------------------------------------------ #
    #  私有辅助方法                                                         #
    # ------------------------------------------------------------------ #

    def _load_default_config(self, filename: str) -> dict:
        """加载 config 目录下的默认配置文件。打包后使用 sys._MEIPASS。"""
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir = os.path.join(base, 'finance_agent_backend', 'config')
        config_path = os.path.join(config_dir, filename)
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_period_end_date(self, d: date) -> date:
        """计算指定日期所在月份的最后一天。

        例如 d 为 2026-03-15，则返回 2026-03-31。
        d 为 2026-04-05，则返回 2026-04-30。
        """
        last_day = calendar.monthrange(d.year, d.month)[1]
        return date(d.year, d.month, last_day)

    def _match_subject_code(
        self, description: str, direction: str, subject_mapping: dict
    ) -> str:
        """根据流水描述和方向，通过关键字映射匹配对方科目代码。

        匹配规则：
          1. 按 direction 选取规则列表（expense / income）
          2. 遍历 rules，description 包含任意 keyword 则返回对应 subject_code
          3. 无匹配时返回空字符串（不使用兜底科目，由调用方决定如何处理）
        """
        direction_key = 'expense' if direction == 'expense' else 'income'
        group = subject_mapping.get(direction_key, {})
        rules = group.get('rules', [])

        desc_lower = description.lower()
        for rule in rules:
            for kw in rule.get('keywords', []):
                if kw in description or kw.lower() in desc_lower:
                    return rule['subject_code']

        return ''

    def _match_bank_subject_code(
        self, transaction: Transaction, account_mapping: dict
    ) -> str:
        """根据流水信息匹配银行科目代码。

        匹配策略（按优先级）：
          1. 优先使用 transaction.account_number 的最后 4 位匹配具体银行账户
          2. 其次在 reference_number / notes / counterparty / description 中寻找账号后缀
          3. 均无匹配时返回 default_bank_subject_code
        """
        accounts = account_mapping.get('accounts', [])
        default_code = account_mapping.get('default_bank_subject_code', '10002')

        # 优先级1：用完整账号的最后4位匹配
        acct = transaction.account_number or ''
        if acct and len(acct) >= 4:
            acct_suffix = acct[-4:]
            for acc in accounts:
                suffix = acc.get('account_no_suffix', '')
                if suffix and acct_suffix == suffix:
                    return acc['subject_code']

        # 优先级2：在其它字段文本中寻找账号后缀（兜底）
        haystack = ' '.join(filter(None, [
            transaction.reference_number or '',
            transaction.notes or '',
            transaction.counterparty or '',
            transaction.description or '',
        ]))

        for acc in accounts:
            suffix = acc.get('account_no_suffix', '')
            if suffix and suffix in haystack:
                return acc['subject_code']

        return default_code

    def _transaction_to_entries(
        self,
        t: Transaction,
        voucher_no: int,
        voucher_date: date,
        bank_subject: Optional[Subject],
        counter_subject: Optional[Subject],
        bank_code: str,
        counter_code: str,
        subjects: Dict[str, Subject],
    ) -> List[VoucherEntry]:
        """将一笔流水转换为两条凭证分录（借贷平衡）。

        支出（expense）：
            分录1（借方）：对方科目  debit_amount=金额
            分录2（贷方）：银行科目  credit_amount=金额

        收入（income）：
            分录1（借方）：银行科目  debit_amount=金额
            分录2（贷方）：对方科目  credit_amount=金额
        """
        amount = t.amount
        summary = t.description or ''
        currency = 'RMB'  # 金蝶导入统一用 RMB

        bank_name = (
            bank_subject.full_name or bank_subject.name
            if bank_subject
            else bank_code
        )
        counter_name = (
            counter_subject.full_name or counter_subject.name
            if counter_subject
            else counter_code
        )

        if t.direction == 'expense':
            entry1 = VoucherEntry(
                date=voucher_date,
                voucher_no=voucher_no,
                entry_seq=1,
                summary=summary,
                subject_code=counter_code,
                subject_name=counter_name,
                debit_amount=amount,
                credit_amount=None,
                original_amount=amount,
                currency=currency,
            )
            entry2 = VoucherEntry(
                date=voucher_date,
                voucher_no=voucher_no,
                entry_seq=2,
                summary=summary,
                subject_code=bank_code,
                subject_name=bank_name,
                debit_amount=None,
                credit_amount=amount,
                original_amount=amount,
                currency=currency,
            )
        else:
            # income
            entry1 = VoucherEntry(
                date=voucher_date,
                voucher_no=voucher_no,
                entry_seq=1,
                summary=summary,
                subject_code=bank_code,
                subject_name=bank_name,
                debit_amount=amount,
                credit_amount=None,
                original_amount=amount,
                currency=currency,
            )
            entry2 = VoucherEntry(
                date=voucher_date,
                voucher_no=voucher_no,
                entry_seq=2,
                summary=summary,
                subject_code=counter_code,
                subject_name=counter_name,
                debit_amount=None,
                credit_amount=amount,
                original_amount=amount,
                currency=currency,
            )

        return [entry1, entry2]

    def _write_voucher_sheet(self, ws, entries: List[VoucherEntry]):
        """将凭证分录列表写入 worksheet，含表头和数字格式。

        25 列顺序与金蝶凭证导入模板完全一致：
        日期/凭证字/凭证号/附件数/分录序号/摘要/科目代码/科目名称/
        借方金额/贷方金额/客户/供应商/职员/项目/部门/存货/
        自定义辅助核算类别/编码/类别1/编码1/数量/单价/原币金额/币别/汇率
        """
        HEADERS = [
            '日期', '凭证字', '凭证号', '附件数', '分录序号',
            '摘要', '科目代码', '科目名称', '借方金额', '贷方金额',
            '客户', '供应商', '职员', '项目', '部门', '存货',
            '自定义辅助核算类别', '自定义辅助核算编码',
            '自定义辅助核算类别1', '自定义辅助核算编码1',
            '数量', '单价', '原币金额', '币别', '汇率',
        ]

        # 写表头
        for col, header in enumerate(HEADERS, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
            cell.alignment = Alignment(horizontal='center', vertical='center')

        # 固定列宽 15
        for i in range(1, len(HEADERS) + 1):
            ws.column_dimensions[get_column_letter(i)].width = 15

        # 写数据行
        for row_idx, e in enumerate(entries, start=2):
            def w(col, value):
                ws.cell(row=row_idx, column=col, value=value)

            # 日期转字符串（金蝶要求 YYYY-MM-DD 文本格式）
            w(1,  e.date.strftime('%Y-%m-%d'))
            w(2,  e.voucher_word)
            w(3,  e.voucher_no)
            w(4,  e.attachment_count)
            w(5,  e.entry_seq)
            w(6,  e.summary)
            w(7,  e.subject_code)
            w(8,  e.subject_name)

            # 借方金额：有值时设 #,##0.00 格式
            cell_debit = ws.cell(row=row_idx, column=9)
            cell_debit.value = float(e.debit_amount) if e.debit_amount is not None else None
            if e.debit_amount is not None:
                cell_debit.number_format = '#,##0.00'

            # 贷方金额
            cell_credit = ws.cell(row=row_idx, column=10)
            cell_credit.value = float(e.credit_amount) if e.credit_amount is not None else None
            if e.credit_amount is not None:
                cell_credit.number_format = '#,##0.00'

            w(11, e.customer)
            w(12, e.supplier)
            w(13, e.employee)
            w(14, e.project)
            w(15, e.department)
            w(16, e.inventory)
            w(17, e.custom_aux_category)
            w(18, e.custom_aux_code)
            w(19, e.custom_aux_category1)
            w(20, e.custom_aux_code1)
            w(21, None)   # 数量
            w(22, None)   # 单价

            # 原币金额
            cell_orig = ws.cell(row=row_idx, column=23)
            cell_orig.value = float(e.original_amount) if e.original_amount is not None else None
            if e.original_amount is not None:
                cell_orig.number_format = '##.00#####'

            w(24, e.currency)

            # 汇率
            cell_rate = ws.cell(row=row_idx, column=25)
            cell_rate.value = float(e.exchange_rate)
            cell_rate.number_format = '##.00#####'

        # 冻结首行
        ws.freeze_panes = 'A2'
