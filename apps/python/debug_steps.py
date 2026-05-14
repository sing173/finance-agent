"""分步输出回单解析算法每一步的结果，用于诊断数据问题。"""
import sys, glob
sys.path.insert(0, "src")
from finance_agent_backend.tools.icbc_receipt_grid_parser import ICBCReceiptGridParser
import fitz, cv2, numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

parser = ICBCReceiptGridParser()
pdfs = list(glob.glob(r'C:\Users\dell\Desktop\finance agent\回单pdf\*363-1*'))
file_path = pdfs[0]
print(f"文件: {pdfs[0]}")

with open(file_path, 'rb') as f:
    pdf_bytes = f.read()
doc = fitz.open('pdf', pdf_bytes)

# 只分析第0页
page = doc[0]
img = parser._render_page(doc, 0)
print(f"\n{'='*80}")
print("步骤1: 渲染页面 (DPI=300)")
print(f"  图片尺寸: {img.shape[1]}x{img.shape[0]}")

# OCR
blocks = parser._ocr_page_data(img)
print(f"\n{'='*80}")
print("步骤2: OCR (全页RapidOCR/ONNX)")
print(f"  识别到 {len(blocks)} 个文本块")
for i, b in enumerate(blocks):
    t = b['text'].strip()
    if t:
        print(f"  [{i:3d}] y={b['y0']:.0f} x={b['x0']:.0f} '{t}'")

# 回单分割
print(f"\n{'='*80}")
print("步骤3: 回单分割 (_split_receipts_per_page)")
print("  逻辑: 找'网上银行电子回单'标题块 → 向上回溯'中国工商银行'作为回单起点")
print("        每个回单从标题起点到下一个标题起点之前结束")

# 打印找到的标题锚点
title_blocks = [(i, b) for i, b in enumerate(blocks) if "网上银行电子回单" in b["text"]]
print(f"\n  找到 {len(title_blocks)} 个标题锚点 '网上银行电子回单':")
for i, b in title_blocks:
    print(f"    块[{i}] y={b['y0']:.0f} '{b['text']}'")

# 找到对应的ICBC标题
for i, b in title_blocks:
    start = i
    for back in range(i - 1, max(i - 5, -1), -1):
        if "中国工商银行" in blocks[back]["text"] and b["y0"] - blocks[back]["y0"] < 60:
            start = back
            print(f"    回溯到 '中国工商银行': 块[{start}] y={blocks[start]['y0']:.0f} '{blocks[start]['text']}'")
            break

receipts = parser._split_receipts_per_page(blocks)
print(f"\n  分割结果: {len(receipts)} 个回单")
for ri, rec in enumerate(receipts):
    y_range = f"y={rec[0]['y0']:.0f} ~ {rec[-1]['y0']:.0f}"
    title_text = [b['text'] for b in rec if "电子回单号码" in b['text']]
    receipt_no = title_text[0] if title_text else "?"
    print(f"  回单{ri}: {len(rec)} 块, {y_range}, 回单号: {receipt_no}")

# 字段提取
print(f"\n{'='*80}")
print("步骤4: 字段提取 (_extract_fields)")
print("  逻辑: Pass1 内联提取(label+value在同一块)")
print("        Pass2 空间提取(value在label右侧)")
print("        Pass3 位置法提取付款人/收款人")

for ri, rec in enumerate(receipts[:2]):  # 只看前两个
    print(f"\n  --- 回单 {ri} ---")
    fields = parser._extract_fields(rec)
    for k, v in sorted(fields.items()):
        print(f"    {k}: {v}")

    # 看merged之后的样子
    merged = parser._merge_label_blocks(rec)
    print(f"  merged后共 {len(merged)} 块:")
    for b in merged:
        t = b['text'].strip()
        if t:
            print(f"    '{t}'")

doc.close()
