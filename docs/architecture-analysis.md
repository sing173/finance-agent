# Finance Assistant 技术架构分析

> 版本: v0.2.0-productization | 日期: 2026-05-20

---

## 1. 总览

### 1.1 系统定位

Finance Assistant 是一款基于 Electron + Python 的**银行流水处理桌面应用**，核心功能为：

- 解析银行流水 PDF / CSV / Excel 文件，提取结构化交易数据
- OCR 识别扫描件回单（工商银行）
- 导出 Excel 交易明细
- 按金蝶精斗云凭证模板格式生成凭证

**不实现**对账（银行-账本匹配）功能。

### 1.2 规模概览

| 层 | 文件数 | 代码行数 | 技术栈 |
|---|---|---|---|
| Electron 主进程 | 4 | ~360 | TypeScript, Node.js |
| React 渲染进程 | 11 | ~1,400 | TypeScript, React, Ant Design, Vite |
| Python 后端 | 15 | ~4,000 | Python 3.11+, RapidOCR, PyMuPDF, openpyxl |
| 共享类型 | 1 | 117 | TypeScript |
| **合计** | **31** | **~5,600** | — |

---

## 2. 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    Electron 主进程 (main.ts)                     │
│                                                                   │
│  ┌──────────────┐   ┌─────────────────┐   ┌──────────────────┐  │
│  │  main.ts     │──▶│ pythonProcess   │──▶│ Python Bridge    │  │
│  │  (窗口创建)   │   │ Manager         │   │ (stdio JSON-RPC) │  │
│  └──────────────┘   │ (子进程生命周期)  │   └──────────────────┘  │
│         │            └─────────────────┘            │              │
│         │                                           │              │
│  ┌──────▼──────┐                          ┌─────────▼──────────┐ │
│  │  preload.ts │                          │  bridge.py         │ │
│  │  contextBridge                        │  METHOD 注册表      │ │
│  │  exposeInMainWorld('electronAPI')     │  handle_parse_pdf   │ │
│  └──────┬──────┘                          │  handle_detect_banks│ │
│         │                                 │  handle_generate_*  │ │
│  ┌──────▼──────┐   ipcMain.handle()      │  ...                │ │
│  │  ipc.ts     │◄────────────────────────│                     │ │
│  │  HANDLERS[] │                          └─────────────────────┘ │
│  │  声明式注册  │                                                  │
│  └──────────────┘                                                  │
└─────────────────────────────────────────────────────────────────┘
          │
          │ contextBridge
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   React 渲染进程 (Vite + HMR)                     │
│                                                                   │
│  ┌──────────────────────┐                                        │
│  │  App.tsx (504 行)     │  主状态机: 单文件 / 批量 模式切换       │
│  │  - single-file detect→parse→export                            │
│  │  - batch add→detect→parse→export                              │
│  └───────┬──────────────┘                                        │
│          │                                                        │
│  ┌───────▼──────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Components (7)    │  │ Hooks (2)        │  │ Ant Design       │ │
│  │ FileDropZone      │  │ useBatchOrch-    │  │ Card, Table,     │ │
│  │ ResultCard        │  │    estrator      │  │ Modal, Form,     │ │
│  │ TransactionTable  │  │ useVoucherExport │  │ message, Button  │ │
│  │ BatchFileSelector │  └─────────────────┘  └─────────────────┘ │
│  │ BatchResultPanel  │                                           │
│  │ ManualOverride-   │                                           │
│  │   Modal           │                                           │
│  │ SummaryBar        │                                           │
│  └───────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
          │
          │ JSON-RPC over stdio (每行一个 JSON 请求/响应)
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Python 后端                                 │
│                                                                   │
│  ┌────────────────────┐                                          │
│  │  bridge.py (383行)   │  JSON-RPC 2.0 方法注册表                │
│  │                     │  METHOD = {}          @register_method  │
│  └────────┬───────────┘                                          │
│           │                                                       │
│  ┌────────▼───────────┐  ┌────────────────────────────────────┐ │
│  │  parser_router.py  │  │  tools/ (11 个模块)                  │ │
│  │  - detect_bank_    │  │  ┌──────────────────────────────┐  │ │
│  │    from_pdf()      │  │  │  PDF Parser (流水)            │  │ │
│  │  - route() 分派    │  │  │  icbc_parser.py (370行)      │  │ │
│  │  - 延迟导入        │  │  │  cmb_parser.py (182行)       │  │ │
│  └────────────────────┘  │  │  cmb_table_parser.py (267行) │  │ │
│                          │  │  gfb_table_parser.py (314行) │  │ │
│                          │  │  pdf_parser.py (172行)       │  │ │
│                          │  ├──────────────────────────────┤  │ │
│                          │  │  Receipt Parser (回单)        │  │ │
│                          │  │  icbc_receipt_grid_parser.py │  │ │
│                          │  │  ─── (513行) 网格线+OCR       │  │ │
│                          │  │  icbc_receipt_parser.py      │  │ │
│                          │  │  ─── (543行) 标签锚定+OCR    │  │ │
│                          │  │  cmb_receipt_parser.py (245) │  │ │
│                          │  ├──────────────────────────────┤  │ │
│                          │  │  CSV / Excel Parser           │  │ │
│                          │  │  icbc_csv_parser.py (189行)  │  │ │
│                          │  │  cmb_excel_parser.py (283行) │  │ │
│                          │  ├──────────────────────────────┤  │ │
│                          │  │  Builder / Loader             │  │ │
│                          │  │  excel_builder.py (409行)    │  │ │
│                          │  │  subject_loader.py (120行)   │  │ │
│                          │  └──────────────────────────────┘  │ │
│                          └────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 架构总览描述

系统是一个典型的三层桌面应用架构，核心设计原则是**单一数据流方向**：所有请求从渲染进程出发，经主进程中转，最终由 Python 后端处理，结果沿原路返回。各层职责边界清晰，仅通过明确的 IPC 协议通信。

#### 顶层：Electron 主进程 — 请求路由与进程编排

主进程是系统的"中枢"，承担三项核心职责：

1. **子进程生命周期管理** — `pythonProcessManager` 负责启动、监控和终止 Python 子进程。它根据运行模式（开发/打包）自动探测 Python 可执行文件路径：开发环境使用 venv 中的 Python 解释器直接运行 `bridge.py`，打包环境启动 PyInstaller 编译的 `bridge.exe`。

2. **IPC 请求路由** — `ipc.ts` 通过一个 `HANDLERS[]` 数组声明所有 RPC 方法，数组中的每一项定义了三元组 `{channel, method, expose}`。对于标记了 Python `method` 的 handler，`ipcMain.handle()` 自动委托给 `pythonProcess.call(method, params)`；对于标记了 `method: null` 的 handler，则在 switch-case 中提供 Electron 原生实现（如文件对话框）。

3. **安全隔离** — `preload.ts` 通过 `contextBridge.exposeInMainWorld()` 将有限 API 暴露给渲染进程，确保渲染进程无法直接访问 Node.js API。暴露的 API 包括解析、检测、导出、文件选择等，每个方法内部调用 `ipcRenderer.invoke()` 发起 IPC 请求。特别地，`getFilePath` 使用 `webUtils.getPathForFile()` 解决了 `contextIsolation` 模式下拖拽文件 `File.path` 为 null 的问题。

子进程通信采用 **JSON-RPC 2.0 over stdio** 协议：Electron 端将请求序列化为单行 JSON 写入 Python 子进程的 stdin，Python 端将响应以单行 JSON 写回 stdout。`pythonProcessManager` 监听 stdout 数据流，通过换行分割和 JSON 解析，按 `id` 匹配并发请求的 Promise。

#### 中间：React 渲染进程 — 用户交互与状态管理

渲染进程是用户界面层，运行在 Vite 开发服务器上（支持 HMR 热更新）。组件树以 `App.tsx` 为根节点，它是一个**双模式状态机**：

- **单文件模式** (`mode='single'`)：处理流程从文件选择开始，自动调用 `detectBanks` 检测银行类型，展示 `ResultCard`（包含银行、文档类型、再检测/修改配置/开始解析按钮）。用户确认后调用 `parsePdf` 解析，交易数据通过 `TransactionTable` 分页展示，最后可通过 `useVoucherExport` 导出凭证。

- **批量模式** (`mode='batch'`)：通过 `useBatchOrchestrator` hook 管理一组文件的状态。文件列表由 `BatchFileSelector` 渲染，提供独立的"识别文件"和"开始解析"两个阶段按钮。检测后的结果通过 Tag 色标展示（蓝=已检测/紫=已设置/绿=成功/红=失败）。解析完成后 `BatchResultPanel` 以饼图+卡片列表呈现汇总。每个失败文件可通过 `ManualOverrideModal` 手动指定银行和文档类型后重试。

模式切换是自动的：`FileDropZone` 的 `handleFilesSelected` 根据文件数量自动决定进入单文件还是批量模式，对用户透明。

#### 底层：Python 后端 — 业务逻辑引擎

Python 后端是业务核心，运行在子进程中，通过 stdio 的逐行 JSON-RPC 循环提供服务。`bridge.py` 使用装饰器 `@register_method("name")` 将函数注册到全局 `METHODS` 字典，主循环读取 stdin → 查表 → 调用 → 写回 stdout。

请求到达后的路由链路：

1. `bridge.handle_parse_pdf()` → `parser_router.route(file_path, bank?)`
2. `route()` 按文件扩展名分发：
   - `.xlsx` → `cmb_excel_parser`（招商银行 Excel 流水）
   - `.csv` → `icbc_csv_parser`（工商银行 GBK 编码 CSV）
   - `.pdf` → 先通过 `detect_bank_from_pdf()` 读取前 3 页文本，匹配 `BANK_KEYWORDS` 识别银行和文档类型，再进入 bank-specific 的路由链
3. PDF 路由链采用**兜底策略**：从最匹配的 parser 开始尝试，逐级 fallback 到通用 parser

`detectBanks()` 独立于解析流程，专门用于批量模式下预先识别文件类型。它对每个文件调用同一个 `_detect_bank_from_pdf()` 函数，返回 `{bank, docType, status}` 三元组，不执行解析。

#### 横切：配置与模型层

`models.py` 定义了四个 dataclass：`Transaction`（交易记录）、`ParseResult`（解析结果）、`Subject`（会计科目）、`VoucherEntry`（金蝶凭证分录）。这些模型贯穿解析→导出全链路。

`base_parser.py` 提供所有 10 个 parser 的公共工具方法：Unicode 安全的 PDF 读取、ParseResult/Transaction 构造器、日期/金额解析。它不是 Template Method 模式 — 每个 parser 自由实现 `parse()` 方法，按需调用基类工具。

`shared_utils.py` 提供更细粒度的 PDF 跨度操作函数（提取、聚类、分区、余额查找），被 `base_parser` 和各个 parser 共同引用。两个模块间存在功能重叠，是 v0.2.0 待清理的技术债之一。

---

## 3. 分层详解

### 3.1 Electron 主进程 (apps/electron/src/)

#### main.ts — 应用入口 (61行)
- 开发模式 (`process.defaultApp`) → 加载 `http://localhost:5173`
- 打包模式 → 加载 `resources/renderer/index.html`
- 启动顺序: `pythonProcess.start()` → `setupIpcHandlers()` → `createWindow()`
- Python 状态事件转发: `mainWindow.webContents.send('python-status', status)`

#### preload.ts — 安全桥接 (30行)
- 通过 `contextBridge.exposeInMainWorld('electronAPI', {...})` 暴露 API 给渲染进程
- 关键 API: `parsePdf`, `detectBanks`, `generateVoucher`, `selectFile`, `getFilePath`
- `getFilePath` 使用 `webUtils.getPathForFile()` 解决拖拽文件路径（contextIsolation 下 `File.path` 为 null）

#### ipc.ts — IPC 声明式注册 (101行)
- `HANDLERS[]` 数组统一声明: channel → method → expose 映射
- 纯 Python 代理: 遍历 `HANDLERS`，有 `method` 则注册 `ipcMain.handle(channel, pythonProcess.call(method))`
- Electron 侧处理器: `select_file`, `save_file_dialog`, `get-python-status`
- 设计优势: 单一事实来源，preload 和 ipcMain 保持同步

#### pythonProcessManager.ts — 子进程生命周期 (170行)
- `PythonProcessManager` extends EventEmitter
- 职责:
  - 启动 Python bridge 子进程 (dev: venv Python, prod: 打包的 bridge.exe)
  - JSON-RPC 2.0 协议: `{jsonrpc, id, method, params}` → stdout → `{jsonrpc, id, result|error}`
  - stdout/err 多行合并处理（跟 T-UI 的 cache handler 类似）
  - 请求超时 60s
- 路径探测: `PYTHON_CMD` 环境变量 → 打包 `resources/python/bridge.exe` → dev venv Python

### 3.2 React 渲染进程 (apps/renderer/src/)

#### App.tsx — 主状态机 (504行)
- **模式**: `single` | `batch`，通过选择文件数量自动切换
- **单文件流程**: select → detect → `ResultCard` (展示检测结果) → parse → `TransactionTable` → export voucher
- **批量流程**: add files → `BatchFileSelector` → detect → parse → `BatchResultPanel` → export voucher
- **通用组件**: `ManualOverrideModal` (手动指定银行/文档类型), `FileDropZone` (入口)

#### Components (7个)

| 组件 | 行数 | 职责 |
|---|---|---|
| `FileDropZone` | 93 | 拖拽/点击选择文件，多文件支持 |
| `ResultCard` | 147 | 单文件检测/解析结果卡片 |
| `TransactionTable` | 119 | 分页交易列表 (Ant Design Table) |
| `BatchFileSelector` | 210 | 批量文件列表，添加/删除/识别/解析按钮 |
| `BatchResultPanel` | 171 | 批量结果汇总 (饼图 + 文件卡片) |
| `ManualOverrideModal` | 130 | 手动配置银行+文档类型 (单文件/批量共用) |
| `SummaryBar` | 102 | 统计摘要条 (总计/收入/支出) |

#### Hooks (2个)

| Hook | 行数 | 职责 |
|---|---|---|
| `useBatchOrchestrator` | 314 | 批量模式状态机: files[], phase(idle/detecting/parsing), detectOnly, parseOnly, retryFailedFiles |
| `useVoucherExport` | 70 | 统一凭证导出逻辑: 打开模态框 → 设置 period → saveFileDialog → generateVoucher |

### 3.3 共享类型 (shared/types.ts, 117行)

定义 IPC 契约类型:
- `JSONRPCRequest<T>`, `JSONRPCResponse<T>` — RPC 包装
- `ParsePDFParams`, `ParsePDFResult` — parse_pdf 入参/出参
- `Transaction` — 交易记录 (date, amount, direction, counterparty 等)
- `DetectFileResult`, `DetectBanksResult` — 批量检测
- `BatchFileResult`, `BatchResult` — 批量解析
- `ChatParams` — 预留 (未实现)

**注意**: 目前 Python 端不 import 此 TypeScript 文件 — 两边的类型通过约定保持同步，有参数名不匹配的风险（如之前的 `file_paths` vs `filePaths`）。

### 3.4 Python 后端

#### bridge.py — JSON-RPC 服务端 (383行)
- 注册表 `METHODS` + `@register_method` 装饰器
- 主循环: `for line in sys.stdin` → `handle_request()` → `sys.stdout.write(JSON line)`
- 同步版本（单线程，逐行处理）
- 日志: RotatingFileHandler, 10MB × 3, 写入 `logs/bridge.log`

**注册的方法 (10个)**:

| 方法 | 说明 |
|---|---|
| `health` | 健康检查 |
| `parse_pdf` | PDF/CSV/Excel 解析 (统一入口) |
| `parse_csv` | [DEPRECATED] ICBC CSV 解析 |
| `generate_excel` | 导出交易明细 Excel |
| `generate_voucher_excel` | 导出金蝶凭证 Excel |
| `import_subjects` | 导入科目表 |
| `get_subjects_info` | 查询科目表信息 |
| `detect_banks` | 批量检测银行类型 |
| `detect_supported_banks` | 查询支持的银行列表 |

#### parser_router.py — 路由分发 (281行)
- `route(file_path, bank?)` 分发:
  - `.xlsx` → CMB Excel Parser
  - `.csv` → ICBC CSV Parser
  - `.pdf` → bank detection → bank-specific parser chain
- `detect_bank_from_pdf()`: 前3页文本 → `BANK_KEYWORDS` 匹配 → `_classify()` 判断银行+文档类型
- PDF 路由策略:
  ```
  扫描件/receipt/未知 → 先试 ICBCReceiptGridParser
  ├─ 失败 → ICBCParser (流水)
  ├─ 招商 + receipt → CMBReceiptParser
  ├─ 招商 + table → CMBTableParser
  ├─ 招商 + column → CMBParser
  ├─ 广发 → GFBTableParser
  └─ 全部失败 → BankStatementParser (通用)
  ```

#### models.py — 数据模型 (103行)
- `Transaction`: date, description, amount (Decimal), direction, counterparty, reference_number, notes, account_number/name
- `ParseResult`: transactions[], bank, statement_date, opening/closing_balance, confidence, errors/warnings
- `Subject`: 会计科目定义 (code, name, category, direction, is_cash, enabled)
- `VoucherEntry`: 金蝶凭证导入模板的 25 列

#### base_parser.py — 解析器基类 (144行)
- `_read_pdf_bytes()` / `_open_pdf()` — Unicode 安全的 PDF 读取
- `_build_result()` / `_build_transaction()` — 构造 ParseResult / Transaction
- `_parse_date()` / `_parse_amount()` / `_parse_amount_lenient()` — 日期/金额解析
- `BANK_NAME` 类属性，parse() 由子类自由实现（非 Template Method）

#### tools/shared_utils.py — 共享工具 (313行)
- 银行名常量: `BANK_ICBC`, `BANK_CMB`, `BANK_GFB`, `BANK_BOC`, `BANK_CCB`
- PDF I/O: `read_pdf_bytes()`, `open_pdf()` — helper 中也有，与 base_parser 重复
- 日期解析: 5 个变体 (`parse_date_yyyymmdd`, `parse_date_chinese`, `parse_date_iso`, `parse_date_flexible`, `parse_timestamp_date`)
- 金额解析: 3 个变体 (`parse_amount`, `parse_amount_lenient`, `parse_amount_clean`)
- PDF 跨度提取: `extract_all_spans()`, `cluster_by_y()`, `find_table_region()`, `partition_spans()`
- 余额/数值查找: `find_nearby_number()`, `find_nearby_value()`, `find_balance_in_spans()`, `extract_balance_from_footer()`
- 表头键标准化: `normalize_key()`, `lookup_header_key()`

### 3.5 PDF 解析器体系 (10个)

| Parser | 行数 | 银行 | 文档类型 | 技术方案 |
|---|---|---|---|---|
| `icbc_parser` | 370 | 工商银行 | 流水 (statement) | PyMuPDF 跨度 + 网格线 + 坐标空间 |
| `icbc_receipt_parser` | 543 | 工商银行 | 回单 (receipt) | OCR + 标签锚定 + 空间近邻 |
| `icbc_receipt_grid_parser` | 513 | 工商银行 | 回单 (receipt) | OCR + 网格线检测 + 单元格映射 |
| `icbc_csv_parser` | 189 | 工商银行 | CSV 对账流水 | GBK 编码 CSV, Tab 分隔 |
| `cmb_parser` | 182 | 招商银行 | 流水 (旧格式) | 列对齐 PDF 解析 |
| `cmb_table_parser` | 267 | 招商银行 | 账务明细清单 | 表格格式 PDF |
| `cmb_receipt_parser` | 245 | 招商银行 | 回单 | 标签值对提取 |
| `cmb_excel_parser` | 283 | 招商银行 | Excel 流水 | .xlsx 读取 + 列映射 |
| `gfb_table_parser` | 314 | 广发银行 | 流水 | 表格格式 PDF |
| `pdf_parser` | 172 | 通用 | 未知银行回退 | HTML 提取 + 正则匹配 |

**两个工商银行回单解析器的差异**:

| 维度 | receipt_parser (标签锚定) | receipt_grid_parser (网格线) |
|---|---|---|
| 核心策略 | OCR → 标签关键词匹配 → 右侧值提取 | OCR + CV 网格线检测 → 固定列映射 |
| 回单分割 | "网上银行电子回单" 锚点 | 标题行+数据行动态切分 |
| 适用场景 | 格式变化大的回单 | 网格线清晰的标准回单 |
| 可靠性 | 对 OCR 字序敏感，标签匹配脆弱 | 对网格线完整性依赖强 |

### 3.6 OCR 管线

当前 OCR 全部用于工商银行回单识别，依赖链:
```
RapidOCR (ONNX Runtime)
  └── icbc_receipt_parser.py          (标签锚定方案)
  └── icbc_receipt_grid_parser.py     (网格线方案)
```

OCR 流程: PDF 页 → PyMuPDF 高 dpi 渲染 → PIL 转灰度 → OpenCV 二值化 → RapidOCR → 文字块列表

需要的 ONNX 模型文件: `rapidocr_onnxruntime` 的默认模型（Chinese text recognition）

PyInstaller 打包注意: 模型文件必须在 `.spec` 的 `datas` 中显式声明。

---

## 4. 数据流

### 4.1 单文件解析完整流程

```
用户选择文件
  │
  ▼
FileDropZone (拖拽/点击)
  │  filePaths[]
  ▼
App.handleFilesSelected()
  │  filePaths.length === 1 → single mode
  ▼
App.handleSingleFileDetect(filePath)
  │  window.electronAPI.detectBanks([filePath])
  ▼
preload.detectBanks → ipcMain.handle('detect_banks')
  │  pythonProcess.call('detect_banks', {filePaths})
  ▼
bridge.handle_detect_banks()
  │  对每个 .pdf 文件: _detect_bank_from_pdf(fp)
  ▼
{"success": true, "results": [{filePath, bank, docType, status}]}
  │
  ▼
App.setState: detectState='detected', detectInfo={bank, docType}
  │
  ▼
ResultCard 渲染 → 用户点击 "开始解析"
  │
  ▼
App.handleSingleFileParse(filePath, bank, docType)
  │  window.electronAPI.parsePdf({filePath, bank, docType})
  ▼
preload.parsePdf → ipcMain.handle('parse_pdf')
  │  pythonProcess.call('parse_pdf', params)
  ▼
bridge.handle_parse_pdf()
  │  parser_router.route(file_path, bank)
  ▼
parser_router: 扩展名分派 (.pdf/.csv/.xlsx) → bank-specific parser
  │
  ▼
ParseResult → _serialize_result() → JSON-safe dict
  │
  ▼
{"success": true, transactions: [...], bank, statementDate, ...}
  │
  ▼
App.setState: currentResult, detectState='detected'
  │
  ▼
TransactionTable 渲染交易列表
  ↓
用户点击 "导出凭证"
  │
  ▼
useVoucherExport.exportVoucher(txns)
  │  saveFileDialog → window.electronAPI.generateVoucher({transactions, period})
  │
  ▼
Excel 文件写入磁盘 → 成功消息
```

### 4.2 批量解析流程

```
用户选择多个文件 / 拖拽多个文件
  │  filePaths[]
  ▼
App.handleFilesSelected()
  │  filePaths.length > 1 → batch mode
  ▼
batch.addFiles(filePaths)  // useBatchOrchestrator
  │  setFiles([...prev, newFiles])
  ▼
BatchFileSelector 渲染文件列表
  │  用户点击 "识别文件"
  ▼
batch.detectOnly()
  │  phase='detecting' → detectBanks(all filePaths)
  │  → setFiles 更新 bank/docType
  │  → phase='idle', detectDone=true
  ▼
BatchFileSelector: 每个文件显示检测结果 Tag
  │  用户可逐个 "修改配置" (ManualOverrideModal)
  │  用户点击 "开始解析"
  ▼
batch.parseOnly()
  │  phase='parsing' → 逐文件 parsePdf()
  │  → setFiles(results)
  │  → onComplete callback → setBatchResult
  ▼
BatchResultPanel 渲染
  │  饼图: success / failed
  │  文件卡片: bank, docType, 交易数, 状态
  ▼
用户点击 "导出凭证"
  │  → 合并所有成功文件的 transactions
  │  → useVoucherExport.exportVoucher(allTxns)
```

---

## 5. 当前架构问题

### 5.1 代码重复 (P1)

- **`shared_utils.py` 与 `base_parser.py` 功能重叠**: PDF I/O (`read_pdf_bytes`/`_read_pdf_bytes`)、日期金额解析函数在两边各有一套。部分 parser 用 `shared_utils`，部分用 `base_parser`，风格不统一。
- **两个 ICBC 回单解析器** (543 + 513 = 1,056 行): `receipt_parser` 和 `receipt_grid_parser` 共享大量 OCR 渲染逻辑、Transaction 构造、日期/金额解析，但各自维护一套实现。
- **日期金额解析函数膨胀**: `shared_utils` 中 5 个 date parse 函数 + 3 个 amount parse 函数，语义重叠，使用不一致。

### 5.2 类型系统断层 (P1)

- Python 和 TypeScript 类型定义**完全独立**，通过约定同步。已有的参数名不匹配 bug (`file_paths` vs `filePaths`) 是典型后果。
- `shared/types.ts` 中的 TypeScript 类型在 Python 端没有对应物。
- 建议: 生成 JSON Schema 或 Protobuf 作为中间契约。

### 5.3 错误处理不统一 (P2)

- Parser 层级: 有 catch 但错误信息粒度不一，前端只能展示原始 error string
- Bridge 层: `handle_request()` 统一 catch → `{"error": {"code": -32603, "message": str(e)}}`，但 Parser 内部的错误分类丢失
- 前端层: `message.error()` 展示但无错误恢复指引
- **缺少错误码体系**: 无法区分"文件损坏" vs "格式不支持" vs "OCR 失败"

### 5.4 bridge.py 膨胀 (P2)

- 383 行: 包含方法注册、RPC 协议、科目管理、CSV 解析 legacy 方法
- `_parse_icbc_csv()` 逻辑重复 — parser_router 已能处理 CSV
- 建议: 科目管理提取到独立模块，CSV legacy 方法移到 parser_router 或删除

### 5.5 App.tsx 状态管理复杂度 (P2)

- 504 行: 2 种模式、8 个 useState、回调链长
- `handleFilesSelected` → `handleSingleFileDetect` / `batch.addFiles` 的嵌套调用难以追踪
- `overrideContext.onConfirm` 闭包捕获当前状态，未来变更容易引入 bug
- 建议: 用 `useReducer` 或提取单文件模式为独立 hook

### 5.6 useBatchOrchestrator 状态闭包 (P1)

- `detectOnly` / `parseOnly` 依赖 `[files, phase]` useCallback，在高频操作中可能用过期状态
- `retryFailedFiles` 用空依赖数组 `[]` — 内部的 `setFiles` 使用 updater 形式规避了部分问题，但 `phase` 未复位时的竞态仍存在
- 建议: 改用 `useReducer` 保证原子状态更新

### 5.7 测试覆盖不足 (P3)

- 无 Python 单元测试（`pytest` 目录存在但为空）
- Electron 集成测试 7 个文件，但覆盖限于 happy path
- Parser 层的解析正确性依赖人工验证
- 无前端组件测试

### 5.8 PDF I/O 路径重复 (P3)

- `base_parser._read_pdf_bytes()` / `_open_pdf()`
- `shared_utils.read_pdf_bytes()` / `open_pdf()`
- `icbc_receipt_grid_parser` 自己的 `_open_pdf()`
- 三处实现完全相同，应在 `base_parser` 中统一并让其他模块 import

---

## 6. v0.2.0 推荐优化路线

### 第一阶段: 质量基础 (本周)

1. **统一 shared_utils → base_parser**: 删除 shared_utils 中与 base_parser 重复的函数，让所有 parser 统一从 base_parser import。预计减少 ~80 行重复代码。

2. **合并 ICBC 回单解析器**: 提取共享 OCR 渲染管线到 `base_parser` 或 `shared_ocr_utils.py`，`receipt_parser` 和 `receipt_grid_parser` 只保留各自的回单分割+字段提取策略。预计减少 ~200 行重复代码。

3. **类型契约化**: 从 `shared/types.ts` 生成 JSON Schema，bridge.py 端加参数校验（用 `jsonschema` 库），自动捕获参数名不匹配。

### 第二阶段: 错误体系 (下周)

4. **错误码体系**: 定义 `ErrorCode` enum (FILE_NOT_FOUND, UNSUPPORTED_FORMAT, OCR_FAILED, PARSE_FAILED 等)，所有 parser 统一返回 `{success, error_code, error_message}`。

5. **bridge.py 瘦身**: 提取 `handle_load_subjects` 和相关到 `subject_manager.py`，移除 `parse_csv` legacy 方法。

6. **App.tsx 重构**: 单文件模式提取为 `useSingleFileParser` hook，批量和单文件共享底层 `useFileParser` 原语。

### 第三阶段: 长期改进

7. **Python 测试**: 为每个 parser 写参数化 pytest（样本 PDF 测试集）
8. **前端测试**: React Testing Library 覆盖关键交互
9. **配置外部化**: Bank-specific 解析规则移到 config YAML/JSON
10. **性能**: OCR 管线惰性加载 + PDF page 按需渲染 + Textract 流式处理

---

## 7. 关键文件索引

| 文件 | 作用 | 风险等级 |
|---|---|---|
| `bridge.py` | JSON-RPC 入口，所有 IPC 在此路由 | 高 — 单点故障 |
| `parser_router.py` | PDF/CSV/Excel 分发，bank 检测 | 高 — 路由错误 = 零结果 |
| `pythonProcessManager.ts` | 子进程生命周期 | 高 — crash 则全挂 |
| `App.tsx` | 前端状态机 | 中 — 复杂度高，改动风险大 |
| `useBatchOrchestrator.ts` | 批量编排 | 中 — 状态闭包问题 |
| `excel_builder.py` | 凭证导出 | 中 — 金蝶格式依赖 |
| `icbc_receipt_grid_parser.py` | OCR 主线 | 低 — 独立模块，变更影响小 |

---

## 8. 配置 & 资源

| 文件 | 用途 |
|---|---|
| `apps/python/.../config/subjects.json` | 内置科目字典 |
| `apps/python/.../config/subject_mapping.json` | 科目映射规则 (关键字→科目代码) |
| `apps/python/.../config/account_mapping.json` | 账号映射规则 (账号后缀→银行科目) |
| `apps/renderer/public/batch_config.json` | 批量模式最大文件数 (默认5) |
| `apps/python/bridge.spec` | PyInstaller 打包配置 |
| `logs/bridge.log` | Python 后端日志 (10MB×3) |

---

## 附录 A: 模块依赖图 (Python Parser)

```
bridge.py
├── excel_builder (ExcelBuilder)
│   └── models (Transaction, Subject, VoucherEntry)
├── subject_loader (SubjectLoader)
│   └── models (Subject)
├── parser_router
│   ├── shared_utils (bank constants, parse functions)
│   ├── base_parser (BaseStatementParser)
│   └── tools/
│       ├── cmb_excel_parser ──▶ base_parser + shared_utils
│       ├── icbc_csv_parser  ──▶ base_parser + shared_utils
│       ├── icbc_parser      ──▶ base_parser + shared_utils
│       ├── icbc_receipt_parser ──▶ base_parser + shared_utils + RapidOCR
│       ├── icbc_receipt_grid_parser ──▶ base_parser + shared_utils + RapidOCR
│       ├── cmb_parser       ──▶ base_parser + shared_utils
│       ├── cmb_table_parser ──▶ base_parser + shared_utils
│       ├── cmb_receipt_parser ──▶ base_parser + shared_utils
│       ├── gfb_table_parser ──▶ base_parser + shared_utils
│       └── pdf_parser       ──▶ base_parser + shared_utils
└── models (Transaction, ParseResult, Subject)
```

## 附录 B: 前端组件依赖图

```
App.tsx
├── FileDropZone ──▶ electronAPI.selectFile / electronAPI.getFilePath
├── ResultCard (单文件)
│   └── (用户操作) → electronAPI.parsePdf / electronAPI.detectBanks
├── TransactionTable
├── BatchFileSelector
│   └── (用户操作) → useBatchOrchestrator
├── BatchResultPanel
├── ManualOverrideModal (单文件+批量共用)
├── SummaryBar
├── useBatchOrchestrator
│   └── electronAPI.detectBanks / electronAPI.parsePdf
└── useVoucherExport
    └── electronAPI.saveFileDialog / electronAPI.generateVoucher
```