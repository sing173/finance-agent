import { Button, Space, Typography, Tag, message, Tooltip } from 'antd';
import { PlusOutlined, CloseOutlined, DeleteOutlined, EditOutlined, PlayCircleOutlined } from '@ant-design/icons';
import type { BatchFileResult } from '@shared/types';

interface BatchFileSelectorProps {
  files: BatchFileResult[];
  onAddFiles: (filePaths: string[]) => void;
  onRemoveFile: (filePath: string) => void;
  onClear: () => void;
  /** 触发检测（只检测，不解析） */
  onDetect: () => void;
  /** 触发批量解析（基于已检测结果） */
  onStartParse: () => void;
  /** 修改单个文件的检测配置（不解析） */
  onModifyConfig: (filePath: string) => void;
  /** 是否正在检测 */
  isDetecting: boolean;
  /** 是否正在解析 */
  isParsing: boolean;
  /** 检测是否已完成（files 有内容且不在检测中） */
  detectDone: boolean;
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
}: BatchFileSelectorProps) {
  const atLimit = files.length >= 5;

  const handleAddFiles = async () => {
    if (atLimit) {
      message.warning('最多只能添加 5 个文件');
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
    if (file.bank && file.bank !== '未知') return <Tag color="blue">已检测</Tag>;
    return <Tag>待检测</Tag>;
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <Space style={{ marginBottom: 12 }}>
        <Tooltip title={atLimit ? '最多 5 个文件' : ''}>
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
                  ...(hasError ? { background: '#fff2f0' } : {}),
                }}
              >
                <Space size={8}>
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
