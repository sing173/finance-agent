import { Layout, Typography, Button, Card, message, Space, Modal, Form, Input } from 'antd';
import { useState, useEffect } from 'react';
import { FileDropZone } from './components/FileDropZone';
import { TransactionTable } from './components/TransactionTable';
import { ProgressSteps } from './components/ProgressSteps';

const { Header, Content, Footer } = Layout;
const { Title, Text } = Typography;

const LS_KEY = 'finance-assistant-subjects-path';

// 声明 window.electronAPI 类型
declare global {
  interface Window {
    electronAPI: {
      health: () => Promise<any>;
      parsePDF: (path: string) => Promise<any>;
      parsePdf: (params: any) => Promise<any>;
      generateExcel: (params: any) => Promise<any>;
      generateVoucher: (params: any) => Promise<any>;
      chat: (msg: string, sessionKey?: string) => Promise<any>;
      selectFile: (filter?: string) => Promise<string | null>;
      saveFileDialog: (params?: any) => Promise<string | null>;
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
  const [currentStep, setCurrentStep] = useState(0);
  const [processingTimeMs, setProcessingTimeMs] = useState(0);

  // 导出凭证弹窗相关状态
  const [voucherModalOpen, setVoucherModalOpen] = useState(false);
  const [voucherLoading, setVoucherLoading] = useState(false);
  const [subjectsPath, setSubjectsPath] = useState('');
  const [period, setPeriod] = useState('');

  // 启动时从 localStorage 恢复上次的科目文件路径
  useEffect(() => {
    const saved = localStorage.getItem(LS_KEY);
    if (saved) {
      setSubjectsPath(saved);
    }
  }, []);

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

    setParseResult(null);
    setLoading(true);
    setCurrentStep(0);
    const startTime = Date.now();

    try {
      message.info('正在解析 PDF...');

      const result = await window.electronAPI.parsePDF(filePath);

      setCurrentStep(1);
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

  const handleExportExcel = async () => {
    if (!parseResult?.transactions?.length) {
      message.warning('没有可导出的交易数据');
      return;
    }

    setCurrentStep(1);
    setLoading(true);
    try {
      const outputPath = `bank_statement_${Date.now()}.xlsx`;
      const result = await window.electronAPI.generateExcel({
        transactions: parseResult.transactions,
        output_path: outputPath,
      });
      setCurrentStep(2);
      if (result.success) {
        message.success(`Excel 已导出: ${result.excel_path}`);
      } else {
        message.error(`导出失败：${result.error}`);
      }
    } catch (error: any) {
      message.error(`导出出错：${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // ---- 导出凭证 ----
  const handleOpenVoucherModal = () => {
    // 自动推导期间名称（取解析结果中最早的月份，如 "2026年3月"）
    if (!period && parseResult?.transactions?.length) {
      const dates: string[] = parseResult.transactions.map((t: any) => t.date as string);
      dates.sort();
      const earliest = dates[0]; // 'YYYY-MM-DD'
      const [y, m] = earliest.split('-');
      setPeriod(`${y}年${Number(m)}月`);
    }
    setVoucherModalOpen(true);
  };

  const handleSelectSubjectsFile = async () => {
    const filePath = await window.electronAPI.selectFile('xlsx');
    if (filePath) {
      setSubjectsPath(filePath);
      localStorage.setItem(LS_KEY, filePath);
    }
  };

  const handleClearSubjectsFile = () => {
    setSubjectsPath('');
    localStorage.removeItem(LS_KEY);
  };

  const handleExportVoucher = async () => {
    if (!parseResult?.transactions?.length) {
      message.warning('没有可导出的交易数据');
      return;
    }

    if (!subjectsPath) {
      message.warning('请先选择科目表文件（xlsx）');
      return;
    }

    // 1. 弹出保存路径对话框
    const defaultName = `voucher_${period || Date.now()}.xlsx`;
    const outputPath = await window.electronAPI.saveFileDialog({
      title: '保存凭证 Excel',
      defaultPath: defaultName,
    });
    if (!outputPath) return; // 用户取消

    setVoucherLoading(true);
    try {
      const result = await window.electronAPI.generateVoucher({
        transactions: parseResult.transactions,
        output_path: outputPath,
        subjects_path: subjectsPath || '',
        period: period,
      });

      if (result.success) {
        message.success(`凭证已导出: ${result.excel_path}`);
        setVoucherModalOpen(false);
      } else {
        message.error(`导出失败：${result.error}`);
      }
    } catch (error: any) {
      message.error(`导出出错：${error.message}`);
    } finally {
      setVoucherLoading(false);
    }
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

          {/* 导出操作区（解析成功后显示） */}
          {parseResult?.success && (
            <Card title="导出" style={{ marginTop: 16 }}>
              <Space>
                <Button
                  type="primary"
                  loading={loading}
                  onClick={handleExportExcel}
                >
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
                <Button onClick={() => { setParseResult(null); setCurrentStep(0); }}>
                  重新选择文件
                </Button>
              </Space>
            </Card>
          )}

          {/* 进度条 */}
          {(loading || currentStep > 0) && (
            <Card title="处理进度" style={{ marginTop: 16 }}>
              <ProgressSteps currentStep={currentStep} processingTime={processingTimeMs} />
            </Card>
          )}

          {/* 解析结果 */}
          {parseResult && (
            <Card title="解析结果" style={{ marginTop: 16 }}>
              <p>银行：{parseResult.bank}</p>
              <p>解析交易数：{matchedCount}</p>
              {parseResult.statement_date && (
                <p>账单日期：{parseResult.statement_date}</p>
              )}
            </Card>
          )}

          {/* 交易表格 */}
          {parseResult?.transactions && (
            <Card title="交易列表" style={{ marginTop: 16 }}>
              <TransactionTable
                transactions={parseResult.transactions}
                loading={loading}
              />
            </Card>
          )}
        </div>
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        Finance Assistant ©2026 — Built with Electron + React + Python
      </Footer>

      {/* 导出凭证弹窗 */}
      <Modal
        title="导出凭证（金蝶精斗云格式）"
        open={voucherModalOpen}
        onCancel={() => setVoucherModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setVoucherModalOpen(false)}>
            取消
          </Button>,
          <Button
            key="export"
            type="primary"
            loading={voucherLoading}
            onClick={handleExportVoucher}
          >
            选择保存路径并导出
          </Button>,
        ]}
        width={520}
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
          <Form.Item
            label="科目表文件"
            validateStatus={!subjectsPath ? 'warning' : undefined}
            help={
              subjectsPath
                ? `当前使用：${subjectsPath.split(/[\\/]/).pop()}`
                : '请选择从金蝶精斗云导出的科目 xlsx'
            }
          >
            <Space.Compact style={{ width: '100%' }}>
              <Input
                value={subjectsPath}
                readOnly
                placeholder="点击右侧「选择文件」按钮"
                status={!subjectsPath ? 'warning' : undefined}
                style={{ flex: 1 }}
              />
              <Button onClick={handleSelectSubjectsFile}>选择文件</Button>
              {subjectsPath && (
                <Button danger onClick={handleClearSubjectsFile}>清除</Button>
              )}
            </Space.Compact>
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}

export default App;
