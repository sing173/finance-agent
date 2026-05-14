"""Debug field extraction step by step."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath('.')), 'src'))

from finance_agent_backend.tools.icbc_receipt_grid_parser import ICBCReceiptGridParser
import fitz, glob
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
receipt_cells = receipts[0]

# Build row_cells
row_cells = defaultdict(dict)
for c in receipt_cells:
    row_cells[c["row"]][c["col"]] = c

# Label cells
label_cells = sorted(
    [c for c in receipt_cells if c["col"] in (0, 1)],
    key=lambda c: (c["row"], c["col"])
)

with open('field_debug4.txt', 'w', encoding='utf-8') as f:
    f.write("Step-by-step field extraction:\n\n")

    fields = {}
    for lc in label_cells:
        label_text = lc["text"].strip()
        ri = lc["row"]
        field_name = parser._label_to_field(label_text)
        if not field_name:
            f.write(f"[{ri},{lc['col']}] '{label_text}' -> SKIP (no match)\n")
            continue

        f.write(f"[{ri},{lc['col']}] '{label_text}' -> {field_name}\n")

        val = ""
        if ri in row_cells:
            for col in [3, 5, 6]:
                if col in row_cells[ri]:
                    candidate = row_cells[ri][col]["text"].strip()
                    f.write(f"  col {col}: '{candidate}'\n")
                    if field_name in ("amount_text", "amount_cn"):
                        if any(c.isdigit() for c in candidate):
                            val = candidate
                            f.write(f"    -> SELECTED\n")
                            break
                    elif candidate != label_text and len(candidate) > 1:
                        if field_name in ("payer", "payee"):
                            if candidate.isdigit() or '*' in candidate:
                                f.write(f"    -> SKIP (digit/masked)\n")
                                continue
                        val = candidate
                        f.write(f"    -> SELECTED\n")
                        break

        fields[field_name] = val
        f.write(f"  Final: '{val}'\n\n")

    f.write("Final fields:\n")
    for k, v in fields.items():
        f.write(f"  {k}: '{v}'\n")

doc.close()
print("Done")
