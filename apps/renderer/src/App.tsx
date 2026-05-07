import { Layout, Typography, Button, Card, message, Space, Tag } from 'antd';
import { useState, useEffect } from 'react';
import { FileDropZone } from './components/FileDropZone';
import { TransactionTable } from './components/TransactionTable';
import { ProgressSteps } from './components/ProgressSteps';
import type { Transaction, ReconcileResult } from '@shared/types';

const { Header, Content, Footer } = Layout;
const { Title, Text } = Typography;

// 声明 window.electronAPI 类型
declare global {
  interface Window {
    electronAPI: {
      health: () => Promise<any>;
      reconcile: (params: any) => Promise<any>;
      parsePDF: (path: string) => Promise<any>;
      parsePdf: (params: any) => Promise<any>;
      chat: (msg: string, sessionKey?: string) => Promise<any>;
      onPythonStatus: (callback: (status: string) => void) => void;
      getPythonStatus: () => Promise<string>;
    };
  }
}

function App() {
  const [backendStatus, setBackendStatus] = useState<string>('检查中...');
  const [loading, setLoading] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [parseResult, setParseResult] = useState<any>(null);

  // 对账相关状态
  const [reconcileResult, setReconcileResult] = useState<ReconcileResult | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [currentStep, setCurrentStep] = useState(0);
  const [processingTimeMs, setProcessingTimeMs] = useState(0);

  // 监听 Python 进程状态变化 + 初始查询
  useEffect(() => {
    // 主动查询当前状态
    window.electronAPI.getPythonStatus?.().then((status: string) => {
      if (status === 'online') {
        setBackendStatus('正常');
      } else {
        setBackendStatus('离线');
      }
    }).catch(() => setBackendStatus('离线'));

    // 监听状态变化
    window.electronAPI.onPythonStatus?.((status: string) => {
      if (status === 'offline') {
        setBackendStatus('离线');
        setTestResult(null);
      } else if (status === 'online') {
        setBackendStatus('正常（已恢复）');
      } else if (status === 'error') {
        setBackendStatus('错误');
      }
    });
  }, []);

  const testConnection = async () => {
    setLoading(true);
    try {
      const result = await window.electronAPI.health();
      setBackendStatus(`正常 (v${result.version})`);
      setTestResult(result);
      message.success('后端连接成功！');
    } catch (error: any) {
      setBackendStatus(`离线: ${error.message}`);
      message.error('后端连接失败');
      setTestResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleFilesSelected = async (files: File[]) => {
    if (files.length === 0) return;

    const file = files[0];
    try {
      message.info(`已选择文件：${file.name}，准备解析...`);
      setParseResult({
        success: true,
        transactions: [],
        bank: '未知银行',
        message: 'PDF 解析功能已就绪，等待后端实现',
      });
    } catch (error: any) {
      message.error(`解析失败：${error.message}`);
    }
  };

  const matchedCount = parseResult?.transactions?.length || 0;

  // 对账流程
  const handleReconcile = async () => {
    if (selectedFiles.length < 2) {
      message.warning('请选择 PDF 和 Excel 文件');
      return;
    }

    const pdfFile = selectedFiles.find(f => f.name.endsWith('.pdf'));
    const ledgerFile = selectedFiles.find(f => f.name.endsWith('.xlsx') || f.name.endsWith('.xls'));

    if (!pdfFile || !ledgerFile) {
      message.error('请选择 PDF 和 Excel 文件各一个');
      return;
    }

    setLoading(true);
    setCurrentStep(0);
    const startTime = Date.now();

    try {
      setCurrentStep(1);
      message.info('正在解析 PDF...');

      // 调用对账接口（后端会完成解析→匹配→导出全流程）
      const result = await window.electronAPI.reconcile({
        pdf_path: pdfFile.name,
        ledger_path: ledgerFile.name,
      });

      setCurrentStep(4);
      setProcessingTimeMs(Date.now() - startTime);

      if (result.success) {
        setReconcileResult(result);
        message.success('对账完成！');
      } else {
        message.error(`对账失败：${result.error}`);
      }
    } catch (error: any) {
      message.error(`对账出错：${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // 示例数据（用于演示表格）
  const sampleTransactions: Transaction[] = [
    {
      date: '2025-03-15',
      description: '工资收入',
      amount: 15000.00,
      currency: 'CNY',
      direction: 'income',
      counterparty: 'XX公司',
      reference_number: 'TXN001',
    },
    {
      date: '2025-03-16',
      description: '房租支出',
      amount: -5000.00,
      currency: 'CNY',
      direction: 'expense',
      counterparty: '房东张三',
      reference_number: 'TXN002',
    },
    {
      date: '2025-03-17',
      description: '银行转账',
      amount: 2000.00,
      currency: 'CNY',
      direction: 'transfer',
      counterparty: '李四',
      reference_number: 'TXN003',
    },
  ];

  // 根据对账结果计算高亮类型
  const getHighlightType = (): 'matched' | 'unreconciled' | 'suspicious' | undefined => {
    if (!reconcileResult) return undefined;
    // 简单逻辑：有匹配数就显示 matched
    if (reconcileResult.matched_count > 0) return 'matched';
    if (reconcileResult.unreconciled_bank > 0 || reconcileResult.unreconciled_ledger > 0) return 'unreconciled';
    return 'suspicious';
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 24px' }}>
        <Title level={3} style={{ color: '#fff', margin: '16px 0' }}>
          Finance Assistant
        </Title>
      </Header>
      <Content style={{ padding: '24px' }}>
        <div style={{ display: 'grid', gap: '24px' }}>
          {/* 连接测试卡片 */}
          <Card title="连接测试" style={{ width: 400 }}>
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary">后端状态：</Text>
              <Text strong>{backendStatus}</Text>
            </div>
            <Button type="primary" loading={loading} onClick={testConnection}>
              测试连接
            </Button>
            {testResult && (
              <div style={{ marginTop: 16, padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  返回数据：{JSON.stringify(testResult, null, 2)}
                </Text>
              </div>
            )}
          </Card>

          {/* 文件上传区域 */}
          <FileDropZone onFilesSelected={handleFilesSelected} />

          {/* 已选文件列表和对账按钮 */}
          {selectedFiles.length > 0 && (
            <Card title="已选文件" style={{ marginTop: 16 }}>
              <Space wrap>
                {selectedFiles.map((f, i) => (
                  <Tag key={i} color="blue" closable onClose={() => {
                    const newFiles = selectedFiles.filter((_, idx) => idx !== i);
                    setSelectedFiles(newFiles);
                  }}>
                    {f.name}
                  </Tag>
                ))}
              </Space>
              <div style={{ marginTop: 16 }}>
                <Button
                  type="primary"
                  loading={loading}
                  onClick={handleReconcile}
                  disabled={selectedFiles.length < 2}
                >
                  开始对账
                </Button>
              </div>
            </Card>
          )}

          {/* 进度条 */}
          {(loading || currentStep > 0) && (
            <Card title="对账进度" style={{ marginTop: 16 }}>
              <ProgressSteps currentStep={currentStep} processingTime={processingTimeMs} />
            </Card>
          )}

          {/* 解析结果 */}
          {parseResult && (
            <Card title="解析结果" style={{ marginTop: 16 }}>
              <p>银行：{parseResult.bank}</p>
              <p>解析交易数：{matchedCount}</p>
            </Card>
          )}

          {/* 对账结果统计 */}
          {reconcileResult && (
            <Card title="对账结果" style={{ marginTop: 16 }}>
              <Space wrap>
                <Text>已匹配：<Text strong style={{ color: '#52c41a' }}>{reconcileResult.matched_count}</Text></Text>
                <Text>银行未达：<Text strong style={{ color: '#faad14' }}>{reconcileResult.unreconciled_bank}</Text></Text>
                <Text>账本未达：<Text strong style={{ color: '#f5222d' }}>{reconcileResult.unreconciled_ledger}</Text></Text>
                <Text>总耗时：<Text strong>{(processingTimeMs / 1000).toFixed(2)} 秒</Text></Text>
              </Space>
              {reconcileResult.excel_path && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">Excel 输出：{reconcileResult.excel_path}</Text>
                </div>
              )}
            </Card>
          )}

          {/* 交易表格 */}
          <Card title="交易列表" style={{ marginTop: 16 }}>
            <TransactionTable
              transactions={reconcileResult ? sampleTransactions : []}
              loading={loading}
              highlight={getHighlightType()}
            />
          </Card>
        </div>
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        Finance Assistant ©2026 — Built with Electron + React + Python
      </Footer>
    </Layout>
  );
}

export default App;
