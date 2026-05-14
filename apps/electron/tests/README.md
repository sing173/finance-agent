# 测试目录结构

本目录存放 Electron 主进程相关的测试脚本。

## 目录分类

### `integration/` 集成测试
测试 Electron 主进程与 Python 后端的完整 IPC 通信流程。

- `bridge-ipc.test.js` - 验证 JSON-RPC 2.0 连接（health 方法）
- `ipc-methods.test.js` - 完整 IPC 方法测试（health/parse_pdf/generate_excel/parse_csv）

运行方式：
```bash
cd apps/electron
node tests/integration/bridge-ipc.test.js
node tests/integration/ipc-methods.test.js
```

### `unit/` 单元测试
待补充：对独立模块（如 PythonProcessManager）的单元测试。

### `e2e/` 端到端测试
已合并到 `integration/` 目录。

## Python Bridge 可用方法

当前 `bridge.py` 注册的 JSON-RPC 方法：

| 方法 | 说明 |
|------|------|
| `health` | 返回后端状态、版本、Python 版本 |
| `parse_pdf` | 解析 PDF 银行流水或 ICBC CSV 对账流水（自动识别文件类型） |
| `parse_csv` | 直接解析 ICBC CSV 对账流水（快捷方法） |
| `generate_excel` | 将交易列表导出为 Excel 文件（.xlsx） |
| `ocr_pdf` | OCR 识别扫描件/图片型 PDF |

**文件类型路由**：
- `.csv` → 自动路由到 `ICBCCSVParser`（支持 ICBC 对账流水格式）
- `.pdf` → 自动检测银行类型和文档类型，路由到对应解析器

### ICBC CSV 解析器特性
- 编码：GBK
- 分隔符：逗号（字段内含 Tab 字符需清理）
- 输出字段：凭证号、本方账号、对方账号、交易时间、起息日、借/贷、借方发生额、贷方发生额、对方行名、摘要、附言、用途、对方单位名称、余额
- 返回额外字段：`opening_balance`、`closing_balance`（期初/期末余额）

### 前端支持的文件类型
- **PDF**（银行流水扫描件/文字型 PDF）
- **CSV**（ICBC 对账流水，`.csv`）
- **Excel**（仅导出，`.xlsx`/`.xls`）

## 测试脚本规范

- 测试文件使用 `.test.js` 后缀
- 文件名格式：`<模块>-<场景>.test.js`
- 示例：`python-process-start.test.js`

## 测试输出管理

- **输出目录**: `tests/output/`
- 测试生成的临时文件统一存放于此
- 测试结束自动清理临时文件

## 测试依赖

运行集成测试前确保：
1. Python 依赖已安装：`cd apps/python && pip install -e ".[dev]"`
2. Python bridge 可执行：配置 `PYTHON_CMD` 环境变量或使用 venv
3. 如需测试 ICBC CSV 解析：准备测试 CSV 文件（GBK 编码）
4. 如需测试 PDF 解析：准备测试 PDF 文件（银行流水）

## 测试覆盖矩阵

| 测试项 | bridge-ipc.test.js | ipc-methods.test.js | icbc-csv.test.js |
|--------|-------------------|---------------------|------------------|
| Python 进程启动 | ✅ | ✅ | ✅ |
| health 方法 | ✅ | ✅ | |
| parse_pdf 参数验证 | | ✅ | |
| parse_pdf 自动路由 CSV | | | ✅ |
| parse_csv 直接解析 | | | ✅ |
| generate_excel 参数验证 | | ✅ | |
| generate_excel 文件生成 | | ✅ | |
| ocr_pdf 方法 | | ⬜ | |
| 进程状态管理 | | ✅ | |
