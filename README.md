# FinanceAssistant

**智能银行对账桌面应用** — 基于 Electron + Python + nanobot

## 🏗️ 项目结构

```
finance-assistant/
├── apps/
│   ├── electron/        # Electron 主进程（Node.js + TypeScript）
│   ├── renderer/        # React 前端（TypeScript + Vite）
│   └── python/          # Python 后端（nanobot SDK + 对账工具）
├── shared/              # 共享类型定义（TypeScript）
├── scripts/             # 构建/打包脚本
└── .github/workflows/   # CI/CD 流水线
```

## 🚀 快速开始

### 前置要求

- **Node.js**: ≥ 18.0.0
- **Python**: ≥ 3.11
- **Git**: 任意版本

### 安装依赖

```bash
# 1. 安装 Python 依赖
cd apps/python
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. 安装 Electron 依赖
cd ../electron
npm install

# 3. 安装 Renderer 依赖
cd ../renderer
npm install
```

### 开发模式

```bash
# 终端 1：启动 Python 后端（独立调试）
cd apps/python
source .venv/bin/activate
python src/bridge.py
# 应看到：{"jsonrpc":"2.0","result":{"status":"ready"}}

# 终端 2：启动 Electron（连接已运行的 Python）
cd apps/electron
npm run dev
```

## 📦 打包发布

### 一键打包（推荐）

项目提供了自动化的打包脚本，会自动生成测试代码签名证书并完成完整打包：

```bash
# Windows
scripts\package.bat

# Linux / macOS
./scripts/package.sh
```

一键打包流程：
1. ✅ 检查 Node.js / Python 依赖
2. ✅ 安装 npm 依赖
3. ✅ 打包 Python 后端（PyInstaller → bridge.exe）
4. ✅ 构建 Renderer 前端（Vite → dist/）
5. ✅ 生成测试代码签名证书（如需要）
6. ✅ 打包 Electron 应用（TypeScript → electron-builder + 代码签名）

输出文件：`release/FinanceAssistant Setup 0.1.0.exe`（Windows）

### 手动打包

```bash
# 1. 打包 Python 后端
cd apps/python
pyinstaller build.spec --onefile

# 2. 构建 Renderer
cd ../renderer
npm run build

# 3. 打包 Electron
cd ../electron
npm run package
```

### 代码签名

项目使用代码签名证书对 Windows 安装包进行签名。测试环境使用自签名证书，生产环境需购买正式证书。

📖 **[详细代码签名配置指南](docs/signing.md)**

## 📚 文档

- [需求说明书](architecture/银行对账系统二期-需求说明书.md)
- [技术实施方案](architecture/银行对账系统-二期 Electron + Python 实施方案.md)
- [执行计划](architecture/银行对账系统二期-执行计划.md)
- [IPC 交互详解](daily/2026-04-28 Electron 主进程与 Python 进程的 IPC 交互详解.md)
- [打包流程详解](daily/2026-04-28 Electron + Python 混合应用打包流程详解.md)

## 🔗 相关项目

- [nanobot](https://github.com/HKUDS/nanobot) — AI Agent 框架
- [Electron](https://www.electronjs.org/) — 跨平台桌面框架
- [PyInstaller](https://www.pyinstaller.org/) — Python 打包工具

## 📄 许可证

MIT License

---

**状态**: 开发中（W5 Phase 1）
