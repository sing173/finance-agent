"""用 icbc_parser 的网格方案重新解析回单."""
# 直接复用 icbc_parser.py 的 detect_lines + build_grid + assign_blocks
# 然后在新文件里用网格坐标提取字段
import sys, glob
sys.path.insert(0, "src")
from finance_agent_backend.tools.icbc_parser import ICBCParser

# 用 icbc_parser 的网格方法看回单的分割结果
p = ICBCParser()
pdfs = list(glob.glob(r'C:\Users\dell\Desktop\finance agent\回单pdf\*363-1*'))

import fitz
with open(pdfs[0], 'rb') as f:
    doc = fitz.open('pdf', f.read())

img = ICBCParser._render_page(doc, 0)
h_coords, v_coords = ICBCParser._detect_table_lines(img)
grid_rows = ICBCParser._build_grid(h_coords, v_coords)

print(f"H lines: {len(h_coords)}")
print(f"V lines: {len(v_coords)}")
print(f"Grid rows: {len(grid_rows)}, cols: {len(grid_rows[0]) if grid_rows else 0}")
print(f"\nH coords: {h_coords}")
print(f"V coords: {v_coords}")
print(f"\nFirst 3 rows (y ranges):")
for i, row in enumerate(grid_rows[:3]):
    x0,y0,x1,y1 = row[0]
    print(f"  row {i}: y=[{y0},{y1}] h={y1-y0}")

# 做OCR
blocks = p._ocr_page_data(img)
print(f"\nOCR blocks: {len(blocks)}")

# 分配块到单元格
cell_grid = p._assign_blocks(blocks, grid_rows)

print(f"\nCell grid: {len(cell_grid)} rows x {len(cell_grid[0]) if cell_grid else 0} cols")

# 打印有文本的单元格
print(f"\nNon-empty cells:")
for ri, row in enumerate(cell_grid):
    for ci, cell in enumerate(row):
        texts = cell['texts']
        if texts:
            print(f"  [{ri:2d},{ci}] y=[{h_coords[ri]},{h_coords[ri+1]}] x=[{v_coords[ci]},{v_coords[ci+1]}] | {'|'.join(texts)}")

doc.close()
