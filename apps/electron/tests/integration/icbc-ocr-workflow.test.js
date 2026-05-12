/**
 * ICBC OCR 全流程集成测试
 * 覆盖：OCR PDF 识别 → ICBC 表格线网格解析 → Excel 导出
 *
 * 运行：node tests/integration/icbc-ocr-workflow.test.js
 */
const { pythonProcess } = require('../../dist/pythonProcessManager');
const fs = require('fs');
const path = require('path');

// —— 配置 ——
const OUTPUT_DIR = path.resolve(__dirname, 'output');
const TEST_PDFS = [
  'C:\\Users\\dell\\Desktop\\finance agent\\中国工商银行企业网上银行931-2603.pdf',
  'C:\\Users\\dell\\Desktop\\finance agent\\中国工商银行企业网上银行931-2-2603.pdf',
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

function validateTransactions(transactions, label) {
  console.log(`  [${label}] 验证 ${transactions.length} 笔交易...`);

  // 基本字段完整性
  for (let i = 0; i < transactions.length; i++) {
    const t = transactions[i];
    assert(t.date, `#${i + 1} 日期缺失`);
    assert(typeof t.amount === 'number' && t.amount > 0, `#${i + 1} 金额无效: ${t.amount}`);
    assert(t.direction === 'expense' || t.direction === 'income', `#${i + 1} 方向无效: ${t.direction}`);
    assert(t.counterparty === null || t.counterparty.length >= 2, `#${i + 1} counterparty 跨行泄漏: "${t.counterparty}"`);
    assert(t.description && t.description.length > 0, `#${i + 1} 描述缺失`);
  }

  // 有 counterparty 的交易数（排除手续费等）
  const withCounterparty = transactions.filter(t => t.counterparty);
  console.log(`    counterparty: ${withCounterparty.length}/${transactions.length}`);

  // 有 ref 的交易
  const withRef = transactions.filter(t => t.reference_number);
  console.log(`    reference:    ${withRef.length}/${transactions.length}`);

  // 余额链
  const withBalance = transactions.filter(t => t.notes);
  if (withBalance.length >= 2) {
    const firstB = parseFloat(withBalance[0].notes.replace(/,/g, ''));
    const lastB = parseFloat(withBalance[withBalance.length - 1].notes.replace(/,/g, ''));
    console.log(`    balance 链:   ${withBalance[0].notes} → ${withBalance[withBalance.length - 1].notes}`);
    // 如果是支出链，最后一次余额应该 <= 第一次（余额递减）
    // 不做强断言，因为中间可能有收入
  }

  // 抽样验证关键字段
  const sample = transactions.filter(t => t.counterparty);
  if (sample.length > 0) {
    console.log(`    Sample: #1 "${sample[0].date}" ${sample[0].counterparty} | ${sample[0].description}`);
  }
  if (withRef.length > 0) {
    const r = withRef[0].reference_number;
    assert(!r.includes('|'), `ref 不应含管道符: ${r}`);
  }
}

async function runTests() {
  console.log('══════════════════════════════════════════════');
  console.log('  ICBC OCR 全流程端到端测试');
  console.log('══════════════════════════════════════════════\n');

  let passed = true;

  try {
    cleanup();
    ensureDir(OUTPUT_DIR);

    // —— 阶段 1：检查测试 PDF ——
    console.log('[1/5] 检查测试文件...');
    const availablePdfs = TEST_PDFS.filter(p => {
      const ok = fs.existsSync(p);
      console.log(ok ? `  ✓ ${path.basename(p)}` : `  ✗ 未找到: ${p}`);
      return ok;
    });
    assert(availablePdfs.length > 0, '至少需要一个 ICBC PDF');
    console.log();

    // —— 阶段 2：启动 Python 后端 ——
    console.log('[2/5] 启动 Python 后端...');
    await pythonProcess.start();
    await new Promise(r => setTimeout(r, 2000));
    console.log('  ✓ 进程已启动\n');

    // —— 阶段 3：健康检查 ——
    console.log('[3/5] 健康检查...');
    const health = await pythonProcess.call('health', {});
    assert(health.status === 'ok', '后端状态应为 ok');
    console.log(`  ✓ 版本: ${health.version}, Python: ${health.python_version}\n`);

    // —— 阶段 4：解析每个 PDF ——
    console.log('[4/5] ICBC 表格线网格解析...');
    const allTransactions = [];
    for (const pdfPath of availablePdfs) {
      const fname = path.basename(pdfPath);
      const start = Date.now();
      const result = await pythonProcess.call('parse_pdf', { file_path: pdfPath });
      const elapsed = ((Date.now() - start) / 1000).toFixed(1);

      assert(result.success, `${fname} 解析应成功`);
      assert(result.bank === '中国工商银行', `${fname} 银行应为 中国工商银行, 实际: ${result.bank}`);
      assert(result.transactions.length >= 1, `${fname} 至少 1 笔交易`);
      assert(result.confidence >= 0.9, `${fname} 置信度 >= 0.9, 实际: ${result.confidence}`);

      console.log(`  ✓ ${fname}: ${result.transactions.length} 笔交易, 日期 ${result.statement_date}, ${elapsed}s`);
      validateTransactions(result.transactions, fname);
      console.log();
      allTransactions.push(...result.transactions);
    }

    // —— 阶段 5：Excel 导出 ——
    const excelPath = path.join(OUTPUT_DIR, 'icbc_ocr_export.xlsx');
    console.log('[5/5] Excel 导出...');
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
    console.log('  ICBC OCR 全流程测试通过');
    console.log('══════════════════════════════════════════════\n');
    console.log(`  PDF 文件: ${availablePdfs.length}`);
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
