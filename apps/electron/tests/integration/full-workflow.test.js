/**
 * 全流程端到端测试
 * 覆盖：Python 启动 → detect → parse → Excel 导出 → 清理
 */

const { pythonProcess } = require('../../dist/pythonProcessManager');
const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = path.resolve(__dirname, 'output');

// ---------- 真实测试文件 ----------

const REAL_FILES = {
  cmb_pdf: path.join('C:\\Users\\dell\\Desktop\\finance agent', 'cmb-03.pdf'),
};

// ---------- 工具 ----------

function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) fs.mkdirSync(dirPath, { recursive: true });
}

function cleanup() {
  console.log('\n[Cleanup] 清理临时文件...');
  const files = fs.readdirSync(OUTPUT_DIR);
  let cleaned = 0;
  for (const f of files) {
    const fp = path.join(OUTPUT_DIR, f);
    if (fs.statSync(fp).isFile()) {
      fs.unlinkSync(fp);
      cleaned++;
    }
  }
  console.log(`  ${cleaned > 0 ? `✓ 清理 ${cleaned} 个文件` : '✓ 无需清理'}`);
}

function assert(cond, msg) {
  if (!cond) throw new Error('断言失败: ' + msg);
}

// ---------- 主流程 ----------

async function runFullWorkflow() {
  console.log('=== 全流程端到端测试 ===\n');
  let passed = true;

  try {
    cleanup();
    ensureDir(OUTPUT_DIR);

    // ── 阶段 1: 启动后端 ──
    console.log('=== 阶段 1: Python 后端 ===\n');
    await pythonProcess.start();
    await new Promise(r => setTimeout(r, 1500));
    console.log('✅ 进程已启动\n');

    // ── 阶段 2: 健康检查 ──
    console.log('=== 阶段 2: 健康检查 ===\n');
    const health = await pythonProcess.call('health', {});
    assert(health.status === 'ok', 'health status 应为 ok');
    assert(health.version === '0.2.0', `版本应为 0.2.0，实际 ${health.version}`);
    console.log('  版本:', health.version);
    console.log('  Python:', health.python_version.split(' ')[0]);
    console.log('✅ 服务正常\n');

    // ── 阶段 3: detect_banks（自动识别）──
    console.log('=== 阶段 3: detect_banks ===\n');
    const detectR = await pythonProcess.call('detect_banks', { filePaths: [REAL_FILES.cmb_pdf] });
    assert(detectR.success === true, 'detect 应成功');
    assert(detectR.results.length === 1, '应返回 1 个结果');
    assert(detectR.results[0].status === 'ok', 'PDF 应检测成功');
    assert(detectR.results[0].bank, '应返回 bank');
    assert(detectR.results[0].docType, '应返回 docType');
    const detectedBank = detectR.results[0].bank;
    const detectedDocType = detectR.results[0].docType;
    console.log(`  检测到: ${detectedBank} · ${detectedDocType}`);
    console.log('✅ 检测成功\n');

    // ── 阶段 4: parse_pdf（透传 detect 结果）──
    console.log('=== 阶段 4: PDF 解析 ===\n');
    const parse = await pythonProcess.call('parse_pdf', {
      filePath: REAL_FILES.cmb_pdf,
      bank: detectedBank,
      docType: detectedDocType,
    });
    assert(typeof parse === 'object', '应返回对象');
    assert('success' in parse, '应含 success 字段');
    assert(Array.isArray(parse.transactions), '应含 transactions 数组');
    assert(parse.bank, '应含 bank');
    console.log('  交易数:', parse.transactions.length);
    console.log('  银行:', parse.bank);
    if (parse.transactions.length > 0) {
      parse.transactions.forEach((t, i) => {
        console.log(`    ${i + 1}. ${t.date} ${t.direction === 'income' ? '+' : ''}${t.amount} - ${t.description}`);
      });
    }
    if (!parse.success) throw new Error('PDF 解析失败: ' + parse.error);
    console.log('✅ 解析成功\n');

    // ── 阶段 5: Excel 导出 ──
    console.log('=== 阶段 5: Excel 导出 ===\n');
    const TEST_EXCEL_PATH = path.join(OUTPUT_DIR, 'full_workflow_export.xlsx');
    const excel = await pythonProcess.call('generate_excel', {
      transactions: parse.transactions,
      output_path: TEST_EXCEL_PATH,
    });
    if (!excel.success || !fs.existsSync(TEST_EXCEL_PATH)) {
      throw new Error('Excel 生成失败: ' + JSON.stringify(excel));
    }
    const stats = fs.statSync(TEST_EXCEL_PATH);
    console.log('  ✅ 生成成功');
    console.log('     路径:', path.basename(TEST_EXCEL_PATH));
    console.log('     大小:', stats.size, '字节\n');

    // ── 阶段 6: 输出验证 ──
    console.log('=== 阶段 6: 输出验证 ===\n');
    const files = fs.readdirSync(OUTPUT_DIR);
    console.log('  输出目录:', path.relative(__dirname, OUTPUT_DIR));
    files.forEach(f => {
      const s = fs.statSync(path.join(OUTPUT_DIR, f));
      console.log('    ├─', f, '(' + s.size + ' 字节)');
    });
    console.log('✅ 所有文件正常\n');

    console.log('╔══════════════════════════════════════╗');
    console.log('║    全流程测试通过 ✅                 ║');
    console.log('╚══════════════════════════════════════╝');
    console.log('\n覆盖：');
    console.log('  ✅ Python 进程启动');
    console.log('  ✅ JSON-RPC 2.0');
    console.log('  ✅ health 检查');
    console.log('  ✅ detect_banks 自动识别');
    console.log('  ✅ parse_pdf 解析（透传 detect 结果）');
    console.log('  ✅ Excel 导出');
    console.log('  ✅ 文件管理');

  } catch (e) {
    console.error('\n❌ 失败:', e.message);
    passed = false;
  } finally {
    cleanup();
    pythonProcess.stop();
    console.log('\n📁 工作目录:', OUTPUT_DIR);
    console.log('✨ 完成');
    process.exit(passed ? 0 : 1);
  }
}

process.on('unhandledRejection', (e) => {
  console.error('未处理异常:', e);
  cleanup();
  pythonProcess.stop();
  process.exit(1);
});
process.on('SIGINT', () => {
  cleanup();
  pythonProcess.stop();
  process.exit(0);
});

runFullWorkflow();
