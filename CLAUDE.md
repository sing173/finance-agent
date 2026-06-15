# CLAUDE.md

本文件为 Claude Code 在此仓库中工作时提供指导。

## 项目概述

**FinanceAssistant** — 桌面应用：银行流水（PDF/CSV/Excel）→ 交易明细 → Excel / 金蝶凭证。

多进程架构：**Renderer**（React + TS + Vite）→ **Electron**（Node + TS）→ **Python**（stdio JSON-RPC）。

**当前状态**：v0.3.0 — 凭证系统（三层科目匹配 + SQLite 草稿 + TF-IDF 历史学习）已上线。

**范围**：领域上下文详见 `CONTEXT.md`。

---

## 关键决策与约束

### 路径解析
- 所有路径逻辑集中在 `apps/python/src/finance_agent_backend/paths.py`（开发环境与打包环境 `sys._MEIPASS` 双模式）。
- 禁止内联计算项目根路径 — 委托给 `paths.get_project_root()` / `get_config_path()` / `get_db_path()`。

### 数据库
- `db.get_db()` 无参时返回单例，传入 `db_path` 时返回独立连接（测试隔离）。
- WAL 模式，`foreign_keys=ON`，`sqlite3.Row` row factory。
- Schema 版本由 `schema_version` 表追踪；迁移通过 `init_db()` 执行。
- **测试必须传入 `db_path`** 获取隔离连接；不要在测试中依赖单例。

### 科目匹配（三层）
- L1：`RuleMatcher` — 从 `subject_mapping.json` 加载 JSON 规则
- L2：`HistoryMatcher` — TF-IDF 余弦相似度（阈值 0.75），类级缓存以 `(db_path, direction)` 为 key，`insert()` 时自动失效
- L3：`SubjectMatcher` — L1/L2 均未命中时返回 `unmatched`
- **训练数据**：仅用户导出时 `is_manual=1` 的分录写入 `subject_history`。自动匹配结果不记录。
- 完整匹配与训练细节见 `CONTEXT.md`。

### IPC / JSON-RPC
- 方法通过 `bridge.py` 中的 `@register_method("name")` 装饰器注册。
- 当前有效 RPC 方法：`parse_pdf`、`detect_banks`、`detect_supported_banks`、`generate_excel`、`import_subjects`、`get_subjects_info`、`select_file`、`voucher.preview`、`voucher.save_draft`、`voucher.export`、`voucher.list_drafts`、`voucher.load_draft`、`voucher.delete_draft`、`db.health`。
- 已删除：`health`（版本号改由 electron-builder 管理）、`generate_voucher_excel`（死代码，前端从未调用）、`parse_csv`（改用 `parse_pdf`）。
- **未知银行 → 强制拒绝**。无通用兜底解析器。用户必须手动选择银行 / docType。

### 解析器架构
- `tools/` 下 11 个解析器，全部继承 `BaseStatementParser`。
- `cmb_table_parser.py` 同时处理表格式流水和回单（内嵌 `_parse_receipt()` 方法）。
- `parser_router.py` 延迟导入 — 每次请求只加载需要的解析器。
- `detect_bank_from_pdf()` 返回 `dict{bankCode, bank, docType}`，而非裸 tuple。

### 凭证管道
- `voucher.preview` → `VoucherComposer` 按（账号, 对方科目, 方向, 对方账号）四元组合并。
- `voucher.save_draft` → 写入 `voucher_draft` + `voucher_draft_entry`（批量 INSERT）。
- `voucher.export` → 直接从 DB 分录导出 Excel（不重新匹配），写入 `export_log`，写入 `subject_history`（仅 manual），标记草稿为 `exported`。
- `match_source` 枚举：`rule` / `history` / `manual` / `unmatched` / `auto`。

### 前端
- `shared/types.ts`：仅类型定义（interface / type），不含函数或常量。工具函数就近存放于消费侧模块（如 `hooks/voucher_utils.ts`）。
- `useVoucherFlow.ts` 管理凭证状态机（idle → preview → saved → exported）。
- `SubjectPickerModal` 使用虚拟滚动（react-window）— 297 条科目仅渲染约 10 个 DOM 节点。

---

## 项目结构

```
apps/
├── electron/src/        # IPC 注册中心、Python 进程管理、preload
├── renderer/src/
│   ├── hooks/           # useVoucherFlow, useBatchOrchestrator, useDebounce, useSubjects
│   └── components/      # VoucherPreviewPanel, SubjectPickerModal, AccountSubjectManager, BatchFileSelector, BatchResultPanel, ...
└── python/src/finance_agent_backend/
    ├── bridge.py        # JSON-RPC 方法注册中心
    ├── paths.py         # 统一路径解析（dev/packaged 双环境）
    ├── db.py            # SQLite 单例 + schema 迁移
    ├── account_registry.py   # 账号→科目 CRUD + match_by_account
    ├── parser_router.py     # 按文件类型分发（延迟导入）
    ├── base_parser.py       # 共享 PDF/结果工具类（所有解析器继承）
    ├── subject_matcher.py   # RuleMatcher / HistoryMatcher / SubjectMatcher
    ├── subject_history_repo.py  # TF-IDF 仓库（类级缓存）
    ├── voucher_composer.py # 5 类组合器（GroupedTxn → VoucherGrouper → VoucherEntryFactory → VoucherComposer）
    ├── tools/            # 11 个解析器 + excel_builder + subject_loader
    └── config/           # subjects.json, subject_mapping.json, account_mapping.json
shared/types.ts          # IPC/JSON-RPC schema, Transaction 模型
docs/voucher-system-prd.md  # 凭证系统 PRD
```

---

## 开发工作流

```bash
# 初始化
cd apps/python && python -m venv .venv && .venv\Scripts\activate && pip install -e ".[dev]"
cd apps/electron && npm install
cd apps/renderer && npm install

# 开发模式
# 终端 1：cd apps/python && .venv\Scripts\activate && python src/finance_agent_backend/bridge.py
# 终端 2：cd apps/electron && npm run dev

# 测试
cd apps/python && pytest                                    # Python 单元测试
cd apps/renderer && npm test                               # Vitest
cd apps/electron && node tests/integration/v030-e2e.test.js # E2E（全功能）

# Lint
cd apps/python && ruff check . && black .
cd apps/electron && npm run lint
cd apps/renderer && npm run lint
```

### Windows 特有
- Bash 路径：使用正斜杠（`D:/git/finance-agent/...`）。
- 启动 Python 子进程时必须设置 `PYTHONIOENCODING=utf-8`。
- PyMuPDF：使用 `fitz.open("pdf", bytes)` 而非 `fitz.open(file_path)` — 解决中文路径问题。
- electron-builder 配置中 `asar: false`（`extraResources` 路径解析所必需）。

---

## 经验教训

### 打包
- PyInstaller C 启动器忽略 `PYTHONIOENCODING` → 在 bridge 启动时显式调用 `sys.stdin/stdout.reconfigure(encoding="utf-8")`。
- RapidOCR ONNX 模型必须加入 PyInstaller `datas`，否则打包后 OCR 静默失败。

### 数据库测试隔离
- `get_db(db_path=X)` 必须返回**新连接**，不能是单例。Bug 历史：曾返回缓存单例，污染测试结果。

### 死代码识别
- `generate_voucher_excel` 存在数月，前端从未调用。保留 bridge 方法前务必确认前端是否实际调用。
- 删除方法时需同步检查：`preload.ts`、`ipc.ts`、`App.tsx`、`shared/types.ts`。

### 科目匹配
- 训练数据质量很重要：只有手动修正的结果才应进入 `subject_history`，自动匹配的噪声会降低 TF-IDF 准确度。
- 缓存失效必须在 `insert()` 路径上触发，不能只在 `find_similar()` 中处理。

---

## 参考

- [Electron](https://www.electronjs.org/docs) · [PyMuPDF](https://pymupdf.readthedocs.io/) · [RapidOCR](https://github.com/RapidAI/RapidOCR)
- [openpyxl](https://openpyxl.readthedocs.io/) · [PyInstaller](https://pyinstaller.org/) · [electron-builder](https://www.electron.build/)
- `CONTEXT.md` — 领域语言、架构、匹配逻辑
- `docs/voucher-system-prd.md` — 凭证功能规格

---

## Agent skills

### Issue tracker

Issues and PRDs live as GitHub Issues for `sing173/finance-agent`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical role names (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.
