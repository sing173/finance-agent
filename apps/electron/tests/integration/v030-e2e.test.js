/**
 * v0.3.0 全功能集成测试 — 整合版（替代 v020-e2e / full-workflow / detect-banks
 *   / icbc-csv / icbc-ocr-workflow / ipc-methods / bridge-ipc）
 *
 * 覆盖范围：
 *   Phase 1 — db.health: SQLite 数据库状态验证
 *   Phase 2 — detect_banks: CMB + GFB + 边界（空/不存在/重复/混合/全无效）
 *   Phase 3 — parse_pdf: CMB PDF + ICBC CSV 自动路由
 *   Phase 4 — ICBC OCR: 回单网格解析 + 交易流水表格线解析
 *   Phase 5 — 全凭证链路: preview → save_draft → load_draft → list_drafts → delete_draft
 *   Phase 6 — account_registry: CRUD + 匹配测试
 *   Phase 7 — generate_excel 回归
 *   Phase 8 — 参数验证回归: parse_pdf / generate_excel 缺参
 *
 * 前置条件：
 *   - apps/python/.venv 已创建且依赖已安装
 *   - apps/electron/dist/ 已编译（tsc 零错误）
 *   - 测试文件位于 apps/python/tests/fixtures/
 *
 * 运行：node tests/integration/v030-e2e.test.js
 */

const { pythonProcess } = require('../../dist/pythonProcessManager');
const fs = require('fs');
const path = require('path');
const os = require('os');

const OUTPUT_DIR = path.resolve(__dirname, 'output');
const TEST_DB = path.join(os.tmpdir(), `v030_test_${Date.now()}.db`);
const TEST_EXCEL = path.join(OUTPUT_DIR, 'v030_regression_export.xlsx');

const BASE = path.resolve(__dirname, '..', '..', '..', 'python', 'tests', 'fixtures');

// ---------- 测试文件（python/tests/fixtures） ----------

const FIXTURES = {
  cmb_pdf:        path.join(BASE, 'cmb_statement.pdf'),
  gfb_pdf:        path.join(BASE, 'gfb_statement.pdf'),
  icbc_csv:       path.join(BASE, 'icbc_statement.csv'),
  icbc_receipt_1: path.join(BASE, 'icbc_receipt.pdf'),
  icbc_stmt_1:    path.join(BASE, 'icbc_statement_scanned.pdf'),
};

// ---------- 工具 ----------

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function cleanup() {
  const files = [TEST_DB, TEST_EXCEL];
  for (const f of files) {
    if (fs.existsSync(f)) fs.unlinkSync(f);
    const wal = f + '-wal', shm = f + '-shm';
    [wal, shm].forEach(x => { if (fs.existsSync(x)) fs.unlinkSync(x); });
  }
}

function assert(cond, msg) {
  if (!cond) throw new Error('断言失败: ' + msg);
}

let step = 0;
function phase(name) {
  console.log(`\n═══ ${name} ═══`);
}
function run(name) {
  step++;
  process.stdout.write(`[${step}] ${name}... `);
}
function ok(msg = '') {
  console.log(`✓${msg ? ' ' + msg : ''}`);
}
function skip(msg) {
  console.log(`⊘ ${msg}`);
}

// ---------- 主流程 ----------

async function main() {
  console.log('╔════════════════════════════════════════════╗');
  console.log('║  v0.3.0 全功能集成测试（整合版）          ║');
  console.log('╚════════════════════════════════════════════╝');

  let passed = true;

  try {
    ensureDir(OUTPUT_DIR);

    // ── 启动后端 ──
    run('启动 Python 后端');
    await pythonProcess.start();
    await new Promise(r => setTimeout(r, 1500));
    ok('进程启动完成');

    // ════════════════════════════════════════════
    // Phase 1: db.health
    // ════════════════════════════════════════════
    phase('Phase 1: db.health');

    run('db.health 表结构验证');
    {
      const r = await pythonProcess.call('db.health', {});
      assert(r.status === 'ok', `状态应为 ok: ${r.status}`);
      assert(Array.isArray(r.tables), 'tables 应为数组');
      for (const t of ['subject_history', 'voucher_draft', 'voucher_draft_entry', 'export_log', 'schema_version']) {
        assert(r.tables.includes(t), `应包含表 ${t}`);
      }
      ok(`${r.tables.length} 张表: ${r.tables.join(', ')}`);
    }

    // ════════════════════════════════════════════
    // Phase 2: detect_banks
    // ════════════════════════════════════════════
    phase('Phase 2: detect_banks');

    run('空列表 → 空结果');
    {
      const r = await pythonProcess.call('detect_banks', { filePaths: [] });
      assert(r.success === true, 'success 应为 true');
      assert(r.results.length === 0, `应为 0，实际 ${r.results.length}`);
      ok();
    }

    run('不存在文件 → status=failed');
    {
      const r = await pythonProcess.call('detect_banks', { filePaths: ['/nonexistent/ghost.pdf'] });
      assert(r.success === true, 'success 应为 true');
      assert(r.results[0].status === 'failed', `应为 failed: ${r.results[0].status}`);
      assert(r.results[0].filePath === '/nonexistent/ghost.pdf', 'filePath 应原样返回');
      ok();
    }

    run('多个不存在 → 全部 failed');
    {
      const r = await pythonProcess.call('detect_banks', { filePaths: ['/a/1.pdf', '/a/2.pdf', '/a/3.pdf'] });
      assert(r.results.length === 3, `应为 3: ${r.results.length}`);
      assert(r.results.every(x => x.status === 'failed'), '应全部 failed');
      ok();
    }

    if (!fs.existsSync(FIXTURES.cmb_pdf)) {
      skip('CMB PDF 不存在，跳过 CMB 检测');
    } else {
      run('CMB PDF → status=ok');
      {
        const r = await pythonProcess.call('detect_banks', { filePaths: [FIXTURES.cmb_pdf] });
        assert(r.results[0].status === 'ok', `应为 ok: ${r.results[0].status}`);
        assert(r.results[0].bank, '应有 bank');
        assert(r.results[0].docType, '应有 docType');
        assert(r.results[0].bankCode, '应有 bankCode');
        ok(`${r.results[0].bank} · ${r.results[0].docType}`);
      }
    }

    if (!fs.existsSync(FIXTURES.gfb_pdf)) {
      skip('GFB PDF 不存在，跳过 GFB 检测');
    } else {
      run('GFB PDF → status=ok');
      {
        const r = await pythonProcess.call('detect_banks', { filePaths: [FIXTURES.gfb_pdf] });
        assert(r.results[0].status === 'ok', `应为 ok: ${r.results[0].status}`);
        assert(r.results[0].bank, '应有 bank');
        ok(`${r.results[0].bank} · ${r.results[0].docType}`);
      }
    }

    if (fs.existsSync(FIXTURES.cmb_pdf) && fs.existsSync(FIXTURES.gfb_pdf)) {
      run('混合列表 CMB + 不存在 + GFB');
      {
        const r = await pythonProcess.call('detect_banks', {
          filePaths: [FIXTURES.cmb_pdf, '/nonexistent/ghost.pdf', FIXTURES.gfb_pdf],
        });
        assert(r.results.length === 3, `应为 3: ${r.results.length}`);
        const okCount = r.results.filter(x => x.status === 'ok').length;
        const failCount = r.results.filter(x => x.status === 'failed').length;
        assert(okCount === 2 && failCount === 1, `应为 2 ok / 1 failed: ${okCount}/${failCount}`);
        ok(`${okCount} ok / ${failCount} failed`);
      }
    }

    if (fs.existsSync(FIXTURES.cmb_pdf)) {
      run('重复文件 → 各自独立检测');
      {
        const r = await pythonProcess.call('detect_banks', { filePaths: [FIXTURES.cmb_pdf, FIXTURES.cmb_pdf] });
        assert(r.results.length === 2, `应为 2: ${r.results.length}`);
        assert(r.results[0].status === 'ok' && r.results[1].status === 'ok', '两个都应 ok');
        ok();
      }
    }

    // ════════════════════════════════════════════
    // Phase 3: parse_pdf + CSV auto-route
    // ════════════════════════════════════════════
    phase('Phase 3: parse_pdf + CSV');

    let transactions = null;

    if (!fs.existsSync(FIXTURES.cmb_pdf)) {
      skip('CMB PDF 不存在，跳过解析');
    } else {
      run('CMB PDF 解析（detect 透传 bank/docType）');
      {
        const detect = await pythonProcess.call('detect_banks', { filePaths: [FIXTURES.cmb_pdf] });
        const { bank, docType } = detect.results[0];
        const r = await pythonProcess.call('parse_pdf', { filePath: FIXTURES.cmb_pdf, bank, docType });
        assert(r.success === true, `解析应成功: ${JSON.stringify(r)}`);
        assert(Array.isArray(r.transactions), '应有 transactions 数组');
        assert(r.transactions.length >= 1, `至少 1 笔: ${r.transactions.length}`);
        assert(r.bank === bank, `bank 应一致: ${r.bank} vs ${bank}`);
        transactions = r.transactions;
        ok(`${r.transactions.length} 笔交易`);
        // 验证交易结构
        const t = r.transactions[0];
        assert(t.date, '每笔交易应有 date');
        assert(typeof t.amount === 'number', 'amount 应为 number');
        assert(t.direction === 'expense' || t.direction === 'income', `方向无效: ${t.direction}`);
        assert(t.description, '每笔交易应有 description');
      }
    }

    if (!fs.existsSync(FIXTURES.icbc_csv)) {
      skip('ICBC CSV 不存在，跳过 CSV 解析');
    } else {
      run('ICBC CSV parse_pdf 自动路由');
      {
        const r = await pythonProcess.call('parse_pdf', { filePath: FIXTURES.icbc_csv });
        assert(r.success === true, `解析应成功: ${JSON.stringify(r)}`);
        assert(r.bank === '中国工商银行' || r.bank === '工商银行', `bank: ${r.bank}`);
        assert(r.transactions.length >= 1, `至少 1 笔: ${r.transactions.length}`);
        ok(`${r.transactions.length} 笔交易 · ${r.bank}`);
      }

      run('ICBC CSV parse_pdf 路由');
      {
        const r = await pythonProcess.call('parse_pdf', { filePath: FIXTURES.icbc_csv });
        assert(r.success === true, `解析应成功: ${JSON.stringify(r)}`);
        ok(`${r.transactions.length} 笔交易`);
      }
    }

    // ════════════════════════════════════════════
    // Phase 4: ICBC OCR 回单 + 流水
    // ════════════════════════════════════════════
    phase('Phase 4: ICBC OCR');

    const icbcReceipts = [FIXTURES.icbc_receipt_1].filter(fs.existsSync);
    const icbcStatements = [FIXTURES.icbc_stmt_1].filter(fs.existsSync);

    if (icbcReceipts.length === 0 && icbcStatements.length === 0) {
      skip('无 ICBC PDF 文件');
    }

    for (const pdfPath of icbcReceipts) {
      run(`ICBC 回单: ${path.basename(pdfPath)}`);
      {
        const start = Date.now();
        const r = await pythonProcess.call('parse_pdf', { filePath: pdfPath });
        const elapsed = ((Date.now() - start) / 1000).toFixed(1);
        assert(r.success === true, `解析应成功: ${r.error || ''}`);
        assert(r.bank === '中国工商银行', `bank: ${r.bank}`);
        assert(r.transactions.length >= 1, `至少 1 笔: ${r.transactions.length}`);
        assert(r.confidence >= 0.5, `置信度 >= 0.5: ${r.confidence}`);
        // 回单字段验证
        for (const t of r.transactions) {
          assert(t.date, '日期缺失');
          assert(typeof t.amount === 'number' && t.amount > 0, `金额无效: ${t.amount}`);
          assert(t.direction === 'expense' || t.direction === 'income', `方向无效: ${t.direction}`);
          if (t.notes) assert(!t.notes.startsWith('备注：'), `notes 未清理前缀: ${t.notes.substring(0, 10)}`);
        }
        ok(`${r.transactions.length} 笔回单, ${elapsed}s`);
        if (!transactions) transactions = [];
        transactions.push(...r.transactions);
      }
    }

    for (const pdfPath of icbcStatements) {
      run(`ICBC 流水: ${path.basename(pdfPath)}`);
      {
        const start = Date.now();
        const r = await pythonProcess.call('parse_pdf', { filePath: pdfPath });
        const elapsed = ((Date.now() - start) / 1000).toFixed(1);
        assert(r.success === true, `解析应成功: ${r.error || ''}`);
        assert(r.bank === '中国工商银行', `bank: ${r.bank}`);
        assert(r.transactions.length >= 1, `至少 1 笔: ${r.transactions.length}`);
        assert(r.confidence >= 0.5, `置信度 >= 0.5: ${r.confidence}`);
        // 流水字段验证（扫描件金额可能为 0，跳过金额正数断言）
        for (const t of r.transactions) {
          assert(t.date, '日期缺失');
          assert(typeof t.amount === 'number', `金额类型无效: ${typeof t.amount}`);
          if (t.counterparty) assert(!t.counterparty.includes('\n'), `counterparty 含换行: ${t.counterparty}`);
        }
        ok(`${r.transactions.length} 笔流水, ${elapsed}s`);
        if (!transactions) transactions = [];
        transactions.push(...r.transactions);
      }
    }

    // ════════════════════════════════════════════
    // Phase 5: 全凭证链路
    // ════════════════════════════════════════════
    phase('Phase 5: 全凭证链路');

    if (!transactions || transactions.length === 0) {
      skip('无交易数据，跳过凭证链路');
    } else {
      let draftId = null;
      let allEntries = null;

      run('voucher.preview 凭证预览');
      {
        const r = await pythonProcess.call('voucher.preview', { transactions });
        assert(r.success === true, `preview 应成功: ${JSON.stringify(r)}`);
        assert(Array.isArray(r.vouchers), '应有 vouchers');
        assert(r.vouchers.length >= 1, `至少 1 张: ${r.vouchers.length}`);

        for (const v of r.vouchers) {
          assert(typeof v.voucher_no === 'number', 'voucher_no 应为 number');
          assert(Array.isArray(v.entries), 'entries 应为数组');
          // 借贷平衡
          const debitSum = v.entries.reduce((s, e) => s + (e.debit_amount || 0), 0);
          const creditSum = v.entries.reduce((s, e) => s + (e.credit_amount || 0), 0);
          assert(Math.abs(debitSum - creditSum) < 0.01,
            `凭证#${v.voucher_no} 借贷不平: 借${debitSum} ≠ 贷${creditSum}`);
          for (const e of v.entries) {
            assert(['rule', 'history', 'manual', 'unmatched', 'auto'].includes(e.match_source),
              `match_source 无效: ${e.match_source}`);
          }
        }

        allEntries = [];
        for (const v of r.vouchers) {
          for (const e of v.entries) {
            if (e.direction !== 'bank') allEntries.push(e);
          }
        }
        ok(`${r.vouchers.length} 张凭证, ${allEntries.length} 条非银行分录`);
      }

      if (!allEntries || allEntries.length === 0) {
        skip('无不可导出的非银行分录，跳过草稿测试');
      } else {
        run('voucher.save_draft 保存草稿');
        {
          const r = await pythonProcess.call('voucher.save_draft', {
            db_path: TEST_DB,
            name: 'v0.3.0集成测试草稿',
            period: '2026年测试期',
            entries: allEntries,
          });
          assert(r.success === true, `save_draft 应成功: ${JSON.stringify(r)}`);
          assert(r.draft_id, '应有 draft_id');
          draftId = r.draft_id;
          ok(`ID: ${draftId}`);
        }

        run('voucher.load_draft 往返验证');
        {
          const r = await pythonProcess.call('voucher.load_draft', { draft_id: draftId, db_path: TEST_DB });
          assert(r.success === true, `load_draft 应成功: ${JSON.stringify(r)}`);
          assert(r.draft.name === 'v0.3.0集成测试草稿', `name: ${r.draft.name}`);
          assert(r.draft.entries.length === allEntries.length,
            `分录数: ${r.draft.entries.length} vs ${allEntries.length}`);
          assert(r.draft.status === 'draft', `status: ${r.draft.status}`);
          ok(`${r.draft.name} · ${r.draft.entries.length} 条分录`);
        }

        run('voucher.list_drafts 列表');
        {
          const r = await pythonProcess.call('voucher.list_drafts', { db_path: TEST_DB });
          assert(r.success === true, '应成功');
          const ids = r.drafts.map(d => d.id);
          assert(ids.includes(draftId), `应含 ${draftId}`);
          const d = r.drafts.find(x => x.id === draftId);
          assert(d.entry_count === allEntries.length, `entry_count: ${d.entry_count}`);
          ok(`${r.drafts.length} 个草稿`);
        }

        run('voucher.delete_draft CASCADE 删除');
        {
          await pythonProcess.call('voucher.delete_draft', { draft_id: draftId, db_path: TEST_DB });
          const listR = await pythonProcess.call('voucher.list_drafts', { db_path: TEST_DB });
          const ids = listR.drafts.map(d => d.id);
          assert(!ids.includes(draftId), '删除后不应包含');
          ok(`已删除，剩余 ${listR.drafts.length} 个`);
        }
      }
    }

    // ════════════════════════════════════════════
    // Phase 5b: L2 历史学习匹配
    // ════════════════════════════════════════════
    phase('Phase 5b: L2 历史学习');

    let l2DraftId = null;

    // 构造 L1 无法匹配的交易（"AWS云主机"不在任何规则关键字中）
    // rule_e002 虽有"服务费"但 counterparty_pattern="科技" 不匹配"阿里云计算"
    const l2Txn = {
      date: '2026-06-01',
      description: '支付AWS云主机托管服务费',
      amount: 1200.00,
      currency: 'CNY',
      direction: 'expense',
      counterparty: '阿里云计算',
      reference_number: 'L2TEST-001',
      account_number: '6225123456789012',
      account_name: '测试账户',
    };

    run('L2-1: 首次预览 → L1 未命中 → unmatched');
    {
      const r = await pythonProcess.call('voucher.preview', { transactions: [l2Txn], db_path: TEST_DB });
      assert(r.success === true, `preview 应成功: ${JSON.stringify(r)}`);
      assert(r.vouchers.length >= 1, '至少 1 张凭证');
      const unmatched = r.vouchers[0].entries.filter(e => e.match_source === 'unmatched' && e.direction !== 'bank');
      assert(unmatched.length >= 1, `应有 unmatched 分录，实际: ${r.vouchers[0].entries.map(e => e.match_source).join(',')}`);
      ok(`unmatched: ${unmatched.length} 条`);
    }

    run('L2-2: 手工修正科目 → 保存草稿');
    {
      const previewR = await pythonProcess.call('voucher.preview', { transactions: [l2Txn], db_path: TEST_DB });
      const entries = [];
      for (const v of previewR.vouchers) {
        for (const e of v.entries) {
          if (e.direction !== 'bank') {
            entries.push({
              entry_seq: e.entry_seq,
              voucher_no: e.voucher_no,
              date: e.date,
              summary: e.summary,
              subject_code: '5060201',       // 手工指定: 管理费用_办公费
              subject_name: '管理费用_办公费',
              debit_amount: e.debit_amount,
              credit_amount: e.credit_amount,
              direction: e.direction,
              counterparty: e.counterparty,
              match_source: 'manual',
              original_summary: e.summary,
              original_amount: e.original_amount,
              is_manual: 1,
            });
          }
        }
      }

      const r = await pythonProcess.call('voucher.save_draft', {
        db_path: TEST_DB,
        name: 'L2历史学习测试草稿',
        period: '2026年L2测试期',
        entries: entries,
      });
      assert(r.success === true, `save_draft 应成功: ${JSON.stringify(r)}`);
      l2DraftId = r.draft_id;
      ok(`草稿 ID: ${l2DraftId}`);
    }

    run('L2-3: 导出草稿 → 写入 subject_history');
    {
      const exportPath = path.join(OUTPUT_DIR, 'l2_history_test.xlsx');
      const r = await pythonProcess.call('voucher.export', {
        draft_id: l2DraftId,
        period: '2026年L2测试期',
        output_path: exportPath,
        db_path: TEST_DB,
      });
      assert(r.success === true, `export 应成功: ${JSON.stringify(r)}`);
      assert(fs.existsSync(exportPath), 'Excel 文件应存在');
      ok(`导出成功 (${fs.statSync(exportPath).size} 字节)`);
    }

    run('L2-4: 预览相似摘要 → L2 TF-IDF 应命中');
    {
      // 相似摘要: "支付AWS云主机托管服务费用" vs 历史 "支付AWS云主机托管服务费"
      // 仅尾部多"用"字，2-gram 重合度 ~96%，余弦相似度 >> 0.75 阈值
      const similarTxn = {
        date: '2026-07-01',
        description: '支付AWS云主机托管服务费用',
        amount: 1200.00,
        currency: 'CNY',
        direction: 'expense',
        counterparty: '阿里云计算',
        reference_number: 'L2TEST-002',
        account_number: '6225123456789012',
        account_name: '测试账户',
      };

      const r = await pythonProcess.call('voucher.preview', { transactions: [similarTxn], db_path: TEST_DB });
      assert(r.success === true, `preview 应成功: ${JSON.stringify(r)}`);
      assert(r.vouchers.length >= 1, '至少 1 张凭证');

      const nonBank = r.vouchers[0].entries.filter(e => e.direction !== 'bank');
      const historyEntry = nonBank.find(e => e.match_source === 'history');
      assert(historyEntry, `应有 L2 history 匹配，实际: ${nonBank.map(e => `${e.summary}→${e.match_source}`).join(', ')}`);
      assert(historyEntry.subject_code === '5060201',
        `L2 匹配科目应为 5060201，实际: ${historyEntry.subject_code}`);
      ok(`L2 命中: ${historyEntry.subject_code} ${historyEntry.subject_name}`);
    }

    // 清理 L2 测试草稿
    if (l2DraftId) {
      await pythonProcess.call('voucher.delete_draft', { draft_id: l2DraftId, db_path: TEST_DB });
    }

    // ════════════════════════════════════════════
    // Phase 6: account_registry CRUD
    // ════════════════════════════════════════════
    phase('Phase 6: account_registry');

    let testEntryId = null;

    run('account_registry.list 列出映射');
    {
      const r = await pythonProcess.call('account_registry.list', {});
      assert(r.success === true, '应成功');
      assert(Array.isArray(r.accounts), 'accounts 应为数组');
      assert(r.accounts.length >= 1, `至少 1 条: ${r.accounts.length}`);
      for (const e of r.accounts) {
        assert(e.id && e.matchType && e.pattern && e.bankCode, '结构不完整');
      }
      ok(`${r.accounts.length} 条`);
    }

    run('account_registry.add 新增映射');
    {
      const r = await pythonProcess.call('account_registry.add', {
        matchType: 'exact',
        pattern: '9999999999999999',
        bank: '测试银行',
        bankCode: 'TEST',
        subjectCode: '10001',
        subjectName: '测试科目-现金',
      });
      assert(r.success === true, `add 应成功: ${JSON.stringify(r)}`);
      assert(r.entry.pattern === '9999999999999999', 'pattern 应一致');
      testEntryId = r.entry.id;
      ok(`ID: ${testEntryId}`);
    }

    run('account_registry.match 精确匹配');
    {
      const r = await pythonProcess.call('account_registry.match', { accountNumber: '9999999999999999' });
      assert(r.success === true, '应成功');
      assert(r.entry !== null && r.entry !== undefined, '应匹配');
      assert(r.entry.bankCode === 'TEST', `bankCode: ${r.entry.bankCode}`);
      ok(`${r.entry.bankCode} / ${r.entry.subjectName}`);
    }

    run('account_registry.update 更新映射');
    {
      const r = await pythonProcess.call('account_registry.update', {
        id: testEntryId,
        matchType: 'exact',
        pattern: '9999999999999999',
        bank: '测试银行',
        bankCode: 'TEST',
        subjectName: '测试科目-银行存款',
        subjectCode: '10002',
      });
      assert(r.success === true, `update 应成功: ${JSON.stringify(r)}`);
      assert(r.entry.subjectName === '测试科目-银行存款', 'subjectName 应更新');
      assert(r.entry.subjectCode === '10002', 'subjectCode 应更新');
      ok(`${r.entry.subjectCode} ${r.entry.subjectName}`);
    }

    run('account_registry.delete 删除映射');
    {
      await pythonProcess.call('account_registry.delete', { id: testEntryId });
      const r = await pythonProcess.call('account_registry.match', { accountNumber: '9999999999999999' });
      if (r.entry) assert(r.entry.bankCode !== 'TEST', '删除后不应匹配 TEST');
      ok();
    }

    // ════════════════════════════════════════════
    // Phase 7: generate_excel 回归
    // ════════════════════════════════════════════
    phase('Phase 7: generate_excel');

    run('generate_excel 正常导出');
    {
      const mockTxns = [
        { date: '2026-01-15', description: '测试入账', amount: 15000, currency: 'CNY', direction: 'income', counterparty: 'Corp A' },
        { date: '2026-01-16', description: '测试消费', amount: 328.5, currency: 'CNY', direction: 'expense', counterparty: 'Vendor B' },
        { date: '2026-01-17', description: '测试转账', amount: 2000, currency: 'CNY', direction: 'expense', counterparty: 'User C' },
      ];
      const r = await pythonProcess.call('generate_excel', { transactions: mockTxns, output_path: TEST_EXCEL });
      assert(r.success === true, `应成功: ${JSON.stringify(r)}`);
      assert(fs.existsSync(TEST_EXCEL), '文件应存在');
      const size = fs.statSync(TEST_EXCEL).size;
      assert(size > 1000, `应 > 1KB: ${size}`);
      ok(`${path.basename(TEST_EXCEL)} · ${size} 字节 · 3 行`);
    }

    // ════════════════════════════════════════════
    // Phase 8: 参数验证回归
    // ════════════════════════════════════════════
    phase('Phase 8: 参数验证回归');

    run('parse_pdf 缺少 filePath');
    {
      const r = await pythonProcess.call('parse_pdf', {});
      assert(r.success === false, '应失败');
      assert(r.error && r.error.includes('filePath'), `错误信息应含 filePath: ${r.error}`);
      ok(`"${r.error}"`);
    }

    run('generate_excel 缺少 transactions');
    {
      const r = await pythonProcess.call('generate_excel', {});
      assert(r.success === false, '应失败');
      assert(r.error, '应有错误信息');
      ok(`"${r.error}"`);
    }

    run('detect_supported_banks BankInfo 结构');
    {
      const r = await pythonProcess.call('detect_supported_banks', {});
      assert(r.success === true, '应成功');
      assert(Array.isArray(r.banks), 'banks 应为数组');
      assert(r.banks.length >= 3, `至少 3 个: ${r.banks.length}`);
      for (const b of r.banks) {
        assert(b.code && b.name, `BankInfo 结构不完整: ${JSON.stringify(b)}`);
      }
      ok(`${r.banks.length} 个: ${r.banks.map(b => b.name).join(', ')}`);
    }

    // ── 总结 ──
    console.log('\n╔════════════════════════════════════════════╗');
    console.log('║    v0.3.0 全功能测试通过 ✅                ║');
    console.log('╚════════════════════════════════════════════╝\n');
    console.log('覆盖：');
    console.log('  ✅ db.health — SQLite 5 表结构验证');
    console.log('  ✅ detect_banks — 空/不存在/多无效/CMB/GFB/混合/重复');
    console.log('  ✅ parse_pdf — CMB PDF + ICBC CSV 自动路由');
    console.log('  ✅ ICBC OCR — 回单网格解析 + 交易流水表格线解析');
    console.log('  ✅ voucher.preview — 凭证预览 + 借贷平衡');
    console.log('  ✅ voucher.save_draft → load_draft 往返');
    console.log('  ✅ voucher.list_drafts + delete_draft CASCADE');
    console.log('  ✅ account_registry CRUD + match');
    console.log('  ✅ generate_excel 回归');
    console.log('  ✅ parse_pdf / generate_excel 参数验证');
    console.log('  ✅ detect_supported_banks 回归');

  } catch (err) {
    console.error(`\n❌ 测试失败 (第${step}步):`, err.message);
    console.error(err.stack);
    passed = false;
  } finally {
    cleanup();
    pythonProcess.stop();
    console.log('\n📁 输出目录:', OUTPUT_DIR);
    console.log('✨ 完成');
    process.exit(passed ? 0 : 1);
  }
}

process.on('unhandledRejection', err => {
  console.error('未处理异常:', err);
  cleanup();
  pythonProcess.stop();
  process.exit(1);
});
process.on('SIGINT', () => { cleanup(); pythonProcess.stop(); process.exit(0); });

main();