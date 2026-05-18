import { useState, useCallback, useRef } from 'react';
import type { BatchFileResult, BatchResult } from '@shared/types';

interface UseBatchOrchestratorOptions {
  /** 最大文件数量限制，0 表示不限制 */
  maxFiles?: number;
  /** 解析完成回调 */
  onComplete?: (result: BatchResult) => void;
}

interface BatchOrchestrator {
  files: BatchFileResult[];
  isParsing: boolean;
  currentIndex: number;
  totalCount: number;
  successCount: number;
  failedCount: number;
  result: BatchResult | null;

  addFiles: (filePaths: string[]) => void;
  removeFile: (filePath: string) => void;
  clearFiles: () => void;

  detectAndParse: () => Promise<void>;
  retryFailedFiles: (filePaths: string[], bank: string, docType: string, forceOcr: boolean) => Promise<void>;

  getResult: () => BatchResult | null;
}

export function useBatchOrchestrator(
  opts: UseBatchOrchestratorOptions = {},
): BatchOrchestrator {
  const { onComplete } = opts;

  const [files, setFiles] = useState<BatchFileResult[]>([]);
  const [isParsing, setIsParsing] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const totalCount = files.length;
  const successCount = files.filter((f) => f.status === 'success').length;
  const failedCount = files.filter((f) => f.status === 'failed').length;

  const result: BatchResult | null = totalCount > 0
    ? {
        files,
        totalFiles: totalCount,
        successCount,
        failedCount,
        totalTransactions: files.reduce((s, f) => s + f.transactionCount, 0),
      }
    : null;

  const addFiles = useCallback((filePaths: string[]) => {
    setFiles((prev) => {
      const merged = [...prev];
      for (const fp of filePaths) {
        if (!merged.some((f) => f.filePath === fp)) {
          merged.push({
            filePath: fp,
            fileName: fp.split(/[/\\]/).pop() || fp,
            bank: '',
            docType: '',
            status: 'pending',
            transactionCount: 0,
          });
        }
      }
      return merged;
    });
  }, []);

  const removeFile = useCallback((filePath: string) => {
    setFiles((prev) => prev.filter((f) => f.filePath !== filePath));
  }, []);

  const clearFiles = useCallback(() => {
    setFiles([]);
    setCurrentIndex(0);
  }, []);

  const detectAndParse = useCallback(async () => {
    if (isParsing || files.length === 0) return;
    setIsParsing(true);

    try {
      const detectResp = await (window as any).electronAPI?.detectBanks?.(
        files.map((f) => f.filePath),
      );

      const detectMap: Record<string, { bank: string; docType: string }> = {};
      if (detectResp?.success && detectResp.results) {
        detectResp.results.forEach((r: any) => {
          detectMap[r.filePath] = { bank: r.bank, docType: r.docType };
        });
      }

      const updatedFiles: BatchFileResult[] = files.map((f) => ({
        ...f,
        bank: detectMap[f.filePath]?.bank || f.bank || '',
        docType: detectMap[f.filePath]?.docType || f.docType || 'unknown',
      }));
      setFiles(updatedFiles);

      const results: BatchFileResult[] = [];

      for (let i = 0; i < updatedFiles.length; i++) {
        const file = updatedFiles[i];
        setCurrentIndex(i + 1);

        try {
          const params: any = { filePath: file.filePath };
          if (file.bank) params.bank = file.bank;

          const r = await (window as any).electronAPI?.parsePdf?.(params);

          if (r?.success) {
            results.push({
              filePath: file.filePath,
              fileName: file.fileName,
              bank: r.bank || file.bank || '未知',
              docType: r.docType || file.docType || 'unknown',
              statementDate: r.statementDate,
              status: 'success',
              transactions: r.transactions,
              transactionCount: r.transactions?.length || 0,
            });
          } else {
            results.push({
              filePath: file.filePath,
              fileName: file.fileName,
              bank: file.bank || '未知',
              docType: file.docType || 'unknown',
              status: 'failed',
              error: r?.error || '解析失败',
              transactionCount: 0,
            });
          }
        } catch (err: any) {
          results.push({
            filePath: file.filePath,
            fileName: file.fileName,
            bank: file.bank || '未知',
            docType: file.docType || 'unknown',
            status: 'failed',
            error: err.message,
            transactionCount: 0,
          });
        }
      }

      setFiles(results);
      onCompleteRef.current?.({
        files: results,
        totalFiles: results.length,
        successCount: results.filter((f) => f.status === 'success').length,
        failedCount: results.filter((f) => f.status === 'failed').length,
        totalTransactions: results.reduce((s, f) => s + f.transactionCount, 0),
      });
    } finally {
      setIsParsing(false);
      setCurrentIndex(0);
    }
  }, [files, isParsing]);

  const retryFailedFiles = useCallback(async (
    filePaths: string[],
    bank: string,
    docType: string,
    forceOcr: boolean,
  ) => {
    for (let i = 0; i < filePaths.length; i++) {
      const fp = filePaths[i];
      setCurrentIndex(i + 1);

      try {
        const params: any = { filePath: fp, bank };
        if (docType) params.docType = docType;
        if (forceOcr) params.forceOcr = true;

        const result = await (window as any).electronAPI?.parsePdf?.(params);

        if (result.success) {
          const newFile: BatchFileResult = {
            filePath: fp,
            fileName: fp.split(/[/\\]/).pop() || fp,
            bank: result.bank || bank,
            docType: result.docType || docType,
            statementDate: result.statementDate,
            status: 'success',
            transactions: result.transactions,
            transactionCount: result.transactions?.length || 0,
          };
          setFiles((prev) => [...prev.filter((f) => f.filePath !== fp), newFile]);
        } else {
          const newFile: BatchFileResult = {
            filePath: fp,
            fileName: fp.split(/[/\\]/).pop() || fp,
            bank,
            docType,
            status: 'failed',
            error: result.error,
            transactionCount: 0,
          };
          setFiles((prev) => [...prev.filter((f) => f.filePath !== fp), newFile]);
        }
      } catch (err: any) {
        const newFile: BatchFileResult = {
          filePath: fp,
          fileName: fp.split(/[/\\]/).pop() || fp,
          bank,
          docType,
          status: 'failed',
          error: err.message,
          transactionCount: 0,
        };
        setFiles((prev) => [...prev.filter((f) => f.filePath !== fp), newFile]);
      }
    }

    setCurrentIndex(0);
  }, [files]);

  const getResult = useCallback(() => result, [result]);

  return {
    files,
    isParsing,
    currentIndex,
    totalCount,
    successCount,
    failedCount,
    result,

    addFiles,
    removeFile,
    clearFiles,

    detectAndParse,
    retryFailedFiles,

    getResult,
  };
}
