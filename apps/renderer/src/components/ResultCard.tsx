import { Button, Space, Typography, Tag, Card } from 'antd';
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface ResultCardProps {
  /** 'detect' | 'parsing' | 'success' | 'failed' */
  phase: 'detect' | 'parsing' | 'success' | 'failed';
  bank: string;
  docType: string;
  transactionCount: number;
  statementDate?: string;
  error?: string;
  detectUnknown?: boolean;
  isManual?: boolean;
  onRedetect: () => void;
  onModifyConfig: () => void;
  onStartParse: () => void;
  onPreviewVoucher?: () => void;
}

const bankLabel = (bank: string) =>
  bank === '未知' || bank === '未知银行' || !bank ? '未知' : bank;

export function ResultCard({
  phase,
  bank,
  docType,
  transactionCount,
  statementDate,
  error,
  detectUnknown,
  isManual = false,
  onRedetect,
  onModifyConfig,
  onStartParse,
  onPreviewVoucher,
}: ResultCardProps) {
  const isSuccess = phase === 'success';
  const isFailed = phase === 'failed';
  const isParsing = phase === 'parsing';
  const beforeParse = phase === 'detect' || phase === 'parsing';
  const afterParse = phase === 'success' || phase === 'failed';

  const tagText = isParsing
    ? '解析中...'
    : detectUnknown
    ? '识别失败'
    : isSuccess
    ? '解析成功'
    : isFailed
    ? '解析失败'
    : isManual
    ? '已设置'
    : '已检测';
  const tagColor = isParsing
    ? 'processing'
    : detectUnknown
    ? 'warning'
    : isSuccess
    ? 'success'
    : isFailed
    ? 'error'
    : isManual
    ? 'purple'
    : 'blue';

  const borderColor = isParsing
    ? '#1677ff'
    : detectUnknown
    ? '#faad14'
    : isSuccess
    ? '#52c41a'
    : isFailed
    ? '#ff4d4f'
    : undefined;

  return (
    <Card style={{ borderColor }}>
      {/* 第一行：Tag + 银行/类型/日期/笔数 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <Tag color={tagColor}>{tagText}</Tag>

        <Text>
          {bankLabel(bank)}
        </Text>
        <Text type="secondary">|</Text>
        <Text>{docType || 'unknown'}</Text>

        {/* 解析成功后显示额外信息 */}
        {isSuccess && (
          <>
            {statementDate && (
              <>
                <Text type="secondary">|</Text>
                <Text>{statementDate}</Text>
              </>
            )}
            <Text type="secondary">|</Text>
            <Text>
              <Text strong>{transactionCount}</Text> 笔交易
            </Text>
          </>
        )}
      </div>

      {/* 第二行：错误信息 */}
      {isFailed && error && (
        <div style={{ marginBottom: 16 }}>
          <Text type="danger">{error}</Text>
        </div>
      )}

      {/* 第三行：按钮 */}
      <Space>
        {/* 重新检测 — 解析前/识别失败后可见 */}
        {beforeParse && (
          <Button onClick={onRedetect} disabled={isParsing}>重新检测</Button>
        )}

        {/* 修改配置 — 仅解析前可见 */}
        {beforeParse && (
          <Button onClick={onModifyConfig} disabled={isParsing}>修改配置</Button>
        )}

        {/* 开始解析 / 重新解析 */}
        <Button
          type="primary"
          icon={afterParse ? <ReloadOutlined /> : <PlayCircleOutlined />}
          onClick={onStartParse}
          loading={isParsing}
        >
          {afterParse ? '重新解析' : '开始解析'}
        </Button>

        {/* 导出凭证 → 凭证预览 — 仅解析成功后可见 */}
        {isSuccess && onPreviewVoucher && (
          <Button
            style={{ background: '#52c41a', color: '#fff', borderColor: '#52c41a' }}
            onClick={onPreviewVoucher}
          >
            导出凭证
          </Button>
        )}
      </Space>
    </Card>
  );
}