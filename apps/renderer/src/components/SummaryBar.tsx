import { Space, Typography, Tag, Button } from 'antd';

const { Text } = Typography;

export interface SummaryBarProps {
  /** Status tag color */
  status: 'success' | 'error' | 'warning' | 'processing' | 'default';
  /** Status tag text */
  statusText: string;
  /** Bank name */
  bank: string;
  /** Document type label */
  docType: string;
  /** Optional statement date */
  date?: string;
  /** Optional transaction count */
  transactionCount?: number;
  /** Optional error message (shown when status is error) */
  error?: string;
  /** Primary CTA button */
  primaryAction?: {
    text: string;
    onClick: () => void;
    loading?: boolean;
    danger?: boolean;
    style?: React.CSSProperties;
  };
  /** Secondary actions */
  secondaryActions?: Array<{
    text: string;
    onClick: () => void;
  }>;
}

export function SummaryBar({
  status,
  statusText,
  bank,
  docType,
  date,
  transactionCount,
  error,
  primaryAction,
  secondaryActions,
}: SummaryBarProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        background: '#fafafa',
        borderRadius: 8,
        flexWrap: 'wrap',
        gap: 12,
      }}
    >
      <Space size={16} wrap>
        <Tag color={status}>{statusText}</Tag>
        <Text>{bank}</Text>
        <Text type="secondary">|</Text>
        <Text>{docType}</Text>
        {date && (
          <>
            <Text type="secondary">|</Text>
            <Text>{date}</Text>
          </>
        )}
        {transactionCount !== undefined && (
          <>
            <Text type="secondary">|</Text>
            <Text>
              <Text strong>{transactionCount}</Text> 笔
            </Text>
          </>
        )}
      </Space>

      <Space>
        {error && (
          <Text type="danger" style={{ marginRight: 8 }}>{error}</Text>
        )}
        {primaryAction && (
          <Button
            onClick={primaryAction.onClick}
            loading={primaryAction.loading}
            danger={primaryAction.danger}
            style={primaryAction.style}
          >
            {primaryAction.text}
          </Button>
        )}
        {secondaryActions?.map((action, i) => (
          <Button key={i} onClick={action.onClick}>
            {action.text}
          </Button>
        ))}
      </Space>
    </div>
  );
}
