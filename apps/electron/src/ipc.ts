import { pythonProcess } from './pythonProcessManager';

// 主进程 IPC 处理器注册
// 延迟到 app.whenReady() 之后执行，确保 Electron 模块系统已就绪
export function setupIpcHandlers() {
  // 此时 require('electron') 已被 Electron 重写为正确的模块
  const { ipcMain, app, dialog, BrowserWindow } = require('electron');
  const path = require('path');

  ipcMain.handle('health', async () => {
    return pythonProcess.call('health', {});
  });

  ipcMain.handle('get-python-status', async () => {
    return pythonProcess.isAlive() ? 'online' : 'offline';
  });

  // 打开文件选择对话框，返回绝对路径
  ipcMain.handle('select_file', async (event: any, params: any) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win) return null;

    const { filePaths } = await dialog.showOpenDialog(win, {
      properties: ['openFile'],
      filters: [
        { name: 'PDF Files', extensions: ['pdf'] },
        { name: 'Excel Files', extensions: ['xlsx', 'xls'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });

    if (filePaths.length > 0) {
      return filePaths[0]; // 返回第一个选中文件的绝对路径
    }
    return null;
  });

  ipcMain.handle('parse_pdf', async (event: any, params: any) => {
    // 如果传入的是相对路径或文件名，尝试解析为绝对路径
    if (params.file_path && !path.isAbsolute(params.file_path)) {
      const absolutePath = path.resolve(params.file_path);
      params.file_path = absolutePath;
    }
    return pythonProcess.call('parse_pdf', params);
  });

  ipcMain.handle('get_file_path', async (event: any, params: any) => {
    // 由渲染进程传递 File 对象的路径，返回绝对路径
    const { app } = require('electron');
    const filePath = params.path;
    if (filePath && path.isAbsolute(filePath)) {
      return filePath;
    }
    // 返回相对路径的绝对版本
    return path.resolve(filePath || '');
  });

  ipcMain.handle('generate_excel', async (event: any, params: any) => {
    return pythonProcess.call('generate_excel', params);
  });

  // 应用退出时清理
  app.on('before-quit', () => {
    // 可扩展：清理 IPC 处理器
  });

  // TODO: 后续添加 chat 等处理器
}
