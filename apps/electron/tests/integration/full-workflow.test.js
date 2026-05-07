/**
 * 全流程端到端测试
 * 覆盖：Python 启动 → PDF 解析 → 对账 → Excel 导出 → 清理
 */

const { pythonProcess } = require('../../dist/pythonProcessManager');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const OUTPUT_BASE = path.resolve(__dirname, 'output');
const WORKFLOW_DIR = path.join(OUTPUT_BASE, 'full-workflow');
const TEST_PDF_PATH = path.join(WORKFLOW_DIR, 'test_statement.pdf');
const TEST_LEDGER_PATH = path.join(WORKFLOW_DIR, 'test_ledger.json');
const TEST_EXCEL_PATH = path.join(WORKFLOW_DIR, 'reconciliation_result.xlsx');

function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) fs.mkdirSync(dirPath, { recursive: true });
}

function cleanup() {
  console.log('\n[Cleanup] 清理临时文件...');
  try {
    if (fs.existsSync(WORKFLOW_DIR)) {
      fs.rmSync(WORKFLOW_DIR, { recursive: true, force: true });
      console.log('  ✓ 输出目录已清空');
    }
  } catch (e) {
    console.error('  ⚠ 清理失败:', e.message);
  }
}

function generateTestPDF() {
  console.log('[Prep] 生成测试 PDF...');
  ensureDir(WORKFLOW_DIR);

  const pythonExe = process.env.PYTHON_CMD ||
    path.resolve(__dirname, '../../../python/.venv/Scripts/python.exe');
  const srcPath = path.resolve(__dirname, '../../../python/src');
  const pdfPath = TEST_PDF_PATH;

  const script = `import sys
sys.path.insert(0, r"${srcPath.replace(/\\/g, '\\\\')}")
import fitz
doc = fitz.open()
page = doc.new_page()
text = """银行流水明细
=====================================
交易日期    交易说明            金额       对方户名
2025-05-01  工资收入            +15000.00  XX科技有限公司
2025-05-02  超市购物            -328.50   沃尔玛超市
2025-05-03  转账给张三          -2000.00  张三
2025-05-05  利息收入            +12.50    中国银行
"""
page.insert_text((50, 50), text, fontsize=12)
doc.save(r"${pdfPath.replace(/\\/g, '\\\\')}")
doc.close()
print("PDF OK")
`;

  return new Promise((resolve, reject) => {
    const tempScript = path.join(WORKFLOW_DIR, 'gen_pdf.py');
    fs.writeFileSync(tempScript, script, 'utf8');
    const proc = spawn(pythonExe, [tempScript], { cwd: __dirname, stdio: 'pipe', shell: true });
    let out = '';
    proc.stdout.on('data', d => out += d.toString());
    proc.stderr.on('data', d => console.error('[PDF]', d.toString().trim()));
    proc.on('close', code => {
      try { fs.unlinkSync(tempScript); } catch (e) {}
      if (code === 0 && fs.existsSync(TEST_PDF_PATH)) {
        console.log('  ✓ PDF 已生成');
        resolve();
      } else {
        reject(new Error('失败 code=' + code + ', out: ' + out));
      }
    });
    proc.on('error', reject);
  });
}

function generateTestLedger() {
  console.log('[Prep] 生成测试台账...');
  ensureDir(WORKFLOW_DIR);
  const ledger = {
    generated_at: new Date().toISOString(),
    transactions: [
      { date: '2025-05-01', description: '工资收入', amount: 15000.00, counterparty: 'XX科技有限公司' },
      { date: '2025-05-02', description: '超市消费', amount: -328.50, counterparty: '沃尔玛' },
      { date: '2025-05-03', description: '借款给张三', amount: -2000.00, counterparty: '张三' },
      { date: '2025-05-06', description: '现金支出', amount: -500.00, counterparty: '备用金' },
    ],
  };
  fs.writeFileSync(TEST_LEDGER_PATH, JSON.stringify(ledger, null, 2));
  console.log('  ✓ 台账文件已创建');
}

async function runFullWorkflow() {
  console.log('=== 全流程端到端测试 ===\n');
  let passed = true;

  try {
    cleanup();
    ensureDir(WORKFLOW_DIR);

    console.log('=== 阶段 1: 测试数据 ===\n');
    await generateTestPDF();
    generateTestLedger();
    console.log('');

    console.log('=== 阶段 2: Python 后端 ===\n');
    await pythonProcess.start();
    await new Promise(r => setTimeout(r, 1500));
    console.log('✅ 进程已启动\n');

    console.log('=== 阶段 3: 健康检查 ===\n');
    const health = await pythonProcess.call('health', {});
    console.log('  版本:', health.version);
    console.log('✅ 服务正常\n');

    console.log('=== 阶段 4: PDF 解析 ===\n');
    const parse = await pythonProcess.call('parse_pdf', {
      file_path: TEST_PDF_PATH,
      bank: '测试银行',
    });
    console.log('  交易数:', parse.transactions.length);
    console.log('  银行:', parse.bank);
    parse.transactions.forEach((t, i) => {
      console.log('    ' + (i + 1) + '. ' + t.date + ' ' + (t.direction === 'income' ? '+' : '') + t.amount + ' - ' + t.description);
    });
    if (!parse.success) throw new Error('PDF 解析失败: ' + parse.error);
    console.log('✅ 解析成功\n');

    console.log('=== 阶段 5: 对账 ===\n');
    const recon = await pythonProcess.call('reconcile', {
      pdf_path: TEST_PDF_PATH,
      ledger_path: TEST_LEDGER_PATH,
    });
    console.log('  匹配数:', recon.matched_count);
    console.log('  银行未达:', recon.unreconciled_bank);
    console.log('  台账未达:', recon.unreconciled_ledger);
    console.log('  匹配率:', (recon.match_rate * 100).toFixed(1) + '%');
    if (!recon.success) throw new Error('对账失败: ' + recon.error);
    console.log('✅ 对账完成\n');

    console.log('=== 阶段 6: Excel 导出 ===\n');
    const excel = await pythonProcess.call('generate_excel', {
      reconcile_result: {
        matched: recon.matched || [],
        bank_unreconciled: [],
        ledger_unreconciled: [],
        suspicious: [],
      },
      output_path: TEST_EXCEL_PATH,
    });
    if (!excel.success || !fs.existsSync(TEST_EXCEL_PATH)) {
      throw new Error('Excel 生成失败: ' + JSON.stringify(excel));
    }
    const stats = fs.statSync(TEST_EXCEL_PATH);
    console.log('  ✅ 生成成功');
    console.log('     路径:', path.basename(TEST_EXCEL_PATH));
    console.log('     大小:', stats.size, '字节\n');

    console.log('=== 阶段 7: 输出验证 ===\n');
    const files = fs.readdirSync(WORKFLOW_DIR);
    console.log('  输出目录:', path.relative(__dirname, WORKFLOW_DIR));
    files.forEach(f => {
      const s = fs.statSync(path.join(WORKFLOW_DIR, f));
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
    console.log('  ✅ PDF 解析');
    console.log('  ✅ 对账算法');
    console.log('  ✅ Excel 导出');
    console.log('  ✅ 文件管理');

  } catch (e) {
    console.error('\n❌ 失败:', e.message);
    passed = false;
  } finally {
    cleanup();
    pythonProcess.stop();
    console.log('\n📁 工作目录:', WORKFLOW_DIR);
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
