import { app, BrowserWindow, ipcMain } from 'electron';
import * as path from 'path';
import { pythonProcess } from './pythonProcessManager';
import { setupIpcHandlers } from './ipc';

let mainWindow: BrowserWindow | null = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.resolve(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // 开发模式：Electron 启动时 process.defaultApp 为 true
  const isDev = (process as any).defaultApp;
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    // 打包模式：resources/renderer/index.html (extraResources 已拷贝 dist/ 内容)
    const rendererPath = path.join((process as any).resourcesPath || __dirname, 'renderer', 'index.html');
    mainWindow.loadFile(rendererPath);
  }
}

// Electron 就绪后初始化
app.whenReady().then(() => {
  pythonProcess.start();  // 启动 Python 后端
  setupIpcHandlers();    // 注册 IPC 处理器
  createWindow();        // 创建窗口

  // 转发 Python 状态事件到渲染进程（窗口已创建后才注册，避免丢失事件）
  pythonProcess.on('status', (status: string) => {
    mainWindow?.webContents.send('python-status', status);
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on('before-quit', () => {
  // 只在进程存在时停止，避免重复操作已销毁对象
  if (pythonProcess.isAlive()) {
    pythonProcess.stop();
  }
});
