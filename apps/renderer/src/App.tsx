import { Layout, Typography, Button, Card, message, Space, Modal, Form, Input } from 'antd';
import { useState, useEffect } from 'react';
import { FileDropZone } from './components/FileDropZone';
import { TransactionTable } from './components/TransactionTable';
import { ProgressSteps } from './components/ProgressSteps';

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
      onPythonStatus: (callback: (status: string) => void) => void;
      getPythonStatus: () => Promise<string>;
    };
  }
}

function App() {
  const [backendStatus, setBackendStatus] = useState<string>('检查中...');
  const [loading, setLoading] = useState(false);
  const [healthModalOpen, setHealthModalOpen] = useState(false);
  const [healthData, setHealthData] = useState<any>(null);
  const [parseResult, setParseResult] = useState<any>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [processingTimeMs, setProcessingTimeMs] = useState(0);

  // 导出凭证弹窗相关状态
  const [voucherModalOpen, setVoucherModalOpen] = useState(false);
  const [voucherLoading, setVoucherLoading] = useState(false);
  const [period, setPeriod] = useState('');

  // 导入科目表
  const [importSubjectsLoading, setImportSubjectsLoading] = useState(false);
  const [subjectsCount, setSubjectsCount] = useState<number | null>(null);

  // 启动时查询内置科目数量
  useEffect(() => {
    const checkSubjects = async () => {
      try {
        const result = await window.electronAPI.getSubjectsInfo();
        if (result.success) {
          setSubjectsCount(result.count);
        }
      } catch {
        // 忽略，检查失败不影响使用
      }
    };
    checkSubjects();
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
        setHealthData(null);
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
      setHealthData(result);
      setHealthModalOpen(true);
      message.success('后端连接成功！');
    } catch (error: any) {
      setBackendStatus(`离线: ${error.message}`);
      message.error('后端连接失败');
      setHealthData(null);
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

  const handleExportVoucher = async () => {
    if (!parseResult?.transactions?.length) {
      message.warning('没有可导出的交易数据');
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

  // ---- 导入科目表 ----
  const handleImportSubjects = async () => {
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
    } catch (error: any) {
      message.error(`导入出错：${error.message}`);
    } finally {
      setImportSubjectsLoading(false);
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 24px' }}>
        <Title level={3} style={{ color: '#fff', margin: '16px 0' }}>
          Finance Assistant
        </Title>
      </Header>
      <Content style={{ padding: '20px 24px' }}>
        {/* 第一行：系统设置 + 文件选择 */}
        <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 16 }}>
          {/* 系统设置卡片（连接测试 + 科目管理） */}
          <Card title="系统设置" style={{ width: 400, flexShrink: 0, height: 200 }}>
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary">后端状态：</Text>
              <Text strong>{backendStatus}</Text>
            </div>
            <Space style={{ marginBottom: 16 }}>
              <Button type="primary" loading={loading} onClick={testConnection}>
                测试连接
              </Button>
              <Button
                loading={importSubjectsLoading}
                onClick={handleImportSubjects}
              >
                导入科目表
              </Button>
            </Space>
            <div>
              <Text type="secondary">
                当前内置科目：{subjectsCount !== null ? `${subjectsCount} 条` : '未知'}
              </Text>
              {subjectsCount !== null && subjectsCount > 0 && (
                <Text type="success" style={{ marginLeft: 8 }}>
                  ✓ 已就绪
                </Text>
              )}
            </div>
          </Card>

          {/* 文件上传区域 */}
          <div style={{ flex: 1, minWidth: 300, height: 200 }}>
            <FileDropZone onFileSelected={handleFileSelected} />
          </div>
        </div>

        {/* 以下卡片垂直排列 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

          {/* 导出操作区（解析成功后显示） */}
          {parseResult?.success && (
            <Card title="导出">
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
            <Card title="处理进度">
              <ProgressSteps currentStep={currentStep} processingTime={processingTimeMs} />
            </Card>
          )}

          {/* 解析结果 */}
          {parseResult && (
            <Card title="解析结果">
              <p>银行：{parseResult.bank}</p>
              <p>解析交易数：{matchedCount}</p>
              {parseResult.statement_date && (
                <p>账单日期：{parseResult.statement_date}</p>
              )}
            </Card>
          )}

          {/* 交易表格 */}
          {parseResult?.transactions && (
            <Card title="交易列表">
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

      {/* 导出凭证弹窗 — 仅保留期间名称 */}
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

      {/* 健康检查结果弹窗 */}
      <Modal
        title="连接测试结果"
        open={healthModalOpen}
        onCancel={() => setHealthModalOpen(false)}
        footer={null}
      >
        <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
          {JSON.stringify(healthData, null, 2)}
        </pre>
      </Modal>
    </Layout>
  );
}

export default App;
