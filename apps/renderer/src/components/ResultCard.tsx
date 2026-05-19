import { Button, Space, Typography, Tag, Card } from 'antd';

const { Text } = Typography;

interface ResultCardProps {
  bank: string;
  docType: string;
  isManual: boolean;
  transactionCount: number;
  statementDate?: string;
  error?: string;
  onRedetect: () => void;
  onModifyConfig: () => void;
  onReselectFile: () => void;
  onConfirmParse?: () => void;
}

export function ResultCard({
  bank,
  docType,
  isManual,
  transactionCount,
  statementDate,
  error,
  onRedetect,
  onModifyConfig,
  onReselectFile,
  onConfirmParse,
}: ResultCardProps) {
  const isSuccess = !error && transactionCount > 0;

  return (
    <Card
      style={{
        borderColor: error ? '#ff4d4f' : isSuccess ? '#52c41a' : undefined,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <Tag
          color={
            error
              ? 'error'
              : isSuccess
              ? 'success'
              : 'default'
          }
        >
          {error ? '失败' : isSuccess ? '成功' : '检测中'}
        </Tag>

        {error ? (
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
          <Button onClick={onRedetect}>重新检测</Button>
        )}
        {onConfirmParse && (
          <Button type="primary" onClick={onConfirmParse}>确认解析</Button>
        )}
        <Button onClick={onModifyConfig}>修改配置</Button>
        <Button onClick={onReselectFile}>重新选择文件</Button>
      </Space>
    </Card>
  );
}
