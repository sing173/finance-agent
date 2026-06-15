import { useState, useCallback } from 'react';
import { message } from 'antd';
import type { ParseFileParams, ParseFileResult, DocType } from '@shared/types';

type DetectState = 'idle' | 'detecting' | 'detected' | 'unknown';

export function useSingleFile() {
  const [detectState, setDetectState] = useState<DetectState>('idle');
  const [detectInfo, setDetectInfo] = useState<{ bank: string; docType: string; isManual: boolean }>({
    bank: '',
    docType: '',
    isManual: false,
  });
  const [filePath, setFilePath] = useState<string | null>(null);
  const [result, setResult] = useState<ParseFileResult | null>(null);
  const [loading, setLoading] = useState(false);

  const detect = useCallback(async (fp: string) => {
    setFilePath(fp);
    setResult(null);
    setDetectState('detecting');
    setDetectInfo({ bank: '', docType: '', isManual: false });

    try {
      const ext = fp.toLowerCase().split('.').pop();
      const fileType = ext === 'csv' ? 'CSV' : ext === 'xlsx' ? 'Excel' : 'PDF';
      message.info(`正在检测${fileType}文件...`);

      const res = await window.electronAPI.detectBanks([fp]);
      const detected = res?.results?.[0];

      if (detected && detected.status === 'ok' && detected.bank && detected.bank !== '未知银行') {
        setDetectInfo({ bank: detected.bank, docType: detected.docType || 'unknown', isManual: false });
        setDetectState('detected');
        message.success(`检测到：${detected.bank} · ${detected.docType || 'unknown'}`);
      } else {
        setDetectInfo({ bank: '未知', docType: 'unknown', isManual: false });
        setDetectState('unknown');
        message.warning('未能自动识别银行类型');
      }
    } catch (error: unknown) {
      setDetectInfo({ bank: '未知', docType: 'unknown', isManual: false });
      setDetectState('unknown');
      message.error('检测失败：' + (error instanceof Error ? error.message : String(error)));
    }
  }, []);

  const parse = useCallback(async (opts?: { bank?: string; docType?: string; forceOcr?: boolean }) => {
    const fp = filePath;
    if (!fp) return;

    const bank = opts?.bank ?? detectInfo.bank;
    const docType = opts?.docType ?? detectInfo.docType;
    const forceOcr = opts?.forceOcr ?? false;

    setLoading(true);

    try {
      const effectiveBank = (bank === '未知' || bank === '未知银行' || !bank) ? undefined : bank;
      message.info(`正在解析${effectiveBank ? `（${effectiveBank} · ${docType}）` : '...'}...`);

      const params: ParseFileParams = { filePath: fp };
      if (effectiveBank) params.bank = effectiveBank;
      if (docType) params.docType = docType as DocType;
      if (forceOcr) params.forceOcr = true;

      const res = await window.electronAPI.parseFile(params);

      if (res.success) {
        setResult(res);
        setDetectState('detected');
        setDetectInfo({ bank: res.bank || bank, docType: res.docType || docType, isManual: false });
        message.success(`解析成功，共 ${res.transactions?.length || 0} 笔交易`);
      } else {
        message.error(`解析失败：${res.errors?.join(', ') || '未知错误'}`);
      }
    } catch (error: unknown) {
      message.error(`解析出错：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setLoading(false);
    }
  }, [filePath, detectInfo]);

  const applyOverride = useCallback((bank: string, docType: string) => {
    setDetectInfo({ bank, docType, isManual: true });
    setDetectState('detected');
  }, []);

  const reset = useCallback(() => {
    setDetectState('idle');
    setDetectInfo({ bank: '', docType: '', isManual: false });
    setFilePath(null);
    setResult(null);
    setLoading(false);
  }, []);

  return {
    detectState,
    detectInfo,
    filePath,
    result,
    loading,
    detect,
    parse,
    applyOverride,
    setResult,
    reset,
  };
}
