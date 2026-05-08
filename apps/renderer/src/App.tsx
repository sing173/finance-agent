import { Layout, Typography, Button, Card, message, Space } from 'antd';
import { useState, useEffect } from 'react';
import { FileDropZone } from './components/FileDropZone';
import { TransactionTable } from './components/TransactionTable';
import { ProgressSteps } from './components/ProgressSteps';
import type { ReconcileResult } from '@shared/types';

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
      selectFile: (filter?: string) => Promise<string | null>;
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

  const handleFileSelected = async (filePath: string) => {
    if (!filePath) return;

    // 检查是否为 PDF 文件
    if (!filePath.toLowerCase().endsWith('.pdf')) {
      message.warning('请选择 PDF 文件');
      return;
    }

    setLoading(true);
    setCurrentStep(0);
    const startTime = Date.now();

    try {
      setCurrentStep(1);
      message.info('正在解析 PDF...');

      const result = await window.electronAPI.parsePDF(filePath);

      setCurrentStep(2);
      setProcessingTimeMs(Date.now() - startTime);

      if (result.success) {
        setParseResult(result);
        message.success(`解析成功，共 ${result.transactions?.length || 0} 笔交易`);
      } else {
        message.error(`解析失败：${result.error}`);
      }
    } catch (error: any) {
      message.error(`解析出错：${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const matchedCount = parseResult?.transactions?.length || 0;

  // 对账流程
  const handleReconcile = async () => {
    // 需要先有解析结果（PDF）和台账文件
    if (!parseResult?.success) {
      message.warning('请先解析 PDF 文件');
      return;
    }

    setLoading(true);
    setCurrentStep(2);
    const startTime = Date.now();

    try {
      message.info('正在进行对账...');

      // 调用对账接口
      const result = await window.electronAPI.reconcile({
        pdf_path: parseResult.pdf_path || 'workflow_test_statement.pdf',
        ledger_path: parseResult.ledger_path || 'workflow_test_ledger.json',
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

  // 根据对账结果计算高亮类型
  const getHighlightType = (): 'matched' | 'unreconciled' | 'suspicious' | undefined => {
    if (!reconcileResult) return undefined;
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
          <FileDropZone onFileSelected={handleFileSelected} />

          {/* 对账按钮（解析成功后显示） */}
          {parseResult?.success && !reconcileResult && (
            <Card title="下一步操作" style={{ marginTop: 16 }}>
              <Space>
                <Button
                  type="primary"
                  loading={loading}
                  onClick={handleReconcile}
                >
                  开始对账
                </Button>
                <Button onClick={() => { setParseResult(null); }}>
                  重新选择文件
                </Button>
              </Space>
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
              transactions={parseResult?.transactions || []}
              loading={loading}
              highlight={reconcileResult ? getHighlightType() : undefined}
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
