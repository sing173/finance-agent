import { useState } from 'react';
import { Collapse, Button, Space, Typography } from 'antd';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import { TransactionTable } from './TransactionTable';
import type { BatchFileResult, Transaction } from '@shared/types';

const { Text } = Typography;

interface BatchResultPanelProps {
  files: BatchFileResult[];
  onRetry: (filePaths: string[]) => void;
  onEditTransaction: (filePath: string, txn: Transaction) => void;
  onPreviewVoucher: () => void;
}

export function BatchResultPanel({
  files,
  onRetry,
  onEditTransaction,
  onPreviewVoucher,
}: BatchResultPanelProps) {
  const [expandAll, setExpandAll] = useState(false);

  const successFiles = files.filter((f) => f.status === 'success');
  const failedFiles = files.filter((f) => f.status === 'failed');
  const totalTransactions = files.reduce((sum, f) => sum + f.transactionCount, 0);

  const allExpanded = expandAll;
  const toggleExpand = () => setExpandAll(!expandAll);

  // 按状态排序：成功在前，失败在后
  const sortedFiles = [...files].sort((a, b) => {
    if (a.status === 'success' && b.status !== 'success') return -1;
    if (a.status !== 'success' && b.status === 'success') return 1;
    return a.fileName.localeCompare(b.fileName);
  });

  const getCollapseItems = () => {
    return sortedFiles.map((file) => {
      const isSuccess = file.status === 'success';
      const isFailed = file.status === 'failed';

      const label = (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
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
                onClick={(e) => {
                  e.stopPropagation();
                  onRetry([file.filePath]);
                }}
              >
                重试
              </Button>
            </>
          )}
        </div>
      );

      // 展开内容
      let body: React.ReactNode = null;
      if (isSuccess && file.transactions && file.transactions.length > 0) {
        body = (
          <TransactionTable
            transactions={file.transactions}
            loading={false}
            onEdit={(txn) => onEditTransaction(file.filePath, txn)}
          />
        );
      } else if (isFailed) {
        body = (
          <Text type="danger">
            {file.error || '解析失败，请重试'}
          </Text>
        );
      }

      return {
        key: file.filePath,
        label,
        children: body,
        style: isFailed ? { border: '1px solid #ff4d4f', borderRadius: 8 } : undefined,
      };
    });
  };

  return (
    <div>
      {/* 摘要卡片 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 16,
          padding: '12px 16px',
          background: '#fafafa',
          borderRadius: 8,
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

        <Space>
          <Button type="primary" onClick={onPreviewVoucher} disabled={successFiles.length === 0}>
            凭证生成
          </Button>
        </Space>
      </div>

      {/* 展开/收起 按钮 */}
      {files.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <Button
            type="link"
            size="small"
            onClick={toggleExpand}
            icon={allExpanded ? <LeftOutlined /> : <RightOutlined />}
          >
            {allExpanded ? '全部收起' : '全部展开'}
          </Button>
        </div>
      )}

      {/* 折叠面板 */}
      <Collapse
        items={getCollapseItems()}
        {...(expandAll
          ? { activeKey: sortedFiles.map((f) => f.filePath) }
          : { defaultActiveKey: [] }
        )}
      />
    </div>
  );
}
