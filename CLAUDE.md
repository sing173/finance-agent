# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FinanceAssistant** — A bank statement processing desktop application built with Electron + Python.

The application is a multi-process desktop app:
- **Renderer** (React + TypeScript + Vite) — Frontend UI
- **Electron** (Node.js + TypeScript) — Main process, window management, IPC
- **Python** (custom tools) — PDF/CSV/Excel parsing, OCR, Excel export, voucher generation

**Note**: This project does NOT implement reconciliation (对账) functionality. Focus is on bank statement PDF/CSV/Excel parsing, OCR-based receipt extraction, and Excel/voucher export.

**Status**: v0.1.0 completed (demo phase). Starting v0.2.0 productization.

---

## High-Level Project Status (v0.1.0 → v0.2.0)

### v0.1.0 Achievements (Demo Phase)
- Multi-bank PDF statement parsing: ICBC (工商银行), CMB (招商银行), GFB (广发银行)
- ICBC receipt (回单) OCR parsing via grid-line detection + RapidOCR
- ICBC CSV account statement parsing (GBK encoding)
- CMB Excel statement parsing (.xlsx)
- CMB receipt parsing
- Excel export for parsed transactions
- Voucher (凭证) export in Kingdee Jingdouyun (金蝶精斗云) format
- Subject (科目) management: import from xlsx, built-in config
- File-based logging with rotation (10MB × 3)
- PyInstaller packaging for Python backend (bridge.exe)
- Electron + electron-builder packaging (NSIS installer)
- Full integration test suite (bridge-ipc, ipc-methods, icbc-csv, icbc-ocr-workflow)

### v0.2.0 Goals (Productization)
- Code quality: reduce duplication across 13 parser files
- Error handling: consistent error propagation and user-facing messages
- Configuration: externalize bank-specific parsing rules
- Testing: expand coverage, add unit tests for individual parsers
- Performance: optimize OCR pipeline, lazy-load heavy dependencies
- UX: improve progress feedback, error display, file type guidance
- Packaging: fix signing, reduce installer size, auto-update support

---

## Common Development Tasks

### Prerequisites

- **Node.js**: >= 18.0.0
- **Python**: >= 3.11
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
python src/finance_agent_backend/bridge.py
# Expected first output: {"jsonrpc":"2.0","result":{"status":"ok","version":"0.2.0",...}}

# Terminal 2: Start Electron (connects to running Python)
cd apps/electron
npm run dev
```

### Build & Package

```bash
# Package Python backend
cd apps/python
python -m PyInstaller bridge.spec --onefile --clean
# Output: dist/bridge.exe

# Package Electron app
cd ../electron
npm run package
# Output: release/FinanceAssistant Setup 0.1.0.exe
```

### Running Tests

```bash
# Electron integration tests
cd apps/electron
node tests/integration/bridge-ipc.test.js       # Health check
node tests/integration/ipc-methods.test.js       # Full IPC methods
node tests/integration/icbc-csv.test.js          # ICBC CSV parsing
node tests/integration/icbc-ocr-workflow.test.js  # OCR workflow
node tests/integration/full-workflow.test.js      # End-to-end flow
```

```bash
# Python tests (no tests directory yet — placeholder)
cd apps/python
pytest
```

### Linting & Formatting

```bash
# Python (ruff + black — config in pyproject.toml)
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
│   │   ├── src/
│   │   │   ├── main.ts              # Entry point, app lifecycle, window creation
│   │   │   ├── ipc.ts               # ipcMain.handle() registry; forwards to Python
│   │   │   ├── preload.ts           # contextBridge exposing electronAPI to renderer
│   │   │   ├── pythonProcessManager.ts  # Spawns/manages Python bridge subprocess
│   │   │   └── pathUtils.ts         # Python spawn path detection (dev vs packaged)
│   │   └── tests/
│   │       ├── integration/         # Integration tests
│   │       │   ├── bridge-ipc.test.js
│   │       │   ├── ipc-methods.test.js
│   │       │   ├── icbc-csv.test.js
│   │       │   ├── icbc-ocr-workflow.test.js
│   │       │   └── full-workflow.test.js
│   │       └── README.md            # Test documentation and coverage matrix
│   ├── renderer/        # React frontend (TypeScript + Vite)
│   │   └── src/
│   │       ├── App.tsx                # Main UI: file select, parse, export, transaction table
│   │       ├── main.tsx               # React entry point
│   │       └── components/
│   │           ├── FileDropZone.tsx    # File selection (PDF/CSV/Excel via Electron dialog)
│   │           ├── TransactionTable.tsx # Paginated transaction table with filtering
│   │           └── ProgressSteps.tsx   # Step indicator (parse → export → done)
│   └── python/          # Python backend
│       ├── bridge.spec               # PyInstaller spec for bridge.exe
│       └── src/finance_agent_backend/
│           ├── bridge.py             # JSON-RPC 2.0 server over stdio (11 registered methods)
│           ├── models.py             # Transaction, ParseResult, Subject, VoucherEntry
│           ├── config/               # Built-in configuration
│           │   ├── subjects.json         # 会计科目字典
│           │   ├── subject_mapping.json  # 科目映射规则
│           │   └── account_mapping.json  # 账号映射规则
│           └── tools/                # 13 parser/builder tools (~4,100 lines total)
│               ├── pdf_parser.py     # Generic bank statement PDF parser
│               ├── cmb_parser.py     # CMB old columnar PDF parser
│               ├── cmb_table_parser.py   # CMB table-format PDF parser (账务明细清单)
│               ├── cmb_receipt_parser.py # CMB receipt PDF parser (回单)
│               ├── cmb_excel_parser.py   # CMB Excel transaction parser (.xlsx)
│               ├── icbc_parser.py        # ICBC statement PDF parser
│               ├── icbc_csv_parser.py    # ICBC CSV account statement parser (GBK)
│               ├── icbc_receipt_parser.py    # ICBC receipt parser (OCR-based)
│               ├── icbc_receipt_grid_parser.py # ICBC receipt grid-line parser
│               ├── gfb_table_parser.py   # GFB (广发银行) table-format PDF parser
│               ├── pdf_ocr.py        # RapidOCR wrapper for scanned PDFs
│               ├── excel_builder.py  # Transaction → Excel + voucher export
│               └── subject_loader.py # Import accounting subjects from xlsx
├── shared/              # Shared type definitions (TypeScript)
│   └── types.ts         # IPC/JSON-RPC message schemas, Transaction model
├── scripts/             # Build/packaging scripts
│   ├── package.bat / package.sh   # Packaging scripts
│   └── generate-test-cert.ps1     # Test cert generation
├── docs/                # Detailed documentation
│   ├── packaging-path-resolution.md  # Electron+Python cross-env path resolution
│   ├── signing.md                    # Code signing guide
│   └── export-excel-design.md        # Excel export design doc
├── logs/                # Bridge log files (gitignored)
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

### Registered JSON-RPC Methods

| Method | Description | Added |
|--------|-------------|-------|
| `health` | Backend status, version, Python version | v0.1.0 |
| `parse_pdf` | Parse bank statement (auto-routes PDF/CSV/Excel by extension and content) | v0.1.0 |
| `parse_csv` | Direct ICBC CSV parsing shortcut | v0.1.0 |
| `ocr_pdf` | OCR scanned/image PDF to text | v0.1.0 |
| `generate_excel` | Export transaction list to Excel (.xlsx) | v0.1.0 |
| `generate_voucher_excel` | Export transactions as Kingdee Jingdouyun voucher template | v0.1.0 |
| `import_subjects` | Import accounting subjects from xlsx → built-in subjects.json | v0.1.0 |
| `get_subjects_info` | Query built-in subject table info | v0.1.0 |
| `select_file` | Native file dialog (Electron-side, not JSON-RPC) | v0.1.0 |

### File Type Routing (parse_pdf)

```
User selects file
  ├── .xlsx → CMBExcelParser (招行Excel交易流水)
  ├── .csv  → ICBCCSVParser (工行CSV对账流水)
  └── .pdf
       └── _detect_bank_from_pdf() → (bank, doc_type)
            ├── 扫描件 (no embedded text) or doc_type=receipt
            │    └── ICBCReceiptGridParser (grid-line OCR, self-validates)
            │         └── (fallback) ICBCParser (流水)
            ├── 工商银行 (statement)
            │    └── ICBCParser
            ├── 招商银行
            │    ├── receipt → CMBReceiptParser
            │    ├── table → CMBTableParser (账务明细清单)
            │    └── column → CMBParser (old format)
            ├── 广发银行 → GFBTableParser
            └── 未知银行 → BankStatementParser (generic)
```

### Bank Support Matrix

| Bank | Statement (流水) | Receipt (回单) | CSV | Excel |
|------|-----------------|---------------|-----|-------|
| 工商银行 (ICBC) | `icbc_parser.py` | `icbc_receipt_grid_parser.py` | `icbc_csv_parser.py` | - |
| 招商银行 (CMB) | `cmb_table_parser.py` / `cmb_parser.py` | `cmb_receipt_parser.py` | - | `cmb_excel_parser.py` |
| 广发银行 (GFB) | `gfb_table_parser.py` | - | - | - |

---

## Technology Stack

- **Electron 32** — Cross-platform desktop shell
- **React + Vite** — Frontend framework and bundler
- **TypeScript 5.6** — Type safety across all layers
- **Python 3.11+** — Business logic (PDF parsing, OCR, Excel generation)
- **PyMuPDF (fitz) 1.24** — PDF text extraction
- **RapidOCR (ONNX Runtime)** — OCR for scanned PDFs/receipts
- **openpyxl 3.1** — Excel file generation
- **opencv-python 4.8** — Image preprocessing for OCR
- **PyInstaller** — Python binary packaging
- **electron-builder 24** — Electron app packaging (NSIS on Windows)
- **Poetry** — Python dependency management
- **Ruff + Black** — Python lint/format
- **ESLint + Prettier** — TS/JS lint/format

---

## Conventions

- Python source lives in `apps/python/src/finance_agent_backend/`
- Electron main process code in `apps/electron/src/`
- Renderer React code in `apps/renderer/src/`
- Shared types in `shared/` — update these when IPC schemas change
- Built-in config in `apps/python/src/finance_agent_backend/config/` (subjects.json, etc.)
- Use named exports consistently; avoid default exports in shared types
- Python virtualenv managed by Poetry, not committed
- Never commit secrets — use `.env` (gitignored) with `.env.example` as template
- **No reconciliation (对账) logic** — this project does not implement bank-ledger matching
- Bridge methods registered via `@register_method("name")` decorator in `bridge.py`

### Windows-specific

- All bash paths must use forward slashes (e.g., `D:/git/finance-agent/...`)
- Activate venv: `apps/python/.venv/Scripts/activate`
- Python spawn in `pathUtils.ts` auto-detects the correct Python executable (venv or bundled bridge.exe)
- PyMuPDF: use `fitz.open("pdf", bytes)` instead of `fitz.open(file_path)` to handle Unicode Windows paths
- `PYTHONIOENCODING=utf-8` must be set when spawning Python subprocess to prevent Chinese garbled output
- Electron packaging: `asar: false` (must be false for `extraResources` path resolution)
- Code signing disabled in current electron-builder config (`signDlls: false`, `signAndEditExecutable: false`)

---

## Key Lessons from v0.1.0

### PyInstaller Packaging Pitfalls
1. **Chinese path encoding**: PyInstaller's C bootloader may not respect `PYTHONIOENCODING`. Workaround: explicit `sys.stdin.reconfigure(encoding="utf-8")` and `sys.stdout.reconfigure(encoding="utf-8")` at bridge startup.
2. **OCR model dependencies**: RapidOCR's ONNX model files must be explicitly added to PyInstaller `datas` or they won't be bundled. Missing models = silent OCR failure in packaged app.
3. **SPECPATH**: Using `SPECPATH` in .spec files allows relative path resolution from the spec file location.

### OCR Pipeline Complexity
- ICBC receipts use grid-line detection to locate form fields — more reliable than pure text OCR
- OCR character variants (e.g., `0` vs `O`, Chinese character substitutions) require simplified regex or direct matching
- Multi-page PDFs: subsequent pages inherit header column mapping from the first page
- OCR is slow (~1-2s per page); lazy-load RapidOCR only when needed

### Parser Architecture
- 13 parser files with duplicated patterns (bank detection, transaction serialization). v0.2.0 should extract a base class.
- All parsers share the same `ParseResult` return type — keeps bridge.py routing consistent
- Routing logic in `bridge.py` `handle_parse_pdf` is becoming complex; consider extracting to a router module

### CSV/Excel Handling
- ICBC CSV uses GBK encoding, comma-delimited, with embedded Tab characters in fields
- CMB Excel (.xlsx) statements use a different column layout than CMB PDF statements
- File extension routing happens before content-based bank detection

---

## Troubleshooting

### Python backend not connecting
- Ensure virtualenv is activated and dependencies installed: `pip install -e ".[dev]"`
- Verify bridge starts: `echo '{"jsonrpc":"2.0","id":1,"method":"health","params":{}}' | python apps/python/src/finance_agent_backend/bridge.py`
- Check `pathUtils.ts` resolves the correct Python executable
- Set `PYTHON_CMD` env var to override: `PYTHON_CMD=D:/Python312/python.exe npm run dev`

### Chinese path garbled (mojibake)
- Two-layer fix: `PYTHONIOENCODING=utf-8` env var + explicit `toString('utf-8')` / `write(str, 'utf-8')` in TypeScript
- PyMuPDF: read PDF as bytes via `open(path, 'rb')` then `fitz.open("pdf", pdf_bytes)` to bypass Unicode path limitation

### PDF parsing returns no transactions
- Debug: check `bridge.log` in `logs/` directory for parser routing and error messages
- Scanned PDFs (no embedded text) → automatically routed through OCR pipeline
- Bank type is auto-detected from PDF text; can be overridden with `bank` param
- Each parser is tried in sequence; fallback to `BankStatementParser` if all fail

### OCR not working in packaged app
- Ensure RapidOCR ONNX models are included in PyInstaller build (check `bridge.spec` `datas` list)
- OCR requires opencv-python and rapidocr-onnxruntime in Python dependencies
- Check `bridge.log` for OCR initialization errors

### PyInstaller build failures
- Run from `apps/python/` directory: `python -m PyInstaller bridge.spec --onefile --clean`
- SPECPATH should be set to the spec file's directory
- Large model files may need `--add-data` flags

### Port conflicts
- Electron/Vite dev server uses port 5173 (strict)
- Python bridge uses stdio — no port needed

---

## References

- [Electron docs](https://www.electronjs.org/docs) — Desktop app framework
- [PyMuPDF docs](https://pymupdf.readthedocs.io/) — PDF library
- [RapidOCR](https://github.com/RapidAI/RapidOCR) — ONNX-based OCR
- [openpyxl docs](https://openpyxl.readthedocs.io/) — Excel library
- [PyInstaller](https://pyinstaller.org/) — Python packaging
- [electron-builder](https://www.electron.build/) — Electron packaging
- Project README: `README.md` (Chinese)
- Test documentation: `apps/electron/tests/README.md`
- Packaging guide: `docs/packaging-path-resolution.md`
