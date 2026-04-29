import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  health: () => ipcRenderer.invoke('health'),
  reconcile: (params: any) => ipcRenderer.invoke('reconcile', params),
  parsePDF: (path: string) => ipcRenderer.invoke('parse_pdf', { file_path: path }),
  chat: (msg: string, sessionKey?: string) =>
    ipcRenderer.invoke('chat', { message: msg, session_key: sessionKey }),
});
