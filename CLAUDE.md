# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FinanceAssistant** — A smart bank reconciliation desktop application built with Electron + Python + nanobot.

The application is a multi-process desktop app:
- **Renderer** (React + TypeScript + Vite) — Frontend UI
- **Electron** (Node.js + TypeScript) — Main process, window management, IPC
- **Python** (nanobot SDK + custom tools) — Backend business logic, reconciliation engine

**Status**: Development phase (W5 Phase 1)

---

## Common Development Tasks

### Prerequisites

- **Node.js**: ≥ 18.0.0
- **Python**: ≥ 3.11
- **Git**: any version

### Install Dependencies

```bash
# 1. Install Python dependencies (using Poetry)
cd apps/python
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. Install Electron dependencies
cd ../electron
npm install

# 3. Install Renderer dependencies
cd ../renderer
npm install
```

### One-shot setup (all apps)

```bash
# From repo root — installs all workspaces
npm install
cd apps/python && pip install -e ".[dev]"
```

### Development Mode

```bash
# Terminal 1: Start Python backend (standalone debugging)
cd apps/python
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python src/bridge.py
# Expected first output: {"jsonrpc":"2.0","result":{"status":"ok","version":"0.1.0",...}}

# Terminal 2: Start Electron (connects to running Python)
cd apps/electron
npm run dev
```

**Renderer standalone** (skip Electron; requires backend proxy — not configured yet):

```bash
cd apps/renderer
npm run dev
```

**Single-command dev** (spawns both processes; future work):

```bash
npm run dev  # at repo root (not yet implemented)
```

### Build & Package

```bash
# Package Python backend (requires build.spec — not yet created)
cd apps/python
pyinstaller build.spec --onefile

# Package Electron app
cd ../electron
npm run package
# Output: release/FinanceAssistant Setup 1.0.0.exe (or .dmg/.AppImage)
```

### Running Tests

```bash
# Python tests (no tests directory yet — placeholder)
cd apps/python
pytest

# Single test file
pytest tests/test_module.py

# Single test
pytest tests/test_module.py::test_function_name

# With coverage
pytest --cov=src
```

```bash
# Electron/Renderer tests (test scripts not yet configured)
cd apps/electron
npm test

cd apps/renderer
npm test
```

### Linting & Formatting

```bash
# Python (ruff + black — config in pyproject.toml)
cd apps/python
ruff check .
black .

# TypeScript/JavaScript (ESLint + Prettier — configs not yet created)
cd apps/electron
npm run lint  # script present; eslint config may be needed

cd apps/renderer
npm run lint
```

---

## Architecture

### High-Level Structure

```
finance-assistant/
├── apps/
│   ├── electron/        # Electron main process (Node.js + TypeScript)
│   │   └── src/
│   │       ├── main.ts              # Entry point, app lifecycle, window creation
│   │       ├── ipc.ts               # ipcMain.handle() registry; forwards to Python
│   │       ├── preload.ts           # contextBridge exposing electronAPI to renderer
│   │       └── pythonProcessManager.ts  # Spawns/manages Python bridge subprocess
│   ├── renderer/        # React frontend (TypeScript + Vite)
│   │   └── src/
│   │       ├── App.tsx             # Top-level UI + connection test
│   │       └── main.tsx            # React entry point
│   └── python/          # Python backend (nanobot SDK + tools)
│       └── src/
│           ├── bridge.py           # JSON-RPC 2.0 server over stdio
│           └── (agent.py planned)  # nanobot agent — not yet implemented
├── shared/              # Shared type definitions (TypeScript)
│   └── types.ts         # IPC/JSON-RPC message schemas, data models
├── .github/workflows/   # CI/CD pipelines
│   └── ci.yml           # Build, test, package on push
├── pyproject.toml       # Python package config (Poetry)
├── package.json         # Root npm workspace config
└── tsconfig.base.json   # Base TypeScript config for all TS projects
```

### IPC Communication Flow

1. **Renderer (React)** → **Electron main** via `window.electronAPI` (exposed by `preload.ts` using `contextBridge`)
2. **Electron main** → **Python backend** via stdio JSON-RPC 2.0 (spawned subprocess managed by `pythonProcessManager.ts`)
3. **Python backend** (`bridge.py`) routes method calls to registered handlers and returns results

**Current IPC methods** (implemented):

| Method | Direction | Description |
|--------|-----------|-------------|
| `health` | Renderer → Python | Returns backend status, version, Python version |

**Planned IPC methods** (in `ipc.ts` / `preload.ts`):

| Method | Direction | Description |
|--------|-----------|-------------|
| `parse_pdf` | Renderer → Python | Parse bank statement PDF → extract transactions |
| `reconcile` | Renderer → Python | Match bank transactions against ledger |
| `chat` | Renderer → Python | Query the AI agent about reconciliation results |

### Key Files

| File | Purpose |
|------|---------|
| `apps/electron/src/main.ts` | Electron bootstrap, menu, window lifecycle |
| `apps/electron/src/ipc.ts` | Registers `ipcMain.handle` handlers; forwards to Python |
| `apps/electron/src/preload.ts` | Exposes safe API to renderer via `contextBridge` |
| `apps/electron/src/pythonProcessManager.ts` | Spawns/manages Python bridge, handles JSON-RPC over stdio |
| `apps/python/src/bridge.py` | JSON-RPC 2.0 server — reads stdin, dispatches to methods, writes stdout |
| `apps/python/src/agent.py` | (planned) nanobot `Agent` with `@tool`-decorated business logic |
| `shared/types.ts` | Shared TypeScript interfaces: IPC params/results, `Transaction`, etc. |

---

## Technology Stack

- **Electron** — Cross-platform desktop shell
- **React + Vite** — Frontend framework and bundler
- **TypeScript** — Type safety across all layers
- **Python 3.11+** — Business logic and AI agent integration
- **nanobot** — AI Agent SDK (HKUDS) for tool calling
- **PyInstaller** — Python binary packaging
- **Ruff + Black** — Python lint/format
- **ESLint + Prettier** — TS/JS lint/format

---

## Conventions

- Python source lives in `apps/python/src/`
- Electron main process code in `apps/electron/src/`
- Renderer React code in `apps/renderer/src/`
- Shared types in `shared/` — update these when IPC schemas change
- Use named exports consistently; avoid default exports in shared types
- Python virtualenv committed as `.venv/` in `apps/python/` (see `.gitignore`)
- Never commit secrets — use `.env` (gitignored) with `.env.example` as template

### Windows-specific

- Activate venv: `apps/python\.venv\Scripts\activate`
- Python spawn in `pythonProcessManager.ts` uses `python3` — either add Python to PATH as `python3` or change to `python`
- Electron `npm run dev` requires Python running in a separate terminal first

---

## Troubleshooting

### Python backend not connecting
- Ensure virtualenv is activated: `source apps/python/.venv/bin/activate` (Windows: `apps/python\.venv\Scripts\activate`)
- Verify bridge starts: `python apps/python/src/bridge.py` outputs JSON-RPC messages when it receives input
- Check that `python3` is in PATH or update `pythonProcessManager.ts` to use `python` on Windows

### Electron can't find Python
The spawn command in `apps/electron/src/pythonProcessManager.ts` uses `python3`. On Windows, either:
- Add Python to PATH as `python3` (via symlink/alias), or
- Change `spawn('python3', ...)` to `spawn('python', ...)` or use the full path

### Port conflicts
- Electron/Vite dev server uses port 5173 (strict)
- Python bridge uses stdio — no port needed

### Python dependency issues
- Dependencies managed by Poetry (`pyproject.toml`)
- Install with: `pip install -e ".[dev]"` inside the virtualenv
- Key packages: `nanobot`, `pymupdf` (PDF parsing), `openpyxl` (Excel output), `rapidfuzz` (fuzzy matching)

---

## References

- [nanobot SDK](https://github.com/HKUDS/nanobot) — AI Agent framework
- [Electron docs](https://www.electronjs.org/docs) — Desktop app framework
- [PyInstaller](https://pyinstaller.org/) — Python packaging
- Project README: `README.md` (Chinese — 需求/方案/执行计划 链接)
