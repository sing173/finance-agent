import { useState, useCallback } from 'react';
import { Card, Table, Tag, Button, Space, Alert, message } from 'antd';
import { WarningOutlined, ExportOutlined } from '@ant-design/icons';
import { SubjectPickerModal } from './SubjectPickerModal';

interface VoucherEntry {
  entry_seq: number;
  voucher_no: number;
  date: string;
  summary: string;
  subject_code: string;
  subject_name: string;
  debit_amount: number | null;
  credit_amount: number | null;
  direction: string;
  counterparty: string;
  match_source: 'rule' | 'history' | 'manual' | 'unmatched';
  original_summary: string;
  original_amount: number;
  is_manual: boolean;
}

interface VoucherData {
  voucher_no: number;
  date: string;
  direction: string;
  bank_subject_code: string;
  counterpart_subject_code: string;
  entries: VoucherEntry[];
}

interface VoucherPreviewPanelProps {
  vouchers: VoucherData[];
  onExport: () => void;
}

const MATCH_TAGS: Record<string, { color: string; label: string }> = {
  rule: { color: 'blue', label: '规则' },
  history: { color: 'green', label: '历史' },
  manual: { color: 'orange', label: '手动' },
  unmatched: { color: 'red', label: '未匹配' },
};

export function VoucherPreviewPanel({ vouchers, onExport }: VoucherPreviewPanelProps) {
  const [pickerVisible, setPickerVisible] = useState(false);
  const [editingEntry, setEditingEntry] = useState<{ vno: number; seq: number } | null>(null);

  const unmatchedCount = vouchers.reduce(
    (s, v) => s + v.entries.filter(e => e.match_source === 'unmatched' && e.direction !== 'bank').length,
    0,
  );

  const handleSubjectClick = useCallback((vno: number, seq: number) => {
    setEditingEntry({ vno, seq });
    setPickerVisible(true);
  }, []);

  const handleSubjectSelect = useCallback((_subject: any) => {
    setPickerVisible(false);
    message.info('科目已选择（预览面板暂不支持实时更新，请保存草稿后刷新）');
  }, []);

  const columns = [
    {
      title: '序号',
      dataIndex: 'entry_seq',
      key: 'seq',
      width: 50,
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
    },
    {
      title: '科目',
      key: 'subject',
      render: (_: any, r: VoucherEntry) => (
        <span onClick={() => handleSubjectClick(r.voucher_no, r.entry_seq)} style={{ cursor: 'pointer' }}>
          {r.match_source === 'unmatched' && r.direction !== 'bank' ? (
            <span style={{ color: 'red' }}>
              <WarningOutlined /> 点击选择科目
            </span>
          ) : (
            <span>
              {r.subject_code} {r.subject_name}
            </span>
          )}
        </span>
      ),
    },
    {
      title: '借方',
      dataIndex: 'debit_amount',
      key: 'debit',
      width: 100,
      render: (v: number | null) => v != null ? v.toLocaleString() : '',
    },
    {
      title: '贷方',
      dataIndex: 'credit_amount',
      key: 'credit',
      width: 100,
      render: (v: number | null) => v != null ? v.toLocaleString() : '',
    },
    {
      title: '来源',
      dataIndex: 'match_source',
      key: 'source',
      width: 80,
      render: (s: string) => {
        const t = MATCH_TAGS[s] || { color: 'default', label: s };
        return <Tag color={t.color}>{t.label}</Tag>;
      },
    },
  ];

  return (
    <div>
      <h3>凭证预览</h3>

      {unmatchedCount > 0 && (
        <Alert
          message={`有 ${unmatchedCount} 条分录未匹配到对方科目`}
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {vouchers.map((v) => (
        <Card
          key={v.voucher_no}
          title={`凭证 #${v.voucher_no} — ${v.date}`}
          size="small"
          style={{ marginBottom: 12 }}
        >
          <Table
            dataSource={v.entries}
            columns={columns}
            rowKey="entry_seq"
            pagination={false}
            size="small"
          />
        </Card>
      ))}

      <Space style={{ marginTop: 16 }}>
        <Button type="primary" icon={<ExportOutlined />} onClick={onExport}>
          确认导出
        </Button>
      </Space>

      <SubjectPickerModal
        visible={pickerVisible}
        onClose={() => setPickerVisible(false)}
        onSelect={handleSubjectSelect}
      />
    </div>
  );
}