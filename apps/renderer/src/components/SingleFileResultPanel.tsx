import type { Transaction, ParseFileResult } from '@shared/types';
import { ResultCard } from './ResultCard';
import { getFileNameFromPath } from '../utils/pathUtils';

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
    <div>
      {(detectState === 'detected' || detectState === 'unknown' || loading || currentResult) && (
        <ResultCard
          key={currentFilePath || undefined}
          fileName={currentFilePath ? getFileNameFromPath(currentFilePath) : undefined}
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
          transactions={currentResult?.transactions || []}
          onRedetect={onRedetect}
          onModifyConfig={onModifyConfig}
          onStartParse={onStartParse}
          onPreviewVoucher={() => onPreviewVoucher(currentResult?.transactions || [])}
          onEditTransaction={onEditTransaction}
        />
      )}
    </div>
  );
}
