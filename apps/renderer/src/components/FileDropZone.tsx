import { useState, useCallback } from 'react';
import { Upload, message, Button } from 'antd';
import { InboxOutlined } from '@ant-design/icons';

const { Dragger } = Upload;

interface FileDropZoneProps {
  onFilesSelected: (files: File[]) => void;
}

export function FileDropZone({ onFilesSelected }: FileDropZoneProps) {
  const [files, setFiles] = useState<File[]>([]);

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      const droppedFiles = Array.from(e.dataTransfer.files);
      const validFiles = droppedFiles.filter(
        (f) =>
          f.name.endsWith('.pdf') ||
          f.name.endsWith('.xlsx') ||
          f.name.endsWith('.xls')
      );

      if (validFiles.length < droppedFiles.length) {
        message.warning('仅支持 PDF 和 Excel 文件');
      }

      const newFiles = [...files, ...validFiles];
      setFiles(newFiles);
      onFilesSelected(validFiles);
    },
    [files, onFilesSelected]
  );

  const handleRemove = (index: number) => {
    const newFiles = files.filter((_, i) => i !== index);
    setFiles(newFiles);
    onFilesSelected(newFiles);
  };

  return (
    <div
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
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
        拖拽文件到此处，或点击上传
      </p>
      <p style={{ color: '#999' }}>支持 PDF、Excel 格式</p>
      <Button type="primary" style={{ marginTop: 16 }}>
        选择文件
      </Button>

      {files.length > 0 && (
        <div style={{ marginTop: 24, textAlign: 'left' }}>
          <h4>已选文件：</h4>
          <ul style={{ paddingLeft: 20 }}>
            {files.map((f, i) => (
              <li key={i} style={{ marginBottom: 8 }}>
                <span>{f.name}</span>
                <span style={{ color: '#999', marginLeft: 8 }}>
                  ({(f.size / 1024).toFixed(1)} KB)
                </span>
                <Button
                  type="link"
                  danger
                  size="small"
                  onClick={() => handleRemove(i)}
                  style={{ marginLeft: 8 }}
                >
                  删除
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
