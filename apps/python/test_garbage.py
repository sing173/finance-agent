"""Test OCR garbage filter directly."""
ocr_garbage = {'号账', '户', '账号', '户名', '付款人', '收款人', '开户银行'}
test_cases = ['号账', '户', '账号', '付款人', '收款人', '开户银行', '中锦技术（广东）有限公司', '3602051729200033487']

print("OCR garbage filter test:")
for candidate in test_cases:
    in_garbage = candidate in ocr_garbage
    print(f"  '{candidate}' -> {'SKIP' if in_garbage else 'OK'}")
