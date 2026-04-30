# Electron + Python 打包路径优化方案

> 本文档描述 Finance Assistant 项目中 Electron 主进程调用 Python 后端的跨环境路径解析方案，支持开发、测试和打包三种场景。

---

## 一、问题背景

在 Electron + Python 混合架构应用中，Python 后端作为子进程由 Electron 主进程通过 `child_process.spawn` 启动。不同环境下的路径差异导致打包后应用无法找到 Python bridge：

| 环境 | Python 可执行文件位置 | 调用方式 | 问题 |
|------|---------------------|---------|------|
| 开发环境 | 系统 Python（如 `D:\Python312\python.exe`） | `spawn('python', ['.../bridge.py'])` | 需硬编码路径，不跨平台 |
| 打包环境 | `resources/python/bridge.exe`（PyInstaller 打包） | `spawn('.../bridge.exe', [])` | 路径动态变化，需解析 `process.resourcesPath` |
| 测试环境 | 虚拟环境内的 Python | `spawn('.../.venv/Scripts/python.exe', [...])` | 需支持自定义路径 |

**原有问题**：`pythonProcessManager.ts` 中硬编码 `D:/Python312/python.exe` 导致：
- 其他开发者无法运行（Python 安装位置不同）
- 打包后路径错误（应为 `resources/python/bridge.exe`）
- 跨平台支持差（macOS/Linux 路径不同）

---

## 二、解决方案架构

引入 `pathUtils.ts` 工具模块，根据运行环境动态计算 Python 启动配置：

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron Main Process                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐     ┌──────────────────────┐         │
│  │  pythonProcess   │ ──▶ │  getPythonSpawnConfig│        │
│  │   Manager.ts     │     │      (pathUtils)     │         │
│  └──────────────────┘     └──────────────────────┘         │
│           │                             │                  │
│           │  {cmd, args, cwd}           │ 环境检测          │
│           └─────────────────────────────┼──────────────┐   │
│                                          │              │   │
│                               ┌──────────▼──┐   ┌──────▼──────┐
│                               │ isElectron   │   │ process.env │
│                               │ Packaged()   │   │ .PYTHON_CMD │
│                               └──────────────┘   └─────────────┘
│                                          │
│                       ┌──────────────────┴──────────────┐
│                       │                                  │
│              ┌────────▼──────────┐           ┌───────────▼──────────┐
│              │ 打包环境           │           │ 开发/测试环境        │
│              │ (Packaged)        │           │ (Development)       │
│              │                   │           │                     │
│              │ 资源路径：         │           │ Python命令：         │
│              │ process.resourcesPath           │ 'python' (Win)      │
│              │  / 'python/bridge.exe'          │ 'python3' (Unix)    │
│              │ 参数：[]           │           │ 参数：['bridge.py']  │
│              │ 工作目录：同 bridge.exe          │ 工作目录：python/src/│
│              └───────────────────┘           └─────────────────────┘
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、核心文件说明

### 3.1 `apps/electron/src/pathUtils.ts`

**作用**：路径解析工具模块，根据运行环境返回 `spawn` 启动配置。

**关键函数**：

```typescript
export function getPythonSpawnConfig(): {
  cmd: string;    // Python可执行文件路径或命令
  args: string[]; // 传递给Python的参数数组
  cwd: string;    // 工作目录
}
```

**环境检测逻辑**：

1. **PYTHON_CMD 环境变量**（最高优先级）
   - 格式：`PYTHON_CMD=python` 或 `PYTHON_CMD=D:\Python\python.exe` 或 `PYTHON_CMD=.../bridge.exe`
   - 若值以 `.exe` 结尾或是绝对路径，视为已打包的 `bridge.exe`，直接运行
   - 否则视为系统 Python 命令，配合 `bridge.py` 脚本使用

2. **打包环境检测**（`isElectronPackaged()`）
   - 检查 `process.execPath` 是否包含 `app.asar`（asar 包）
   - 检查 `process.execPath` 是否以 `.exe` 结尾且不是 `node.exe`
   - 检查 `process.defaultApp` 是否存在
   - 打包后 `resourcesPath` 指向 `.../resources` 目录

3. **开发环境**（默认）
   - Windows：`python`
   - macOS/Linux：`python3`
   - 脚本路径：`.../apps/python/src/finance_agent_backend/bridge.py`

### 3.2 `apps/electron/src/pythonProcessManager.ts`

**改动**：使用 `getPythonSpawnConfig()` 替代硬编码路径

```typescript
import { spawn } from 'child_process';
import { getPythonSpawnConfig } from './pathUtils';

const pythonConfig = getPythonSpawnConfig();

export class PythonProcessManager {
  start() {
    if (this.process) return;

    console.log(`[Python] Starting: ${pythonConfig.cmd} ${pythonConfig.args.join(' ')}`);

    this.process = spawn(pythonConfig.cmd, pythonConfig.args, {
      cwd: pythonConfig.cwd,
    });

    // ... 标准输出/错误处理
  }
}
```

### 3.3 `apps/python/bridge.spec`

**作用**：PyInstaller 打包配置，将 Python 后端编译为独立 `bridge.exe`。

```python
from PyInstaller.building.build_main import Analysis, PYZ, EXE

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    ...,
    name='bridge',
    console=True,  # 必须保留控制台，用于 stdio 通信
)
```

**输出**：`apps/python/dist/bridge.exe`

### 3.4 `apps/electron/package.json`

**新增脚本**：

```json
{
  "scripts": {
    "package:python": "cd ../python && pyinstaller bridge.spec --onefile --clean",
    "package:all": "npm run package:python && npm run package"
  }
}
```

**electron-builder 配置**：

```json
{
  "build": {
    "appId": "com.finance-assistant.app",
    "productName": "FinanceAssistant",
    "directories": { "output": "../../release" },
    "files": [
      "dist/**/*.js",          // 所有编译后的JS文件
      "node_modules/**/*",     // 依赖模块
      "package.json"
    ],
    "asarUnpack": [
      "dist/main.js",
      "dist/ipc.js",
      "dist/preload.js",
      "dist/pythonProcessManager.js",
      "dist/pathUtils.js"
      // 注意：新增的被主进程 require 的模块也需在此添加
    ],
    "extraResources": [
      {
        "from": "../../apps/python/dist/bridge.exe",
        "to": "python/bridge.exe"
      }
    ],
    "win": {
      "target": [{ "target": "nsis", "arch": ["x64"] }]
    },
    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true,
      "createDesktopShortcut": true,
      "createStartMenuShortcut": true
    }
  }
}
```

**关键配置说明**：

| 配置项 | 作用 |
|--------|------|
| `files` | 指定打包进 `app.asar` 的文件模式。使用 `dist/**/*.js` 通配符自动包含所有编译后的主进程和渲染进程文件 |
| `asarUnpack` | 指定从 asar 压缩包中解压到 `app.asar.unpacked/` 的文件。**主进程文件必须解压**，因为 asar 虚拟文件系统的模块解析（`require()`）在某些路径计算场景下会失败 |
| `extraResources` | 指定额外资源文件（不编译进 asar），复制到 `resources/` 目录。用于存放 `bridge.exe` 等外部依赖 |

**asarUnpack 的必要性**：
- 主进程使用 `__dirname` 计算路径（如 `path.resolve(__dirname, '...')`）
- asar 模式下 `__dirname` 指向虚拟路径（如 `app.asar/dist/`），`path.resolve` 可能解析失败
- 解压后文件在真实文件系统（`app.asar.unpacked/dist/`），路径计算稳定

**新增文件的 asarUnpack 维护**：
- 新增 **被主进程 require 的模块** → 需要手动添加到 `asarUnpack` 数组
- 新增 **渲染进程模块**（React 组件）→ 由 Vite 打包，自动处理，无需添加

---

## 四、环境适配逻辑详解

### 4.1 开发环境（默认）

**条件**：未检测到 Electron 打包特征，且未设置 `PYTHON_CMD`

**路径计算**：

```
electron/dist/main.js (运行目录)
    ↓ __dirname = D:\git\finance-agent\apps\electron\dist
    ↓ path.resolve(__dirname, '..', '..', 'python', ...)
    ↓
D:\git\finance-agent\apps\python\src\finance_agent_backend\bridge.py
```

**Spawning**：

```bash
python D:\git\finance-agent\apps\python\src\finance_agent_backend\bridge.py
# cwd = D:\git\finance-agent\apps\python\src\finance_agent_backend
```

**优势**：
- 直接使用开发者已安装的 Python 环境
- 可配合虚拟环境调试（设置 `PYTHON_CMD=.\\.venv\\Scripts\\python.exe`）
- 无需预先打包 Python 后端

### 4.2 打包环境

**条件**：`isElectronPackaged()` 返回 `true`

**检测实现**：

```typescript
function isElectronPackaged(): boolean {
  const execPath = process.execPath;
  // 情况1：asar 打包（Mac/Linux）
  if (execPath.includes('app.asar')) return true;
  // 情况2：Windows .exe（且不是 node.exe）
  if (execPath.endsWith('.exe') && !execPath.includes('node.exe')) return true;
  // 情况3：Electron defaultApp 标志
  if (process.defaultApp) return true;
  return false;
}
```

**路径计算**：

```
用户安装位置（示例）：
C:\Program Files\FinanceAssistant\FinanceAssistant.exe
    ↓ process.execPath
    ↓ process.resourcesPath = C:\Program Files\FinanceAssistant\resources
    ↓ path.join(resourcesPath, 'python', 'bridge.exe')
    ↓
C:\Program Files\FinanceAssistant\resources\python\bridge.exe
```

**Spawning**：

```bash
# 直接运行 bridge.exe（已包含所有依赖）
C:\Program Files\FinanceAssistant\resources\python\bridge.exe
# cwd = C:\Program Files\FinanceAssistant\resources\python
```

**优势**：
- 无需用户额外安装 Python 环境
- 所有依赖已打包进 `bridge.exe`
- 路径由 electron-builder 的 `extraResources` 机制保证

### 4.3 自定义环境（PYTHON_CMD）

**用途**：调试、CI/CD、特殊部署场景

**用法示例**：

```bash
# Windows：指定Python虚拟环境
set PYTHON_CMD=D:\git\finance-agent\apps\python\.venv\Scripts\python.exe
npm run dev

# 直接使用已打包的bridge.exe调试
set PYTHON_CMD=apps\python\dist\bridge.exe
npm run dev

# macOS/Linux
export PYTHON_CMD=/usr/local/bin/python3
npm run dev
```

**逻辑**：
- 若 `PYTHON_CMD` 以 `.exe` 结尾或为绝对路径 → 视为 `bridge.exe`（无参数）
- 否则 → 视为系统 Python 命令，自动拼接 `bridge.py` 路径

---

## 五、打包流程完整步骤

### 5.1 前置准备

确保已安装：
- Node.js ≥ 18
- Python ≥ 3.11（开发用）
- PyInstaller（在 Python venv 中）

```bash
cd apps/python
.venv\Scripts\pip install pyinstaller
```

### 5.2 开发调试

```bash
# 启动Python后端（单独终端，可选）
cd apps/python
.venv\Scripts\python src/finance_agent_backend/bridge.py

# 启动Electron（会自动spawn Python）
cd apps/electron
npm run dev
```

### 5.3 完整打包

```bash
# 方式1：分步打包
cd apps/electron
npm run package:python   # 1. 打包Python为bridge.exe
npm run package          # 2. 打包Electron（自动复制bridge.exe）

# 方式2：一键打包
cd apps/electron
npm run package:all

# 输出位置：release/FinanceAssistant Setup 0.1.0.exe
```

### 5.4 打包产物结构

```
release/
└── FinanceAssistant Setup 0.1.0.exe  # NSIS安装包

# 安装后的目录结构：
C:\Program Files\FinanceAssistant\
├── FinanceAssistant.exe           # Electron主程序
├── resources\
│   ├── app.asar                   # Electron应用代码（压缩）
│   └── python\
│       └── bridge.exe             # Python后端（已打包）
└── ...
```

**关键机制**：`extraResources` 配置将 `apps/python/dist/bridge.exe` 复制到安装包的 `resources/python/` 目录，运行时通过 `process.resourcesPath` 找到它。

---

## 六、验证方法

### 6.1 开发模式验证

```bash
cd apps/electron
node -e "
const { pythonProcess } = require('./dist/pythonProcessManager');
pythonProcess.start();
setTimeout(async () => {
  const r = await pythonProcess.call('health', {});
  console.log('✅', r.status, 'v'+r.version);
  process.exit(0);
}, 1500);
"
```

**预期输出**：
```
[Python] Starting: python D:\...\bridge.py
✅ ok v0.1.0
```

### 6.2 打包模式验证（模拟）

```bash
cd apps/electron
node -e "
// 模拟打包环境变量
process.execPath = 'C:\\Program Files\\FinanceAssistant\\FinanceAssistant.exe';
process.resourcesPath = 'C:\\Program Files\\FinanceAssistant\\resources';

const { getPythonSpawnConfig } = require('./dist/pathUtils');
const cfg = getPythonSpawnConfig();
console.log('cmd:', cfg.cmd);
console.log('args:', cfg.args);
console.log('cwd:', cfg.cwd);
"
```

**预期输出**：
```
cmd: C:\Program Files\FinanceAssistant\resources\python\bridge.exe
args: []
cwd: C:\Program Files\FinanceAssistant\resources\python
```

### 6.3 完整UI测试

```bash
# 1. 启动应用
cd apps/electron
npm run dev

# 2. 在UI中点击"测试连接"按钮
# 3. 预期：显示 "正常 (v0.1.0)" 和绿色成功提示
```

### 6.4 打包后安装测试

```bash
# 1. 运行生成的安装包
release/FinanceAssistant Setup 0.1.0.exe

# 2. 安装后启动应用
# 3. 点击"测试连接"应同样成功（无需系统安装Python）
```

---

## 七、常见问题与排查

### Q1: 打包后应用启动报错 "找不到 bridge.exe"

**原因**：`extraResources` 配置错误或打包中断

**排查**：
1. 检查 `apps/python/dist/bridge.exe` 是否存在
2. 检查 `package.json` 中 `extraResources.from` 路径是否正确
3. 重新运行 `npm run package:python` 确保 bridge.exe 生成
4. 查看 electron-builder 日志确认文件复制成功

### Q2: 开发模式下找不到 Python

**原因**：`PYTHON_CMD` 未设置且系统 PATH 中无 `python` 命令

**解决**：
```bash
# 显式设置
set PYTHON_CMD=D:\Python312\python.exe
# 或
set PYTHON_CMD=.\\.venv\\Scripts\\python.exe
```

### Q3: 打包后的 bridge.exe 一闪而过

**原因**：PyInstaller 打包时 `console=False` 或 bridge.py 异常退出

**排查**：
1. 确保 `bridge.spec` 中 `console=True`
2. 手动测试 bridge.exe：
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"health","params":{}}' | dist/bridge.exe
   ```
3. 检查 `bridge.py` 是否有未捕获异常

### Q4: macOS/Linux 打包路径分隔符问题

**处理**：`pathUtils.ts` 使用 Node.js `path` 模块，自动适配平台：
- Windows：`C:\...\bridge.exe`
- macOS：`/Applications/.../bridge`（无 `.exe` 后缀）

**注意**：PyInstaller 在非 Windows 平台输出无后缀的可执行文件，需调整 `bridge.spec` 中的 `name='bridge'` 即可。

### Q5: 多架构打包（arm64/x64）

**配置**：在 `package.json` 的 `build.win.target` 中添加多架构：

```json
{
  "win": {
    "target": [
      { "target": "nsis", "arch": ["x64"] },
      { "target": "nsis", "arch": ["arm64"] }
    ]
  }
}
```

**Python 桥接**：需为各架构分别运行 PyInstaller（在对应 Python 环境中）。

---

## 八、扩展：多进程架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron Renderer (React)                │
│                    通过 preload.js 暴露 API                  │
│                 window.electronAPI.health()                  │
└────────────────────────────┬────────────────────────────────┘
                             │ IPC (ipcRenderer.invoke)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              Electron Main Process (Node.js)                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ipcMain.handle('health') → pythonProcess.call()    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  pythonProcessManager (pathUtils + spawn)           │  │
│  │  ├─ 开发模式： spawn('python', ['bridge.py'])       │  │
│  │  └─ 打包模式： spawn('bridge.exe', [])              │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────┘
                             │ stdio (JSON-RPC 2.0)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│          Python Bridge (bridge.py / bridge.exe)             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  接收 stdin JSON-RPC → dispatch → 返回 stdout JSON   │  │
│  │  @register_method('health') → handle_health()       │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  finance_agent_backend.agent (nanobot Agent)        │  │
│  │  @tool 装饰的业务逻辑：parse_pdf, reconcile, chat   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 九、快速参考

| 场景 | 命令 | 关键文件 |
|------|------|---------|
| 开发调试 | `npm run dev` | `pathUtils.ts` 开发分支 |
| 打包Python | `npm run package:python` | `bridge.spec` |
| 打包Electron | `npm run package` | `package.json` build 配置 |
| 一键打包 | `npm run package:all` | - |
| 自定义Python | `PYTHON_CMD=... npm run dev` | 环境变量 |
| 手动测试IPC | `node tests/integration/bridge-ipc.test.js` | `tests/integration/` |

---

## 十、相关文档

- [CLAUDE.md](../CLAUDE.md) — 项目开发指南
- [apps/python/README.md](../apps/python/README.md) — Python 后端说明
- [apps/electron/tests/README.md](../apps/electron/tests/README.md) — 测试指南
- Electron 官方文档：https://www.electronjs.org/docs/latest/
- PyInstaller 文档：https://pyinstaller.org/

---

**维护者**：Finance Assistant 开发团队  
**最后更新**：2026-04-29  
**适用版本**：v0.1.0 (W5 Phase 1)
