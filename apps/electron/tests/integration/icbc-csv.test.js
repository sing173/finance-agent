// ICBC CSV 真实文件解析测试
const { pythonProcess } = require('../../dist/pythonProcessManager');
const path = require('path');

const CSV_FILE = 'C:\\Users\\dell\\Desktop\\finance agent\\historydetail0.csv';

async function main() {
  console.log('=== ICBC CSV 真实文件解析测试 ===\n');

  await pythonProcess.start();
  await new Promise(r => setTimeout(r, 1000));

  // Test 1: parse_csv (direct)
  console.log('[1/2] 测试 parse_csv 方法（直接解析 ICBC CSV）...');
  try {
    const result = await pythonProcess.call('parse_csv', { file_path: CSV_FILE });
    if (result.success) {
      console.log(`  ✅ 解析成功`);
      console.log(`     银行: ${result.bank}`);
      console.log(`     交易数: ${result.transactions?.length || 0}`);
      console.log(`     期初余额: ${result.opening_balance}`);
      console.log(`     期末余额: ${result.closing_balance}`);
      if (result.transactions?.length > 0) {
        console.log(`     首笔交易: ${result.transactions[0].date} ${result.transactions[0].description} ${result.transactions[0].amount}`);
        console.log(`     末笔交易: ${result.transactions[result.transactions.length - 1].date} ${result.transactions[result.transactions.length - 1].description} ${result.transactions[result.transactions.length - 1].amount}`);
      }
      if (result.errors?.length) console.log(`     错误: ${result.errors.join(', ')}`);
      if (result.warnings?.length) console.log(`     警告: ${result.warnings.join(', ')}`);
    } else {
      console.error(`  ❌ 解析失败: ${result.error}`);
    }
  } catch (err) {
    console.error(`  ❌ 异常:`, err.message);
  }

  // Test 2: parse_pdf (auto-route by extension)
  console.log('\n[2/2] 测试 parse_pdf 方法（自动路由到 CSV 解析器）...');
  try {
    const result = await pythonProcess.call('parse_pdf', { file_path: CSV_FILE });
    if (result.success) {
      console.log(`  ✅ 解析成功（自动路由）`);
      console.log(`     银行: ${result.bank}`);
      console.log(`     交易数: ${result.transactions?.length || 0}`);
    } else {
      console.error(`  ❌ 解析失败: ${result.error}`);
    }
  } catch (err) {
    console.error(`  ❌ 异常:`, err.message);
  }

  pythonProcess.stop();
  console.log('\n✨ CSV 解析测试完成！');
}

main().catch(err => { console.error(err); process.exit(1); });
