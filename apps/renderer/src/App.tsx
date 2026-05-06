import { Layout, Typography, Button, Card, message } from 'antd';
import { useState, useEffect } from 'react';
import { FileDropZone } from './components/FileDropZone';

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

          {/* 解析结果 */}
          {parseResult && (
            <Card title="解析结果" style={{ marginTop: 16 }}>
              <p>银行：{parseResult.bank}</p>
              <p>解析交易数：{matchedCount}</p>
            </Card>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
            <ReconDashboard />
          </div>
        </div>
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        Finance Assistant ©2026 — Built with Electron + React + Python
      </Footer>
    </Layout>
  );
}

function ReconDashboard() {
  return (
    <Card title="对账仪表盘" style={{ minHeight: 200 }}>
      <div style={{ textAlign: 'center', padding: '48px 0' }}>
        <Text type="secondary">对账统计和操作面板（开发中）</Text>
      </div>
    </Card>
  );
}

export default App;
