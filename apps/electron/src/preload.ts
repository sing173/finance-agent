import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  health: () => ipcRenderer.invoke('health'),
  reconcile: (params: any) => ipcRenderer.invoke('reconcile', params),
  parsePDF: (path: string) => ipcRenderer.invoke('parse_pdf', { file_path: path }),
  chat: (msg: string, sessionKey?: string) =>
    ipcRenderer.invoke('chat', { message: msg, session_key: sessionKey }),

  // 新增：parse_pdf, reconcile, generate_excel
  parsePdf: (params: any) => ipcRenderer.invoke('parse_pdf', params),
  reconcile: (params: any) => ipcRenderer.invoke('reconcile', params),
  generateExcel: (params: any) => ipcRenderer.invoke('generate_excel', params),

  // 监听 Python 进程状态变化
  onPythonStatus: (callback: (status: string) => void) => {
    ipcRenderer.on('python-status', (event, status) => callback(status));
  },

  // 主动查询 Python 进程状态
  getPythonStatus: () => ipcRenderer.invoke('get-python-status'),
});
