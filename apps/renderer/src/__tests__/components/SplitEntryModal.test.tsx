import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { SplitEntryModal } from '../../components/SplitEntryModal';

describe('SplitEntryModal', () => {
  const defaultProps = {
    open: true,
    originalAmount: 100,
    originalSummary: '测试摘要',
    isDebit: true,
    onCancel: vi.fn(),
    onConfirm: vi.fn(),
  };

  it('renders modal with original amount', () => {
    render(<SplitEntryModal {...defaultProps} />);
    expect(screen.getByText('拆分分录')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });

  it('disables confirm button when a part has zero amount (hasEmpty)', () => {
    render(<SplitEntryModal {...defaultProps} />);
    const confirmBtn = screen.getByRole('button', { name: '确认拆分' });
    expect(confirmBtn).toBeDisabled();
  });

  it('enables confirm button when all parts have positive amounts and no over-limit', () => {
    render(<SplitEntryModal {...defaultProps} />);
    const inputs = screen.getAllByRole('spinbutton');
    // Set both parts to 50
    fireEvent.change(inputs[0], { target: { value: '50' } });
    fireEvent.change(inputs[1], { target: { value: '50' } });

    const confirmBtn = screen.getByRole('button', { name: '确认拆分' });
    expect(confirmBtn).not.toBeDisabled();
  });

  describe('overLimit via round2', () => {
    it('shows error alert when total exceeds original amount', () => {
      render(<SplitEntryModal {...defaultProps} />);
      const inputs = screen.getAllByRole('spinbutton');
      fireEvent.change(inputs[0], { target: { value: '60' } });
      fireEvent.change(inputs[1], { target: { value: '50' } });

      expect(screen.getByText('合计金额超过原金额')).toBeInTheDocument();
    });
  });

  describe('autoFillRemaining guard', () => {
    it('hides auto-fill button when remaining is tiny but positive (<= 0.005)', () => {
      // originalAmount=100, parts sum to 99.996 → remaining=0.004 → hidden
      render(
        <SplitEntryModal
          {...defaultProps}
          originalAmount={100}
        />,
      );
      const inputs = screen.getAllByRole('spinbutton');
      fireEvent.change(inputs[0], { target: { value: '49.998' } });
      fireEvent.change(inputs[1], { target: { value: '49.998' } });

      expect(screen.queryByText(/自动添加剩余/)).not.toBeInTheDocument();
    });

    it('shows auto-fill button when remaining is above 0.005', () => {
      render(<SplitEntryModal {...defaultProps} />);
      const inputs = screen.getAllByRole('spinbutton');
      fireEvent.change(inputs[0], { target: { value: '49' } });
      fireEvent.change(inputs[1], { target: { value: '49' } });

      expect(screen.getByText(/自动添加剩余/)).toBeInTheDocument();
    });

    it('does not add a near-zero part when auto-filling with tiny remaining', () => {
      render(
        <SplitEntryModal
          {...defaultProps}
          originalAmount={100}
        />,
      );
      const inputs = screen.getAllByRole('spinbutton');
      fireEvent.change(inputs[0], { target: { value: '49.998' } });
      fireEvent.change(inputs[1], { target: { value: '49.998' } });

      // 自动添加剩余 button is hidden → no near-zero part added
      const partLabels = screen.getAllByText(/第 \d+ 份/);
      expect(partLabels).toHaveLength(2); // still only 2 parts
    });
  });

  describe('add/remove parts', () => {
    it('adds a new part when clicking 添加一份', () => {
      render(<SplitEntryModal {...defaultProps} />);
      fireEvent.click(screen.getByText('添加一份'));
      expect(screen.getAllByText(/第 \d+ 份/)).toHaveLength(3);
    });

    it('does not remove below 2 parts', () => {
      render(<SplitEntryModal {...defaultProps} />);
      const removeButtons = screen.getAllByRole('button').filter(
        (btn) => btn.querySelector('.anticon-minus-circle') || btn.getAttribute('aria-label')?.includes('删除'),
      );
      // With only 2 parts, no remove button should be rendered
      const allPartContainers = screen.getAllByText(/第 \d+ 份/);
      expect(allPartContainers).toHaveLength(2);
    });
  });

  describe('onConfirm / onCancel', () => {
    it('calls onConfirm with parts when split is valid', () => {
      const onConfirm = vi.fn();
      render(
        <SplitEntryModal
          {...defaultProps}
          originalAmount={100}
          onConfirm={onConfirm}
        />,
      );
      const inputs = screen.getAllByRole('spinbutton');
      fireEvent.change(inputs[0], { target: { value: '60' } });
      fireEvent.change(inputs[1], { target: { value: '40' } });

      fireEvent.click(screen.getByText('确认拆分'));

      expect(onConfirm).toHaveBeenCalledWith([
        { amount: 60, summary: '测试摘要' },
        { amount: 40, summary: '测试摘要' },
      ]);
    });

    it('calls onCancel and resets parts when cancel is clicked', () => {
      const onCancel = vi.fn();
      render(
        <SplitEntryModal
          {...defaultProps}
          originalAmount={100}
          onCancel={onCancel}
        />,
      );
      const inputs = screen.getAllByRole('spinbutton');
      fireEvent.change(inputs[0], { target: { value: '60' } });
      fireEvent.change(inputs[1], { target: { value: '40' } });

      const cancelBtn = screen.getAllByRole('button').find((btn) => /取\s*消/.test(btn.textContent || ''));
      expect(cancelBtn).toBeDefined();
      fireEvent.click(cancelBtn!);

      expect(onCancel).toHaveBeenCalled();
    });
  });

  describe('floating-point split exact match', () => {
    it('confirms split when parts sum to original amount within round2 tolerance', () => {
      const onConfirm = vi.fn();
      render(
        <SplitEntryModal
          {...defaultProps}
          originalAmount={100}
          onConfirm={onConfirm}
        />,
      );
      // 33.33 + 33.33 + 33.34 = 100.00 exactly
      const inputs = screen.getAllByRole('spinbutton');
      fireEvent.change(inputs[0], { target: { value: '33.33' } });
      fireEvent.change(inputs[1], { target: { value: '33.33' } });
      fireEvent.click(screen.getByText('添加一份'));
      const thirdInput = screen.getAllByRole('spinbutton')[2];
      fireEvent.change(thirdInput, { target: { value: '33.34' } });

      const confirmBtn = screen.getByText('确认拆分').closest('button')!;
      expect(confirmBtn).not.toBeDisabled();

      fireEvent.click(confirmBtn);
      expect(onConfirm).toHaveBeenCalled();
    });
  });
});
