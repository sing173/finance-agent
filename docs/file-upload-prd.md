# PRD: 文件上传与解析 — 单文件 + 批量模式

> 基于 `docs/file-upload-design.md` 对齐决策（50 条），覆盖单文件解析和批量解析（同类型文档，最多 5 个）。

---

## Problem Statement

当前应用只有一个单一的文件入口（`FileDropZone`），用户选择文件后自动检测银行和文档类型并解析。这个流程在单文件场景下基本可用，但存在两个核心痛点：

1. **检测失败时用户无法手动覆盖**：后端自动检测银行失败（未知银行/未知类型）或用户知道银行类型但后端猜错时，唯一的选择是关掉重新选文件，没有中途修正的路径。

2. **没有批量解析能力**：财务人员处理一个月对账单时通常需要处理 5–10 个 PDF 文件，逐个选文件逐个解析的体验极差，且无法合并导出。

从用户视角看：**"我选了一个文件但系统识别错了，我怎么告诉它到底是哪家银行？"** 以及 **"我有 5 个同类型文件，能不能一次全部解析然后合并导出？"** 这两个问题当前都没有答案。

---

## Solution

### 单文件模式（增强）

用户在 `FileDropZone` 选文件 → 后端毫秒级检测银行+文档名 → 结果卡片展示"检测到：招商银行 · 账务明细清单" → 用户确认解析 → 展示结果。

- 检测失败或解析失败时弹出 **ManualOverrideModal**（共用手动覆盖模态），让用户手动选择银行+表格类型+是否强制OCR。
- 用户手动覆盖后，结果卡片文案变为"已选择：XX"，区分于"检测到"。
- 结果卡片有三个按钮：`[重新检测]`（回到自动检测）、`[修改配置]`（打开 fallback 面板）、`[重新选择文件]`（清空重来）。

### 批量模式（新增）

独立的 `[批量解析]` 入口 → 用户点击 `[+ 添加文件]` 逐个选择或一次多选（最多 5 个）→ 已选文件列表展示（文件名+检测状态+删除按钮）→ 用户点 `[识别文件]` → 后端批量检测每个文件的银行 → 列表状态更新 → 如有失败文件，配置面板提示"有 X 个文件无法识别" → 统一配置银行+表格类型 → 逐个解析，跳过失败继续 → 按文件分组折叠展示 → 顶部摘要+`[全部导出 Excel]`/`[全部导出凭证]`。

批量模式文件数量上限从 `public/batch_config.json` 读取，默认为 5，软上限（可配置为硬限制）。

---

## User Stories

### 单文件模式

1. As a 财务人员, I want to select a single bank statement PDF file, so that I can view and export its transactions
2. As a 财务人员, I want the app to automatically detect the bank type from the file, so that I don't need to manually specify it every time
3. As a 财务人员, I want to see the detected bank and document name on the result card, so that I can confirm the app identified my file correctly
4. As a 财务人员, I want to manually override the bank type when auto-detection fails, so that I can still parse files from unsupported or unrecognizable banks
5. As a 财务人员, I want to manually override the table type (流水/回单) when needed, so that the app routes to the correct parser
6. As a 财务人员, I want to force OCR on a PDF when the app treats it as a native-PDF but it's actually a scan, so that I can extract text from image-based files
7. As a 财务人员, I want to see "已选择" instead of "检测到" after manual override, so that I can distinguish auto-detected from manually specified values
8. As a 财务人员, I want a `[重新检测]` button to revert to auto-detection after manual override, so that I can quickly undo my manual selection
9. As a 财务人员, I want a `[修改配置]` button to reopen the override panel with pre-filled values, so that I can tweak my selection without re-selecting the file
10. As a 财务人员, I want a `[重新选择文件]` button to clear everything and start over, so that I can parse a different file from scratch
11. As a 财务人员, I want to see error messages when parsing fails, so that I understand what went wrong
12. As a 财务人员, I want to export parsed transactions to Excel (流水明细) or Kingdee vouchers (精斗云凭证), so that I can use the data in downstream accounting workflows

### 批量模式

13. As a 财务人员, I want a dedicated `[批量解析]` entry point, so that I can parse multiple files of the same type in one session
14. As a 财务人员, I want to add files to a batch queue one by one or select multiple at once, so that I have flexibility in how I build the batch
15. As a 财务人员, I want to see a list of selected files with their detection status before parsing, so that I can verify the batch composition
16. As a 财务人员, I want to remove individual files from the batch list, so that I can correct mistakes without re-selecting everything
17. As a 财务人员, I want a hard limit on batch file count (default 5, configurable), so that I don't accidentally queue too many files
18. As a 财务人员, I want the app to detect the bank type of each file in the batch upfront, so that I can see which files are recognized and which aren't before parsing
19. As a 财务人员, I want to configure the bank type and table type once for the entire batch, so that I don't have to repeat the same selection for every file
20. As a 财务人员, I want the app to warn me when files in the batch have mixed formats or mixed bank types, so that I know if my batch is heterogeneous
21. As a 财务人员, I want the batch to skip files that fail parsing and continue with the rest, so that one bad file doesn't block the entire batch
22. As a 财务人员, I want to retry individual failed files after the batch completes, so that I can fix specific files without re-parsing everything
23. As a 财务人员, I want to see batch parsing progress (X of Y files, current file name), so that I know how long the batch will take
24. As a 财务人员, I want a `[取消]` button during batch parsing, so that I can stop the batch if it's taking too long
25. As a 财务人员, I want failed files highlighted in red in the batch result panel, so that I can quickly spot and address them
26. As a 财务人员, I want to expand/collapse individual file results in the batch, so that I can scan the overview or drill into details
27. As a 财务人员, I want `[全部展开]` / `[全部收起]` buttons on the batch panel, so that I can quickly toggle all file groups
28. As a 财务人员, I want to view a single file's details in the same format as single-file mode, so that I get a familiar and consistent experience
29. As a 财务人员, I want `[全部导出 Excel]` and `[全部导出凭证]` buttons that merge all successful files into one output, so that I can produce a consolidated report
30. As a 财务人员, I want the export button to show the count of successful files, so that I know how many files will be included before clicking
31. As a 财务人员, I want transaction tables in batch mode to have the same columns as single-file mode, so that the data presentation is consistent

### 共用 / 基础

32. As a 财务人员, I want the fallback override panel to work for both single-file and batch modes, so that I have a consistent manual-selection experience
33. As a 财务人员, I want the override panel to preserve my selections when I cancel, so that I don't lose my configuration when I change my mind
34. As a 财务人员, I want the app to remember my session results (but not persist across app restarts), so that I don't lose work when switching between modes
35. As a 财务人员, I want the bank dropdown in the override panel to be dynamically populated from the backend, so that adding a new bank to the backend automatically makes it available in the UI

---

## Implementation Decisions

### 模块划分

#### 1. 前端模块（Renderer — React + TypeScript）

**`App.tsx`（重构）**
当前单文件流程的容器，将扩展为双模式容器。用 `mode: 'single' | 'batch'` state 控制渲染 `SingleFileView` 或 `BatchView`。单文件模式保留现有布局结构（系统设置卡片 + 文件上传区域 + 导出区域 + 结果区域），批量模式替换为批量选择器 + 批量结果面板。

关键 state：
- `mode: 'single' | 'batch'`
- `currentResult: ParseResult | null` — 单文件解析结果（会话级）
- `batchResult: BatchResult | null` — 批量解析结果（会话级）
- `loading: boolean` — 全局加载状态

**`components/FileDropZone.tsx`（保留）**
单文件入口卡片，点击打开原生文件选择器。接口不变：`onFileSelected(filePath: string)`。

**`components/BatchFileSelector.tsx`（新建）**
批量文件选择器。包含：
- `[+ 添加文件]` 按钮 → 打开多选文件选择器（`maxCount` 来自 `batch_config.json`）
- 已选文件列表（每行：文件名截断 + 检测状态 + 删除按钮）
- `[清空列表]` 按钮
- `[识别文件]` 按钮 → 调用后端 `detect_banks` RPC

文件数量上限从 `public/batch_config.json` 的 `maxBatchFiles` 字段读取，`[+ 添加文件]` 按钮在达到上限时灰显+tooltip。

**`components/ManualOverrideModal.tsx`（新建）**
共用手动覆盖模态框，单文件和批量共用。内部包含：
- 银行类型下拉（`detect_supported_banks` RPC 动态填充）
- 表格类型下拉（固定：`流水` / `回单`）
- 强制 OCR 复选框（仅 PDF 文件时显示）
- `[解析]` / `[取消]` 按钮

批量模式下，面板顶部文案动态显示"有 X 个文件无法自动识别，请手动选择"。`[取消]` 和 `[×]` 关闭时保留用户已选配置。

**`components/ResultCard.tsx`（新建）**
单文件结果展示卡片。展示：检测到的银行+文档名（或"已选择"文案）、解析交易数、账单日期、三个按钮（`[重新检测]` `[修改配置]` `[重新选择文件]`）。解析失败时展示错误信息+`[修改配置]`。

**`components/BatchResultPanel.tsx`（新建）**
批量结果面板。包含：
- 摘要卡片：文件数/成功数/失败数/交易数 + `[全部导出 Excel]`/`[全部导出凭证]` 按钮
- Antd Collapse（折叠面板）：每个文件一个折叠项
  - 成功文件标题：`▶ filename.pdf  ✓ 23笔  |  招商银行  |  账务明细清单  |  2026-03-15`
  - 失败文件标题：`▶ scan.pdf  ✗ 解析失败  [重试]`（红色收起样式）
  - 展开内容：交易表格（与单文件相同的列）+ `[查看详情]` 链接
- `[全部展开]` / `[全部收起]` 按钮

**`components/TransactionTable.tsx`（保留）**
已有，列：日期/描述/金额/方向/对方户名/本方帐号/本方户名/流水号/操作。单文件和批量模式下复用。

**`components/ProgressSteps.tsx`（保留）**
已有，批量模式复用显示解析进度。

**`public/batch_config.json`（新建）**
批量模式配置：
```json
{ "maxBatchFiles": 5 }
```
前端启动时 fetch，不依赖构建步骤。

#### 2. 后端模块（Python — `bridge.py`）

**`detect_banks`（新建 RPC 方法）**
批量文件银行检测。接收 `file_paths: string[]`，并行读取每个文件前 3 页文字，匹配银行关键字，返回 `[{file_path, bank, doc_type, status}]`。独立方法，不复用 `parse_pdf`。

**`detect_supported_banks`（新建 RPC 方法）**
动态返回支持的银行列表，从 `BANK_KEYWORDS` 字典的 keys 自动生成，零维护成本。前端 fallback 模态框的银行下拉从此 RPC 读取。

**`handle_parse_pdf`（微调）**
路由逻辑保持不变，但支持 `bank` 参数透传（用户手动覆盖时从前端传入）。批量模式解析单个文件时也复用此方法。

#### 3. 数据模型

**`BatchResult`（新建 TypeScript 类型）**
```ts
interface BatchFileResult {
  filePath: string;
  fileName: string;
  bank: string;
  docType: string;
  statementDate?: string;
  status: 'success' | 'failed' | 'cancelled';
  transactions?: Transaction[];
  error?: string;
  transactionCount: number;
}

interface BatchResult {
  files: BatchFileResult[];
  totalFiles: number;
  successCount: number;
  failedCount: number;
  totalTransactions: number;
}
```

### 前端视图状态机

```
App.tsx
 ├── mode === 'single'
 │    ├── SingleFileView
 │    │    ├── FileDropZone (选文件)
 │    │    ├── ResultCard (检测/解析结果 + 3 按钮)
 │    │    ├── ManualOverrideModal (检测失败 / 解析失败 / 修改配置)
 │    │    ├── ProgressSteps (解析中)
 │    │    └── TransactionTable + 导出按钮
 │    └── SingleFileDetailView (从批量查看详情，复用上述组件)
 │
 └── mode === 'batch'
      ├── BatchFileSelector (文件列表 + [识别文件])
      ├── ManualOverrideModal (批量 fallback)
      ├── ProgressSteps (批量解析进度，阻塞)
      └── BatchResultPanel (折叠面板 + 全部导出)
```

### 关键交互时序

**单文件自动检测成功：**
```
选文件 → detect_bank(file_path) → ResultCard("检测到：招商银行 · 账务明细清单")
         → 用户点[解析] → parse_pdf(file_path) → TransactionTable + 导出按钮
```

**单文件检测失败：**
```
选文件 → detect_bank → bank=unknown → 立即弹 ManualOverrideModal
         → 用户选[工商银行 / 流水 / OCR] → 点[解析] → parse_pdf(bank=工商银行) → 结果
```

**单文件解析失败：**
```
选文件 → 检测成功 → 解析 → 0 条交易 → ResultCard("解析失败：未找到交易数据") [修改配置]
         → 点[修改配置] → ManualOverrideModal（预填当前检测值）→ 重新解析
```

**批量流程：**
```
[批量解析] → BatchFileSelector
 → [+ 添加文件] → 列表展示 → [识别文件]
 → detect_banks([...]) → 列表更新状态 → [配置并解析]
 → ManualOverrideModal（如有失败文件）→ 逐个解析
 → BatchResultPanel（折叠面板 + 全部导出）
```

---

## Testing Decisions

### 测试原则

- 只测试外部行为，不测试内部实现
- 优先测试用户可观察的结果（UI 状态、API 返回、文件输出）
- 不 mock 业务逻辑，用集成测试验证完整流程

### 待测试模块

#### 1. `bridge.py` — 后端 RPC（已有集成测试基础）

- `detect_banks`：传入多个 PDF 文件路径，验证返回结构（file_path / bank / doc_type / status 字段齐全，状态标记正确）
- `detect_supported_banks`：验证返回当前支持的银行列表
- `handle_parse_pdf`：手动覆盖 `bank` 参数时，验证路由到正确解析器（用已知的测试 PDF 文件）

参考现有测试：`apps/electron/tests/integration/ipc-methods.test.js`

#### 2. `shared_utils.py` — 工具函数（新增单元测试）

- `read_pdf_bytes` / `open_pdf`：读取测试 PDF，验证返回 bytes 和 fitz.Document
- `parse_date_*` 系列：各种日期格式（YYYYMMDD / YYYY-MM-DD / 中文 / 混合）
- `parse_amount_*` 系列：含逗号、含 ￥、负数、空值
- `extract_all_spans` / `cluster_by_y` / `partition_spans`：用测试 PDF 页面验证 span 提取和聚类

参考现有测试：`apps/electron/tests/integration/icbc-csv.test.js`（展示后端测试模式）

#### 3. 前端组件 — 手动覆盖模态框（新组件，需新增测试）

- 打开模态框时银行下拉动态加载
- 选择银行+表格类型+OCR → 点[解析] → 关闭模态框 → 触发解析
- 点[取消] → 关闭模态框 → 配置保留 → 重新打开时预填

#### 4. 批量模式端到端（新增集成测试）

- 选 3 个测试 PDF → 检测 → 展示列表 → 配置 → 解析 → 验证折叠面板展示结果
- 混入 1 个无法识别的 PDF → 验证 fallback 提示文案
- 1 个文件解析失败 → 验证跳过继续 → 失败文件标红 → 验证[重试]功能

---

## Out of Scope

- **多银行混合批量解析**：当前批量模式假设所有文件为同一银行类型，混合银行的批量子场景（如"招行文件 3 个 + 工行文件 2 个"）不在本次范围，后续迭代支持。
- **解析历史持久化**：会话级 state 仅在当前 app 生命周期内保留，关闭重开后不恢复。永久历史记录功能不纳入本次范围。
- **凭证导出增强**：金蝶精斗云凭证导出功能（`generate_voucher_excel`）已有，本次不扩展其功能。
- **账号映射导入 UI**：`account_mapping.json` 的编辑/管理不在本次范围，当前为内置 JSON 配置。
- **自动科目推断（AI）**：凭证导出文档中提到的 Phase 4 "AI 自动推断科目" 不纳入本次范围。
- **文件类型扩展**：当前只支持 PDF/CSV/Excel，不支持 TXT/OFX 等其他格式。

---

## Further Notes

### 与现有代码的兼容性

- 单文件模式的 `FileDropZone` 和 `handleFileSelected` 逻辑保持向后兼容，仅在其上方新增 `BatchFileSelector` 作为独立入口。
- `bridge.py` 的 `parse_pdf` RPC 方法保持签名不变，新增 `bank` 参数透传已支持。
- `ParseResult` 数据模型不变，新增 `BatchResult` 为纯前端类型，不涉及后端改动。

### 术语一致性

遵循 `CONTEXT.md` 定义的领域词汇：
- **文件类型（File format）**：`.pdf` / `.csv` / `.xlsx` — 由扩展名决定
- **表格类型（Doc format）**：**流水**（水平多行表格）或 **回单**（垂直单条表格）— 由文档内容布局决定
- **银行类型（Bank）**：ICBC / CMB / GFB — 由关键词检测或用户手动选择

### 关键约束

- 批量模式硬限制 5 个文件，配置在 `public/batch_config.json`
- 批量解析期间阻塞 UI，可取消但不保留中间结果
- 结果持久化为会话级（React state），不写 localStorage 或 IndexedDB
- Fallback 面板单文件和批量共用组件，动态文案和文件列表参数区分上下文
- 错误信息始终展示一句话，不提供详细错误开关
