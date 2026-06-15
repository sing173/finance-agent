# 测试目录结构

本目录存放 Electron 主进程相关的测试脚本。

## 目录分类

### `integration/` 集成测试

测试 Electron 主进程与 Python 后端的完整 IPC 通信流程。

**`v030-e2e.test.js`** — v0.3.0 全功能集成测试（32 步 / 8 Phase）

运行方式：
```bash
cd apps/electron
node tests/integration/v030-e2e.test.js
```

覆盖范围：
| Phase | 内容 | 容错 |
|-------|------|------|
| Phase 0 | 备份 account_mapping.json | 自动 |
| Phase 1 | db.health — SQLite 表结构验证 | — |
| Phase 2 | detect_banks — 空/不存在/多无效/CMB/GFB/混合/重复 | — |
| Phase 3 | parse_pdf — CMB PDF + ICBC CSV 自动路由 | — |
| Phase 4 | ICBC OCR — 回单网格解析 + 交易流水表格线解析 | 软失败 |
| Phase 5 | 全凭证链路 — preview → save/load/list/delete draft | — |
| Phase 5b | L2 历史学习 — unmatched → 手动修正 → 导出 → TF-IDF 命中 | — |
| Phase 6 | account_registry — CRUD + match（使用独立测试文件） | — |
| Phase 7 | generate_excel — 正常导出 | — |
| Phase 8 | 参数验证回归 — parse_pdf/generate_excel 缺参 + detect_supported_banks | — |

Phase 4 失败不阻断后续 Phase（OCR 已知问题）。cleanup 无条件恢复 account_mapping.json。

### `unit/` 单元测试

待补充：对独立模块（如 PythonProcessManager）的单元测试。

## Python Bridge 可用方法

当前 `bridge.py` 注册的 JSON-RPC 方法（业务逻辑委托给 `services/` 层）：

| 方法 | Service | 说明 |
|------|---------|------|
| `parse_pdf` | ParseService | 解析 PDF/CSV/Excel 银行流水 |
| `generate_excel` | ParseService | 将交易列表导出为 Excel |
| `detect_banks` | ParseService | 批量检测文件银行类型 |
| `detect_supported_banks` | ParseService | 查询支持的银行列表 |
| `import_subjects` | SubjectService | 导入会计科目 |
| `get_subjects_info` | SubjectService | 查询内置科目表信息 |
| `db.health` | — | 验证 SQLite 数据库状态 |
| `voucher.preview` | VoucherService | 交易列表 → 凭证预览 |
| `voucher.save_draft` | VoucherService | 保存凭证草稿 |
| `voucher.load_draft` | VoucherService | 加载草稿 |
| `voucher.list_drafts` | VoucherService | 列出所有草稿 |
| `voucher.delete_draft` | VoucherService | 删除草稿 |
| `voucher.export` | VoucherService | 确认导出（Excel + 审计日志 + 历史写入） |
| `account_registry.*` | AccountRegistryService | 账号映射 CRUD + 匹配 |

## 测试输出管理

- **输出目录**: `tests/integration/output/`
- 测试生成的临时文件统一存放于此
- cleanup 自动清理临时文件 + 恢复 account_mapping.json

## 测试依赖

运行集成测试前确保：
1. Python 依赖已安装：`cd apps/python && pip install -e ".[dev]"`
2. Python bridge 可执行：配置 `PYTHON_CMD` 环境变量或使用 venv
3. 测试 fixtures 位于 `apps/python/tests/fixtures/`
