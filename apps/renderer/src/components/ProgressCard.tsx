import { Card, Typography, Space } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface ProgressCardProps {
  /** Current file being parsed */
  currentFile?: string;
  /** 1-based current index */
  currentIndex?: number;
  /** Total files to parse */
  totalFiles?: number;
  /** Parsing status text */
  status?: string;
}

export function ProgressCard({
  currentFile,
  currentIndex = 0,
  totalFiles = 0,
  status = '正在解析',
}: ProgressCardProps) {
  return (
    <Card>
      <Space>
        <LoadingOutlined />
        <Text type="secondary">{status}</Text>
        {currentFile && (
          <>
            <Text type="secondary">|</Text>
            <Text ellipsis style={{ maxWidth: 300 }}>{currentFile}</Text>
          </>
        )}
        {totalFiles > 0 && (
          <>
            <Text type="secondary">|</Text>
            <Text>{currentIndex}/{totalFiles}</Text>
          </>
        )}
      </Space>
    </Card>
  );
}
