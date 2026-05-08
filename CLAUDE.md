# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FinanceAssistant** — A bank statement processing desktop application built with Electron + Python + nanobot.

The application is a multi-process desktop app:
- **Renderer** (React + TypeScript + Vite) — Frontend UI
- **Electron** (Node.js + TypeScript) — Main process, window management, IPC
- **Python** (custom tools + nanobot SDK) — PDF parsing, Excel export, AI agent

**Note**: This project does NOT implement reconciliation (对账) functionality. Focus is on bank statement PDF parsing and Excel export.

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
# Expected first output: {"jsonrpc":"2.0","result":{"status":"ok","version":"0.2.0",...}}

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
# Electron integration tests
cd apps/electron
node tests/integration/bridge-ipc.test.js
node tests/integration/ipc-methods.test.js
node tests/integration/full-workflow.test.js
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
│   │   ├── src/
│   │   │   ├── main.ts              # Entry point, app lifecycle, window creation
│   │   │   ├── ipc.ts               # ipcMain.handle() registry; forwards to Python
│   │   │   ├── preload.ts           # contextBridge exposing electronAPI to renderer
│   │   │   ├── pythonProcessManager.ts  # Spawns/manages Python bridge subprocess
│   │   │   └── pathUtils.ts         # Python spawn path detection (dev vs packaged)
│   │   └── tests/
│   │       └── integration/         # Integration tests (bridge-ipc, ipc-methods, full-workflow)
│   ├── renderer/        # React frontend (TypeScript + Vite)
│   │   └── src/
│   │       ├── App.tsx                # Main UI: file select, PDF parse, Excel export, transaction table
│   │       ├── main.tsx               # React entry point
│   │       └── components/
│   │           ├── FileDropZone.tsx    # File selection button (via Electron dialog)
│   │           ├── TransactionTable.tsx # Paginated transaction table with filtering
│   │           └── ProgressSteps.tsx   # Step indicator (parse → export → done)
│   └── python/          # Python backend (custom tools)
│       └── src/finance_agent_backend/
│           ├── bridge.py             # JSON-RPC 2.0 server over stdio
│           ├── models.py             # Transaction, ParseResult dataclasses
│           └── tools/
│               ├── pdf_parser.py     # Generic bank statement PDF parser
│               ├── cmb_parser.py     # 招商银行 (CMB) dedicated columnar PDF parser
│               └── excel_builder.py  # Transaction list → Excel export (openpyxl)
├── shared/              # Shared type definitions (TypeScript)
│   └── types.ts         # IPC/JSON-RPC message schemas, Transaction model
├── scripts/             # Build/packaging scripts (package.bat, sign.js)
├── docs/                # Documentation (signing.md, packaging-path-resolution.md)
├── .github/workflows/   # CI/CD pipelines
│   └── ci.yml           # Build, test, package on push
├── pyproject.toml       # Python package config
├── package.json         # Root npm workspace config
└── tsconfig.base.json   # Base TypeScript config for all TS projects
```

### IPC Communication Flow

1. **Renderer (React)** → **Electron main** via `window.electronAPI` (exposed by `preload.ts` using `contextBridge`)
2. **Electron main** → **Python backend** via stdio JSON-RPC 2.0 (spawned subprocess managed by `pythonProcessManager.ts`)
3. **Python backend** (`bridge.py`) routes method calls to registered handlers and returns results

**Implemented IPC methods**:

| Method | Direction | Description |
|--------|-----------|-------------|
| `health` | Renderer → Python | Returns backend status, version, Python version |
| `parse_pdf` | Renderer → Python | Parse bank statement PDF → extract transactions (auto-detects bank type) |
| `generate_excel` | Renderer → Python | Export transaction list to Excel (.xlsx) |
| `select_file` | Renderer → Electron | Opens native file dialog, returns absolute file path |

**Planned IPC methods**:

| Method | Direction | Description |
|--------|-----------|-------------|
| `chat` | Renderer → Python | Query the AI agent about parsed transactions |

### PDF Parsing Flow

1. User clicks "选择文件" → Electron `dialog.showOpenDialog` → returns absolute path
2. Path sent via `parse_pdf` IPC → Python `_detect_bank_from_pdf()` scans PDF text for bank name
3. Routes to appropriate parser:
   - 招商银行 → `CMBParser` (columnar format: date/currency/amount/balance/type/counterparty)
   - Other banks → `BankStatementParser` (line-based format)
4. Returns `Transaction[]` with date, description, amount, direction, counterparty, reference_number
5. Frontend renders in `TransactionTable` with pagination, filtering, sorting
6. User can export to Excel via `generate_excel`

### Key Files

| File | Purpose |
|------|---------|
| `apps/electron/src/main.ts` | Electron bootstrap, menu, window lifecycle |
| `apps/electron/src/ipc.ts` | Registers `ipcMain.handle` handlers; forwards to Python |
| `apps/electron/src/preload.ts` | Exposes safe API to renderer via `contextBridge` |
| `apps/electron/src/pythonProcessManager.ts` | Spawns/manages Python bridge, handles JSON-RPC over stdio |
| `apps/electron/src/pathUtils.ts` | Resolves Python executable path (venv in dev, bundled exe in prod) |
| `apps/python/src/finance_agent_backend/bridge.py` | JSON-RPC 2.0 server — reads stdin, dispatches to methods, writes stdout |
| `apps/python/src/finance_agent_backend/models.py` | `Transaction` and `ParseResult` dataclasses |
| `apps/python/src/finance_agent_backend/tools/pdf_parser.py` | Generic bank statement PDF parser |
| `apps/python/src/finance_agent_backend/tools/cmb_parser.py` | 招商银行 dedicated parser for columnar PDF format |
| `apps/python/src/finance_agent_backend/tools/excel_builder.py` | Exports `Transaction[]` to single-sheet Excel workbook |
| `shared/types.ts` | Shared TypeScript interfaces: IPC params/results, `Transaction`, etc. |

---

## Technology Stack

- **Electron** — Cross-platform desktop shell
- **React + Vite** — Frontend framework and bundler
- **TypeScript** — Type safety across all layers
- **Python 3.11+** — Business logic (PDF parsing, Excel generation)
- **PyMuPDF (fitz)** — PDF text extraction
- **openpyxl** — Excel file generation
- **nanobot** — AI Agent SDK (HKUDS) for tool calling (planned)
- **PyInstaller** — Python binary packaging
- **Ruff + Black** — Python lint/format
- **ESLint + Prettier** — TS/JS lint/format

---

## Conventions

- Python source lives in `apps/python/src/finance_agent_backend/`
- Electron main process code in `apps/electron/src/`
- Renderer React code in `apps/renderer/src/`
- Shared types in `shared/` — update these when IPC schemas change
- Use named exports consistently; avoid default exports in shared types
- Python virtualenv committed as `.venv/` in `apps/python/` (see `.gitignore`)
- Never commit secrets — use `.env` (gitignored) with `.env.example` as template
- **No reconciliation (对账) logic** — this project does not implement bank-ledger matching

### Windows-specific

- Activate venv: `apps/python\.venv\Scripts\activate`
- Python spawn in `pathUtils.ts` auto-detects the correct Python executable (venv or bundled)
- Electron `npm run dev` requires Python running in a separate terminal first
- PyMuPDF uses `fitz.open("pdf", bytes)` instead of `fitz.open(file_path)` to handle Unicode Windows paths

---

## Troubleshooting

### Python backend not connecting
- Ensure virtualenv is activated: `source apps/python/.venv/bin/activate` (Windows: `apps/python\.venv\Scripts\activate`)
- Verify bridge starts: `python apps/python/src/bridge.py` outputs JSON-RPC messages when it receives input
- Check `pathUtils.ts` to ensure it resolves the correct Python executable

### Chinese path garbled (mojibake)
- Two-layer fix: `PYTHONIOENCODING=utf-8` env var + explicit `toString('utf-8')` / `write(str, 'utf-8')` in TypeScript
- PyMuPDF: read PDF as bytes via `open(path, 'rb')` then `fitz.open("pdf", pdf_bytes)` to bypass Unicode path limitation

### PDF parsing returns no transactions
- 招商银行 PDFs use a columnar format → handled by `CMBParser`
- Generic bank PDFs use line-based format → handled by `BankStatementParser` in `pdf_parser.py`
- Bank type is auto-detected from PDF text; can be overridden with `bank` param

### Port conflicts
- Electron/Vite dev server uses port 5173 (strict)
- Python bridge uses stdio — no port needed

### Python dependency issues
- Dependencies managed via `pyproject.toml`
- Install with: `pip install -e ".[dev]"` inside the virtualenv
- Key packages: `pymupdf` (PDF parsing), `openpyxl` (Excel output), `nanobot` (AI agent)

---

## References

- [nanobot SDK](https://github.com/HKUDS/nanobot) — AI Agent framework
- [Electron docs](https://www.electronjs.org/docs) — Desktop app framework
- [PyMuPDF docs](https://pymupdf.readthedocs.io/) — PDF library
- [openpyxl docs](https://openpyxl.readthedocs.io/) — Excel library
- [PyInstaller](https://pyinstaller.org/) — Python packaging
- Project README: `README.md` (Chinese)
