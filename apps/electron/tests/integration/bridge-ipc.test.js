// Direct test of Python bridge connection
const { pythonProcess } = require('./dist/pythonProcessManager');

console.log('Starting Python bridge test...');

pythonProcess.start();

// Wait a bit for Python to start, then send health check
setTimeout(async () => {
  try {
    console.log('Sending health check request...');
    const result = await pythonProcess.call('health', {});
    console.log('Health check result:', JSON.stringify(result, null, 2));
    console.log('✅ IPC connection working!');
    process.exit(0);
  } catch (err) {
    console.error('❌ Health check failed:', err);
    process.exit(1);
  }
}, 2000);

// Handle errors
setTimeout(() => {
  console.error('Test timeout');
  process.exit(1);
}, 10000);
