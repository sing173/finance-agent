import { useState, useCallback, useEffect } from 'react';
import { Card, Table, Tag, Button, Space, Alert, message, Dropdown, Popconfirm, Tooltip, Spin } from 'antd';
import {
  WarningOutlined,
  ExportOutlined,
  SaveOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
// SwapOutlined — 翻转列暂时隐藏
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
  match_source: string;
  original_summary: string;
  original_amount: number;
  is_manual: boolean;
}

export type { VoucherEntry };

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
  subjects: { code: string; name: string; category: string; direction: string; enabled: boolean }[];
  onSaveDraft: (entries: VoucherEntry[]) => void;
  onExport: (entries: VoucherEntry[]) => void;
  onCancel?: () => void;
  saveDisabled?: boolean;
  loading?: boolean;
  batchSubjects?: { code: string; name: string }[];
}

const MATCH_TAGS: Record<string, { color: string; label: string }> = {
  rule: { color: 'blue', label: '规则' },
  history: { color: 'green', label: '历史' },
  manual: { color: 'orange', label: '手动' },
  unmatched: { color: 'red', label: '未匹配' },
  auto: { color: 'default', label: '自动' },
};

export function VoucherPreviewPanel({
  vouchers: propVouchers,
  subjects,
  onSaveDraft,
  onExport,
  onCancel,
  saveDisabled,
  loading = false,
  batchSubjects = [],
}: VoucherPreviewPanelProps) {
  const [pickerVisible, setPickerVisible] = useState(false);
  const [editingEntry, setEditingEntry] = useState<{ vno: number; seq: number } | null>(null);

  // 内部可变副本
  const [editedVouchers, setEditedVouchers] = useState<VoucherData[]>([]);

  useEffect(() => {
    setEditedVouchers(JSON.parse(JSON.stringify(propVouchers)));
  }, [propVouchers]);

  const updateEntry = useCallback(
    (vno: number, seq: number, patch: Partial<VoucherEntry>) => {
      setEditedVouchers((prev) => {
        const next = prev.map((v) => {
          if (v.voucher_no !== vno) return v;
          return {
            ...v,
            entries: v.entries.map((e) => {
              if (e.entry_seq !== seq) return e;
              const subjectChanged = patch.subject_code !== undefined
                && patch.subject_code !== e.subject_code;
              return {
                ...e, ...patch,
                ...(subjectChanged ? { is_manual: true, match_source: 'manual' as const } : {}),
              };
            }),
          };
        });
        return next;
      });
    },
    [],
  );

  // Subject picker 选择 → 回填科目
  const handleSubjectSelect = useCallback(
    (subject: { code: string; name: string }) => {
      if (!editingEntry) return;
      updateEntry(editingEntry.vno, editingEntry.seq, {
        subject_code: subject.code,
        subject_name: subject.name,
      });
      setPickerVisible(false);
      setEditingEntry(null);
      message.success(`已设置科目: ${subject.code} ${subject.name}`);
    },
    [editingEntry, updateEntry],
  );

  const handleSubjectClick = useCallback((vno: number, seq: number) => {
    setEditingEntry({ vno, seq });
    setPickerVisible(true);
  }, []);

  
  // 批量填充：对所有未匹配分录应用兜底科目
  const handleBatchFill = useCallback(
    (subject: { code: string; name: string }) => {
      let count = 0;
      setEditedVouchers((prev) => {
        const next = prev.map((v) => ({
          ...v,
          entries: v.entries.map((e) => {
            if (e.match_source === 'unmatched' && e.direction !== 'bank') {
              count++;
              return {
                ...e,
                subject_code: subject.code,
                subject_name: subject.name,
                is_manual: true,
                match_source: 'manual' as const,
              };
            }
            return e;
          }),
        }));
        return next;
      });
      message.success(`批量填充完成: ${count} 条分录 → ${subject.name}`);
    },
    [],
  );

  // Return flattened entries for save/export
  const getFlatEntries = useCallback((): VoucherEntry[] => {
    const all: VoucherEntry[] = [];
    for (const vc of editedVouchers) {
      for (const e of vc.entries) {
        all.push(e);
      }
    }
    return all;
  }, [editedVouchers]);

  const unmatchedCount = editedVouchers.reduce(
    (s, v) => s + v.entries.filter((e) => e.match_source === 'unmatched' && e.direction !== 'bank').length,
    0,
  );

  const columns = [
    { title: '序号', dataIndex: 'entry_seq', key: 'seq', width: '6%' as any },
    { title: '日期', dataIndex: 'date', key: 'date', width: '10%' as any },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      width: '24%' as any,
      ellipsis: { showTitle: false },
      render: (v: string) => (
        <Tooltip title={v} placement="topLeft">
          <span>{v}</span>
        </Tooltip>
      ),
    },
    {
      title: '科目',
      key: 'subject',
      width: '22%' as any,
      ellipsis: { showTitle: false },
      render: (_: any, r: VoucherEntry) => {
        const text = r.match_source === 'unmatched' && r.direction !== 'bank'
          ? '点击选择科目'
          : `${r.subject_code} ${r.subject_name}`;
        const isUnmatched = r.match_source === 'unmatched' && r.direction !== 'bank';
        return (
          <Tooltip title={isUnmatched ? '点击选择科目' : text} placement="topLeft">
            <span onClick={() => handleSubjectClick(r.voucher_no, r.entry_seq)} style={{ cursor: 'pointer' }}>
              {isUnmatched ? (
                <span style={{ color: 'red' }}>
                  <WarningOutlined /> 点击选择科目
                </span>
              ) : (
                <span>{text}</span>
              )}
            </span>
          </Tooltip>
        );
      },
    },
    {
      title: '借方',
      dataIndex: 'debit_amount',
      key: 'debit',
      width: '10%' as any,
      align: 'right' as const,
      render: (v: number | null) => (v != null ? v.toLocaleString() : ''),
    },
    {
      title: '贷方',
      dataIndex: 'credit_amount',
      key: 'credit',
      width: '10%' as any,
      align: 'right' as const,
      render: (v: number | null) => (v != null ? v.toLocaleString() : ''),
    },
    {
      title: '对方名',
      dataIndex: 'counterparty',
      key: 'counterparty',
      width: '12%' as any,
      ellipsis: { showTitle: false },
      render: (v: string) => (
        <Tooltip title={v || ''} placement="topLeft">
          <span>{v}</span>
        </Tooltip>
      ),
    },
    {
      title: '来源',
      dataIndex: 'match_source',
      key: 'source',
      width: '6%' as any,
      render: (s: string) => {
        const t = MATCH_TAGS[s] || { color: 'default', label: s };
        return <Tag color={t.color}>{t.label}</Tag>;
      },
    },
  ];

  return (
    <Spin spinning={loading} tip="正在生成凭证...">
      {unmatchedCount > 0 && (
        <Alert
          message={`有 ${unmatchedCount} 条分录未匹配到对方科目，请点击科目列选择或使用批量填充`}
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {editedVouchers.map((v) => (
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
        {unmatchedCount > 0 && (
          <Dropdown
            menu={{
              items: batchSubjects.map((s) => ({
                key: s.code,
                label: `${s.code} ${s.name}`,
                onClick: () => handleBatchFill(s),
              })),
            }}
          >
            <Button icon={<ThunderboltOutlined />}>批量填充</Button>
          </Dropdown>
        )}
        <Button type="default" icon={<SaveOutlined />} onClick={() => onSaveDraft(getFlatEntries())} disabled={saveDisabled}>
          保存草稿
        </Button>
        <Popconfirm
          title="确认导出"
          description={
            unmatchedCount > 0
              ? `还有 ${unmatchedCount} 条分录未匹配科目，确认继续导出？`
              : '确认导出所有凭证？'
          }
          onConfirm={() => onExport(getFlatEntries())}
          okText="确认导出"
          cancelText="取消"
        >
          <Button type="primary" icon={<ExportOutlined />}>
            确认导出
          </Button>
        </Popconfirm>
        {onCancel && (
          <Button onClick={onCancel}>取消</Button>
        )}
      </Space>

      <SubjectPickerModal
        visible={pickerVisible}
        onClose={() => {
          setPickerVisible(false);
          setEditingEntry(null);
        }}
        onSelect={handleSubjectSelect}
        subjects={subjects}
      />
    </Spin>
  );
}