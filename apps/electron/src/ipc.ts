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
  { channel: 'parse_pdf',               method: 'parse_pdf',           expose: true  },
  { channel: 'generate_excel',          method: 'generate_excel',      expose: true  },
  { channel: 'import_subjects',         method: 'import_subjects',     expose: true  },
  { channel: 'get_subjects_info',       method: 'get_subjects_info',   expose: true  },
  { channel: 'detect_banks',            method: 'detect_banks',        expose: true  },
  { channel: 'detect_supported_banks',  method: 'detect_supported_banks', expose: true },

  // Issue #29: FR-1 账号-科目管理
  { channel: 'account_registry.list',    method: 'account_registry.list',    expose: true },
  { channel: 'account_registry.match',   method: 'account_registry.match',   expose: true },
  { channel: 'account_registry.add',     method: 'account_registry.add',     expose: true },
  { channel: 'account_registry.update',  method: 'account_registry.update',  expose: true },
  { channel: 'account_registry.delete',  method: 'account_registry.delete',  expose: true },

  // Issue #34-#36: 凭证预览 + 草稿 + 导出
  { channel: 'voucher.preview',          method: 'voucher.preview',          expose: true },
  { channel: 'voucher.save_draft',       method: 'voucher.save_draft',       expose: true },
  { channel: 'voucher.load_draft',       method: 'voucher.load_draft',       expose: true },
  { channel: 'voucher.list_drafts',      method: 'voucher.list_drafts',      expose: true },
  { channel: 'voucher.delete_draft',     method: 'voucher.delete_draft',     expose: true },
  { channel: 'voucher.export',           method: 'voucher.export',           expose: true },

  // db.health — 数据库状态检查
  { channel: 'db.health',                method: 'db.health',                expose: true },

  // Electron-side (no Python backend)
  { channel: 'select_file',             method: null,                  expose: true  },
  { channel: 'save_file_dialog',        method: null,                  expose: true  },

  // Internal / health-check only (not exposed to renderer)
  { channel: 'get-python-status',       method: null,                  expose: false },
];


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


