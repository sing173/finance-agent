"""统一路径解析 — 开发环境 / 打包环境 / HNP 模式自动切换 (Issue #33).

所有路径推导集中在此，避免 5 个位置用 5 种方式计算项目根路径。

提供:
  get_project_root()   → 项目根目录
  get_config_path()    → config 目录下的文件
  get_db_path()        → SQLite 数据库路径
  get_log_dir()        → 日志目录
"""
from __future__ import annotations

import os
import sys


def _is_hnp_mode() -> bool:
    """检测是否在 HNP 模式下运行（HarmonyOS）。"""
    try:
        return '/data/app/' in os.path.abspath(__file__)
    except Exception:
        return False


def _get_sandbox_dir() -> str | None:
    """获取 HarmonyOS 应用沙箱物理路径。

    读取环境变量 APP_SANDBOX_DIR（由 Electron 侧传入），
    格式：/data/app/el2/100/base/<bundleName>/

    若沙箱目录不可写，返回 None（调用方需自行处理）。
    绝不 fallback 到 HNP 安装目录（HNP 安装目录只读）。
    """
    sandbox = os.environ.get('APP_SANDBOX_DIR') or None
    if sandbox:
        try:
            test_path = os.path.join(sandbox, 'temp')
            os.makedirs(test_path, exist_ok=True)
            return sandbox
        except OSError:
            pass
    return None


def get_project_root() -> str:
    """获取项目根目录（开发环境）。

    通过当前文件位置向上推导 5 层到达 monorepo 根。
    打包环境 / HNP 模式不适用。
    """
    # finance_agent_backend/paths.py → src/ → python/ → apps/ → project root
    path = os.path.abspath(__file__)
    for _ in range(5):
        path = os.path.dirname(path)
    return path


def get_config_path(filename: str = '') -> str:
    """获取 config 目录下的文件路径。

    - 开发环境: <backend_dir>/config/<filename>
    - PyInstaller 打包: <sys._MEIPASS>/finance_agent_backend/config/<filename>
    - HNP 模式: <site-packages>/finance_agent_backend/config/<filename>
    """
    if _is_hnp_mode():
        # HNP 模式下，config 与 paths.py 同级
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(backend_dir, 'config', filename)

    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
        return os.path.join(base, 'finance_agent_backend', 'config', filename)

    # 开发环境：config 目录与 paths.py 同级
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(backend_dir, 'config', filename)


def get_db_path() -> str:
    """获取 SQLite 数据库路径。

    - 开发环境: <project_root>/data.db
    - PyInstaller 打包: %APPDATA%/FinanceAssistant/data.db
    - HNP 模式: <sandbox>/files/finance_agent.db（HarmonyOS 应用沙箱）
    """
    sandbox = _get_sandbox_dir()
    if sandbox:
        dir_path = os.path.join(sandbox, 'files')
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, 'finance_agent.db')

    if getattr(sys, 'frozen', False):
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        return os.path.join(base, 'FinanceAssistant', 'data.db')

    return os.path.join(get_project_root(), 'data.db')


def get_log_dir() -> str:
    """获取日志目录路径。

    - 开发环境: <project_root>/logs/
    - PyInstaller 打包: %APPDATA%/FinanceAssistant/logs/
    - HNP 模式: <sandbox>/files/logs/（HarmonyOS 应用沙箱）
      若沙箱不可写，返回 /tmp（日志写入 /tmp）。
    """
    sandbox = _get_sandbox_dir()
    if sandbox:
        dir_path = os.path.join(sandbox, 'files', 'logs')
        try:
            os.makedirs(dir_path, exist_ok=True)
            return dir_path
        except OSError:
            pass  # fallback to /tmp

    if getattr(sys, 'frozen', False):
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        return os.path.join(base, 'FinanceAssistant', 'logs')

    return os.path.join(get_project_root(), 'logs')


def get_export_dir() -> str:
    """获取导出文件目录路径。

    - 开发环境: <project_root>/exports/
    - PyInstaller 打包: %APPDATA%/FinanceAssistant/exports/
    - HNP 模式: /storage/media/100/local/files/Docs/Documents/
      （HarmonyOS 公共文档目录，用户可通过文件管理器访问）
    """
    sandbox = _get_sandbox_dir()
    if sandbox:
        # HarmonyOS：写到公共文档目录（用户可访问）
        dir_path = '/storage/media/100/local/files/Docs/Documents'
        try:
            os.makedirs(dir_path, exist_ok=True)
            return dir_path
        except OSError:
            pass  # fallback to /tmp

    if getattr(sys, 'frozen', False):
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        return os.path.join(base, 'FinanceAssistant', 'exports')

    return os.path.join(get_project_root(), 'exports')
