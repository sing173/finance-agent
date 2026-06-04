import { useState, useEffect } from 'react';
import { Button, Space, Typography, Tag, message, Tooltip, Spin } from 'antd';
import { PlusOutlined, CloseOutlined, DeleteOutlined, EditOutlined, PlayCircleOutlined } from '@ant-design/icons';
import type { BatchFileResult } from '@shared/types';

interface BatchFileSelectorProps {
  files: BatchFileResult[];
  onAddFiles: (filePaths: string[]) => void;
  onRemoveFile: (filePath: string) => void;
  onClear: () => void;
  /** Detect banks (no parse) */
  onDetect: () => void;
  /** Parse all files based on detected results */
  onStartParse: () => void;
  /** Modify a single file's detection config (no parse) */
  onModifyConfig: (filePath: string) => void;
  /** Currently detecting banks */
  isDetecting: boolean;
  /** Currently parsing files */
  isParsing: boolean;
  /** Detection done (files added and not detecting) */
  detectDone: boolean;
  /** Current parsing index (1-based), 0 means not parsing */
  currentIndex?: number;
  /** Total file count */
  totalCount?: number;
}

export function BatchFileSelector({
  files,
  onAddFiles,
  onRemoveFile,
  onClear,
  onDetect,
  onStartParse,
  onModifyConfig,
  isDetecting,
  isParsing,
  detectDone,
  currentIndex = 0,
  totalCount = 0,
}: BatchFileSelectorProps) {
  const [maxFiles, setMaxFiles] = useState(5);

  // Load batch config dynamically
  useEffect(() => {
    const controller = new AbortController();
    fetch('./batch_config.json', { signal: controller.signal })
      .then((r) => r.json())
      .then((data) => setMaxFiles(data.maxBatchFiles || 5))
      .catch((err) => {
        if (err.name !== 'AbortError') setMaxFiles(5);
      });
    return () => controller.abort();
  }, []);

  const atLimit = files.length >= maxFiles;

  const handleAddFiles = async () => {
    if (atLimit) {
      message.warning(`最多只能添加 ${maxFiles} 个文件`);
      return;
    }
    try {
      const filePaths = await (window as any).electronAPI?.selectFile?.('all', true);
      if (!filePaths || !filePaths.length) return;
      onAddFiles(filePaths);
    } catch (err: any) {
      message.error('文件选择失败：' + err.message);
    }
  };

  const getStatusTag = (file: BatchFileResult) => {
    if (file.status === 'success') return <Tag color="green">解析成功</Tag>;
    if (file.status === 'failed') return <Tag color="red">解析失败</Tag>;
    if (file.bank && file.bank !== '未知') return <Tag color={file.isManual ? 'purple' : 'blue'}>{file.isManual ? '已设置' : '已检测'}</Tag>;
    return <Tag>待检测</Tag>;
  };

  // Parsing progress text
  const parsingProgress = isParsing && totalCount > 0
    ? `正在解析 ${currentIndex}/${totalCount}`
    : null;

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
              onClick={onDetect}
              disabled={isDetecting || isParsing}
              loading={isDetecting}
              icon={<EditOutlined />}
            >
              识别文件
            </Button>

            <Button
              type="primary"
              onClick={onStartParse}
              disabled={isDetecting || isParsing || !detectDone}
              loading={isParsing}
              icon={<PlayCircleOutlined />}
            >
              开始解析
            </Button>

            <Button
              icon={<CloseOutlined />}
              onClick={onClear}
              disabled={isDetecting || isParsing}
            >
              清空列表
            </Button>
          </>
        )}
      </Space>

      {isParsing && parsingProgress && (
        <div style={{ marginBottom: 8 }}>
          <Typography.Text type="secondary">
            <Spin size="small" style={{ marginRight: 8 }} />
            {parsingProgress}
          </Typography.Text>
        </div>
      )}

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
            const isCurrentParsing = isParsing && file.status === 'pending' && files.indexOf(file) === currentIndex - 1;
            return (
              <div
                key={file.filePath}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 8px',
                  borderBottom: '1px solid #f0f0f0',
                  background: isCurrentParsing ? '#e6f7ff' : hasError ? '#fff2f0' : undefined,
                  transition: 'background 0.2s',
                }}
              >
                <Space size={8}>
                  {isParsing && isCurrentParsing && <Spin size="small" />}
                  <Typography.Text
                    ellipsis={{ tooltip: file.fileName }}
                    style={{ maxWidth: 260 }}
                  >
                    {file.fileName}
                  </Typography.Text>
                  {file.bank && file.bank !== '未知' && (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {file.bank} · {file.docType || 'unknown'}
                    </Typography.Text>
                  )}
                  {getStatusTag(file)}
                  {hasError && file.error && (
                    <Typography.Text type="danger" style={{ fontSize: 12 }}>
                      {file.error}
                    </Typography.Text>
                  )}
                </Space>
                <Space size={4}>
                  {detectDone && (
                    <Button
                      type="link"
                      size="small"
                      icon={<EditOutlined />}
                      onClick={() => onModifyConfig(file.filePath)}
                      disabled={isParsing}
                      title="修改配置"
                    >
                      修改
                    </Button>
                  )}
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => onRemoveFile(file.filePath)}
                    disabled={isDetecting || isParsing}
                  />
                </Space>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
