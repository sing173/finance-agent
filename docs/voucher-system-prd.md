# 凭证生成系统 — 需求对齐文档

> 分支：待定
> 版本：v0.3.0
> 目标：将凭证生成从"一次性黑盒导出"升级为**三层匹配 + 人工确认**的可控流程

---

## 一、背景与现状

### 1.1 项目定位

FinanceAssistant 的核心输出是**凭证 Excel**（金蝶精斗云导入格式）。用户提供银行流水/回单文件，系统解析出交易数据，自动匹配会计科目并推导借贷方向，最终生成可直接导入财务系统的凭证。

### 1.2 当前流程

```
流水解析 → 账号后4位匹配银行科目 + 摘要关键字匹配对方科目 → 推导借贷方向 → 一键导出 Excel
```

两端匹配各自独立：

| 匹配对象 | 数据来源 | 方式 |
|---------|---------|------|
| 银行科目（本方） | `account_mapping.json` | 账号后4位查表 |
| 对方科目 | `subject_mapping.json` | 摘要包含关键字 |

借贷方向由交易方向推导：支出 → 借对方贷银行，收入 → 借银行贷对方。

### 1.3 核心痛点

| # | 痛点 | 影响 |
|---|------|------|
| P1 | 账号→科目映射硬编码在 `account_mapping.json`，无管理界面，需改 JSON 文件来新增/修改账号 | 用户无法自主维护账号→科目映射，新增银行账号成本高 |
| P2 | 摘要→科目仅靠关键字匹配，一词多义时命中错误科目 | "服务费"可能是物业费/研发费/收入，无上下文区分 |
| P3 | 凭证无预览即导出，科目为空也照写 Excel | 导入金蝶后发现科目缺失，需逐条补填 |
| P4 | 关键字规则全靠 JSON 手写，缺少结构化的联合匹配条件 | 无法区分不同对方户名的同关键字交易 |

---

## 二、设计方案

### 2.1 三层匹配体系

```
Layer 1: JSON 规则匹配（确定性）
  └── 多字段联合条件：关键字 + 方向 + 对方户名 + 金额范围
  └── 覆盖 80% 常见场景

Layer 2: 历史学习（用户反馈驱动）
  └── 用户手动修正科目 → 记录到 SQLite 历史库
  └── 下次相似摘要 → 余弦相似度匹配历史记录

Layer 3: 凭证预览兜底（人工）
  └── 前两层都未命中 → 科目留空，标记为 ⚠
  └── 用户在预览面板手动选择
```

### 2.2 数据分层策略

```
┌─────────────────────────────────────────────┐
│           JSON 配置层（git 可追踪）            │
│                                              │
│  subjects.json          — 科目字典            │
│  subject_mapping.json   — 关键字规则 (L1)     │
│  account_mapping.json   — 账号→科目映射       │
│                                              │
│  → 变更频率低，发行版内置                      │
└────────────────────┬────────────────────────┘
                     │
                     │ 加载时读入，运行时不写
                     │
┌────────────────────▼────────────────────────┐
│           SQLite 运行时层                     │
│                                              │
│  subject_history    — 历史学习 (L2)           │
│  voucher_draft      — 凭证草稿               │
│  voucher_draft_entry— 草稿分录明细            │
│  export_log         — 导出审计记录            │
│                                              │
│  → 用户操作产生，随使用增长                    │
│  → 存储路径：%APPDATA%/FinanceAssistant/data.db│
└──────────────────────────────────────────────┘
```

---

## 三、功能需求

### FR-0：解析器路由重构（旧版改造）

#### 背景

当前 `parser_router._do_parse_pdf()` 通过关键字匹配识别银行名（`BANK_KEYWORDS`），然后按 `if '工商'/'招商'/'广发' in bank` 门控路由到对应 parser。这条路有两大缺陷：

1. **关键字匹配不可靠**：银行名不出现（部分模板无银行标题）或关键字二义（如 ICBC 同时出现在多银行联名单据中）则失灵
2. **无关的路由耦合**：11 个 parser 中只有 2 个回单 parser 内含银行名作为 OCR 布局锚点，其余 9 个根本不检查银行身份——说明 parser 不需要事先知道"这是哪家银行"，只需要知道"这个文档结构长得像我的格式"

FR-0 的目标：将路由从"银行关键字识别"改为**结构特征驱动的多级路由**，同时保持前端"选择文件→识别银行→解析→展示→导出"的交互流程不变。

#### 设计：三级路由体系

```
route(file_path)
  │
  ├── Level 0: 扩展名分流（现有，保留）
  │   .csv  → 直接路由（当前仅 ICBCCSVParser，预留未来多 parser 扩展）
  │   .xlsx → 直接路由（当前仅 CMBExcelParser，预留未来多 parser 扩展）
  │   .pdf  → fitz 检测是否有嵌入式文本 → 分支
  │
  ├── Level 1: 嵌入式 PDF → 结构特征匹配 → 试错兜底
  │   fitz 提取前 3 页文本 → 匹配表标题+列头关键字
  │   命中 → 返回 (bank, docType) → 路由到对应 parser
  │   未命中 → _has_result 试错链（逐个尝试 parser，返回 0 条跳过）
  │   （不经过账号匹配——嵌入式文本中账号提取不可靠）
  │
  └── Level 2: 扫描件/图片 PDF → OCR 账号匹配 → ManualOverride 兜底
      fitz 文本为空 → 渲染首页为图片 → RapidOCR
      → 正则提取账号 → account_registry.match_by_account()
      命中 → 返回 (bank, docType) → 路由到对应 parser
      未命中 → ('未知银行', 'unknown') → 前端 ManualOverrideModal
```

**关键变化**：路由仍然存在，仍然识别银行，仍然返回 `(bank, docType)`。改变的是**用什么方法判断**——从不可靠的关键字匹配改为可靠的结构/账号匹配。

#### 决策原理

| 文件类型 | 主路径 | 兜底 | 跳过 |
|---------|--------|------|------|
| 嵌入式 PDF（招行、广发） | Level 1 结构特征匹配，命中即停 | _has_result 试错链 | Level 2（嵌入式文本中账号提取不可靠） |
| 扫描件/图片 PDF（工行 receipt） | Level 2 OCR → 账号匹配 | ManualOverrideModal | 试错链（OCR parser 代价高，账号匹配不到 = 无法识别） |

#### Level 1：嵌入式 PDF 结构特征匹配

`fitz` 提取前 3 页文本，检测表标题+列头组合：

```python
PDF_STRUCTURE_MATCHERS = [
    # (标题关键字, 列头关键字...) → (bank, doc_type)
    # 招商银行 — 嵌入式 PDF
    ('账务明细清单', '交易日期', '交易金额'): ('招商银行', 'statement'),
    ('Date', 'Currency', 'Counter Party'): ('招商银行', 'statement'),
    ('出账回单', '入账回单'): ('招商银行', 'receipt'),
    # 广发银行 — 嵌入式 PDF
    ('交易日期', '交易类型', '交易金额'): ('广发银行', 'statement'),
    # 工商银行 — 不在此列表。工行 receipt 全是扫描件，无嵌入式文本
]
```

匹配规则：
- 标题关键字 AND 列头关键字 同时出现 → 命中
- 回单类（只有标题无列头）→ 仅匹配标题
- **Level 1 命中即停**，不进入后续 Level 校验。后续可扩展为让客户自行配置结构特征规则

未命中（无匹配的结构特征）→ `_has_result` 试错链：

```
CMBTableParser → CMBReceiptParser → CMBParser → GFBTableParser → BankStatementParser
（不包含 ICBCReceiptGridParser、ICBCParser——这两个是 OCR parser，嵌入式 PDF 不适用）
```

#### Level 2：扫描件/图片 OCR + 账号匹配

仅当 `fitz` 嵌入式文本为空时进入：

```
1. fitz 渲染首页为图片 → RapidOCR 识别文字
2. 正则 \d{12,19} 提取所有候选账号
3. account_registry.match_by_account() —— 遍历候选账号，首个命中即返回
4. 命中 → 返回 (entry.bank, 'receipt')
5. 未命中 → 返回 ('未知银行', 'unknown')
```

`detect_bank_from_pdf()` 保留但重写：改为调用 `_match_pdf_structure(text)` 替代 `_classify()`。

#### PARSER_REGISTRY：统一 bankCode → parser 映射

所有检测路径统一返回 `(bankCode, docType)`，`_do_parse_pdf()` 通过查表路由，不再用 `if '工商'/'招商'/'广发' in bank` 门控：

```python
# bankCode 是路由 key，bank 中文名仅用于 UI 展示
PARSER_REGISTRY: dict[str, dict] = {
    'ICBC': {
        'statement':  ('icbc_parser', 'ICBCParser'),
        'receipt':    ('icbc_receipt_grid_parser', 'ICBCReceiptGridParser'),
        'fallback':   ('icbc_parser', 'ICBCParser'),
    },
    'CMB': {
        'statement':  {
            'table':  ('cmb_table_parser', 'CMBTableParser'),
            'column': ('cmb_parser', 'CMBParser'),
        },
        'receipt':    ('cmb_receipt_parser', 'CMBReceiptParser'),
        'fallback':   ('pdf_parser', 'BankStatementParser'),
    },
    'GFB': {
        'statement':  ('gfb_table_parser', 'GFBTableParser'),
        'fallback':   ('pdf_parser', 'BankStatementParser'),
    },
}

DEFAULT_PARSER = ('pdf_parser', 'BankStatementParser')
```

**`_do_parse_pdf()` bank 参数行为**：
- `bank` 非空 → **外部覆盖**，跳过 Level 1/2 检测，直接用 `bank` 值查 PARSER_REGISTRY
- `bank` 为空/None → 走完整三级路由检测
- 用户在前端 `ManualOverrideModal` 手动选择银行后传入 `bank`，此时绕过检测

#### 对 parser 本身的影响

**parser 代码完全不变**。变化只在 `parser_router`：
- `BANK_KEYWORDS` 字典 → 删除，替换为 `PDF_STRUCTURE_MATCHERS`
- `_classify()` 内部函数 → 删除，替换为 `_match_pdf_structure()`
- `detect_bank_from_pdf()` → 保留函数签名，重写为三级路由调度：L1 结构特征 → L2 账号匹配 → 兜底 ManualOverride
- 新增 `_detect_bank_by_ocr_account()` — OCR 首页 + 正则提取账号 → account_registry.match_by_account()
- `_do_parse_pdf()` 中的 `if '工商'/'招商'/'广发' in bank` 门控 → 删除，改为直接根据 `bankCode` 查 `PARSER_REGISTRY` 映射表
- `try_receipt_first` → 删除（Level 2 OCR 账号匹配已从 account_registry 返回 bankCode + docType）
- `detect_cmb_pdf_type()` → 并入 Level 1 结构匹配器，删除独立函数

#### 前端保持不变

```
选择文件 → detectBanks([filePath])
  → 后端检测银行（新方法：结构特征/OCR 账号匹配）
  → 返回 { bank, bankCode, docType, status }
  
展示结果: "检测到：工商银行 · 流水"
  → 用户确认 → parseFile({ filePath, bank, docType })
  → 解析 → 展示交易列表
  → 导出凭证（走 FR-1/2/3 凭证预览流程）
```

`detect_banks` JSON-RPC 签名不变，`DetectFileResult` 结构不变（仅内部增加 `bankCode` 字段用于 parser 路由），`App.tsx` 检测流程不变。唯一变化：检测结果更可靠——结构特征匹配（嵌入式 PDF）比关键字二义性低，账号匹配（扫描件）能精确定位银行和科目。

#### 涉及改动的文件

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `parser_router.py` | **重构** | 新增 `PARSER_REGISTRY`、`PDF_STRUCTURE_MATCHERS`；`_classify()`→`_match_pdf_structure()`；新增 `_detect_bank_by_ocr_account()`；`detect_bank_from_pdf()` 重写为三级路由调度；`_do_parse_pdf()` 门控改为 PARSER_REGISTRY 查表；删除 `try_receipt_first`、`detect_cmb_pdf_type()` |
| `bridge.py` | **微调** | 删除 `_detect_bank_from_pdf()` 代理和 `detect_cmb_pdf_type()` 代理；`handle_detect_banks` 内联调用新 `detect_bank_from_pdf()` |
| `account_mapping.json` | **升级** | 直接采用 v2 格式（增加 `id`/`matchType`/`bank`/`bankCode`/`subjectCode`/`subjectName` 字段），保留 `defaultBankSubjectCode` |
| `account_registry.py` | **新增** | `match_by_account()` 按账号匹配返回 AccountEntry（含 bankCode、subjectCode 等），同时服务 FR-0 OCR 路由和 FR-1 凭证科目填充 |
| `parser`（11 个） | **不变** | 照常解析，不受路由重构影响 |
| `App.tsx` / `ManualOverrideModal` / `shared/types.ts` | **不变** | 检测→解析→展示流程不变 |

---

### FR-1：账号-科目管理

#### 用途

建立银行账号→科目的映射知识库，服务于**凭证生成**一个环节：
- 凭证导出时，从流水中的银行账号查表 → 自动填充银行科目代码和科目名称

#### 数据模型（升级 `account_mapping.json`）

```json
{
  "accounts": [
    {
      "id": "acc_001",
      "matchType": "suffix",
      "pattern": "4363",
      "bank": "工商银行",
      "bankCode": "ICBC",
      "subjectCode": "1000201",
      "subjectName": "银行存款-工行基本户"
    }
  ],
  "defaultBankSubjectCode": "10002"
}
```

字段说明：

| 字段 | 说明 |
|------|------|
| `id` | 自动生成（时间戳），仅用于删除/编辑时定位，表单不展示 |
| `matchType` | `suffix` / `exact` |
| `pattern` | 匹配用的账号片段 |
| `bank` | 银行名称（选择 bankCode 后自动填充，可手动修改） |
| `bankCode` | 银行简称（ICBC/CMB/GFB）——下拉选择，选项来自后端 `detect_supported_banks`；FR-0 PARSER_REGISTRY 路由 key |
| `subjectCode` | 对应的会计科目代码 |
| `subjectName` | 科目全名（从 `subjects.json` 带出，冗余便于展示） |

#### 匹配引擎

```python
# account_registry.py
class AccountRegistry:
    def __init__(self, config_path: str):
        """从 account_mapping.json 加载。加载时信任存储值（不重新对齐 subjectName）。"""

    def match_by_account(self, account_number: str) -> AccountEntry | None
        """按 matchType 规则遍历所有条目。
        优先级: exact > suffix。
        返回 AccountEntry（含 bank, bankCode, subjectCode, subjectName）。
        """

    # CRUD 方法
    def list_all(self) -> list[AccountEntry]: ...
    def add(self, entry: AccountEntry) -> None:
        """保存时校验 subjectCode 存在于 subjects.json 中，校验失败抛 ValueError。"""
    def update(self, id: str, entry: AccountEntry) -> None:
        """保存时校验 subjectCode 存在于 subjects.json 中，校验失败抛 ValueError。"""
    def delete(self, id: str) -> None: ...
```

**存储策略**：Phase 0/1 阶段直接读写 `account_mapping.json` 文件（与 `subjects.json` 同级），不引入 SQLite。Phase 3 引入 SQLite 后一并迁移，改用 `data.db` 中的 `account_mappings` 表。

#### 管理功能

| 功能 | 说明 |
|------|------|
| 入口 | 系统设置卡片中增加"账号管理"按钮，点击弹出 Modal |
| 列表视图 | 表格展示所有账号条目（匹配类型/模式/银行/科目代码/科目名称），无搜索框 |
| 新增 | 表单：匹配类型下拉（suffix/exact）、匹配模式输入框、银行代码下拉（选项来自后端 `detect_supported_banks`，选择后 `bank` 自动填充中文名）、科目选择器（复用 `SubjectPickerModal`）。`bankCode` + `subjectCode` 均必填，`subjectCode` 须存在于 `subjects.json` 中 |
| 编辑 | 同新增表单，预填当前值 |
| 删除 | 确认后删除，不可恢复 |
| 科目选择器 | 复用 `SubjectPickerModal`（搜索/分类筛选弹窗），与 FR-3 凭证预览中共用同一组件 |
| xlsx 导入 | 预留，Phase 1 不实现 |
| xlsx 导出 | 预留，Phase 1 不实现 |

---

### FR-2：交易-科目三层匹配规则

#### Layer 1：JSON 关键字规则（保留并增强）

**数据模型**（升级 `subject_mapping.json`）：

```json
{
  "version": 2,
  "expense": {
    "default_subject_code": "",
    "rules": [
      {
        "id": "rule_001",
        "priority": 1,
        "match": {
          "keywords": ["物业费", "物管费", "物业管理费"],
          "counterparty_pattern": "启胜"
        },
        "subject_code": "5060203",
        "subject_name": "管理费用_物业管理费",
        "comment": "启胜物业管理费（联合规则）"
      },
      {
        "id": "rule_002",
        "priority": 2,
        "match": {
          "keywords": ["服务费", "技术服务费"],
          "counterparty_pattern": "科技"
        },
        "subject_code": "403010113",
        "subject_name": "研发支出_技术服务费",
        "comment": "技术服务费（限定对方户名含'科技'）"
      },
      {
        "id": "rule_003",
        "priority": 3,
        "match": {
          "keywords": ["手续费", "服务费用", "汇款手续费"]
        },
        "subject_code": "1022120",
        "subject_name": "其他应收款_手续费",
        "comment": "银行手续费（纯关键字）"
      }
    ]
  },
  "income": {
    "default_subject_code": "",
    "rules": [
      {
        "id": "rule_004",
        "priority": 1,
        "match": {
          "keywords": ["收款", "回款", "货款", "销售收入"]
        },
        "subject_code": "10122",
        "subject_name": "应收账款",
        "comment": "销售收入回款"
      }
    ]
  }
}
```

`match` 字段规则：

| 条件字段 | 必填 | 说明 |
|---------|------|------|
| `keywords` | 是 | 任一命中即触发 |
| `direction` | 否 | 规则已按 expense/income 分组，此字段预留 |
| `counterparty_pattern` | 否 | 对方户名包含此字符串 |
| `amount_min` / `amount_max` | 否 | 金额范围（预留） |

匹配优先级：
1. 联合规则（keywords + counterparty_pattern）优先于纯 keywords 规则
2. 长关键字优先于短关键字（"物业管理费" > "物管费" > "物业"）
3. 命中即停，不继续尝试
4. 全部未命中 → `default_subject_code`（兜底科目）

**不引入 DSL**：规则保持 JSON 格式，与项目现有配置体系一致（`subjects.json`、`account_mapping.json` 均为 JSON），无需新解析器。

#### Layer 2：历史学习（仅用户手动修正触发）

**设计原则**：简单、零依赖、用户驱动。

```
凭证预览 → 用户手动修改了某条分录的科目 → 记录到 subject_history 表
凭证预览 → 自动匹配的科目用户未改动 → 不记录
```

**触发条件**：
- 用户在凭证预览面板中 **手动选择或修改** 了科目代码
- 从前端传入 `is_manual=true` 标记
- 后端在确认导出时写入 `subject_history` 表

**匹配方式**（TF-IDF 余弦相似度，纯 Python 标准库）：

```python
# subject_matcher.py

def match_by_history(summary: str, direction: str) -> str | None:
    """在 subject_history 中查找与摘要最相似的记录。
    
    1. 中文 2-gram 字符切片分词（不需要 jieba）
    2. 计算 TF-IDF 向量
    3. 余弦相似度 ≥ 0.75 → 返回科目代码
    4. < 0.75 → 返回 None（不匹配，留给 Layer 3 手动）
    """
```

**实现依赖**：`math.sqrt` + `collections.Counter` + `sqlite3`，全部标准库，~80 行代码。

#### Layer 3：凭证预览手动兜底

Layer 1 + Layer 2 都未命中 → 科目留空，在凭证预览中高亮标记为 ⚠，用户手动选择。

详见 FR-4。

---

### FR-3：凭证预览 + 手动配置

#### 用途

在导出 Excel 之前展示每条凭证的分录、科目、金额、借贷方向，允许用户修改。这是三个需求中最核心的环节——它是自动匹配的最终防线。

#### 预览面板示意

```
┌─ 凭证预览（12笔流水 → 3张凭证） ──────────────────────────────┐
│                                                                │
│  ⚠ 有 2 条分录未匹配到对方科目                                   │
│                                                                │
│  ┌─ 凭证 #1 物业管理费 ───────────────────────────────────┐    │
│  │ 日期: 2026-03-31                                        │    │
│  │                                                         │    │
│  │ 分录1  借  5060203  管理费用_物业管理费   ¥1,200.00      │    │
│  │ 分录2  借  5060203  管理费用_物业管理费   ¥1,200.00      │    │
│  │ 分录3  贷  1000201  银行存款_工行基本户   ¥2,400.00      │    │
│  │        ↑ 合并自: 支付启胜物业1月/2月管费                  │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌─ 凭证 #2 技术服务费 ───────────────────────────────────┐    │
│  │ 日期: 2026-03-31                                        │    │
│  │                                                         │    │
│  │ 分录1  借  403010113  研发支出_技术服务费  ¥50,000.00    │    │
│  │ 分录2  贷  1000201  银行存款_工行基本户    ¥50,000.00    │    │
│  │        match: rule（规则命中）                            │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌─ 凭证 #3 ⚠ 未匹配 ───────────────────────────────────┐    │
│  │ 日期: 2026-03-31  摘要: 网银转账                          │    │
│  │                                                         │    │
│  │ 分录1  借  [点击选择科目 ▼]                ¥5,000.00  ⚠  │    │
│  │ 分录2  贷  [1000201 ▼] 银行存款_工行基本户  ¥5,000.00    │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                │
│                              [取消]  [保存草稿]  [确认导出]      │
└────────────────────────────────────────────────────────────────┘
```

#### 功能点

| # | 功能 | 说明 |
|---|------|------|
| F1 | 凭证列表展示 | 所有凭证按凭证号排列，每条显示日期、摘要、分录行、匹配来源 |
| F2 | 科目可编辑 | 点击科目代码弹出 `SubjectPickerModal`（搜索/分类筛选） |
| F3 | 异常高亮 | 未匹配科目（`source=unmatched`）红色/警告标记 |
| F4 | 匹配来源标识 | 每条分录标记来源：`rule` / `history` / `manual` / `unmatched` |
| F5 | 同类交易合并 | 相同对方科目的交易合并为一张凭证（凭证号一致，分录序号递增），每笔原交易保留为独立分录行 |
| F6 | 借贷方向覆盖 | 正常由收入/支出自动推导，允许手动翻转（处理转账、退款等特殊场景） |
| F7 | 批量操作 | "全部应用兜底科目"、一键填充相同科目到所有未匹配分录 |
| F8 | 保存草稿 | 未完成配置存为草稿（SQLite），下次打开继续编辑 |
| F9 | 加载草稿 | 从历史草稿列表中选择恢复 |
| F10 | 确认导出 | 最终确认后生成金蝶精斗云格式 Excel；导出后写入 `export_log` |

#### 同类交易合并规则

```
合并条件:
  - 对方科目代码相同
  - 交易方向相同（同为借或同为贷）
  - 银行科目相同

合并结果:
  - 生成一张凭证（凭证号一致）
  - 每条原交易作为独立分录行（分录序号递增）
  - 银行方分录金额 = 该凭证下所有原交易金额之和
  - 摘要取第一条原交易的摘要
  - 借方合计 = 贷方合计（系统校验）
```

#### 借贷方向规则

| 交易方向 | 分录1（借方） | 分录2（贷方） |
|---------|-------------|-------------|
| 支出 | 对方科目，金额 | 银行科目，金额 |
| 收入 | 银行科目，金额 | 对方科目，金额 |
| 退款冲销 | 银行科目，金额 | 原对方科目（冲减），金额 |

退款冲销场景需要用户在预览面板手动调整——系统难以自动判断是退款还是新收入。

---

### FR-4：SQLite 数据库

#### 4.1 部署

- 路径：`%APPDATA%/FinanceAssistant/data.db`
- 引擎：Python 标准库 `sqlite3`，零额外依赖
- 模式：WAL 模式（读写并发友好）
- 迁移：版本号记录在 `schema_version` 表，启动时自动检查并执行迁移

#### 4.2 表结构

```sql
-- 历史学习库（Layer 2）
CREATE TABLE subject_history (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  summary         TEXT    NOT NULL,
  summary_hash    TEXT    NOT NULL,
  subject_code    TEXT    NOT NULL,
  subject_name    TEXT,
  direction       TEXT    NOT NULL CHECK (direction IN ('expense', 'income')),
  amount          REAL,
  counterparty    TEXT,
  confirmed_at    TEXT    NOT NULL,
  voucher_id      TEXT,
  UNIQUE(summary_hash, subject_code, direction)
);

CREATE INDEX idx_history_code_dir ON subject_history(subject_code, direction);
CREATE INDEX idx_history_hash ON subject_history(summary_hash);


-- 凭证草稿
CREATE TABLE voucher_draft (
  id              TEXT PRIMARY KEY,
  name            TEXT,
  period          TEXT,
  status          TEXT NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft', 'confirmed', 'exported')),
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  metadata_json   TEXT
);

CREATE TABLE voucher_draft_entry (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id        TEXT NOT NULL REFERENCES voucher_draft(id) ON DELETE CASCADE,
  entry_seq       INTEGER NOT NULL,
  voucher_no      INTEGER NOT NULL,
  date            TEXT NOT NULL,
  summary         TEXT NOT NULL,
  subject_code    TEXT NOT NULL,
  subject_name    TEXT,
  debit_amount    REAL,
  credit_amount   REAL,
  direction       TEXT,
  counterparty    TEXT,
  match_source    TEXT CHECK (match_source IN ('rule', 'history', 'manual', 'unmatched')),
  original_summary TEXT,
  original_amount  REAL,
  is_manual       INTEGER DEFAULT 0,
  sort_order      INTEGER DEFAULT 0
);

CREATE INDEX idx_draft_entry ON voucher_draft_entry(draft_id);


-- 导出审计日志
CREATE TABLE export_log (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  exported_at       TEXT NOT NULL,
  period            TEXT,
  file_path         TEXT NOT NULL,
  voucher_count     INTEGER,
  entry_count       INTEGER,
  transaction_count INTEGER,
  source_files      TEXT,
  match_stats       TEXT,
  draft_id          TEXT
);


-- Schema 版本管理
CREATE TABLE schema_version (
  version   INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
```

#### 4.3 表职责

| 表 | 读写模式 | 数据量预期 |
|---|---------|-----------|
| `subject_history` | 用户手动修正时追加写入；Layer 2 匹配时只读 | 数百条（去重防膨胀） |
| `voucher_draft` + `voucher_draft_entry` | 草稿保存/加载；导出后标记状态 | 数十条（草稿可手动清理） |
| `export_log` | 每次确认导出追加一条 | 随使用增长（只增不删） |

---

## 四、架构变更

### 4.1 后端新增

#### Phase 0（FR-0 路由重构）

| 文件 | 职责 |
|------|------|
| `account_registry.py` | `match_by_account()` 账号→科目匹配引擎（纯 JSON 文件读写，无 SQLite），服务 Level 2 OCR 路由 |

#### Phase 1（FR-1 账号-科目管理）

| 文件 | 职责 |
|------|------|
| `account_registry.py` | 扩展：新增 CRUD 方法（list/add/update/delete） |

#### Phase 2-3（后续阶段）

| 文件 | 职责 |
|------|------|
| `db.py` | SQLite 连接管理（WAL 模式）、建表、迁移 |
| `subject_matcher.py` | 三层匹配引擎：L1 JSON 规则 → L2 SQLite 历史 → L3 兜底 |
| `subject_history_repo.py` | 历史学习库读写 |
| `voucher_composer.py` | 凭证组装 + 同类合并 + 草稿/导出读写 |

### 4.2 后端修改

#### Phase 0

| 文件 | 改动 |
|------|------|
| `parser_router.py` | **路由重构**：新增 `PARSER_REGISTRY`、`PDF_STRUCTURE_MATCHERS`；`_classify()`→`_match_pdf_structure()`；新增 `_detect_bank_by_ocr_account()`（调用 `account_registry.match_by_account()`）；`_do_parse_pdf()` 门控改为 `PARSER_REGISTRY[bankCode]` 查表；删除 `try_receipt_first`、`detect_cmb_pdf_type()` |
| `bridge.py` | 删除 `_detect_bank_from_pdf()` 代理和 `detect_cmb_pdf_type()` 代理；`handle_detect_banks` 内联调用新路由函数 |
| `models.py` | 新增 `AccountEntry` 数据类 |

#### Phase 1

| 文件 | 改动 |
|------|------|
| `bridge.py` | 新增 `account_registry.list`/`add`/`update`/`delete` JSON-RPC 方法 |

#### Phase 2-3

| 文件 | 改动 |
|------|------|
| `models.py` | 新增 `SubjectRule`、`VoucherPreviewEntry`、`VoucherDraft` 数据类 |
| `bridge.py` | 新增 `voucher.*` JSON-RPC 方法 |
| `excel_builder.py` | `build_voucher()` 拆为 `preview()` + `export()` 两阶段；`_match_subject_code()` 接入三层引擎 |

### 4.3 前端新增

#### Phase 1

| 组件 | 职责 |
|------|------|
| `AccountSubjectManager.tsx` | 账号-科目管理 Modal（表格 CRUD，无搜索框） |
| `SubjectPickerModal.tsx` | 科目选择器弹窗（搜索/分类筛选），FR-3 凭证预览共享复用 |

#### Phase 3

| 组件 | 职责 |
|------|------|
| `VoucherPreviewPanel.tsx` | 凭证预览面板（主组件） |
| `VoucherDraftList.tsx` | 草稿列表（加载历史草稿） |

### 4.4 JSON-RPC 方法

#### Phase 0（FR-0 路由重构）

| 方法 | 用途 |
|------|------|
| `detect_banks` | 批量检测文件银行类型（重写为三级路由：Level 0 扩展名→Level 1 结构特征→Level 2 OCR 账号匹配），`DetectFileResult` 内部增加 `bankCode` 字段 |
| `detect_supported_banks` | 查询支持银行列表（从 `PARSER_REGISTRY` keys 动态返回） |
| `parse_pdf` | 解析入口不变，后端路由改为 `PARSER_REGISTRY[bankCode]` 查表 |

#### Phase 1（FR-1 账号-科目管理）

| 方法 | 用途 |
|------|------|
| `account_registry.list` | 列出所有账号-科目映射 |
| `account_registry.add` | 新增映射（校验 bankCode + subjectCode 必填，subjectCode 须存在于 subjects.json） |
| `account_registry.update` | 更新映射 |
| `account_registry.delete` | 删除映射 |
| `account_registry.match` | 给定账号，返回匹配的科目+银行 |

#### Phase 3（后续阶段）

| 方法 | 用途 |
|------|------|
| `voucher.preview` | 交易列表 → 凭证预览（含 matchStatus） |
| `voucher.save_draft` | 保存用户编辑后的凭证草稿 |
| `voucher.load_draft` | 加载草稿 |
| `voucher.list_drafts` | 列出所有草稿 |
| `voucher.delete_draft` | 删除草稿 |
| `voucher.export` | 确认导出，生成 Excel + 写入历史库 + 写入审计日志 |

### 4.5 共享类型

#### Phase 0 + Phase 1

```typescript
// 账号-科目映射
interface AccountEntry {
  id: string;
  matchType: 'suffix' | 'exact';
  pattern: string;
  bank: string;
  bankCode: string;
  subjectCode: string;
  subjectName: string;
}
```

#### Phase 2+（后续阶段）

```typescript
// 关键字规则（Layer 1）
interface SubjectRule {
  id: string;
  priority: number;
  match: {
    keywords: string[];
    counterparty_pattern?: string;
    amount_min?: number;
    amount_max?: number;
  };
  subject_code: string;
  subject_name: string;
  comment?: string;
}

// 凭证预览分录
interface VoucherPreviewEntry {
  entrySeq: number;
  voucherNo: number;
  date: string;
  summary: string;
  subjectCode: string;
  subjectName: string;
  debitAmount?: number;
  creditAmount?: number;
  direction: 'expense' | 'income';
  matchSource: 'rule' | 'history' | 'manual' | 'unmatched';
  originalSummary?: string;
  isManual: boolean;
}

// 凭证草稿
interface VoucherDraft {
  id: string;
  name: string;
  period: string;
  status: 'draft' | 'confirmed' | 'exported';
  createdAt: string;
  updatedAt: string;
  entries: VoucherPreviewEntry[];
}

// 导出日志
interface ExportLog {
  id: number;
  exportedAt: string;
  period: string;
  filePath: string;
  voucherCount: number;
  entryCount: number;
  transactionCount: number;
  sourceFiles: string[];
  matchStats: { rule: number; history: number; manual: number; unmatched: number };
}
```

---

## 五、分层实现计划

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **Phase 0** 解析器路由重构（FR-0） | `parser_router.py`：三级路由（Level 0 扩展名分流 + Level 1 嵌入式 PDF 结构特征匹配 → 试错链 + Level 2 OCR 账号匹配）、`PARSER_REGISTRY` 查表替换 `BANK_KEYWORDS` 门控、`PDF_STRUCTURE_MATCHERS` 替换 `_classify()`、所有检测路径统一返回 `(bankCode, docType)`；`account_registry.py`：`match_by_account()` 方法（纯 JSON 文件读写，无 SQLite）；`account_mapping.json`：直接采用 v2 格式；`models.py`：新增 `AccountEntry` 数据类；`bridge.py`：删除旧代理函数 | 无（优先执行） |
| **Phase 1** 账号-科目管理（FR-1） | `account_registry.py`：CRUD 方法（list/add/update/delete），JSON 文件同步写回，校验 `subjectCode` 存在于 `subjects.json`；`bridge.py`：新增 `account_registry.*` JSON-RPC 方法；`shared/types.ts`：`AccountEntry` 接口；`AccountSubjectManager.tsx`：Modal 表格 CRUD（无搜索框）；`SubjectPickerModal.tsx`：科目搜索/分类筛选弹窗（FR-3 凭证预览复用） | Phase 0 |
| **Phase 2** 三层匹配引擎（FR-2） | `subject_matcher.py`：L1 JSON 规则匹配（多字段联合条件）、L2 历史库 TF-IDF 余弦相似度匹配（依赖 SQLite `subject_history` 表）、L3 兜底；`excel_builder.py`：`_match_subject_code()` 接入新引擎 | Phase 1 |
| **Phase 3** 凭证预览 + SQLite（FR-3 + FR-4） | `db.py`：SQLite WAL 模式建表+迁移（`subject_history`/`voucher_draft`/`voucher_draft_entry`/`export_log`/`schema_version`）；`subject_history_repo.py`；`voucher_composer.py`：同类合并+草稿+导出；`VoucherPreviewPanel.tsx`；`VoucherDraftList.tsx`；所有 `voucher.*` JSON-RPC 方法（preview/save_draft/load_draft/list_drafts/delete_draft/export） | Phase 2 |
| **Phase 4** 管理 UI 完善 | xlsx 批量导入导出账号映射；剩余 UI 细节 | Phase 3 |

---

## 六、关键决策记录

| # | 决策 | 结论 | 原因 |
|---|------|------|------|
| D1 | 规则格式 | **JSON** | 统一现有配置体系，无需额外解析器 |
| D2 | 存储引擎 | **SQLite + JSON 混合** | 配置用 JSON（git 可追踪），运行时数据用 SQLite（事务、去重、查询） |
| D3 | 学习触发条件 | **仅用户手动修正时记录** | 简单可控，手动修正代表关键词匹配失败的高价值纠正样本 |
| D4 | 饱和机制 | **不需要** | 仅记录手动修正，数据量自然有限；UNIQUE 约束防重复即可 |
| D5 | ANTLR | **不引入** | 无形式语言解析需求；关键词语义匹配与语法解析无关 |
| D6 | 语义匹配算法 | **TF-IDF 余弦相似度，纯 Python 标准库** | 零依赖，性能满足历史库规模（~数百条记录） |
| D7 | 借贷方向 | **自动推导 + 手动翻转** | 支出=借对方贷银行，收入=借银行贷对方；特殊场景（转账/退款）预览中覆盖 |
| D8 | 同类合并 | **同对方科目+同方向→合并凭证，每笔原始交易保留独立分录行** | 减少凭证数量，保留追溯能力 |
| D9 | 银行检测方式 | **结构特征匹配 + OCR 账号匹配，替代关键字匹配** | 关键字不可靠（银行名不出现则失灵）。半结构化文件用列头/表标题匹配，扫描件用 OCR 首页提取账号反查 `account_registry`。前端 `detectBanks → parseFile` 流程不变 |
| D10 | 解析器路由 | **三级路由：扩展名→半结构结构特征→OCR 账号匹配。保留 `(bank, docType)` 返回值** | 路由仍然存在，parser 代码不改。改的是"怎么判断银行"——从不可靠的关键字改为可靠的结构/账号方法 |
| D11 | `account_mapping.json` 作用 | **双重用途：FR-0 OCR 账号匹配（返回 bankCode 用于 parser 路由） + FR-1 凭证银行科目填充（返回 subjectCode/Name）** | `bankCode` 作为 FR-0 OCR 匹配后 parser 路由的 key，`subjectCode` 作为 FR-1 凭证导出的银行科目 |
| D12 | `subjectCode` 必填 | **必填**，不允许为空，须存在于 `subjects.json` | 为空则凭证导出时银行科目缺失，与其让用户后续在预览中补填，不如入口约束 |
| D13 | `matchType` 范围 | **suffix + exact** | regex 有安全风险（ReDoS）且无实际场景；prefix 无需求 |
| D14 | `bankCode` 输入方式 | **下拉选择**，选项来自 `detect_supported_banks` | 新增银行需同步更新前端下拉 + 后端 PARSER_REGISTRY，由程序控制可解析银行范围 |
| D15 | v1→v2 迁移 | **不需要**，直接 v2 格式发布 | v0 版本无正式用户，v1 格式仅内部使用，无需兼容迁移逻辑 |
| D16 | `id` 生成策略 | **自动生成（时间戳）**，表单不展示 | 仅用于删除/编辑时定位，非用户关注字段 |
| D17 | 运行时写入策略 | **Phase 0/1 直接写 JSON 文件**，Phase 3 迁 SQLite | 数据量小（几条到几十条），JSON 足够；SQLite 引入留到草稿/凭证阶段统一 |
| D18 | `subjectName` 刷新策略 | **信任存储值**，不自动对齐 `subjects.json` | 用户可能手动修改科目名称，自动刷新会覆盖用户修改 |
| D19 | `bank` 字段 | **保留冗余存储**，选择 bankCode 后自动填充中文名 | 用户可手动修改，存储为字段保证展示一致性 |
| D20 | CRUD 搜索框 | **不需要** | 映射条目数量少（<100），搜索无实际价值 |
| D21 | `account_registry.match_by_account` | **Phase 0 只实现 match_by_account()（FR-0 Level 2 依赖），Phase 1 实现 CRUD** | FR-0 OCR 路由需先有匹配能力，CRUD 管理功能后续补充 |

---

---

## 七、不实现的内容

| 内容 | 说明 |
|------|------|
| 规则文件 DSL | 保持 JSON，不引入自定义语法格式 |
| 银行独立档案表 | 银行是科目的派生属性，不单独建表 |
| 自动学习（自确认记录） | 仅用户手动修正触发记录，避免引入置信度/饱和阈值等复杂机制 |
| ANTLR 解析器 | 项目无形式语言解析需求 |
| 在线 LLM 分类 | 纯桌面应用，离线优先 |