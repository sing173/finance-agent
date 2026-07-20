import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import * as path from 'path';
import * as fs from 'fs';
import { dialog } from 'electron';

function getResourcesPath(): string | undefined {
  try {
    return (process as any).resourcesPath;
  } catch {
    return undefined;
  }
}

function isElectronPackaged(): boolean {
  try {
    const { app } = require('electron');
    return app.isPackaged === true;
  } catch {
    return false;
  }
}

function getPythonSpawnConfig(): { cmd: string; args: string[]; cwd: string } {
  // HarmonyOS HNP 模式：通过 HNP 执行 Python 后端
  // HNP 安装路径格式：/data/app/{hnp-name}.org/{hnp-name}_{version}/
  if (
    (process.platform as string) === 'ohos' ||
    (process.platform as string) === 'openharmony' ||
    process.env.OHOS_HNP_MODE === '1'
  ) {
    const HNP_NAME    = 'finance-agent-backend';
    const HNP_VERSION = '1.0';
    const hnpHome     = `/data/app/${HNP_NAME}.org/${HNP_NAME}_${HNP_VERSION}`;
    const pythonPath   = `${hnpHome}/bin/python3`;
    const sitePackages = `${hnpHome}/lib/python3.12/site-packages`;

    console.log('[PathUtils] HarmonyOS HNP mode, using:', pythonPath);
    return {
      cmd: pythonPath,
      args: ['-m', 'finance_agent_backend.bridge'],
      cwd: sitePackages,
    };
  }

  if (process.env.PYTHON_CMD) {
    // validate explicit path when provided
    if (!fs.existsSync(process.env.PYTHON_CMD)) {
      const msg = `PYTHON_CMD is set but executable not found: ${process.env.PYTHON_CMD}`;
      console.error(`[PathUtils] ${msg}`);
      throw new Error(msg);
    }
    const scriptPath = path.resolve(__dirname, '..', '..', 'python', 'src', 'finance_agent_backend', 'bridge.py');
    return { cmd: process.env.PYTHON_CMD, args: [scriptPath], cwd: path.dirname(scriptPath) };
  }
  if (isElectronPackaged()) {
    const resourcesPath = getResourcesPath();
    if (resourcesPath) {
      const ext = process.platform === 'win32' ? '.exe' : '';
      const exePath = path.join(resourcesPath, 'python', 'bridge' + ext);
      if (!fs.existsSync(exePath)) {
        console.error(`[PathUtils] bridge executable not found: ${exePath}`);
        throw new Error(`bridge executable not found: ${exePath}`);
      }
      console.log('[PathUtils] Packaged mode, using:', exePath);
      return { cmd: exePath, args: [], cwd: path.dirname(exePath) };
    }
    console.warn('[PathUtils] Packaged mode but resourcesPath unavailable, falling back to dev mode');
  }
  const isWindows = process.platform === 'win32';
  const venvBinDir = isWindows ? 'Scripts' : 'bin';
  const pythonExe = isWindows ? 'python.exe' : 'python3';
  const venvPython = path.resolve(__dirname, '..', '..', 'python', '.venv', venvBinDir, pythonExe);
  if (!fs.existsSync(venvPython)) {
    const msg = `venv Python not found: ${venvPython}. Set PYTHON_CMD env var or create the virtualenv.`;
    console.error(`[PathUtils] ${msg}`);
    throw new Error(msg);
  }
  const scriptPath = path.resolve(__dirname, '..', '..', 'python', 'src', 'finance_agent_backend', 'bridge.py');
  console.log('[PathUtils] Dev mode, using:', venvPython, scriptPath);
  return { cmd: venvPython, args: [scriptPath], cwd: path.dirname(scriptPath) };
}

export class PythonProcessManager extends EventEmitter {
  private process: ChildProcess | null = null;
  private pendingRequests = new Map<number, {
    resolve: (value: any) => void;
    reject: (error: any) => void;
  }>();
  private requestId = 0;
  private stdoutBuffer = '';
  private stopping = false; // 是否为主动停止（如点击菜单 Quit），用于退出时是否弹错误框

  constructor() {
    super();
  }

  async start(): Promise<void> {
    if (this.process) return;

    const pythonConfig = getPythonSpawnConfig();
    console.log(`[Python] Starting: ${pythonConfig.cmd} ${pythonConfig.args.join(' ')}`);

    // HarmonyOS HNP 模式需要设置 PYTHONHOME/PYTHONPATH 让 Python 找到标准库
    const isHarmonyOS = (process.platform as string) === 'ohos' || (process.platform as string) === 'openharmony' || process.env.OHOS_HNP_MODE === '1';
    const env: NodeJS.ProcessEnv = { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' };
    if (isHarmonyOS) {
      const HNP_NAME    = 'finance-agent-backend';
      const HNP_VERSION = '1.0';
      const hnpHome     = `/data/app/${HNP_NAME}.org/${HNP_NAME}_${HNP_VERSION}`;
      env.PYTHONHOME = hnpHome;
      env.PYTHONPATH = [
        `${hnpHome}/lib/python3.12`,
        `${hnpHome}/lib/python3.12/lib-dynload`,
        `${hnpHome}/lib/python3.12/site-packages`,
      ].join(':');
      // LD_LIBRARY_PATH：让 Python 的 _sqlite3 模块能找到 libsqlite3.so.0
      env.LD_LIBRARY_PATH = `${hnpHome}/lib:${process.env.LD_LIBRARY_PATH || ''}`;
      // 告诉 Python 进程当前在 HNP 模式下运行
      env.OHOS_HNP_MODE = '1';
      // 应用沙箱目录（HarmonyOS）
      // Electron 应用的 bundleName 是 com.zungen.financeassistant
      // 必须使用沙箱虚拟路径（/data/storage/...），不能用物理路径（/data/app/...）
      // 物理路径：/data/app/el2/100/base/com.zungen.financeassistant/
      // 虚拟路径：/data/storage/el2/base/com.zungen.financeassistant/  ← Python 进程用这个
      env.APP_SANDBOX_DIR = '/data/storage/el2/base/com.zungen.financeassistant';
      // TMPDIR：让 openpyxl 等库能创建临时文件
      env.TMPDIR = `${env.APP_SANDBOX_DIR}/temp`;
      // LOG_DIR：Python 侧优先读此环境变量
      env.LOG_DIR = `${env.APP_SANDBOX_DIR}/files/logs`;
      console.log('[Python] HNP mode, PYTHONHOME:', env.PYTHONHOME, 'SANDBOX:', env.APP_SANDBOX_DIR);

      // 确保应用沙箱目录存在（HarmonyOS 可能不会自动创建 files/ 等目录）
      // 必须在 spawn Python 之前创建，否则 sqlite3.connect() 会因父目录不存在而失败
      // 注意：必须使用虚拟路径（/data/storage/...），不能用物理路径（/data/app/...）
      const sandboxVirtual = env.APP_SANDBOX_DIR;  // /data/storage/el2/base/com.zungen.financeassistant
      const dirsToCreate = [
        `${sandboxVirtual}/files`,
        `${sandboxVirtual}/temp`,
        `${sandboxVirtual}/files/logs`,
      ];
      for (const dir of dirsToCreate) {
        try {
          fs.mkdirSync(dir, { recursive: true });
          console.log('[Python] Sandbox dir ready:', dir);
        } catch (e: any) {
          console.warn('[Python] Cannot create sandbox dir:', dir, e.message);
        }
      }
    }

    this.process = spawn(pythonConfig.cmd, pythonConfig.args, {
      cwd: pythonConfig.cwd,
      env: env,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    // stdout：处理 JSON-RPC 响应
    this.process.stdout?.on('data', (chunk: Buffer) => {
      this.handleStdout(chunk.toString('utf-8'));
    });

    // stderr：收集错误输出，仅在开发期异常退出时弹框显示（生产环境不弹）
    let stderrBuf = '';
    this.process.stderr?.on('data', (chunk: Buffer) => {
      const text = chunk.toString('utf-8');
      stderrBuf += text;
      console.error('[Python] stderr:', text.trim());
    });

    // 用局部变量捕获当前进程，避免 exit 时 this.process 已被置空
    const proc = this.process;
    proc.on('exit', (code: number | null, signal: string | null) => {
      const msg = `Process exited: code=${code}, signal=${signal}`;
      console.log('[Python] ' + msg);
      // 生产环境（已打包）不向终端用户弹窗：原始 stderr 含内部路径/日志，对最终用户无意义且可能泄露信息。
      // 仅开发期（未打包）弹窗便于调试；异常/正常退出信息均经 console 落日志，便于事后排查。
      const devMode = !isElectronPackaged();
      if (!this.stopping && stderrBuf && devMode) {
        dialog.showErrorBox('Python Process Exited', msg + '\n\nstderr:\n' + stderrBuf.slice(0, 2000));
      }
      this.stopping = false; // 重置标记
      // 只在进程还存在时清理（防止重复）
      if (this.process === proc) {
        this.process = null;
      }
      this.emit('status', 'offline');
    });

    this.process.on('error', (err: Error) => {
      console.error('[Python] Process error:', err.message);
      // 生产环境不弹原生对话框，仅落日志 + 通知前端状态（避免向终端用户暴露原始错误）
      if (!isElectronPackaged()) {
        dialog.showErrorBox('Python Spawn Error', err.message);
      }
      this.process = null;
      this.emit('status', 'error', err.message);
    });

    this.emit('status', 'online');
  }

  async call(method: string, params: object = {}): Promise<any> {
    if (!this.process) {
      throw new Error('Python process not started');
    }

    const id = ++this.requestId;
    const request = { jsonrpc: '2.0' as const, id, method, params };

    const promise = new Promise<any>((resolve, reject) => {
      this.pendingRequests.set(id, { resolve, reject });
    });

    this.process.stdin!.write(JSON.stringify(request) + '\n', 'utf-8');

    return Promise.race([
      promise,
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('请求超时（60s）')), 60000)
      ),
    ]);
  }

  private handleStdout(chunk: string): void {
    this.stdoutBuffer += chunk;
    const lines = this.stdoutBuffer.split('\n');
    this.stdoutBuffer = lines.pop() || '';

    for (const line of lines) {
      if (line.trim()) {
        try {
          const response = JSON.parse(line);
          this.handleResponse(response);
        } catch {
          // 忽略非 JSON 输出
        }
      }
    }
  }

  private handleResponse(response: any): void {
    const { id, result, error } = response;
    const pending = this.pendingRequests.get(id);
    if (pending) {
      if (error) {
        pending.reject(new Error(error.message));
      } else {
        pending.resolve(result);
      }
      this.pendingRequests.delete(id);
    }
  }

  stop(): void {
    if (this.process && !this.process.killed) {
      const proc = this.process;
      this.stopping = true; // 标记为主动停止，退出时不再弹错误框
      this.process = null; // 立即置空，防止重复调用
      try {
        proc.kill();
      } catch (e) {
        // 忽略已销毁对象的错误
      }
      this.emit('status', 'offline');
    }
  }

  isAlive(): boolean {
    return this.process !== null && !this.process.killed;
  }
}

export const pythonProcess = new PythonProcessManager();
