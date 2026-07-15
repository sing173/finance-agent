import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { VoucherPreviewPanel } from '../../components/VoucherPreviewPanel';
import type { VoucherData } from '@shared/types';

const mockSubjects = [
  { code: '5060203', name: '管理费用_物业管理费', category: '管理费用', direction: '借', aux_category: '', aux_category_name: '', is_cash: false, enabled: true, full_name: '管理费用_物业管理费' },
  { code: '5060201', name: '管理费用_租赁费', category: '管理费用', direction: '借', aux_category: '', aux_category_name: '', is_cash: false, enabled: true, full_name: '管理费用_租赁费' },
];

const mockVouchers: VoucherData[] = [
  {
    voucher_no: 1,
    date: '2026-03-01',
    direction: 'expense',
    bank_subject_code: '1000201',
    counterpart_subject_code: '5060203',
    entries: [
      {
        entry_seq: 1, voucher_no: 1,
        date: '2026-03-01', summary: '支付启胜物业费1月',
        subject_code: '5060203', subject_name: '管理费用_物业管理费',
        debit_amount: 1200.0, credit_amount: null,
        direction: 'expense', counterparty: '启胜物业',
        match_source: 'rule', rule_id: 'rule_e031',
        original_summary: '支付启胜物业费1月', original_amount: 1200.0,
        is_manual: false, aux_category: '04', aux_category_name: '公共部门',
      },
      {
        entry_seq: 2, voucher_no: 1,
        date: '2026-03-01', summary: '支付启胜物业费2月',
        subject_code: '', subject_name: '',
        debit_amount: 1200.0, credit_amount: null,
        direction: 'expense', counterparty: '启胜物业',
        match_source: 'unmatched', rule_id: '',
        original_summary: '支付启胜物业费2月', original_amount: 1200.0,
        is_manual: false, aux_category: '', aux_category_name: '',
      },
      {
        entry_seq: 3, voucher_no: 1,
        date: '2026-03-01', summary: '银行科目',
        subject_code: '1000201', subject_name: '银行存款-工行基本户',
        debit_amount: null, credit_amount: 2400.0,
        direction: 'bank', counterparty: '',
        match_source: 'auto', rule_id: '',
        original_summary: '', original_amount: 0,
        is_manual: false, aux_category: '', aux_category_name: '',
      },
    ],
  },
];

describe('VoucherPreviewPanel', () => {
  it('renders voucher cards from data', () => {
    render(
      <VoucherPreviewPanel
        vouchers={mockVouchers}
        subjects={mockSubjects}
        onVouchersChange={vi.fn()}
        onSaveDraft={vi.fn()}
        onExport={vi.fn()}
      />
    );
    expect(screen.getByText('支付启胜物业费1月')).toBeInTheDocument();
    expect(screen.getByText((content: string) => content.includes('管理费用_物业管理费'))).toBeInTheDocument();
  });

  it('shows unmatched warning alert', () => {
    render(
      <VoucherPreviewPanel
        vouchers={mockVouchers}
        subjects={mockSubjects}
        onVouchersChange={vi.fn()}
        onSaveDraft={vi.fn()}
        onExport={vi.fn()}
      />
    );
    expect(screen.getByText(/未匹配到对方科目/)).toBeInTheDocument();
  });

  it('shows click-to-select subject for unmatched entries', () => {
    render(
      <VoucherPreviewPanel
        vouchers={mockVouchers}
        subjects={mockSubjects}
        onVouchersChange={vi.fn()}
        onSaveDraft={vi.fn()}
        onExport={vi.fn()}
      />
    );
    expect(screen.getByText('点击选择科目')).toBeInTheDocument();
  });

  
  it('calls onSaveDraft when save button clicked', () => {
    const onSaveDraft = vi.fn();
    render(
      <VoucherPreviewPanel
        vouchers={mockVouchers}
        subjects={mockSubjects}
        onVouchersChange={vi.fn()}
        onSaveDraft={onSaveDraft}
        onExport={vi.fn()}
      />
    );
    fireEvent.click(screen.getByText('保存草稿'));
    expect(onSaveDraft).toHaveBeenCalled();
  });

  it('calls onVouchersChange when vouchers are edited', async () => {
    const onVouchersChange = vi.fn();
    render(
      <VoucherPreviewPanel
        vouchers={mockVouchers}
        subjects={mockSubjects}
        onVouchersChange={onVouchersChange}
        onSaveDraft={vi.fn()}
        onExport={vi.fn()}
      />
    );
    await waitFor(() => {
      expect(onVouchersChange).toHaveBeenCalled();
    });
  });

  it('shows export popconfirm with unmatched warning', async () => {
    render(
      <VoucherPreviewPanel
        vouchers={mockVouchers}
        subjects={mockSubjects}
        onVouchersChange={vi.fn()}
        onSaveDraft={vi.fn()}
        onExport={vi.fn()}
      />
    );
    fireEvent.click(screen.getByText('确认导出'));
    await waitFor(() => {
      expect(screen.getByText(/未匹配科目/)).toBeInTheDocument();
    });
  });
});