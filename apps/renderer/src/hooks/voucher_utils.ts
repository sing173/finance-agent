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
