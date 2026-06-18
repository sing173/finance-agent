import { useState, useMemo } from 'react';
import { Modal, InputNumber, Input, Space, Typography, Button, Alert } from 'antd';
import { PlusOutlined, MinusCircleOutlined, ThunderboltOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface SplitPart {
  amount: number;
  summary: string;
}

interface SplitEntryModalProps {
  open: boolean;
  originalAmount: number;
  originalSummary: string;
  isDebit: boolean;
  onCancel: () => void;
  onConfirm: (parts: SplitPart[]) => void;
}

export function SplitEntryModal({
  open,
  originalAmount,
  originalSummary,
  isDebit,
  onCancel,
  onConfirm,
}: SplitEntryModalProps) {
  const [parts, setParts] = useState<SplitPart[]>([
    { amount: 0, summary: originalSummary },
    { amount: 0, summary: originalSummary },
  ]);

  const total = useMemo(() => parts.reduce((s, p) => s + (p.amount || 0), 0), [parts]);
  const remaining = originalAmount - total;
  const overLimit = remaining < 0;
  const hasEmpty = parts.some((p) => !p.amount || p.amount <= 0);

  const addPart = () => {
    setParts([...parts, { amount: 0, summary: originalSummary }]);
  };

  const removePart = (index: number) => {
    if (parts.length <= 2) return;
    setParts(parts.filter((_, i) => i !== index));
  };

  const updateAmount = (index: number, value: number | null) => {
    const next = [...parts];
    next[index] = { ...next[index], amount: value || 0 };
    setParts(next);
  };

  const updateSummary = (index: number, value: string) => {
    const next = [...parts];
    next[index] = { ...next[index], summary: value };
    setParts(next);
  };

  const autoFillRemaining = () => {
    if (remaining <= 0) return;
    setParts([...parts, { amount: Math.round(remaining * 100) / 100, summary: originalSummary }]);
  };

  const handleConfirm = () => {
    if (overLimit || hasEmpty) return;
    onConfirm(parts);
  };

  const handleCancel = () => {
    setParts([
      { amount: 0, summary: originalSummary },
      { amount: 0, summary: originalSummary },
    ]);
    onCancel();
  };

  return (
    <Modal
      title="拆分分录"
      open={open}
      onOk={handleConfirm}
      onCancel={handleCancel}
      okText="确认拆分"
      cancelText="取消"
      okButtonProps={{ disabled: overLimit || hasEmpty }}
      width={520}
    >
      <div style={{ marginBottom: 16 }}>
        <Text>
          原金额：{isDebit ? '借方' : '贷方'}{' '}
          <Text strong>{originalAmount.toLocaleString()}</Text>
        </Text>
      </div>

      <div style={{ marginBottom: 12 }}>
        <Text>拆分为 {parts.length} 份：</Text>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
        {parts.map((part, index) => (
          <div key={index} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Text style={{ width: 50, flexShrink: 0 }}>第 {index + 1} 份</Text>
            <InputNumber
              value={part.amount}
              onChange={(v) => updateAmount(index, v)}
              min={0.01}
              step={0.01}
              precision={2}
              style={{ width: 130 }}
              placeholder="金额"
            />
            <Input
              value={part.summary}
              onChange={(e) => updateSummary(index, e.target.value)}
              placeholder="摘要"
              style={{ flex: 1 }}
            />
            {parts.length > 2 && (
              <Button
                type="text"
                danger
                icon={<MinusCircleOutlined />}
                onClick={() => removePart(index)}
              />
            )}
          </div>
        ))}
      </div>

      <Space style={{ marginBottom: 16 }}>
        <Button type="dashed" icon={<PlusOutlined />} onClick={addPart}>
          添加一份
        </Button>
        {!overLimit && remaining > 0.005 && (
          <Button type="dashed" icon={<ThunderboltOutlined />} onClick={autoFillRemaining}>
            自动添加剩余 {remaining.toFixed(2)}
          </Button>
        )}
      </Space>

      <div style={{ borderTop: '1px solid #d6d3cd', paddingTop: 12 }}>
        <Space>
          <Text>合计：</Text>
          <Text strong style={{ color: overLimit ? '#991b1b' : '#065f46' }}>
            {total.toLocaleString()}
          </Text>
          <Text type="secondary">/ {originalAmount.toLocaleString()}</Text>
        </Space>
        {overLimit && (
          <Alert
            message="合计金额超过原金额"
            type="error"
            showIcon
            style={{ marginTop: 8 }}
          />
        )}
        {!overLimit && remaining > 0.005 && (
          <Alert
            message={`剩余 ${remaining.toFixed(2)} 未分配`}
            type="warning"
            showIcon
            style={{ marginTop: 8 }}
          />
        )}
      </div>
    </Modal>
  );
}
