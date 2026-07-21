import { useState, useCallback, useMemo, useEffect } from 'react';
import {
  Modal, Button, Table, Input, Select, Form, Switch, message,
  Space, Tag, Popconfirm,
} from 'antd';
import { PlusOutlined, UploadOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useDebounce } from '../hooks/useDebounce';
import { useSubjects } from '../hooks/useSubjects';
import type { SubjectItem } from '@shared/types';

interface SubjectManagerModalProps {
  visible: boolean;
  onClose: () => void;
}

export function SubjectManagerModal({ visible, onClose }: SubjectManagerModalProps) {
  const { subjects, loading, reload } = useSubjects();
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [formVisible, setFormVisible] = useState(false);
  const [editing, setEditing] = useState<SubjectItem | null>(null);
  const [importing, setImporting] = useState(false);
  const [form] = Form.useForm();

  // 打开弹窗时刷新科目列表，避免 mount 时 db.health 尚未完成的竞态
  useEffect(() => {
    if (visible) {
      reload();
    }
  }, [visible, reload]);

  const debouncedSearch = useDebounce(searchText, 200);

  const categories = useMemo(
    () => Array.from(new Set(subjects.map((s) => s.category).filter(Boolean))),
    [subjects],
  );

  const filtered = useMemo(() => {
    let list = subjects.filter((s) => s.enabled !== false);
    if (categoryFilter) {
      list = list.filter((s) => s.category === categoryFilter);
    }
    if (debouncedSearch.trim()) {
      const q = debouncedSearch.toLowerCase();
      list = list.filter(
        (s) =>
          s.code.toLowerCase().includes(q) ||
          s.name.toLowerCase().includes(q) ||
          (s.full_name || '').toLowerCase().includes(q),
      );
    }
    return list;
  }, [subjects, categoryFilter, debouncedSearch]);

  const openAdd = useCallback(() => {
    setEditing(null);
    form.resetFields();
    setFormVisible(true);
  }, [form]);

  const openEdit = useCallback((record: SubjectItem) => {
    setEditing(record);
    form.setFieldsValue({
      code: record.code,
      name: record.name,
      full_name: record.full_name,
      category: record.category,
      direction: record.direction,
      aux_category: record.aux_category || '',
      aux_category_name: record.aux_category_name || '',
      is_cash: record.is_cash,
      enabled: record.enabled,
    });
    setFormVisible(true);
  }, [form]);

  const handleSubmit = useCallback(async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        const r = await (window as any).electronAPI?.invoke('update_subject', {
          code: editing.code,
          ...values,
        });
        if (r?.success) {
          message.success('更新成功');
          setFormVisible(false);
          reload();
        } else {
          message.error(r?.error || '更新失败');
        }
      } else {
        const r = await (window as any).electronAPI?.invoke('add_subject', values);
        if (r?.success) {
          message.success('新增成功');
          setFormVisible(false);
          reload();
        } else {
          message.error(r?.error || '新增失败');
        }
      }
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error('操作失败: ' + (err?.message || String(err)));
    }
  }, [editing, form, reload]);

  const handleDelete = useCallback(async (code: string) => {
    try {
      const r = await (window as any).electronAPI?.invoke('delete_subject', { code });
      if (r?.success) {
        message.success('删除成功');
        reload();
      } else {
        message.error(r?.error || '删除失败');
      }
    } catch (err: any) {
      message.error('删除失败：' + err.message);
    }
  }, [reload]);

  const handleImport = useCallback(async () => {
    try {
      const filePath = await (window as any).electronAPI?.selectFile?.('xlsx');
      if (!filePath) return;
      setImporting(true);
      const r = await (window as any).electronAPI?.invoke('import_subjects', { xlsx_path: filePath });
      if (r?.success) {
        message.success(`成功导入 ${r.count} 条科目`);
        reload();
      } else {
        message.error(r?.error || '导入失败');
      }
    } catch (err: any) {
      message.error('导入失败：' + err.message);
    } finally {
      setImporting(false);
    }
  }, [reload]);

  const columns = useMemo(() => [
    { title: '代码', dataIndex: 'code', key: 'code', width: 100 },
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    { title: '类别', dataIndex: 'category', key: 'category', width: 100, render: (c: string) => c ? <Tag>{c}</Tag> : null },
    { title: '方向', dataIndex: 'direction', key: 'direction', width: 80 },
    { title: '辅助核算', dataIndex: 'aux_category', key: 'aux_category', width: 90 },
    { title: '辅助核算名称', dataIndex: 'aux_category_name', key: 'aux_category_name', width: 120 },
    {
      title: '现金', dataIndex: 'is_cash', key: 'is_cash', width: 80,
      render: (v: boolean) => (v ? <Tag color="success">是</Tag> : '否'),
    },
    {
      title: '启用', dataIndex: 'enabled', key: 'enabled', width: 80,
      render: (v: boolean) => (v ? <Tag color="success">是</Tag> : <Tag>否</Tag>),
    },
    {
      title: '操作', key: 'action', width: 140,
      render: (_: any, record: SubjectItem) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm
            title="确认删除"
            description={`删除科目 ${record.code}（${record.name}）？`}
            onConfirm={() => handleDelete(record.code)}
            okText="删除"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ], [openEdit, handleDelete]);

  return (
    <Modal
      title="科目管理"
      open={visible}
      onCancel={onClose}
      footer={null}
      width={1100}
      destroyOnClose
    >
      <div style={{ marginBottom: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Input
          placeholder="搜索科目代码 / 名称"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
          style={{ flex: 1, minWidth: 180 }}
        />
        <Select
          placeholder="分类筛选"
          value={categoryFilter || undefined}
          onChange={setCategoryFilter}
          allowClear
          style={{ width: 150 }}
          options={categories.map((c) => ({ label: c, value: c }))}
        />
        <Button icon={<UploadOutlined />} loading={importing} onClick={handleImport}>
          导入
        </Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
          新增科目
        </Button>
      </div>

      <Table
        dataSource={filtered}
        columns={columns}
        rowKey="code"
        size="small"
        pagination={{ pageSize: 15 }}
        scroll={{ x: 980 }}
        loading={loading}
      />

      <Modal
        title={editing ? '编辑科目' : '新增科目'}
        open={formVisible}
        onCancel={() => setFormVisible(false)}
        onOk={handleSubmit}
        okText={editing ? '更新' : '新增'}
        cancelText="取消"
        width={520}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="code" label="科目代码" rules={[{ required: true, message: '必填' }]}>
            <Input disabled={!!editing} placeholder="如 1001" />
          </Form.Item>
          <Form.Item name="name" label="科目名称" rules={[{ required: true, message: '必填' }]}>
            <Input placeholder="如 库存现金" />
          </Form.Item>
          <Form.Item name="full_name" label="完整名称">
            <Input placeholder="可选" />
          </Form.Item>
          <Form.Item name="category" label="类别">
            <Input placeholder="如 流动资产" />
          </Form.Item>
          <Form.Item name="direction" label="方向" initialValue="借">
            <Select style={{ width: 100 }}>
              <Select.Option value="借">借</Select.Option>
              <Select.Option value="贷">贷</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="aux_category" label="辅助核算类别">
            <Input placeholder="如 04 / 供应商" />
          </Form.Item>
          <Form.Item name="aux_category_name" label="辅助核算名称">
            <Input placeholder="如 公共部门" />
          </Form.Item>
          <Form.Item name="is_cash" label="现金科目" valuePropName="checked">
            <Switch checkedChildren="是" unCheckedChildren="否" />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked" initialValue>
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>
    </Modal>
  );
}
