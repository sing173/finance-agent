import { useState, useCallback } from 'react';

export type OverrideContext = {
  fileCount: number;
  isPdfOnly: boolean;
  onConfirm: (bank: string, docType: string, forceOcr: boolean) => void;
};

export function useOverrideModal() {
  const [open, setOpen] = useState(false);
  const [context, setContext] = useState<OverrideContext | null>(null);
  const [initialBank, setInitialBank] = useState('');
  const [initialDocType, setInitialDocType] = useState('');
  const [initialOcr, setInitialOcr] = useState(false);

  const show = useCallback((opts: {
    context: OverrideContext;
    initialBank?: string;
    initialDocType?: string;
    initialOcr?: boolean;
  }) => {
    setContext(opts.context);
    setInitialBank(opts.initialBank || '');
    setInitialDocType(opts.initialDocType || '');
    setInitialOcr(opts.initialOcr || false);
    setOpen(true);
  }, []);

  const close = useCallback(() => {
    setOpen(false);
    setContext(null);
  }, []);

  return {
    open,
    context,
    initialBank,
    initialDocType,
    initialOcr,
    show,
    close,
  };
}
