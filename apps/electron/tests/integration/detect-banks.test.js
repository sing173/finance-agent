/**
 * detect_banks / detect_supported_banks 集成测试
 *
 * 覆盖：成功场景 + 失败场景 + 边界情况
 *
 * 前置条件：
 *   - apps/python/.venv 已创建且依赖已安装
 *   - apps/electron/dist/ 已编译（tsc 零错误）
 *
 * 运行：node tests/integration/detect-banks.test.js
 */
const { pythonProcess } = require('../../dist/pythonProcessManager');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const OUTPUT_DIR = path.resolve(__dirname, 'output');
const TEST_PDF_1 = path.join(OUTPUT_DIR, 'detect_test_icbc.pdf');
const TEST_PDF_2 = path.join(OUTPUT_DIR, 'detect_test_cmb.pdf');

// ---------- 工具 ----------

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function cleanup() {
  const files = [TEST_PDF_1, TEST_PDF_2];
  let cleaned = 0;
  for (const f of files) {
    if (fs.existsSync(f)) {
      fs.unlinkSync(f);
      cleaned++;
    }
  }
  if (cleaned > 0) console.log(`  ✓ 清理 ${cleaned} 个临时文件`);
}

function assert(cond, msg) {
  if (!cond) throw new Error('断言失败: ' + msg);
}

/**
 * 生成测试 PDF（复用 v020-e2e 的模式）
 */
function generateTestPDF(outPath, bankText, docTypeText, suffix) {
  return new Promise((resolve, reject) => {
    ensureDir(OUTPUT_DIR);
    const srcPath = path.resolve(__dirname, '../../../python/src');
    const script = `import sys
sys.path.insert(0, r"${srcPath.replace(/\\/g, '\\\\')}")
import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), r"${bankText} ${docTypeText}", fontsize=16, fontname="china-ss")
page.insert_text((50, 75), r"=====================================", fontsize=12, fontname="china-ss")
page.insert_text((50, 95), r"Date       Description                Amount    Counterparty", fontsize=12, fontname="china-ss")
page.insert_text((50, 115), r"2025-06-01  ${suffix} Income           +15000.00  Corp A", fontsize=12, fontname="china-ss")
page.insert_text((50, 135), r"2025-06-02  ${suffix} Shopping         -328.50   Mart Inc", fontsize=12, fontname="china-ss")
doc.save(r"${outPath.replace(/\\/g, '\\\\')}")
doc.close()
print("OK")
`;
    const tmpScript = path.join(OUTPUT_DIR, '_gen_' + path.basename(outPath, '.pdf') + '.py');
    fs.writeFileSync(tmpScript, script, 'utf8');
    const pyExe = path.resolve(__dirname, '../../../python/.venv/Scripts/python.exe');
    const proc = spawn(pyExe, [tmpScript], { shell: true, stdio: 'pipe' });
    let out = '';
    proc.stdout.on('data', d => out += d.toString());
    proc.on('close', code => {
      try { fs.unlinkSync(tmpScript); } catch (_) {}
      if (code === 0 && fs.existsSync(outPath)) resolve();
      else reject(new Error('PDF gen failed, code=' + code + ', out=' + out));
    });
    proc.on('error', reject);
  });
}

// ---------- 主流程 ----------

async function runTests() {
  console.log('=== detect_banks / detect_supported_banks 集成测试 ===\n');
  let allPassed = true;
  let testCount = 0;
  let passCount = 0;

  function test(name, fn) {
    testCount++;
    console.log(`[${testCount}] ${name}...`);
    fn();
    passCount++;
    console.log(`  ✅ 通过\n`);
  }

  try {
    cleanup();

    // 准备测试数据
    console.log('[Prep] 生成测试 PDF...');
    await generateTestPDF(TEST_PDF_1, '工商银行', '交易流水', 'ICBC-Stmt');
    await generateTestPDF(TEST_PDF_2, '招商银行', '交易流水', 'CMB-Stmt');
    console.log('  ✓ 2 份 PDF 已生成\n');

    // 启动后端
    console.log('[Boot] 启动 Python 后端...');
    await pythonProcess.start();
    await new Promise(r => setTimeout(r, 1500));
    console.log('  ✓ 进程启动完成\n');

    // ═══ Slice 8: 失败场景 + 边界测试 ═══

    // Test 1: detect_supported_banks（回归）
    test('detect_supported_banks 返回银行列表', () => {
      // 在 async 块中同步执行 — 用 Promise 链
    });
    const banksResult = await pythonProcess.call('detect_supported_banks', {});
    assert(banksResult.success === true, 'success 应为 true');
    assert(Array.isArray(banksResult.banks), 'banks 应为数组');
    assert(banksResult.banks.length >= 3, `银行列表至少 3 个，实际 ${banksResult.banks.length}`);
    console.log(`  支持银行: ${banksResult.banks.join(', ')}`);
    testCount++; passCount++;
    console.log(`[${testCount}] detect_supported_banks 返回银行列表 ✅\n`);

    // Test 2: 空列表 → 空结果
    const emptyResult = await pythonProcess.call('detect_banks', { filePaths: [] });
    assert(emptyResult.success === true, '空列表 success 应为 true');
    assert(Array.isArray(emptyResult.results), '空列表 results 应为数组');
    assert(emptyResult.results.length === 0, `空列表应返回 0 个结果，实际 ${emptyResult.results.length}`);
    testCount++; passCount++;
    console.log(`[${testCount}] 空列表 → 空结果 ✅\n`);

    // Test 3: 文件不存在 → status=failed
    const badResult = await pythonProcess.call('detect_banks', {
      filePaths: ['/nonexistent/ghost_file.pdf'],
    });
    assert(badResult.success === true, 'success 应为 true');
    assert(badResult.results.length === 1, `应返回 1 个结果，实际 ${badResult.results.length}`);
    assert(badResult.results[0].status === 'failed', `不存在文件应 status=failed，实际 ${badResult.results[0].status}`);
    assert(badResult.results[0].filePath === '/nonexistent/ghost_file.pdf', 'filePath 应原样返回');
    testCount++; passCount++;
    console.log(`[${testCount}] 文件不存在 → status=failed ✅\n`);

    // Test 4: 有效 PDF 检测成功（工商银行）
    const okResult = await pythonProcess.call('detect_banks', { filePaths: [TEST_PDF_1] });
    assert(okResult.success === true, 'success 应为 true');
    assert(okResult.results.length === 1, `应返回 1 个结果，实际 ${okResult.results.length}`);
    assert(okResult.results[0].status === 'ok', `有效 PDF 应 status=ok，实际 ${okResult.results[0].status}`);
    assert(okResult.results[0].bank, '应返回 bank 字段');
    assert(okResult.results[0].docType, '应返回 docType 字段');
    console.log(`  检测到: ${okResult.results[0].bank} · ${okResult.results[0].docType}`);
    testCount++; passCount++;
    console.log(`[${testCount}] 有效 PDF → status=ok ✅\n`);

    // Test 5: 有效 PDF 检测成功（招商银行）
    const okResult2 = await pythonProcess.call('detect_banks', { filePaths: [TEST_PDF_2] });
    assert(okResult2.success === true, 'success 应为 true');
    assert(okResult2.results[0].status === 'ok', '有效 PDF 应 status=ok');
    assert(okResult2.results[0].bank, '应返回 bank 字段');
    console.log(`  检测到: ${okResult2.results[0].bank} · ${okResult2.results[0].docType}`);
    testCount++; passCount++;
    console.log(`[${testCount}] 有效 PDF（招商银行）→ status=ok ✅\n`);

    // Test 6: 混合列表 — 有效 + 不存在
    const mixedResult = await pythonProcess.call('detect_banks', {
      filePaths: [TEST_PDF_1, '/nonexistent/ghost.pdf', TEST_PDF_2],
    });
    assert(mixedResult.success === true, 'success 应为 true');
    assert(mixedResult.results.length === 3, `应返回 3 个结果，实际 ${mixedResult.results.length}`);
    const okCount = mixedResult.results.filter(x => x.status === 'ok').length;
    const failCount = mixedResult.results.filter(x => x.status === 'failed').length;
    assert(okCount === 2, `应有 2 个 ok，实际 ${okCount}`);
    assert(failCount === 1, `应有 1 个 failed，实际 ${failCount}`);
    // 验证每个结果都有 filePath
    for (const r of mixedResult.results) {
      assert(r.filePath, '每个结果应有 filePath');
    }
    console.log(`  混合 3 文件 → ${okCount} ok / ${failCount} failed`);
    testCount++; passCount++;
    console.log(`[${testCount}] 混合列表（有效+不存在）→ 独立状态 ✅\n`);

    // Test 7: 多个不存在文件
    const multiBad = await pythonProcess.call('detect_banks', {
      filePaths: ['/a/bad1.pdf', '/a/bad2.pdf', '/a/bad3.pdf'],
    });
    assert(multiBad.success === true, 'success 应为 true');
    assert(multiBad.results.length === 3, `应返回 3 个结果`);
    assert(multiBad.results.every(r => r.status === 'failed'), '所有文件应 status=failed');
    testCount++; passCount++;
    console.log(`[${testCount}] 多个不存在文件 → 全部 failed ✅\n`);

    // Test 8: 同一文件在列表中重复出现
    const dupResult = await pythonProcess.call('detect_banks', {
      filePaths: [TEST_PDF_1, TEST_PDF_1],
    });
    assert(dupResult.success === true, 'success 应为 true');
    assert(dupResult.results.length === 2, `应返回 2 个结果，实际 ${dupResult.results.length}`);
    assert(dupResult.results[0].status === 'ok' && dupResult.results[1].status === 'ok',
      '两个结果都应 status=ok');
    testCount++; passCount++;
    console.log(`[${testCount}] 重复文件 → 各自独立检测 ✅\n`);

    console.log(`\n=== 全部 ${testCount} 个测试通过 ===`);
  } catch (error) {
    console.error('\n❌ 测试失败:', error.message);
    allPassed = false;
  } finally {
    cleanup();
    pythonProcess.stop();
    process.exit(allPassed ? 0 : 1);
  }
}

runTests();