import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  health: () => ipcRenderer.invoke('health'),
  reconcile: (params: any) => ipcRenderer.invoke('reconcile', params),
  parsePDF: (path: string) => ipcRenderer.invoke('parse_pdf', { file_path: path }),
  chat: (msg: string, sessionKey?: string) =>
    ipcRenderer.invoke('chat', { message: msg, session_key: sessionKey }),

  // 监听 Python 进程状态变化
  onPythonStatus: (callback: (status: string) => void) => {
    ipcRenderer.on('python-status', (event, status) => callback(status));
  },

  // 主动查询 Python 进程状态
  getPythonStatus: () => ipcRenderer.invoke('get-python-status'),
});
