import { Table, Tag, Space, Typography, Button } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { Transaction } from '@shared/types';
import { useMemo, useState } from 'react';

const { Text } = Typography;

interface TransactionTableProps {
  transactions: Transaction[];
  loading?: boolean;
  onEdit?: (txn: Transaction) => void;
  onDelete?: (txn: Transaction) => void;
}

export function TransactionTable({ transactions, loading, onEdit, onDelete }: TransactionTableProps) {
  const [currentPageSize, setCurrentPageSize] = useState(10);

  const dataSource = useMemo(() =>
    transactions.map((t, i) => ({ ...t, _key: t.reference_number || `tx-${i}` })),
    [transactions]
  );

  const needScroll = currentPageSize >= 20 && dataSource.length > 10;

  const columns: ColumnsType<Transaction> = [
    {
      title: '日期',
      dataIndex: 'date',
      key: 'date',
      sorter: (a, b) => a.date.localeCompare(b.date),
      width: 120,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 300,
    },
    {
      title: '金额',
      dataIndex: 'amount',
      key: 'amount',
      render: (amount: number, record: Transaction) => (
        <Text strong style={{ color: record.direction === 'income' ? '#065f46' : '#991b1b' }}>
          {Math.abs(amount).toFixed(2)}
        </Text>
      ),
      sorter: (a, b) => Math.abs(a.amount) - Math.abs(b.amount),
      width: 120,
    },
    {
      title: '方向',
      dataIndex: 'direction',
      key: 'direction',
      render: (dir: string) => (
        <Tag color={dir === 'income' ? 'success' : 'error'}>
          {dir === 'income' ? '收入' : '支出'}
        </Tag>
      ),
      filters: [
        { text: '收入', value: 'income' },
        { text: '支出', value: 'expense' },
      ],
      onFilter: (value: boolean | React.Key, record: Transaction) => record.direction === value,
      width: 100,
    },
    {
      title: '对方户名',
      dataIndex: 'counterparty',
      key: 'counterparty',
      ellipsis: true,
      width: 200,
    },
    {
      title: '本方帐号',
      dataIndex: 'account_number',
      key: 'account_number',
      width: 200,
    },
    // {
    //   title: '本方户名',
    //   dataIndex: 'account_name',
    //   key: 'account_name',
    //   ellipsis: true,
    //   width: 200,
    // },
    // {
    //   title: '流水号',
    //   dataIndex: 'reference_number',
    //   key: 'reference_number',
    //   width: 150,
    // },
    {
      title: '操作',
      key: 'action',
      render: (_: any, _record: Transaction, index: number) => (
        <Space>
          {onEdit && (
            <Button type="link" size="small" onClick={() => onEdit(transactions[index])}>编辑</Button>
          )}
          {onDelete && (
            <Button type="link" size="small" danger onClick={() => onDelete(transactions[index])}>删除</Button>
          )}
        </Space>
      ),
      width: 120,
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={dataSource}
      rowKey="_key"
      loading={loading}
      pagination={{
        defaultPageSize: 10,
        showSizeChanger: true,
        pageSizeOptions: ['10', '20', '50', '100'],
        showTotal: (total: number) => `共 ${total} 条`,
        onShowSizeChange: (_, size) => setCurrentPageSize(size),
      }}
      scroll={needScroll ? { y: 470 } : undefined}
      bordered
      size="middle"
    />
  );
}
