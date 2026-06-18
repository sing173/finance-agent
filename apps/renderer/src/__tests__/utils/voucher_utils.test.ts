import { describe, it, expect } from 'vitest';
import { flattenToRows, moveEntries, splitEntry } from '../../hooks/voucher_utils';
import type { VoucherData } from '@shared/types';

const makeEntry = (overrides: Partial<any> = {}) => ({
  entry_seq: 1, voucher_no: 1,
  date: '2026-03-01', summary: 'test',
  subject_code: '5060203', subject_name: '管理费用',
  debit_amount: 100, credit_amount: null,
  direction: 'expense' as const, counterparty: 'test',
  match_source: 'rule', rule_id: '',
  original_summary: '', original_amount: 100,
  is_manual: false, aux_category: '', aux_category_name: '',
  ...overrides,
});

const mockVouchers: VoucherData[] = [
  {
    voucher_no: 1, date: '2026-03-01', direction: 'expense',
    bank_subject_code: '1000201', counterpart_subject_code: '5060203',
    entries: [
      makeEntry({ entry_seq: 1, debit_amount: 1000, credit_amount: null }),
      makeEntry({ entry_seq: 2, debit_amount: null, credit_amount: 1000 }),
    ],
  },
  {
    voucher_no: 2, date: '2026-03-02', direction: 'income',
    bank_subject_code: '1000201', counterpart_subject_code: '5060202',
    entries: [
      makeEntry({ entry_seq: 1, voucher_no: 2, debit_amount: 500 }),
    ],
  },
];

describe('flattenToRows', () => {
  it('produces group header + entry rows for each voucher', () => {
    const rows = flattenToRows(mockVouchers);

    expect(rows).toHaveLength(5); // 2 groups + 2 entries + 1 entry

    // First group header
    expect(rows[0].type).toBe('group');
    expect(rows[0].voucher_no).toBe(1);
    expect((rows[0] as any).entryCount).toBe(2);

    // Entries under first group
    expect(rows[1].type).toBe('entry');
    expect(rows[1].voucher_no).toBe(1);
    expect(rows[2].type).toBe('entry');
    expect(rows[2].voucher_no).toBe(1);

    // Second group header
    expect(rows[3].type).toBe('group');
    expect(rows[3].voucher_no).toBe(2);
    expect((rows[3] as any).entryCount).toBe(1);

    // Entry under second group
    expect(rows[4].type).toBe('entry');
    expect(rows[4].voucher_no).toBe(2);
  });

  it('computes debit and credit totals for group headers', () => {
    const rows = flattenToRows(mockVouchers);
    const group1 = rows[0] as any;

    expect(group1.totalDebit).toBe(1000);
    expect(group1.totalCredit).toBe(1000);
  });

  it('returns empty array for empty input', () => {
    expect(flattenToRows([])).toEqual([]);
  });

  it('generates unique keys for all rows', () => {
    const rows = flattenToRows(mockVouchers);
    const keys = rows.map((r) => r.key);
    expect(new Set(keys).size).toBe(keys.length);
  });
});

describe('moveEntries', () => {
  const vouchers: VoucherData[] = [
    {
      voucher_no: 1, date: '2026-03-01', direction: 'expense',
      bank_subject_code: '1000201', counterpart_subject_code: '5060203',
      entries: [
        makeEntry({ entry_seq: 1, voucher_no: 1, debit_amount: 100 }),
        makeEntry({ entry_seq: 2, voucher_no: 1, debit_amount: 200 }),
        makeEntry({ entry_seq: 3, voucher_no: 1, debit_amount: 300 }),
      ],
    },
    {
      voucher_no: 2, date: '2026-03-02', direction: 'expense',
      bank_subject_code: '1000201', counterpart_subject_code: '5060203',
      entries: [
        makeEntry({ entry_seq: 1, voucher_no: 2, debit_amount: 500 }),
      ],
    },
    {
      voucher_no: 3, date: '2026-03-03', direction: 'expense',
      bank_subject_code: '1000201', counterpart_subject_code: '5060203',
      entries: [
        makeEntry({ entry_seq: 1, voucher_no: 3, debit_amount: 700 }),
      ],
    },
  ];

  it('moves selected entries to target voucher', () => {
    const selected = [{ voucher_no: 1, entry_seq: 1 }, { voucher_no: 1, entry_seq: 2 }];
    const result = moveEntries(vouchers, selected, 2);

    // After move: voucher 1 has 1 entry left, voucher 2 has 3, voucher 3 has 1
    // Re-numbered: #1 (was #1, 1 entry), #2 (was #2, 3 entries), #3 (was #3, 1 entry)
    const target = result.find((v) => v.voucher_no === 2)!;
    expect(target.entries).toHaveLength(3);
  });

  it('deletes source voucher when all entries are moved out and re-numbers', () => {
    const selected = [
      { voucher_no: 1, entry_seq: 1 },
      { voucher_no: 1, entry_seq: 2 },
      { voucher_no: 1, entry_seq: 3 },
    ];
    const result = moveEntries(vouchers, selected, 2);

    // Voucher 1 deleted. Remaining: was #2 (now #1, 4 entries), was #3 (now #2, 1 entry)
    expect(result).toHaveLength(2);
    expect(result[0].voucher_no).toBe(1);
    expect(result[0].entries).toHaveLength(4); // 1 original + 3 moved
    expect(result[1].voucher_no).toBe(2);
    expect(result[1].entries).toHaveLength(1);
  });

  it('deletes voucher when only bank entry remains after move', () => {
    const vouchersWithBank: VoucherData[] = [
      {
        voucher_no: 1, date: '2026-03-01', direction: 'expense',
        bank_subject_code: '1000201', counterpart_subject_code: '5060203',
        entries: [
          makeEntry({ entry_seq: 1, voucher_no: 1, debit_amount: 100, direction: 'expense' }),
          makeEntry({ entry_seq: 2, voucher_no: 1, debit_amount: null, credit_amount: 100, direction: 'bank' }),
        ],
      },
      {
        voucher_no: 2, date: '2026-03-02', direction: 'expense',
        bank_subject_code: '1000201', counterpart_subject_code: '5060203',
        entries: [
          makeEntry({ entry_seq: 1, voucher_no: 2, debit_amount: 500, direction: 'expense' }),
          makeEntry({ entry_seq: 2, voucher_no: 2, debit_amount: null, credit_amount: 500, direction: 'bank' }),
        ],
      },
    ];

    // Move the only non-bank entry from voucher 1 to voucher 2
    const selected = [{ voucher_no: 1, entry_seq: 1 }];
    const result = moveEntries(vouchersWithBank, selected, 2);

    // Voucher 1 only had bank entry left → deleted
    expect(result).toHaveLength(1);
    expect(result[0].voucher_no).toBe(1); // re-numbered from 2 to 1
  });

  it('re-numbers entry_seq in target voucher after move', () => {
    const selected = [{ voucher_no: 1, entry_seq: 1 }];
    const result = moveEntries(vouchers, selected, 2);

    const v2 = result.find((v) => v.voucher_no === 2)!;
    const seqs = v2.entries.map((e) => e.entry_seq);
    expect(seqs).toEqual([1, 2]); // re-sequenced
  });

  it('supports cross-voucher selection', () => {
    const selected = [
      { voucher_no: 1, entry_seq: 1 },
      { voucher_no: 3, entry_seq: 1 },
    ];
    const result = moveEntries(vouchers, selected, 2);

    // Voucher 3 emptied and deleted. Re-numbered: #1 (was #1, 2 entries), #2 (was #2, 3 entries)
    expect(result).toHaveLength(2);
    const target = result.find((v) => v.voucher_no === 2)!;
    expect(target.entries).toHaveLength(3); // 1 original + 2 moved
  });

  it('updates voucher_no on moved entries', () => {
    const selected = [{ voucher_no: 1, entry_seq: 1 }];
    const result = moveEntries(vouchers, selected, 2);

    const v2 = result.find((v) => v.voucher_no === 2)!;
    const moved = v2.entries.find((e) => e.debit_amount === 100)!;
    expect(moved.voucher_no).toBe(2);
  });
});

describe('splitEntry', () => {
  const vouchers: VoucherData[] = [
    {
      voucher_no: 1, date: '2026-03-01', direction: 'expense',
      bank_subject_code: '1000201', counterpart_subject_code: '5060203',
      entries: [
        makeEntry({ entry_seq: 1, voucher_no: 1, debit_amount: 1000, credit_amount: null, subject_code: '5060203', subject_name: '管理费用' }),
        makeEntry({ entry_seq: 2, voucher_no: 1, debit_amount: null, credit_amount: 1000, direction: 'bank' }),
      ],
    },
  ];

  it('splits one entry into two within the same voucher', () => {
    const newEntries = [
      { debit_amount: 600, credit_amount: null, subject_code: '5060203', subject_name: '管理费用_A' },
      { debit_amount: 400, credit_amount: null, subject_code: '5060204', subject_name: '管理费用_B' },
    ];
    const result = splitEntry(vouchers, 1, 1, newEntries);

    const v1 = result.find((v) => v.voucher_no === 1)!;
    expect(v1.entries).toHaveLength(3); // 2 new + 1 original bank entry
    expect(v1.entries[0].debit_amount).toBe(600);
    expect(v1.entries[1].debit_amount).toBe(400);
  });

  it('preserves other entries in the voucher', () => {
    const newEntries = [
      { debit_amount: 500, credit_amount: null },
      { debit_amount: 500, credit_amount: null },
    ];
    const result = splitEntry(vouchers, 1, 1, newEntries);

    const v1 = result.find((v) => v.voucher_no === 1)!;
    const bankEntry = v1.entries.find((e) => e.direction === 'bank');
    expect(bankEntry).toBeDefined();
    expect(bankEntry!.credit_amount).toBe(1000);
  });

  it('re-numbers entry_seq after split', () => {
    const newEntries = [
      { debit_amount: 600, credit_amount: null },
      { debit_amount: 400, credit_amount: null },
    ];
    const result = splitEntry(vouchers, 1, 1, newEntries);

    const v1 = result.find((v) => v.voucher_no === 1)!;
    const seqs = v1.entries.map((e) => e.entry_seq);
    expect(seqs).toEqual([1, 2, 3]);
  });

  it('inherits fields from original entry when not provided in split', () => {
    const newEntries = [
      { debit_amount: 600, credit_amount: null },
      { debit_amount: 400, credit_amount: null },
    ];
    const result = splitEntry(vouchers, 1, 1, newEntries);

    const v1 = result.find((v) => v.voucher_no === 1)!;
    // Both new entries should inherit date, summary, counterparty from original
    expect(v1.entries[0].date).toBe('2026-03-01');
    expect(v1.entries[1].counterparty).toBe('test');
  });
});
