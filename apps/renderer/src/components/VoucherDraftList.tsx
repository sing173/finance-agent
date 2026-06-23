import { List, Button, Tag, Space, Popconfirm, Empty, Spin } from 'antd';
import { FolderOpenOutlined, DeleteOutlined } from '@ant-design/icons';

interface DraftItem {
  id: string;
  name: string;
  period: string;
  status: string;
  created_at: string;
  updated_at: string;
  entry_count: number;
}

interface VoucherDraftListProps {
  drafts: DraftItem[];
  onLoad: (draftId: string) => void;
  onDelete: (draftId: string) => void;
  loading: boolean;
}

export function VoucherDraftList({ drafts, onLoad, onDelete, loading }: VoucherDraftListProps) {
  return (
    <div>
      <h4>草稿列表</h4>

      <Spin spinning={loading}>
        {drafts.length === 0 ? (
          <Empty description="暂无草稿" />
        ) : (
          <List
            dataSource={drafts}
            renderItem={(item) => (
              <List.Item
                actions={[
                  <Button
                    key="load"
                    type="link"
                    icon={<FolderOpenOutlined />}
                    onClick={() => onLoad(item.id)}
                  >
                    加载
                  </Button>,
                  <Popconfirm
                    key="delete"
                    title="确认删除"
                    description={`删除草稿 ${item.name}？`}
                    onConfirm={() => onDelete(item.id)}
                    okText="删除"
                    cancelText="取消"
                  >
                    <Button type="link" danger icon={<DeleteOutlined />} />
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      {item.name}
                      {item.status === 'exported' && <Tag color="success">已导出</Tag>}
                      {item.status === 'draft' && <Tag color="primary">草稿</Tag>}
                    </Space>
                  }
                  description={
                    <span>
                      {item.period} · {item.entry_count} 条分录 · {item.updated_at?.slice(0, 10)}
                    </span>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Spin>
    </div>
  );
}