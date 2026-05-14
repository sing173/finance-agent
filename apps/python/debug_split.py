"""Debug receipt splitting on page 1 of 363-1."""
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

# Flatten cells
all_cells = parser._flatten_cells(cell_grid, h_coords, v_coords)

print("All cells sorted by row:")
for c in sorted(all_cells, key=lambda x: (x['row'], x['col'])):
    marker = ""
    if "网上银行电子回单" in c['text']:
        marker = " *** TITLE (网上银行电子回单)"
    elif "电子回单号码" in c['text']:
        marker = " *** TITLE (电子回单号码)"
    elif "中国工商银行" in c['text']:
        marker = " *** BANK"
    print(f"  [{c['row']:2d},{c['col']}] '{c['text']}'{marker}")

print("\n\nDetailed title check:")
for c in all_cells:
    if "网上银行电子回单" in c["text"] or "电子回单号码" in c["text"]:
        print(f"  Row {c['row']}, Col {c['col']}: full text = '{c['text']}'")
        if "网上银行电子回单" in c["text"]:
            print(f"    -> Contains '网上银行电子回单'")
        if "电子回单号码" in c["text"]:
            print(f"    -> Contains '电子回单号码'")

doc.close()
