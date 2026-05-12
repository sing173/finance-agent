import { useCallback } from 'react';
import { message, Card } from 'antd';
import { InboxOutlined } from '@ant-design/icons';

interface FileDropZoneProps {
  onFileSelected: (filePath: string) => void;
}

export function FileDropZone({ onFileSelected }: FileDropZoneProps) {
  const handleSelectFile = useCallback(async () => {
    try {
      const filePath = await window.electronAPI?.selectFile?.('pdf');
      if (filePath) {
        onFileSelected(filePath);
        message.success(`已选择: ${filePath.split(/[/\\]/).pop()}`);
      }
    } catch (error: any) {
      message.error('文件选择失败：' + error.message);
    }
  }, [onFileSelected]);

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
        <span style={{ fontSize: 14 }}>点击此区域选择 PDF 银行流水文件</span>
      </div>
    </Card>
  );
}
