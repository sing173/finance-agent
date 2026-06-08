# FinanceAssistant


## 产品概述

FinanceAssistant 是一款面向中小企业财务人员的桌面应用程序，旨在解决银行流水文件（PDF / CSV / Excel 等）到金蝶精斗云会计凭证的全链路自动化转换问题。（后续会扩展对接更多平台或自定义凭证模板）

传统工作流中，财务人员需要手动打开银行对账单 PDF，逐条录入摘要、金额、对方户名，再对照科目表手工匹配借贷方科目——一条交易约需 1–2 分钟，一个月 200 条交易意味着 3–6 小时的低价值重复劳动。FinanceAssistant 将这一流程压缩至分钟级：拖入文件 → 自动识别银行与格式 → 解析交易 → 三层智能匹配科目 → 预览确认 → 一键导出金蝶凭证 Excel。

## 📋 1. 产品概述

**FinanceAssistant** 是一款面向中小企业财务人员的桌面应用程序，旨在解决银行流水文件（PDF / CSV / Excel 等）到金蝶精斗云会计凭证的全链路自动化转换问题。**（后续会扩展对接更多平台或自定义凭证模板）**

传统工作流中，财务人员需要手动打开银行对账单 PDF，逐条录入摘要、金额、对方户名，再对照科目表手工匹配借贷方科目——一条交易约需 1–2 分钟，一个月 200 条交易意味着 3–6 小时的低价值重复劳动。FinanceAssistant 将这一流程压缩至分钟级：拖入文件 → 自动识别银行与格式 → 解析交易 → 三层智能匹配科目 → 预览确认 → 一键导出金蝶凭证 Excel。

### 产品边界

| 范畴 | 说明 |
| --- | --- |
| 已支持 | 银行流水 / 回单文件解析、科目自动匹配、凭证预览编辑、Excel 导出 |
| 已支持 | 批量文件处理（数量可配置，默认 5 文件）、草稿持久化、历史学习 |
| 规划中 | 更多银行支持、OCR 优化、自定义规则配置界面 |
| 暂不支持 | 通用银行解析兜底（未知银行强制拒绝）、在线同步、多用户协作 |

## 👥2. 目标用户

#### 🏢 中小企业财务人员

每月处理 1–10 份银行对账单，使用金蝶精斗云做账。不具备编程能力，核心诉求是减少手工录入。

#### 📊 代账会计

同时服务多个客户，每月需处理数十份不同银行的对账单。核心诉求是批量处理效率和准确性。

#### 🔧 个体经营者

自行管理公司账目，偶尔需要将银行流水转为凭证。核心诉求是零学习成本、开箱即用。

### 用户画像

| 维度 | 描述 |
| --- | --- |
| 角色 | 财务 / 会计 / 代账 |
| 技术能力 | 基础电脑操作，无编程经验 |
| 核心痛点 | 手工录入银行流水耗时、科目匹配易出错、金蝶导入格式复杂 |
| 使用频率 | 每月 1–4 次（月末 / 月中批量处理） |
| 环境 | Windows、Linux、Mac |

## 💎3. 核心价值主张

**一句话：将银行流水到金蝶凭证的端到端时间从数小时压缩到数分钟。**

#### ⚡ 智能识别

三级银行检测（结构特征匹配 → OCR 账号匹配 → 人工覆盖），支持工行/招行/广发共 11 种文件格式，无需手动指定银行类型。

#### 🎯 三层匹配

系统会分三步自动为每笔交易匹配合适的会计科目：**预设规则匹配**（如"物业费"自动归到物业管理费）→ **智能记忆**（记住你之前的手动修正，下次类似交易自动套用）→ **人工确认**（前两层都没命中的，在预览中高亮提示你手动选择）。用得越久，系统越懂你的业务，自动匹配率越高。

#### 📦 批量处理

一次添加多个文件，批量检测、批量解析、折叠展示，合并导出统一凭证。

#### ✅ 凭证预览

导出前完整预览每笔分录的借贷方科目，未匹配条目高亮提示，支持逐条或批量修正后再导出。

## ✨4. 功能概览

FinanceAssistant 的核心能力围绕**"文件解析 → 科目匹配 → 凭证生成 → 导出"**这条主线展开，分为四大功能模块：

#### 📂 文件解析

支持工行 / 招行 / 广发PDF、CSV、Excel 多格式

#### 🏦 账号科目管理

账号映射维护金蝶科目表导入

#### 🧾 凭证生成预览

三层智能匹配草稿保存与编辑

#### 📤 数据导出

流水明细 Excel金蝶凭证导入模板

### 4.1 文件解析

| 功能 | 说明 | 状态 |
| --- | --- | --- |
| 拖拽 / 点击选择文件 | 拖拽上传区域支持多文件拖入和系统文件浏览器选择 | 已上线 |
| 自动银行检测 | 三级路由：嵌入式文本结构匹配 → OCR 账号匹配 → 未知银行强制拦截 | 已上线 |
| 手动覆盖 | 检测失败时弹出手动配置面板，用户手动选择银行 + 文档类型 + 是否强制 OCR | 已上线 |
| 单文件模式 | 选择 1 个文件 → 检测 → 解析 → 结果卡片 → 交易明细表 | 已上线 |
| 批量模式 | 选择 >1 文件 → 批量检测 → 逐个解析（失败跳过） → 折叠面板展示 → 合并导出 | 已上线 |

### 4.2 账号与科目管理

| 功能 | 说明 | 状态 |
| --- | --- | --- |
| 账号-科目映射 CRUD | 账号科目管理功能支持增删改查银行账号到会计科目的精确/后缀匹配规则 | 已上线 |
| 科目表导入 | 从金蝶 xlsx 格式导入 297 条会计科目，构建完整科目字典 | 已上线 |
| 科目搜索选择器 | 虚拟滚动技术支持关键词搜索 + 类别筛选，297 条科目流畅展示 | 已上线 |

### 4.3 凭证生成与预览

| 功能 | 说明 | 状态 |
| --- | --- | --- |
| 凭证预览面板 | 按四元组（账号、对方科目、方向、对方账号）合并交易为凭证，逐条展示借贷分录 | 已上线 |
| 未匹配科目高亮 | L3 未命中条目红色标记，点击即开科目选择器手动指定 | 已上线 |
| 批量填充 | 下拉菜单提供预设科目（如"管理费用_物业管理费"），一键填充所有未匹配条目 | 已上线 |
| 草稿保存 | 凭证草稿持久化至 SQLite，支持保存 / 加载 / 删除，跨会话不丢失（后续扩展草稿管理功能） | 已上线 |
| 导出审计日志 | 每次导出记录 period、文件路径、匹配统计、来源文件，可追溯 | 已上线 |

### 4.4 数据导出

| 功能 | 说明 | 状态 |
| --- | --- | --- |
| 流水明细 Excel | 原始交易列表导出，含统计摘要（收入/支出笔数与总额） | 已开发 |
| 金蝶凭证 Excel | 25 列凭证导入模板，符合金蝶精斗云批量导入格式，含日期、凭证字、摘要、借贷方科目及金额 | 已上线 |

## 🔄5. 用户旅程

### 5.1 单文件解析流程

- 1 选择文件 拖拽或浏览 →
- 2 银行检测 三级路由识别 →
- 3 确认 / 覆盖 检测失败时手动选 →
- 4 解析交易 11 个解析器之一 →
- 5 查看明细 排序 / 筛选 / 分页 →
- 6 凭证生成 三层匹配 + 预览 →
- 7 导出 Excel 金蝶导入格式

### 5.2 批量处理流程

- 1 添加文件 可配置上限 →
- 2 批量检测 逐个识别银行 →
- 3 配置覆盖 失败文件手动设置 →
- 4 批量解析 逐个执行，失败跳过 →
- 5 折叠结果 按文件分组展示 →
- 6 合并导出 统一凭证 Excel

### 5.3 凭证预览与编辑流程

- 1 触发预览 单文件 / 批量"凭证生成" →
- 2 后端组合 凭证组合引擎按四元组合并交易 →
- 3 三层匹配 L1 规则 → L2 历史 → L3 未匹配 →
- 4 人工修正 点击未匹配条目选择科目 →
- 5 保存 / 导出 草稿持久化 → 导出 Excel

---

## 📖 完整文档

- **[产品需求文档 (PRD)](docs/PRD.html)** — 产品经理视角，涵盖产品概述、目标用户、核心价值、功能概览、用户旅程
- **[技术架构文档](docs/architecture.html)** — 涵盖进程架构、银行与格式支持、科目匹配系统、凭证系统、导出能力、技术栈、路线图、产品指标

---

## 🏗️ 技术架构

## 🏗️ 1. 技术架构

FinanceAssistant 采用 **三层进程架构**，通过 IPC / JSON-RPC 实现跨进程通信：

```svg
<svg viewBox="0 0 760 490" xmlns="http://www.w3.org/2000/svg"
     style="width:100%; max-width:760px; font-family: -apple-system,'PingFang SC','Microsoft YaHei',sans-serif;">

  
  <rect width="760" height="490" rx="12" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1"/>
  <text x="380" y="26" text-anchor="middle" font-size="14" font-weight="700" fill="#0f172a">FinanceAssistant 三层进程架构</text>

  
  <rect x="120" y="42" width="500" height="164" rx="10" fill="#fffbeb" stroke="#f59e0b" stroke-width="2"/>
  
  <rect x="120" y="34" width="92" height="18" rx="4" fill="#f59e0b"/>
  <text x="166" y="47" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">Electron Shell</text>

  
  <rect x="140" y="58" width="170" height="90" rx="7" fill="#dbeafe" stroke="#3b82f6" stroke-width="2"/>
  <text x="225" y="76" text-anchor="middle" font-size="12" font-weight="700" fill="#1e40af">Renderer</text>
  <text x="225" y="89" text-anchor="middle" font-size="9" fill="#1e3a8a">React + TypeScript</text>
  <line x1="150" y1="96" x2="300" y2="96" stroke="#93c5fd" stroke-width="1"/>
  <text x="225" y="108" text-anchor="middle" font-size="9" fill="#1e3a8a">文件选择 / 拖拽上传</text>
  <text x="225" y="120" text-anchor="middle" font-size="9" fill="#1e3a8a">交易表格展示</text>
  <text x="225" y="132" text-anchor="middle" font-size="9" fill="#1e3a8a">科目匹配交互</text>
  <text x="225" y="144" text-anchor="middle" font-size="9" fill="#1e3a8a">凭证预览编辑</text>

  
  <rect x="430" y="58" width="170" height="90" rx="7" fill="#fef3c7" stroke="#f59e0b" stroke-width="2"/>
  <text x="515" y="76" text-anchor="middle" font-size="12" font-weight="700" fill="#92400e">Electron Main</text>
  <text x="515" y="89" text-anchor="middle" font-size="9" fill="#78350f">Node.js + TypeScript</text>
  <line x1="440" y1="96" x2="590" y2="96" stroke="#fcd34d" stroke-width="1"/>
  <text x="515" y="108" text-anchor="middle" font-size="9" fill="#78350f">窗口生命周期管理</text>
  <text x="515" y="120" text-anchor="middle" font-size="9" fill="#78350f">Python 子进程管理</text>
  <text x="515" y="132" text-anchor="middle" font-size="9" fill="#78350f">IPC 路由转发</text>
  <text x="515" y="144" text-anchor="middle" font-size="9" fill="#78350f">文件系统权限</text>

  
  <text x="370" y="84" text-anchor="middle" font-size="9" font-weight="600" fill="#78716c">IPC</text>
  <text x="370" y="160" text-anchor="middle" font-size="9" fill="#78716c">contextBridge</text>

  
  <rect x="120" y="240" width="500" height="110" rx="7" fill="#d1fae5" stroke="#22c55e" stroke-width="2"/>
  <text x="370" y="260" text-anchor="middle" font-size="12" font-weight="700" fill="#065f46">Python Backend</text>
  <text x="370" y="273" text-anchor="middle" font-size="9" fill="#064e3b">bridge.py · JSON-RPC 2.0 · stdio</text>
  <line x1="138" y1="282" x2="602" y2="282" stroke="#6ee7b7" stroke-width="1"/>
  <text x="370" y="296" text-anchor="middle" font-size="9" fill="#064e3b">PDF / CSV / Excel 文件解析</text>
  <text x="370" y="310" text-anchor="middle" font-size="9" fill="#064e3b">OCR 文字识别（RapidOCR）</text>
  <text x="370" y="324" text-anchor="middle" font-size="9" fill="#064e3b">三层科目匹配（规则 / 智能记忆 / 人工兜底）</text>
  <text x="370" y="338" text-anchor="middle" font-size="9" fill="#064e3b">SQLite 数据持久化 · 金蝶凭证 Excel 导出</text>

  
  <rect x="120" y="400" width="245" height="58" rx="7" fill="#fce7f3" stroke="#ec4899" stroke-width="2"/>
  <text x="242" y="418" text-anchor="middle" font-size="11" font-weight="700" fill="#9d174d">📁 配置层（JSON）</text>
  <text x="242" y="433" text-anchor="middle" font-size="9" fill="#831843">科目字典</text>
  <text x="242" y="445" text-anchor="middle" font-size="9" fill="#831843">匹配规则配置表（37 条预设规则）</text>
  <text x="242" y="455" text-anchor="middle" font-size="9" fill="#831843">账号映射配置表</text>

  
  <rect x="375" y="400" width="245" height="58" rx="7" fill="#ede9fe" stroke="#8b5cf6" stroke-width="2"/>
  <text x="497" y="418" text-anchor="middle" font-size="11" font-weight="700" fill="#5b21b6">💾 SQLite 运行时层</text>
  <text x="497" y="433" text-anchor="middle" font-size="9" fill="#4c1d95">历史学习库（智能记忆）</text>
  <text x="497" y="445" text-anchor="middle" font-size="9" fill="#4c1d95">凭证草稿 · 分录明细 · 导出审计</text>

  
  <defs>
    <marker id="aB" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3Z" fill="#3b82f6"/></marker>
    <marker id="aA" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3Z" fill="#f59e0b"/></marker>
    <marker id="aG" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3Z" fill="#22c55e"/></marker>
    <marker id="aP" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3Z" fill="#ec4899"/></marker>
    <marker id="aV" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3Z" fill="#8b5cf6"/></marker>
  </defs>

  

  
  <line x1="310" y1="103" x2="430" y2="103" stroke="#3b82f6" stroke-width="2" marker-end="url(#aB)"/>

  
  <line x1="430" y1="116" x2="310" y2="116" stroke="#f59e0b" stroke-width="2" marker-end="url(#aA)"/>

  
  <line x1="515" y1="148" x2="515" y2="240" stroke="#22c55e" stroke-width="2.5" marker-end="url(#aG)"/>
  <text x="498" y="192" text-anchor="end" font-size="9" font-weight="600" fill="#065f46">stdin</text>

  
  <line x1="535" y1="240" x2="535" y2="148" stroke="#22c55e" stroke-width="2" stroke-dasharray="5,3" marker-end="url(#aG)"/>
  <text x="540" y="198" text-anchor="start" font-size="9" font-weight="600" fill="#065f46">stdout 返回</text>

  
  <line x1="242" y1="400" x2="242" y2="350" stroke="#ec4899" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#aP)"/>
  <text x="260" y="378" text-anchor="start" font-size="8" fill="#9d174d">启动加载</text>

  
  <line x1="497" y1="350" x2="497" y2="400" stroke="#8b5cf6" stroke-width="2" marker-end="url(#aV)"/>
  <text x="505" y="378" text-anchor="start" font-size="9" font-weight="600" fill="#5b21b6">读写</text>

</svg>
```

### 进程职责

#### Renderer（React）

用户界面层。负责文件选择、交易表格展示、科目匹配交互、凭证预览编辑。通过 `window.electronAPI` 与主进程通信。

#### Electron Main（Node.js）

桌面壳层。管理窗口生命周期、启动/监控 Python 子进程、声明式 IPC 路由、文件系统权限。Python 进程崩溃时自动重启。

#### Python Backend

核心业务层。JSON-RPC 2.0 服务器（stdio 传输），负责 PDF/CSV/Excel 解析、OCR 识别、三层科目匹配、SQLite 数据持久化、Excel 导出。

### 数据分层

**📁 配置层（JSON，git 可追踪，后续扩展为规则管理功能）**
科目配置表（科目字典）、匹配规则配置表（37 条预设匹配规则）、账号映射配置表（5 个银行账号映射）
→ 变更频率低，随安装包内置，运行时只读。

**💾 运行时层（SQLite）**
历史学习库（智能记忆数据）、凭证草稿表、草稿分录明细表、导出审计记录表
→ 用户操作产生，随使用增长。开发环境 `data.db`，生产环境 `%APPDATA%/FinanceAssistant/data.db`。

### 通信协议

前端与后端之间通过 **16 个 JSON-RPC 2.0 方法**交互，所有请求通过 Electron IPC 转发至 Python 子进程的 stdin，响应从 stdout 返回。关键接口：

| RPC 方法 | 用途 |
| --- | --- |
| parse_pdf | 统一解析入口（PDF / CSV / Excel） |
| detect_banks | 批量银行检测 |
| detect_supported_banks | 获取支持银行列表 |
| voucher.preview | 凭证预览（三层匹配） |
| voucher.save_draft | 保存凭证草稿 |
| voucher.load_draft | 加载凭证草稿 |
| voucher.list_drafts | 列出所有草稿 |
| voucher.export | 确认导出（Excel + 审计 + 学习） |
| account_registry.* | 账号-科目映射 CRUD |
| import_subjects | 导入金蝶科目表 |
| generate_excel | 导出流水明细 Excel |
| db.health | 数据库健康检查 |

## 🏦2. 银行与格式支持

| 银行 | 代码 | 格式 | 解析能力 | 实现方式 |
| --- | --- | --- | --- | --- |
| 工商银行 | ICBC | PDF 流水 | PDF 流水解析 | 图像网格线检测 + OCR 文字识别 |
| 工商银行 | ICBC | PDF 回单 | PDF 回单解析 | 网格定位 + 固定字段映射 |
| 工商银行 | ICBC | PDF 回单（备用） | PDF 回单解析（备用） | 标签定位 + 邻近字段提取 |
| 工商银行 | ICBC | CSV 流水 | CSV 流水解析 | GBK 编码读取，字段映射 |
| 招商银行 | CMB | PDF 流水（竖排） | PDF 流水解析 | 文本行序列解析 |
| 招商银行 | CMB | PDF 流水（表格） | PDF 流水解析 | 坐标分区 + 列映射 |
| 招商银行 | CMB | PDF 回单 | PDF 回单解析 | 标题识别 + 键值对提取 |
| 招商银行 | CMB | Excel 流水 | Excel 流水解析 | 表头扫描 + 列映射 |
| 广发银行 | GFB | PDF 流水 | PDF 流水解析 | 坐标分区 + 7 列映射 |

**⚠ 设计原则：未知银行强制拒绝**
系统不提供通用兜底解析器。当三级银行检测均无法识别文件来源时，系统拒绝解析并要求用户通过手动配置面板指定银行类型和文档格式。这一决策避免了静默解析错误导致的数据污染。

## 🎯3. 科目匹配系统

科目匹配是 FinanceAssistant 的核心竞争力。系统采用三级递进策略，从确定性规则到模糊历史学习，最终以人工兜底，实现准确率与覆盖率的平衡。

#### L1 · 规则匹配 规则引擎

从匹配规则配置表加载预设规则。每条规则包含多字段联合条件：**关键字**（摘要中包含）+ **对方户名模式**（可选）+ **方向**。规则按优先级排序，首条命中即停。

当前配置：31 条支出规则 + 6 条收入规则

#### L2 · 历史学习 学习引擎

用户手动修正的科目记录存入历史学习库。下次相似摘要通过 **智能相似度匹配**查找历史记录（相似度阈值 0.75）。

仅记录手动修正条目，自动匹配结果不写入，防止噪声数据污染。

#### L3 · 人工兜底 未匹配

前两层均未命中时标记为未匹配。凭证预览面板中未匹配条目**红色高亮**，用户点击选择科目后标记为已人工修正。

手动修正条目自动写入 L2 历史库，下次更准。

### 匹配数据流

```svg
<svg viewBox="0 0 660 380" xmlns="http://www.w3.org/2000/svg"
     style="width:100%; max-width:660px; font-family: -apple-system,'PingFang SC','Microsoft YaHei',sans-serif;">

  <rect width="660" height="380" rx="12" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1"/>
  <text x="330" y="24" text-anchor="middle" font-size="14" font-weight="700" fill="#0f172a">科目匹配数据流</text>

  
  <defs>
    <marker id="mB8" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3Z" fill="#3b82f6"/></marker>
    <marker id="mG8" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3Z" fill="#22c55e"/></marker>
    <marker id="mR8" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3Z" fill="#ef4444"/></marker>
    <marker id="mY8" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3Z" fill="#64748b"/></marker>
  </defs>

  

  
  <rect x="30" y="52" width="130" height="56" rx="8" fill="#f1f5f9" stroke="#64748b" stroke-width="1.5"/>
  <text x="95" y="72" text-anchor="middle" font-size="10" font-weight="700" fill="#334155">交易明细输入</text>
  <text x="95" y="86" text-anchor="middle" font-size="8" fill="#64748b">摘要 · 对方户名</text>

  
  <rect x="210" y="52" width="120" height="56" rx="8" fill="#dbeafe" stroke="#3b82f6" stroke-width="2"/>
  <text x="270" y="72" text-anchor="middle" font-size="11" font-weight="700" fill="#1e40af">L1 规则引擎</text>
  <line x1="220" y1="80" x2="320" y2="80" stroke="#93c5fd" stroke-width="1"/>
  <text x="270" y="94" text-anchor="middle" font-size="8" fill="#1e3a8a">关键字 + 对方户名</text>

  
  <polygon points="400,58 430,80 400,102 370,80" fill="#fff" stroke="#3b82f6" stroke-width="2"/>
  <text x="400" y="76" text-anchor="middle" font-size="10" font-weight="700" fill="#334155">命中?</text>
  <text x="400" y="92" text-anchor="middle" font-size="8" fill="#64748b">L1 规则</text>

  
  <rect x="510" y="52" width="120" height="56" rx="8" fill="#dcfce7" stroke="#22c55e" stroke-width="2.5"/>
  <text x="570" y="72" text-anchor="middle" font-size="11" font-weight="700" fill="#065f46">✅ 匹配成功</text>
  <text x="570" y="86" text-anchor="middle" font-size="8" fill="#064e3b">自动填充科目</text>
  <text x="570" y="98" text-anchor="middle" font-size="8" fill="#064e3b">规则匹配</text>

  

  
  <rect x="210" y="172" width="120" height="56" rx="8" fill="#dcfce7" stroke="#22c55e" stroke-width="2"/>
  <text x="270" y="192" text-anchor="middle" font-size="11" font-weight="700" fill="#065f46">L2 学习引擎</text>
  <line x1="220" y1="200" x2="320" y2="200" stroke="#6ee7b7" stroke-width="1"/>
  <text x="270" y="214" text-anchor="middle" font-size="8" fill="#064e3b">智能相似度匹配</text>

  
  <polygon points="400,178 430,200 400,222 370,200" fill="#fff" stroke="#22c55e" stroke-width="2"/>
  <text x="400" y="196" text-anchor="middle" font-size="10" font-weight="700" fill="#334155">命中?</text>
  <text x="400" y="212" text-anchor="middle" font-size="8" fill="#64748b">L2 历史</text>

  
  <rect x="510" y="172" width="120" height="56" rx="8" fill="#dcfce7" stroke="#22c55e" stroke-width="2.5"/>
  <text x="570" y="194" text-anchor="middle" font-size="11" font-weight="700" fill="#065f46">✅ 匹配成功</text>
  <text x="570" y="208" text-anchor="middle" font-size="8" fill="#064e3b">历史匹配</text>

  

  
  <rect x="210" y="292" width="120" height="56" rx="8" fill="#fee2e2" stroke="#ef4444" stroke-width="2"/>
  <text x="270" y="312" text-anchor="middle" font-size="11" font-weight="700" fill="#991b1b">L3 人工兜底</text>
  <line x1="220" y1="320" x2="320" y2="320" stroke="#fca5a5" stroke-width="1"/>
  <text x="270" y="334" text-anchor="middle" font-size="8" fill="#991b1b">预览面板手动选择</text>

  
  <rect x="510" y="292" width="120" height="56" rx="8" fill="#fee2e2" stroke="#ef4444" stroke-width="2.5"/>
  <text x="570" y="314" text-anchor="middle" font-size="11" font-weight="700" fill="#991b1b">⚠️ 需人工处理</text>
  <text x="570" y="328" text-anchor="middle" font-size="8" fill="#991b1b">红色高亮提示</text>

  

  
  <line x1="160" y1="80" x2="210" y2="80" stroke="#64748b" stroke-width="2" marker-end="url(#mY8)"/>
  <line x1="330" y1="80" x2="370" y2="80" stroke="#3b82f6" stroke-width="2" marker-end="url(#mB8)"/>
  <line x1="430" y1="80" x2="510" y2="80" stroke="#22c55e" stroke-width="2" marker-end="url(#mG8)"/>

  
  <line x1="330" y1="200" x2="370" y2="200" stroke="#22c55e" stroke-width="2" marker-end="url(#mG8)"/>
  <line x1="430" y1="200" x2="510" y2="200" stroke="#22c55e" stroke-width="2" marker-end="url(#mG8)"/>

  
  <line x1="330" y1="320" x2="510" y2="320" stroke="#ef4444" stroke-width="2" marker-end="url(#mR8)"/>

  
  <line x1="400" y1="102" x2="400" y2="130" stroke="#ef4444" stroke-width="2"/>
  <line x1="400" y1="130" x2="270" y2="130" stroke="#ef4444" stroke-width="2"/>
  <line x1="270" y1="130" x2="270" y2="172" stroke="#ef4444" stroke-width="2" marker-end="url(#mR8)"/>

  
  <line x1="400" y1="222" x2="400" y2="250" stroke="#ef4444" stroke-width="2"/>
  <line x1="400" y1="250" x2="270" y2="250" stroke="#ef4444" stroke-width="2"/>
  <line x1="270" y1="250" x2="270" y2="290" stroke="#ef4444" stroke-width="2" marker-end="url(#mR8)"/>

  
  
  <text x="434" y="78" text-anchor="start" font-size="9" font-weight="700" fill="#22c55e">是</text>
  
  <text x="406" y="106" text-anchor="start" font-size="9" font-weight="700" fill="#ef4444">否</text>
  
  <text x="434" y="198" text-anchor="start" font-size="9" font-weight="700" fill="#22c55e">是</text>
  
  <text x="406" y="226" text-anchor="start" font-size="9" font-weight="700" fill="#ef4444">否</text>

</svg>
```

### 训练数据策略

**质量优先原则**
导出功能仅将人工修正的分录写入历史学习库。自动匹配的结果不产生训练样本。这一设计确保智能记忆仅从经过人工验证的高质量数据中学习，避免错误匹配的级联传播。

### 缓存机制

- 历史匹配使用**内存缓存**，加速相似度计算

- 新数据写入时自动刷新缓存，确保数据即时生效

- OCR 文字识别引擎采用单例模式，避免每次解析重复加载模型

## 🧾4. 凭证系统

### 凭证组合逻辑

凭证组合引擎将解析后的交易流水转换为符合借贷记账规则的凭证分录。核心流程：

```svg
<svg viewBox="0 0 760 300" xmlns="http://www.w3.org/2000/svg"
     style="width:100%; max-width:760px; font-family: -apple-system,'PingFang SC','Microsoft YaHei',sans-serif;">
  <rect width="760" height="300" rx="12" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1"/>
  <text x="380" y="24" text-anchor="middle" font-size="13" font-weight="700" fill="#0f172a">凭证组合逻辑</text>

  
  <rect x="30" y="42" width="130" height="64" rx="8" fill="#f1f5f9" stroke="#64748b" stroke-width="1.5"/>
  <text x="95" y="62" text-anchor="middle" font-size="11" font-weight="700" fill="#334155">📥 交易流水</text>
  <text x="95" y="78" text-anchor="middle" font-size="9" fill="#64748b">解析后的交易列表</text>
  <text x="95" y="92" text-anchor="middle" font-size="9" fill="#64748b">日期/摘要/金额/对方户名</text>

  
  <line x1="160" y1="74" x2="195" y2="74" stroke="#1677ff" stroke-width="2" marker-end="url(#vArrB)"/>

  
  <rect x="200" y="42" width="150" height="64" rx="8" fill="#dbeafe" stroke="#3b82f6" stroke-width="2"/>
  <text x="275" y="62" text-anchor="middle" font-size="11" font-weight="700" fill="#1e40af">交易分组</text>
  <text x="275" y="78" text-anchor="middle" font-size="9" fill="#1e3a8a">按四元组分组</text>
  <text x="275" y="92" text-anchor="middle" font-size="9" fill="#1e3a8a">账号·对方科目·方向·对方账号</text>

  
  <line x1="350" y1="74" x2="385" y2="74" stroke="#1677ff" stroke-width="2" marker-end="url(#vArrB)"/>

  
  <rect x="390" y="42" width="150" height="64" rx="8" fill="#dcfce7" stroke="#22c55e" stroke-width="2"/>
  <text x="465" y="62" text-anchor="middle" font-size="11" font-weight="700" fill="#065f46">分录生成</text>
  <text x="465" y="78" text-anchor="middle" font-size="9" fill="#064e3b">支出：借对方 / 贷银行</text>
  <text x="465" y="92" text-anchor="middle" font-size="9" fill="#064e3b">收入：借银行 / 贷对方</text>

  
  <line x1="540" y1="74" x2="575" y2="74" stroke="#1677ff" stroke-width="2" marker-end="url(#vArrB)"/>

  
  <rect x="580" y="42" width="130" height="64" rx="8" fill="#fef3c7" stroke="#f59e0b" stroke-width="2"/>
  <text x="645" y="62" text-anchor="middle" font-size="11" font-weight="700" fill="#92400e">📤 凭证数据</text>
  <text x="645" y="78" text-anchor="middle" font-size="9" fill="#78350f">凭证号 · 日期</text>
  <text x="645" y="92" text-anchor="middle" font-size="9" fill="#78350f">借贷分录明细</text>

  
  <rect x="200" y="150" width="340" height="40" rx="6" fill="#fff" stroke="#e2e8f0" stroke-width="1"/>
  <text x="370" y="166" text-anchor="middle" font-size="10" font-weight="600" fill="#334155">借贷方向决定</text>
  <text x="370" y="182" text-anchor="middle" font-size="9" fill="#64748b">收入 → 借银行 / 贷对方  |  支出 → 借对方 / 贷银行</text>

  
  <line x1="275" y1="106" x2="275" y2="150" stroke="#64748b" stroke-width="1.5" marker-end="url(#vArrB)"/>
  <line x1="465" y1="106" x2="465" y2="150" stroke="#64748b" stroke-width="1.5" marker-end="url(#vArrB)"/>

  
  <rect x="200" y="220" width="340" height="40" rx="6" fill="#fef9c3" stroke="#f59e0b" stroke-width="1.5"/>
  <text x="370" y="236" text-anchor="middle" font-size="10" font-weight="600" fill="#92400e">三层科目匹配</text>
  <text x="370" y="252" text-anchor="middle" font-size="9" fill="#a16207">L1 规则 → L2 智能记忆 → L3 人工兜底</text>

  
  <line x1="370" y1="190" x2="370" y2="220" stroke="#f59e0b" stroke-width="1.5" marker-end="url(#vArrA)"/>

  
  <defs>
    <marker id="vArrB" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3Z" fill="#3b82f6"/></marker>
    <marker id="vArrA" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3Z" fill="#f59e0b"/></marker>
  </defs>
</svg>
```

### 凭证字段说明

| 字段 | 说明 |
| --- | --- |
| 凭证号 | 自动生成 |
| 交易日期 | 银行流水日期 |
| 借贷方向 | 收入 / 支出（决定借方和贷方） |
| 分录列表 | 每笔分录含科目、借方金额、贷方金额、摘要、对方户名 |
| 匹配来源 | 规则匹配 / 历史学习 / 人工修正 / 未匹配 / 自动 |
| 人工标记 | 是否经用户手动修正 |

### 草稿管理

- 凭证草稿存储在 SQLite 的凭证草稿表，每条草稿含唯一标识、名称、期间、状态（草稿 / 已导出）

- 分录存储在草稿分录明细表，含多个字段，与草稿通过外键关联（级联删除）

- 前端提供草稿列表功能，支持加载和删除

- 导出时自动将草稿状态标记为"已导出"

## 📤5. 导出能力

### 流水明细 Excel（`generate_excel`）

- 原始交易列表 + 统计摘要（收入/支出笔数与总额）

- 格式化表头（加粗、蓝色填充）、冻结首行、自适应列宽

### 金蝶凭证 Excel（`voucher.export`）

生成的 Excel 严格遵循**金蝶精斗云凭证批量导入模板**的 25 列格式：

| 列序 | 字段 | 说明 |
| --- | --- | --- |
| 1 | 凭证日期 | 交易日期 |
| 2 | 凭证字 | 记账凭证类型 |
| 3 | 凭证号 | 自动生成 |
| 4 | 分录序号 | 1 / 2（借 / 贷） |
| 5 | 摘要 | 交易描述 |
| 6-7 | 科目代码 / 名称 | 借贷方科目 |
| 8-9 | 借方金额 / 贷方金额 | 根据方向填充 |
| 10-14 | 客户 / 供应商 / 员工 / 项目 / 部门 | 辅助核算类别 |
| 15-25 | 数量、单价、原币、汇率等 | 扩展字段 |

### 导出审计

每次 `voucher.export` 执行以下操作：

- 生成金蝶凭证 Excel 文件

- 写入导出审计记录（期间、文件路径、凭证数、分录数、匹配统计、来源文件列表）

- 将人工修正的分录写入历史学习库，丰富智能记忆数据

- 将草稿状态标记为"已导出"

## 🛠️6. 技术栈

| 层 | 技术 | 版本 | 用途 |
| --- | --- | --- | --- |
| 桌面壳 | Electron | 32.x | 跨平台桌面应用框架 |
| 前端 UI | React + TypeScript + Vite | React 18 / TS 5.6 | 用户界面 |
| UI 组件库 | Ant Design 5 | 5.22 | 表格 / 表单 / 模态框 / 标签 |
| 虚拟列表 | react-window | 1.8 | 297 条科目虚拟滚动 |
| 前端测试 | Vitest + RTL | 4.1 / 16.3 | 单元测试 |
| 后端 | Python | 3.11+ | 核心业务逻辑 |
| PDF 解析 | PyMuPDF (fitz) | 1.24+ | PDF 文本 / 结构提取 |
| OCR | RapidOCR (ONNX Runtime) | 1.4+ | 扫描件文字识别 |
| 图像处理 | OpenCV | 4.8+ | 网格线检测、图像预处理 |
| Excel | openpyxl | 3.1+ | Excel 读写与格式化 |
| 数据库 | SQLite (stdlib) | — | WAL 模式，运行时数据 |
| NLP | scikit-learn (TF-IDF) | — | L2 历史学习向量化 |
| 打包 (Py) | PyInstaller | — | Python 单文件打包 |
| 打包 (El) | electron-builder | 24.x | NSIS 安装包 |
| 包管理 | Poetry / npm workspaces | — | Python / JS 依赖管理 |

## 🗺️7. 路线图

### v0.3.0 — 凭证系统上线 已完成

- ✅ 三层科目匹配引擎（L1 规则 + L2 智能记忆 + L3 人工兜底）

- ✅ 凭证预览与编辑面板

- ✅ 草稿管理（SQLite 持久化：保存 / 加载 / 删除）

- ✅ 金蝶凭证 Excel 导出（25 列精斗云导入模板）

- ✅ 批量文件处理（数量可配置，默认 5 文件，折叠面板展示）

- ✅ 账号-科目映射管理界面

- ✅ 三级银行检测路由（结构特征 → OCR 账号 → 人工覆盖）

### v0.4.0 — 智能化增强 规划中

- 🔲 更多银行支持（建设银行、农业银行、交通银行等）

- 🔲 L1 规则可视化配置界面（替代手写 JSON）

- 🔲 匹配准确率仪表盘（各层级命中率统计）

- 🔲 凭证模板自定义（不同金蝶版本的列映射）

### v0.5.0 — 内嵌Agent 远期

## 📊8. 产品指标

### 代码规模

~4,500 Python 代码行数
~3,500 TypeScript/React 代码行数
14解析器模块
16RPC 接口

### 功能覆盖率

| 维度 | 当前状态 |
| --- | --- |
| 银行覆盖 | 工行 / 招行 / 广发（3 家主流银行） |
| 文件格式 | PDF（嵌入式 + 扫描件）、CSV、Excel（.xlsx） |
| 科目数量 | 297 条（完整会计科目表） |
| 匹配层级 | L1 规则（37 条）→ L2 智能记忆 → L3 人工 |
| 批量处理 | 数量可配置（默认 5）/ 批次 |
| 导出格式 | 金蝶精斗云凭证导入模板（25 列） |
| 测试覆盖 | 前端 Vitest（组件 + Hook 单元测试）；Python pytest 框架已就绪 |

### 核心设计决策回顾

#### 🚫 未知银行强制拒绝

不提供通用兜底解析器。宁可让用户在覆盖面板手动选择，也不允许系统在不确定时静默解析，从源头避免数据污染。

#### 🧠 仅人工修正写入历史

L2 智能记忆模型的训练数据仅来自用户手动确认的分录。自动匹配结果不产生训练样本，确保模型质量。

#### ⚡ 延迟加载解析器

11 个解析器全部延迟导入，每次请求仅加载目标解析器，保持 bridge 启动速度。

#### 🔒 OCR 单例模式

OCR 文字识别引擎（~50MB 模型）采用单例模式，避免重复加载消耗内存。

#### 📜 虚拟滚动科目表

297 条科目通过 react-window FixedSizeList 渲染，仅产生 ~10 个 DOM 节点，保持列表流畅。

#### 🔀 三层路由检测

银行检测从关键字匹配升级为结构特征匹配（L1）→ OCR 账号匹配（L2）→ 人工覆盖（L3），准确率大幅提升。
