import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import * as path from 'path';
import * as fs from 'fs';

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
  if (process.env.PYTHON_CMD) {
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

  async start(): Promise<void> {
    if (this.process) return;

    const pythonConfig = getPythonSpawnConfig();
    console.log(`[Python] Starting: ${pythonConfig.cmd} ${pythonConfig.args.join(' ')}`);

    this.process = spawn(pythonConfig.cmd, pythonConfig.args, {
      cwd: pythonConfig.cwd,
      env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    this.process.stdout?.on('data', (chunk: Buffer) => {
      this.handleStdout(chunk.toString('utf-8'));
    });

    this.process.stderr?.on('data', (chunk: Buffer) => {
      console.error('[Python]', chunk.toString('utf-8').trim());
    });

    // 用局部变量捕获当前进程，避免 exit 时 this.process 已被置空
    const proc = this.process;
    proc.on('exit', (code: number | null, signal: string | null) => {
      console.log(`[Python] Process exited: code=${code}, signal=${signal}`);
      // 只在进程还存在时清理（防止重复）
      if (this.process === proc) {
        this.process = null;
      }
      this.emit('status', 'offline');
    });

    this.process.on('error', (err: Error) => {
      console.error('[Python] Process error:', err.message);
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
