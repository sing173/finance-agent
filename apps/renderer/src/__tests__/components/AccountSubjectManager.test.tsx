import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AccountSubjectManager } from '../../components/AccountSubjectManager';
import type { AccountEntry } from '@shared/types';

// --- mocks ---

const mockAccounts: AccountEntry[] = [
  {
    id: '1',
    matchType: 'suffix',
    pattern: '1234',
    bank: '工商银行',
    bankCode: 'ICBC',
    subjectCode: '1000201',
    subjectName: '银行存款-工行基本户',
  },
  {
    id: '2',
    matchType: 'exact',
    pattern: '6222021234567890',
    bank: '招商银行',
    bankCode: 'CMB',
    subjectCode: '1000203',
    subjectName: '银行存款-招商银行',
  },
];

const invokeMock = vi.fn();

function defaultInvoke(api: string, _params: any) {
  if (api === 'account_registry.list') {
    return Promise.resolve({ success: true, accounts: mockAccounts });
  }
  if (api === 'get_subjects_info') {
    return Promise.resolve({
      success: true, count: 3, subjects: [
        { code: '1000201', name: '银行存款-工行基本户', category: '资产', direction: '借', is_cash: false, enabled: true, full_name: '银行存款-工商银行基本户' },
        { code: '1000203', name: '银行存款-招商银行', category: '资产', direction: '借', is_cash: false, enabled: true, full_name: '银行存款-招商银行' },
        { code: '6001001', name: '主营业务收入', category: '收入', direction: '贷', is_cash: false, enabled: true, full_name: '主营业务收入' },
      ],
    });
  }
  return Promise.resolve({ success: true });
}

const detectSupportedBanksMock = vi.fn().mockResolvedValue({
  success: true,
  banks: [
    { code: 'ICBC', name: '工商银行' },
    { code: 'CMB', name: '招商银行' },
    { code: 'GFB', name: '广发银行' },
  ],
});

beforeEach(() => {
  invokeMock.mockImplementation(defaultInvoke);
  (window as any).electronAPI = {
    invoke: invokeMock,
    detectSupportedBanks: detectSupportedBanksMock,
  };
});

afterEach(() => {
  (window as any).electronAPI = undefined;
});

// --- tests ---

describe('AccountSubjectManager', () => {
  it('renders card with title and accounts table', async () => {
    render(<AccountSubjectManager />);
    await waitFor(() => {
      expect(screen.getByText('账号-科目管理')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(invokeMock).toHaveBeenCalledWith('account_registry.list', {});
    });
    // Table renders bank names, bank codes, tags
    expect(screen.getAllByText('工商银行').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('ICBC')).toBeInTheDocument();
    expect(screen.getByText('CMB')).toBeInTheDocument();
    expect(screen.getByText('后缀')).toBeInTheDocument();
    expect(screen.getByText('精确')).toBeInTheDocument();
  });

  it('opens add modal when 新增 clicked', async () => {
    render(<AccountSubjectManager />);
    fireEvent.click(screen.getByText('新增'));

    // Modal should show a "银行代码" form label (also a column header — use getAllByText)
    await waitFor(() => {
      const bankCodeLabels = screen.getAllByText('银行代码');
      expect(bankCodeLabels.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('bankCode-select auto-fills bank input', async () => {
    render(<AccountSubjectManager />);
    fireEvent.click(screen.getByText('新增'));

    await waitFor(() => {
      const titles = document.querySelectorAll('.ant-modal-title');
      expect(titles.length).toBeGreaterThanOrEqual(1);
    });

    // Open bankCode dropdown (2nd ant-select on page — 1st is matchType)
    const selectors = document.querySelectorAll('.ant-select-selector');
    expect(selectors.length).toBeGreaterThanOrEqual(2);
    fireEvent.mouseDown(selectors[1]);
    const cmbOpt = await screen.findByText('招商银行 (CMB)');
    fireEvent.click(cmbOpt);

    // bank Input now shows 招商银行
    const bankDisplay = screen.getByDisplayValue('招商银行');
    expect(bankDisplay).toBeInTheDocument();
    expect((bankDisplay as HTMLInputElement).disabled).toBe(true);
  });

  it('submits add with correct params to backend', async () => {
    let captured: any = null;
    invokeMock.mockImplementation((api, params) => {
      if (api === 'account_registry.add') { captured = params; return Promise.resolve({ success: true, id: 'new-1' }); }
      return defaultInvoke(api, params);
    });

    render(<AccountSubjectManager />);
    fireEvent.click(screen.getByText('新增'));

    await waitFor(() => {
      const titles = document.querySelectorAll('.ant-modal-title');
      expect(titles.length).toBeGreaterThanOrEqual(1);
    });

    // Fill pattern
    fireEvent.change(screen.getByPlaceholderText('账号后缀或完整账号'), { target: { value: '9999' } });

    // Select GFB
    const selectors = document.querySelectorAll('.ant-select-selector');
    fireEvent.mouseDown(selectors[1]);
    fireEvent.click(await screen.findByText('广发银行 (GFB)'));

    // Submit — antd Modal's onOk handler
    const modalFooter = document.querySelector('.ant-modal-footer')!;
    const okBtn = modalFooter.querySelector('.ant-btn-primary')!;
    fireEvent.click(okBtn);

    await waitFor(() => { expect(captured).not.toBeNull(); });
    expect(captured.bankCode).toBe('GFB');
    expect(captured.bank).toBe('广发银行');
    expect(captured.pattern).toBe('9999');
  });

  it('edit opens with pre-filled bank value from bankCode', async () => {
    render(<AccountSubjectManager />);
    await waitFor(() => { expect(invokeMock).toHaveBeenCalledWith('account_registry.list', {}); });

    fireEvent.click(screen.getAllByLabelText('edit')[0]);

    await waitFor(() => {
      const titles = document.querySelectorAll('.ant-modal-title');
      expect(titles.length).toBeGreaterThanOrEqual(1);
      expect(titles[0].textContent).toBe('编辑账号映射');
    });

    expect(screen.getByDisplayValue('工商银行')).toBeInTheDocument();
  });

  it('submits update with correct params', async () => {
    let captured: any = null;
    invokeMock.mockImplementation((api, params) => {
      if (api === 'account_registry.update') { captured = params; return Promise.resolve({ success: true }); }
      return defaultInvoke(api, params);
    });

    render(<AccountSubjectManager />);
    await waitFor(() => { expect(invokeMock).toHaveBeenCalledWith('account_registry.list', {}); });

    fireEvent.click(screen.getAllByLabelText('edit')[0]);
    await waitFor(() => {
      const titles = document.querySelectorAll('.ant-modal-title');
      expect(titles.length).toBeGreaterThanOrEqual(1);
    });

    // Click 更新 (modal footer primary button)
    const modalFooter = document.querySelector('.ant-modal-footer')!;
    fireEvent.click(modalFooter.querySelector('.ant-btn-primary')!);

    await waitFor(() => { expect(captured).not.toBeNull(); });
    expect(captured.id).toBe('1');
    expect(captured.bankCode).toBe('ICBC');
    expect(captured.bank).toBe('工商银行');
  });

  it('deletes account after popconfirm', async () => {
    let deleteId: string | null = null;
    invokeMock.mockImplementation((api, params) => {
      if (api === 'account_registry.delete') { deleteId = params.id; return Promise.resolve({ success: true }); }
      return defaultInvoke(api, params);
    });

    render(<AccountSubjectManager />);
    await waitFor(() => { expect(invokeMock).toHaveBeenCalledWith('account_registry.list', {}); });

    // Click delete icon (opens Popconfirm with okText="删除")
    fireEvent.click(screen.getAllByLabelText('delete')[0]);

    // Popconfirm renders its buttons under .ant-popover-content in document.body
    // The ok button has class .ant-btn-primary and text "删除"
    await waitFor(() => {
      const popContent = document.querySelector('.ant-popover-content');
      expect(popContent).toBeTruthy();
      const okBtn = popContent!.querySelector('.ant-btn-primary') as HTMLButtonElement;
      expect(okBtn).toBeTruthy();
      fireEvent.click(okBtn);
    }, { timeout: 3000 });

    await waitFor(() => { expect(deleteId).toBe('1'); });
  });
});