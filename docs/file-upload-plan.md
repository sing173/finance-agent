# 实施计划：文件上传与解析 — 单文件增强 + 批量模式

> 基于 `docs/file-upload-design.md` 50 条对齐决策
> 预计执行顺序：后端先行 → 前端组件 → 视图整合 → 测试验证

---

## 阶段 0：基础设施

### 0.1 创建 `public/batch_config.json`

```json
{ "maxBatchFiles": 5 }
```

**验收**：浏览器 fetch `batch_config.json` 返回 `{maxBatchFiles: 5}`。

---

## 阶段 1：后端 RPC（先做，前端依赖）

### 1.1 新建 `detect_banks` RPC

在 `bridge.py` 新增 `@register_method("detect_banks")`：

```python
def handle_detect_banks(params: dict) -> dict:
    """批量检测文件银行类型"""
    file_paths = params.get("file_paths", [])
    # 前端先过滤扩展名，后端只接收 .pdf 文件
    # 每个文件：读取前3页文字 → _classify(bank, doc_type) → {file_path, bank, doc_type, status}
    # 异常捕获：文件损坏/无法读取 → status='failed', bank='未知银行'
    ...
```

**改动文件**：`apps/python/src/finance_agent_backend/bridge.py`

**验收**：传入 `["a.pdf", "b.pdf"]`，返回 `[{"file_path": "a.pdf", "bank": "招商银行", "doc_type": "table", "status": "ok"}, ...]`。

### 1.2 新建 `detect_supported_banks` RPC

```python
def handle_detect_supported_banks(params: dict) -> dict:
    """返回当前支持的银行列表（从 BANK_KEYWORDS 自动生成）"""
    banks = list(BANK_KEYWORDS.keys())
    return {"success": True, "banks": banks}
```

**改动文件**：`bridge.py`

**验收**：返回 `{"success": true, "banks": ["招商银行", "工商银行", "广发银行", ...]}`。

---

## 阶段 2：前端组件（并行开发）

### 2.1 新建 `ManualOverrideModal.tsx`

共用手动覆盖模态框，单文件和批量模式共用。

**Props**：
- `open: boolean`
- `filePaths: string[]` — 单文件传 `[path]`，批量传 `[path1, path2, ...]`
- `initialBank?: string` — 预填银行（批量从第一个成功检测文件推导）
- `initialDocType?: string` — 预填表格类型
- `initialOcr?: boolean` — 预填 OCR
- `onConfirm: (bank, docType, forceOcr) => void` — 确认后回调
- `onCancel: () => void`

**内部组件**：
- 银行下拉：调用 `detect_supported_banks()` 动态填充
- 表格类型下拉：固定 `['流水', '回单']`
- 强制 OCR 复选框：仅当所有文件都是 `.pdf` 时显示

**动态文案**：
- 单文件：`无法自动识别，请手动选择`
- 批量（失败文件 > 1）：`有 {count} 个文件无法自动识别，请手动选择`
- 批量（失败文件 = 1）：`1 个文件无法自动识别，请手动选择`

**状态保留**：`[取消]` 和 `[×]` 关闭时不重置用户选择。

**文件**：`apps/renderer/src/components/ManualOverrideModal.tsx`

**验收**：
- 打开模态框，银行下拉显示所有支持银行
- 选择+确认 → onConfirm 回调收到 `(bank, docType, forceOcr)`
- 取消后重新打开 → 预填上次选择

### 2.2 新建 `ResultCard.tsx`

单文件结果展示卡片。

**Props**：
- `bank: string` — 检测到的银行（如"招商银行"）
- `docType: string` — 文档名（如"账务明细清单"）
- `isManual: boolean` — 是否手动选择（决定文案"检测到" vs "已选择"）
- `transactionCount: number`
- `statementDate?: string`
- `error?: string`
- `onRedetect: () => void`
- `onModifyConfig: () => void`
- `onReselectFile: () => void`

**文案**：
- 正常：`检测到：招商银行 · 账务明细清单` 或 `已选择：招商银行 · 银行流水`
- 失败：`解析失败：{error}`（绿色/红色状态指示）
- 按钮：`[重新检测]` `[修改配置]` `[重新选择文件]`

**文件**：`apps/renderer/src/components/ResultCard.tsx`

**验收**：传入 `isManual=true` → 显示"已选择"；传入 `error` → 显示错误+`[修改配置]`。

### 2.3 新建 `BatchFileSelector.tsx`

批量文件选择器。

**State**：
- `files: SelectedFile[]` — 已选文件列表
- `detected: Record<string, DetectResult | null>` — 检测结果

**结构**：
- `[+ 添加文件]` 按钮 → 打开多选文件选择器，`maxCount` 来自 `batch_config.json`
- 已选文件列表：每行 `[文件名（截断）] [检测状态] [× 删除]`
- `[清空列表]` 按钮（仅在 files.length > 0 时显示）
- `[识别文件]` 按钮（files.length > 0 时激活）→ 调用 `detect_banks`

**文件数量上限**：启动时 fetch `batch_config.json`，`addFiles` 时校验不超过 `maxBatchFiles`。

**文件**：`apps/renderer/src/components/BatchFileSelector.tsx`

**验收**：选 3 个文件 → 列表展示 3 行 → 点 `[识别文件]` → 列表状态更新 → 点 `[×]` 移除文件 → 列表减少。

### 2.4 新建 `BatchResultPanel.tsx`

批量结果面板（折叠面板 + 全部导出）。

**Props**：
- `files: BatchFileResult[]` — 批量解析结果
- `onRetry: (filePaths: string[]) => void` — 重试失败文件
- `onViewDetail: (filePath: string) => void` — 查看单文件详情
- `onExportExcel: () => void` — 全部导出 Excel
- `onExportVoucher: () => void` — 全部导出凭证

**结构**：
- 摘要卡片：`共 {totalFiles} 个文件 / {totalTxns} 笔交易 / 成功 {successCount} / 失败 {failedCount}`
- `[全部导出 Excel（成功 {successCount}）]` / `[全部导出凭证]`
- Antd Collapse：
  - 成功项：`▶ filename.pdf  ✓ 23笔  |  招商银行  |  账务明细清单  |  2026-03-15`
  - 失败项：红色收起样式 `▶ filename.pdf  ✗ 解析失败  [重试]`
  - 展开内容：TransactionTable + `[查看详情]`
- `[全部展开]` / `[全部收起]` 按钮

**文件**：`apps/renderer/src/components/BatchResultPanel.tsx`

**验收**：传入 3 个成功+1个失败 → 折叠面板展示 4 项 → 失败项红色 → 点 `[全部展开]` 全部展开 → 点 `[重试]` 触发 onRetry。

---

## 阶段 3：视图整合（改 App.tsx）

### 3.1 App.tsx 重构为双模式容器

**新增 State**：
```ts
mode: 'single' | 'batch' = 'single'
currentResult: SingleParseResult | null = null
batchResult: BatchResult | null = null
loading: boolean = false
```

**视图切换**：
```tsx
{mode === 'single' ? (
  <SingleFileView result={currentResult} loading={loading} ... />
) : (
  <BatchView result={batchResult} loading={loading} ... />
)}
```

**单文件模式布局**（保持现有结构）：
- 系统设置卡片（不变）
- `FileDropZone`（不变）
- 导出卡片（解析成功后显示，不变）
- 进度条（不变）
- 结果区域 → 改为 `ResultCard` + `TransactionTable` + `ManualOverrideModal`

**批量模式布局**（替换）：
- 系统设置卡片（不变）
- `BatchFileSelector`
- 进度条（批量解析时阻塞，显示当前文件）
- `BatchResultPanel`

**互斥规则**：进入批量模式 → `setCurrentResult(null)`；切回单文件 → `setBatchResult(null)`。

**文件**：`apps/renderer/src/App.tsx`

**验收**：切换 mode → 对应视图渲染；单文件解析成功 → currentResult 有值 → 显示结果卡片和交易列表；切到批量 → currentResult 清空 → batchResult 有值 → 显示批量面板。

### 3.2 提取 `SingleFileView` 组件

从 `App.tsx` 提取单文件视图逻辑到独立组件（可选，如果 `App.tsx` 仍保持简洁可跳过）。

**建议**：App.tsx 保留作为容器，SingleFileView 作为子组件提取。

---

## 阶段 4：IPC 桥接（Electron main）

### 4.1 新增 IPC 通道

在 `apps/electron/src/ipc.ts` 新增：

```ts
// 批量检测
ipcMain.handle('detect-banks', async (_, filePaths: string[]) => {
  return await pythonProcess.sendRequest('detect_banks', { file_paths: filePaths });
});

// 获取支持银行列表
ipcMain.handle('detect-supported-banks', async () => {
  return await pythonProcess.sendRequest('detect_supported_banks', {});
});
```

**文件**：`apps/electron/src/ipc.ts`

### 4.2 更新 preload.ts

```ts
detectBanks: (filePaths: string[]) => Promise<any>;
detectSupportedBanks: () => Promise<any>;
```

**文件**：`apps/electron/src/preload.ts`

### 4.3 更新 App.tsx 类型声明

在 `declare global` 里补充 `detectBanks` 和 `detectSupportedBanks`。

---

## 阶段 5：测试验证

### 5.1 后端集成测试（`apps/electron/tests/integration/`）

新建 `detect-banks.test.js`：
```js
describe('detect_banks', () => {
  it('detects CMB bank from PDF', async () => {
    const result = await electronAPI.detectBanks(['test/cmb_statement.pdf']);
    expect(result[0].bank).toBe('招商银行');
    expect(result[0].doc_type).toBe('table');
  });
  it('returns unknown for non-bank PDF', async () => {
    // ...
  });
});
```

新建 `detect-supported-banks.test.js`：
```js
describe('detect_supported_banks', () => {
  it('returns list of supported banks', async () => {
    const { banks } = await electronAPI.detectSupportedBanks();
    expect(banks).toContain('招商银行');
    expect(banks).toContain('工商银行');
  });
});
```

### 5.2 前端组件测试（手动）

- `ManualOverrideModal`：打开 → 选银行 → 确认 → onConfirm 被调用
- `BatchFileSelector`：添加 3 文件 → 检测 → 列表更新 → 移除 1 个
- `BatchResultPanel`：传入 3 成功 1 失败 → 折叠项 4 个 → 失败项红色

---

## 执行顺序总结

| 阶段 | 内容 | 预计工作量 | 依赖 |
|------|------|-----------|------|
| 0 | `batch_config.json` | 5 分钟 | 无 |
| 1.1 | `detect_banks` RPC | 30 分钟 | 无 |
| 1.2 | `detect_supported_banks` RPC | 5 分钟 | 无 |
| 2.1 | `ManualOverrideModal` | 45 分钟 | 1.1, 1.2 |
| 2.2 | `ResultCard` | 30 分钟 | 无 |
| 2.3 | `BatchFileSelector` | 60 分钟 | 1.1, batch_config |
| 2.4 | `BatchResultPanel` | 60 分钟 | 无 |
| 3 | App.tsx 重构 | 60 分钟 | 2.1-2.4 |
| 4.1-4.3 | IPC 桥接 | 30 分钟 | 1.1, 1.2 |
| 5 | 测试验证 | 60 分钟 | 全部 |

**总计约 6 小时**

---

## 关键风险

| 风险 | 缓解措施 |
|------|---------|
| `detect_banks` 在大文件上耗时 | 只读前 3 页，超时 5s 标为 unknown |
| 批量解析取消后状态清理 | cancel 时 clear all state，不保留中间结果 |
| fallback 面板在单/批量上下文切换时文案错误 | 用 `useContext` 或显式 `mode` prop 控制文案 |
| 文件选择器 `maxCount` 与 batch_config 不一致 | 统一从 batch_config 读取，选择器和校验层各读一次 |
