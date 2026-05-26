"""pytest 配置 — OCR marker + 默认只跑快速测试。"""
import pytest


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    config.addinivalue_line("markers", "ocr: 需要 OCR（扫描件/回单解析），默认跳过")


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    """默认 -m 'not ocr'。显式 -m ocr 时只跑 OCR。"""
    if config.getoption("-m"):
        return  # 用户已指定 -m，尊重用户选择
    skip_ocr = pytest.mark.skip(reason="默认跳过 OCR 测试，加 -m ocr 显式运行")
    for item in items:
        if "ocr" in item.keywords:
            item.add_marker(skip_ocr)