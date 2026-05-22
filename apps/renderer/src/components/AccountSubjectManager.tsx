import { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  message,
  Modal,
  Form,
  Select,
  Input,
  Popconfirm,
  Spin,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import type { AccountEntry } from '@shared/types';
import { SubjectPickerModal } from './SubjectPickerModal';

interface AccountSubjectManagerProps {
  /** 可选：从外部传入账号列表（由父组件通过 account_registry.list 获取） */
  accounts?: AccountEntry[];
  /** 刷新列表的回调 */
  onRefresh?: () => void;
}

/**
 * AccountSubjectManager — 账号-科目管理主组件
 *
 * 功能：
 * - 表格展示所有账号映射
 * - 新增 / 编辑 / 删除
 * - 科目选择器（SubjectPickerModal）
 *
 * 数据流：
 * 1. 组件挂载 → 调用 account_registry.list 获取初始数据
 * 2. 用户操作 → 调用 account_registry.add/update/delete
 * 3. 成功后 → 重新获取列表
 */
export function AccountSubjectManager({
  accounts: propAccounts,
  onRefresh,
}: AccountSubjectManagerProps) {
  const [accounts, setAccounts] = useState<AccountEntry[]>(propAccounts || []);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingEntry, setEditingEntry] = useState<AccountEntry | null>(null);
  const [subjectPickerVisible, setSubjectPickerVisible] = useState(false);
  const [selectedSubject, setSelectedSubject] = useState<{
    code: string;
    name: string;
  } | null>(null);

  const [form] = Form.useForm();

  // 从 bridge 加载账号列表
  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const result = await (window as any).electronAPI?.invoke(
        'account_registry.list',
        {}
      );
      if (result?.success) {
        setAccounts(result.accounts || []);
      }
    } catch (err: any) {
      message.error('加载账号列表失败：' + err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // 初始加载 + propAccounts 变化
  useEffect(() => {
    if (propAccounts) {
      setAccounts(propAccounts);
    } else {
      loadAccounts();
    }
  }, [propAccounts, loadAccounts]);

  // 新增按钮
  const handleAdd = () => {
    setEditingEntry(null);
    form.resetFields();
    setSelectedSubject(null);
    setModalVisible(true);
  };

  // 编辑按钮
  const handleEdit = (record: AccountEntry) => {
    setEditingEntry(record);
    form.setFieldsValue({
      matchType: record.matchType,
      pattern: record.pattern,
      bank: record.bank,
      bankCode: record.bankCode,
      subjectCode: record.subjectCode,
      subjectName: record.subjectName,
    });
    setSelectedSubject({
      code: record.subjectCode,
      name: record.subjectName,
    });
    setModalVisible(true);
  };

  // 删除确认
  const handleDelete = async (id: string) => {
    try {
      const result = await (window as any).electronAPI?.invoke(
        'account_registry.delete',
        { id }
      );
      if (result?.success) {
        message.success('删除成功');
        loadAccounts();
        onRefresh?.();
      } else {
        message.error(result?.error || '删除失败');
      }
    } catch (err: any) {
      message.error('删除失败：' + err.message);
    }
  };

  // 选择科目
  const handleSelectSubject = (subject: any) => {
    setSelectedSubject({ code: subject.code, name: subject.name });
    form.setFieldsValue({
      subjectCode: subject.code,
      subjectName: subject.name,
    });
  };

  // 表单提交（新增 / 更新）
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const params = {
        ...values,
        subjectCode: selectedSubject?.code || values.subjectCode,
        subjectName: selectedSubject?.name || values.subjectName,
      };

      if (editingEntry) {
        // 更新
        const result = await (window as any).electronAPI?.invoke(
          'account_registry.update',
          { id: editingEntry.id, ...params }
        );
        if (result?.success) {
          message.success('更新成功');
          setModalVisible(false);
          loadAccounts();
          onRefresh?.();
        } else {
          message.error(result?.error || '更新失败');
        }
      } else {
        // 新增
        const result = await (window as any).electronAPI?.invoke(
          'account_registry.add',
          params
        );
        if (result?.success) {
          message.success('新增成功');
          setModalVisible(false);
          loadAccounts();
          onRefresh?.();
        } else {
          message.error(result?.error || '新增失败');
        }
      }
    } catch (err: any) {
      if (err.errorFields) return; // 表单校验失败
      message.error('操作失败：' + err.message);
    }
  };

  // 表格列定义
  const columns = [
    {
      title: '匹配类型',
      dataIndex: 'matchType',
      key: 'matchType',
      width: 100,
      render: (type: string) => (
        <Tag color={type === 'exact' ? 'blue' : 'green'}>
          {type === 'exact' ? '精确' : '后缀'}
        </Tag>
      ),
    },
    {
      title: '匹配模式',
      dataIndex: 'pattern',
      key: 'pattern',
      width: 150,
    },
    {
      title: '银行',
      dataIndex: 'bank',
      key: 'bank',
      width: 120,
    },
    {
      title: '银行代码',
      dataIndex: 'bankCode',
      key: 'bankCode',
      width: 100,
      render: (code: string) => <Tag>{code}</Tag>,
    },
    {
      title: '科目代码',
      dataIndex: 'subjectCode',
      key: 'subjectCode',
      width: 120,
    },
    {
      title: '科目名称',
      dataIndex: 'subjectName',
      key: 'subjectName',
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: AccountEntry) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="确认删除"
            description={`删除账号映射 ${record.pattern}？`}
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <SettingOutlined />
          账号-科目管理
        </Space>
      }
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新增
        </Button>
      }
    >
      <Spin spinning={loading}>
        <Table
          dataSource={accounts}
          columns={columns}
          rowKey="id"
          size="small"
          pagination={{ pageSize: 10 }}
          scroll={{ x: 800 }}
        />
      </Spin>

      {/* 新增 / 编辑表单 */}
      <Modal
        title={editingEntry ? '编辑账号映射' : '新增账号映射'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSubmit}
        okText={editingEntry ? '更新' : '新增'}
        cancelText="取消"
        width={600}
      >
        <Form form={form} layout="vertical" initialValues={{ matchType: 'suffix' }}>
          <Form.Item
            label="匹配类型"
            name="matchType"
            rules={[{ required: true, message: '请选择匹配类型' }]}
          >
            <Select
              options={[
                { label: '后缀匹配', value: 'suffix' },
                { label: '精确匹配', value: 'exact' },
              ]}
            />
          </Form.Item>

          <Form.Item
            label="匹配模式"
            name="pattern"
            rules={[{ required: true, message: '请输入匹配模式' }]}
          >
            <Input placeholder="账号后缀或完整账号" />
          </Form.Item>

          <Form.Item
            label="银行"
            name="bank"
            rules={[{ required: true, message: '请输入银行名称' }]}
          >
            <Input placeholder="如：工商银行" />
          </Form.Item>

          <Form.Item
            label="银行代码"
            name="bankCode"
            rules={[{ required: true, message: '请输入银行代码' }]}
          >
            <Select
              placeholder="选择银行"
              options={[
                { label: '工商银行 (ICBC)', value: 'ICBC' },
                { label: '招商银行 (CMB)', value: 'CMB' },
                { label: '广发银行 (GFB)', value: 'GFB' },
              ]}
            />
          </Form.Item>

          <Form.Item label="科目" required>
            <div style={{ display: 'flex', gap: 8 }}>
              <Input
                value={selectedSubject?.code || ''}
                placeholder="科目代码"
                disabled
                style={{ width: 120 }}
              />
              <Input
                value={selectedSubject?.name || ''}
                placeholder="科目名称"
                disabled
                style={{ flex: 1 }}
              />
              <Button onClick={() => setSubjectPickerVisible(true)}>
                选择科目
              </Button>
            </div>
            <Form.Item name="subjectCode" hidden>
              <Input />
            </Form.Item>
            <Form.Item name="subjectName" hidden>
              <Input />
            </Form.Item>
          </Form.Item>
        </Form>
      </Modal>

      {/* 科目选择弹窗 */}
      <SubjectPickerModal
        visible={subjectPickerVisible}
        onClose={() => setSubjectPickerVisible(false)}
        onSelect={handleSelectSubject}
      />
    </Card>
  );
}
