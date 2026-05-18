import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  health: () => ipcRenderer.invoke('health'),
  parsePDF: (path: string) => ipcRenderer.invoke('parse_pdf', { file_path: path }),
  parsePdf: (params: any) => ipcRenderer.invoke('parse_pdf', params),
  generateExcel: (params: any) => ipcRenderer.invoke('generate_excel', params),
  generateVoucher: (params: any) => ipcRenderer.invoke('generate_voucher_excel', params),
  importSubjects: (params: any) => ipcRenderer.invoke('import_subjects', params),
  getSubjectsInfo: () => ipcRenderer.invoke('get_subjects_info', {}),
  ocrPDF: (params: any) => ipcRenderer.invoke('ocr_pdf', params),
  chat: (msg: string, sessionKey?: string) =>
    ipcRenderer.invoke('chat', { message: msg, session_key: sessionKey }),
  selectFile: (filter: string, allowMulti?: boolean) => ipcRenderer.invoke('select_file', { filter, allowMulti: !!allowMulti }),
  saveFileDialog: (params?: any) => ipcRenderer.invoke('save_file_dialog', params),

  // 监听 Python 进程状态变化
  onPythonStatus: (callback: (status: string) => void) => {
    ipcRenderer.on('python-status', (event, status) => callback(status));
  },

  // 主动查询 Python 进程状态
  getPythonStatus: () => ipcRenderer.invoke('get-python-status'),

  // ========== 文件上传方案新增 RPC ==========

  detectBanks: (filePaths: string[]) => ipcRenderer.invoke('detect-banks', { file_paths: filePaths }),
  detectSupportedBanks: () => ipcRenderer.invoke('detect-supported-banks'),
});

