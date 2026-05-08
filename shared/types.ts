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
  file_path: string;
  bank?: string; // 可选：自动识别银行
}
export interface ParsePDFResult {
  success: boolean;
  transactions: Transaction[];
  bank: string;
  statement_date: string;
  confidence: number;
  errors: string[];
}

/** 交易记录 */
export interface Transaction {
  date: string; // "2025-03-15"
  description: string;
  amount: number; // 单位：元，正数为收入，负数为支出
  currency: string; // "CNY"
  balance?: number;
  direction: "income" | "expense" | "transfer";
  counterparty?: string;
  reference_number?: string;
  notes?: string;
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
