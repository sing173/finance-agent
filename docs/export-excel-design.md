# 导出凭证 Excel 功能设计文档

> 分支：`features/export-excel`
> 目标文件：`apps/python/src/finance_agent_backend/tools/excel_builder.py`

***

## 一、背景与目标

当前 `ExcelBuilder.build()` 只能导出原始流水明细，不符合金蝶精斗云凭证批量导入的格式要求。

本功能需要在现有流水数据的基础上，结合用户提供的**科目列表**，按照金蝶精斗云的**凭证导入模板**格式生成可直接导入的 Excel 文件。

***

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

| 列 | 字段名    | 说明                  |
| - | ------ | ------------------- |
| A | 编码     | 科目代码，如 `1000201`    |
| B | 名称     | 科目名称，如 `工商银行（4363）` |
| C | 类别     | 流动资产、负债等            |
| D | 余额方向   | 借 / 贷               |
| E | 辅助核算类别 | 客户、供应商等（可空）         |
| F | 是否现金科目 | 是 / 否               |
| G | 状态     | 启用 / 停用             |
| H | 是否平行科目 | 是 / 否               |

**关键科目举例：**

- `1000201` → `银行存款_工商银行（4363）`（现金科目、借方）
- `1000202` → `银行存款_广发银行（0146）`
- `10002` → `银行存款`（父科目）

**科目名称规则**：金蝶中科目名称用 `_` 拼接父子层级，导出时 `科目名称` 列需填写完整层级名称，格式为 `父名称_子名称`。

***

## 三、输出模板分析

### 3.1 凭证导入模板（`20260509160818_凭证导入模板.xlsx`）

- Sheet 名：`凭证列表#2026年第3期`（动态，实际使用时 Sheet 名需按期间命名）
- 共 **25 列**，列头说明：

| 列 | 字段名        | 说明                           | 示例值          | 数字格式         |
| - | ---------- | ---------------------------- | ------------ | ------------ |
| A | 日期         | 凭证日期                         | `2026-03-31` | General      |
| B | 凭证字        | 固定填 `记`                      | `记`          | General      |
| C | 凭证号        | 同一张凭证的所有分录共用同一个凭证号（从 1 开始递增） | `1`          | General      |
| D | 附件数        | 固定填 `0`                      | `0`          | General      |
| E | 分录序号       | 同一凭证内分录的序号，从 1 开始            | `1`          | General      |
| F | 摘要         | 对应流水 description             | `支付电话费`      | General      |
| G | 科目代码       | 从科目表中匹配                      | `5060201`    | General      |
| H | 科目名称       | 从科目表中匹配（全路径名称，父\_子）          | `管理费用_办公费`   | General      |
| I | 借方金额       | 借方时填金额，贷方时为空                 | `799.0`      | `#,##0.00`   |
| J | 贷方金额       | 贷方时填金额，借方时为空                 | `None`       | `#,##0.00`   |
| K | 客户         | 辅助核算-客户编码（可空）                | \`\`         | General      |
| L | 供应商        | 辅助核算-供应商编码（可空）               | \`\`         | General      |
| M | 职员         | 辅助核算-职员编码（可空）                | \`\`         | General      |
| N | 项目         | 辅助核算-项目编码（可空）                | \`\`         | General      |
| O | 部门         | 辅助核算-部门编码（可空）                | `03`         | General      |
| P | 存货         | 辅助核算-存货编码（可空）                | \`\`         | General      |
| Q | 自定义辅助核算类别  | 可空                           | \`\`         | General      |
| R | 自定义辅助核算编码  | 可空                           | \`\`         | General      |
| S | 自定义辅助核算类别1 | 可空                           | \`\`         | General      |
| T | 自定义辅助核算编码1 | 可空                           | \`\`         | General      |
| U | 数量         | 一般为空                         | `None`       | General      |
| V | 单价         | 一般为空                         | `None`       | General      |
| W | 原币金额       | 等于借方或贷方金额                    | `799.0`      | `##.00#####` |
| X | 币别         | 默认 `RMB`                     | `RMB`        | General      |
| Y | 汇率         | 默认 `1.0`                     | `1.0`        | `##.00#####` |

### 3.2 关键约束

1. **一张凭证 = 多行分录**：同一凭证号的多行分录借贷必须平衡（借方合计 = 贷方合计）。
2. **凭证号递增**：每笔银行流水对应一张凭证，凭证号从 1 开始递增。
3. **分录序号**：同一凭证内从 1 开始递增。
4. **科目名称**：需拼接完整层级路径，如 `银行存款_工商银行（4363）`。
5. **金额格式**：借/贷方金额数字格式为 `#,##0.00`，原币金额为 `##.00#####`。

***

## 四、核心业务逻辑设计

### 4.1 科目匹配策略：关键字映射

维护一份 JSON 配置文件（如 `subject_mapping.json`），结构如下：

```json
{
  "expense": [
    { "keywords": ["手续费", "服务费"], "subject_code": "6601" },
    { "keywords": ["工资", "薪酬"], "subject_code": "50501" },
    { "keywords": ["电话费", "通讯"], "subject_code": "5060201" },
    { "keywords": ["电费", "水费"], "subject_code": "5060204" }
  ],
  "income": [
    { "keywords": ["收款", "回款", "货款"], "subject_code": "10122" }
  ],
  "default_expense_subject_code": "5060201",
  "default_income_subject_code": "10122"
}
```

**匹配逻辑**：
1. 按 `direction` 选择 `expense` 或 `income` 规则列表
2. 遍历规则，检查流水 `description` 是否包含任意一个 `keyword`（不区分大小写）
3. 命中第一条规则即返回对应 `subject_code`
4. 无匹配时使用 `default_*_subject_code` 兜底

### 4.2 多银行账户支持

`bank_subject_code` 通过独立的账户映射配置传入，结构建议：

```json
{
  "accounts": [
    { "account_no_suffix": "4363", "subject_code": "1000201" },
    { "account_no_suffix": "0146", "subject_code": "1000202" },
    { "account_no_suffix": "0288", "subject_code": "1000203" }
  ],
  "default_bank_subject_code": "10002"
}
```

`Transaction` 模型的 `notes` 或 `reference_number` 字段可携带账号信息，用于反查银行科目代码。若无法反查则使用 `default_bank_subject_code`。

### 4.3 凭证日期规则

- 取该批次流水中**最大日期**所在月份的最后一天
- 示例：一批流水日期为 `2026-03-01 ~ 2026-03-31`，凭证日期统一填 `2026-03-31`
- 计算方式：`date(year, month, last_day_of_month)`

### 4.4 分录生成规则

**支出流水（direction=expense）** → 两条分录：
```
分录1（借方）：对方科目  debit_amount=流水金额
分录2（贷方）：银行科目  credit_amount=流水金额
```

**收入流水（direction=income）** → 两条分录：
```
分录1（借方）：银行科目  debit_amount=流水金额
分录2（贷方）：对方科目  credit_amount=流水金额
```

借贷合计必须相等（天然平衡，因为每张凭证只有两条分录）。

### 4.5 数据流程图

```
银行流水 (List[Transaction])
        ↓
[SubjectMapper]  ←  subject_mapping.json
        ↓ 每笔流水确定「对方科目代码」
[AccountMapper]  ←  account_mapping.json
        ↓ 每笔流水确定「银行科目代码」
[ExcelBuilder.build_voucher()]
        ↓ 计算期末日期，生成 VoucherEntry 列表（每笔 2 条）
[_write_voucher_sheet()]
        ↓ 写入 25 列，设置数字格式
输出 凭证导入.xlsx
```

***

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

    # 新增凭证导出方法（已确认签名）
    def build_voucher(
        self,
        transactions: List[Transaction],
        subjects: Dict[str, Subject],         # SubjectLoader 加载的科目字典
        subject_mapping: dict,                # 关键字→科目代码映射配置（JSON 解析后的 dict）
        account_mapping: dict,                # 账号后缀→银行科目代码映射配置
        output_path: str,
        period: str = '',                     # 期间名称，用于 Sheet 名，如 '2026年第3期'
    ) -> str:
        """按凭证模板格式导出 Excel
        
        - 凭证日期：取流水最大日期所在月份最后一天
        - 每笔流水生成一张凭证（两条分录，借贷平衡）
        - 凭证号从 1 开始递增
        - Sheet 名：f'凭证列表#{period}' 或 '凭证列表' 若 period 为空
        """
        ...

    def _get_period_end_date(self, transactions: List[Transaction]) -> date:
        """计算期末日期（最大日期所在月份的最后一天）"""
        ...

    def _match_subject_code(
        self, description: str, direction: str, subject_mapping: dict
    ) -> str:
        """根据流水描述和方向匹配对方科目代码"""
        ...

    def _match_bank_subject_code(
        self, transaction: Transaction, account_mapping: dict
    ) -> str:
        """根据流水信息匹配银行科目代码"""
        ...

    def _transaction_to_entries(
        self,
        t: Transaction,
        voucher_no: int,
        voucher_date: date,
        bank_subject: Subject,
        counter_subject: Subject,
    ) -> List[VoucherEntry]:
        """将一笔流水转换为两条凭证分录"""
        ...

    def _write_voucher_sheet(self, ws, entries: List[VoucherEntry]):
        """将凭证分录写入 worksheet（含列宽和数字格式）"""
        ...
```

### 5.4 新增配置文件

`apps/python/src/finance_agent_backend/config/subject_mapping.json`（示例）：

```json
{
  "expense": [
    { "keywords": ["手续费", "服务费"], "subject_code": "6601" },
    { "keywords": ["工资", "薪酬", "绩效"], "subject_code": "50501" },
    { "keywords": ["电话费", "通讯费"], "subject_code": "5060201" },
    { "keywords": ["电费", "水费", "物管费"], "subject_code": "5060204" },
    { "keywords": ["个人所得税", "印花税"], "subject_code": "2022112" }
  ],
  "income": [
    { "keywords": ["收款", "回款", "货款", "销售"], "subject_code": "10122" }
  ],
  "default_expense_subject_code": "5060201",
  "default_income_subject_code": "10122"
}
```

`apps/python/src/finance_agent_backend/config/account_mapping.json`（示例）：

```json
{
  "accounts": [
    { "account_no_suffix": "4363", "subject_code": "1000201" },
    { "account_no_suffix": "0146", "subject_code": "1000202" },
    { "account_no_suffix": "0288", "subject_code": "1000203" },
    { "account_no_suffix": "0118", "subject_code": "1000204" },
    { "account_no_suffix": "7931", "subject_code": "1000205" }
  ],
  "default_bank_subject_code": "10002"
}
```

***

## 六、业务决策（已确认）

> 2026-05-11 确认，开发可直接依照以下结论实现。

| # | 问题 | **决策** |
| - | --- | ------- |
| 1 | 对方科目如何确定？ | **关键字映射**：维护一份关键字→科目代码的 JSON 配置，匹配流水 `description`；无匹配时使用 `default_subject_code` 兜底 |
| 2 | 多笔流水是否合并凭证？ | **每笔单独一张凭证**，凭证号按流水顺序递增 |
| 3 | 凭证日期如何取？ | **期末汇总日期**（该批次所有流水所在月份的最后一天），例如全月流水统一填 `2026-03-31` |
| 4 | Sheet 名中的期间？ | 由调用方传入（精斗云导出文件默认命名，如 `2026年第3期`），`build_voucher()` 接收 `period` 参数用于拼接 Sheet 名 `凭证列表#{period}` |
| 5 | 部门字段（O 列） | **留空**，暂无部门数据 |
| 6 | 多银行账户支持？ | **支持**，`bank_subject_code` 改为接收 `List[str]` 或通过映射配置指定，每笔流水对应的银行科目由流水所属账户决定 |

***

## 七、开发计划

```
Phase 1: 基础结构
  ├── models.py 新增 Subject、VoucherEntry 数据模型
  ├── tools/subject_loader.py（加载科目 xlsx，拼接全路径名称）
  ├── config/subject_mapping.json（关键字→科目 初始配置）
  ├── config/account_mapping.json（账号后缀→银行科目 初始配置）
  └── 单元测试：SubjectLoader.load() + get_full_name()

Phase 2: 核心导出
  ├── ExcelBuilder.build_voucher() 主方法
  ├── _get_period_end_date()（期末日期计算）
  ├── _match_subject_code()（关键字映射匹配）
  ├── _match_bank_subject_code()（账户映射匹配）
  ├── _transaction_to_entries()（分录生成）
  ├── _write_voucher_sheet()（写入逻辑，含 #,##0.00 数字格式）
  └── 集成测试：对照模板 xlsx 逐列验证

Phase 3: 联调
  ├── 接入 bridge.py，暴露给 Electron 前端调用
  └── 实际导入金蝶精斗云验证格式

Phase 4: 扩展（后期）
  └── AI 自动推断科目（替代纯关键字映射）
```

***

## 八、参考文件

| 文件           | 路径                                                             | 说明                      |
| ------------ | -------------------------------------------------------------- | ----------------------- |
| 科目表          | `D:\工作文档\中锦技术\20260509163323_科目.xlsx`                          | 297 条科目，编码+名称+余额方向      |
| 凭证模板         | `D:\工作文档\中锦技术\20260509160818_凭证导入模板.xlsx`                      | 25 列，含实际数据示例            |
| ExcelBuilder | `apps/python/src/finance_agent_backend/tools/excel_builder.py` | 现有实现                    |
| 数据模型         | `apps/python/src/finance_agent_backend/models.py`              | Transaction、ParseResult |

