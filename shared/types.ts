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

/** 健康检查 */
export interface HealthParams {}
export interface HealthResult {
  status: "ok";
  version: string;
  python_version: string;
}

/** PDF 解析 */
export interface ParsePDFParams {
  filePath: string;
  bank?: string; // 可选：自动识别银行
  docType?: string; // 可选：手动指定文档类型（statement / receipt）
  forceOcr?: boolean; // 可选：强制 OCR
}
export interface ParsePDFResult {
  success: boolean;
  transactions: Transaction[];
  bank: string;
  statementDate: string;
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

// ========== 文件上传方案新增类型 ==========

/** 批量检测单个文件的返回 */
export interface DetectFileResult {
  filePath: string;
  bank: string;
  docType: string;
  status: 'ok' | 'failed';
}

/** 批量检测结果 */
export interface DetectBanksResult {
  success: boolean;
  results: DetectFileResult[];
}

/** 批量解析单个文件的结果 */
export interface BatchFileResult {
  filePath: string;
  fileName: string;
  bank: string;
  docType: string;
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
