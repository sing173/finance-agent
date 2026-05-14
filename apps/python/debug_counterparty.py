"""Check where counterparty info is in both receipts."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from finance_agent_backend.tools.icbc_receipt_grid_parser import ICBCReceiptGridParser
import fitz, glob

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

print(f"V coords: {v_coords}")
print(f"Receipt 1:")
for c in sorted(receipts[0], key=lambda x: (x['row'], x['col'])):
    print(f"  [{c['row']:2d},{c['col']}] x=[{c['x0']:.0f}-{c['x1']:.0f}] '{c['text'][:40]}'")

print(f"\nReceipt 2:")
for c in sorted(receipts[1], key=lambda x: (x['row'], x['col'])):
    print(f"  [{c['row']:2d},{c['col']}] x=[{c['x0']:.0f}-{c['x1']:.0f}] '{c['text'][:40]}'")

doc.close()
