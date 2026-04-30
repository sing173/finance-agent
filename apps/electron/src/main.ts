import { app, BrowserWindow } from 'electron';
import * as path from 'path';
import { pythonProcess } from './pythonProcessManager';
import { setupIpcHandlers } from './ipc';

let mainWindow = null;

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

  // 开发模式判断：优先使用 defaultApp（Electron 开发标志），其次检查 NODE_ENV
  const isDev = (process as any).defaultApp || process.env.NODE_ENV === 'development';
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    // 打包模式：resources/renderer/dist/index.html
    const rendererPath = path.join(process.resourcesPath || __dirname, 'renderer', 'dist', 'index.html');
    mainWindow.loadFile(rendererPath);
  }
}

// 启动 Python 后端
pythonProcess.start();

// Electron 就绪后初始化
app.whenReady().then(() => {
  setupIpcHandlers();  // 注册 IPC 处理器
  createWindow();      // 创建窗口
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on('before-quit', () => {
  pythonProcess.stop();
});
