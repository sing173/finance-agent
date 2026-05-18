import { useState, useEffect } from 'react';
import { Button, message, Tooltip, Space, Tag } from 'antd';
import { Typography } from 'antd';
const { Text } = Typography;
import { PlusOutlined, CloseOutlined, DeleteOutlined } from '@ant-design/icons';

interface SelectedFile {
  path: string;
  name: string;
  status: 'pending' | 'detected' | 'failed';
  bank: string;
  docType: string;
}

interface DetectResult {
  file_path: string;
  bank: string;
  doc_type: string;
  status: 'ok' | 'failed';
}

interface BatchFileSelectorProps {
  files: SelectedFile[];
  detected: Record<string, DetectResult | null>;
  onFilesChange: (files: SelectedFile[]) => void;
  onDetect: (filePaths: string[]) => void;
}

export function BatchFileSelector({
  files,
  detected,
  onFilesChange,
  onDetect,
}: BatchFileSelectorProps) {
  const [maxFiles, setMaxFiles] = useState(5);

  // 加载 batch_config.json
  useEffect(() => {
    fetch('/batch_config.json')
      .then((r) => r.json())
      .then((data) => setMaxFiles(data.maxBatchFiles || 5))
      .catch(() => setMaxFiles(5));
  }, []);

  const atLimit = files.length >= maxFiles;

  const handleAddFiles = async () => {
    try {
      const filePaths = await (window as any).electronAPI?.selectFile?.('pdf');
      if (!filePaths) return;

      const newFiles: SelectedFile[] = (filePaths as string[]).map((fp: string) => ({
        path: fp,
        name: fp.split(/[/\\]/).pop() || fp,
        status: 'pending' as const,
        bank: '',
        docType: '',
      }));

      const merged = [...files, ...newFiles];
      if (merged.length > maxFiles) {
        message.warning(`最多只能添加 ${maxFiles} 个文件`);
        return;
      }
      onFilesChange(merged);
    } catch (err: any) {
      message.error('文件选择失败：' + err.message);
    }
  };

  const handleRemove = (path: string) => {
    onFilesChange(files.filter((f) => f.path !== path));
    // 也清理 detected 中对应的条目
    const newDetected = { ...detected };
    delete newDetected[path];
    onFilesChange(files.filter((f) => f.path !== path));
  };

  const handleClear = () => {
    onFilesChange([]);
  };

  const handleDetect = () => {
    if (files.length === 0) return;
    onDetect(files.map((f) => f.path));
  };

  const getStatusLabel = (file: SelectedFile) => {
    const d = detected[file.path];
    if (!d) return file.status === 'pending' ? '待检测' : '—';
    if (d.status === 'ok') return `${d.bank} · ${d.doc_type}`;
    return '无法识别';
  };

  const isDetected = (file: SelectedFile) => !!detected[file.path];

  return (
    <div style={{ marginBottom: 16 }}>
      <Space style={{ marginBottom: 12 }}>
        <Tooltip title={atLimit ? `最多 ${maxFiles} 个文件` : ''}>
          <Button
            icon={<PlusOutlined />}
            onClick={handleAddFiles}
            disabled={atLimit}
          >
            添加文件
          </Button>
        </Tooltip>
        {files.length > 0 && (
          <>
            <Button
              type="primary"
              onClick={handleDetect}
              disabled={!files.some((f) => !isDetected(f))}
            >
              识别文件
            </Button>
            <Button
              icon={<CloseOutlined />}
              onClick={handleClear}
            >
              清空列表
            </Button>
          </>
        )}
      </Space>

      {files.length > 0 && (
        <div
          style={{
            border: '1px solid #d9d9d9',
            borderRadius: 8,
            padding: 8,
            maxHeight: 300,
            overflowY: 'auto',
          }}
        >
          {files.map((file) => {
            const d = detected[file.path];
            const hasError = d?.status === 'failed';

            return (
              <div
                key={file.path}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 8px',
                  borderBottom: '1px solid #f0f0f0',
                }}
              >
                <Space size={8}>
                  <Text
                    ellipsis={{ tooltip: file.name }}
                    style={{ maxWidth: 280 }}
                  >
                    {file.name}
                  </Text>
                  {isDetected(file) && (
                    <Tag color={hasError ? 'error' : 'blue'}>
                      {getStatusLabel(file)}
                    </Tag>
                  )}
                  {!isDetected(file) && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      待检测
                    </Text>
                  )}
                </Space>
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleRemove(file.path)}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
