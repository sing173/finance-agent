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
      style={{
        height: '100%',
        cursor: 'pointer',
        border: '2px dashed #1677ff33',
        transition: 'border-color 0.2s',
      }}
      bodyStyle={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 140,
        padding: '24px 16px',
      }}
      onClick={handleSelectFile}
    >
      <InboxOutlined style={{ fontSize: 48, color: '#1677ff', marginBottom: 12 }} />
      <span style={{ fontSize: 15, fontWeight: 500, color: '#333' }}>
        点击此区域选择文件
      </span>
      <span style={{ fontSize: 13, color: '#999', marginTop: 4 }}>
        支持 PDF / CSV / Excel，可多选
      </span>
    </Card>
  );
}
