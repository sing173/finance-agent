import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useBatchOrchestrator } from '../../hooks/useBatchOrchestrator';

function mockElectronAPI(overrides: Record<string, any> = {}) {
  (window as any).electronAPI = {
    detectBanks: vi.fn(),
    parseFile: vi.fn(),
    ...overrides,
  };
}

describe('useBatchOrchestrator', () => {
  beforeEach(() => {
    mockElectronAPI();
  });

  describe('addFiles', () => {
    it('adds files with pending status and computed fileName', () => {
      const { result } = renderHook(() => useBatchOrchestrator());

      act(() => {
        result.current.addFiles(['/path/to/file.pdf', '/another/file.csv']);
      });

      expect(result.current.files).toHaveLength(2);
      expect(result.current.files[0]).toMatchObject({
        filePath: '/path/to/file.pdf',
        fileName: 'file.pdf',
        status: 'pending',
        transactionCount: 0,
      });
    });

    it('deduplicates files by filePath', () => {
      const { result } = renderHook(() => useBatchOrchestrator());

      act(() => {
        result.current.addFiles(['/path/a.pdf']);
        result.current.addFiles(['/path/a.pdf', '/path/b.pdf']);
      });

      expect(result.current.files).toHaveLength(2);
    });

    it('detectDone is false when no files are present', () => {
      const { result } = renderHook(() => useBatchOrchestrator());
      expect(result.current.detectDone).toBe(false);
    });
  });

  describe('removeFile', () => {
    it('removes a file by filePath', () => {
      const { result } = renderHook(() => useBatchOrchestrator());

      act(() => {
        result.current.addFiles(['/a.pdf', '/b.pdf']);
        result.current.removeFile('/a.pdf');
      });

      expect(result.current.files).toHaveLength(1);
      expect(result.current.files[0].filePath).toBe('/b.pdf');
    });
  });

  describe('clearFiles', () => {
    it('clears all files and resets currentIndex', () => {
      const { result } = renderHook(() => useBatchOrchestrator());

      act(() => {
        result.current.addFiles(['/a.pdf', '/b.pdf']);
        result.current.clearFiles();
      });

      expect(result.current.files).toHaveLength(0);
      expect(result.current.currentIndex).toBe(0);
    });
  });

  describe('detectOnly', () => {
    it('updates files with detected bank and docType', async () => {
      const detectBanks = vi.fn()
        .mockResolvedValueOnce({
          success: true,
          results: [{ filePath: '/a.pdf', bank: '工商银行', docType: '流水', status: 'ok' }],
        })
        .mockResolvedValueOnce({
          success: true,
          results: [{ filePath: '/b.pdf', bank: '招商银行', docType: '流水', status: 'ok' }],
        });
      mockElectronAPI({ detectBanks });

      const { result } = renderHook(() => useBatchOrchestrator());

      act(() => {
        result.current.addFiles(['/a.pdf', '/b.pdf']);
      });

      await act(async () => {
        await result.current.detectOnly();
      });

      expect(result.current.files[0]).toMatchObject({
        bank: '工商银行',
        docType: '流水',
        status: 'pending',
      });
      expect(result.current.files[1]).toMatchObject({
        bank: '招商银行',
        docType: '流水',
        status: 'pending',
      });
    });

    it('marks files with failed status when detection returns failed', async () => {
      const detectBanks = vi.fn().mockResolvedValue({
        success: true,
        results: [
          { filePath: '/a.pdf', bank: '未知银行', docType: 'unknown', status: 'failed' },
        ],
      });
      mockElectronAPI({ detectBanks });

      const { result } = renderHook(() => useBatchOrchestrator());

      act(() => {
        result.current.addFiles(['/a.pdf']);
      });

      await act(async () => {
        await result.current.detectOnly();
      });

      expect(result.current.files[0]).toMatchObject({
        status: 'failed',
        error: '检测失败',
      });
    });
  });

  describe('parseOnly', () => {
    it('parses files and updates results', async () => {
      const parseFile = vi.fn().mockResolvedValue({
        success: true,
        bank: '工商银行',
        docType: '流水',
        statementDate: '2026-01-15',
        transactions: [{ date: '2026-01-01', description: 'test', amount: 100 }],
      });
      mockElectronAPI({ parseFile });

      const { result } = renderHook(() => useBatchOrchestrator());

      act(() => {
        result.current.addFiles(['/a.pdf']);
        result.current.updateFile('/a.pdf', { bank: '工商银行', docType: '流水' });
      });

      await act(async () => {
        await result.current.parseOnly();
      });

      expect(result.current.files[0]).toMatchObject({
        status: 'success',
        transactionCount: 1,
      });
    });

    it('handles parse failures gracefully', async () => {
      const parseFile = vi.fn().mockRejectedValue(new Error('parse error'));
      mockElectronAPI({ parseFile });

      const { result } = renderHook(() => useBatchOrchestrator());

      act(() => {
        result.current.addFiles(['/a.pdf']);
        result.current.updateFile('/a.pdf', { bank: '工商银行', docType: '流水' });
      });

      await act(async () => {
        await result.current.parseOnly();
      });

      expect(result.current.files[0]).toMatchObject({
        status: 'failed',
        error: 'parse error',
      });
    });

    it('processes remaining files after one is removed between parseOnly calls (filesRef guard)', async () => {
      // 模拟用户中途删掉一个文件后再次点解析：filesRef 保证每次调用
      // parseOnly 都读到当前的 files 数组，不会访问已删除槽位崩溃。
      const parseFile = vi.fn()
        .mockResolvedValueOnce({
          success: true,
          bank: '工商银行',
          docType: '流水',
          statementDate: '2026-01-15',
          transactions: [{ date: '2026-01-01', description: 'a', amount: 100 }],
        })
        .mockResolvedValueOnce({
          success: true,
          bank: '工商银行',
          docType: '流水',
          statementDate: '2026-01-16',
          transactions: [{ date: '2026-01-02', description: 'b', amount: 200 }],
        });
      mockElectronAPI({ parseFile });

      const { result } = renderHook(() => useBatchOrchestrator());

      act(() => {
        result.current.addFiles(['/a.pdf', '/b.pdf']);
        result.current.updateFile('/a.pdf', { bank: '工商银行', docType: '流水' });
        result.current.updateFile('/b.pdf', { bank: '工商银行', docType: '流水' });
      });

      // 第一次 parseOnly：处理两个文件
      await act(async () => {
        await result.current.parseOnly();
      });
      expect(parseFile).toHaveBeenCalledTimes(2);
      expect(result.current.files).toHaveLength(2);
      expect(result.current.files.every((f) => f.status === 'success')).toBe(true);

      // 中途移除 /a.pdf，再次 parseOnly：只处理剩余的 /b.pdf
      parseFile.mockResolvedValueOnce({
        success: true,
        bank: '工商银行',
        docType: '流水',
        statementDate: '2026-01-17',
        transactions: [{ date: '2026-01-03', description: 'c', amount: 300 }],
      });

      act(() => {
        result.current.removeFile('/a.pdf');
      });

      await act(async () => {
        await result.current.parseOnly();
      });

      // filesRef 读到的已经是只剩 1 个文件的数组，parseFile 仅被调用 1 次
      expect(parseFile).toHaveBeenCalledTimes(3);
      expect(result.current.files).toHaveLength(1);
      expect(result.current.files[0].filePath).toBe('/b.pdf');
      expect(result.current.files[0].status).toBe('success');
    });
  });

  describe('updateFile', () => {
    it('patches a file with partial data', () => {
      const { result } = renderHook(() => useBatchOrchestrator());

      act(() => {
        result.current.addFiles(['/a.pdf']);
        result.current.updateFile('/a.pdf', { bank: '工商银行', isManual: true });
      });

      expect(result.current.files[0]).toMatchObject({
        bank: '工商银行',
        isManual: true,
      });
    });
  });

  describe('derived values', () => {
    it('computes successCount and failedCount correctly', () => {
      const { result } = renderHook(() => useBatchOrchestrator());

      act(() => {
        result.current.addFiles(['/a.pdf', '/b.pdf', '/c.pdf']);
        result.current.updateFile('/a.pdf', { status: 'success' as const, transactionCount: 5 });
        result.current.updateFile('/b.pdf', { status: 'failed' as const });
        result.current.updateFile('/c.pdf', { status: 'failed' as const });
      });

      expect(result.current.successCount).toBe(1);
      expect(result.current.failedCount).toBe(2);
      expect(result.current.totalCount).toBe(3);
    });
  });
});