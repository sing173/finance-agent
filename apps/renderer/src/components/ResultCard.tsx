import { Button, Space, Typography, Tag, Card } from 'antd';

const { Text } = Typography;

interface ResultCardProps {
  bank: string;
  docType: string;
  isManual: boolean;
  transactionCount: number;
  statementDate?: string;
  error?: string;
  detectUnknown?: boolean;
  loading?: boolean;
  onRedetect: () => void;
  onModifyConfig: () => void;
  onConfirmParse?: () => void;
}

export function ResultCard({
  bank,
  docType,
  isManual,
  transactionCount,
  statementDate,
  error,
  detectUnknown,
  loading = false,
  onRedetect,
  onModifyConfig,
  onConfirmParse,
}: ResultCardProps) {
  const isSuccess = !error && transactionCount > 0;
  const isDetectFail = detectUnknown || false;

  return (
    <Card
      style={{
        borderColor: isDetectFail ? '#faad14' : error ? '#ff4d4f' : isSuccess ? '#52c41a' : undefined,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <Tag
          color={
            loading
              ? 'processing'
              : isDetectFail
              ? 'warning'
              : error
              ? 'error'
              : isSuccess
              ? 'success'
              : 'default'
          }
        >
          {loading ? '解析中...' : isDetectFail ? '识别失败' : error ? '失败' : isSuccess ? '成功' : '检测中'}
        </Tag>

        {loading ? (
          <Text type="secondary">正在解析文件，请稍候...</Text>
        ) : isDetectFail ? (
          <Text type="warning">未能自动识别银行类型</Text>
        ) : error ? (
          <Text type="danger">解析失败：{error}</Text>
        ) : (
          <Text>
            <Text strong>{isManual ? '已选择' : '检测到'}</Text>
            {`：${bank} · ${docType}`}
          </Text>
        )}
      </div>

      {isSuccess && (
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">
            解析交易数：{transactionCount} 笔
            {statementDate && ` · 账单日期：${statementDate}`}
          </Text>
        </div>
      )}

      <Space>
        {!error && (
          <Button onClick={onRedetect} disabled={loading}>重新检测</Button>
        )}
        {onConfirmParse && (
          <Button type="primary" onClick={onConfirmParse} loading={loading}>
            确认解析
          </Button>
        )}
        <Button onClick={onModifyConfig} disabled={loading}>修改配置</Button>
      </Space>
    </Card>
  );
}
