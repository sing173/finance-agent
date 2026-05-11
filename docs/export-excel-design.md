# 导出凭证 Excel 功能设计文档

> 分支：`features/export-excel`
> 目标文件：`apps/python/src/finance_agent_backend/tools/excel_builder.py`

---

## 一、背景与目标

当前 `ExcelBuilder.build()` 只能导出原始流水明细，不符合金蝶精斗云凭证批量导入的格式要求。

本功能需要在现有流水数据的基础上，结合用户提供的**科目列表**，按照金蝶精斗云的**凭证导入模板**格式生成可直接导入的 Excel 文件。

---

## 二、输入数据分析

### 2.1 流水数据（Transaction 模型）

```python
@dataclass
class Transaction:
    date: date             # 交易日期
    description: str       # 摘要/描述
    amount: Decimal        # 金额（正数）
    currency: str          # 币种，默认 CNY
    direction: str         # 'income' | 'expense'
    counterparty: str      # 对方户名
    reference_number: str  # 流水号
    notes: str             # 备注
```

### 2.2 科目表（`20260509163323_科目.xlsx`）

- Sheet 名：`科目`
- 共 **297 条**科目（不含表头）
- 列结构：

| 列 | 字段名 | 说明 |
|---|---|---|
| A | 编码 | 科目代码，如 `1000201` |
| B | 名称 | 科目名称，如 `工商银行（4363）` |
| C | 类别 | 流动资产、负债等 |
| D | 余额方向 | 借 / 贷 |
| E | 辅助核算类别 | 客户、供应商等（可空） |
| F | 是否现金科目 | 是 / 否 |
| G | 状态 | 启用 / 停用 |
| H | 是否平行科目 | 是 / 否 |

**关键科目举例：**
- `1000201` → `银行存款_工商银行（4363）`（现金科目、借方）
- `1000202` → `银行存款_广发银行（0146）`
- `10002` → `银行存款`（父科目）

**科目名称规则**：金蝶中科目名称用 `_` 拼接父子层级，导出时 `科目名称` 列需填写完整层级名称，格式为 `父名称_子名称`。

---

## 三、输出模板分析

### 3.1 凭证导入模板（`20260509160818_凭证导入模板.xlsx`）

- Sheet 名：`凭证列表#2026年第3期`（动态，实际使用时 Sheet 名需按期间命名）
- 共 **25 列**，列头说明：

| 列 | 字段名 | 说明 | 示例值 | 数字格式 |
|---|---|---|---|---|
| A | 日期 | 凭证日期 | `2026-03-31` | General |
| B | 凭证字 | 固定填 `记` | `记` | General |
| C | 凭证号 | 同一张凭证的所有分录共用同一个凭证号（从 1 开始递增） | `1` | General |
| D | 附件数 | 固定填 `0` | `0` | General |
| E | 分录序号 | 同一凭证内分录的序号，从 1 开始 | `1` | General |
| F | 摘要 | 对应流水 description | `支付电话费` | General |
| G | 科目代码 | 从科目表中匹配 | `5060201` | General |
| H | 科目名称 | 从科目表中匹配（全路径名称，父_子） | `管理费用_办公费` | General |
| I | 借方金额 | 借方时填金额，贷方时为空 | `799.0` | `#,##0.00` |
| J | 贷方金额 | 贷方时填金额，借方时为空 | `None` | `#,##0.00` |
| K | 客户 | 辅助核算-客户编码（可空） | `` | General |
| L | 供应商 | 辅助核算-供应商编码（可空） | `` | General |
| M | 职员 | 辅助核算-职员编码（可空） | `` | General |
| N | 项目 | 辅助核算-项目编码（可空） | `` | General |
| O | 部门 | 辅助核算-部门编码（可空） | `03` | General |
| P | 存货 | 辅助核算-存货编码（可空） | `` | General |
| Q | 自定义辅助核算类别 | 可空 | `` | General |
| R | 自定义辅助核算编码 | 可空 | `` | General |
| S | 自定义辅助核算类别1 | 可空 | `` | General |
| T | 自定义辅助核算编码1 | 可空 | `` | General |
| U | 数量 | 一般为空 | `None` | General |
| V | 单价 | 一般为空 | `None` | General |
| W | 原币金额 | 等于借方或贷方金额 | `799.0` | `##.00#####` |
| X | 币别 | 默认 `RMB` | `RMB` | General |
| Y | 汇率 | 默认 `1.0` | `1.0` | `##.00#####` |

### 3.2 关键约束

1. **一张凭证 = 多行分录**：同一凭证号的多行分录借贷必须平衡（借方合计 = 贷方合计）。
2. **凭证号递增**：每笔银行流水对应一张凭证，凭证号从 1 开始递增。
3. **分录序号**：同一凭证内从 1 开始递增。
4. **科目名称**：需拼接完整层级路径，如 `银行存款_工商银行（4363）`。
5. **金额格式**：借/贷方金额数字格式为 `#,##0.00`，原币金额为 `##.00#####`。

---

## 四、核心业务逻辑设计

### 4.1 科目匹配策略

每笔流水需要生成**至少两条分录**（借贷平衡），分录的科目需要由用户或系统指定。

**方式一（简单，MVP）**：外部传入科目映射配置
- 调用方提前指定「银行账户科目代码」（如 `1000201`），以及「对方科目代码」映射规则。
- `ExcelBuilder` 专注格式写入，不做科目推断。

**方式二（智能）**：根据流水描述自动推断科目
- 用关键字匹配（如含「手续费」→ 财务费用科目，含「工资」→ 应付职工薪酬等）。
- 可结合 AI 识别（后期扩展点）。

> **推荐 MVP 方案**：先实现方式一，科目映射由调用方传入，`ExcelBuilder` 只负责按模板写入。

### 4.2 分录生成规则（以支出为例）

**支出流水** → 生成两条分录：
```
分录1（借方）：对方科目 debit_amount=流水金额
分录2（贷方）：银行科目 credit_amount=流水金额
```

**收入流水** → 生成两条分录：
```
分录1（借方）：银行科目 debit_amount=流水金额
分录2（贷方）：对方科目 credit_amount=流水金额
```

### 4.3 数据流程图

```
银行流水 (List[Transaction])
        ↓
[科目匹配器] ← 科目列表 (subjects.xlsx)
        ↓ 生成 VoucherEntry 列表
[ExcelBuilder.build_voucher()]
        ↓ 写入 25 列标准格式
输出 凭证导入.xlsx
```

---

## 五、代码改造方案

### 5.1 新增数据模型

在 `models.py` 中新增：

```python
@dataclass
class Subject:
    """科目"""
    code: str               # 科目代码
    name: str               # 科目名称
    category: str           # 类别
    direction: str          # 余额方向：借/贷
    aux_category: str = ''  # 辅助核算类别
    is_cash: bool = False   # 是否现金科目
    enabled: bool = True    # 是否启用


@dataclass
class VoucherEntry:
    """凭证分录"""
    date: date
    voucher_word: str = '记'
    voucher_no: int = 1
    attachment_count: int = 0
    entry_seq: int = 1
    summary: str = ''
    subject_code: str = ''
    subject_name: str = ''
    debit_amount: Optional[Decimal] = None   # 借方金额
    credit_amount: Optional[Decimal] = None  # 贷方金额
    customer: str = ''
    supplier: str = ''
    employee: str = ''
    project: str = ''
    department: str = ''
    inventory: str = ''
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    original_amount: Optional[Decimal] = None
    currency: str = 'RMB'
    exchange_rate: Decimal = Decimal('1.0')
```

### 5.2 新增科目加载器

新文件 `tools/subject_loader.py`：

```python
class SubjectLoader:
    def load(self, xlsx_path: str) -> Dict[str, Subject]:
        """从科目 xlsx 加载科目字典，key 为科目编码"""
        ...
    
    def get_full_name(self, code: str, subjects: Dict[str, Subject]) -> str:
        """拼接完整科目层级名称，如 银行存款_工商银行（4363）"""
        ...
```

### 5.3 改造 ExcelBuilder

在 `excel_builder.py` 中新增方法：

```python
class ExcelBuilder:
    # 现有方法保留
    def build(self, transactions, output_path): ...
    
    # 新增凭证导出方法
    def build_voucher(
        self,
        transactions: List[Transaction],
        subjects: Dict[str, Subject],
        bank_subject_code: str,          # 银行科目代码，如 '1000201'
        default_expense_subject_code: str,   # 默认支出科目（无匹配时）
        default_income_subject_code: str,    # 默认收入科目（无匹配时）
        output_path: str,
        subject_mapper: Optional[Callable] = None,  # 自定义科目映射函数
        period: str = '',                # 期间名称，用于 Sheet 名，如 '2026年第3期'
    ) -> str:
        """按凭证模板格式导出 Excel"""
        ...
    
    def _transaction_to_entries(
        self, t: Transaction, voucher_no: int,
        bank_subject: Subject, counter_subject: Subject
    ) -> List[VoucherEntry]:
        """将一笔流水转换为两条凭证分录"""
        ...
    
    def _write_voucher_sheet(self, ws, entries: List[VoucherEntry]):
        """将凭证分录写入 worksheet"""
        ...
```

---

## 六、待确认问题

在开始编码前，以下问题需要明确：

| # | 问题 | 影响 |
|---|---|---|
| 1 | 每笔流水对应的**对方科目**如何确定？是固定一个、还是需要关键字映射表？ | 直接决定 `subject_mapper` 接口设计 |
| 2 | 同一天多笔相同对方科目的流水，是合并成一张凭证还是每笔单独一张凭证？ | 影响凭证号分配逻辑 |
| 3 | 凭证日期是否使用流水的实际日期，还是期末汇总日期？ | 影响 A 列的填写 |
| 4 | Sheet 名中的期间（如 `2026年第3期`）是否由调用方传入，还是自动根据日期推算？ | 影响接口参数 |
| 5 | `部门` 字段（O 列）如何填写？模板中部分有值（如 `03`），是否有固定规则？ | 影响 O 列写入 |
| 6 | 是否需要支持多银行账户（不同科目代码）在同一个导出文件中？ | 影响函数签名 |

---

## 七、开发计划

```
Phase 1: 基础结构
  ├── 新增 Subject、VoucherEntry 数据模型
  ├── 新增 SubjectLoader（从 xlsx 加载科目）
  └── 编写单元测试

Phase 2: 核心导出
  ├── ExcelBuilder.build_voucher() 主方法
  ├── _transaction_to_entries() 分录生成
  ├── _write_voucher_sheet() 写入逻辑（含数字格式）
  └── 完整集成测试（对照模板验证列格式）

Phase 3: 科目匹配（可选/扩展）
  ├── 关键字映射表（JSON 配置）
  └── AI 推断接口（后期）

Phase 4: 联调
  ├── 接入 bridge.py 暴露给 Electron 前端
  └── 实际凭证文件导入金蝶验证
```

---

## 八、参考文件

| 文件 | 路径 | 说明 |
|---|---|---|
| 科目表 | `D:\工作文档\中锦技术\20260509163323_科目.xlsx` | 297 条科目，编码+名称+余额方向 |
| 凭证模板 | `D:\工作文档\中锦技术\20260509160818_凭证导入模板.xlsx` | 25 列，含实际数据示例 |
| ExcelBuilder | `apps/python/src/finance_agent_backend/tools/excel_builder.py` | 现有实现 |
| 数据模型 | `apps/python/src/finance_agent_backend/models.py` | Transaction、ParseResult |
