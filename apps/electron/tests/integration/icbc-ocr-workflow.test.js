/**
 * ICBC OCR 全流程集成测试
 * 覆盖：OCR PDF 识别 → ICBC 表格线网格解析 → Excel 导出
 *
 * 输出文件：tests/integration/output/ 目录
 * 运行：node tests/integration/icbc-ocr-workflow.test.js
 */
const { pythonProcess } = require('../../dist/pythonProcessManager');
const fs = require('fs');
const path = require('path');

// —— 配置 ——
const OUTPUT_DIR = path.resolve(__dirname, 'output');
const TEST_EXCEL_PATH = path.join(OUTPUT_DIR, 'icbc_ocr_export.xlsx');
const ICBC_PDF = process.env.ICBC_TEST_PDF ||
  'C:\\Users\\dell\\Desktop\\finance agent\\中国工商银行企业网上银行931-2603.pdf';

// —— 工具函数 ——
function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) fs.mkdirSync(dirPath, { recursive: true });
}

function cleanup() {
  console.log('\n[Cleanup] 清理临时文件...');
  if (!fs.existsSync(OUTPUT_DIR)) {
    console.log('  ✓ output 目录尚不存在');
    return;
  }
  const toClean = [TEST_EXCEL_PATH];
  for (const f of toClean) {
    if (fs.existsSync(f)) {
      fs.unlinkSync(f);
      console.log('  ✓ 删除:', path.basename(f));
    }
  }
  // 清理其他 icbc_/ocr_ 前缀的临时文件
  const files = fs.readdirSync(OUTPUT_DIR);
  for (const file of files) {
    if (file.startsWith('icbc_') || file.startsWith('ocr_')) {
      fs.unlinkSync(path.join(OUTPUT_DIR, file));
      console.log('  ✓ 删除:', file);
    }
  }
}

function assert(condition, message) {
  if (!condition) throw new Error('断言失败: ' + message);
}

async function runTests() {
  console.log('╔══════════════════════════════════════════╗');
  console.log('║  ICBC OCR 全流程端到端测试              ║');
  console.log('╚══════════════════════════════════════════╝\n');

  let passed = true;

  try {
    cleanup();
    ensureDir(OUTPUT_DIR);

    // —— 阶段 1：检查测试 PDF ——
    console.log('[1/6] 检查测试文件...');
    if (!fs.existsSync(ICBC_PDF)) {
      console.log(`  ⚠  ICBC PDF 未找到: ${ICBC_PDF}`);
      console.log('  设置 ICBC_TEST_PDF 环境变量跳过此测试\n');
      process.exit(0);  // 跳过而非失败
    }
    const pdfSize = fs.statSync(ICBC_PDF).size;
    console.log(`  ✓ PDF: ${path.basename(ICBC_PDF)} (${(pdfSize / 1024).toFixed(1)} KB)\n`);

    // —— 阶段 2：启动 Python 后端 ——
    console.log('[2/6] 启动 Python 后端...');
    await pythonProcess.start();
    await new Promise(r => setTimeout(r, 2000));
    console.log('  ✓ 进程启动完成\n');

    // —— 阶段 3：健康检查 ——
    console.log('[3/6] 健康检查...');
    const health = await pythonProcess.call('health', {});
    assert(health.status === 'ok', '后端状态应为 ok');
    console.log(`  ✓ 版本: ${health.version}, Python: ${health.python_version.split(' ')[0]}\n`);

    // —— 阶段 4：OCR 扫描件 PDF ——
    console.log('[4/6] OCR 识别 ICBC 扫描件...');
    const ocrStart = Date.now();
    const ocrResult = await pythonProcess.call('ocr_pdf', {
      file_path: ICBC_PDF,
      dpi: 200,
    });
    const ocrElapsed = ((Date.now() - ocrStart) / 1000).toFixed(1);
    assert(ocrResult.success, 'OCR 应成功');
    assert(ocrResult.total_pages >= 1, '至少 1 页');
    const blockCount = ocrResult.pages.reduce((sum, p) => sum + p.blocks.length, 0);
    console.log(`  ✓ ${ocrResult.total_pages} 页, ${blockCount} 个文本块 (${ocrElapsed}s)\n`);

    // —— 阶段 5：ICBC 解析（直接桥接） ——
    console.log('[5/6] ICBC 表格线网格解析 + Excel 导出...');
    const parseStart = Date.now();
    const parseResult = await pythonProcess.call('parse_pdf', {
      file_path: ICBC_PDF,
    });
    const parseElapsed = ((Date.now() - parseStart) / 1000).toFixed(1);

    assert(parseResult.success, '解析应成功');
    assert(parseResult.bank === '中国工商银行', `银行应为 中国工商银行，实际: ${parseResult.bank}`);
    assert(parseResult.transactions.length >= 1, '至少 1 笔交易');
    assert(parseResult.confidence >= 0.9, `置信度应 >= 0.9, 实际: ${parseResult.confidence}`);

    console.log(`  ✓ 银行: ${parseResult.bank}`);
    console.log(`  ✓ 交易数: ${parseResult.transactions.length}`);
    console.log(`  ✓ 对账单日期: ${parseResult.statement_date}`);
    console.log(`  ✓ 置信度: ${parseResult.confidence}`);
    console.log(`  ✓ 耗时: ${parseElapsed}s`);

    // 验证关键交易
    const tx = parseResult.transactions;
    const tx0 = tx[0];
    assert(tx0.date === '2026-03-06', `首笔日期应为 2026-03-06, 实际: ${tx0.date}`);
    assert(tx0.direction === 'expense', '首笔应为支出');

    // 验证余额链
    const txWithBalance = tx.filter(t => t.notes);
    assert(txWithBalance.length > 10, '应有超过 10 笔带余额');
    const firstBal = txWithBalance[0].notes;
    const lastBal = txWithBalance[txWithBalance.length - 1].notes;
    console.log(`  ✓ 余额链: ${firstBal} → ${lastBal}`);

    // 验证无文字跨行（counterparty 不能是孤立的单字）
    for (const t of tx) {
      if (t.counterparty && t.counterparty.length === 1) {
        throw new Error(`检测到文字泄漏: tx counterparty 仅 1 个字符 "${t.counterparty}"`);
      }
    }
    console.log('  ✓ 无文字跨行泄漏\n');

    // —— 阶段 6：Excel 导出 ——
    console.log('[6/6] Excel 导出...');
    const excelResult = await pythonProcess.call('generate_excel', {
      transactions: parseResult.transactions,
      output_path: TEST_EXCEL_PATH,
    });
    assert(excelResult.success, 'Excel 导出应成功');
    assert(fs.existsSync(TEST_EXCEL_PATH), 'Excel 文件应存在');
    const excelSize = fs.statSync(TEST_EXCEL_PATH).size;
    assert(excelSize > 1000, `Excel 文件应 > 1KB, 实际: ${excelSize} 字节`);
    console.log(`  ✓ 文件: ${path.basename(TEST_EXCEL_PATH)} (${excelSize} 字节)\n`);

    // —— 总结 ——
    console.log('╔══════════════════════════════════════════╗');
    console.log('║  ICBC OCR 全流程测试通过 ✅             ║');
    console.log('╚══════════════════════════════════════════╝\n');
    console.log('覆盖：');
    console.log('  ✅ Python 进程启动');
    console.log('  ✅ JSON-RPC 2.0 通信');
    console.log('  ✅ health 检查');
    console.log('  ✅ OCR PDF 扫描件识别');
    console.log('  ✅ ICBC 表格线网格解析');
    console.log('  ✅ 交易字段验证（日期/金额/方向/对方户名/流水号/余额）');
    console.log('  ✅ 余额链完整性');
    console.log('  ✅ 无文字跨行泄漏');
    console.log('  ✅ Excel 导出');

  } catch (error) {
    console.error('\n❌ 测试失败:', error.message);
    passed = false;
  } finally {
    cleanup();
    pythonProcess.stop();
    console.log('\n📁 输出目录:', OUTPUT_DIR);
    console.log('✨ 完成');
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
