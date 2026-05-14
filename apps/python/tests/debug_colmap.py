"""Debug: find where header text actually is in OCR output."""
import sys
sys.path.insert(0, r'D:\git\finance-agent\.claude\worktrees\pdf-ocr-experiment\apps\python\src')

from finance_agent_backend.tools.icbc_parser import ICBCParser
import fitz
import cv2
import numpy as np

path = r'C:\Users\dell\Desktop\finance agent\中国工商银行企业网上银行931-2603.pdf'
with open(path, 'rb') as f:
    doc = fitz.open('pdf', f.read())

p = ICBCParser()
img = ICBCParser._render_page(doc, 0)
h_coords, v_coords = p._detect_table_lines(img)

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, img_bin = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)
ocr_result, _ = p._ocr(img_bin)

print(f'Total blocks: {len(ocr_result) if ocr_result else 0}')
print(f'h_coords: {h_coords}')
print(f'v_coords: {v_coords}')
print(f'n_cols from grid: {len(v_coords) - 1}')

# Check which h_coords rows have blocks
if ocr_result:
    row_counts = {}
    for box, text, conf in ocr_result:
        cy = (box[0][1] + box[2][1]) / 2
        # Find which h row
        for ri in range(len(h_coords) - 1):
            if h_coords[ri] <= cy <= h_coords[ri+1]:
                row_counts[ri] = row_counts.get(ri, 0) + 1
                break
    print('\nBlocks per h_row:')
    for ri, cnt in sorted(row_counts.items()):
        print(f'  row {ri} y=[{h_coords[ri]},{h_coords[ri+1]}] has {cnt} blocks')

# Show ALL blocks with their text to find header keywords
print('\n--- All OCR blocks ---')
if ocr_result:
    for box, text, conf in ocr_result:
        cy = (box[0][1] + box[2][1]) / 2
        cx = (box[0][0] + box[2][0]) / 2
        print(f'  y={cy:.0f} x={cx:.0f} conf={conf:.2f} text={text!r}')

# Also show which row each block falls in
print('\n--- Blocks per row with text ---')
if ocr_result:
    for ri in range(len(h_coords) - 1):
        hy0, hy1 = h_coords[ri], h_coords[ri+1]
        row_blocks = [(box, text) for box, text, _ in ocr_result if hy0 <= (box[0][1]+box[2][1])/2 <= hy1]
        if row_blocks:
            print(f'  Row {ri} y=[{hy0},{hy1}] ({len(row_blocks)} blocks):')
            for box, text in row_blocks:
                print(f'    x=[{box[0][0]:.0f},{box[2][0]:.0f}] text={text!r}')
