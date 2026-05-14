/**
 * ICBC 全流程集成测试 — 涵盖回单 + 交易流水
 * 覆盖：PDF 解析 (回单/流水) → OCR → Excel 导出
 *
 * 运行：node tests/integration/icbc-ocr-workflow.test.js
 */
const { pythonProcess } = require('../../dist/pythonProcessManager');
const fs = require('fs');
const path = require('path');

// —— 配置 ——
const OUTPUT_DIR = path.resolve(__dirname, 'output');
const BASE = 'C:\\Users\\dell\\Desktop\\finance agent';

// 回单 PDFs
const RECEIPT_PDFS = [
  path.join(BASE, '回单pdf', '中国工商银行企业网上银行363-1回单.pdf'),
  path.join(BASE, '回单pdf', '中国工商银行企业网上银行363-2回单.pdf'),
];

// 交易流水 PDFs (如果存在)
const STATEMENT_PDFS = [
  path.join(BASE, '中国工商银行企业网上银行931-2603.pdf'),
  path.join(BASE, '中国工商银行企业网上银行931-2-2603.pdf'),
];

// 其他银行对账单
const OTHER_PDFS = [
  path.join(BASE, '广发hq_9550880227328600146_18050959_924910_1.pdf'),
  path.join(BASE, '招行对账单，中锦技术（广东）有限公司，120921552710288，人民币，202603，共1份.pdf'),
];

// —— 工具函数 ——
function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) fs.mkdirSync(dirPath, { recursive: true });
}

function cleanup() {
  console.log('\n[Cleanup] 清理输出文件...');
  if (!fs.existsSync(OUTPUT_DIR)) return;
  const files = fs.readdirSync(OUTPUT_DIR);
  for (const f of files) {
    fs.unlinkSync(path.join(OUTPUT_DIR, f));
    console.log('  已删除:', f);
  }
}

function assert(condition, message) {
  if (!condition) throw new Error('断言失败: ' + message);
}

// —— 回单验证 ——
function validateReceipts(transactions, label) {
  console.log(`  [${label}] 验证 ${transactions.length} 笔回单交易...`);

  assert(transactions.length >= 1, `${label} 至少 1 笔回单`);

  for (let i = 0; i < transactions.length; i++) {
    const t = transactions[i];
    assert(t.date, `#${i + 1} 日期缺失`);
    assert(typeof t.amount === 'number' && t.amount > 0, `#${i + 1} 金额无效: ${t.amount}`);
    assert(t.direction === 'expense' || t.direction === 'income', `#${i + 1} 方向无效: ${t.direction}`);
    assert(t.description && t.description.length > 0, `#${i + 1} 描述缺失`);
    // notes 应该已清理"备注："前缀
    if (t.notes) {
      assert(!t.notes.startsWith('备注：'), `#${i + 1} notes 未清理"备注："前缀: "${t.notes.substring(0, 10)}"`);
    }
  }

  // 统计
  const expenses = transactions.filter(t => t.direction === 'expense');
  const incomes = transactions.filter(t => t.direction === 'income');
  const withCounterparty = transactions.filter(t => t.counterparty);
  const withRef = transactions.filter(t => t.reference_number);
  console.log(`    expense: ${expenses.length}, income: ${incomes.length}`);
  console.log(`    counterparty: ${withCounterparty.length}/${transactions.length}`);
  console.log(`    reference:    ${withRef.length}/${transactions.length}`);

  // 抽样
  if (withCounterparty.length > 0) {
    const sample = withCounterparty[0];
    console.log(`    Sample: "${sample.date}" ${sample.direction} [${sample.counterparty}] ${sample.description} 金额=${sample.amount}`);
  }
}

// —— 流水验证 ——
function validateStatements(transactions, label) {
  console.log(`  [${label}] 验证 ${transactions.length} 笔流水交易...`);

  for (let i = 0; i < transactions.length; i++) {
    const t = transactions[i];
    assert(t.date, `#${i + 1} 日期缺失`);
    assert(typeof t.amount === 'number' && t.amount > 0, `#${i + 1} 金额无效: ${t.amount}`);
    assert(t.direction === 'expense' || t.direction === 'income', `#${i + 1} 方向无效: ${t.direction}`);
    assert(t.description && t.description.length > 0, `#${i + 1} 描述缺失`);
    // counterparty 不应有跨行泄漏
    if (t.counterparty) {
      assert(!t.counterparty.includes('\n'), `#${i + 1} counterparty 含换行: "${t.counterparty}"`);
    }
  }

  const withCounterparty = transactions.filter(t => t.counterparty);
  const withRef = transactions.filter(t => t.reference_number);
  console.log(`    counterparty: ${withCounterparty.length}/${transactions.length}`);
  console.log(`    reference:    ${withRef.length}/${transactions.length}`);
}

// —— 主流程 ——
async function runTests() {
  console.log('══════════════════════════════════════════════');
  console.log('  ICBC 全流程端到端测试 (回单 + 交易流水)');
  console.log('══════════════════════════════════════════════\n');

  let passed = true;

  try {
    cleanup();
    ensureDir(OUTPUT_DIR);

    // —— 阶段 1：检查文件 ——
    console.log('[1/6] 检查测试文件...');
    const availableReceipts = RECEIPT_PDFS.filter(p => {
      const ok = fs.existsSync(p);
      console.log(ok ? `  ✓ [回单] ${path.basename(p)}` : `  ✗ 未找到: ${p}`);
      return ok;
    });
    const availableStatements = STATEMENT_PDFS.filter(p => {
      const ok = fs.existsSync(p);
      console.log(ok ? `  ✓ [流水] ${path.basename(p)}` : `  ✗ 未找到: ${p}`);
      return ok;
    });
    assert(availableReceipts.length > 0 || availableStatements.length > 0, '至少需要一个测试 PDF');
    console.log();

    // —— 阶段 2：启动 Python 后端 ——
    console.log('[2/6] 启动 Python 后端...');
    await pythonProcess.start();
    await new Promise(r => setTimeout(r, 2000));
    console.log('  ✓ 进程已启动\n');

    // —— 阶段 3：健康检查 ——
    console.log('[3/6] 健康检查...');
    const health = await pythonProcess.call('health', {});
    assert(health.status === 'ok', '后端状态应为 ok');
    console.log(`  ✓ 版本: ${health.version}, Python: ${health.python_version}\n`);

    let allTransactions = [];

    // —— 阶段 4：解析回单 PDF ——
    console.log('[4/6] ICBC 回单网格解析...');
    for (const pdfPath of availableReceipts) {
      const fname = path.basename(pdfPath);
      const start = Date.now();
      const result = await pythonProcess.call('parse_pdf', { file_path: pdfPath });
      const elapsed = ((Date.now() - start) / 1000).toFixed(1);

      assert(result.success, `${fname} 解析应成功: ${result.error || ''}`);
      assert(result.bank === '中国工商银行', `${fname} 银行应为 中国工商银行, 实际: ${result.bank}`);
      assert(result.transactions.length >= 1, `${fname} 至少 1 笔交易`);
      assert(result.confidence >= 0.5, `${fname} 置信度 >= 0.5, 实际: ${result.confidence}`);

      console.log(`  ✓ ${fname}: ${result.transactions.length} 笔回单, 日期 ${result.statement_date}, ${elapsed}s`);
      validateReceipts(result.transactions, fname);
      console.log();
      allTransactions.push(...result.transactions);
    }

    // —— 阶段 5：解析交易流水 PDF (如果存在) ——
    if (availableStatements.length > 0) {
      console.log('[5/6] ICBC 交易流水表格线解析...');
      for (const pdfPath of availableStatements) {
        const fname = path.basename(pdfPath);
        const start = Date.now();
        const result = await pythonProcess.call('parse_pdf', { file_path: pdfPath });
        const elapsed = ((Date.now() - start) / 1000).toFixed(1);

        assert(result.success, `${fname} 解析应成功: ${result.error || ''}`);
        assert(result.bank === '中国工商银行', `${fname} 银行应为 中国工商银行`);
        assert(result.transactions.length >= 1, `${fname} 至少 1 笔交易`);
        assert(result.confidence >= 0.5, `${fname} 置信度 >= 0.5, 实际: ${result.confidence}`);

        console.log(`  ✓ ${fname}: ${result.transactions.length} 笔交易, 日期 ${result.statement_date}, ${elapsed}s`);
        validateStatements(result.transactions, fname);
        console.log();
        allTransactions.push(...result.transactions);
      }
    } else {
      console.log('[5/6] 跳过交易流水测试 (无文件)\n');
    }

    // —— 阶段 6：Excel 导出 ——
    const excelPath = path.join(OUTPUT_DIR, 'icbc_full_export.xlsx');
    console.log('[6/6] Excel 导出...');
    const excelResult = await pythonProcess.call('generate_excel', {
      transactions: allTransactions,
      output_path: excelPath,
    });
    assert(excelResult.success, 'Excel 导出应成功');
    assert(fs.existsSync(excelPath), 'Excel 文件应存在');
    const excelSize = fs.statSync(excelPath).size;
    assert(excelSize > 2000, `Excel 应 > 2KB, 实际: ${excelSize} 字节`);
    console.log(`  ✓ ${path.basename(excelPath)} (${excelSize} 字节, ${allTransactions.length} 行)\n`);

    // —— 总结 ——
    console.log('══════════════════════════════════════════════');
    console.log('  ICBC 全流程测试通过');
    console.log('══════════════════════════════════════════════\n');
    console.log(`  回单 PDF: ${availableReceipts.length} 个`);
    console.log(`  流水 PDF: ${availableStatements.length} 个`);
    console.log(`  总交易数: ${allTransactions.length}`);
    console.log(`  Excel 导出: ${path.basename(excelPath)}`);

  } catch (error) {
    console.error('\n❌ 测试失败:', error.message);
    passed = false;
  } finally {
    cleanup();
    pythonProcess.stop();
    console.log('\n✨ 完成');
    process.exit(passed ? 0 : 1);
  }
}

process.on('unhandledRejection', (err) => {
  console.error('未处理异常:', err);
  cleanup();
  pythonProcess.stop();
  process.exit(1);
});
process.on('SIGINT', () => {
  cleanup();
  pythonProcess.stop();
  process.exit(0);
});

runTests();
