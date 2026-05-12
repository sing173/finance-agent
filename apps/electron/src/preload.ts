import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  health: () => ipcRenderer.invoke('health'),
  parsePDF: (path: string) => ipcRenderer.invoke('parse_pdf', { file_path: path }),
  parsePdf: (params: any) => ipcRenderer.invoke('parse_pdf', params),
  generateExcel: (params: any) => ipcRenderer.invoke('generate_excel', params),
  generateVoucher: (params: any) => ipcRenderer.invoke('generate_voucher_excel', params),
  chat: (msg: string, sessionKey?: string) =>
    ipcRenderer.invoke('chat', { message: msg, session_key: sessionKey }),
  selectFile: (filter: string) => ipcRenderer.invoke('select_file', { filter }),
  saveFileDialog: (params?: any) => ipcRenderer.invoke('save_file_dialog', params),

  // 监听 Python 进程状态变化
  onPythonStatus: (callback: (status: string) => void) => {
    ipcRenderer.on('python-status', (event, status) => callback(status));
  },

  // 主动查询 Python 进程状态
  getPythonStatus: () => ipcRenderer.invoke('get-python-status'),
});

