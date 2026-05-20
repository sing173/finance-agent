import { useState, useCallback } from 'react';
import { message } from 'antd';

/**
 * useVoucherExport — unified voucher export logic for single-file and batch modes.
 *
 * Merges what was previously two separate callbacks (handleOpenVoucherModal +
 * handleExportVoucher) into one hook with shared save-file-dialog and
 * generateVoucher call chain.
 */
export function useVoucherExport() {
  const [voucherModalOpen, setVoucherModalOpen] = useState(false);
  const [voucherLoading, setVoucherLoading] = useState(false);
  const [period, setPeriod] = useState('');

  const openModal = useCallback((txns: any[]) => {
    if (!period && txns?.length) {
      const dates: string[] = txns.map((t: any) => t.date as string);
      dates.sort();
      const earliest = dates[0];
      const [y, m] = earliest.split('-');
      setPeriod(`${y}年${Number(m)}月`);
    }
    setVoucherModalOpen(true);
  }, [period]);

  const closeModal = useCallback(() => {
    setVoucherModalOpen(false);
  }, []);

  const exportVoucher = useCallback(async (
    txns: any[],
    onSuccess?: () => void,
  ) => {
    if (!txns?.length) {
      message.warning('没有可导出的交易数据');
      return;
    }

    const defaultName = `voucher_${period || Date.now()}.xlsx`;
    const outputPath = await (window as any).electronAPI?.saveFileDialog?.({
      title: '保存凭证 Excel',
      defaultPath: defaultName,
    });
    if (!outputPath) return;

    setVoucherLoading(true);
    try {
      const result = await (window as any).electronAPI?.generateVoucher?.({
        transactions: txns,
        output_path: outputPath,
        period,
      });

      if (result?.success) {
        message.success(`凭证已导出: ${result.excel_path}`);
        setVoucherModalOpen(false);
        onSuccess?.();
      } else {
        message.error(`导出失败：${result?.error || '未知错误'}`);
      }
    } catch (error: unknown) {
      message.error(`导出出错：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setVoucherLoading(false);
    }
  }, [period]);

  return { voucherModalOpen, voucherLoading, period, setPeriod, openModal, closeModal, exportVoucher };
}
