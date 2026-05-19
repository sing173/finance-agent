import { Layout, Typography, Button, Card, message, Space, Modal, Form, Input } from 'antd';
import { useState, useEffect, useCallback } from 'react';
import { FileDropZone } from './components/FileDropZone';
import { TransactionTable } from './components/TransactionTable';
import { ProgressSteps } from './components/ProgressSteps';
import { ResultCard } from './components/ResultCard';
import { ManualOverrideModal } from './components/ManualOverrideModal';
import { BatchFileSelector } from './components/BatchFileSelector';
import { BatchResultPanel } from './components/BatchResultPanel';
import { useBatchOrchestrator } from './hooks/useBatchOrchestrator';
import type { BatchResult } from '@shared/types';

const { Header, Content, Footer } = Layout;
const { Title, Text } = Typography;

// 声明 window.electronAPI 类型
declare global {
  interface Window {
    electronAPI: {
      health: () => Promise<any>;
      parsePDF: (path: string) => Promise<any>;
      parsePdf: (params: any) => Promise<any>;
      generateExcel: (params: any) => Promise<any>;
      generateVoucher: (params: any) => Promise<any>;
      importSubjects: (params: any) => Promise<any>;
      getSubjectsInfo: () => Promise<any>;
      ocrPDF: (params: any) => Promise<any>;
      chat: (msg: string, sessionKey?: string) => Promise<any>;
      selectFile: (filter?: string, allowMulti?: boolean) => Promise<string[] | string | null>;
      saveFileDialog: (params?: any) => Promise<string | null>;
      detectBanks: (filePaths: string[]) => Promise<any>;
      detectSupportedBanks: () => Promise<any>;
      onPythonStatus: (callback: (status: string) => void) => void;
      getPythonStatus: () => Promise<string>;
    };
  }
}

type OverrideContext = {
  fileCount: number;
  isPdfOnly: boolean;
  onConfirm: (bank: string, docType: string, forceOcr: boolean) => void;
};

// 单文件检测阶段状态
type DetectState = 'idle' | 'detecting' | 'detected' | 'unknown';

function App() {
  // ====== 模式 & 结果 ======
  const [mode, setMode] = useState<'single' | 'batch'>('single');
  const [currentResult, setCurrentResult] = useState<any>(null);
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);

  // ====== 单文件检测阶段 ======
  const [detectState, setDetectState] = useState<DetectState>('idle');
  const [detectInfo, setDetectInfo] = useState<{ bank: string; docType: string }>({ bank: '', docType: '' });
  const [currentFilePath, setCurrentFilePath] = useState<string | null>(null);

  // ====== 加载 & 进度 ======
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [processingTimeMs, setProcessingTimeMs] = useState(0);

  // ====== 批量编排 ======
  const batch = useBatchOrchestrator({
    onComplete: (result) => {
      setBatchResult(result);
    },
  });

  // ====== 凭证导出 ======
  const [voucherModalOpen, setVoucherModalOpen] = useState(false);
  const [voucherLoading, setVoucherLoading] = useState(false);
  const [period, setPeriod] = useState('');

  // ====== 科目管理 ======
  const [importSubjectsLoading, setImportSubjectsLoading] = useState(false);
  const [subjectsCount, setSubjectsCount] = useState<number | null>(null);
  const [backendStatus, setBackendStatus] = useState<string>('检查中...');

  // ====== 手动覆盖模态框 ======
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [overrideContext, setOverrideContext] = useState<OverrideContext | null>(null);
  const [overrideInitialBank, setOverrideInitialBank] = useState('');
  const [overrideInitialDocType, setOverrideInitialDocType] = useState('');
  const [overrideInitialOcr, setOverrideInitialOcr] = useState(false);

  // ====== 启动时查询 ======
  useEffect(() => {
    const checkSubjects = async () => {
      try {
        const result = await window.electronAPI.getSubjectsInfo();
        if (result.success) setSubjectsCount(result.count);
      } catch { /* ignore */ }
    };
    checkSubjects();

    window.electronAPI.getPythonStatus?.().then((status: string) => {
      setBackendStatus(status === 'online' ? '正常' : '离线');
    }).catch(() => setBackendStatus('离线'));

    window.electronAPI.onPythonStatus?.((status: string) => {
      if (status === 'offline') { setBackendStatus('离线'); setCurrentResult(null); }
      else if (status === 'online') setBackendStatus('正常（已恢复）');
      else if (status === 'error') setBackendStatus('错误');
    });
  }, []);

  // ====== 连接测试 ======
  const testConnection = useCallback(async () => {
    setLoading(true);
    try {
      const result = await window.electronAPI.health();
      setBackendStatus(`正常 (v${result.version})`);
      message.success('后端连接成功！');
    } catch (error: unknown) {
      setBackendStatus(`离线: ${error instanceof Error ? error.message : String(error)}`);
      message.error('后端连接失败');
    } finally {
      setLoading(false);
    }
  }, []);

  // ====== 统一入口：选择文件 → 根据数量决定模式 ======
  const handleFilesSelected = useCallback((filePaths: string[]) => {
    if (!filePaths || filePaths.length === 0) return;

    if (filePaths.length === 1) {
      // 单文件模式
      setMode('single');
      setBatchResult(null);
      setCurrentStep(0);
      setProcessingTimeMs(0);
      handleSingleFileDetect(filePaths[0]);
    } else {
      // 批量模式
      setMode('batch');
      setCurrentResult(null);
      setCurrentStep(0);
      setProcessingTimeMs(0);
      setVoucherModalOpen(false);
      batch.clearFiles();
      batch.addFiles(filePaths);
    }
  }, [batch.clearFiles, batch.addFiles]);

  // ====== 单文件：检测银行 ======
  const handleSingleFileDetect = useCallback(async (filePath: string) => {
    setCurrentFilePath(filePath);
    setCurrentResult(null);
    setDetectState('detecting');
    setDetectInfo({ bank: '', docType: '' });

    try {
      const ext = filePath.toLowerCase().split('.').pop();
      const fileType = ext === 'csv' ? 'CSV' : ext === 'xlsx' ? 'Excel' : 'PDF';
      message.info(`正在检测${fileType}文件...`);

      const result = await window.electronAPI.detectBanks([filePath]);
      const detected = result?.results?.[0];

      if (detected && detected.status === 'ok' && detected.bank && detected.bank !== '未知银行') {
        setDetectInfo({ bank: detected.bank, docType: detected.docType || 'unknown' });
        setDetectState('detected');
        message.success(`检测到：${detected.bank} · ${detected.docType || 'unknown'}`);
      } else {
        setDetectInfo({ bank: '未知', docType: 'unknown' });
        setDetectState('unknown');
        message.warning('未能自动识别银行类型');
      }
    } catch (error: unknown) {
      setDetectInfo({ bank: '未知', docType: 'unknown' });
      setDetectState('unknown');
      message.error('检测失败：' + (error instanceof Error ? error.message : String(error)));
    }
  }, []);

  // ====== 单文件：确认解析 ======
  const handleSingleFileParse = useCallback(async (filePath: string, bank: string, docType: string, forceOcr: boolean) => {
    if (!filePath) return;
    setLoading(true);
    setCurrentStep(0);
    const startTime = Date.now();
    setOverrideModalOpen(false);

    try {
      // 未知银行时传 '未知银行'，让后端走 generic BankStatementParser fallback
      const effectiveBank = (bank === '未知' || bank === '未知银行' || !bank) ? undefined : bank;
      message.info(`正在解析${effectiveBank ? `（${effectiveBank} · ${docType}）` : '...'}...`);
      const params: any = { filePath };
      if (effectiveBank) params.bank = effectiveBank;
      if (docType) params.docType = docType;
      if (forceOcr) params.forceOcr = true;

      const result = await window.electronAPI.parsePdf(params);
      setCurrentStep(1);
      setProcessingTimeMs(Date.now() - startTime);

      if (result.success) {
        setCurrentResult(result);
        setDetectState('detected');
        setDetectInfo({ bank: result.bank || bank, docType: result.docType || docType });
        message.success(`解析成功，共 ${result.transactions?.length || 0} 笔交易`);
      } else {
        message.error(`解析失败：${result.error}`);
      }
    } catch (error: unknown) {
      message.error(`解析出错：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  // ====== 单文件：从 fallback 确认解析 ======
  const handleSingleOverrideConfirm = useCallback((bank: string, docType: string, forceOcr: boolean) => {
    if (currentFilePath) {
      handleSingleFileParse(currentFilePath, bank, docType, forceOcr);
    }
  }, [currentFilePath, handleSingleFileParse]);

  // ====== 打开单文件 fallback 模态框 ======
  const openSingleOverride = useCallback(() => {
    const ext = currentFilePath?.toLowerCase().split('.').pop();
    const isPdfOnly = ext === 'pdf';
    setOverrideInitialBank(detectInfo.bank || '');
    setOverrideInitialDocType(detectInfo.docType || '');
    setOverrideInitialOcr(false);
    setOverrideContext({
      fileCount: 1,
      isPdfOnly,
      onConfirm: handleSingleOverrideConfirm,
    });
    setOverrideModalOpen(true);
  }, [detectInfo, handleSingleOverrideConfirm, currentFilePath]);

  // ====== 打开批量 fallback 模态框 ======
  const openBatchOverride = useCallback((filePaths: string[]) => {
    const allPdf = filePaths.every(fp => fp.toLowerCase().endsWith('.pdf'));
    setOverrideInitialBank('');
    setOverrideInitialDocType('');
    setOverrideInitialOcr(false);
    setOverrideContext({
      fileCount: filePaths.length,
      isPdfOnly: allPdf,
      onConfirm: (bank: string, docType: string, forceOcr: boolean) => {
        batch.retryFailedFiles(filePaths, bank, docType, forceOcr);
      },
    });
    setOverrideModalOpen(true);
  }, [batch.retryFailedFiles]);

  // ====== 导出 Excel ======
  const handleExportExcel = useCallback(async () => {
    const txns = mode === 'single' ? currentResult?.transactions : undefined;
    if (!txns?.length) {
      message.warning('没有可导出的交易数据');
      return;
    }

    setCurrentStep(1);
    setLoading(true);
    try {
      const outputPath = `bank_statement_${Date.now()}.xlsx`;
      const result = await window.electronAPI.generateExcel({
        transactions: txns,
        output_path: outputPath,
      });
      setCurrentStep(2);
      if (result.success) {
        message.success(`Excel 已导出: ${result.excel_path}`);
      } else {
        message.error(`导出失败：${result.error}`);
      }
    } catch (error: unknown) {
      message.error(`导出出错：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setLoading(false);
    }
  }, [mode, currentResult]);

  // ====== 导出凭证（单文件） ======
  const handleOpenVoucherModal = useCallback(() => {
    if (!period && currentResult?.transactions?.length) {
      const dates: string[] = currentResult.transactions.map((t: any) => t.date as string);
      dates.sort();
      const earliest = dates[0];
      const [y, m] = earliest.split('-');
      setPeriod(`${y}年${Number(m)}月`);
    }
    setVoucherModalOpen(true);
  }, [currentResult, period]);

  const handleExportVoucher = useCallback(async () => {
    const txns = mode === 'single' ? currentResult?.transactions : undefined;
    if (!txns?.length) {
      message.warning('没有可导出的交易数据');
      return;
    }

    const defaultName = `voucher_${period || Date.now()}.xlsx`;
    const outputPath = await window.electronAPI.saveFileDialog({
      title: '保存凭证 Excel',
      defaultPath: defaultName,
    });
    if (!outputPath) return;

    setVoucherLoading(true);
    try {
      const result = await window.electronAPI.generateVoucher({
        transactions: txns,
        output_path: outputPath,
        period,
      });

      if (result.success) {
        message.success(`凭证已导出: ${result.excel_path}`);
        setVoucherModalOpen(false);
      } else {
        message.error(`导出失败：${result.error}`);
      }
    } catch (error: unknown) {
      message.error(`导出出错：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setVoucherLoading(false);
    }
  }, [mode, currentResult, period]);

  // ====== 导入科目表 ======
  const handleImportSubjects = useCallback(async () => {
    const filePath = await window.electronAPI.selectFile('xlsx');
    if (!filePath) return;

    setImportSubjectsLoading(true);
    try {
      const result = await window.electronAPI.importSubjects({ xlsx_path: filePath });
      if (result.success) {
        setSubjectsCount(result.count);
        message.success(`科目表导入成功，共 ${result.count} 条科目`);
      } else {
        message.error(`导入失败：${result.error}`);
      }
    } catch (error: unknown) {
      message.error(`导入出错：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setImportSubjectsLoading(false);
    }
  }, []);

  // ====== 单文件结果卡片 handlers ======
  const handleSingleReselectFile = useCallback(() => {
    setCurrentResult(null);
    setDetectState('idle');
    setDetectInfo({ bank: '', docType: '' });
    setCurrentFilePath(null);
    setCurrentStep(0);
    setProcessingTimeMs(0);
  }, []);

  // ====== 单文件：确认解析按钮（检测阶段） ======
  const handleSingleConfirmParse = useCallback(() => {
    if (currentFilePath) {
      handleSingleFileParse(currentFilePath, detectInfo.bank, detectInfo.docType, false);
    }
  }, [currentFilePath, detectInfo, handleSingleFileParse]);

  // ====== 批量：开始解析 ======
  const handleBatchStartParse = useCallback(() => {
    batch.parseOnly();
  }, [batch.parseOnly]);

  // ====== 批量：修改单文件配置（不解析） ======
  const handleBatchModifyConfig = useCallback((filePath: string) => {
    const file = batch.files.find((f) => f.filePath === filePath);
    if (!file) return;

    const ext = file.filePath.toLowerCase().split('.').pop();
    const isPdfOnly = ext === 'pdf';
    setOverrideInitialBank(file.bank || '');
    setOverrideInitialDocType(file.docType || '');
    setOverrideInitialOcr(false);
    setOverrideContext({
      fileCount: 1,
      isPdfOnly,
      onConfirm: (bank: string, docType: string, _forceOcr: boolean) => {
        // 只更新检测值，不触发解析
        batch.updateFile(filePath, { bank, docType, error: undefined });
      },
    });
    setOverrideModalOpen(true);
  }, [batch.files, batch.updateFile]);

  // ====== 批量：addFiles / detectOnly / parse / clear ======
  const handleBatchAddFiles = useCallback((filePaths: string[]) => {
    batch.addFiles(filePaths);
  }, [batch.addFiles]);

  const handleBatchDetectOnly = useCallback(() => {
    batch.detectOnly();
  }, [batch.detectOnly]);

  const handleBatchClear = useCallback(() => {
    batch.clearFiles();
    setBatchResult(null);
  }, [batch.clearFiles]);

  // ====== 批量：重试单个失败文件 ======
  const handleBatchRetry = useCallback((filePaths: string[]) => {
    openBatchOverride(filePaths);
  }, [openBatchOverride]);

  // ====== 批量：导出凭证（合并所有成功文件） ======
  const handleBatchExportVoucher = useCallback(async () => {
    if (!batchResult) return;
    const allTxns = batchResult.files.flatMap((f) =>
      f.status === 'success' ? (f.transactions || []) : []
    );
    if (!allTxns.length) {
      message.warning('没有可导出的交易数据');
      return;
    }

    const defaultName = `batch_voucher_${Date.now()}.xlsx`;
    const outputPath = await window.electronAPI.saveFileDialog({
      title: '保存凭证 Excel',
      defaultPath: defaultName,
    });
    if (!outputPath) return;

    setVoucherLoading(true);
    try {
      const result = await window.electronAPI.generateVoucher({
        transactions: allTxns,
        output_path: outputPath,
        period,
      });
      if (result.success) {
        message.success(`凭证已导出: ${result.excel_path}`);
      } else {
        message.error(`导出失败：${result.error}`);
      }
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : String(error);
      message.error(`导出出错：${msg}`);
    } finally {
      setVoucherLoading(false);
    }
  }, [batchResult, period]);

  // ====== 辅助 ======
  const detectUnknown = detectState === 'unknown';

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 24px' }}>
        <Title level={3} style={{ color: '#fff', margin: '16px 0' }}>
          Finance Assistant
        </Title>
      </Header>
      <Content style={{ padding: '20px 24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

          {/* ====== 第一行：系统设置 + 文件选择 ====== */}
          <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            {/* 系统设置卡片 */}
            <Card title="系统设置" style={{ width: 400, flexShrink: 0, height: 200 }}>
              <div style={{ marginBottom: 16 }}>
                <Text type="secondary">后端状态：</Text>
                <Text strong>{backendStatus}</Text>
              </div>
              <Space style={{ marginBottom: 16 }}>
                <Button type="primary" loading={loading} onClick={testConnection}>
                  测试连接
                </Button>
                <Button loading={importSubjectsLoading} onClick={handleImportSubjects}>
                  导入科目表
                </Button>
              </Space>
              <div>
                <Text type="secondary">
                  当前内置科目：{subjectsCount !== null ? `${subjectsCount} 条` : '未知'}
                </Text>
                {subjectsCount !== null && subjectsCount > 0 && (
                  <Text type="success" style={{ marginLeft: 8 }}>✓ 已就绪</Text>
                )}
              </div>
            </Card>

            {/* 统一文件选择入口 */}
            <div style={{ flex: 1, minWidth: 400 }}>
              <FileDropZone onFilesSelected={handleFilesSelected} />
            </div>
          </div>

          {/* ====== 单文件模式视图 ====== */}
          {mode === 'single' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* 检测阶段：展示结果 + [确认解析] / [修改配置] */}
              {detectState === 'detecting' && (
                <Card title="检测中">
                  <Text type="secondary">正在识别银行类型...</Text>
                </Card>
              )}

              {(detectState === 'detected' || detectState === 'unknown') && (
                <ResultCard
                  bank={detectInfo.bank || '未知'}
                  docType={detectInfo.docType || '未知'}
                  isManual={false}
                  transactionCount={0}
                  statementDate={undefined}
                  error={detectUnknown ? '未能自动识别银行类型' : undefined}
                  onRedetect={() => currentFilePath && handleSingleFileDetect(currentFilePath)}
                  onModifyConfig={openSingleOverride}
                  onReselectFile={handleSingleReselectFile}
                  onConfirmParse={handleSingleConfirmParse}
                />
              )}

              {/* 解析结果展示 */}
              {currentResult && (
                <>
                  {/* 解析成功 */}
                  {currentResult.success && currentResult.transactions?.length > 0 && (
                    <>
                      <Card title="导出">
                        <Space>
                          <Button type="primary" loading={loading} onClick={handleExportExcel}>
                            导出 Excel（流水表）
                          </Button>
                          <Button
                            type="primary"
                            style={{ background: '#52c41a', borderColor: '#52c41a' }}
                            loading={loading}
                            onClick={handleOpenVoucherModal}
                          >
                            导出凭证（精斗云）
                          </Button>
                          <Button onClick={handleSingleReselectFile}>重新选择文件</Button>
                        </Space>
                      </Card>

                      {(loading || currentStep > 0) && (
                        <Card title="处理进度">
                          <ProgressSteps currentStep={currentStep} processingTime={processingTimeMs} />
                        </Card>
                      )}

                      <Card title="交易列表">
                        <TransactionTable
                          transactions={currentResult.transactions}
                          loading={loading}
                        />
                      </Card>
                    </>
                  )}

                  {/* 解析失败 */}
                  {(!currentResult.success || !currentResult.transactions?.length) && (
                    <>
                      <Card title="处理进度">
                        <ProgressSteps currentStep={currentStep} processingTime={processingTimeMs} />
                      </Card>
                      <ResultCard
                        bank={currentResult.bank || detectInfo.bank || '未知'}
                        docType={currentResult.docType || detectInfo.docType || '未知'}
                        isManual={false}
                        transactionCount={0}
                        error={currentResult.error || '解析失败'}
                        onRedetect={() => currentFilePath && handleSingleFileDetect(currentFilePath)}
                        onModifyConfig={openSingleOverride}
                        onReselectFile={handleSingleReselectFile}
                      />
                    </>
                  )}
                </>
              )}

              {/* 解析进行中 */}
              {loading && detectState === 'detected' && !currentResult && (
                <Card title="处理进度">
                  <ProgressSteps currentStep={currentStep} processingTime={processingTimeMs} />
                </Card>
              )}
            </div>
          )}

          {/* ====== 批量模式视图 ====== */}
          {mode === 'batch' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <BatchFileSelector
                files={batch.files}
                onAddFiles={handleBatchAddFiles}
                onRemoveFile={batch.removeFile}
                onClear={handleBatchClear}
                onDetect={handleBatchDetectOnly}
                onStartParse={handleBatchStartParse}
                onModifyConfig={handleBatchModifyConfig}
                isDetecting={batch.isDetecting}
                isParsing={batch.isParsing}
                detectDone={batch.detectDone}
                currentIndex={batch.currentIndex}
                totalCount={batch.totalCount}
              />

              {/* 批量解析进度 */}
              {batch.isParsing && batch.currentIndex > 0 && batch.totalCount > 0 && (
                <Card title={`正在解析 ${batch.currentIndex}/${batch.totalCount}`}>
                  <ProgressSteps currentStep={currentStep} processingTime={processingTimeMs} />
                </Card>
              )}

              {batchResult && (
                <BatchResultPanel
                  files={batchResult.files}
                  onRetry={handleBatchRetry}
                  onExportVoucher={handleBatchExportVoucher}
                />
              )}
            </div>
          )}
        </div>
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        Finance Assistant ©2026 — Built with Electron + React + Python
      </Footer>

      {/* 手动覆盖模态框（单文件 + 批量共用） */}
      {overrideContext && (
        <ManualOverrideModal
          open={overrideModalOpen}
          fileCount={overrideContext.fileCount}
          isPdfOnly={overrideContext.isPdfOnly}
          initialBank={overrideInitialBank}
          initialDocType={overrideInitialDocType}
          initialOcr={overrideInitialOcr}
          onConfirm={(bank, docType, forceOcr) => overrideContext.onConfirm(bank, docType, forceOcr)}
          onCancel={() => setOverrideModalOpen(false)}
        />
      )}

      {/* 导出凭证弹窗 */}
      <Modal
        title="导出凭证（金蝶精斗云格式）"
        open={voucherModalOpen}
        onCancel={() => setVoucherModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setVoucherModalOpen(false)}>取消</Button>,
          <Button key="export" type="primary" loading={voucherLoading} onClick={handleExportVoucher}>
            选择保存路径并导出
          </Button>,
        ]}
        width={420}
      >
        <Form layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="期间名称（用于 Sheet 名）"
            help="例如：2026年3月、2026年第3期"
          >
            <Input
              value={period}
              onChange={e => setPeriod(e.target.value)}
              placeholder="2026年3月"
            />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}

export default App;
