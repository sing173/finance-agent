# CONTEXT.md — FinanceAssistant Domain Context

## Project

**FinanceAssistant** — Desktop app: bank statement (PDF/CSV/Excel) → transactions → Excel/Kingdee vouchers.

**Scope**: No reconciliation (对账).

---

## Key Terms

| Term | Meaning |
|------|---------|
| 流水 / Statement | 水平多行交易明细 |
| 回单 / Receipt | 垂直单条交易凭证 |
| 科目 / Subject | 会计科目 |
| 凭证 / Voucher | 金蝶精斗云导入格式 |
| bankCode | 银行路由键（ICBC/CMB/GFB） |
| docType | `流水` / `回单` / `流水`（兜底） |

---

## Banks

| Bank | Code | Statement | Receipt | CSV | Excel |
|------|------|-----------|---------|-----|-------|
| 工商银行 | ICBC | `icbc_parser.py` | `icbc_receipt_grid_parser.py` | `icbc_csv_parser.py` | — |
| 招商银行 | CMB | `cmb_table_parser.py`, `cmb_parser.py` | `cmb_receipt_parser.py` | — | `cmb_excel_parser.py` |
| 广发银行 | GFB | `gfb_table_parser.py` | — | — | — |

---

## Routing

**v0.2.0** (structure/account matching):

```
.xlsx  → CMBExcelParser
.csv   → ICBCCSVParser (GBK)
.pdf   → detect_bank_from_pdf() — three-level routing
          Level 1: Embedded PDF → structure matcher (all/any modes) → (bankCode, docType)
          Level 2: Scanned PDF → OCR account number → account_registry.match_by_account()
          Route via PARSER_REGISTRY[bankCode] ordered list (first result wins)
          Unknown bank → force-reject (user must manually select bank)
```

**v0.3.0 planned** (three-layer voucher matching):

```
L1 JSON rules → L2 SQLite history (TF-IDF ≥ 0.75) → L3 manual subject picker
PARSER_REGISTRY unchanged from v0.2.0.
```

---

## Voucher System (v0.3.0 planned)

**Three-layer matching**: L1 JSON rules → L2 SQLite history (TF-IDF ≥ 0.75) → L3 manual

**Storage**: JSON config (git-tracked) + SQLite runtime (`%APPDATA%/FinanceAssistant/data.db`)

---

## Architecture

```
Renderer (React)  ←IPC→  Electron (Node)  ←stdio JSON-RPC→  Python
```

- `bridge.py`: JSON-RPC registry
- All parsers return `ParseResult`
- Config: `apps/python/src/finance_agent_backend/config/`
- `shared/types.ts`: 仅类型定义（interface/type），零函数/常量导出。工具函数放各自就近模块（如 voucher 工具放 `hooks/voucher_utils.ts`）。

---

## Stack

- Electron 32 · React + Vite · TS 5.6
- Python 3.11+, PyMuPDF, RapidOCR, openpyxl, opencv-python
- SQLite (v0.3.0+)
- PyInstaller + electron-builder (NSIS)
- Poetry, ruff, black

---

## Constraints

- Windows Chinese paths: read PDFs as bytes, `PYTHONIOENCODING=utf-8`
- OCR: ~1-2s/page; lazy-load RapidOCR
- ICBC CSV: GBK + Tab-in-fields
- CMB Excel vs PDF: separate parsers
- No reconciliation (对账)
