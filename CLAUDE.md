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
# 1. Install Python dependencies
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

### Development Mode

```bash
# Terminal 1: Start Python backend (standalone debugging)
cd apps/python
source .venv/bin/activate
python src/bridge.py
# Expected: {"jsonrpc":"2.0","result":{"status":"ready"}}

# Terminal 2: Start Electron (connects to running Python)
cd apps/electron
npm run dev
```

### Build & Package

```bash
# Package Python backend
cd apps/python
pyinstaller build.spec --onefile

# Package Electron app
cd ../electron
npm run package
# Output: release/FinanceAssistant Setup 1.0.0.exe (or .dmg/.AppImage)
```

### Running Tests

```bash
# Python tests
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
# Electron/Renderer tests
cd apps/electron
npm test

cd apps/renderer
npm test
```

### Linting & Formatting

```bash
# Python
cd apps/python
ruff check .
black .

# TypeScript/JavaScript
cd apps/electron
npm run lint

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
│   │       ├── main.ts      # Entry point, app lifecycle
│   │       ├── ipc.ts        # IPC handlers (Electron ↔ Python)
│   │       └── window.ts     # Window management
│   ├── renderer/        # React frontend (TypeScript + Vite)
│   │   └── src/
│   │       ├── App.tsx
│   │       ├── main.tsx
│   │       └── components/
│   └── python/          # Python backend (nanobot SDK + tools)
│       └── src/
│           ├── bridge.py     # JSON-RPC bridge (Electron ↔ Python)
│           ├── agent.py      # nanobot agent definition
│           └── tools/        # Business logic tools
│               ├── reconciliation.py
│               └── bank_statement.py
├── shared/              # Shared type definitions (TypeScript)
│   └── types.ts         # IPC message schemas, data models
├── scripts/             # Build/packaging scripts
│   ├── build.sh
│   └── package.sh
└── .github/workflows/   # CI/CD pipelines
    └── ci.yml           # Build, test, package on push
```

### IPC Communication Flow

1. **Renderer (React)** → **Electron main** via `electron.ipcRenderer`
2. **Electron main** → **Python backend** via stdio JSON-RPC (spawned subprocess)
3. **Python backend** (nanobot agent) processes requests and returns results

The Python backend exposes tools that the frontend can call through this chain. The `bridge.py` handles the JSON-RPC protocol; the agent uses the nanobot SDK to route tool calls.

### Key Files (to be created)

| File | Purpose |
|------|---------|
| `apps/electron/src/main.ts` | Electron app bootstrap, menu, Tray, lifecycle |
| `apps/electron/src/ipc.ts` | Registers `ipcMain.handle` handlers; forwards to Python via stdio |
| `apps/python/src/bridge.py` | Spawns agent, reads/writes JSON-RPC messages on stdin/stdout |
| `apps/python/src/agent.py` | nanobot `Agent` with `@tool`-decorated reconciliation functions |
| `shared/types.ts` | Shared TypeScript interfaces: `ReconciliationRequest`, `BankTransaction`, etc. |

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

---

## Troubleshooting

### Python backend not connecting
- Ensure virtualenv is activated: `source apps/python/.venv/bin/activate`
- Verify agent starts: `python apps/python/src/bridge.py` should print `{"jsonrpc":"2.0","result":{"status":"ready"}}`

### Electron can't find Python
- Check Python path in `apps/electron/src/main.ts` (spawn config)
- On Windows, use full path like `C:\\Python311\\python.exe`

### Port conflicts
- Electron uses a random available port for the dev server (Vite)
- Python bridge uses stdio — no port needed

---

## References

- [nanobot SDK](https://github.com/HKUDS/nanobot) — AI Agent framework
- [Electron docs](https://www.electronjs.org/docs) — Desktop app framework
- [PyInstaller](https://pyinstaller.org/) — Python packaging
- Architecture docs (planned): `architecture/` directory
- Daily notes (planned): `daily/` directory
