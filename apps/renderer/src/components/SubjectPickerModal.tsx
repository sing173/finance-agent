import { useState, useCallback, useMemo, memo } from 'react';
import { Modal, Input, Select, Typography, Tag, Empty, Button, Form, Switch, message } from 'antd';
import { SearchOutlined, PlusOutlined } from '@ant-design/icons';
import { FixedSizeList } from 'react-window';
import { useDebounce } from '../hooks/useDebounce';
import { useSubjects } from '../hooks/useSubjects';
import type { SubjectItem } from '@shared/types';

const { Text } = Typography;

const LIST_ITEM_HEIGHT = 64; // 每行固定高度 px

interface RowData {
  data: SubjectItem[];
  onSelect: (subject: SubjectItem) => void;
}

// Row 组件：使用 React.memo 避免不必要的重渲染
const Row = memo(function Row({
  index,
  style,
  data,
}: {
  index: number;
  style: React.CSSProperties;
  data: RowData;
}) {
  const item = data.data[index];

  return (
    <div
      style={{
        ...style,
        padding: '8px 12px',
        cursor: 'pointer',
        borderBottom: '1px solid #f0f0f0',
        display: 'flex',
        alignItems: 'center',
        boxSizing: 'border-box',
      }}
      onClick={() => data.onSelect(item)}
      className="subject-picker-item"
    >
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Text strong>{item.code}</Text>
          <Text>{item.name}</Text>
          {item.is_cash && <Tag color="success">现金</Tag>}
        </div>
        {item.full_name && item.full_name !== item.name && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {item.full_name}
          </Text>
        )}
        {item.category && (
          <Tag style={{ marginLeft: 8 }}>{item.category}</Tag>
        )}
      </div>
      <Text type="secondary" style={{ fontSize: 12 }}>
        {item.direction === '借' ? '借' : '贷'}
      </Text>
    </div>
  );
});

interface SubjectPickerModalProps {
  visible: boolean;
  onClose: () => void;
  onSelect: (subject: SubjectItem) => void;
  subjects?: SubjectItem[];
}

/**
 * SubjectPickerModal — 科目选择弹窗
 *
 * 支持：
 * - 关键字搜索（科目代码/名称）
 * - 分类筛选（category）
 * - 点击选中 → 回调 onSelect
 *
 * 数据源由父组件传入（get_subjects_info 结果），避免内部调用 IPC。
 */
export function SubjectPickerModal({
  visible,
  onClose,
  onSelect,
  subjects: propSubjects,
}: SubjectPickerModalProps) {
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [adding, setAdding] = useState(false);
  const [addForm] = Form.useForm();

  // 防抖搜索文本（150ms延迟）
  const debouncedSearchText = useDebounce(searchText, 150);

  // 科目数据：propSubjects 优先，否则自动 IPC 加载
  const { subjects, reload } = useSubjects(propSubjects);

  // 提取所有分类（useMemo缓存）
  const categories = useMemo(
    () => Array.from(new Set(subjects.map((s) => s.category).filter(Boolean))),
    [subjects]
  );

  // 过滤逻辑（useMemo缓存，使用防抖搜索文本）
  const filteredList = useMemo(() => {
    let result = subjects.filter((s) => s.enabled !== false);

    // 分类筛选
    if (categoryFilter) {
      result = result.filter((s) => s.category === categoryFilter);
    }

    // 关键字搜索（使用防抖文本 + 预计算小写）
    if (debouncedSearchText.trim()) {
      const text = debouncedSearchText.toLowerCase();
      result = result.filter(
        (s) =>
          s.code.toLowerCase().includes(text) ||
          s.name.toLowerCase().includes(text) ||
          (s.full_name && s.full_name.toLowerCase().includes(text))
      );
    }

    return result;
  }, [subjects, categoryFilter, debouncedSearchText]);

  const handleSelect = useCallback(
    (subject: SubjectItem) => {
      onSelect(subject);
      onClose();
    },
    [onSelect, onClose]
  );

  const handleClose = useCallback(() => {
    setSearchText('');
    setCategoryFilter('');
    setShowAddForm(false);
    addForm.resetFields();
    onClose();
  }, [onClose, addForm]);

  const handleAddSubject = useCallback(async () => {
    try {
      const values = await addForm.validateFields();
      setAdding(true);
      const r = await (window as any).electronAPI?.invoke('add_subject', {
        code: values.code.trim(),
        name: values.name.trim(),
        full_name: values.full_name?.trim() || values.name.trim(),
        category: values.category || '',
        direction: values.direction || '借',
        is_cash: values.is_cash || false,
        enabled: true,
      });
      if (r?.success) {
        message.success('科目新增成功');
        addForm.resetFields();
        setShowAddForm(false);
        reload();
      } else {
        message.error(r?.error || '新增失败');
      }
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error('新增失败: ' + (err?.message || String(err)));
    } finally {
      setAdding(false);
    }
  }, [addForm, reload]);

  return (
    <Modal
      title="选择会计科目"
      open={visible}
      onCancel={handleClose}
      footer={null}
      width={600}
      destroyOnClose
    >
      {/* 新增科目入口 */}
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'flex-end' }}>
        {!showAddForm ? (
          <Button
            type="dashed"
            icon={<PlusOutlined />}
            onClick={() => setShowAddForm(true)}
          >
            新增科目
          </Button>
        ) : (
          <Button onClick={() => { setShowAddForm(false); addForm.resetFields(); }}>
            取消新增
          </Button>
        )}
      </div>

      {/* 新增科目表单 */}
      {showAddForm && (
        <div style={{
          marginBottom: 16,
          padding: 12,
          border: '1px solid #d9d9d9',
          borderRadius: 6,
          background: '#fafafa',
        }}>
          <Form form={addForm} layout="inline" size="small">
            <Form.Item
              name="code"
              rules={[{ required: true, message: '必填' }]}
              style={{ marginBottom: 8 }}
            >
              <Input placeholder="科目代码" style={{ width: 100 }} />
            </Form.Item>
            <Form.Item
              name="name"
              rules={[{ required: true, message: '必填' }]}
              style={{ marginBottom: 8 }}
            >
              <Input placeholder="科目名称" style={{ width: 140 }} />
            </Form.Item>
            <Form.Item name="full_name" style={{ marginBottom: 8 }}>
              <Input placeholder="完整名称（可选）" style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="category" style={{ marginBottom: 8 }}>
              <Input placeholder="类别（可选）" style={{ width: 100 }} />
            </Form.Item>
            <Form.Item name="direction" initialValue="借" style={{ marginBottom: 8 }}>
              <Select style={{ width: 70 }}>
                <Select.Option value="借">借</Select.Option>
                <Select.Option value="贷">贷</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="is_cash" valuePropName="checked" style={{ marginBottom: 8 }}>
              <Switch checkedChildren="现金" unCheckedChildren="非现金" />
            </Form.Item>
            <Form.Item style={{ marginBottom: 8 }}>
              <Button
                type="primary"
                loading={adding}
                onClick={handleAddSubject}
              >
                确认新增
              </Button>
            </Form.Item>
          </Form>
        </div>
      )}

      {/* 搜索 + 筛选 */}
      <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
        <Input
          placeholder="搜索科目代码/名称"
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
          style={{ flex: 1 }}
        />
        <Select
          placeholder="分类"
          value={categoryFilter || undefined}
          onChange={setCategoryFilter}
          allowClear
          style={{ width: 150 }}
          options={categories.map((c) => ({ label: c, value: c }))}
        />
      </div>

      {/* 科目列表（虚拟滚动） */}
      {filteredList.length === 0 ? (
        <Empty description="无匹配科目" />
      ) : (
        <FixedSizeList
          height={400}
          itemCount={filteredList.length}
          itemSize={LIST_ITEM_HEIGHT}
          itemData={{ data: filteredList, onSelect: handleSelect }}
          width="100%"
          style={{ border: '2px solid #1890ff' }} // 调试用边框
        >
          {Row}
        </FixedSizeList>
      )}
    </Modal>
  );
}
