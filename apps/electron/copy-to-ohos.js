const fs = require('fs');
const path = require('path');

// 原项目 JS 源文件目录（已去掉 TS，直接用 JS）
const srcDir = path.join(__dirname, 'src');

// 鸿蒙项目 app 目录
const ohosAppDir = path.join(__dirname, '..', '..', 'finance-assistant-ohos', 'web_engine', 'src', 'main', 'resources', 'resfile', 'resources', 'app');

// 需要复制的 JS 文件
const filesToCopy = ['main.js', 'ipc.js', 'preload.js', 'pythonProcessManager.js'];

console.log('[copy-to-ohos] 复制 JS 源码到鸿蒙项目...');
console.log('[copy-to-ohos] 源目录:', srcDir);
console.log('[copy-to-ohos] 目标目录:', ohosAppDir);

if (!fs.existsSync(ohosAppDir)) {
  console.error('[copy-to-ohos] 错误：鸿蒙项目目录不存在：', ohosAppDir);
  process.exit(1);
}

for (const file of filesToCopy) {
  const srcPath = path.join(srcDir, file);
  const destPath = path.join(ohosAppDir, file);
  if (!fs.existsSync(srcPath)) {
    console.warn('[copy-to-ohos] 警告：源文件不存在，跳过：', srcPath);
    continue;
  }
  fs.copyFileSync(srcPath, destPath);
  console.log('[copy-to-ohos] ✓ 已复制：', file);
}

console.log('[copy-to-ohos] 完成！');
