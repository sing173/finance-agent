import { contextBridge, ipcRenderer } from 'electron';
import { EXPOSED_CHANNELS } from './ipc';

// Dev-mode assertion: preload and ipc.ts registry must agree on exposed channels
console.log('[preload] script loaded');  // DEBUG
if (process.env.NODE_ENV !== 'production') {
  const defined = ['health', 'parsePDF', 'parsePdf', 'generateExcel', 'generateVoucher',
    'importSubjects', 'getSubjectsInfo', 'ocrPDF', 'selectFile', 'saveFileDialog',
    'detectBanks', 'detectSupportedBanks'];
  const missing = EXPOSED_CHANNELS.filter(c => !defined.includes(c));
  if (missing.length > 0) {
    console.warn('[preload] Channels in ipc.ts registry but missing from preload type:', missing);
  }
}

contextBridge.exposeInMainWorld('electronAPI', {
  health: () => ipcRenderer.invoke('health'),
  parsePDF: (path: string) => ipcRenderer.invoke('parse_pdf', { filePath: path }),
  parsePdf: (params: any) => ipcRenderer.invoke('parse_pdf', params),
  generateExcel: (params: any) => ipcRenderer.invoke('generate_excel', params),
  generateVoucher: (params: any) => ipcRenderer.invoke('generate_voucher_excel', params),
  importSubjects: (params: any) => ipcRenderer.invoke('import_subjects', params),
  getSubjectsInfo: () => ipcRenderer.invoke('get_subjects_info', {}),
  ocrPDF: (params: any) => ipcRenderer.invoke('ocr_pdf', params),
  selectFile: (filter: string, allowMulti?: boolean) => ipcRenderer.invoke('select_file', { filter, allowMulti: !!allowMulti }),
  saveFileDialog: (params?: any) => ipcRenderer.invoke('save_file_dialog', params),

  // 监听 Python 进程状态变化
  onPythonStatus: (callback: (status: string) => void) => {
    ipcRenderer.on('python-status', (event, status) => callback(status));
  },

  // 主动查询 Python 进程状态
  getPythonStatus: () => ipcRenderer.invoke('get-python-status'),

  // ========== 文件上传方案新增 RPC ==========

  detectBanks: (filePaths: string[]) => ipcRenderer.invoke('detect-banks', { filePaths }),
  detectSupportedBanks: () => ipcRenderer.invoke('detect-supported-banks'),
});

