# 测试目录结构

本目录存放 Electron 主进程相关的测试脚本。

## 目录分类

### `integration/` 集成测试
测试 Electron 主进程与 Python 后端的完整 IPC 通信流程。

- `bridge-ipc.test.js` - 验证 JSON-RPC 2.0 连接（health 方法）
- `ipc-methods.test.js` - 完整 IPC 方法测试（health/parse_pdf/generate_excel）

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
