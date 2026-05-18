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
      selectFile: (filter?: string) => Promise<string | null>;
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
  onConfirm: (bank: string, docType: string, forceOcr: boolean) => void;
};

function App() {
  // ====== 模式 & 结果 ======
  const [mode, setMode] = useState<'single' | 'batch'>('single');
  const [currentResult, setCurrentResult] = useState<any>(null);
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);

  // ====== 加载 & 进度 ======
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [processingTimeMs, setProcessingTimeMs] = useState(0);

  // ====== 批量编排 ======
  const batch = useBatchOrchestrator({
    onComplete: (result) => {
      setBatchResult(result);
      if (result.failedCount > 0) {
        const failedPaths = result.files
          .filter((f) => f.status === 'failed')
          .map((f) => f.filePath);
        openBatchOverride(failedPaths);
      }
    },
  });

  // 单文件 fallback 用：记录最近一次通过文件选择打开的文件
  const [batchSingleFilePath] = useState<string | null>(null);

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

  // ====== 单文件：选择文件 → 检测 → 解析 ======
  const handleFileSelected = useCallback(async (filePath: string) => {
    if (!filePath) return;
    setCurrentResult(null);
    setLoading(true);
    setCurrentStep(0);
    const startTime = Date.now();

    try {
      const ext = filePath.toLowerCase().split('.').pop();
      const fileType = ext === 'csv' ? 'CSV' : 'PDF';
      message.info(`正在解析${fileType}文件...`);

      const result = await window.electronAPI.parsePDF(filePath);
      setCurrentStep(1);
      setProcessingTimeMs(Date.now() - startTime);

      if (result.success) {
        setCurrentResult(result);
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

  // ====== 单文件：手动覆盖后解析 ======
  const handleSingleFileParse = useCallback(async (filePath: string, bank: string, docType: string, forceOcr: boolean) => {
    setLoading(true);
    setCurrentStep(0);
    const startTime = Date.now();
    setOverrideModalOpen(false);

    try {
      message.info(`正在解析（${bank} · ${docType}）...`);
      const params: any = { filePath, bank };
      if (docType) params.docType = docType;
      if (forceOcr) params.forceOcr = true;

      const result = await window.electronAPI.parsePdf(params);
      setCurrentStep(1);
      setProcessingTimeMs(Date.now() - startTime);

      if (result.success) {
        setCurrentResult(result);
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

  // ====== 打开单文件 fallback 模态框 ======
  const openSingleOverride = useCallback(() => {
    setOverrideInitialBank(currentResult?.bank || '');
    setOverrideInitialDocType('');
    setOverrideInitialOcr(false);
    setOverrideContext({
      fileCount: 1,
      onConfirm: (bank: string, docType: string, forceOcr: boolean) => {
        // 单文件 fallback：需要文件路径，从 batchSingleFilePath 或重新选择
        // 这里复用当前结果中的信息，重新解析
        handleSingleFileParse(
          currentResult?._filePath || batchSingleFilePath || '',
          bank, docType, forceOcr,
        );
      },
    });
    setOverrideModalOpen(true);
  }, [currentResult, batchSingleFilePath, handleSingleFileParse]);

  // ====== 打开批量 fallback 模态框 ======
  const openBatchOverride = useCallback((filePaths: string[]) => {
    setOverrideInitialBank('');
    setOverrideInitialDocType('');
    setOverrideInitialOcr(false);
    setOverrideContext({
      fileCount: filePaths.length,
      onConfirm: (bank: string, docType: string, forceOcr: boolean) => {
        batch.retryFailedFiles(filePaths, bank, docType, forceOcr);
      },
    });
    setOverrideModalOpen(true);
  }, [batch]);

  // ====== 批量：解析失败文件 → 委托给 orchestrator ======

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

  // ====== 切换模式（互斥） ======
  const switchMode = useCallback((newMode: 'single' | 'batch') => {
    setMode(newMode);
    setOverrideModalOpen(false);
    if (newMode === 'single') {
      setBatchResult(null);
      batch.clearFiles();
    } else {
      setCurrentResult(null);
      setCurrentStep(0);
      setProcessingTimeMs(0);
      setVoucherModalOpen(false);
      batch.clearFiles();
    }
  }, [batch]);

  // ====== 单文件模式有解析结果时的导出按钮 ======
  const singleFileHasResult = currentResult?.success && currentResult?.transactions?.length > 0;

  // ====== 匹配数 ======
  const matchedCount = currentResult?.transactions?.length || 0;

  // ====== 单文件结果卡片 handlers ======
  const handleSingleRedetect = useCallback(async () => {
    const filePath = await window.electronAPI.selectFile('all');
    if (filePath) await handleFileSelected(filePath);
  }, [handleFileSelected]);

  const handleSingleModifyConfig = useCallback(() => {
    openSingleOverride();
  }, [openSingleOverride]);

  const handleSingleReselectFile = useCallback(() => {
    setCurrentResult(null);
    setCurrentStep(0);
    setProcessingTimeMs(0);
  }, []);

  // ====== 批量：addFiles / detectAndParse / clear ======
  const handleBatchAddFiles = useCallback((filePaths: string[]) => {
    batch.addFiles(filePaths);
  }, [batch]);

  const handleBatchDetectAndParse = useCallback(() => {
    batch.detectAndParse();
  }, [batch]);

  const handleBatchClear = useCallback(() => {
    batch.clearFiles();
    setBatchResult(null);
  }, [batch]);

  // ====== 批量：重试单个失败文件 → 直接打开 fallback ======
  const handleBatchRetry = useCallback((filePaths: string[]) => {
    openBatchOverride(filePaths);
  }, [openBatchOverride]);

  // ====== 批量：查看详情 ======
  const handleBatchViewDetail = useCallback((filePath: string) => {
    const file = batchResult?.files.find((f) => f.filePath === filePath);
    if (!file || file.status !== 'success') return;

    // 切换到单文件模式，展示该文件详情
    setCurrentResult({
      success: true,
      transactions: file.transactions || [],
      bank: file.bank,
      statementDate: file.statementDate,
      confidence: 1,
      errors: [],
      warnings: [],
      _filePath: filePath,
    });
    switchMode('single');
  }, [batchResult, switchMode]);

  // ====== 批量：导出 Excel（合并所有成功文件） ======
  const handleBatchExportExcel = useCallback(async () => {
    if (!batchResult) return;
    const allTxns = batchResult.files.flatMap((f) =>
      f.status === 'success' ? (f.transactions || []) : []
    );
    if (!allTxns.length) {
      message.warning('没有可导出的交易数据');
      return;
    }

    setCurrentStep(1);
    setLoading(true);
    try {
      const outputPath = `batch_statement_${Date.now()}.xlsx`;
      const result = await window.electronAPI.generateExcel({
        transactions: allTxns,
        output_path: outputPath,
      });
      setCurrentStep(2);
      if (result.success) {
        message.success(`批量 Excel 已导出: ${result.excel_path}`);
      } else {
        message.error(`导出失败：${result.error}`);
      }
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : String(error);
      message.error(`导出出错：${msg}`);
    } finally {
      setLoading(false);
    }
  }, [batchResult]);

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

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 24px' }}>
        <Title level={3} style={{ color: '#fff', margin: '16px 0' }}>
          Finance Assistant
        </Title>
      </Header>
      <Content style={{ padding: '20px 24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

          {/* ====== 第一行：系统设置 + 模式入口 ====== */}
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

            {/* 模式入口 */}
            <div style={{ flex: 1, display: 'flex', gap: 16, minWidth: 400 }}>
              {/* 单文件入口 */}
              <Card
                hoverable
                onClick={() => switchMode('single')}
                style={{
                  flex: 1,
                  borderColor: mode === 'single' ? '#1677ff' : undefined,
                  borderWidth: mode === 'single' ? 2 : 1,
                  cursor: 'pointer',
                }}
              >
                <div style={{ textAlign: 'center', padding: '20px 0' }}>
                  <Title level={4} style={{ marginBottom: 8 }}>单文件解析</Title>
                  <Text type="secondary">选择单个文件进行解析</Text>
                </div>
              </Card>

              {/* 批量入口 */}
              <Card
                hoverable
                onClick={() => switchMode('batch')}
                style={{
                  flex: 1,
                  borderColor: mode === 'batch' ? '#1677ff' : undefined,
                  borderWidth: mode === 'batch' ? 2 : 1,
                  cursor: 'pointer',
                }}
              >
                <div style={{ textAlign: 'center', padding: '20px 0' }}>
                  <Title level={4} style={{ marginBottom: 8 }}>批量解析</Title>
                  <Text type="secondary">一次解析多个同类型文件</Text>
                </div>
              </Card>
            </div>
          </div>

          {/* ====== 单文件模式视图 ====== */}
          {mode === 'single' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* 文件上传 */}
              <FileDropZone onFileSelected={handleFileSelected} />

              {/* 结果卡片 */}
              {currentResult && !loading && (
                <ResultCard
                  bank={currentResult.bank || '未知'}
                  docType={currentResult.docType || currentResult._docType || '未知'}
                  isManual={!!(currentResult as any)._isManual}
                  transactionCount={matchedCount}
                  statementDate={currentResult.statementDate}
                  error={currentResult.success ? undefined : currentResult.error}
                  onRedetect={handleSingleRedetect}
                  onModifyConfig={handleSingleModifyConfig}
                  onReselectFile={handleSingleReselectFile}
                />
              )}

              {/* 导出操作区 */}
              {singleFileHasResult && (
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
              )}

              {/* 进度条 */}
              {(loading || currentStep > 0) && (
                <Card title="处理进度">
                  <ProgressSteps currentStep={currentStep} processingTime={processingTimeMs} />
                </Card>
              )}

              {/* 交易表格 */}
              {currentResult?.transactions && (
                <Card title="交易列表">
                  <TransactionTable
                    transactions={currentResult.transactions}
                    loading={loading}
                  />
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
                onDetectAndParse={handleBatchDetectAndParse}
                isParsing={batch.isParsing}
              />

              {batchResult && (
                <BatchResultPanel
                  files={batchResult.files}
                  onRetry={handleBatchRetry}
                  onViewDetail={handleBatchViewDetail}
                  onExportExcel={handleBatchExportExcel}
                  onExportVoucher={handleBatchExportVoucher}
                />
              )}

              {/* 批量解析进度 */}
              {batch.isParsing && batch.currentIndex > 0 && batch.result && (
                <Card title={`正在解析 ${batch.currentIndex}/${batch.result.totalFiles}`}>
                  <ProgressSteps currentStep={currentStep} processingTime={processingTimeMs} />
                </Card>
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
