import { useState, useCallback } from 'react';
import { message } from 'antd';
import type { VoucherEntry } from '../components/VoucherPreviewPanel';

interface VoucherData {
  voucher_no: number; date: string; direction: string;
  bank_subject_code: string; counterpart_subject_code: string;
  entries: VoucherEntry[];
}

export function useVoucherFlow() {
  const [vouchers, setVouchers] = useState<VoucherData[]>([]);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [currentDraftId, setCurrentDraftId] = useState<string | null>(null);
  const [period, setPeriod] = useState('');
  const [showPage, setShowPage] = useState(false);

  const api = () => (window as any).electronAPI;

  const loadSubjects = useCallback(async () => {
    try {
      const r = await api()?.invoke?.('get_subjects_info', {});
      if (r?.success && r.subjects) {
        setSubjects(r.subjects);
      }
    } catch { /* ignore */ }
  }, []);

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
        await loadSubjects();
      } else {
        message.error(`凭证生成失败: ${r?.error}`);
      }
    } catch (e: any) {
      message.error(`凭证生成出错: ${e.message}`);
    } finally {
      setPreviewLoading(false);
    }
  }, [loadSubjects]);

  const closePage = useCallback(() => {
    setShowPage(false);
  }, []);

  const handleSaveDraft = useCallback(async (entries: VoucherEntry[]) => {
    if (entries.length === 0) return;
    setSaving(true);
    try {
      const r = await api()?.invoke?.('voucher.save_draft', {
        name: `凭证草稿_${period || Date.now()}`,
        period: period || '未命名期间',
        entries,
      });
      if (r?.success) {
        setCurrentDraftId(r.draft_id);
        message.success('草稿已保存');
      }
    } catch { /* ignore */ }
    finally { setSaving(false); }
  }, [period]);

  const handleExport = useCallback(async (entries: VoucherEntry[]) => {
    const unmatched = entries.filter(
      e => e.match_source === 'unmatched' && e.direction !== 'bank',
    ).length;
    if (unmatched > 0) {
      message.warning(`还有 ${unmatched} 条分录未匹配科目`);
    }

    setExportLoading(true);
    try {
      let draftId = currentDraftId;
      if (!draftId) {
        const saveR = await api()?.invoke?.('voucher.save_draft', {
          name: `凭证草稿_${period || Date.now()}`,
          period: period || '未命名期间',
          entries,
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
  }, [currentDraftId, period, closePage]);

  return {
    vouchers, subjects, previewLoading, saving, exportLoading,
    currentDraftId, period, showPage, closePage,
    preview, handleSaveDraft, handleExport,
  };
}