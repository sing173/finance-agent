import { Card } from 'antd';
import type { Transaction, ParseFileResult } from '@shared/types';
import { ResultCard } from './ResultCard';
import { TransactionTable } from './TransactionTable';

interface SingleFileResultPanelProps {
  detectState: 'idle' | 'detecting' | 'detected' | 'unknown';
  loading: boolean;
  currentFilePath: string | null;
  currentResult: ParseFileResult | null;
  detectInfo: { bank: string; docType: string; isManual: boolean };
  detectUnknown: boolean;
  onRedetect: () => void;
  onModifyConfig: () => void;
  onStartParse: () => void;
  onPreviewVoucher: (transactions: Transaction[]) => void;
  onEditTransaction: (txn: Transaction) => void;
}

export function SingleFileResultPanel({
  detectState,
  loading,
  currentFilePath,
  currentResult,
  detectInfo,
  detectUnknown,
  onRedetect,
  onModifyConfig,
  onStartParse,
  onPreviewVoucher,
  onEditTransaction,
}: SingleFileResultPanelProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 检测中 */}
      {detectState === 'detecting' && (
        <Card title="检测中">
          <span style={{ color: '#999' }}>正在识别银行类型...</span>
        </Card>
      )}

      {/* 检测完成 / 解析中 / 解析结果 */}
      {(detectState === 'detected' || detectState === 'unknown' || loading || currentResult) && (
        <ResultCard
          key={currentFilePath || undefined}
          phase={
            loading
              ? 'parsing'
              : currentResult
              ? currentResult.success
                ? 'success'
                : 'failed'
              : 'detect'
          }
          bank={currentResult?.bank || detectInfo.bank || '未知'}
          docType={currentResult?.docType || detectInfo.docType || 'unknown'}
          transactionCount={currentResult?.transactions?.length || 0}
          statementDate={currentResult?.statementDate}
          error={currentResult?.errors?.join(', ') || undefined}
          detectUnknown={detectUnknown}
          isManual={detectInfo.isManual}
          onRedetect={onRedetect}
          onModifyConfig={onModifyConfig}
          onStartParse={onStartParse}
          onPreviewVoucher={() => onPreviewVoucher(currentResult?.transactions || [])}
        />
      )}

      {/* 交易列表 */}
      {currentResult?.success && currentResult.transactions?.length > 0 && (
        <Card title="交易列表">
          <TransactionTable
            transactions={currentResult.transactions}
            loading={loading}
            onEdit={onEditTransaction}
          />
        </Card>
      )}
    </div>
  );
}
