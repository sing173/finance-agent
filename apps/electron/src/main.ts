import { app, BrowserWindow, ipcMain } from 'electron';
import * as path from 'path';

// 在Electron CommonJS环境中，使用全局的__dirname
declare const __dirname: string;

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

  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    // __dirname = apps/electron/dist/ (编译后的目录)
    // 路径: dist/ -> .. -> electron/ -> .. -> 项目根目录 -> renderer/dist/
    // 即: ../../renderer/dist/
    mainWindow.loadFile(path.resolve(__dirname, '../../renderer/dist/index.html'));
  }
}

import { registerHandlers } from './ipc';
import { pythonProcess } from './pythonProcessManager';

registerHandlers();
pythonProcess.start();

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on('before-quit', () => {
  pythonProcess.stop();
});
