import { useState, useEffect } from 'react';
import { Modal, Select, Checkbox, Button, Space } from 'antd';

interface ManualOverrideModalProps {
  open: boolean;
  fileCount: number; // 1 = 单文件, >1 = 批量
  isPdfOnly: boolean; // 仅当所有文件都是 PDF 时显示 OCR 选项
  initialBank?: string;
  initialDocType?: string;
  initialOcr?: boolean;
  onConfirm: (bank: string, docType: string, forceOcr: boolean) => void;
  onCancel: () => void;
}

export function ManualOverrideModal({
  open,
  fileCount,
  isPdfOnly,
  initialBank,
  initialDocType,
  initialOcr = false,
  onConfirm,
  onCancel,
}: ManualOverrideModalProps) {
  const [bank, setBank] = useState<string>(initialBank || '');
  const [docType, setDocType] = useState<string>(initialDocType || '');
  const [forceOcr, setForceOcr] = useState<boolean>(initialOcr);
  const [banks, setBanks] = useState<string[]>([]);

  // 加载支持银行列表
  useEffect(() => {
    if (open) {
      (window as any).electronAPI?.detectSupportedBanks?.()
        .then((r: any) => {
          if (r?.success) setBanks(r.banks || []);
        })
        .catch(() => {});
    }
  }, [open]);

  // 打开时预填初始值
  useEffect(() => {
    if (open) {
      if (initialBank) setBank(initialBank);
      if (initialDocType) setDocType(initialDocType);
      setForceOcr(initialOcr);
    }
  }, [open, initialBank, initialDocType, initialOcr]);

  const handleConfirm = () => {
    if (!bank) return;
    onConfirm(bank, docType, forceOcr);
  };

  const docTypeOptions = [
    { value: '流水', label: '流水' },
    { value: '回单', label: '回单' },
  ];

  // 动态文案
  let title: string;
  if (fileCount === 1) {
    title = '无法自动识别，请手动选择';
  } else if (fileCount > 1) {
    title = `有 ${fileCount} 个文件无法自动识别，请手动选择`;
  } else {
    title = '请手动选择';
  }


  return (
    <Modal
      title={title}
      open={open}
      onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button
          key="confirm"
          type="primary"
          disabled={!bank}
          onClick={handleConfirm}
        >
          确定
        </Button>,
      ]}
      width={480}
    >
      <Space direction="vertical" style={{ width: '100%', marginTop: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
            银行类型
          </label>
          <Select
            style={{ width: '100%' }}
            placeholder="请选择银行类型"
            value={bank || undefined}
            onChange={(val) => setBank(val)}
            options={banks.map((b) => ({ value: b, label: b }))}
            showSearch
            filterOption={(input, opt) =>
              (opt?.label ?? '').toLowerCase().includes(input.toLowerCase())
            }
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
            表格类型
          </label>
          <Select
            style={{ width: '100%' }}
            placeholder="请选择表格类型"
            value={docType || undefined}
            onChange={(val) => setDocType(val)}
            options={docTypeOptions}
          />
        </div>

        {isPdfOnly && (
          <Checkbox checked={forceOcr} onChange={(e) => setForceOcr(e.target.checked)}>
            强制 OCR（扫描件/图片型 PDF）
          </Checkbox>
        )}
      </Space>
    </Modal>
  );
}
