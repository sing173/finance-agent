import { app, BrowserWindow, ipcMain } from 'electron';
import * as path from 'path';

let mainWindow: BrowserWindow | null = null;

function getDirname(): string {
  // 使用 __dirname 的兼容写法（tsconfig 使用 CommonJS 时）
  return path.dirname(require.main?.filename || '');
}

function createWindow() {
  const __dirname = getDirname();
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/dist/index.html'));
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
