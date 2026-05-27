# 测试目录结构

本目录存放 Electron 主进程相关的测试脚本。

## 目录分类

### `integration/` 集成测试

测试 Electron 主进程与 Python 后端的完整 IPC 通信流程。

**`v030-e2e.test.js`** — v0.3.0 全功能集成测试（整合版，31 步 / 8 Phase）

运行方式：
```bash
cd apps/electron
node tests/integration/v030-e2e.test.js
```

覆盖范围：
| Phase | 内容 |
|-------|------|
| Phase 1 | db.health — SQLite 5 表结构验证 |
| Phase 2 | detect_banks — 空/不存在/多无效/CMB/GFB/混合/重复 |
| Phase 3 | parse_pdf — CMB PDF + ICBC CSV 自动路由 + parse_csv 直连 |
| Phase 4 | ICBC OCR — 回单网格解析 + 交易流水表格线解析 |
| Phase 5 | 全凭证链路 — preview → save/load/list/delete draft |
| Phase 6 | account_registry — CRUD + match |
| Phase 7 | generate_excel — 正常导出 |
| Phase 8 | 参数验证回归 — parse_pdf/generate_excel 缺参 + health/detect_supported_banks |

### `unit/` 单元测试

待补充：对独立模块（如 PythonProcessManager）的单元测试。

## Python Bridge 可用方法

当前 `bridge.py` 注册的 JSON-RPC 方法：

| 方法 | 说明 |
|------|------|
| `health` | 返回后端状态、版本、Python 版本 |
| `parse_pdf` | 解析 PDF 银行流水或 ICBC CSV 对账流水（自动识别文件类型） |
| `parse_csv` | 直接解析 ICBC CSV 对账流水 |
| `generate_excel` | 将交易列表导出为 Excel 文件 |
| `generate_voucher_excel` | 导出金蝶精斗云凭证模板 |
| `import_subjects` | 导入会计科目 |
| `get_subjects_info` | 查询内置科目表信息 |
| `detect_banks` | 批量检测 PDF 银行类型 |
| `detect_supported_banks` | 查询支持的银行列表 |
| `db.health` | 验证 SQLite 数据库状态 |
| `voucher.preview` | 交易列表 → 凭证预览（含科目匹配+同类合并） |
| `voucher.save_draft` | 保存凭证草稿到 SQLite |
| `voucher.load_draft` | 加载草稿（往返验证） |
| `voucher.list_drafts` | 列出所有草稿 |
| `voucher.delete_draft` | 删除草稿（CASCADE 删除关联分录） |
| `voucher.export` | 确认导出（Excel + 审计日志 + 历史写入） |
| `account_registry.*` | 账号映射 CRUD + 匹配 |

## 测试输出管理

- **输出目录**: `tests/output/`
- 测试生成的临时文件统一存放于此
- 测试结束自动清理临时文件

## 测试依赖

运行集成测试前确保：
1. Python 依赖已安装：`cd apps/python && pip install -e ".[dev]"`
2. Python bridge 可执行：配置 `PYTHON_CMD` 环境变量或使用 venv
3. 真实测试文件位于 `C:\Users\dell\Desktop\finance agent`