# 测试方法分类汇总

**总计：148 Python + 40 Renderer + 31 E2E = 219 个测试**

> ⏱ = 需要 OCR，默认跳过（`pytest -m ocr` 显式运行）

---

## 一、文件解析与银行检测（39 个）

### 银行检测

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_cmb_statement` | test_parser_router | CMB PDF 流水检测 |
| `test_gfb_statement` | test_parser_router | GFB PDF 流水检测 |
| `test_cmb_receipt` | test_parser_router | CMB PDF 回单检测 |
| `test_icbc_scanned` | test_parser_router | ICBC 扫描件 OCR 检测 ⏱ |
| `test_icbc_receipt` | test_parser_router | ICBC 回单 OCR 检测 ⏱ |
| `test_ocr_reuse_speedup` | test_parser_router | OCR 引擎复用性能 ⏱ |

### 路由分发

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_icbc_csv` | test_parser_router | ICBC CSV 路由 |
| `test_cmb_xlsx` | test_parser_router | CMB Excel 路由 |
| `test_cmb_statement` | test_parser_router | CMB PDF 路由 |
| `test_gfb_statement` | test_parser_router | GFB PDF 路由 |
| `test_cmb_receipt` | test_parser_router | CMB 回单路由 |
| `test_bank_override` | test_parser_router | 手动指定 bank 参数 |
| `test_bank_doctype_override` | test_parser_router | 手动指定 bank+docType ⏱ |
| `test_icbc_scanned` (Route) | test_parser_router | ICBC 扫描件路由 ⏱ |
| `test_icbc_receipt` (Route) | test_parser_router | ICBC 回单路由 ⏱ |
| `test_cmb_opening_balance_is_number` | test_parser_router | CMB 期初余额为数值 |

### ICBC 解析器细节

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_parse_result` | test_parser_router | ICBC 解析结果基本验证 ⏱ |
| `test_count` | test_parser_router | 恰好 20 笔交易 ⏱ |
| `test_first_transaction` | test_parser_router | 首笔交易日期/金额/方向 ⏱ |
| `test_last_transaction` | test_parser_router | 末笔交易日期的金额 ⏱ |
| `test_income_count` | test_parser_router | 5 笔收入 + 抽查第 3 笔 ⏱ |
| `test_statement_date` | test_parser_router | 对账日期 2026-03-30 ⏱ |
| `test_all_fields` | test_parser_router | 每笔有 date/amount/direction ⏱ |
| `test_balance_chain` | test_parser_router | notes 中余额解析 ⏱ |
| `test_refs_clean` | test_parser_router | reference_number 无管道符 ⏱ |
| `test_counterparty_no_bleed` | test_parser_router | 对方户名 ≥2 字符 ⏱ |

### Bridge RPC 解析

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_unknown_method` | test_parser_router | 未知方法返回 -32601 |
| `test_parse_pdf_missing_path` | test_parser_router | 缺 filePath 报错 |
| `test_parse_pdf_nonexistent` | test_parser_router | 不存在文件报错 |
| `test_generate_excel_missing_txns` | test_parser_router | 缺 transactions 报错 |
| `test_parse_pdf_icbc` | test_parser_router | JSON-RPC 解析 ICBC ⏱ |
| `test_generate_excel` | test_parser_router | JSON-RPC 导出 Excel ⏱ |

### 前端批量编排

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `adds files with pending status` | useBatchOrchestrator.test | 添加文件 → pending 状态 |
| `deduplicates files by filePath` | useBatchOrchestrator.test | 去重 |
| `removes a file by filePath` | useBatchOrchestrator.test | 移除文件 |
| `clears all files` | useBatchOrchestrator.test | 清空文件列表 |
| `detectDone is false` | useBatchOrchestrator.test | 初始检测状态 |

---

## 二、科目匹配（51 个）

### L1 规则匹配

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_keyword_hit` | test_subject_matcher | 关键词命中 |
| `test_keyword_any_hit` | test_subject_matcher | 关键词命中但 counterparty 不匹配 |
| `test_no_match_returns_unmatched` | test_subject_matcher | 无匹配返回 unmatched |
| `test_joint_rule_hit` | test_subject_matcher | keyword+counterparty 联合命中 |
| `test_joint_rule_counterparty_mismatch` | test_subject_matcher | counterparty 不匹配回退 |
| `test_joint_rule_service_tech` | test_subject_matcher | 技术服务费+中锦科技 |
| `test_long_keyword_over_short` | test_subject_matcher | 高优先级规则优先 |
| `test_short_keyword_when_no_long_match` | test_subject_matcher | 长关键词不匹配时短规则生效 |
| `test_income_keyword` | test_subject_matcher | 收入方向匹配 |
| `test_expense_rule_not_applied_to_income` | test_subject_matcher | 方向隔离 |
| `test_real_config_loads` | test_subject_matcher | 内置配置加载 |
| `test_real_config_no_match` | test_subject_matcher | 内置配置无匹配 |
| `test_real_config_service_fee_with_counterparty` | test_subject_matcher | 内置配置 counterparty 匹配 |

### RuleMatcher 类

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_match_hit` | test_subject_matcher | RuleMatcher 命中 |
| `test_match_miss` | test_subject_matcher | RuleMatcher 未命中 |
| `test_match_counterparty_filter` | test_subject_matcher | counterparty 过滤 |
| `test_match_from_file` | test_subject_matcher | 从文件加载规则 |
| `test_match_default_config_loads` | test_subject_matcher | 默认配置加载 |
| `test_match_priority_order` | test_subject_matcher | 优先级排序 |
| `test_match_direction_isolation` | test_subject_matcher | 方向隔离 |

### L2 TF-IDF 历史匹配

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_match_hit` (History) | test_subject_matcher | HistoryMatcher 命中 |
| `test_match_miss` (History) | test_subject_matcher | HistoryMatcher 未命中 |
| `test_match_none_repo` | test_subject_matcher | repo=None 安全返回 |
| `test_match_direction_filter` (History) | test_subject_matcher | 方向隔离 |
| `test_insert_and_find_similar_exact_match` | test_subject_history | 精确匹配 |
| `test_find_similar_no_match` | test_subject_history | 无关摘要无匹配 |
| `test_unique_constraint_dedup` | test_subject_history | UNIQUE 去重 |
| `test_direction_filter` | test_subject_history | 方向隔离 |
| `test_idf_exact_similar_still_matches` | test_subject_history | IDF 加权后仍匹配 |
| `test_compute_idf_rare_term_has_higher_weight` | test_subject_history | 稀有词 IDF 权重更高 |
| `test_repeated_calls_return_same_result` | test_subject_history | 缓存一致性 |
| `test_cache_invalidated_after_insert` | test_subject_history | insert 后缓存失效 |
| `test_default_threshold_is_075` | test_subject_history | 阈值常量 0.75 |
| `test_above_threshold_returns_match` | test_subject_history | 高相似度命中 |
| `test_low_threshold_allows_loose_match` | test_subject_history | 低阈值宽松匹配 |

### 三层链编排

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_l1_hit_skips_l2` | test_subject_matcher | L1 命中跳过 L2 |
| `test_l1_miss_l2_hit` | test_subject_matcher | L1 未命中 → L2 命中 |
| `test_both_miss_returns_unmatched` | test_subject_matcher | 全未命中 → unmatched |
| `test_swap_rule_matcher` | test_subject_matcher | 自定义 RuleMatcher 注入 |
| `test_no_history_matcher_falls_through` | test_subject_matcher | 无 HistoryMatcher 直通 |
| `test_l1_hit_skips_l2` (history) | test_subject_history | L1 命中跳过 L2 |
| `test_l1_miss_l2_hit` (history) | test_subject_history | L1→L2 回退 |
| `test_both_miss_returns_unmatched` (history) | test_subject_history | 全未命中 |

### L2 辅助核算

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_l2_aux_category_filled_by_subject_matcher` | test_issue46_l2_aux | L2 结果补充 aux_category |
| `test_l2_preserves_existing_aux_category` | test_issue46_l2_aux | 不覆盖已有 aux_category |

### 连接管理

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_insert_accepts_external_conn` | test_subject_history | 外部 conn 注入 |
| `test_find_similar_accepts_external_conn` | test_subject_history | 外部 conn 注入 |
| `test_batch_insert_reuses_connection` | test_subject_history | 50 条批量 < 0.5s |

---

## 三、凭证系统（47 个）

### 凭证组装

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_basic_compose` | test_voucher_composer | 2 支出+1 收入 → 2 张凭证 |
| `test_merge_same_counterparty` | test_voucher_composer | 同对方合并 → 3 条分录 |
| `test_direction_expense_debit_counterpart` | test_voucher_composer | 支出：借对方/贷银行 |
| `test_direction_income_credit_counterpart` | test_voucher_composer | 收入：借银行/贷对方 |
| `test_totals_balance` | test_voucher_composer | 借贷平衡 |
| `test_no_merge_different_counterparty_account` | test_voucher_composer | 不同对方账号不合并 |
| `test_merge_same_counterparty_account` | test_voucher_composer | 同对方账号合并 |
| `test_unmatched_transactions_not_merged` | test_voucher_composer | 未匹配各自独立 |
| `test_unmatched_same_account_different_descriptions` | test_voucher_composer | 同账号不同摘要独立 |

### PipelineEntry 类型化

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_pipeline_entry_has_all_fields` | test_issue48_pipeline_entry | 17 字段完整性 |
| `test_from_dict_rejects_unknown_fields` | test_issue48_pipeline_entry | 未知字段报错 |
| `test_from_dict_accepts_valid_fields` | test_issue48_pipeline_entry | 已知字段构造 |
| `test_from_db_row_dynamic_mapping` | test_issue48_pipeline_entry | sqlite3.Row 动态映射 |
| `test_db_schema_v4_has_rule_id` | test_issue48_pipeline_entry | schema v4 含 rule_id |
| `test_export_preserves_all_fields` | test_issue48_pipeline_entry | 全链路字段保留 |
| `test_excel_column_map_writes_aux_category` | test_issue48_pipeline_entry | COLUMN_MAP 写入 aux |

### 辅助核算 (Issue #46)

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_aux_category_present_in_match_result` | test_issue46_aux_category | 匹配结果含 aux |
| `test_aux_category_empty_for_non_50602` | test_issue46_aux_category | 非 50602 无 aux |
| `test_excel_department_column_has_aux_category` | test_issue46_excel_aux | Excel 第 15 列写入 |
| `test_exclude_keywords_blocks_match` | test_issue46_exclude_keywords | exclude 阻止匹配 |
| `test_exclude_keywords_allows_normal` | test_issue46_exclude_keywords | 无 exclude 正常匹配 |
| `test_entry_includes_aux_category` | test_issue46_voucher_aux | 分录含 aux |
| `test_bank_entry_does_not_have_aux_category` | test_issue46_voucher_aux | 银行分录无 aux |
| `test_aux_category_save_load_roundtrip` | test_issue46_db_pipeline | save→load 保留 aux |
| `test_aux_category_db_schema` | test_issue46_db_pipeline | schema v3 含 aux 列 |
| `test_bank_entry_uses_original_summary` | test_issue46_bank_summary | 银行分录用原始摘要 |
| `test_bank_entry_income_uses_original_summary` | test_issue46_bank_summary | 收入银行分录用原始摘要 |

### 规则回归 (Issue #46)

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_baoxiao_expense_match` | test_issue46_rules | 报销 → 管理费用 |
| `test_dianxin_expense_match` | test_issue46_rules | 电信费 → 电讯费 |
| `test_tuanxian_expense_match` | test_issue46_rules | 团险 → 福利费 |
| `test_zhengwei_expense_match` | test_issue46_rules | 郑炜 → 房租 |
| `test_baozhengjin_expense_match` | test_issue46_rules | 保证金 → 押金 |
| `test_tuiyaojin_income_match` | test_issue46_rules | 退押金 → 押金 |
| `test_tuibaozhengjin_income_match` | test_issue46_rules | 退保证金 → 押金 |
| `test_shouxufei_income_match` | test_issue46_rules | 手续费 → 手续费 |
| `test_dailixi_income_match` | test_issue46_rules | 贷款利息收入 |
| `test_existing_wuye_expense` | test_issue46_rules | 回归：物业费 |
| `test_existing_shouqian_expense` | test_issue46_rules | 回归：收款 |
| `test_existing_unmatched` | test_issue46_rules | 回归：未匹配 |

### 草稿 CRUD + 导出

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_load_existing_draft` | test_voucher_export | 加载已有草稿 |
| `test_load_nonexistent_draft` | test_voucher_export | 加载不存在草稿 |
| `test_list_drafts` | test_voucher_export | 列出草稿 |
| `test_list_drafts_empty` | test_voucher_export | 空列表 |
| `test_delete_draft` | test_voucher_export | CASCADE 删除 |
| `test_export_marks_draft_exported` | test_voucher_export | 导出标记 exported |
| `test_export_writes_audit_log` | test_voucher_export | 审计日志写入 |
| `test_export_writes_subject_history_for_manual` | test_voucher_export | 仅 manual 写入历史 |
| `test_voucher_full_pipeline` | test_voucher_pipeline | 全链路端到端 |

### RPC 层

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_preview_returns_vouchers` | test_voucher_composer | preview RPC 返回凭证 |
| `test_save_draft` (RPC) | test_voucher_composer | save_draft RPC |

---

## 四、账号映射（26 个）

### 加载与匹配

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_load_v2_format` | test_account_registry | v2 格式加载 |
| `test_match_by_account_exact` | test_account_registry | 精确匹配 |
| `test_match_by_account_exact_no_partial` | test_account_registry | 精确不部分匹配 |
| `test_match_by_account_suffix` | test_account_registry | 后缀匹配 |
| `test_match_by_account_suffix_exact_priority` | test_account_registry | exact > suffix 优先级 |
| `test_match_by_account_no_match` | test_account_registry | 无匹配返回 None |
| `test_match_masked_account` | test_account_registry | 带星号账号后缀匹配 |
| `test_match_empty_account` | test_account_registry | 空字符串返回 None |

### Repository CRUD

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_repository_load` | test_account_registry | JSON 加载 |
| `test_repository_load_empty` | test_account_registry | 空文件加载 |
| `test_repository_save` | test_account_registry | save 往返验证 |
| `test_save_persistence` | test_account_registry | JSON 结构含 defaultBankSubjectCode |
| `test_update_entry` | test_account_registry | update 修改 |
| `test_delete_entry` | test_account_registry | delete 删除 |
| `test_delete_entry_not_found` | test_account_registry | 删除不存在静默 |
| `test_update_entry_not_found` | test_account_registry | 更新不存在抛 ValueError |
| `test_add_entry` | test_account_registry | add 自动生成 id |
| `test_add_entry_subjectcode_validation` | test_account_registry | subjectCode 校验 |
| `test_add_entry_bankcode_required` | test_account_registry | bankCode 必填 |

### Bridge RPC

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_list` | test_account_registry | list RPC |
| `test_match_found` | test_account_registry | match 命中 |
| `test_match_not_found` | test_account_registry | match 未命中 |
| `test_add` | test_account_registry | add RPC |
| `test_add_validation_bankcode` | test_account_registry | add 校验 bankCode |
| `test_update` | test_account_registry | update RPC |
| `test_delete` | test_account_registry | delete RPC |

---

## 五、数据库基础设施（11 个）

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `test_creates_all_five_tables` | test_db | 建表 5 张 |
| `test_idempotent` | test_db | 幂等建表 |
| `test_wal_mode` | test_db | WAL 模式 |
| `test_schema_version_recorded` | test_db | schema_version 记录 |
| `test_insert_and_select` | test_db | 插入+读取 |
| `test_unique_constraint` | test_db | UNIQUE 约束 |
| `test_get_db_creates_connection` | test_db | 连接创建 |
| `test_get_db_singleton` | test_db | 单例模式 |
| `test_returns_all_tables` | test_db | db.health RPC |
| `test_health_auto_init_db` | test_db | health 自动建库 |
| `pathUtils (3 tests)` | pathUtils.test.ts | 路径提取（Win/Unix/bare） |

---

## 六、前端组件（25 个）

### VoucherDraftList

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `renders draft list` | VoucherDraftList.test | 渲染草稿列表 |
| `shows empty state` | VoucherDraftList.test | 空状态 |
| `calls onLoad` | VoucherDraftList.test | 加载回调 |
| `calls onDelete with confirmation` | VoucherDraftList.test | 删除+确认 |
| `shows status tag` | VoucherDraftList.test | 已导出标签 |

### AccountSubjectManager

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `renders card with title` | AccountSubjectManager.test | 渲染卡片+表格 |
| `opens add modal` | AccountSubjectManager.test | 新增弹窗 |
| `bankCode-select auto-fills bank` | AccountSubjectManager.test | bankCode 自动填充 |
| `submits add with correct params` | AccountSubjectManager.test | 提交新增 |
| `edit opens with pre-filled` | AccountSubjectManager.test | 编辑预填充 |
| `submits update` | AccountSubjectManager.test | 提交更新 |
| `deletes after popconfirm` | AccountSubjectManager.test | 删除+确认 |

### SubjectPickerModal

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `renders modal when visible` | SubjectPickerModal.test | 渲染弹窗 |
| `displays subjects list` | SubjectPickerModal.test | 科目列表 |
| `filters by search text` | SubjectPickerModal.test | 搜索过滤 |
| `renders category filter` | SubjectPickerModal.test | 分类筛选 |
| `calls onSelect` | SubjectPickerModal.test | 选择回调 |
| `calls onClose on cancel` | SubjectPickerModal.test | 关闭回调 |
| `shows empty state` | SubjectPickerModal.test | 无匹配科目 |
| `filters out disabled subjects` | SubjectPickerModal.test | 过滤已禁用 |

### VoucherPreviewPanel

| 测试方法 | 文件 | 说明 |
|---------|------|------|
| `renders voucher cards` | VoucherPreviewPanel.test | 渲染凭证卡片 |
| `shows unmatched warning` | VoucherPreviewPanel.test | 未匹配警告 |
| `shows click-to-select` | VoucherPreviewPanel.test | 点击选择科目 |
| `calls onSaveDraft` | VoucherPreviewPanel.test | 保存草稿回调 |
| `calls onVouchersChange` | VoucherPreviewPanel.test | 编辑回调 |
| `shows export popconfirm` | VoucherPreviewPanel.test | 导出确认 |

---

## 七、E2E 集成测试（31 步）

### Phase 1: db.health

| 步骤 | 说明 |
|------|------|
| 表结构验证 | SQLite 6 张表 |

### Phase 2: detect_banks

| 步骤 | 说明 |
|------|------|
| 空列表 → 空结果 | 空文件列表返回空数组 |
| 不存在文件 → status=failed | 不存在路径返回 failed |
| 多个不存在 → 全部 failed | 多个不存在全 failed |
| CMB PDF → status=ok | CMB 检测返回 bank/docType/bankCode |
| GFB PDF → status=ok | GFB 检测 |
| 混合列表 CMB + 不存在 + GFB | 2 ok / 1 failed |
| 重复文件 → 各自独立检测 | 重复路径独立处理 |

### Phase 3: parse_pdf + CSV

| 步骤 | 说明 |
|------|------|
| CMB PDF 解析 | detect 透传 bank/docType + 交易结构验证 |
| ICBC CSV parse_pdf 自动路由 | CSV 自动路由到 ICBC 解析器 |
| ICBC CSV parse_pdf 路由 | 二次验证路由一致性 |

### Phase 4: ICBC OCR

| 步骤 | 说明 |
|------|------|
| ICBC 回单 | OCR 解析 + 字段验证（预存在失败） |
| ICBC 流水 | OCR 解析 + counterparty 格式验证 |

### Phase 5: 全凭证链路

| 步骤 | 说明 |
|------|------|
| voucher.preview | 凭证预览 + 借贷平衡 + match_source 验证 |
| voucher.save_draft | 保存草稿 + draft_id |
| voucher.load_draft | 往返验证 name/count/status |
| voucher.list_drafts | 列表含 draft_id + entry_count |
| voucher.delete_draft | CASCADE 删除验证 |

### Phase 5b: L2 历史学习

| 步骤 | 说明 |
|------|------|
| L2-1: 首次预览 → unmatched | L1 未命中 → unmatched |
| L2-2: 手工修正 → 保存草稿 | is_manual=1 保存 |
| L2-3: 导出 → 写入 subject_history | 导出触发历史写入 |
| L2-4: 相似摘要 → L2 TF-IDF 命中 | 2-gram 相似度匹配 |

### Phase 6: account_registry

| 步骤 | 说明 |
|------|------|
| list 列出映射 | 结构验证（使用独立测试文件） |
| add 新增映射 | exact 匹配条目 |
| match 精确匹配 | 新增账号精确命中 |
| update 更新映射 | subjectName + subjectCode 更新 |
| delete 删除映射 | 删除后不再匹配 |

### Phase 7: generate_excel

| 步骤 | 说明 |
|------|------|
| 正常导出 | mock 交易 → Excel > 1KB |

### Phase 8: 参数验证回归

| 步骤 | 说明 |
|------|------|
| parse_pdf 缺少 filePath | 返回含 filePath 的错误 |
| generate_excel 缺少 transactions | 返回错误 |
| detect_supported_banks BankInfo 结构 | ≥3 银行 + code/name |

---

## 运行方式

```bash
# Python 单元测试（OCR 默认跳过）
cd apps/python && pytest

# Python OCR 测试（显式运行）
cd apps/python && pytest -m ocr

# Renderer 前端测试
cd apps/renderer && npm test

# E2E 集成测试
cd apps/electron && node tests/integration/v030-e2e.test.js
```
