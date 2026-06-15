import { Layout, Typography, Button, Card, message, Space, Modal } from 'antd';
import { useState, useEffect, useCallback } from 'react';
import { SettingOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { FileDropZone } from './components/FileDropZone';
import { ManualOverrideModal } from './components/ManualOverrideModal';
import { TransactionEditModal } from './components/TransactionEditModal';
import { SingleFileResultPanel } from './components/SingleFileResultPanel';
import { BatchFileSelector } from './components/BatchFileSelector';
import { BatchResultPanel } from './components/BatchResultPanel';
import { AccountSubjectManager } from './components/AccountSubjectManager';
import { VoucherPreviewPanel } from './components/VoucherPreviewPanel';
import { useBatchOrchestrator } from './hooks/useBatchOrchestrator';
import { useVoucherFlow } from './hooks/useVoucherFlow';
import { useTransactionEdit } from './hooks/useTransactionEdit';
import { useOverrideModal } from './hooks/useOverrideModal';
import { useSingleFile } from './hooks/useSingleFile';
import type { BatchResult, Transaction, ParseFileParams, ParseFileResult, DetectBanksResult, DetectSupportedBanksResult } from '@shared/types';

const { Header, Content } = Layout;
const { Title, Text } = Typography;

// 声明 window.electronAPI 类型
declare global {
  interface Window {
    electronAPI: {
      parseFile: (params: ParseFileParams) => Promise<ParseFileResult>;
      generateExcel: (params: any) => Promise<any>;
      importSubjects: (params: any) => Promise<any>;
      getSubjectsInfo: () => Promise<any>;
      selectFile: (filter?: string, allowMulti?: boolean) => Promise<string[] | string | null>;
      saveFileDialog: (params?: any) => Promise<string | null>;
      detectBanks: (filePaths: string[]) => Promise<DetectBanksResult>;
      detectSupportedBanks: () => Promise<DetectSupportedBanksResult>;
      invoke: (method: string, params?: any) => Promise<any>;
      getFilePath: (file: File) => string;
      onPythonStatus: (callback: (status: string) => void) => void;
      getPythonStatus: () => Promise<string>;
    };
  }
}

function App() {
  // ====== 模式 & 结果 ======
  const [mode, setMode] = useState<'single' | 'batch'>('single');
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);

  // ====== 单文件 ======
  const single = useSingleFile();

  // ====== 批量编排 ======
  const batch = useBatchOrchestrator({
    onComplete: (result) => {
      setBatchResult(result);
    },
  });

  // ====== 凭证预览 + 草稿 (#35) ======
  const voucherFlow = useVoucherFlow();

  // ====== 科目管理 ======
  const [importSubjectsLoading, setImportSubjectsLoading] = useState(false);
  const [subjectsCount, setSubjectsCount] = useState<number | null>(null);
  const [backendStatus, setBackendStatus] = useState<string>('检查中...');

  // ====== 账号-科目管理 ======
  const [accountManagerVisible, setAccountManagerVisible] = useState(false);

  // ====== 交易编辑弹窗 ======
  const txnEdit = useTransactionEdit();

  // ====== 手动覆盖模态框 ======
  const overrideModal = useOverrideModal();

  // ====== 启动时查询 ======
  useEffect(() => {
    if (!window.electronAPI) return;

    const checkSubjects = async () => {
      try {
        const result = await window.electronAPI.getSubjectsInfo();
        if (result.success) setSubjectsCount(result.count);
      } catch { /* ignore */ }
    };
    checkSubjects();

    window.electronAPI.getPythonStatus?.().then((status: string) => {
      setBackendStatus(status === 'online' ? '正常' : '离线');
    }).catch((err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      setBackendStatus(msg.includes('not started') ? '未启动' : '离线');
    });

    window.electronAPI.onPythonStatus?.((status: string) => {
      if (status === 'offline') { setBackendStatus('离线'); }
      else if (status === 'online') setBackendStatus('正常（已恢复）');
      else if (status === 'error') setBackendStatus('错误');
    });
  }, []);

  // ====== 统一入口：选择文件 → 根据数量决定模式 ======
  const handleFilesSelected = useCallback((filePaths: string[]) => {
    if (!filePaths || filePaths.length === 0) return;

    if (filePaths.length === 1) {
      // 单文件模式
      setMode('single');
      setBatchResult(null);
      single.detect(filePaths[0]);
    } else {
      // 批量模式
      setMode('batch');
      batch.clearFiles();
      batch.addFiles(filePaths);
    }
  }, [batch.clearFiles, batch.addFiles]);

  // ====== 打开单文件 fallback 模态框 ======
  const openSingleOverride = useCallback(() => {
    const ext = single.filePath?.toLowerCase().split('.').pop();
    const isPdfOnly = ext === 'pdf';
    overrideModal.show({
      context: {
        fileCount: 1,
        isPdfOnly,
        onConfirm: (bank: string, docType: string, _forceOcr: boolean) => {
          single.applyOverride(bank, docType);
          overrideModal.close();
        },
      },
      initialBank: single.detectInfo.bank || '',
      initialDocType: single.detectInfo.docType || '',
      initialOcr: false,
    });
  }, [single.filePath, single.detectInfo, single.applyOverride, overrideModal]);

  // ====== 打开批量 fallback 模态框 ======
  const openBatchOverride = useCallback((filePaths: string[]) => {
    const allPdf = filePaths.every(fp => fp.toLowerCase().endsWith('.pdf'));
    overrideModal.show({
      context: {
        fileCount: filePaths.length,
        isPdfOnly: allPdf,
        onConfirm: (bank: string, docType: string, _forceOcr: boolean) => {
          overrideModal.close();
          // 只更新检测值，不触发解析
          for (const fp of filePaths) {
            batch.updateFile(fp, { bank, docType: docType as any, error: undefined, isManual: true });
          }
        },
      },
      initialOcr: false,
    });
  }, [batch.updateFile, overrideModal]);

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
    overrideModal.show({
      context: {
        fileCount: 1,
        isPdfOnly,
        onConfirm: (bank: string, docType: string, _forceOcr: boolean) => {
          overrideModal.close();
          // 只更新检测值，不触发解析
          batch.updateFile(filePath, { bank, docType: docType as any, error: undefined, isManual: true });
        },
      },
      initialBank: file.bank || '',
      initialDocType: file.docType || '',
      initialOcr: false,
    });
  }, [batch.files, batch.updateFile, overrideModal]);

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

  // ====== 交易编辑保存 ======
  const handleSaveEdit = useCallback((updated: Transaction) => {
    if (txnEdit.filePath && batchResult) {
      // 批量模式：更新对应文件的交易
      setBatchResult({
        ...batchResult,
        files: batchResult.files.map((f) =>
          f.filePath === txnEdit.filePath && f.transactions
            ? {
                ...f,
                transactions: f.transactions.map((t) =>
                  t === txnEdit.txn ? updated : t
                ),
              }
            : f
        ),
      });
    } else {
      // 单文件模式
      single.setResult(
        single.result
          ? {
              ...single.result,
              transactions: single.result.transactions.map((t: Transaction) =>
                t === txnEdit.txn ? updated : t
              ),
            }
          : single.result
      );
    }
    txnEdit.close();
    message.success('交易已更新');
  }, [txnEdit, batchResult]);

  // ====== 批量：导出凭证（合并所有成功文件） ======
  const getTransactionsForExport = useCallback((): Transaction[] => {
    if (mode === 'single') {
      return single.result?.transactions || [];
    }
    if (!batchResult) {
      return [];
    }
    return batchResult.files.flatMap((f) =>
      f.status === 'success' ? (f.transactions || []) : []
    );
  }, [mode, single.result, batchResult]);

  // ====== 辅助 ======
  const detectUnknown = single.detectState === 'unknown';

  // ====== 凭证生成子页面 ======
  if (voucherFlow.showPage) {
    return (
      <Layout style={{ minHeight: '100vh' }}>
        <Header style={{ background: '#001529', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={voucherFlow.closePage}
            style={{ color: '#fff', fontSize: 16 }}
          >
            返回
          </Button>
          <Title level={4} style={{ color: '#fff', margin: 0 }}>凭证生成</Title>
        </Header>
        <Content style={{ padding: '20px 24px' }}>
          <VoucherPreviewPanel
            vouchers={voucherFlow.vouchers}
            subjects={voucherFlow.subjects}
            onVouchersChange={voucherFlow.onVouchersChange}
            onSaveDraft={voucherFlow.handleSaveDraft}
            onExport={voucherFlow.handleExport}
            onCancel={voucherFlow.closePage}
            saveDisabled={voucherFlow.saving}
            loading={voucherFlow.previewLoading}
          />
        </Content>
      </Layout>
    );
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 24px' }}>
        <Title level={3} style={{ color: '#fff', margin: '16px 0' }}>
          财务助手
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
                <Button loading={importSubjectsLoading} onClick={handleImportSubjects}>
                  导入科目表
                </Button>
                <Button icon={<SettingOutlined />} onClick={() => setAccountManagerVisible(true)}>
                  账号管理
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
            <SingleFileResultPanel
              detectState={single.detectState}
              loading={single.loading}
              currentFilePath={single.filePath}
              currentResult={single.result}
              detectInfo={single.detectInfo}
              detectUnknown={detectUnknown}
              onRedetect={() => single.filePath && single.detect(single.filePath)}
              onModifyConfig={openSingleOverride}
              onStartParse={() => single.parse()}
              onPreviewVoucher={(txns) => voucherFlow.preview(txns)}
              onEditTransaction={txnEdit.openSingle}
            />
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

              {batchResult && (
                <BatchResultPanel
                  files={batchResult.files}
                  onRetry={handleBatchRetry}
                  onEditTransaction={txnEdit.openBatch}
                  onPreviewVoucher={() => {
                    const txns = getTransactionsForExport();
                    if (txns.length === 0) { message.warning('没有成功的交易数据'); return; }
                    voucherFlow.preview(txns);
                  }}
                />
              )}
            </div>
          )}

        </div>
      </Content>

      {/* 交易编辑弹窗 */}
      <TransactionEditModal
        open={txnEdit.open}
        transaction={txnEdit.txn}
        onSave={handleSaveEdit}
        onCancel={txnEdit.close}
      />

      {/* 手动覆盖模态框（单文件 + 批量共用） */}
      {overrideModal.context && (
        <ManualOverrideModal
          open={overrideModal.open}
          fileCount={overrideModal.context.fileCount}
          isPdfOnly={overrideModal.context.isPdfOnly}
          initialBank={overrideModal.initialBank}
          initialDocType={overrideModal.initialDocType}
          initialOcr={overrideModal.initialOcr}
          onConfirm={(bank, docType, forceOcr) => overrideModal.context!.onConfirm(bank, docType, forceOcr)}
          onCancel={overrideModal.close}
        />
      )}

      {/* 账号-科目管理模态框 */}
      <Modal
        title="账号-科目管理"
        open={accountManagerVisible}
        onCancel={() => setAccountManagerVisible(false)}
        footer={null}
        width={1000}
        destroyOnHidden
      >
        <AccountSubjectManager
          onRefresh={() => {
            // 刷新时更新科目数量显示
            window.electronAPI?.getSubjectsInfo?.().then((result: any) => {
              if (result?.success) setSubjectsCount(result.count);
            });
          }}
        />
      </Modal>
    </Layout>
  );
}

export default App;
