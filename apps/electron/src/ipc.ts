import { ipcMain } from 'electron';
import { pythonProcess } from './pythonProcessManager';

export function registerHandlers() {
  ipcMain.handle('health', async () => {
    return pythonProcess.call('health', {});
  });

  // TODO: 后续添加 parse_pdf, reconcile, chat 等处理器
}
