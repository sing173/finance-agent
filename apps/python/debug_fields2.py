"""Debug field extraction with more logging."""
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

receipt_cells = receipts[0]

# Debug the field extraction
with open('field_debug2.txt', 'w', encoding='utf-8') as f:
    f.write("Receipt 1 cells:\n")
    for c in sorted(receipt_cells, key=lambda x: (x['row'], x['col'])):
        f.write(f"  [{c['row']:2d},{c['col']}] '{c['text']}'\n")

    # Manually run field extraction with logging
    from collections import defaultdict
    row_cells = defaultdict(dict)
    for c in receipt_cells:
        row_cells[c["row"]][c["col"]] = c

    label_cells = sorted(
        [c for c in receipt_cells if c["col"] in (0, 1)],
        key=lambda c: (c["row"], c["col"])
    )

    f.write(f"\nLabel cells found: {len(label_cells)}\n")
    for lc in label_cells:
        label_text = lc["text"].strip()
        field_name = parser._label_to_field(label_text)
        f.write(f"  [{lc['row']},{lc['col']}] '{label_text}' -> {field_name}\n")

doc.close()
print("Done")
