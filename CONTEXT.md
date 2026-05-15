# CONTEXT.md — FinanceAssistant Domain Context

## Project

**FinanceAssistant** — A desktop application for bank statement processing. Users select bank statement files (PDF, CSV, Excel); the app parses transactions and exports them to Excel or Kingdee Jingdouyun voucher format.

**Scope boundary**: This project does NOT implement reconciliation (对账). Bank-ledger matching is out of scope.

---

## Domain vocabulary

| Term | Meaning |
|------|---------|
| 银行流水 / Statement | 按时间排序的交易明细列表（水平表格，多行多列） |
| 银行回单 / Receipt | 单笔交易的凭证（垂直表格，通常一个条目一张表） |
| 对账流水 / Account statement | 银行门户导出的 CSV 文件，用于对账式复核（ICBC 专用） |
| 科目 / Subject | 会计科目表条目，用于生成凭证时匹配借贷科目 |
| 凭证 / Voucher | 会计分录凭证，金蝶精斗云导入格式 |
| 表格类型 / Doc format | 文档内部内容的布局方式：**流水**（水平多行表格）或 **回单**（垂直单条表格） |
| 文件类型 / File format | 文件扩展名：`.pdf` / `.csv` / `.xlsx` / `.xls` |

---

## Supported banks

| Bank | Code | Statement | Receipt | CSV | Excel |
|------|------|-----------|---------|-----|-------|
| 工商银行 | ICBC | `icbc_parser.py` | `icbc_receipt_grid_parser.py` | `icbc_csv_parser.py` | — |
| 招商银行 | CMB | `cmb_table_parser.py`, `cmb_parser.py` | `cmb_receipt_parser.py` | — | `cmb_excel_parser.py` |
| 广发银行 | GFB | `gfb_table_parser.py` | — | — | — |

### Parser routing

File extension is checked first:

```
.xlsx  → CMBExcelParser
.csv   → ICBCCSVParser (GBK encoding)
.pdf   → _detect_bank_from_pdf()
          ├── scanned / receipt → ICBCReceiptGridParser (grid-line OCR)
          ├── ICBC statement    → ICBCParser
          ├── CMB receipt       → CMBReceiptParser
          ├── CMB table         → CMBTableParser
          ├── CMB columnar      → CMBParser
          ├── GFB               → GFBTableParser
          └── unknown           → BankStatementParser (generic fallback)
```

---

## Architecture (process boundary)

```
Renderer (React)  ←IPC→  Electron main (Node.js)  ←stdio JSON-RPC→  Python backend
```

- Python backend (`bridge.py`) exposes JSON-RPC methods over stdio.
- All parsers return `ParseResult` objects — a shared contract keeps routing consistent.
- Configuration (科目, 账号 mapping rules) is built-in JSON under `apps/python/src/finance_agent_backend/config/`.

---

## Tech stack

- Electron 32 · React + Vite · TypeScript 5.6
- Python 3.11+, PyMuPDF, RapidOCR (ONNX), openpyxl, opencv-python
- PyInstaller (Python → bridge.exe), electron-builder (Electron → NSIS installer)
- Poetry (Python deps), ruff + black (Python lint/format)

---

## Key constraints

- Chinese text path handling on Windows: read PDFs as bytes, set `PYTHONIOENCODING=utf-8`.
- OCR is the slow path (~1–2 s/page); lazy-load RapidOCR only when needed.
- ICBC CSV is GBK-encoded with Tab characters inside fields.
- CMB Excel column layout differs from CMB PDF layout — separate parser.
