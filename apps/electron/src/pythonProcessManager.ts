import { spawn } from 'child_process';
import * as path from 'path';

// Path to Python bridge: from apps/electron/dist/ -> ../../python/src/...
const PYTHON_SCRIPT = path.join(__dirname, '..', '..', 'python', 'src', 'finance_agent_backend', 'bridge.py');

// Use absolute path with forward slashes for Windows
const PYTHON_CMD = process.platform === 'win32'
  ? 'D:/Python312/python.exe'
  : 'python3';

export class PythonProcessManager {
  private process: ReturnType<typeof spawn> | null = null;
  private pendingRequests: Map<number, { resolve: Function; reject: Function }> = new Map();
  private nextId = 1;

  start() {
    if (this.process) return;

    console.log(`[Python] Starting with command: ${PYTHON_CMD} ${PYTHON_SCRIPT}`);

    this.process = spawn(PYTHON_CMD, [PYTHON_SCRIPT], {
      cwd: path.join(__dirname, '..', '..', 'python'),
    });

    this.process.stdout?.on('data', (data: Buffer) => {
      const lines = data.toString().split('\n').filter(Boolean);
      for (const line of lines) {
        try {
          const response = JSON.parse(line);
          const pending = this.pendingRequests.get(response.id);
          if (pending) {
            if (response.error) {
              pending.reject(new Error(response.error.message));
            } else {
              pending.resolve(response.result);
            }
            this.pendingRequests.delete(response.id);
          }
        } catch {
          // 忽略非 JSON 输出
        }
      }
    });

    this.process.stderr?.on('data', (data: Buffer) => {
      console.error(`[Python stderr] ${data.toString().trim()}`);
    });

    this.process.on('exit', (code: number | null) => {
      console.log(`[Python] exited with code ${code}`);
      this.process = null;
    });

    this.process.on('error', (err: Error) => {
      console.error(`[Python] spawn error:`, err.message);
    });
  }

  stop() {
    this.process?.kill();
    this.process = null;
  }

  call(method: string, params: object): Promise<any> {
    if (!this.process) {
      this.start();
    }

    const id = this.nextId++;
    const request = {
      jsonrpc: '2.0' as const,
      id,
      method,
      params,
    };

    return new Promise((resolve, reject) => {
      this.pendingRequests.set(id, { resolve, reject });
      this.process!.stdin!.write(JSON.stringify(request) + '\n');
    });
  }
}

export const pythonProcess = new PythonProcessManager();
