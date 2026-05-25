import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { VoucherPreviewPanel } from '../VoucherPreviewPanel';

const mockVouchers = [
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
        match_source: 'rule', original_summary: '支付启胜物业费1月',
        original_amount: 1200.0, is_manual: false,
      },
      {
        entry_seq: 2, voucher_no: 1,
        date: '2026-03-01', summary: '支付启胜物业费2月',
        subject_code: '', subject_name: '',
        debit_amount: 1200.0, credit_amount: null,
        direction: 'expense', counterparty: '启胜物业',
        match_source: 'unmatched', original_summary: '支付启胜物业费2月',
        original_amount: 1200.0, is_manual: false,
      },
      {
        entry_seq: 3, voucher_no: 1,
        date: '2026-03-01', summary: '银行科目',
        subject_code: '1000201', subject_name: '银行存款-工行基本户',
        debit_amount: null, credit_amount: 2400.0,
        direction: 'bank', counterparty: '',
        match_source: 'unmatched', original_summary: '',
        original_amount: 0, is_manual: false,
      },
    ],
  },
];

const invokeMock = vi.fn().mockResolvedValue({ success: true });

beforeEach(() => {
  (window as any).electronAPI = { invoke: invokeMock };
});

afterEach(() => {
  (window as any).electronAPI = undefined;
});

describe('VoucherPreviewPanel', () => {
  it('renders voucher cards from data', () => {
    render(
      <VoucherPreviewPanel
        vouchers={mockVouchers}
        onExport={vi.fn()}
      />
    );
    expect(screen.getByText('凭证预览')).toBeInTheDocument();
    expect(screen.getByText('支付启胜物业费1月')).toBeInTheDocument();
    // antd Table renders cell text as separate nodes — use function matcher
    expect(screen.getByText((content: string) => content.includes('管理费用_物业管理费'))).toBeInTheDocument();
  });

  it('shows unmatched warning alert', () => {
    render(
      <VoucherPreviewPanel
        vouchers={mockVouchers}
        onExport={vi.fn()}
      />
    );
    // Entry 2 has match_source=unmatched → warning alert shown
    expect(screen.getByText(/未匹配到对方科目/)).toBeInTheDocument();
  });

  it('shows click-to-select subject for unmatched entries', () => {
    render(
      <VoucherPreviewPanel
        vouchers={mockVouchers}
        onExport={vi.fn()}
      />
    );
    expect(screen.getByText('点击选择科目')).toBeInTheDocument();
  });

  it('calls onExport when export button clicked', () => {
    const onExport = vi.fn();
    render(
      <VoucherPreviewPanel
        vouchers={mockVouchers}
        onExport={onExport}
      />
    );
    fireEvent.click(screen.getByText('确认导出'));
    expect(onExport).toHaveBeenCalled();
  });
});