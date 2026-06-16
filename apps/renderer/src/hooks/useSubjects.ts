import { useState, useCallback, useEffect } from 'react';
import type { SubjectItem } from '@shared/types';

/**
 * useSubjects — 共享科目数据加载 Hook
 *
 * @param initial - 外部传入的初始科目列表。提供时直接使用，不发起 IPC 加载。
 * @returns { subjects, loading, error, reload }
 *
 * 行为：
 *   initial 提供  → subjects = initial，loading = false，不自动加载
 *   initial 未提供 → mount 时自动 IPC 加载一次
 */
export function useSubjects(initial?: SubjectItem[]) {
  const [subjects, setSubjects] = useState<SubjectItem[]>(initial ?? []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const _load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await (window as any).electronAPI?.invoke('get_subjects_info', {});
      if (r?.success && r.subjects) {
        setSubjects(r.subjects);
      } else if (!r?.success) {
        setError(r?.error ?? '加载科目失败');
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const reload = useCallback(async () => {
    await _load();
  }, [_load]);

  // initial 未提供或为空数组时自动加载
  useEffect(() => {
    if (initial === undefined || (Array.isArray(initial) && initial.length === 0)) {
      _load();
    }
  }, [initial, _load]);

  // initial 变化时同步内部状态（父组件 reload 后传入新数据）
  useEffect(() => {
    if (initial !== undefined && initial.length > 0) {
      setSubjects(initial);
    }
  }, [initial]);

  return { subjects, loading, error, reload };
}
