import { ConfigProvider, Layout, Typography, Button, Card, message, Space, Modal } from 'antd';
import { useState, useEffect, useCallback } from 'react';
import { SettingOutlined } from '@ant-design/icons';
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

const { Content } = Layout;
const { Text } = Typography;

/* ── Ledger 风格主题 ── */
const ledgerTheme = {
  token: {
    // 主色
    colorPrimary: '#1e3a5f',
    colorPrimaryHover: '#2a4a73',
    colorPrimaryActive: '#142a4a',
    colorPrimaryTextHover: '#2a4a73',
    // 语义色（文字/边框用深色，背景另设浅色）
    colorError: '#991b1b',
    colorWarning: '#d97706',
    colorSuccess: '#065f46',
    colorInfo: '#1e3a5f',
    // 语义背景色（浅色，保证黑字可读）
    colorErrorBg: '#fef2f2',
    colorErrorBorder: '#fecaca',
    colorWarningBg: '#fffbeb',
    colorWarningBorder: '#fde68a',
    colorSuccessBg: '#ecfdf5',
    colorSuccessBorder: '#a7f3d0',
    colorInfoBg: '#e8eef5',
    colorInfoBorder: '#bfdbfe',
    // 边框
    borderRadius: 2,
    borderRadiusLG: 2,
    borderRadiusSM: 0,
    colorBorder: '#d6d3cd',
    colorBorderSecondary: '#e7e5e4',
    // 背景
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBgLayout: '#faf9f7',
    colorBgSpotlight: '#1c1917',
    // 文字
    colorText: '#1c1917',
    colorTextSecondary: '#44403c',
    colorTextDescription: '#78716c',
    colorTextHeading: '#1c1917',
    // 字体
    fontFamily:
      'system-ui, -apple-system, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif',
    fontSize: 14,
    // 控件尺寸（紧凑）
    controlHeight: 32,
    controlHeightLG: 40,
    controlHeightSM: 24,
    // 阴影
    boxShadow: 'none',
    boxShadowSecondary: 'none',
  },
  components: {
    Table: {
      headerBg: '#faf9f7',
      headerColor: '#1c1917',
      headerSplitColor: '#d6d3cd',
      rowHoverBg: 'rgba(0,0,0,0.025)',
      borderColor: '#d6d3cd',
      cellPaddingBlock: 8,
      cellPaddingInline: 12,
      fontSize: 13,
    },
    Card: {
      headerBg: '#ffffff',
      actionsBg: '#faf9f7',
      borderRadiusLG: 2,
      borderRadius: 2,
      headerFontSize: 14,
      headerHeight: 40,
    },
    Button: {
      borderRadius: 2,
      primaryShadow: 'none',
      defaultShadow: 'none',
      dangerShadow: 'none',
    },
    Modal: {
      borderRadiusLG: 2,
      borderRadius: 2,
    },
    Tag: {
      borderRadiusSM: 0,
      borderRadius: 0,
    },
    Alert: {
      borderRadiusLG: 2,
      borderRadius: 2,
    },
    Layout: {
      headerBg: '#faf9f7',
      headerColor: '#1c1917',
      headerHeight: 48,
      bodyBg: '#faf9f7',
      siderBg: '#ffffff',
    },
    Menu: {
      borderRadius: 0,
    },
    Dropdown: {
      borderRadiusLG: 2,
    },
    Tooltip: {
      borderRadius: 2,
    },
    Popover: {
      borderRadiusLG: 2,
    },
    Select: {
      borderRadius: 2,
    },
    Input: {
      borderRadius: 2,
    },
    InputNumber: {
      borderRadius: 2,
    },
    DatePicker: {
      borderRadius: 2,
    },
    Form: {
      itemMarginBottom: 16,
    },
    List: {
      borderRadiusLG: 2,
    },
    Collapse: {
      borderRadiusLG: 2,
    },
    Descriptions: {
      borderRadius: 2,
    },
    Empty: {
      borderRadius: 2,
    },
  },
};

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
  const [showBatchSelector, setShowBatchSelector] = useState(true);

  // ====== 单文件 ======
  const single = useSingleFile();

  // ====== 批量编排 ======
  const batch = useBatchOrchestrator({
    onComplete: (result) => {
      setBatchResult(result);
      setShowBatchSelector(false);
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
      setBatchResult(null);
      setShowBatchSelector(true);
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
          for (const fp of filePaths) {
            batch.updateFile(fp, { bank, docType: docType as any, error: undefined, isManual: true });
          }
          setBatchResult(null);
          setShowBatchSelector(true);
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
    setBatchResult(null);
    setShowBatchSelector(false);
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
    setBatchResult(null);
    setShowBatchSelector(true);
    batch.addFiles(filePaths);
  }, [batch.addFiles]);

  const handleBatchDetectOnly = useCallback(() => {
    batch.detectOnly();
  }, [batch.detectOnly]);

  // ====== 批量：重试单个失败文件 ======
  const handleBatchRetry = useCallback((filePaths: string[]) => {
    openBatchOverride(filePaths);
  }, [openBatchOverride]);

  // ====== 交易编辑保存 ======
  const handleSaveEdit = useCallback((updated: Transaction) => {
    if (txnEdit.filePath && batchResult) {
      // 批量模式：更新对应文件的交易
      setBatchResult((prev) =>
        prev
          ? {
              ...prev,
              files: prev.files.map((f) =>
                f.filePath === txnEdit.filePath && f.transactions
                  ? {
                      ...f,
                      transactions: f.transactions.map((t) =>
                        t === txnEdit.txn ? updated : t
                      ),
                    }
                  : f
              ),
            }
          : prev
      );
    } else {
      // 单文件模式
      single.setResult((prev) =>
        prev
          ? {
              ...prev,
              transactions: prev.transactions.map((t: Transaction) =>
                t === txnEdit.txn ? updated : t
              ),
            }
          : prev
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

  // ====== 页面内容 ======
  const pageContent = voucherFlow.showPage ? (
    <Layout style={{ minHeight: '100vh' }}>
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
  ) : (
    <Layout style={{ minHeight: '100vh' }}>
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
              {/* 识别列表：解析完成后自动隐藏，点击重新识别后恢复 */}
              {showBatchSelector && (
                <BatchFileSelector
                  files={batch.files}
                  onAddFiles={handleBatchAddFiles}
                  onRemoveFile={batch.removeFile}
                  onDetect={handleBatchDetectOnly}
                  onStartParse={handleBatchStartParse}
                  onModifyConfig={handleBatchModifyConfig}
                  isDetecting={batch.isDetecting}
                  detectDone={batch.detectDone}
                  currentIndex={batch.currentIndex}
                />
              )}

              {/* 解析过程中 + 解析完成后显示结果卡片 */}
              {(batch.isParsing || batchResult) && !showBatchSelector && (
                <BatchResultPanel
                  files={batch.files}
                  isParsing={batch.isParsing}
                  currentIndex={batch.currentIndex}
                  onRetry={handleBatchRetry}
                  onRetryDetect={() => {
                    setShowBatchSelector(true);
                    setBatchResult(null);
                  }}
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

  return (
    <ConfigProvider theme={ledgerTheme}>
      {pageContent}
    </ConfigProvider>
  );
}

export default App;
