import { useState, useEffect } from 'react';
import { Button, Space, Typography, Tag, message, Tooltip, Spin } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, PlayCircleOutlined } from '@ant-design/icons';
import type { BatchFileResult } from '@shared/types';

interface BatchFileSelectorProps {
  files: BatchFileResult[];
  onAddFiles: (filePaths: string[]) => void;
  onRemoveFile: (filePath: string) => void;
  onDetect: () => void;
  onStartParse: () => void;
  onModifyConfig: (filePath: string) => void;
  isDetecting: boolean;
  detectDone: boolean;
  allConfigured: boolean;
  currentIndex?: number;
}

export function BatchFileSelector({
  files,
  onAddFiles,
  onRemoveFile,
  onDetect,
  onStartParse,
  onModifyConfig,
  isDetecting,
  detectDone,
  allConfigured,
  currentIndex = 0,
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

  const getStatusTag = (file: BatchFileResult, isCurrentDetecting: boolean) => {
    if (isCurrentDetecting) return <Tag color="processing">识别中...</Tag>;
    if (file.isManual && file.bank && file.bank !== '未知') return <Tag color="purple">已设置</Tag>;
    if (file.status === 'failed') return <Tag color="error">检测失败</Tag>;
    if (file.bank && file.bank !== '未知') return <Tag color="success">已检测</Tag>;
    return <Tag>待检测</Tag>;
  };

  return (
    <div style={{ marginBottom: 16 }}>
      {/* 操作按钮区 */}
      <Space style={{ marginBottom: 12 }}>
        <Tooltip title={atLimit ? `最多 ${maxFiles} 个文件` : ''}>
          <Button icon={<PlusOutlined />} onClick={handleAddFiles} disabled={atLimit}>添加文件</Button>
        </Tooltip>

        {files.length > 0 && (
          <>
            <Button onClick={onDetect} disabled={isDetecting} loading={isDetecting} icon={<EditOutlined />}>识别文件</Button>
            <Button style={{ background: '#dc2626', color: '#fff', borderColor: '#dc2626' }} onClick={() => allConfigured ? onStartParse() : message.warning('请先识别文件或手动设置类型')} disabled={isDetecting} icon={<PlayCircleOutlined />}>开始解析</Button>
          </>
        )}
      </Space>

      {/* 文件列表 */}
      {files.length > 0 && (
        <div
          style={{
            border: '1px solid #d6d3cd',
            borderRadius: 6,
            padding: 8,
            maxHeight: 300,
            overflowY: 'auto',
          }}
        >
          {files.map((file) => {
            const hasError = file.status === 'failed';
            const isCurrentDetecting = isDetecting && file.status === 'pending' && files.indexOf(file) === currentIndex - 1;
            return (
              <div
                key={file.filePath}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 8px',
                  borderBottom: '1px solid #e7e5e4',
                  background: isCurrentDetecting ? '#e8eef5' : hasError ? '#fef2f2' : undefined,
                  transition: 'background 0.2s',
                }}
              >
                <Space size={8}>
                  {isCurrentDetecting && <Spin size="small" />}
                  <Typography.Text ellipsis={{ tooltip: file.fileName }} style={{ maxWidth: 260 }}>{file.fileName}</Typography.Text>
                  {file.bank && file.bank !== '未知' && (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>{file.bank} · {file.docType || 'unknown'}</Typography.Text>
                  )}
                  {getStatusTag(file, isCurrentDetecting)}
                  {hasError && file.error && (
                    <Typography.Text type="danger" style={{ fontSize: 12 }}>{file.error}</Typography.Text>
                  )}
                </Space>
                <Space size={4}>
                  {detectDone && (
                    <Button type="link" size="small" icon={<EditOutlined />} onClick={() => onModifyConfig(file.filePath)} title="修改配置">修改</Button>
                  )}
                  <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => onRemoveFile(file.filePath)} disabled={isDetecting} />
                </Space>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
