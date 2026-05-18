import { useState, useEffect, useCallback } from 'react';
import { Button, message, Tooltip, Space, Tag } from 'antd';
import { Typography } from 'antd';
const { Text } = Typography;
import { PlusOutlined, CloseOutlined, DeleteOutlined } from '@ant-design/icons';
import type { BatchFileResult } from '@shared/types';

interface BatchFileSelectorProps {
  files: BatchFileResult[];
  onAddFiles: (filePaths: string[]) => void;
  onRemoveFile: (filePath: string) => void;
  onClear: () => void;
  onDetectAndParse: () => void;
  isParsing: boolean;
  maxFiles?: number;
}

export function BatchFileSelector({
  files,
  onAddFiles,
  onRemoveFile,
  onClear,
  onDetectAndParse,
  isParsing,
  maxFiles = 5,
}: BatchFileSelectorProps) {
  const [localMaxFiles, setLocalMaxFiles] = useState(maxFiles);

  // 加载 batch_config.json
  useEffect(() => {
    fetch('/batch_config.json')
      .then((r) => r.json())
      .then((data) => setLocalMaxFiles(data.maxBatchFiles || maxFiles))
      .catch(() => setLocalMaxFiles(maxFiles));
  }, [maxFiles]);

  const atLimit = files.length >= localMaxFiles;

  const handleAddFiles = useCallback(async () => {
    try {
      const filePaths = await (window as any).electronAPI?.selectFile?.('pdf', true);
      if (!filePaths || !filePaths.length) return;

      const merged = [...files];
      for (const fp of filePaths) {
        if (!merged.some((f) => f.filePath === fp)) {
          merged.push({
            filePath: fp,
            fileName: fp.split(/[/\\]/).pop() || fp,
            bank: '',
            docType: '',
            status: 'pending',
            transactionCount: 0,
          });
        }
      }
      if (merged.length > localMaxFiles) {
        message.warning(`最多只能添加 ${localMaxFiles} 个文件`);
        return;
      }
      onAddFiles(merged.map((f) => f.filePath));
    } catch (err: any) {
      message.error('文件选择失败：' + err.message);
    }
  }, [files, onAddFiles, localMaxFiles]);

  const getStatusLabel = (file: BatchFileResult) => {
    if (file.status === 'success') return `${file.bank} · ${file.docType}`;
    if (file.status === 'failed') return '解析失败';
    return '待检测';
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <Space style={{ marginBottom: 12 }}>
        <Tooltip title={atLimit ? `最多 ${localMaxFiles} 个文件` : ''}>
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
              onClick={onDetectAndParse}
              disabled={isParsing}
              loading={isParsing}
            >
              识别并解析（{files.length}）
            </Button>
            <Button
              icon={<CloseOutlined />}
              onClick={onClear}
              disabled={isParsing}
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
            const hasError = file.status === 'failed';
            return (
              <div
                key={file.filePath}
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
                    ellipsis={{ tooltip: file.fileName }}
                    style={{ maxWidth: 280 }}
                  >
                    {file.fileName}
                  </Text>
                  {file.status !== 'pending' && (
                    <Tag color={hasError ? 'error' : 'blue'}>
                      {getStatusLabel(file)}
                    </Tag>
                  )}
                  {file.status === 'pending' && (
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
                  onClick={() => onRemoveFile(file.filePath)}
                  disabled={isParsing}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
