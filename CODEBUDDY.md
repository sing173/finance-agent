# CODEBUDDY.md This file provides guidance to CodeBuddy when working with code in this repository.

## Project Overview

**FinanceAssistant** — A bank statement processing desktop application (Electron + Python monorepo). Parses bank statement PDFs/CSVs/Excels to extract transactions, matches accounting subjects, and exports as Excel or Kingdee Jingdouyun vouchers.

**Status**: v0.3.0 development, transitioning from prototype to product. This project does NOT implement reconciliation (对账) — it is focused on statement parsing, receipt OCR, and voucher generation.

---

## Common Commands

### Install Dependencies

```bash
# Root workspaces (Electron + Renderer)
npm install

# Python backend
cd apps/python
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Development Mode

```bash
# Terminal 1: Start Python backend
cd apps/python && source .venv/bin/activate
python src/finance_agent_backend/bridge.py
# Expect: {"jsonrpc":"2.0","result":{"status":"ok","version":"0.3.0",...}}

# Terminal 2: Start Electron + Renderer
cd apps/electron && npm run dev
```

### Run Tests

```bash
# Full integration test (31-step, 8-phase end-to-end)
cd apps/electron && node tests/integration/v030-e2e.test.js

# Python unit tests
cd apps/python && pytest

# Renderer unit tests (vitest)
cd apps/renderer && npm test
```

### Build & Package

```bash
# Python backend executable
cd apps/python && python -m PyInstaller bridge.spec --onefile --clean
# Output: dist/bridge.exe

# Electron app NSIS installer
cd apps/electron && npm run package
# Output: release/FinanceAssistant Setup x.x.x.exe
```

### Lint & Format

```bash
# Python (ruff + black — config in pyproject.toml)
cd apps/python && ruff check . && black .

# TypeScript/JavaScript
cd apps/electron && npm run lint
cd apps/renderer && npm run lint
```

---

## Architecture

### Three-Process Desktop App

```
Renderer (React + Vite)  ←IPC→  Electron Main (Node.js)  ←stdio JSON-RPC→  Python Backend
```

**Renderer** (`apps/renderer/`): React 18 + TypeScript + Ant Design UI. Vite dev server on port 5173 (strict). In production, built to `dist/` and loaded via `file://` protocol. Single-page app with two modes: single-file (detect bank → parse → view transactions) and batch (multiple files → detect all → parse sequentially → aggregated results).

**Electron Main** (`apps/electron/`): Electron 32, compiled to CommonJS. Manages window lifecycle, spawns the Python subprocess, and acts as the IPC bridge. Uses `contextBridge` to expose a limited `window.electronAPI` to the renderer. `contextIsolation: true`, `nodeIntegration: false`.

**Python Backend** (`apps/python/`): JSON-RPC 2.0 server over stdin/stdout. Handles all business logic: PDF parsing, OCR, Excel export, voucher composition, subject matching. Packaged as a single `bridge.exe` via PyInstaller for distribution.

### IPC Communication Flow

The IPC chain has four layers, each with a clear purpose:

1. **Renderer** calls `window.electronAPI.parseFile(params)` (exposed by `preload.ts` via `contextBridge`)
2. **Preload** maps the call to `ipcRenderer.invoke('parse_pdf', params)`
3. **Electron Main** (`ipc.ts`) looks up `parse_pdf` in the `HANDLERS` registry and delegates to `pythonProcess.call('parse_pdf', params)`
4. **PythonProcessManager** writes a JSON-RPC 2.0 line to the Python subprocess's stdin, then waits for a matching JSON-RPC response on stdout (60-second timeout)

The `HANDLERS` array in `ipc.ts` is the single source of truth — each entry defines an IPC channel, the corresponding Python method name (or `null` for Electron-native operations like `select_file`), and whether to expose it to the renderer. New Python methods only need one line added to this registry. The preload exposes a generic `invoke(method, params)` for dynamically-registered methods (`voucher.*`, `account_registry.*`), avoiding preload bloat.

Python status is pushed to the renderer via `webContents.send('python-status', ...)` whenever the `PythonProcessManager` emits a `status` event (online/offline/error).

### Python Backend Architecture

`bridge.py` is a minimal JSON-RPC 2.0 server. Methods are registered via the `@register_method("name")` decorator, which stores handler functions in a module-level `METHODS` dict. The main loop reads JSON lines from stdin, routes to the handler, and writes JSON responses to stdout. All heavy dependencies (OCR, openpyxl, parsers) are lazy-imported inside handler functions to keep startup fast.

**Layered structure:**

- **`parser_router.py`** — File routing by extension: `.xlsx` → CMB Excel, `.csv` → ICBC CSV (GBK), `.pdf` → three-level bank detection:
  - Level 1: Embedded PDF text matched against `PDF_STRUCTURE_MATCHERS` keywords (supports `all` and `any` match modes)
  - Level 2: OCR (RapidOCR via ONNX Runtime) for scanned PDFs, extracts account numbers and matches via `AccountRegistry`
  - Level 3: Returns unknown bank — user must manually select
  - Routed bank is looked up in `PARSER_REGISTRY[bankCode]`, an ordered list of parsers tried sequentially until one returns transactions

- **`tools/*.py`** — 11 bank-specific parsers (ICBC, CMB, GFB) handling statements, receipts, CSV, and Excel formats. All inherit from `BaseStatementParser` (static utility methods for PDF I/O, date/amount parsing) and share data via `shared_utils.py` (consolidated helpers: 5 date parsers, 3 amount parsers, PDF span layout analysis). Each parser implements `parse(file_path) -> ParseResult`.

- **`models.py`** — Pure dataclasses: `Transaction`, `ParseResult`, `Subject`, `VoucherEntry`, `AccountEntry`. All have `to_dict()` serialization for JSON-RPC wire format (camelCase keys for the frontend).

- **`subject_matcher.py`** — Three-layer voucher matching (currently implementing v0.3.0): L1 JSON rule-based keyword matching (`subject_mapping.json` with 31 expense + 6 income rules, priority-ordered), L2 SQLite history TF-IDF matching (threshold ≥ 0.75), L3 manual selection.

- **`voucher_composer.py`** — Groups transactions by date/journal, assigns subjects via the matcher, and generates `VoucherEntry` objects for export.

- **`account_registry.py`** — Maps bank account number suffixes to accounting subjects (Repository pattern: JSON persistence via `AccountMappingRepository`, in-memory matching via `AccountRegistry`).

- **`config/`** — Built-in configuration: `subjects.json` (chart of accounts, 75KB), `subject_mapping.json` (expense/income matching rules), `account_mapping.json` (account-to-subject mappings with suffix/exact matching).

### Key Architectural Patterns

**Lazy imports throughout**: Python's `bridge.py` and `parser_router.py` use `__import__` inside handler functions so heavy modules (RapidOCR ~50MB, openpyxl, PyMuPDF) only load when needed.

**Strategy pattern in subject matching**: `RuleMatcher` (JSON keyword rules) and `HistoryMatcher` (TF-IDF over SQLite) are interchangeable strategy objects with a unified `match(transaction) -> MatchResult` interface.

**Repository pattern in account_registry**: `AccountMappingRepository` handles JSON file I/O; `AccountRegistry` is pure in-memory business logic. Designed for future migration to SQLite.

**Batch orchestration in renderer**: `useBatchOrchestrator` hook manages the full batch file pipeline — add files (deduplicated), detect banks in bulk, parse sequentially (tracking progress via `currentIndex`), retry failed files with manual override. `BatchFileSelector` is pure UI; orchestration lives in the hook + `App.tsx`.

**Path resolution**: `apps/python/src/finance_agent_backend/paths.py` centralizes all path logic with `sys.frozen` (PyInstaller) detection. `apps/electron/src/pathUtils.ts` detects Python executable location across three modes: `PYTHON_CMD` env var, packaged `resources/python/bridge.exe`, or dev `.venv/Scripts/python.exe`.

### Technology Stack

- **Electron 32** — Desktop shell, **React 18 + Vite 5** — Frontend, **TypeScript 5.6** — Type safety
- **Python 3.11+** — Business logic, **Poetry** — Python dependency management
- **PyMuPDF (fitz) 1.24** — PDF text extraction, **RapidOCR** — OCR via ONNX Runtime
- **openpyxl 3.1** — Excel generation, **opencv-python 4.8** — Image preprocessing
- **PyInstaller** — Python → `bridge.exe`, **electron-builder 24** — NSIS installer for Windows
- **Ruff + Black** — Python lint/format, **ESLint + Prettier** — TS/JS lint/format

### Windows-Specific Constraints

- Python spawn requires `PYTHONIOENCODING=utf-8` env var to prevent Chinese garbled output
- PyMuPDF: always read PDF as bytes (`fitz.open("pdf", bytes)`) to handle Unicode Windows paths
- ICBC CSV uses GBK encoding with embedded Tab characters in fields
- PyInstaller bundling: ONNX model files must be listed explicitly in `bridge.spec` `datas` — they are not auto-collected
- `electron-builder` requires `asar: false` for `extraResources` path resolution to work
- Code signing is disabled in current config (`signDlls: false`)

### File Organization Rules

- Python source: `apps/python/src/finance_agent_backend/`
- Electron main process: `apps/electron/src/`
- Renderer React code: `apps/renderer/src/`
- Shared TypeScript types: `shared/types.ts` — interface/type definitions only, no functions or constants
- Built-in config: `apps/python/src/finance_agent_backend/config/`
- Use named exports; avoid default exports in shared types
- Never commit secrets; use `.env` (gitignored)
- Bridge methods registered via `@register_method("name")` decorator
- All IPC parameter names and response fields use camelCase across the full stack (Python → Electron → React)
