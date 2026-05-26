import { useState, useCallback, useRef, useEffect } from 'react';
import { message } from 'antd';
import type { VoucherEntry } from '../components/VoucherPreviewPanel';

interface VoucherData {
  voucher_no: number; date: string; direction: string;
  bank_subject_code: string; counterpart_subject_code: string;
  entries: VoucherEntry[];
}
interface DraftItem {
  id: string; name: string; period: string; status: string;
  created_at: string; updated_at: string; entry_count: number;
}

const AUTO_SAVE_MS = 3000;

export function useVoucherFlow() {
  const [vouchers, setVouchers] = useState<VoucherData[]>([]);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [drafts, setDrafts] = useState<DraftItem[]>([]);
  const [draftsLoading, setDraftsLoading] = useState(false);
  const [currentDraftId, setCurrentDraftId] = useState<string | null>(null);
  const [period, setPeriod] = useState('');
  const [showPanel, setShowPanel] = useState(false);

  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestVouchersRef = useRef<VoucherData[]>([]);

  const api = () => (window as any).electronAPI;

  // ── load subjects ──
  const loadSubjects = useCallback(async () => {
    try {
      const r = await api()?.invoke?.('get_subjects_info', {});
      if (r?.success && r.subjects) {
        setSubjects(r.subjects);
      }
    } catch { /* ignore */ }
  }, []);

  // ── preview: transactions → vouchers ──
  const preview = useCallback(async (transactions: any[], p?: string) => {
    setPreviewLoading(true);
    try {
      const r = await api()?.invoke?.('voucher.preview', { transactions });
      if (r?.success) {
        setVouchers(r.vouchers);
        if (!period) {
          const dates = transactions.map((t: any) => t.date).sort();
          setPeriod(p || (dates.length ? dates[0]?.slice(0, 7)?.replace('-', '年') + '月' : ''));
        }
        setShowPanel(true);
        await loadSubjects();
        await loadDrafts();
      } else {
        message.error(`凭证预览失败: ${r?.error}`);
      }
    } catch (e: any) {
      message.error(`预览出错: ${e.message}`);
    } finally {
      setPreviewLoading(false);
    }
  }, [period, loadSubjects]);

  // ── auto-save draft (debounced) ──
  const doSaveDraft = useCallback(async (v: VoucherData[]) => {
    if (v.length === 0) return;
    const allEntries: any[] = [];
    for (const vc of v) {
      for (const e of vc.entries) {
        if (e.direction !== 'bank') allEntries.push(e);
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
  }, [period]);

  const scheduleAutoSave = useCallback((v: VoucherData[]) => {
    latestVouchersRef.current = v;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      doSaveDraft(latestVouchersRef.current);
    }, AUTO_SAVE_MS);
  }, [doSaveDraft]);

  // ── manual save ──
  const handleSaveDraft = useCallback(async () => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    await doSaveDraft(vouchers);
    await loadDrafts();
  }, [vouchers, doSaveDraft]);

  // ── load drafts ──
  const loadDrafts = useCallback(async () => {
    setDraftsLoading(true);
    try {
      const r = await api()?.invoke?.('voucher.list_drafts', {});
      if (r?.success) setDrafts(r.drafts || []);
    } catch { /* ignore */ }
    finally { setDraftsLoading(false); }
  }, []);

  // ── load draft (restore) ──
  const handleLoadDraft = useCallback(async (draftId: string) => {
    try {
      const r = await api()?.invoke?.('voucher.load_draft', { draft_id: draftId });
      if (r?.success) {
        setCurrentDraftId(draftId);
        setPeriod(r.draft.period || '');
        // reconstruct vouchers from entries
        const entries = r.draft.entries || [];
        const groups = new Map<number, any[]>();
        for (const e of entries) {
          const k = e.voucher_no || 1;
          if (!groups.has(k)) groups.set(k, []);
          groups.get(k)!.push(e);
        }
        const vcs: VoucherData[] = [];
        for (const [vno, es] of groups) {
          vcs.push({
            voucher_no: vno,
            date: es[0]?.date || '',
            direction: es[0]?.direction || 'expense',
            bank_subject_code: '',
            counterpart_subject_code: '',
            entries: es,
          });
        }
        setVouchers(vcs);
        setShowPanel(true);
        message.success(`已恢复草稿: ${r.draft.name}`);
      }
    } catch (e: any) {
      message.error(`加载草稿失败: ${e.message}`);
    }
  }, []);

  // ── delete draft ──
  const handleDeleteDraft = useCallback(async (draftId: string) => {
    try {
      await api()?.invoke?.('voucher.delete_draft', { draft_id: draftId });
      if (currentDraftId === draftId) setCurrentDraftId(null);
      await loadDrafts();
    } catch { /* ignore */ }
  }, [currentDraftId, loadDrafts]);

  // ── export ──
  const handleExport = useCallback(async () => {
    if (!currentDraftId) {
      message.warning('请先保存草稿再导出');
      return;
    }
    const unmatched = vouchers.reduce(
      (s, v) => s + v.entries.filter(e => e.match_source === 'unmatched' && e.direction !== 'bank').length, 0,
    );
    if (unmatched > 0) {
      message.warning(`还有 ${unmatched} 条分录未匹配科目`);
    }
    try {
      const outputPath = await api()?.saveFileDialog?.({
        title: '保存凭证 Excel',
        defaultPath: `voucher_${period || Date.now()}.xlsx`,
      });
      if (!outputPath) return;

      const r = await api()?.invoke?.('voucher.export', {
        draft_id: currentDraftId,
        period: period || '未命名期间',
        output_path: outputPath,
        source_files: [],
      });
      if (r?.success) {
        message.success(`凭证已导出: ${r.file_path}`);
        await loadDrafts();
      } else {
        message.error(`导出失败: ${r?.error}`);
      }
    } catch (e: any) {
      message.error(`导出出错: ${e.message}`);
    }
  }, [currentDraftId, vouchers, period, loadDrafts]);

  // cleanup
  useEffect(() => {
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current); };
  }, []);

  return {
    vouchers, subjects, previewLoading, saving, drafts, draftsLoading,
    currentDraftId, period, showPanel, setShowPanel,
    preview, handleSaveDraft, handleExport,
    loadDrafts, handleLoadDraft, handleDeleteDraft,
    onVouchersChange: scheduleAutoSave,
  };
}