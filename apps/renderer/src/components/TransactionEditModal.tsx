import { useEffect } from 'react';
import { Modal, Form, Input, InputNumber, Tag } from 'antd';
import type { Transaction } from '@shared/types';

interface TransactionEditModalProps {
  open: boolean;
  transaction: Transaction | null;
  onSave: (updated: Transaction) => void;
  onCancel: () => void;
}

export function TransactionEditModal({ open, transaction, onSave, onCancel }: TransactionEditModalProps) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (transaction && open) {
      form.setFieldsValue({
        description: transaction.description,
        amount: Math.abs(transaction.amount),
        counterparty: transaction.counterparty || '',
      });
    }
  }, [transaction, open, form]);

  const handleOk = () => {
    form.validateFields().then((values) => {
      if (!transaction) return;
      const updated: Transaction = {
        ...transaction,
        description: values.description,
        amount: Math.abs(values.amount),
        counterparty: values.counterparty || undefined,
      };
      onSave(updated);
    });
  };

  return (
    <Modal
      title="编辑交易"
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      okText="保存"
      cancelText="取消"
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={handleOk}>
        <Form.Item label="日期">
          <Input value={transaction?.date} disabled />
        </Form.Item>
        <Form.Item
          label="描述"
          name="description"
          rules={[
            { required: true, message: '请输入描述' },
            { max: 200, message: '最多200字符' },
          ]}
        >
          <Input placeholder="交易描述" />
        </Form.Item>
        <Form.Item
          label="金额"
          name="amount"
          rules={[{ required: true, message: '请输入金额' }]}
        >
          <InputNumber min={0.01} precision={2} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="方向">
          <Tag color={transaction?.direction === 'income' ? 'green' : 'red'}>
            {transaction?.direction === 'income' ? '收入' : '支出'}
          </Tag>
        </Form.Item>
        <Form.Item label="对方户名" name="counterparty">
          <Input placeholder="对方户名" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
