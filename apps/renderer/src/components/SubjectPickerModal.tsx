import { useState, useEffect, useCallback, useMemo, memo } from 'react';
import { Modal, Input, Select, Typography, Tag, Empty } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { FixedSizeList } from 'react-window';
import { useDebounce } from '../hooks/useDebounce';

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
    </div>
  );
});

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

  // 防抖搜索文本（150ms延迟）
  const debouncedSearchText = useDebounce(searchText, 150);

  // 同步外部 subjects 变化
  useEffect(() => {
    if (propSubjects) {
      setSubjects(propSubjects);
    }
  }, [propSubjects]);

  // 延迟加载：弹窗首次打开时自动加载科目数据
  useEffect(() => {
    if (visible && subjects.length === 0 && !propSubjects) {
      // 通过 window.electronAPI 加载科目
      (async () => {
        try {
          const r = await (window as any).electronAPI?.invoke('get_subjects_info', {});
          if (r?.success && r.subjects) {
            setSubjects(r.subjects);
          }
        } catch (err) {
          console.error('加载科目失败:', err);
        }
      })();
    }
  }, [visible, subjects.length, propSubjects]);

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
