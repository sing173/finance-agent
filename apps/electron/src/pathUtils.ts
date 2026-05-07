import * as path from 'path';

// 安全获取 process.resourcesPath（Electron 打包后才有）
function getResourcesPath(): string | undefined {
  try {
    return (process as any).resourcesPath;
  } catch {
    return undefined;
  }
}

// 检测是否在 Electron 打包应用中运行
// 使用 Electron 官方 API：app.isPackaged
function isElectronPackaged(): boolean {
  try {
    const { app } = require('electron');
    return app.isPackaged === true;
  } catch {
    return false;
  }
}

/**
 * 获取 Python bridge 的 spawn 配置（支持开发、测试、打包环境）
 * @returns {cmd, args, cwd} 可直接传给 spawn 的参数
 *
 * 环境优先级：
 * 1. PYTHON_CMD 环境变量
 * 2. 打包环境（Electron app packaged）：使用 resources/python/bridge(.exe)
 * 3. 开发环境：使用 venv Python + 源码 bridge.py
 */
export function getPythonSpawnConfig(): { cmd: string; args: string[]; cwd: string } {
  // 1. 环境变量优先
  if (process.env.PYTHON_CMD) {
    const cmd = process.env.PYTHON_CMD;
    if (cmd.endsWith('.exe') || path.isAbsolute(cmd)) {
      const cwd = path.dirname(cmd);
      return { cmd, args: [], cwd };
    } else {
      const scriptPath = path.resolve(__dirname, '..', '..', 'python', 'src', 'finance_agent_backend', 'bridge.py');
      return { cmd, args: [scriptPath], cwd: path.dirname(scriptPath) };
    }
  }

  // 2. 打包环境：使用 resources/python/bridge(.exe)
  if (isElectronPackaged()) {
    const resourcesPath = getResourcesPath();
    if (resourcesPath) {
      const ext = process.platform === 'win32' ? '.exe' : '';
      const exePath = path.join(resourcesPath, 'python', 'bridge' + ext);
      console.log('[PathUtils] Packaged mode, using:', exePath);
      return { cmd: exePath, args: [], cwd: path.dirname(exePath) };
    }
    console.warn('[PathUtils] Packaged mode but resourcesPath unavailable, falling back to dev mode');
  }

  // 3. 开发环境：使用 venv Python + 源码 bridge.py
  const venvPython = path.resolve(__dirname, '..', '..', 'python', '.venv', 'bin', 'python3');
  const scriptPath = path.resolve(__dirname, '..', '..', 'python', 'src', 'finance_agent_backend', 'bridge.py');
  console.log('[PathUtils] Dev mode, using:', venvPython, scriptPath);
  return { cmd: venvPython, args: [scriptPath], cwd: path.dirname(scriptPath) };
}
