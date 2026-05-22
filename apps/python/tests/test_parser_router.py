"""Tests for parser_router — 使用真实文件测试识别 + 解析全流程。

测试通过 public interface: detect_bank_from_pdf() 和 route()。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from finance_agent_backend.parser_router import detect_bank_from_pdf, route

# ── 真实文件路径 ──────────────────────────────────────────────────

BASE = r"C:\Users\dell\Desktop\finance agent"

REAL_FILES = {
    "icbc_csv": os.path.join(BASE, "historydetail0.csv"),
    "cmb_xlsx": os.path.join(BASE, "招行流水.xlsx"),
    "cmb_pdf_embedded": os.path.join(BASE, "cmb-03.pdf"),
    "gfb_pdf_embedded": os.path.join(BASE, "广发.pdf"),
    "icbc_pdf_scanned": os.path.join(BASE, "中国工商银行企业网上银行363-2603.pdf"),
    "cmb_receipt_pdf": os.path.join(BASE, "回单pdf", "招行回单2.pdf"),
    "icbc_receipt_pdf": os.path.join(BASE, "回单pdf", "中国工商银行企业网上银行363-1回单.pdf"),
}


def _skip_if_missing(*paths):
    for p in paths:
        if not os.path.exists(p):
            pytest.skip(f"文件不存在: {p}")


# ── 辅助：计时装饰器 ──────────────────────────────────────────────

def _timed(label, func, *args, **kwargs):
    t0 = time.time()
    result = func(*args, **kwargs)
    elapsed = time.time() - t0
    print(f"\n  [{label}] 耗时: {elapsed:.2f}s")
    return result


# ═══════════════════════════════════════════════════════════════════
# detect_bank_from_pdf — 识别银行测试
# ═══════════════════════════════════════════════════════════════════

class TestDetectBankEmbedded:
    """嵌入式 PDF — Level 1 结构匹配，不应走 OCR"""

    def test_detect_cmb_table_embedded(self):
        path = REAL_FILES["cmb_pdf_embedded"]
        _skip_if_missing(path)
        bank_code, doc_type = _timed("cmb-03 识别", detect_bank_from_pdf, path)
        assert bank_code == 'CMB'
        assert doc_type == '流水'

    def test_detect_gfb_table_embedded(self):
        path = REAL_FILES["gfb_pdf_embedded"]
        _skip_if_missing(path)
        bank_code, doc_type = _timed("广发 识别", detect_bank_from_pdf, path)
        assert bank_code == 'GFB'
        assert doc_type == '流水'


class TestDetectBankScanned:
    """扫描件 PDF — Level 2 OCR 账号匹配（复用 OCR 实例）"""

    def test_detect_icbc_scanned(self):
        path = REAL_FILES["icbc_pdf_scanned"]
        _skip_if_missing(path)
        bank_code, doc_type = _timed("工行扫描件 识别", detect_bank_from_pdf, path)
        assert bank_code == 'ICBC'
        assert doc_type == '回单'

    def test_detect_cmb_receipt_embedded(self):
        """招行回单2 嵌入式文本 — 含'出账回单'+'入账回单'"""
        path = REAL_FILES["cmb_receipt_pdf"]
        _skip_if_missing(path)
        bank_code, doc_type = _timed("招行回单2 识别", detect_bank_from_pdf, path)
        assert bank_code == 'CMB'
        assert doc_type == '回单'

    def test_detect_icbc_receipt_scanned(self):
        path = REAL_FILES["icbc_receipt_pdf"]
        _skip_if_missing(path)
        bank_code, doc_type = _timed("工行回单 识别", detect_bank_from_pdf, path)
        assert bank_code == 'ICBC'
        assert doc_type == '回单'

    def test_ocr_instance_reuse_speedup(self):
        """第二次 OCR 应显著快于首次（RapidOCR 单例复用）"""
        path = REAL_FILES["icbc_pdf_scanned"]
        _skip_if_missing(path)

        t0 = time.time()
        detect_bank_from_pdf(path)
        first_run = time.time() - t0

        t0 = time.time()
        detect_bank_from_pdf(path)
        second_run = time.time() - t0

        print(f"\n  首次 OCR: {first_run:.2f}s, 二次 OCR: {second_run:.2f}s "
              f"(加速 {first_run/second_run:.1f}x)")
        # 第二次可预期 ≤ 首次（首次含模型加载）
        assert second_run <= first_run * 1.2  # 允许波动


# ═══════════════════════════════════════════════════════════════════
# route — 解析全流程测试
# ═══════════════════════════════════════════════════════════════════

class TestRouteCSV:
    """CSV 解析 — 扩展名直接路由，不走银行检测"""

    def test_parse_icbc_csv(self):
        path = REAL_FILES["icbc_csv"]
        _skip_if_missing(path)
        result = _timed("工行 CSV 解析", route, path)
        assert result["success"] is True
        assert result["bank"] == "中国工商银行"
        assert len(result["transactions"]) >= 30
        assert result["confidence"] >= 0.9


class TestRouteExcel:
    """Excel 解析 — 扩展名直接路由，不走银行检测"""

    def test_parse_cmb_xlsx(self):
        path = REAL_FILES["cmb_xlsx"]
        _skip_if_missing(path)
        result = _timed("招行 Excel 解析", route, path)
        assert result["success"] is True
        assert result["bank"] == "招商银行"
        assert len(result["transactions"]) >= 1


class TestRouteEmbeddedPDF:
    """嵌入式 PDF 解析 — 先识别再解析"""

    def test_parse_cmb_table_embedded(self):
        path = REAL_FILES["cmb_pdf_embedded"]
        _skip_if_missing(path)
        result = _timed("cmb-03 解析", route, path)
        assert result["success"] is True
        assert "招商银行" in result["bank"]
        assert len(result["transactions"]) >= 1

    def test_parse_gfb_table_embedded(self):
        path = REAL_FILES["gfb_pdf_embedded"]
        _skip_if_missing(path)
        result = _timed("广发 解析", route, path)
        assert result["success"] is True
        assert "广发银行" in result["bank"]
        assert len(result["transactions"]) >= 1


class TestRouteScannedPDF:
    """扫描件 PDF 解析 — OCR 识别 + 解析"""

    def test_parse_icbc_scanned(self):
        path = REAL_FILES["icbc_pdf_scanned"]
        _skip_if_missing(path)
        result = _timed("工行扫描件 解析", route, path)
        assert result["success"] is True
        assert result["bank"] == "中国工商银行"
        assert len(result["transactions"]) >= 10
        assert result["confidence"] >= 0.9

    def test_parse_cmb_receipt_embedded(self):
        """招行回单2 嵌入式文本 — 含多张出账+入账回单"""
        path = REAL_FILES["cmb_receipt_pdf"]
        _skip_if_missing(path)
        result = _timed("招行回单2 解析", route, path)
        assert result["success"] is True
        assert "招商银行" in result["bank"]
        assert len(result["transactions"]) >= 3

    def test_parse_icbc_receipt(self):
        path = REAL_FILES["icbc_receipt_pdf"]
        _skip_if_missing(path)
        result = _timed("工行回单 解析", route, path)
        assert result["success"] is True
        assert "工商银行" in result["bank"]
        assert len(result["transactions"]) >= 1


class TestRouteManualOverride:
    """手动覆盖银行/docType 参数"""

    def test_parse_cmb_with_bank_override(self):
        """指定 bank='招商银行' 跳过检测直接路由"""
        path = REAL_FILES["cmb_pdf_embedded"]
        _skip_if_missing(path)
        result = _timed("cmb-03 bank覆盖", route, path, bank="招商银行")
        assert result["success"] is True
        assert len(result["transactions"]) >= 1

    def test_parse_icbc_with_bank_and_doctype_override(self):
        """指定 bank + docType 双覆盖"""
        path = REAL_FILES["icbc_pdf_scanned"]
        _skip_if_missing(path)
        result = _timed("工行 bank+docType覆盖", route, path,
                        bank="工商银行", doc_type="流水")
        assert result["success"] is True
        assert result["bank"] == "中国工商银行"
        assert len(result["transactions"]) >= 10