/**
 * detect_banks 批量检测集成测试
 * 测试 Python 后端 detect_banks / detect_supported_banks 方法
 */
const { pythonProcess } = require('../../dist/pythonProcessManager');
const path = require('path');

const OUTPUT_DIR = path.resolve(__dirname, 'output');

function cleanup() {
  const fs = require('fs');
  if (fs.existsSync(OUTPUT_DIR)) {
    const files = fs.readdirSync(OUTPUT_DIR);
    for (const file of files) {
      if (file.startsWith('test_') || file.startsWith('temp_')) {
        fs.unlinkSync(path.join(OUTPUT_DIR, file));
      }
    }
  }
}

async function runTests() {
  console.log('=== detect_banks / detect_supported_banks 集成测试 ===\n');
  let allPassed = true;

  try {
    cleanup();
    console.log('[1/3] 启动 Python 后端...');
    await pythonProcess.start();
    await new Promise(r => setTimeout(r, 1000));
    console.log('✅ 进程启动完成\n');

    // Test 1: detect_supported_banks
    console.log('[2/3] 测试 detect_supported_banks...');
    const banksResult = await pythonProcess.call('detect_supported_banks', {});
    if (banksResult.success && Array.isArray(banksResult.banks)) {
      console.log(`  支持银行: ${banksResult.banks.join(', ')}`);
      if (banksResult.banks.length >= 3) {
        console.log('✅ detect_supported_banks 通过\n');
      } else {
        throw new Error('银行列表数量不足');
      }
    } else {
      throw new Error('detect_supported_banks 返回异常: ' + JSON.stringify(banksResult));
    }

    // Test 2: detect_banks with empty list
    console.log('[3/3] 测试 detect_banks（空列表）...');
    const emptyResult = await pythonProcess.call('detect_banks', { file_paths: [] });
    if (emptyResult.success && Array.isArray(emptyResult.results) && emptyResult.results.length === 0) {
      console.log('  空列表返回空结果 ✅');
    } else {
      throw new Error('detect_banks 空列表测试失败: ' + JSON.stringify(emptyResult));
    }

    // Test 3: detect_banks with nonexistent file
    console.log('[3b/3] 测试 detect_banks（不存在的文件）...');
    const badResult = await pythonProcess.call('detect_banks', { file_paths: ['/nonexistent/file.pdf'] });
    if (badResult.success && badResult.results[0]?.status === 'failed') {
      console.log('  不存在的文件返回 status=failed ✅');
    } else {
      throw new Error('detect_banks 异常文件测试失败: ' + JSON.stringify(badResult));
    }

    console.log('\n=== 所有测试通过 ===');
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
