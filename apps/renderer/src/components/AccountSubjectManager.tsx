import { useState, useEffect, useCallback } from 'react';
import {
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
} from '@ant-design/icons';
import type { AccountEntry } from '@shared/types';
import { SubjectPickerModal } from './SubjectPickerModal';
import { useSubjects } from '../hooks/useSubjects';

interface AccountSubjectManagerProps {
  /** 可选：从外部传入账号列表（由父组件通过 account_registry.list 获取） */
  accounts?: AccountEntry[];
  /** 刷新列表的回调 */
  onRefresh?: () => void;
}


/**
 * AccountSubjectManager — 账户管理主组件
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
  const { subjects, reload: reloadSubjects } = useSubjects();
  const [bankOptions, setBankOptions] = useState<{ code: string; name: string }[]>([]);

  const [form] = Form.useForm();

  // bankCode 变化时自动填充 bank 中文名（从 detect_supported_banks 加载的列表查）
  const handleBankCodeChange = useCallback((bankCode: string) => {
    const found = bankOptions.find((b) => b.code === bankCode);
    form.setFieldsValue({
      bank: found?.name || bankCode,
    });
  }, [form, bankOptions]);

  // 加载银行列表（下拉选项，替代硬编码 BANK_CODE_MAP）
  const loadBankOptions = useCallback(async () => {
    try {
      const r = await (window as any).electronAPI?.detectSupportedBanks?.();
      if (r?.success && r.banks) {
        setBankOptions(r.banks);  // [{code, name}, ...]
      }
    } catch (err) {
      console.error('加载银行列表失败:', err);
    }
  }, []);

  // 初始加载：账号列表 + 银行选项
  useEffect(() => { loadBankOptions(); }, [loadBankOptions]);

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

  // 打开科目选择器时刷新科目列表
  useEffect(() => {
    if (subjectPickerVisible) {
      reloadSubjects();
    }
  }, [subjectPickerVisible, reloadSubjects]);

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
    // bankCode 通过 onChange 联动填充 bank，需先设 bankCode 再设 bank
    form.setFieldsValue({
      matchType: record.matchType,
      pattern: record.pattern,
      bankCode: record.bankCode,
      subjectCode: record.subjectCode,
      subjectName: record.subjectName,
    });
    // 手动触发 bankCode → bank 联动
    handleBankCodeChange(record.bankCode);
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
        matchType: values.matchType,
        pattern: values.pattern,
        bankCode: values.bankCode,
        bank: values.bank || bankOptions.find(b => b.code === values.bankCode)?.name || '',
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
    <>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'flex-end' }}>
        <Button style={{ background: '#dc2626', color: '#fff', borderColor: '#dc2626' }} icon={<PlusOutlined />} onClick={handleAdd}>
          新增
        </Button>
      </div>
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
            label="银行代码"
            name="bankCode"
            rules={[{ required: true, message: '请选择银行代码' }]}
          >
            <Select
              placeholder="选择银行"
              onChange={handleBankCodeChange}
              options={bankOptions.map((b) => ({
                label: `${b.name} (${b.code})`,
                value: b.code,
              }))}
            />
          </Form.Item>

          <Form.Item
            label="银行"
            name="bank"
            rules={[{ required: true, message: '银行名称必填' }]}
          >
            <Input disabled placeholder="由银行代码自动填充" />
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
        subjects={subjects}
      />
    </>
  );
}
