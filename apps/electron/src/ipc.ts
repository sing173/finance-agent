import { pythonProcess } from './pythonProcessManager';

// 主进程 IPC 处理器注册
// 延迟到 app.whenReady() 之后执行，确保 Electron 模块系统已就绪
export function setupIpcHandlers() {
  // 此时 require('electron') 已被 Electron 重写为正确的模块
  const { ipcMain, app } = require('electron');

  ipcMain.handle('health', async () => {
    return pythonProcess.call('health', {});
  });

  ipcMain.handle('get-python-status', async () => {
    return pythonProcess.isAlive() ? 'online' : 'offline';
  });

  // 应用退出时清理
  app.on('before-quit', () => {
    // 可扩展：清理 IPC 处理器
  });

  // TODO: 后续添加 parse_pdf, reconcile, chat 等处理器
}
