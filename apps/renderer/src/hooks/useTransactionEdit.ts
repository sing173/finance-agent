import { useState, useCallback } from 'react';
import type { Transaction } from '@shared/types';

export function useTransactionEdit() {
  const [open, setOpen] = useState(false);
  const [txn, setTxn] = useState<Transaction | null>(null);
  const [filePath, setFilePath] = useState<string | null>(null);

  const openSingle = useCallback((t: Transaction) => {
    setTxn(t);
    setFilePath(null);
    setOpen(true);
  }, []);

  const openBatch = useCallback((fp: string, t: Transaction) => {
    setTxn(t);
    setFilePath(fp);
    setOpen(true);
  }, []);

  const close = useCallback(() => {
    setOpen(false);
    setTxn(null);
    setFilePath(null);
  }, []);

  return {
    open,
    txn,
    filePath,
    openSingle,
    openBatch,
    close,
  };
}
