"""Runtime hook: pre-load onnxruntime.dll with correct DLL search flags.

PyInstaller onefile mode extracts to a temp directory where Windows API set
forwarders (api-ms-win-crt-*) cannot resolve to their UCRT implementations.
Pre-loading onnxruntime.dll via LoadLibraryExW with LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR
ensures the DLL and its dependencies are resolved before Python's import machinery
tries to load onnxruntime_pybind11_state.pyd.
"""
import os
import sys
import ctypes
import logging

logger = logging.getLogger('finance_agent_backend')
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('[rt_hook] %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)

_MEIPASS = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
_capi = os.path.join(_MEIPASS, 'onnxruntime', 'capi')
_dll_path = os.path.join(_capi, 'onnxruntime.dll')

LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR = 0x00000100
LOAD_LIBRARY_SEARCH_SYSTEM32 = 0x00000800

if os.path.exists(_dll_path):
    try:
        os.add_dll_directory(_MEIPASS)
        h = ctypes.windll.kernel32.LoadLibraryExW(
            _dll_path, None,
            LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32,
        )
        if h:
            logger.info("Pre-loaded onnxruntime.dll (handle=%s)", h)
        else:
            logger.warning("LoadLibraryExW onnxruntime.dll failed, error=%s", ctypes.GetLastError())
    except Exception as e:
        logger.warning("Pre-load onnxruntime.dll error: %s", e)
