import { useCallback, useState } from 'react';
import { message, Card } from 'antd';
import { InboxOutlined } from '@ant-design/icons';

interface FileDropZoneProps {
  onFilesSelected: (filePaths: string[]) => void;
}

export function FileDropZone({ onFilesSelected }: FileDropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleSelectFile = useCallback(async () => {
    try {
      const result = await window.electronAPI?.selectFile?.('all', true);
      if (result && Array.isArray(result)) {
        onFilesSelected(result);
      }
    } catch (error: any) {
      message.error('文件选择失败：' + error.message);
    }
  }, [onFilesSelected]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const files = Array.from(e.dataTransfer.files);
    const filePaths = files
      .map((f: File) => {
        try {
          return window.electronAPI?.getFilePath?.(f) || '';
        } catch {
          return '';
        }
      })
      .filter((p: string) => !!p);

    if (filePaths.length === 0) {
      message.warning('未能获取文件路径');
      return;
    }
    onFilesSelected(filePaths);
  }, [onFilesSelected]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = 'copy';
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  return (
    <Card
      title="上传交易流水文件"
      hoverable
      style={{
        height: 200,
        cursor: 'pointer',
        border: isDragOver ? '2px dashed #1e3a5f' : '2px dashed #d6d3cd',
        background: isDragOver ? '#e8eef5' : undefined,
        transition: 'border-color 0.2s, background 0.2s',
      }}
      styles={{
        body: {
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px 16px',
        },
      }}
      onClick={handleSelectFile}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      <InboxOutlined style={{ fontSize: 48, color: '#1e3a5f', marginBottom: 12 }} />
      <span style={{ fontSize: 15, fontWeight: 500, color: '#333' }}>
        点击或拖拽文件至此区域
      </span>
      <span style={{ fontSize: 13, color: '#999', marginTop: 4 }}>
        支持 PDF / CSV / Excel，可多选
      </span>
    </Card>
  );
}
