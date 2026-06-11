/**
 * shared/types.ts
 * IPC 接口契约 — 前端、Electron 主进程、Python 后端三方共享
 * JSON-RPC 2.0 风格
 */

/** 基础请求/响应包装器 */
export interface JSONRPCRequest<T = any> {
  jsonrpc: "2.0";
  id: number | string;
  method: string;
  params: T;
}

export interface JSONRPCResponse<T = any> {
  jsonrpc: "2.0";
  id: number | string;
  result?: T;
  error?: { code: number; message: string; data?: any };
}

/** 文档类型：统一使用中文 */
export type DocType = '流水' | '回单' | 'unknown';

/** 文件解析（统一入口：PDF/CSV/Excel） */
export interface ParseFileParams {
  filePath: string;
  bank?: string; // 可选：自动识别银行
  docType?: DocType; // 可选：手动指定文档类型（流水 / 回单）
  forceOcr?: boolean; // 可选：强制 OCR
}
export interface ParseFileResult {
  success: boolean;
  transactions: Transaction[];
  bank: string;
  docType: DocType;
  statementDate?: string;
  openingBalance?: number;
  closingBalance?: number;
  confidence: number;
  errors: string[];
  warnings: string[];
}

/** 交易记录 */
export interface Transaction {
  date: string; // "2025-03-15"
  description: string;
  amount: number; // 单位：元，正数为收入，负数为支出
  currency: string; // "CNY"
  balance?: number;
  direction: "income" | "expense";
  counterparty?: string;
  reference_number?: string;
  notes?: string | null;
  account_number?: string | null;
  account_name?: string | null;
}

/** Agent 聊天（非流式） */
export interface ChatParams {
  message: string;
  session_key?: string;
  context?: any;
}
export interface ChatResult {
  content: string;
  tools_used?: string[];
}

/** Agent 聊天（流式） */
export interface ChatStreamParams extends ChatParams {
  on_chunk: (chunk: string) => void;
}

/** 账号-科目映射（Issue #29: FR-1） */
export interface AccountEntry {
  id: string;
  matchType: 'suffix' | 'exact';
  pattern: string;
  bank: string;
  bankCode: string;
  subjectCode: string;
  subjectName: string;
  /** 完整科目名称（可选） */
  full_name?: string;
}

// ========== 科目相关类型 ==========

/** 会计科目条目（后端 get_subjects_info 返回） */
export interface SubjectItem {
  code: string;
  name: string;
  category: string;
  direction: string;
  /** 是否现金类科目 */
  is_cash: boolean;
  /** 是否启用 */
  enabled: boolean;
  /** 完整科目名称 */
  full_name: string;
}

// ========== 文件上传方案新增类型 ==========

/** 批量检测单个文件的返回 */
export interface DetectFileResult {
  filePath: string;
  bank: string;
  bankCode?: string;
  docType: DocType;
  status: 'ok' | 'failed';
}

/** 批量检测结果 */
export interface DetectBanksResult {
  success: boolean;
  results: DetectFileResult[];
}

/** 支持银行列表查询 */
export interface BankInfo {
  code: string;  // ICBC / CMB / GFB
  name: string;  // 工商银行 / 招商银行 / 广发银行
}

export interface DetectSupportedBanksResult {
  success: boolean;
  banks: BankInfo[];
}

/** 批量解析单个文件的结果 */
export interface BatchFileResult {
  filePath: string;
  fileName: string;
  bank: string;
  docType: DocType;
  statementDate?: string;
  status: 'pending' | 'success' | 'failed' | 'cancelled';
  isManual?: boolean;
  transactions?: Transaction[];
  error?: string;
  transactionCount: number;
}

/** 批量解析总体结果 */
export interface BatchResult {
  files: BatchFileResult[];
  totalFiles: number;
  successCount: number;
  failedCount: number;
  totalTransactions: number;
}

// ========== 凭证管道类型（Issue #48 / Issue #47 P0）==========

/** 凭证分录 — 与 Python PipelineEntry 17 字段对齐。 */
export interface VoucherEntry {
  entry_seq: number;
  voucher_no: number;
  date: string;
  summary: string;
  subject_code: string;
  subject_name: string;
  debit_amount: number | null;
  credit_amount: number | null;
  direction: 'income' | 'expense' | 'bank';
  counterparty: string;
  match_source: string;
  rule_id: string;
  original_summary: string;
  original_amount: number;
  is_manual: boolean;
  aux_category: string;
  aux_category_name: string;
}

/** 凭证（包含多条分录） */
export interface VoucherData {
  voucher_no: number;
  date: string;
  direction: string;
  bank_subject_code: string;
  counterpart_subject_code: string;
  entries: VoucherEntry[];
}