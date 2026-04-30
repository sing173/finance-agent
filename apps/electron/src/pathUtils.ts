import * as path from 'path';

// 安全获取process.resourcesPath（Electron打包后才有）
function getResourcesPath(): string | undefined {
  try {
    return (process as any).resourcesPath;
  } catch {
    return undefined;
  }
}

// 检测是否在Electron打包应用中运行
function isElectronPackaged(): boolean {
  // 优先检查 defaultApp（Electron 开发模式标志）
  // 开发模式（electron .）下 process.defaultApp === true
  // 打包后此属性不存在或为 false
  try {
    if ((process as any).defaultApp) return false;
  } catch {
    // ignore
  }

  const execPath = (process as any).execPath;
  if (typeof execPath === 'string') {
    // 情况1：asar 包（打包后主进程在 app.asar 内）
    if (execPath.includes('app.asar')) return true;

    // 情况2：Windows .exe（排除开发环境的 electron.exe）
    if (execPath.endsWith('.exe') && !execPath.toLowerCase().includes('node.exe')) {
      // 开发环境的 electron.exe 位于项目内的 node_modules/electron/dist/electron.exe
      // 打包后的 exe 在 Program Files 等安装目录
      const normalizedPath = execPath.toLowerCase().replace(/\\/g, '/');
      const isDevElectron = normalizedPath.includes('/node_modules/electron/');
      if (!isDevElectron) {
        return true;  // 不在 node_modules/electron 内 → 打包环境
      }
    }
  }

  return false;
}

/**
 * 获取Python bridge的spawn配置（支持开发、测试、打包环境）
 * @returns {cmd, args, cwd} 可直接传给spawn的参数
 *
 * 环境优先级：
 * 1. PYTHON_CMD环境变量（如 "python" 或 "D:\Python\python.exe" 或 ".../bridge.exe"）
 * 2. 打包环境（Electron app packaged）：使用 resources/python/bridge.exe
 * 3. 开发环境：使用系统 python/python3 + 源码 bridge.py
 */
export function getPythonSpawnConfig(): { cmd: string; args: string[]; cwd: string } {
  // 1. 环境变量优先
  if (process.env.PYTHON_CMD) {
    const cmd = process.env.PYTHON_CMD;
    if (cmd.endsWith('.exe') || path.isAbsolute(cmd)) {
      // 打包的bridge.exe - 直接运行，无需额外参数
      const cwd = path.dirname(cmd);
      return { cmd, args: [], cwd };
    } else {
      // 系统python命令 - 需要指定bridge.py脚本
      const scriptPath = path.resolve(__dirname, '..', '..', 'python', 'src', 'finance_agent_backend', 'bridge.py');
      return { cmd, args: [scriptPath], cwd: path.dirname(scriptPath) };
    }
  }

  // 2. 打包环境：使用 resources/python/bridge.exe
  if (isElectronPackaged()) {
    const resourcesPath = getResourcesPath();
    if (resourcesPath) {
      const exePath = path.join(resourcesPath, 'python', 'bridge.exe');
      console.log('[PathUtils] Packaged mode, using:', exePath);
      return { cmd: exePath, args: [], cwd: path.dirname(exePath) };
    }
    console.warn('[PathUtils] Packaged mode but resourcesPath unavailable, falling back to dev mode');
  }

  // 3. 开发/测试环境：系统Python + 源码
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
  const scriptPath = path.resolve(__dirname, '..', '..', 'python', 'src', 'finance_agent_backend', 'bridge.py');
  console.log('[PathUtils] Dev mode, using:', pythonCmd, scriptPath);
  return { cmd: pythonCmd, args: [scriptPath], cwd: path.dirname(scriptPath) };
}
