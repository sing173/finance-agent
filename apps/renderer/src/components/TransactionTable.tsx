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
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const dataSource = useMemo(() =>
    transactions.map((t, i) => ({
      ...t,
      _key: `tx-${i}`,
    })),
    [transactions]
  );

  const needScroll = pageSize > 10 && dataSource.length > 10;

  const columns: ColumnsType<any> = [
    {
      title: '#',
      key: 'seq',
      width: '4%',
      render: (_: any, __: any, index: number) => (currentPage - 1) * pageSize + index + 1,
    },
    {
      title: '日期',
      dataIndex: 'date',
      key: 'date',
      sorter: (a, b) => a.date.localeCompare(b.date),
      width: '10%',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: '25%',
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
      width: '10%',
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
      width: '6%',
    },
    {
      title: '对方户名',
      dataIndex: 'counterparty',
      key: 'counterparty',
      ellipsis: true,
      width: '18%',
    },
    {
      title: '本方帐号',
      dataIndex: 'account_number',
      key: 'account_number',
      width: '18%',
    },
    {
      title: '操作',
      key: 'action',
      width: '9%',
      render: (_: any, record: any) => (
        <Space>
          {onEdit && (
            <Button type="link" size="small" onClick={() => onEdit(record)}>编辑</Button>
          )}
          {onDelete && (
            <Button type="link" size="small" danger onClick={() => onDelete(record)}>删除</Button>
          )}
        </Space>
      ),
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
        showTotal: (total) => `共 ${total} 条`,
        onChange: (page, size) => {
          setCurrentPage(page);
          setPageSize(size);
        },
      }}
      scroll={needScroll ? { y: 470 } : undefined}
      bordered
      size="middle"
    />
  );
}
