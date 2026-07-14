import { useState, useCallback, useRef } from 'react';
import { message } from 'antd';
import type { BatchFileResult, BatchResult, ParseFileParams, DocType } from '@shared/types';
import { getFileNameFromPath } from '../utils/pathUtils';

interface UseBatchOrchestratorOptions {
  maxFiles?: number;
  onComplete?: (result: BatchResult) => void;
}

interface BatchOrchestrator {
  files: BatchFileResult[];
  isParsing: boolean;
  isDetecting: boolean;
  currentIndex: number;
  totalCount: number;
  successCount: number;
  failedCount: number;
  detectDone: boolean;
  allConfigured: boolean;
  result: BatchResult | null;

  addFiles: (filePaths: string[]) => void;
  removeFile: (filePath: string) => void;
  clearFiles: () => void;
  updateFile: (filePath: string, patch: Partial<BatchFileResult>) => void;

  detectOnly: () => Promise<void>;
  parseOnly: () => Promise<void>;
  retryFailedFiles: (filePaths: string[], bank: string, docType: string, forceOcr: boolean) => Promise<void>;

  getResult: () => BatchResult | null;
}

type BatchPhase = 'idle' | 'detecting' | 'parsing';

export function useBatchOrchestrator(
  opts: UseBatchOrchestratorOptions = {},
): BatchOrchestrator {
  const { onComplete } = opts;

  const [files, setFiles] = useState<BatchFileResult[]>([]);
  const filesRef = useRef(files);
  filesRef.current = files;
  const [isParsing, setIsParsing] = useState(false);
  const [phase, setPhase] = useState<BatchPhase>('idle');
  const [currentIndex, setCurrentIndex] = useState(0);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const totalCount = files.length;
  const successCount = files.filter((f) => f.status === 'success').length;
  const failedCount = files.filter((f) => f.status === 'failed').length;
  const isDetecting = phase === 'detecting';
  const detectDone = totalCount > 0 && phase === 'idle';
  const allConfigured = totalCount > 0 && files.every((f) => f.bank && f.bank !== '未知' && f.bank !== 'UNKNOWN' && f.docType);

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
            fileName: getFileNameFromPath(fp),
            bank: '',
            docType: '流水',
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

  const updateFile = useCallback((filePath: string, patch: Partial<BatchFileResult>) => {
    setFiles((prev) =>
      prev.map((f) => (f.filePath === filePath ? { ...f, ...patch } : f)),
    );
  }, []);

  const clearFiles = useCallback(() => {
    setFiles([]);
    setCurrentIndex(0);
  }, []);

  const detectOnly = useCallback(async () => {
    if (phase !== 'idle' || files.length === 0) return;
    setPhase('detecting');
    setCurrentIndex(0);
    setFiles((prev) =>
      prev.map((f) => ({ ...f, status: 'pending' as const, bank: '', docType: '流水', error: undefined, isManual: false, transactionCount: 0, transactions: undefined })),
    );
    try {
      for (let i = 0; i < filesRef.current.length; i++) {
        const file = filesRef.current[i];
        if (!file) continue;
        setCurrentIndex(i + 1);

        const detectResp = await window.electronAPI?.detectBanks?.([file.filePath]);

        if (detectResp?.success && detectResp.results?.length > 0) {
          const detected = detectResp.results[0];
          setFiles((prev) =>
            prev.map((f) => {
              if (f.filePath !== file.filePath) return f;
              return {
                ...f,
                bank: detected.bank,
                docType: detected.docType,
                status: detected.status === 'ok' ? 'pending' : 'failed',
                error: detected.status === 'failed' ? '检测失败' : f.error,
              };
            }),
          );
        }
      }
    } catch (err: any) {
      message.error('检测失败：' + err.message);
    } finally {
      setPhase('idle');
      setCurrentIndex(0);
    }
  }, [files, phase]);

  const parseOnly = useCallback(async () => {
    if (phase !== 'idle' || files.length === 0) return;
    setPhase('parsing');
    setIsParsing(true);
    setCurrentIndex(0);
    setFiles((prev) =>
      prev.map((f) => ({ ...f, status: 'pending' as const, error: undefined, transactionCount: 0, transactions: undefined })),
    );

    const latestFiles: BatchFileResult[] = files.map((f) => ({ ...f, status: 'pending' as const, error: undefined, transactionCount: 0, transactions: undefined }));

    try {
      for (let i = 0; i < filesRef.current.length; i++) {
        const file = filesRef.current[i];
        if (!file) continue;
        setCurrentIndex(i + 1);

        let updated: BatchFileResult;

        // 强制验证：银行和文件类型必须都已配置，否则跳过
        const isUnknownBank = !file.bank ||
          file.bank === '未知' || file.bank === '未知银行' ||
          file.bank === 'UNKNOWN';
        const isMissingDocType = !file.docType;

        if (isUnknownBank || isMissingDocType) {
          updated = {
            filePath: file.filePath,
            fileName: file.fileName,
            bank: file.bank || '未知',
            docType: file.docType || '流水',
            status: 'failed',
            error: '无法识别银行类型或文件类型，请手动选择银行和文件类型后再解析',
            transactionCount: 0,
          };
        } else {
          try {
            const params: ParseFileParams = { filePath: file.filePath };
            if (file.bank) params.bank = file.bank;
            if (file.docType) params.docType = file.docType;

            const r = await window.electronAPI?.parseFile?.(params);

            if (r?.success) {
              updated = {
                filePath: file.filePath,
                fileName: file.fileName,
                bank: r.bank || file.bank || '未知',
                docType: r.docType || file.docType || 'unknown',
                statementDate: r.statementDate,
                status: 'success',
                transactions: r.transactions,
                transactionCount: r.transactions?.length || 0,
              };
            } else {
              updated = {
                filePath: file.filePath,
                fileName: file.fileName,
                bank: file.bank || '未知',
                docType: file.docType || '流水',
                status: 'failed',
                error: r?.errors?.join(", ") || '解析失败',
                transactionCount: 0,
              };
            }
          } catch (err: any) {
            updated = {
              filePath: file.filePath,
              fileName: file.fileName,
              bank: file.bank || '未知',
              docType: file.docType || '流水',
              status: 'failed',
              error: err.message,
              transactionCount: 0,
            };
          }
        }

        latestFiles[i] = updated;

        // 每解析完一个立即更新状态，让 UI 实时显示已完成的结果
        setFiles((prev) => {
          const next = [...prev];
          next[i] = updated;
          return next;
        });
      }

      onCompleteRef.current?.({
        files: latestFiles,
        totalFiles: latestFiles.length,
        successCount: latestFiles.filter((f) => f.status === 'success').length,
        failedCount: latestFiles.filter((f) => f.status === 'failed').length,
        totalTransactions: latestFiles.reduce((s, f) => s + f.transactionCount, 0),
      });
    } finally {
      setPhase('idle');
      setIsParsing(false);
      setCurrentIndex(0);
    }
  }, [files, phase]);

  const retryFailedFiles = useCallback(async (
    filePaths: string[],
    bank: string,
    docType: string,
    forceOcr: boolean,
  ) => {
    setPhase('parsing');
    setIsParsing(true);
    setCurrentIndex(0);

    for (let i = 0; i < filePaths.length; i++) {
      const fp = filePaths[i];
      setCurrentIndex(i + 1);

      try {
        const params: ParseFileParams = { filePath: fp, bank };
        if (docType) params.docType = docType as DocType;
        if (forceOcr) params.forceOcr = true;

        const r = await window.electronAPI?.parseFile?.(params);

        if (r.success) {
          setFiles((prev) =>
            prev.map((f) =>
              f.filePath === fp
                ? {
                    filePath: fp,
                    fileName: getFileNameFromPath(fp),
                    bank: r.bank || bank,
                    docType: r.docType || docType,
                    statementDate: r.statementDate,
                    status: 'success' as const,
                    transactions: r.transactions,
                    transactionCount: r.transactions?.length || 0,
                  }
                : f,
            ),
          );
        } else {
          setFiles((prev) =>
            prev.map((f) =>
              f.filePath === fp
                ? {
                    filePath: fp,
                    fileName: getFileNameFromPath(fp),
                    bank,
                    docType: docType as DocType,
                    status: 'failed' as const,
                    error: r.errors?.join(", ") || "解析失败",
                    transactionCount: 0,
                  }
                : f,
            ),
          );
        }
      } catch (err: any) {
        setFiles((prev) =>
          prev.map((f) =>
            f.filePath === fp
              ? {
                  filePath: fp,
                  fileName: getFileNameFromPath(fp),
                  bank,
                  docType: docType as DocType,
                  status: 'failed' as const,
                  error: err.message,
                  transactionCount: 0,
                }
              : f,
          ),
        );
      }
    }
    setPhase('idle');
    setIsParsing(false);
    setCurrentIndex(0);
  }, []);

  const getResult = useCallback(() => result, [result]);

  return {
    files,
    isParsing,
    isDetecting,
    currentIndex,
    totalCount,
    successCount,
    failedCount,
    detectDone,
    allConfigured,
    result,

    addFiles,
    removeFile,
    clearFiles,
    updateFile,

    detectOnly,
    parseOnly,

    retryFailedFiles,

    getResult,
  };
}
