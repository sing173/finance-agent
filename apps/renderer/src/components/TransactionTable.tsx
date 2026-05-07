import { Table, Tag, Space, Typography, Button } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { Transaction } from '@shared/types';

const { Text } = Typography;

interface TransactionTableProps {
  transactions: Transaction[];
  loading?: boolean;
  highlight?: 'matched' | 'unreconciled' | 'suspicious';
}

export function TransactionTable({ transactions, loading, highlight }: TransactionTableProps) {
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
      render: (amount: number) => (
        <Text strong style={{ color: amount >= 0 ? '#52c41a' : '#ff4d4f' }}>
          {amount.toFixed(2)}
        </Text>
      ),
      sorter: (a, b) => a.amount - b.amount,
      width: 120,
    },
    {
      title: '方向',
      dataIndex: 'direction',
      key: 'direction',
      render: (dir: string) => (
        <Tag color={dir === 'income' ? 'green' : dir === 'expense' ? 'red' : 'blue'}>
          {dir === 'income' ? '收入' : dir === 'expense' ? '支出' : '转账'}
        </Tag>
      ),
      filters: [
        { text: '收入', value: 'income' },
        { text: '支出', value: 'expense' },
        { text: '转账', value: 'transfer' },
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
      title: '流水号',
      dataIndex: 'reference_number',
      key: 'reference_number',
      width: 150,
    },
    {
      title: '操作',
      key: 'action',
      render: () => (
        <Space>
          <Button type="link" size="small">编辑</Button>
          <Button type="link" size="small" danger>删除</Button>
        </Space>
      ),
      width: 120,
    },
  ];

  // 根据 highlight 类型设置行样式
  const rowClassName = (_record: Transaction) => {
    if (highlight === 'matched') return 'row-matched';
    if (highlight === 'unreconciled') return 'row-unreconciled';
    if (highlight === 'suspicious') return 'row-suspicious';
    return '';
  };

  return (
    <Table
      columns={columns}
      dataSource={transactions}
      rowKey={(record) => record.reference_number || `row-${record.date}-${record.amount}`}
      loading={loading}
      pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
      scroll={{ y: 400 }}
      bordered
      size="middle"
      rowClassName={rowClassName}
    />
  );
}
