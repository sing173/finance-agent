import { useState, useCallback } from 'react';
import { message } from 'antd';
import type { VoucherData } from '@shared/types';
import { isUnmatchedNonBank } from './voucher_utils';
import { useSubjects } from './useSubjects';

export function useVoucherFlow() {
  const [vouchers, setVouchers] = useState<VoucherData[]>([]);
  const [editedVouchers, setEditedVouchers] = useState<VoucherData[]>([]);
  const { subjects, reload: reloadSubjects } = useSubjects();
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [currentDraftId, setCurrentDraftId] = useState<string | null>(null);
  const [period, setPeriod] = useState('');
  const [showPage, setShowPage] = useState(false);

  const api = () => (window as any).electronAPI;

  // ── preview: transactions → vouchers ──
  const preview = useCallback(async (transactions: any[], p?: string) => {
    setPreviewLoading(true);
    try {
      const r = await api()?.invoke?.('voucher.preview', { transactions });
      if (r?.success) {
        setVouchers(r.vouchers);
        setCurrentDraftId(null);
        const dates = transactions.map((t: any) => t.date).sort();
        setPeriod(p || (dates.length ? dates[0]?.slice(0, 7)?.replace('-', '年') + '月' : ''));
        setShowPage(true);
        await reloadSubjects();
      } else {
        message.error(`凭证生成失败: ${r?.error}`);
      }
    } catch (e: any) {
      message.error(`凭证生成出错: ${e.message}`);
    } finally {
      setPreviewLoading(false);
    }
  }, [reloadSubjects]);

  // ── close page ──
  const closePage = useCallback(() => {
    setShowPage(false);
  }, []);

  // ── voucher changes (from panel user edits) ──
  const onVouchersChange = useCallback((v: VoucherData[]) => {
    setEditedVouchers(v);
  }, []);

  // ── manual save draft ──
  const handleSaveDraft = useCallback(async () => {
    const v = editedVouchers.length > 0 ? editedVouchers : vouchers;
    if (v.length === 0) return;
    const allEntries: any[] = [];
    for (const vc of v) {
      for (const e of vc.entries) {
        allEntries.push(e);
      }
    }
    if (allEntries.length === 0) return;

    setSaving(true);
    try {
      const r = await api()?.invoke?.('voucher.save_draft', {
        name: `凭证草稿_${period || Date.now()}`,
        period: period || '未命名期间',
        entries: allEntries,
      });
      if (r?.success) {
        setCurrentDraftId(r.draft_id);
        message.success('草稿已保存');
      }
    } catch { /* ignore */ }
    finally { setSaving(false); }
  }, [editedVouchers, vouchers, period]);

  // ── export ──
  const handleExport = useCallback(async () => {
    const v = editedVouchers.length > 0 ? editedVouchers : vouchers;
    const unmatched = v.reduce(
      (s, vc) => s + vc.entries.filter(e => isUnmatchedNonBank(e)).length, 0,
    );
    if (unmatched > 0) {
      message.warning(`还有 ${unmatched} 条分录未匹配科目`);
    }

    setExportLoading(true);
    try {
      // 先保存草稿（无草稿时自动保存）
      let draftId = currentDraftId;
      if (!draftId) {
        const allEntries: any[] = [];
        for (const vc of v) {
          for (const e of vc.entries) {
            allEntries.push(e);
          }
        }
        const saveR = await api()?.invoke?.('voucher.save_draft', {
          name: `凭证草稿_${period || Date.now()}`,
          period: period || '未命名期间',
          entries: allEntries,
        });
        if (saveR?.success) {
          draftId = saveR.draft_id;
          setCurrentDraftId(draftId);
        } else {
          message.error('保存草稿失败，无法导出');
          return;
        }
      }

      const outputPath = await api()?.saveFileDialog?.({
        title: '保存凭证 Excel',
        defaultPath: `voucher_${period || Date.now()}.xlsx`,
      });
      if (!outputPath) return;

      const r = await api()?.invoke?.('voucher.export', {
        draft_id: draftId,
        period: period || '未命名期间',
        output_path: outputPath,
        source_files: [],
      });
      if (r?.success) {
        message.success(`凭证已导出: ${r.file_path}`);
        closePage();
      } else {
        message.error(`导出失败: ${r?.error}`);
      }
    } catch (e: any) {
      message.error(`导出出错: ${e.message}`);
    } finally {
      setExportLoading(false);
    }
  }, [currentDraftId, editedVouchers, vouchers, period, closePage]);

  return {
    vouchers, subjects, previewLoading, saving, exportLoading,
    currentDraftId, period, showPage, closePage,
    preview, handleSaveDraft, handleExport,
    onVouchersChange,
  };
}