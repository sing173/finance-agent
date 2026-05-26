"""Regression test: CMBTableParser opening_balance parse_amount must convert string to Decimal.

Bug: _parse_header_metadata stored opening_balance as raw string '14,479.96' because
OPENING_BALANCE_KEY ('上页余额') didn't match the meta dict key ('opening_balance'),
so parse_amount() was never called. ParseResult.to_dict() then crashed on
float('14,479.96').
"""
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from finance_agent_backend.parser_router import route


def test_cmb_opening_balance_is_number():
    """完整解析招行 PDF → openingBalance 应为 float 而非字符串。"""
    file_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'cmb_statement.pdf')

    # 如果没有测试文件，使用桌面文件作为临时测试
    real_path = r"C:\Users\dell\Desktop\finance agent\招行对账单.pdf"
    if not os.path.exists(file_path) and os.path.exists(real_path):
        file_path = real_path

    if not os.path.exists(file_path):
        print("SKIP: no CMB PDF fixture found")
        return

    result = route(file_path)

    assert result['success'] is True, f"parse failed: {result.get('error')}"
    assert result['openingBalance'] is not None, "openingBalance should not be None"
    assert isinstance(result['openingBalance'], (int, float)), \
        f"openingBalance type={type(result['openingBalance'])}, expected int/float"

    assert result['openingBalance'] > 0, "openingBalance should be positive"
    print(f"PASS: openingBalance={result['openingBalance']}, {len(result['transactions'])} txns")


if __name__ == '__main__':
    test_cmb_opening_balance_is_number()
