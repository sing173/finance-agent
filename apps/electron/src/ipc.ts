import { pythonProcess } from './pythonProcessManager';
import { ipcMain, app, dialog, BrowserWindow } from 'electron';

// ═══════════════════════════════════════════════════════════════════
// Declarative IPC handler registry
// Single source of truth for RPC methods — drives both ipcMain registration
// and preload.ts type declarations.
// ═══════════════════════════════════════════════════════════════════

interface HandlerDef {
  /** IPC channel name (also used as JSON-RPC method in bridge.py) */
  channel: string;
  /** JSON-RPC method name in bridge.py (null = pure Electron-side handler) */
  method: string | null;
  /** Exposed in preload.ts → renderer? */
  expose: boolean;
}

// All registered handlers. Pure Python-call handlers use `method`, Electron-only
// handlers use method=null and provide their own implementation inline.
const HANDLERS: HandlerDef[] = [
  // Pure Python delegation
  { channel: 'health',                  method: 'health',             expose: true  },
  { channel: 'parse_pdf',               method: 'parse_pdf',           expose: true  },
  { channel: 'generate_excel',          method: 'generate_excel',      expose: true  },
  { channel: 'generate_voucher_excel',  method: 'generate_voucher_excel', expose: true },
  { channel: 'import_subjects',         method: 'import_subjects',     expose: true  },
  { channel: 'get_subjects_info',       method: 'get_subjects_info',   expose: true  },
  { channel: 'ocr_pdf',                 method: 'ocr_pdf',             expose: true  },
  { channel: 'detect_banks',            method: 'detect_banks',        expose: true  },
  { channel: 'detect_supported_banks',  method: 'detect_supported_banks', expose: true },

  // Electron-side (no Python backend)
  { channel: 'select_file',             method: null,                  expose: true  },
  { channel: 'save_file_dialog',        method: null,                  expose: true  },

  // Internal / health-check only (not exposed to renderer)
  { channel: 'get-python-status',       method: null,                  expose: false },
];

// Channels that need access to event.sender (BrowserWindow)
const EVENT_CHANNELS = new Set(['select_file', 'save_file_dialog', 'parse_pdf', 'get_file_path']);

export function setupIpcHandlers() {
  for (const h of HANDLERS) {
    if (h.method) {
      // Pure Python delegation
      ipcMain.handle(h.channel, async (_event: any, params: any) => {
        return pythonProcess.call(h.method!, params);
      });
    } else {
      // Electron-side handler — registered per-channel below
      switch (h.channel) {
        case 'select_file': {
          ipcMain.handle('select_file', async (event: any, params: any) => {
            const win = BrowserWindow.fromWebContents(event.sender);
            if (!win) return null;
            const allowMulti = params?.allowMulti || false;
            const filters = [
              { name: 'All Supported Files', extensions: ['pdf', 'csv', 'xlsx', 'xls'] },
              { name: 'PDF Files', extensions: ['pdf'] },
              { name: 'CSV Files', extensions: ['csv'] },
              { name: 'Excel Files', extensions: ['xlsx', 'xls'] },
              { name: 'All Files', extensions: ['*'] },
            ];
            const dialogOpts: any = { filters };
            if (allowMulti) dialogOpts.properties = ['openFile', 'multiSelections'];
            else dialogOpts.properties = ['openFile'];
            const { filePaths } = await dialog.showOpenDialog(win, dialogOpts);
            return allowMulti ? filePaths : filePaths[0];
          });
          break;
        }
        case 'save_file_dialog': {
          ipcMain.handle('save_file_dialog', async (event: any, params: any) => {
            const win = BrowserWindow.fromWebContents(event.sender);
            if (!win) return null;
            const { filePath } = await dialog.showSaveDialog(win, {
              title: params?.title || 'Save File',
              defaultPath: params?.defaultPath || 'voucher.xlsx',
              filters: [
                { name: 'Excel Files', extensions: ['xlsx'] },
                { name: 'All Files', extensions: ['*'] },
              ],
            });
            return filePath || null;
          });
          break;
        }
        case 'get-python-status': {
          ipcMain.handle('get-python-status', async () => {
            return pythonProcess.isAlive() ? 'online' : 'offline';
          });
          break;
        }
        // get_file_path 已移除 — 改用 path.resolve() 在渲染层处理
      }
    }
  }

  app.on('before-quit', () => {});
}

// Expose registry for preload type generation
export const EXPOSED_CHANNELS = HANDLERS.filter(h => h.expose).map(h => h.channel);

