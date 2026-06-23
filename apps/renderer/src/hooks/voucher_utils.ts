/**
 * voucher_utils — 凭证数据处理工具函数
 *
 * 消除 useVoucherFlow 与 VoucherPreviewPanel 之间的重复 flatten/resolve 逻辑。
 * 注意：不导入 useVoucherFlow 以避免 circular dependency。
 */

/** 分录条目（最小类型，仅用于工具函数参数） */
export interface VoucherEntryLike {
  entry_seq: number;
  voucher_no: number;
  match_source: string;
  direction: string;
}

/** 凭证数据（最小类型，仅用于工具函数参数） */
export interface VoucherDataLike {
  voucher_no: number;
  entries: VoucherEntryLike[];
}

/** 从 voucher 数据中提取所有分录（扁平化） */
export function flattenEntries(vouchers: VoucherDataLike[]): VoucherEntryLike[] {
  const all: VoucherEntryLike[] = [];
  for (const vc of vouchers) {
    for (const e of vc.entries) {
      all.push(e);
    }
  }
  return all;
}

/** 解析实际使用的 voucher 数据（edited 非空优先） */
export function resolveVouchers(
  edited: VoucherDataLike[],
  original: VoucherDataLike[],
): VoucherDataLike[] {
  return edited.length > 0 ? edited : original;
}

/** 判断分录是否为「未匹配且非银行」条目 */
export function isUnmatchedNonBank(e: { match_source: string; direction: string }): boolean {
  return e.match_source === 'unmatched' && e.direction !== 'bank';
}

/** 单表行类型：分组行或明细行 */
export type TableRow =
  | { key: string; type: 'group'; voucher_no: number; date: string; entryCount: number; totalDebit: number; totalCredit: number }
  | { key: string; type: 'entry'; voucher_no: number; entry_seq: number; [field: string]: any };

/** 将凭证数组扁平化为表格行（分组行 + 明细行交替） */
export function flattenToRows(vouchers: { voucher_no: number; date: string; entries: any[] }[]): TableRow[] {
  const rows: TableRow[] = [];
  for (const v of vouchers) {
    let totalDebit = 0;
    let totalCredit = 0;
    for (const e of v.entries) {
      if (e.debit_amount != null) totalDebit += e.debit_amount;
      if (e.credit_amount != null) totalCredit += e.credit_amount;
    }
    rows.push({
      key: `group-${v.voucher_no}`,
      type: 'group',
      voucher_no: v.voucher_no,
      date: v.date,
      entryCount: v.entries.length,
      totalDebit,
      totalCredit,
    });
    for (const e of v.entries) {
      rows.push({
        key: `entry-${v.voucher_no}-${e.entry_seq}`,
        type: 'entry',
        voucher_no: v.voucher_no,
        entry_seq: e.entry_seq,
        ...e,
      });
    }
  }
  return rows;
}

/** 重新计算凭证中银行存款分录的金额（借方=非银行贷方合计，贷方=非银行借方合计） */
export function recalcBankEntry<T extends { entries: any[] }>(voucher: T): T {
  let totalDebit = 0;
  let totalCredit = 0;
  for (const e of voucher.entries) {
    if (e.direction === 'bank') continue;
    if (e.debit_amount != null) totalDebit += e.debit_amount;
    if (e.credit_amount != null) totalCredit += e.credit_amount;
  }
  return {
    ...voucher,
    entries: voucher.entries.map((e) =>
      e.direction === 'bank'
        ? { ...e, debit_amount: totalCredit || null, credit_amount: totalDebit || null }
        : e,
    ),
  } as T;
}

/** 排序分录：银行存款分录始终排在最后 */
function bankLast(entries: any[]): any[] {
  return [...entries].sort((a, b) => {
    if (a.direction === 'bank' && b.direction !== 'bank') return 1;
    if (a.direction !== 'bank' && b.direction === 'bank') return -1;
    return 0;
  });
}

/** 分录移动：将选中的分录移至目标凭证，空凭证自动删除 */
export function moveEntries(
  vouchers: { voucher_no: number; date: string; direction: string; entries: any[];[k: string]: any }[],
  selected: { voucher_no: number; entry_seq: number }[],
  targetVoucherNo: number,
): typeof vouchers {
  const selectedSet = new Set(selected.map((s) => `${s.voucher_no}-${s.entry_seq}`));

  // 1. Collect all entries to move (update voucher_no to target)
  const movedEntries: any[] = [];
  for (const v of vouchers) {
    for (const e of v.entries) {
      if (selectedSet.has(`${v.voucher_no}-${e.entry_seq}`) && v.voucher_no !== targetVoucherNo) {
        movedEntries.push({ ...e, voucher_no: targetVoucherNo });
      }
    }
  }

  // 2. Remove selected entries from source vouchers, append to target, filter empty
  const filtered = vouchers
    .map((v) => {
      if (v.voucher_no === targetVoucherNo) {
        return { ...v, entries: [...v.entries, ...movedEntries] };
      }
      return { ...v, entries: v.entries.filter((e) => !selectedSet.has(`${v.voucher_no}-${e.entry_seq}`)) };
    })
    .filter((v) => v.voucher_no === targetVoucherNo || v.entries.some((e: any) => e.direction !== 'bank'))
    .map((v) => {
      const sorted = bankLast(v.entries);
      return { ...v, entries: sorted.map((e: any, i: number) => ({ ...e, entry_seq: i + 1 })) };
    })
    .map(recalcBankEntry);

  // 3. Re-number voucher_no sequentially and update entry voucher_no
  return filtered.map((v, i) => {
    const newNo = i + 1;
    return {
      ...v,
      voucher_no: newNo,
      entries: v.entries.map((e: any) => ({ ...e, voucher_no: newNo })),
    };
  });
}

/** 拆分分录：将一条分录替换为多条，留在原凭证内 */
export function splitEntry(
  vouchers: { voucher_no: number; entries: any[];[k: string]: any }[],
  voucherNo: number,
  entrySeq: number,
  newEntries: Partial<any>[],
): typeof vouchers {
  return vouchers.map((v) => {
    if (v.voucher_no !== voucherNo) return v;

    const idx = v.entries.findIndex((e) => e.entry_seq === entrySeq);
    if (idx === -1) return v;

    const original = v.entries[idx];
    const replacements = newEntries.map((n) => ({ ...original, ...n, voucher_no: voucherNo }));
    const replaced = [...v.entries.slice(0, idx), ...replacements, ...v.entries.slice(idx + 1)];
    const sorted = bankLast(replaced);

    const updated = {
      ...v,
      entries: sorted.map((e: any, i: number) => ({ ...e, entry_seq: i + 1 })),
    };
    return recalcBankEntry(updated);
  });
}
