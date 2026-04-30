# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/finance_agent_backend/bridge.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['nanobot', 'pymupdf', 'openpyxl', 'rapidfuzz'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.tundra)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 保留控制台用于 stdio JSON-RPC 通信
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
