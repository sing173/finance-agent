# CONTEXT.md — 财务助手领域上下文

## 项目概述

**FinanceAssistant** — 桌面应用：银行流水（PDF/CSV/Excel）→ 交易明细 → Excel / 金蝶凭证。


---

## 核心术语

| 术语 | 含义 |
|------|------|
| 流水 / Statement | 水平多行交易明细 |
| 回单 / Receipt | 垂直单条交易凭证 |
| 科目 / Subject | 会计科目 |
| 凭证 / Voucher | 金蝶精斗云导入格式 |
| bankCode | 银行路由键（ICBC/CMB/GFB） |
| docType | `流水` / `回单` / `流水`（兜底） |

---

## 银行支持

| 银行 | 代码 | 流水 | 回单 | CSV | Excel |
|------|------|------|------|-----|-------|
| 工商银行 | ICBC | `icbc_parser.py` | `icbc_receipt_grid_parser.py` | `icbc_csv_parser.py` | — |
| 招商银行 | CMB | `cmb_table_parser.py`, `cmb_parser.py` | `cmb_receipt_parser.py` | — | `cmb_excel_parser.py` |
| 广发银行 | GFB | `gfb_table_parser.py` | — | — | — |

---

## 路由逻辑

```
.xlsx  → CMBExcelParser（招行 Excel 流水）
.csv   → ICBCCSVParser（工行 CSV，GBK 编码 + 字段内嵌 Tab）
.pdf   → detect_bank_from_pdf() — 三级路由
          一级：原生 PDF → 结构匹配器（all/any 模式）→ (bankCode, docType)
          二级：扫描件 PDF → OCR 账号 → account_registry.match_by_account()
          通过 PARSER_REGISTRY[bankCode] 有序列表路由（首个命中即停，无兜底链）
          未知银行 → 强制拒绝，用户须手动选择银行

```

---

## 凭证系统

### 三层科目匹配

| 层级 | 机制 | 触发时机 |
|------|------|---------|
| L1 | JSON 规则匹配（`subject_mapping.json`，priority 排序 + keywords + counterparty_pattern + direction 分离） | 自动匹配 |
| L2 | TF-IDF 余弦相似度（中文 2-gram，阈值 0.75） | 自动匹配 |
| L3 | 兜底 `unmatched`，前端标红，用户手动选择 | L1/L2 均未命中 |

三层通过 `RuleMatcher → HistoryMatcher → SubjectMatcher` 策略链顺序执行，命中即停。

### L2 训练过程

仅 `is_manual=1` 且用户确认导出的分录写入 `subject_history`，自动匹配不记录。

1. 写入字段：`summary`、`subject_code`、`subject_name`、`direction`、`counterparty`
2. 唯一约束 `(summary_hash, subject_code, direction)` 去重
3. 类级缓存 `_cache[(db_path, direction)]`，insert 后自动失效，新数据立即生效
4. 下次相同 / 相似摘要出现时，中文 2-gram 分词 → TF-IDF 向量 → 余弦相似度 ≥ 0.75 即命中

### 凭证全生命周期

```
解析交易 → VoucherComposer 按 (账号, 对方科目, 方向, 对方账号) 四元组合并
         ↓
VoucherPreviewPanel（全屏子页面）
  - 列：凭证号、日期、摘要、科目（可编辑）、借方、贷方、对方户名、匹配来源
  - 支持：SubjectPickerModal 选科目 / 批量填充 / 保存草稿 / 确认导出
         ↓
voucher.save_draft  → voucher_draft + voucher_draft_entry
voucher.export     → Excel 导出 + export_log 写入 + subject_history 写入(manual only) + 标记 exported
voucher.list_drafts / load_draft / delete_draft
```

导出直出 DB 分录，不重新做科目匹配，与预览面板完全一致。

### 数据库 Schema

| 表 | 用途 | 关键字段 |
|----|------|---------|
| `voucher_draft` | 凭证草稿头 | id, name, period, status(draft/confirmed/exported) |
| `voucher_draft_entry` | 分录明细 | draft_id, voucher_no, entry_seq, subject_code, debit/credit_amount, direction, match_source, is_manual |
| `subject_history` | L2 训练库 | summary_hash, subject_code, direction, confirmed_at |
| `export_log` | 导出审计日志 | exported_at, period, file_path, match_stats, draft_id |

`match_source` 枚举：`rule` / `history` / `manual` / `unmatched` / `auto`

---

## 架构

```
Renderer（React）  ←IPC→  Electron（Node）  ←stdio JSON-RPC→  Python
```

- `bridge.py`：JSON-RPC 方法注册中心
- 所有解析器统一返回 `ParseResult`
- 配置目录：`apps/python/src/finance_agent_backend/config/`
- `shared/types.ts`：仅类型定义（interface / type），零函数 / 常量导出。工具函数就近存放于各自模块（如 voucher 工具放 `hooks/voucher_utils.ts`）。

---

## 技术栈

- Electron 32 · React + Vite · TS 5.6
- Python 3.11+，PyMuPDF，RapidOCR，openpyxl，opencv-python
- SQLite（WAL 模式）
- PyInstaller + electron-builder（NSIS 安装包）
- Poetry，ruff，black

---

## 约束与注意事项

- Windows 中文路径：PDF 以 bytes 方式读取，环境变量 `PYTHONIOENCODING=utf-8`
- OCR：约 1–2 秒 / 页；延迟加载 RapidOCR
- 工行 CSV：GBK 编码 + 字段内嵌 Tab 字符
- 招行 Excel 与 PDF：各自独立解析器
