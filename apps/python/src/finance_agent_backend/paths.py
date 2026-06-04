"""统一路径解析 — 开发环境 / 打包环境自动切换 (Issue #33).

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


def get_project_root() -> str:
    """获取项目根目录（开发环境）。

    通过当前文件位置向上推导 2 层到达项目根。
    打包环境不适用（使用 sys._MEIPASS）。
    """
    # finance_agent_backend/paths.py → parent = src/, parent's parent = project root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config_path(filename: str = '') -> str:
    """获取 config 目录下的文件路径。

    - 开发环境: <project_root>/finance_agent_backend/config/<filename>
    - 打包环境: <sys._MEIPASS>/finance_agent_backend/config/<filename>
    """
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = get_project_root()
    return os.path.join(base, 'finance_agent_backend', 'config', filename)


def get_db_path() -> str:
    """获取 SQLite 数据库路径。

    - 开发环境: <project_root>/data.db
    - 打包环境: %APPDATA%/FinanceAssistant/data.db
    """
    if getattr(sys, 'frozen', False):
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        return os.path.join(base, 'FinanceAssistant', 'data.db')
    return os.path.join(get_project_root(), 'data.db')


def get_log_dir() -> str:
    """获取日志目录路径。

    - 开发环境: <project_root>/logs/
    - 打包环境: %APPDATA%/FinanceAssistant/logs/
    """
    if getattr(sys, 'frozen', False):
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        return os.path.join(base, 'FinanceAssistant', 'logs')
    return os.path.join(get_project_root(), 'logs')
