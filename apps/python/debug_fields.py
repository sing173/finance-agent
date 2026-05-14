"""Debug field extraction for first receipt."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath('.')), 'src'))

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

with open('field_debug.txt', 'w', encoding='utf-8') as f:
    for ri, receipt_cells in enumerate(receipts[:2], 1):
        f.write(f"\n{'='*60}\n")
        f.write(f"Receipt {ri}:\n")
        f.write(f"{'='*60}\n")

        # Show all cells
        f.write("\nAll cells:\n")
        for c in sorted(receipt_cells, key=lambda x: (x['row'], x['col'])):
            f.write(f"  [{c['row']:2d},{c['col']}] '{c['text']}'\n")

        # Extract fields
        fields = parser._cells_to_fields(receipt_cells)
        f.write(f"\nExtracted fields:\n")
        for k, v in fields.items():
            f.write(f"  {k}: '{v}'\n")

doc.close()
print("Done")
