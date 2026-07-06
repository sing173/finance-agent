# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

# rapidocr_onnxruntime 模型文件 — PyInstaller 不会自动收集 .onnx 文件
_rapidocr_root = Path(
    os.path.join(SPECPATH, ".venv", "Lib", "site-packages", "rapidocr_onnxruntime")
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

# config 文件 — PyInstaller 不会自动收集 JSON 配置文件
_config_src = Path(os.path.join(SPECPATH, "src", "finance_agent_backend", "config"))
_config_datas = []
if _config_src.exists():
    for fname in ('subjects.json', 'subject_mapping.json', 'account_mapping.json'):
        src = _config_src / fname
        if src.exists():
            _config_datas.append((str(src), "finance_agent_backend/config"))

# UCRT — onnxruntime 依赖 api-ms-win-crt-* forwarder，这些在 PyInstaller onefile
# temp 目录中无法通过 API set 解析到 System32 的 ucrtbase.dll，必须显式打包。
_ucrt_dll = r'C:\Windows\System32\ucrtbase.dll'
_ucrt_binaries = [(_ucrt_dll, '.')] if os.path.exists(_ucrt_dll) else []

a = Analysis(
    ['src/finance_agent_backend/bridge.py'],
    pathex=[],
    binaries=_ucrt_binaries,
    datas=_rapidocr_datas + _config_datas,
    hiddenimports=[
        'nanobot',
        'pymupdf',
        'openpyxl',
        'et_xmlfile',
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
        'finance_agent_backend.tools.cmb_table_parser',
        'finance_agent_backend.tools.cmb_parser',
        'finance_agent_backend.tools.cmb_receipt_parser',
        'finance_agent_backend.tools.icbc_parser',
        'finance_agent_backend.tools.icbc_csv_parser',
        'finance_agent_backend.tools.icbc_receipt_grid_parser',
        'finance_agent_backend.tools.icbc_receipt_parser',
        'finance_agent_backend.tools.gfb_table_parser',
        'finance_agent_backend.tools.cmb_excel_parser',
        'finance_agent_backend.tools.pdf_parser',
        'finance_agent_backend.tools.excel_builder',
        'finance_agent_backend.tools.subject_loader',
        'finance_agent_backend.tools.shared_utils',
        'finance_agent_backend.tools.base_parser',
        'PIL',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['_rt_hook_onnxruntime.py'],
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
