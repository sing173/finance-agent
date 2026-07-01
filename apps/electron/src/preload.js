const { contextBridge, ipcRenderer, webUtils } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  parseFile: (params) => ipcRenderer.invoke('parse_pdf', params),
  generateExcel: (params) => ipcRenderer.invoke('generate_excel', params),
  importSubjects: (params) => ipcRenderer.invoke('import_subjects', params),
  getSubjectsInfo: () => ipcRenderer.invoke('get_subjects_info', {}),
  selectFile: (filter, allowMulti) => ipcRenderer.invoke('select_file', { filter, allowMulti: !!allowMulti }),
  saveFileDialog: (params) => ipcRenderer.invoke('save_file_dialog', params),

  // 拖拽文件 → 获取真实路径
  getFilePath: (file) => {
    if (!file || !webUtils) return '';
    return webUtils.getPathForFile(file);
  },

  // 监听 Python 进程状态变化
  onPythonStatus: (callback) => {
    ipcRenderer.on('python-status', (event, status) => callback(status));
  },

  // 主动查询 Python 进程状态
  getPythonStatus: () => ipcRenderer.invoke('get-python-status'),

  // ========== 文件上传方案新增 RPC ==========

  detectBanks: (filePaths) => ipcRenderer.invoke('detect_banks', { filePaths }),
  detectSupportedBanks: () => ipcRenderer.invoke('detect_supported_banks'),

  // 通用 JSON-RPC 调用（支持 account_registry.* 等动态方法）
  invoke: (method, params) => ipcRenderer.invoke(method, params),
});
