import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { VoucherDraftList } from '../VoucherDraftList';

const mockDrafts = [
  {
    id: 'draft001',
    name: '2026年3月凭证',
    period: '2026年第3期',
    status: 'draft',
    created_at: '2026-03-01T00:00:00',
    updated_at: '2026-03-15T00:00:00',
    entry_count: 12,
  },
  {
    id: 'draft002',
    name: '2026年2月凭证',
    period: '2026年第2期',
    status: 'exported',
    created_at: '2026-02-01T00:00:00',
    updated_at: '2026-02-28T00:00:00',
    entry_count: 8,
  },
];

const invokeMock = vi.fn().mockResolvedValue({ success: true });

beforeEach(() => {
  vi.clearAllMocks();
  (window as any).electronAPI = { invoke: invokeMock };
});

afterEach(() => {
  (window as any).electronAPI = undefined;
});

describe('VoucherDraftList', () => {
  it('renders draft list when drafts provided', () => {
    render(
      <VoucherDraftList
        drafts={mockDrafts}
        onLoad={vi.fn()}
        onDelete={vi.fn()}
        loading={false}
      />
    );
    expect(screen.getByText('草稿列表')).toBeInTheDocument();
    expect(screen.getByText('2026年3月凭证')).toBeInTheDocument();
    expect(screen.getByText('2026年2月凭证')).toBeInTheDocument();
  });

  it('shows empty state when no drafts', () => {
    render(
      <VoucherDraftList
        drafts={[]}
        onLoad={vi.fn()}
        onDelete={vi.fn()}
        loading={false}
      />
    );
    expect(screen.getByText('暂无草稿')).toBeInTheDocument();
  });

  it('calls onLoad when 加载 clicked', () => {
    const onLoad = vi.fn();
    render(
      <VoucherDraftList
        drafts={mockDrafts}
        onLoad={onLoad}
        onDelete={vi.fn()}
        loading={false}
      />
    );
    const loadBtns = screen.getAllByText('加载');
    fireEvent.click(loadBtns[0]);
    expect(onLoad).toHaveBeenCalledWith('draft001');
  });

  it('calls onDelete with confirmation', async () => {
    const onDelete = vi.fn();
    render(
      <VoucherDraftList
        drafts={mockDrafts}
        onLoad={vi.fn()}
        onDelete={onDelete}
        loading={false}
      />
    );
    const deleteBtns = screen.getAllByLabelText('delete');
    fireEvent.click(deleteBtns[0]);

    // Popconfirm appears in a popover — find the OK button which is "删除"
    await waitFor(() => {
      const popDeleteBtns = document.querySelectorAll('.ant-popconfirm-buttons .ant-btn-primary');
      expect(popDeleteBtns.length).toBeGreaterThan(0);
      fireEvent.click(popDeleteBtns[0]);
    });

    expect(onDelete).toHaveBeenCalledWith('draft001');
  });

  it('shows status tag for exported drafts', () => {
    render(
      <VoucherDraftList
        drafts={mockDrafts}
        onLoad={vi.fn()}
        onDelete={vi.fn()}
        loading={false}
      />
    );
    expect(screen.getByText('已导出')).toBeInTheDocument();
  });
});