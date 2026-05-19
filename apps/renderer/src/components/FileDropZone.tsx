import { useCallback } from 'react';
import { message, Card } from 'antd';
import { InboxOutlined } from '@ant-design/icons';

interface FileDropZoneProps {
  onFilesSelected: (filePaths: string[]) => void;
}

export function FileDropZone({ onFilesSelected }: FileDropZoneProps) {
  const handleSelectFile = useCallback(async () => {
    try {
      // 支持 PDF、CSV、Excel 文件，允许多选
      const result = await window.electronAPI?.selectFile?.('all', true);
      if (result && Array.isArray(result)) {
        onFilesSelected(result);
      }
    } catch (error: any) {
      message.error('文件选择失败：' + error.message);
    }
  }, [onFilesSelected]);

  return (
    <Card
      title="上传交易流水文件"
      hoverable
      style={{ height: '100%', cursor: 'pointer' }}
      onClick={handleSelectFile}
    >
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 120,
        color: '#999',
      }}>
        <InboxOutlined style={{ fontSize: 40, color: '#1677ff', marginBottom: 12 }} />
        <span style={{ fontSize: 14 }}>点击此区域选择文件（PDF / CSV / Excel）</span>
      </div>
    </Card>
  );
}
