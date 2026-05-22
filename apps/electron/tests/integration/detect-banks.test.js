/**
 * detect_banks / detect_supported_banks 集成测试
 *
 * 覆盖：成功场景 + 失败场景 + 边界情况
 *
 * 前置条件：
 *   - apps/python/.venv 已创建且依赖已安装
 *   - apps/electron/dist/ 已编译（tsc 零错误）
 *   - 真实测试 PDF 位于 C:\Users\dell\Desktop\finance agent
 *
 * 运行：node tests/integration/detect-banks.test.js
 */
const { pythonProcess } = require('../../dist/pythonProcessManager');
const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = path.resolve(__dirname, 'output');

// ---------- 真实测试文件（与 Python 测试一致） ----------

const REAL_FILES = {
  cmb_pdf: path.join('C:\\Users\\dell\\Desktop\\finance agent', 'cmb-03.pdf'),
  gfb_pdf: path.join('C:\\Users\\dell\\Desktop\\finance agent', '广发.pdf'),
  icbc_csv: path.join('C:\\Users\\dell\\Desktop\\finance agent', 'historydetail0.csv'),
};

// ---------- 工具 ----------

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function cleanup() {
  console.log('\n[Cleanup] 清理临时文件...');
  console.log('  ✓ 无需清理');
}

function assert(cond, msg) {
  if (!cond) throw new Error('断言失败: ' + msg);
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
    // 启动后端
    console.log('[Boot] 启动 Python 后端...');
    await pythonProcess.start();
    await new Promise(r => setTimeout(r, 1500));
    console.log('  ✓ 进程启动完成\n');

    // ═══ 失败场景 + 边界测试 ═══

    // Test 1: detect_supported_banks（回归）
    test('detect_supported_banks 返回银行列表', () => {});
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

    // Test 4: 有效 PDF 检测成功（CMB 真实文件）
    const okResult = await pythonProcess.call('detect_banks', { filePaths: [REAL_FILES.cmb_pdf] });
    assert(okResult.success === true, 'success 应为 true');
    assert(okResult.results.length === 1, `应返回 1 个结果，实际 ${okResult.results.length}`);
    assert(okResult.results[0].status === 'ok', `有效 PDF 应 status=ok，实际 ${okResult.results[0].status}`);
    assert(okResult.results[0].bank, '应返回 bank 字段');
    assert(okResult.results[0].docType, '应返回 docType 字段');
    console.log(`  检测到: ${okResult.results[0].bank} · ${okResult.results[0].docType}`);
    testCount++; passCount++;
    console.log(`[${testCount}] 有效 PDF（CMB）→ status=ok ✅\n`);

    // Test 5: 有效 PDF 检测成功（GFB 真实文件）
    const okResult2 = await pythonProcess.call('detect_banks', { filePaths: [REAL_FILES.gfb_pdf] });
    assert(okResult2.success === true, 'success 应为 true');
    assert(okResult2.results[0].status === 'ok', '有效 PDF 应 status=ok');
    assert(okResult2.results[0].bank, '应返回 bank 字段');
    console.log(`  检测到: ${okResult2.results[0].bank} · ${okResult2.results[0].docType}`);
    testCount++; passCount++;
    console.log(`[${testCount}] 有效 PDF（GFB）→ status=ok ✅\n`);

    // Test 6: 混合列表 — 有效 + 不存在
    const mixedResult = await pythonProcess.call('detect_banks', {
      filePaths: [REAL_FILES.cmb_pdf, '/nonexistent/ghost.pdf', REAL_FILES.gfb_pdf],
    });
    assert(mixedResult.success === true, 'success 应为 true');
    assert(mixedResult.results.length === 3, `应返回 3 个结果，实际 ${mixedResult.results.length}`);
    const okCount = mixedResult.results.filter(x => x.status === 'ok').length;
    const failCount = mixedResult.results.filter(x => x.status === 'failed').length;
    assert(okCount === 2, `应有 2 个 ok，实际 ${okCount}`);
    assert(failCount === 1, `应有 1 个 failed，实际 ${failCount}`);
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

    // Test 8: 同一文件重复出现
    const dupResult = await pythonProcess.call('detect_banks', {
      filePaths: [REAL_FILES.cmb_pdf, REAL_FILES.cmb_pdf],
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
