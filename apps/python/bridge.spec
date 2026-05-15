# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

# rapidocr_onnxruntime 模型文件 — PyInstaller 不会自动收集 .onnx 文件
_rapidocr_root = Path(
    os.path.join(os.path.dirname(__file__), ".venv", "Lib", "site-packages", "rapidocr_onnxruntime")
)
_rapidocr_datas = []
if _rapidocr_root.exists():
    _rapidocr_datas = [
        (str(_rapidocr_root / "config.yaml"), "rapidocr_onnxruntime"),
        (str(_rapidocr_root / "models" / "ch_PP-OCRv4_det_infer.onnx"),
         "rapidocr_onnxruntime/models"),
        (str(_rapidocr_root / "models" / "ch_PP-OCRv4_rec_infer.onnx"),
         "rapidocr_onnxruntime/models"),
        (str(_rapidocr_root / "models" / "ch_ppocr_mobile_v2.0_cls_infer.onnx"),
         "rapidocr_onnxruntime/models"),
    ]

a = Analysis(
    ['src/finance_agent_backend/bridge.py'],
    pathex=[],
    binaries=[],
    datas=_rapidocr_datas,
    hiddenimports=[
        'nanobot',
        'pymupdf',
        'openpyxl',
        'rapidocr_onnxruntime',
        'rapidocr_onnxruntime.main',
        'rapidocr_onnxruntime.ch_ppocr_det',
        'rapidocr_onnxruntime.ch_ppocr_rec',
        'rapidocr_onnxruntime.ch_ppocr_cls',
        'rapidocr_onnxruntime.cal_rec_boxes',
        'rapidocr_onnxruntime.utils',
        'rapidocr_onnxruntime.utils.infer_engine',
        'rapidocr_onnxruntime.utils.parse_parameters',
        'cv2',
        'numpy',
        'onnxruntime',
        'PIL',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
