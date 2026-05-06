import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import { getPythonSpawnConfig } from './pathUtils';

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
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    this.process.stdout?.on('data', (chunk: Buffer) => {
      this.handleStdout(chunk.toString());
    });

    this.process.stderr?.on('data', (chunk: Buffer) => {
      console.error('[Python]', chunk.toString().trim());
    });

    this.process.on('exit', (code: number | null, signal: string | null) => {
      console.log(`[Python] Process exited: code=${code}, signal=${signal}`);
      this.process = null;
      this.emit('status', 'offline');
    });

    this.process.on('error', (err: Error) => {
      console.error('[Python] Process error:', err.message);
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

    this.process.stdin!.write(JSON.stringify(request) + '\n');

    return Promise.race([
      promise,
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('请求超时（10s）')), 10000)
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
    this.process?.kill();
    this.process = null;
    this.emit('status', 'offline');
  }
}

export const pythonProcess = new PythonProcessManager();
