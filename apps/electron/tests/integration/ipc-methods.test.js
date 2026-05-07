/**
 * IPC 方法完整集成测试
 * 测试 Python 后端所有 IPC 方法的请求/响应流程
 *
 * 输出文件：tests/output/ 目录
 * 临时文件：测试结束后自动清理
 */

const { pythonProcess } = require('../../dist/pythonProcessManager');
const fs = require('fs');
const path = require('path');

// 统一输出目录
const OUTPUT_DIR = path.resolve(__dirname, 'output');
const TEST_EXCEL_PATH = path.join(OUTPUT_DIR, 'test_reconcile_result.xlsx');

// 确保输出目录存在
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// 清理函数
function cleanup() {
  console.log('\n[Cleanup] 清理临时文件...');
  try {
    // 清理测试生成的 Excel 文件
    if (fs.existsSync(TEST_EXCEL_PATH)) {
      fs.unlinkSync(TEST_EXCEL_PATH);
      console.log(`  ✓ 删除: ${path.basename(TEST_EXCEL_PATH)}`);
    }
    // 清理 output 目录中的其他测试临时文件（test_* 或 temp_* 前缀）
    const files = fs.readdirSync(OUTPUT_DIR);
    for (const file of files) {
      if (file.startsWith('test_') || file.startsWith('temp_')) {
        fs.unlinkSync(path.join(OUTPUT_DIR, file));
        console.log(`  ✓ 删除: ${file}`);
      }
    }
    const remaining = fs.readdirSync(OUTPUT_DIR);
    if (remaining.length === 0) {
      console.log('  ✓ output 目录已清空');
    }
  } catch (err) {
    console.error('  ⚠ 清理失败:', err.message);
  }
}

async function runTests() {
  console.log('=== IPC 方法集成测试 ===\n');

  let allPassed = true;

  try {
    // 前置清理
    cleanup();

    // 启动 Python 进程
    console.log('[1/6] 启动 Python 后端...');
    await pythonProcess.start();
    await new Promise(r => setTimeout(r, 1000));
    console.log('✅ 进程启动完成\n');

    // Test: health
    console.log('[2/6] 测试 health 方法...');
    const health = await pythonProcess.call('health', {});
    if (health.status === 'ok' && health.version) {
      console.log(`  版本: ${health.version}`);
      console.log(`  Python: ${health.python_version.split(' ')[0]}`);
      console.log('✅ health 通过\n');
    } else {
      throw new Error('health 返回异常');
    }

    // Test: parse_pdf - 参数缺失
    console.log('[3/6] 测试 parse_pdf（参数验证）...');
    const parseErr = await pythonProcess.call('parse_pdf', {});
    if (!parseErr.success && parseErr.error.includes('file_path')) {
      console.log(`  ✅ 错误提示: "${parseErr.error}"\n`);
    } else {
      throw new Error('parse_pdf 参数验证失败');
    }

    // Test: reconcile - 文件不存在
    console.log('[4/6] 测试 reconcile（异常处理）...');
    const reconErr = await pythonProcess.call('reconcile', {
      pdf_path: 'nonexistent.pdf'
    });
    if (!reconErr.success && reconErr.error) {
      console.log(`  ✅ 错误提示: "${reconErr.error}"\n`);
    } else {
      throw new Error('reconcile 异常处理失败');
    }

    // Test: generate_excel - 正常流程
    console.log('[5/6] 测试 generate_excel（Excel 生成）...');
    const excelResult = await pythonProcess.call('generate_excel', {
      reconcile_result: {
        matched: [],
        bank_unreconciled: [],
        ledger_unreconciled: [],
        suspicious: [],
      },
      output_path: TEST_EXCEL_PATH,
    });

    if (excelResult.success && fs.existsSync(TEST_EXCEL_PATH)) {
      const stats = fs.statSync(TEST_EXCEL_PATH);
      console.log(`  ✅ Excel 生成成功: ${path.basename(TEST_EXCEL_PATH)} (${stats.size} 字节)\n`);
    } else {
      throw new Error('Excel 生成失败: ' + JSON.stringify(excelResult));
    }

    // Test: 进程状态
    console.log('[6/6] 测试进程状态管理...');
    const status = pythonProcess.isAlive();
    console.log(`  进程状态: ${status ? '运行中' : '已停止'}`);
    if (status) {
      console.log('✅ 进程状态检查通过\n');
    } else {
      throw new Error('进程意外停止');
    }

    // 总结
    console.log('=== 所有测试通过 ===');
    console.log('\n验证项：');
    console.log('  ✅ Python 进程启动');
    console.log('  ✅ health 方法');
    console.log('  ✅ parse_pdf 参数验证');
    console.log('  ✅ reconcile 异常处理');
    console.log('  ✅ generate_excel 文件生成');
    console.log('  ✅ 进程状态管理');

  } catch (error) {
    console.error('\n❌ 测试失败:', error.message);
    allPassed = false;
  } finally {
    // 清理临时文件
    cleanup();
    pythonProcess.stop();
    console.log('\n📁 输出目录:', OUTPUT_DIR);
    console.log('✨ 测试完成！');
    process.exit(allPassed ? 0 : 1);
  }
}

// 处理未捕获异常
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
