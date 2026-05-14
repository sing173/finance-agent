"""Test the ACTUAL field extraction method."""
import sys
# Insert src at the VERY BEGINNING to override venv packages
sys.path.insert(0, 'src')

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

# Call the ACTUAL method
fields = parser._cells_to_fields(receipts[0])

with open('actual_fields.txt', 'w', encoding='utf-8') as f:
    f.write("Actual extracted fields:\n")
    for k, v in fields.items():
        f.write(f"  {k}: '{v}'\n")

print("Fields:")
for k, v in fields.items():
    print(f"  {k}: '{v}'")

# Also print all fields
print(f"\nTotal fields: {len(fields)}")

doc.close()
