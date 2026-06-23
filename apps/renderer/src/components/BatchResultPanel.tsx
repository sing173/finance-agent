import { Button, Space, Typography, Tag, Card, Spin } from 'antd';
import { TransactionTable } from './TransactionTable';
import type { BatchFileResult, Transaction } from '@shared/types';

const { Text } = Typography;

interface BatchResultPanelProps {
  files: BatchFileResult[];
  isParsing?: boolean;
  currentIndex?: number;
  onRetry: (filePaths: string[]) => void;
  onRetryDetect?: () => void;
  onEditTransaction: (filePath: string, txn: Transaction) => void;
  onPreviewVoucher: () => void;
}

export function BatchResultPanel({
  files,
  isParsing = false,
  currentIndex = 0,
  onRetry,
  onRetryDetect,
  onEditTransaction,
  onPreviewVoucher,
}: BatchResultPanelProps) {
  const successFiles = files.filter((f) => f.status === 'success');
  const failedFiles = files.filter((f) => f.status === 'failed');
  const totalTransactions = files.reduce((sum, f) => sum + f.transactionCount, 0);

  // 保留原始索引以便判断 currentIndex
  const filesWithIndex = files.map((f, i) => ({ ...f, _originalIndex: i }));

  // 按状态排序：成功在前，失败在后（解析中不排序，保持原始顺序以匹配 currentIndex）
  const displayFiles = isParsing
    ? filesWithIndex
    : [...filesWithIndex].sort((a, b) => {
        if (a.status === 'success' && b.status !== 'success') return -1;
        if (a.status !== 'success' && b.status === 'success') return 1;
        return a.fileName.localeCompare(b.fileName);
      });

  return (
    <div>
      {/* 摘要卡片 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          marginBottom: 16,
          padding: '12px 16px',
          background: '#ffffff',
          border: '1px solid #d6d3cd',
          borderRadius: 6,
        }}
      >
        <Space size={16}>
          <Text>
            共 <Text strong>{files.length}</Text> 个文件
          </Text>
          <Text>
            <Text strong>{totalTransactions}</Text> 笔交易
          </Text>
          <Text type="success">
            成功 <Text strong>{successFiles.length}</Text>
          </Text>
          {failedFiles.length > 0 && (
            <Text type="danger">
              失败 <Text strong>{failedFiles.length}</Text>
            </Text>
          )}
        </Space>

        <Space size={12}>
          {onRetryDetect && (
            <Button onClick={onRetryDetect}>重新识别</Button>
          )}
          <Button
            style={{ background: '#dc2626', color: '#fff', borderColor: '#dc2626' }}
            onClick={onPreviewVoucher}
            disabled={successFiles.length === 0 || isParsing}
          >
            凭证生成
          </Button>
        </Space>
      </div>

      {/* 解析进度（从 BatchFileSelector 迁移） */}
      {isParsing && currentIndex > 0 && (
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary">
            <Spin size="small" style={{ marginRight: 8 }} />
            正在解析 {currentIndex}/{files.length}
          </Text>
        </div>
      )}

      {/* 文件卡片列表 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {displayFiles.map((file) => {
          const isSuccess = file.status === 'success';
          const isFailed = file.status === 'failed';
          const isCurrentParsing =
            isParsing && (file._originalIndex as number) === currentIndex - 1;

          const tagText = isCurrentParsing
            ? '解析中...'
            : isSuccess
            ? '解析成功'
            : isFailed
            ? '解析失败'
            : '等待解析';
          const tagColor = isCurrentParsing
            ? 'processing'
            : isSuccess
            ? 'success'
            : isFailed
            ? 'error'
            : 'default';

          return (
            <Card
              key={file.filePath}
              style={{
                border: '1px solid #d6d3cd',
                marginBottom: 0,
                background: isCurrentParsing ? '#e8eef5' : undefined,
                transition: 'background 0.2s',
              }}
              styles={{ body: { padding: '16px 20px' } }}
            >
              {/* 第一行：Tag + 文件名/银行/类型/日期/笔数 */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  marginBottom: 16,
                  flexWrap: 'wrap',
                }}
              >
                {isCurrentParsing && <Spin size="small" />}
                <Tag color={tagColor}>{tagText}</Tag>

                <Text strong ellipsis style={{ maxWidth: 260 }}>
                  {file.fileName}
                </Text>

                {isSuccess && (
                  <>
                    <Text type="success">✓ {file.transactionCount}笔</Text>
                    <Text type="secondary">|</Text>
                    <Text>{file.bank}</Text>
                    <Text type="secondary">|</Text>
                    <Text>{file.docType}</Text>
                    {file.statementDate && (
                      <>
                        <Text type="secondary">|</Text>
                        <Text>{file.statementDate}</Text>
                      </>
                    )}
                  </>
                )}

                {isFailed && (
                  <>
                    <Text type="danger">✗ 解析失败</Text>
                    <Button
                      size="small"
                      type="link"
                      danger
                      onClick={() => onRetry([file.filePath])}
                    >
                      重试
                    </Button>
                  </>
                )}
              </div>

              {/* 第二行：错误信息 */}
              {isFailed && file.error && (
                <div style={{ marginBottom: 16 }}>
                  <Text type="danger">{file.error}</Text>
                </div>
              )}

              {/* 第三行：交易表格 */}
              {isSuccess &&
                file.transactions &&
                file.transactions.length > 0 && (
                  <TransactionTable
                    transactions={file.transactions}
                    loading={false}
                    onEdit={(txn) => onEditTransaction(file.filePath, txn)}
                  />
                )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
