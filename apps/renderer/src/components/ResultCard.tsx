import { Button, Space, Typography, Tag, Card } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { TransactionTable } from './TransactionTable';
import type { Transaction } from '@shared/types';

const { Text } = Typography;

interface ResultCardProps {
  /** 'detect' | 'parsing' | 'success' | 'failed' */
  phase: 'detect' | 'parsing' | 'success' | 'failed';
  fileName?: string;
  bank: string;
  docType: string;
  transactionCount: number;
  statementDate?: string;
  error?: string;
  detectUnknown?: boolean;
  isManual?: boolean;
  transactions?: Transaction[];
  onRedetect: () => void;
  onModifyConfig: () => void;
  onStartParse: () => void;
  onPreviewVoucher?: () => void;
  onEditTransaction?: (txn: Transaction) => void;
}

const bankLabel = (bank: string) =>
  bank === '未知' || bank === '未知银行' || !bank ? '未知' : bank;

export function ResultCard({
  phase,
  fileName,
  bank,
  docType,
  transactionCount,
  statementDate,
  error,
  detectUnknown,
  isManual = false,
  transactions = [],
  onRedetect,
  onModifyConfig,
  onStartParse,
  onPreviewVoucher,
  onEditTransaction,
}: ResultCardProps) {
  const isSuccess = phase === 'success';
  const isFailed = phase === 'failed';
  const isParsing = phase === 'parsing';
  const beforeParse = phase === 'detect' || phase === 'parsing';

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

  return (
    <Card style={{ border: '1px solid #d6d3cd' }}>
      {/* 顶部信息行：Tag + 银行/类型/日期/笔数 + 凭证生成按钮（靠右） */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginBottom: 16,
          flexWrap: 'wrap',
        }}
      >
        <Tag color={tagColor}>{tagText}</Tag>

        {fileName && (
          <>
            <Text strong ellipsis={{ tooltip: fileName }} style={{ maxWidth: 260 }}>{fileName}</Text>
            <Text type="secondary">|</Text>
          </>
        )}

        <Text>{bankLabel(bank)}</Text>
        <Text type="secondary">|</Text>
        <Text>{docType || 'unknown'}</Text>

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

        {/* 凭证生成按钮 */}
        {isSuccess && onPreviewVoucher && (
          <Button
            style={{
              background: '#dc2626',
              color: '#fff',
              borderColor: '#dc2626',
            }}
            onClick={onPreviewVoucher}
          >
            凭证生成
          </Button>
        )}
      </div>

      {/* 错误信息 */}
      {isFailed && error && (
        <div style={{ marginBottom: 16 }}>
          <Text type="danger">{error}</Text>
        </div>
      )}

      {/* 交易表格 — 直接融合在 Card 内部 */}
      {isSuccess && transactions.length > 0 && onEditTransaction && (
        <TransactionTable
          transactions={transactions}
          loading={isParsing}
          onEdit={onEditTransaction}
        />
      )}

      {/* 底部操作按钮 — 仅解析前可见 */}
      {beforeParse && (
        <Space style={{ marginTop: 16 }}>
          <Button onClick={onRedetect} disabled={isParsing}>重新检测</Button>
          <Button onClick={onModifyConfig} disabled={isParsing}>修改配置</Button>
          <Button
            style={{ background: '#dc2626', color: '#fff', borderColor: '#dc2626' }}
            icon={<PlayCircleOutlined />}
            onClick={onStartParse}
            loading={isParsing}
          >
            开始解析
          </Button>
        </Space>
      )}
    </Card>
  );
}
