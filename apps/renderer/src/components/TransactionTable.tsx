import { Table, Tag, Space, Typography, Button, Pagination } from 'antd';
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
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(10);

  const paginatedData = useMemo(() => {
    const start = (page - 1) * size;
    return transactions.slice(start, start + size).map((t, i) => ({
      ...t,
      _key: t.reference_number || `tx-${start + i}`,
    }));
  }, [transactions, page, size]);

  const columns: ColumnsType<any> = [
    {
      title: '#',
      key: 'seq',
      width: 50,
      render: (_: any, __: any, index: number) => (page - 1) * size + index + 1,
    },
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
    {
      title: '操作',
      key: 'action',
      width: 120,
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
    <div>
      <Table
        columns={columns}
        dataSource={paginatedData}
        rowKey="_key"
        loading={loading}
        pagination={false}
        scroll={{ y: 470 }}
        bordered
        size="middle"
      />
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
        <Pagination
          current={page}
          pageSize={size}
          total={transactions.length}
          showSizeChanger
          pageSizeOptions={[10, 20, 50, 100]}
          showTotal={(total) => `共 ${total} 条`}
          onChange={(p, s) => { setPage(p); if (s !== size) { setSize(s); setPage(1); } }}
        />
      </div>
    </div>
  );
}
