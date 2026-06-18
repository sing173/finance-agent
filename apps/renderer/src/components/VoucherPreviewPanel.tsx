import { useState, useCallback, useEffect, useMemo } from 'react';
import { Table, Tag, Button, Space, Alert, message, Dropdown, Popconfirm, Tooltip, Spin, Checkbox, Select } from 'antd';
import {
  WarningOutlined,
  ExportOutlined,
  SaveOutlined,
  ThunderboltOutlined,
  DownOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { SubjectPickerModal } from './SubjectPickerModal';
import type { SubjectItem, VoucherEntry, VoucherData } from '@shared/types';
import { isUnmatchedNonBank, flattenToRows, moveEntries, splitEntry, type TableRow } from '../hooks/voucher_utils';

interface VoucherPreviewPanelProps {
  vouchers: VoucherData[];
  subjects: SubjectItem[];
  onVouchersChange: (vouchers: VoucherData[]) => void;
  onSaveDraft: () => void;
  onExport: () => void;
  onCancel?: () => void;
  saveDisabled?: boolean;
  loading?: boolean;
}

const MATCH_TAGS: Record<string, { color: string; label: string }> = {
  rule: { color: 'blue', label: '规则' },
  history: { color: 'green', label: '历史' },
  manual: { color: 'orange', label: '手动' },
  unmatched: { color: 'red', label: '未匹配' },
  auto: { color: 'default', label: '自动' },
};

const BATCH_SUBJECTS = [
  { code: '5060203', name: '管理费用_物业管理费' },
  { code: '5060202', name: '管理费用_办公费' },
];

const TOTAL_COLUMNS = 9;

export function VoucherPreviewPanel({
  vouchers: propVouchers,
  subjects,
  onVouchersChange,
  onSaveDraft,
  onExport,
  onCancel,
  saveDisabled,
  loading = false,
}: VoucherPreviewPanelProps) {
  const [pickerVisible, setPickerVisible] = useState(false);
  const [editingEntry, setEditingEntry] = useState<{ vno: number; seq: number } | null>(null);
  const [editedVouchers, setEditedVouchers] = useState<VoucherData[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<Set<number>>(new Set());
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());

  useEffect(() => {
    setEditedVouchers(JSON.parse(JSON.stringify(propVouchers)));
    setExpandedKeys(new Set(propVouchers.map((v) => v.voucher_no)));
    setSelectedKeys(new Set());
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
              return { ...e, ...patch, is_manual: true, match_source: 'manual' as const };
            }),
          };
        });
        return next;
      });
    },
    [],
  );

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

  const handleBatchFill = useCallback(
    (subject: { code: string; name: string }) => {
      let count = 0;
      setEditedVouchers((prev) => {
        const next = prev.map((v) => ({
          ...v,
          entries: v.entries.map((e) => {
            if (isUnmatchedNonBank(e)) {
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

  useEffect(() => {
    if (editedVouchers.length > 0) {
      onVouchersChange(editedVouchers);
    }
  }, [editedVouchers, onVouchersChange]);

  const unmatchedCount = editedVouchers.reduce(
    (s, v) => s + v.entries.filter((e) => isUnmatchedNonBank(e)).length,
    0,
  );

  // Toggle expand/collapse for a voucher group
  const toggleExpand = useCallback((voucherNo: number) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(voucherNo)) next.delete(voucherNo);
      else next.add(voucherNo);
      return next;
    });
  }, []);

  // Selection helpers (bank entries excluded — not selectable)
  const entryKeys = useMemo(() => {
    const keys: string[] = [];
    for (const v of editedVouchers) {
      for (const e of v.entries) {
        if (e.direction === 'bank') continue;
        keys.push(`entry-${v.voucher_no}-${e.entry_seq}`);
      }
    }
    return keys;
  }, [editedVouchers]);

  const allSelected = entryKeys.length > 0 && entryKeys.every((k) => selectedKeys.has(k));

  const toggleSelectAll = useCallback(() => {
    if (allSelected) {
      setSelectedKeys(new Set());
    } else {
      setSelectedKeys(new Set(entryKeys));
    }
  }, [allSelected, entryKeys]);

  const toggleSelectEntry = useCallback((key: string) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const toggleSelectGroup = useCallback((voucherNo: number) => {
    const voucher = editedVouchers.find((v) => v.voucher_no === voucherNo);
    if (!voucher) return;
    const groupKeys = voucher.entries
      .filter((e) => e.direction !== 'bank')
      .map((e) => `entry-${voucherNo}-${e.entry_seq}`);
    const allInGroup = groupKeys.length > 0 && groupKeys.every((k) => selectedKeys.has(k));
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      for (const k of groupKeys) {
        if (allInGroup) next.delete(k);
        else next.add(k);
      }
      return next;
    });
  }, [editedVouchers, selectedKeys]);

  // Selected entries parsed for move target filtering
  const selectedEntryList = useMemo(() => {
    const list: { voucher_no: number; entry_seq: number }[] = [];
    for (const k of selectedKeys) {
      const parts = k.replace('entry-', '').split('-');
      list.push({ voucher_no: Number(parts[0]), entry_seq: Number(parts[1]) });
    }
    return list;
  }, [selectedKeys]);

  const sourceVoucherNos = useMemo(() => new Set(selectedEntryList.map((s) => s.voucher_no)), [selectedEntryList]);
  const targetOptions = editedVouchers.filter((v) => !sourceVoucherNos.has(v.voucher_no));

  const handleMove = useCallback((targetVoucherNo: number) => {
    setEditedVouchers((prev) => moveEntries(prev, selectedEntryList, targetVoucherNo) as VoucherData[]);
    setSelectedKeys(new Set());
    message.success(`已移动 ${selectedEntryList.length} 条分录`);
  }, [selectedEntryList]);

  // Build flattened rows
  const rows = useMemo(() => flattenToRows(editedVouchers), [editedVouchers]);

  // Filter rows: only show entry rows if their group is expanded
  const visibleRows = useMemo(() => {
    return rows.filter((r) => r.type === 'group' || expandedKeys.has(r.voucher_no));
  }, [rows, expandedKeys]);

  // Group row renderer — renders across all columns via colSpan
  const renderGroupRow = (row: Extract<TableRow, { type: 'group' }>) => {
    const voucher = editedVouchers.find((v) => v.voucher_no === row.voucher_no);
    const groupKeys = voucher?.entries.filter((e) => e.direction !== 'bank').map((e) => `entry-${row.voucher_no}-${e.entry_seq}`) || [];
    const groupAllSelected = groupKeys.length > 0 && groupKeys.every((k) => selectedKeys.has(k));
    const isExpanded = expandedKeys.has(row.voucher_no);

    return {
      children: (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Checkbox
            checked={groupAllSelected}
            indeterminate={!groupAllSelected && groupKeys.some((k) => selectedKeys.has(k))}
            onChange={(e) => { e.stopPropagation(); toggleSelectGroup(row.voucher_no); }}
          />
          <span
            onClick={() => toggleExpand(row.voucher_no)}
            style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}
          >
            {isExpanded ? <DownOutlined style={{ fontSize: 11 }} /> : <RightOutlined style={{ fontSize: 11 }} />}
          </span>
          <Tag color="processing">凭证 #{row.voucher_no}</Tag>
          <span>{row.date}</span>
          <span style={{ color: '#78716c' }}>{row.entryCount} 笔分录</span>
        </div>
      ),
      props: { colSpan: TOTAL_COLUMNS },
    };
  };

  const columns: any[] = [
    {
      title: (
        <Checkbox checked={allSelected} indeterminate={!allSelected && selectedKeys.size > 0} onChange={toggleSelectAll} />
      ),
      key: 'select',
      width: 40,
      render: (_: any, row: TableRow) => {
        if (row.type === 'group') return renderGroupRow(row).children;
        if (row.direction === 'bank') return null;
        return (
          <Checkbox
            checked={selectedKeys.has(row.key)}
            onChange={() => toggleSelectEntry(row.key)}
          />
        );
      },
      onCell: (row: TableRow) => {
        if (row.type === 'group') return { colSpan: TOTAL_COLUMNS };
        return {};
      },
    },
    {
      title: '序号', dataIndex: 'entry_seq', key: 'seq', width: 50,
      onCell: (row: TableRow) => row.type === 'group' ? { colSpan: 0 } : {},
    },
    {
      title: '日期', dataIndex: 'date', key: 'date', width: '10%' as any,
      onCell: (row: TableRow) => row.type === 'group' ? { colSpan: 0 } : {},
    },
    {
      title: '摘要', dataIndex: 'summary', key: 'summary', width: '22%' as any,
      ellipsis: { showTitle: false },
      render: (v: string) => (
        <Tooltip title={v} placement="topLeft"><span>{v}</span></Tooltip>
      ),
      onCell: (row: TableRow) => row.type === 'group' ? { colSpan: 0 } : {},
    },
    {
      title: '科目', key: 'subject', width: '20%' as any,
      ellipsis: { showTitle: false },
      render: (_: any, r: any) => {
        if (r.type === 'group') return null;
        const text = isUnmatchedNonBank(r) ? '点击选择科目' : `${r.subject_code} ${r.subject_name}`;
        const isUnmatched = isUnmatchedNonBank(r);
        return (
          <Tooltip title={isUnmatched ? '点击选择科目' : text} placement="topLeft">
            <span onClick={() => handleSubjectClick(r.voucher_no, r.entry_seq)} style={{ cursor: 'pointer' }}>
              {isUnmatched ? (
                <span style={{ color: 'red' }}><WarningOutlined /> 点击选择科目</span>
              ) : (
                <span>{text}</span>
              )}
            </span>
          </Tooltip>
        );
      },
      onCell: (row: TableRow) => row.type === 'group' ? { colSpan: 0 } : {},
    },
    {
      title: '借方', dataIndex: 'debit_amount', key: 'debit', width: '8%' as any,
      align: 'right' as const,
      render: (v: number | null) => (v != null ? v.toLocaleString() : ''),
      onCell: (row: TableRow) => row.type === 'group' ? { colSpan: 0 } : {},
    },
    {
      title: '贷方', dataIndex: 'credit_amount', key: 'credit', width: '8%' as any,
      align: 'right' as const,
      render: (v: number | null) => (v != null ? v.toLocaleString() : ''),
      onCell: (row: TableRow) => row.type === 'group' ? { colSpan: 0 } : {},
    },
    {
      title: '对方名', dataIndex: 'counterparty', key: 'counterparty', width: '12%' as any,
      ellipsis: { showTitle: false },
      render: (v: string) => (
        <Tooltip title={v || ''} placement="topLeft"><span>{v}</span></Tooltip>
      ),
      onCell: (row: TableRow) => row.type === 'group' ? { colSpan: 0 } : {},
    },
    {
      title: '来源', dataIndex: 'match_source', key: 'source', width: '6%' as any,
      render: (s: string) => {
        const t = MATCH_TAGS[s] || { color: 'default', label: s };
        return <Tag color={t.color}>{t.label}</Tag>;
      },
      onCell: (row: TableRow) => row.type === 'group' ? { colSpan: 0 } : {},
    },
  ];

  const selectedCount = selectedKeys.size;
  const isSingleSelect = selectedCount === 1;

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

      <Space
        style={{
          marginBottom: 16,
          position: 'sticky',
          top: 0,
          background: '#faf9f7',
          padding: '12px 0',
          zIndex: 10,
        }}
      >
        {unmatchedCount > 0 && (
          <Dropdown
            menu={{
              items: BATCH_SUBJECTS.map((s) => ({
                key: s.code,
                label: `${s.code} ${s.name}`,
                onClick: () => handleBatchFill(s),
              })),
            }}
          >
            <Button icon={<ThunderboltOutlined />}>批量填充</Button>
          </Dropdown>
        )}
        <Button type="default" icon={<SaveOutlined />} onClick={onSaveDraft} disabled={saveDisabled}>
          保存草稿
        </Button>
        <Popconfirm
          title="确认导出"
          description={
            unmatchedCount > 0
              ? `还有 ${unmatchedCount} 条分录未匹配科目，确认继续导出？`
              : '确认导出所有凭证？'
          }
          onConfirm={onExport}
          okText="确认导出"
          cancelText="取消"
        >
          <Button style={{ background: '#dc2626', color: '#fff', borderColor: '#dc2626' }} icon={<ExportOutlined />}>
            确认导出
          </Button>
        </Popconfirm>
        {onCancel && (
          <Button onClick={onCancel}>取消</Button>
        )}
      </Space>

      <Table
        dataSource={visibleRows}
        columns={columns}
        rowKey="key"
        pagination={false}
        size="small"
        bordered
        rowClassName={(row) => row.type === 'group' ? 'voucher-group-row' : ''}
      />

      {/* 浮动操作栏 */}
      {selectedCount > 0 && (
        <div
          style={{
            position: 'sticky',
            bottom: 0,
            background: '#ffffff',
            border: '1px solid #d6d3cd',
            borderRadius: 2,
            padding: '10px 16px',
            marginTop: 12,
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            zIndex: 10,
          }}
        >
          <span>已选 <strong>{selectedCount}</strong> 条分录</span>

          {targetOptions.length > 0 && (
            <Select
              showSearch
              placeholder="移动到..."
              style={{ width: 140 }}
              listHeight={480}
              filterOption={(input, option) =>
                String(option?.value).includes(input)
              }
              onChange={(val: number) => { handleMove(val); }}
              options={targetOptions.map((v) => ({
                value: v.voucher_no,
                label: `凭证 #${v.voucher_no}`,
              }))}
            />
          )}

          {isSingleSelect && (
            <Button onClick={() => {
              const sel = selectedEntryList[0];
              const voucher = editedVouchers.find((v) => v.voucher_no === sel.voucher_no);
              const entry = voucher?.entries.find((e) => e.entry_seq === sel.entry_seq);
              if (!entry || !voucher) return;

              const half = Math.round((entry.debit_amount || entry.credit_amount || 0) / 2);
              const newEntries = [
                { debit_amount: entry.debit_amount != null ? half : null, credit_amount: entry.credit_amount != null ? half : null },
                { debit_amount: entry.debit_amount != null ? (entry.debit_amount! - half) : null, credit_amount: entry.credit_amount != null ? (entry.credit_amount! - half) : null },
              ];
              setEditedVouchers((prev) => splitEntry(prev, sel.voucher_no, sel.entry_seq, newEntries) as VoucherData[]);
              setSelectedKeys(new Set());
              message.success('分录已拆分');
            }}>
              拆分
            </Button>
          )}

          <Button type="text" onClick={() => setSelectedKeys(new Set())}>取消选择</Button>
        </div>
      )}

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
