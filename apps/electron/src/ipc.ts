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
  // params.filter: 'pdf' | 'xlsx' | undefined（默认 PDF）
  ipcMain.handle('select_file', async (event: any, params: any) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win) return null;

    let filters: any;
    const f = params?.filter?.toLowerCase();

    // 默认 PDF
    filters = [
      { name: 'All Supported Files', extensions: ['pdf', 'csv', 'xlsx', 'xls'] },
      { name: 'PDF Files', extensions: ['pdf'] },
      { name: 'CSV Files', extensions: ['csv'] },
      { name: 'Excel Files', extensions: ['xlsx', 'xls'] },
      { name: 'All Files', extensions: ['*'] },
    ];

    const { filePaths } = await dialog.showOpenDialog(win, {
      properties: ['openFile'],
      filters,
    });

    if (filePaths.length > 0) {
      return filePaths[0];
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

  ipcMain.handle('generate_voucher_excel', async (event: any, params: any) => {
    return pythonProcess.call('generate_voucher_excel', params);
  });

  ipcMain.handle('import_subjects', async (event: any, params: any) => {
    return pythonProcess.call('import_subjects', params);
  });

  ipcMain.handle('get_subjects_info', async (event: any, params: any) => {
    return pythonProcess.call('get_subjects_info', params);
  });

  ipcMain.handle('ocr_pdf', async (event: any, params: any) => {
    return pythonProcess.call('ocr_pdf', params);
  });

  // 保存文件对话框：返回用户选择的保存路径，取消返回 null
  ipcMain.handle('save_file_dialog', async (event: any, params: any) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win) return null;
    const { filePath } = await dialog.showSaveDialog(win, {
      title: params?.title || '保存文件',
      defaultPath: params?.defaultPath || 'voucher.xlsx',
      filters: [
        { name: 'Excel Files', extensions: ['xlsx'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });
    return filePath || null;
  });

  // 应用退出时清理
  app.on('before-quit', () => {
    // 可扩展：清理 IPC 处理器
  });

  // TODO: 后续添加 chat 等处理器
}
