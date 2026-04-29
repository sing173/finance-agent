import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

const PYTHON_SCRIPT = path.join(__dirname, '..', 'python', 'src', 'bridge.py');

class PythonProcessManager {
  private process: ChildProcess | null = null;
  private pendingRequests: Map<number, { resolve: Function; reject: Function }> = new Map();
  private nextId = 1;

  start() {
    if (this.process) return;

    this.process = spawn('python3', [PYTHON_SCRIPT], {
      cwd: path.join(__dirname, '..', 'python'),
    });

    this.process.stdout?.on('data', (data) => {
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

    this.process.stderr?.on('data', (data) => {
      console.error(`[Python stderr] ${data}`);
    });

    this.process.on('exit', (code) => {
      console.log(`[Python] exited with code ${code}`);
      this.process = null;
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
