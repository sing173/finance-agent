import { useState, useEffect, useCallback } from 'react';
import { Modal, Input, Select, List, Typography, Tag, Empty } from 'antd';
import { SearchOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface SubjectItem {
  code: string;
  name: string;
  category: string;
  direction: string;
  is_cash?: boolean;
  enabled: boolean;
  full_name?: string;
}

interface SubjectPickerModalProps {
  visible: boolean;
  onClose: () => void;
  onSelect: (subject: SubjectItem) => void;
  subjects?: SubjectItem[];
  loading?: boolean;
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
  const [subjects, setSubjects] = useState<SubjectItem[]>(propSubjects || []);
  const [filtered, setFiltered] = useState<SubjectItem[]>([]);

  // 同步外部 subjects 变化
  useEffect(() => {
    if (propSubjects) {
      setSubjects(propSubjects);
    }
  }, [propSubjects]);

  // 提取所有分类
  const categories = Array.from(new Set(subjects.map((s) => s.category).filter(Boolean)));

  // 过滤逻辑
  useEffect(() => {
    let result = subjects;

    // 分类筛选
    if (categoryFilter) {
      result = result.filter((s) => s.category === categoryFilter);
    }

    // 关键字搜索
    if (searchText.trim()) {
      const text = searchText.toLowerCase();
      result = result.filter(
        (s) =>
          s.code.toLowerCase().includes(text) ||
          s.name.toLowerCase().includes(text) ||
          (s.full_name && s.full_name.toLowerCase().includes(text))
      );
    }

    // 只显示启用的科目
    result = result.filter((s) => s.enabled !== false);

    setFiltered(result);
  }, [subjects, searchText, categoryFilter]);

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
    onClose();
  }, [onClose]);

  return (
    <Modal
      title="选择会计科目"
      open={visible}
      onCancel={handleClose}
      footer={null}
      width={600}
      destroyOnClose
    >
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

      {/* 科目列表 */}
      <div style={{ maxHeight: 400, overflowY: 'auto' }}>
        {filtered.length === 0 ? (
          <Empty description="无匹配科目" />
        ) : (
          <List
            dataSource={filtered}
            renderItem={(item) => (
              <List.Item
                key={item.code}
                onClick={() => handleSelect(item)}
                style={{ cursor: 'pointer', padding: '8px 12px' }}
                className="subject-picker-item"
              >
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Text strong>{item.code}</Text>
                    <Text>{item.name}</Text>
                    {item.is_cash && <Tag color="green">现金</Tag>}
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
              </List.Item>
            )}
          />
        )}
      </div>
    </Modal>
  );
}
