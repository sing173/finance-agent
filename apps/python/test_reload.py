"""Force reload and test field extraction."""
import sys
import importlib

# Ensure src is first in path
if 'src' not in sys.path[0]:
    sys.path.insert(0, 'src')

# Force reload of the module
import finance_agent_backend.tools.icbc_receipt_grid_parser as mod
importlib.reload(mod)

from finance_agent_backend.tools.icbc_receipt_grid_parser import ICBCReceiptGridParser
import glob, fitz
from collections import defaultdict

parser = ICBCReceiptGridParser()
pdf_path = glob.glob(r'C:\Users\dell\Desktop\finance agent\回单pdf\*363-1*.pdf')[0]

with open(pdf_path, 'rb') as f:
    pdf_bytes = f.read()
doc = fitz.open('pdf', pdf_bytes)

img = parser._render_page(doc, 0)
h_coords, v_coords = parser._detect_table_lines(img)
grid_rows = parser._build_grid(h_coords, v_coords)
blocks = parser._ocr_page_data(img)
cell_grid = parser._assign_blocks(blocks, grid_rows)
all_cells = parser._flatten_cells(cell_grid, h_coords, v_coords)
receipts = parser._split_receipts(all_cells)

print(f"Calling _cells_to_fields...")
fields = parser._cells_to_fields(receipts[0])

print(f"\nExtracted fields:")
for k, v in fields.items():
    print(f"  {k}: '{v}'")

doc.close()
