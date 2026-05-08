import { useCallback } from 'react';
import { message, Button } from 'antd';
import { InboxOutlined } from '@ant-design/icons';

interface FileDropZoneProps {
  onFileSelected: (filePath: string) => void;
}

export function FileDropZone({ onFileSelected }: FileDropZoneProps) {
  const handleSelectFile = useCallback(async () => {
    try {
      // 通过 Electron dialog 选择文件，返回绝对路径
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
    <div
      style={{
        border: '2px dashed #d9d9d9',
        borderRadius: '8px',
        padding: '40px 24px',
        textAlign: 'center',
        backgroundColor: '#fafafa',
        transition: 'border-color 0.3s',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = '#1677ff';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = '#d9d9d9';
      }}
    >
      <InboxOutlined style={{ fontSize: 48, color: '#1677ff', marginBottom: 16 }} />
      <p style={{ fontSize: 16, color: '#666' }}>
        点击选择 PDF 银行流水文件
      </p>
      <p style={{ color: '#999' }}>支持 PDF、Excel 格式</p>
      <Button
        type="primary"
        style={{ marginTop: 16 }}
        onClick={handleSelectFile}
      >
        选择文件
      </Button>
    </div>
  );
}
