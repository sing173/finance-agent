"""Debug field extraction with detailed logging."""
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

with open('field_debug3.txt', 'w', encoding='utf-8') as f:
    f.write("Field extraction debug:\n\n")

    for lc in label_cells:
        label_text = lc["text"].strip()
        ri = lc["row"]
        field_name = parser._label_to_field(label_text)
        if not field_name:
            continue

        f.write(f"[{ri},{lc['col']}] '{label_text}' -> {field_name}\n")

        # Same row check
        val = ""
        if ri in row_cells:
            value_cols = [3, 5, 6]
            if field_name in ("payer", "payee", "payer_account", "payee_account"):
                value_cols = [6, 3, 5]

            for col in value_cols:
                if col in row_cells[ri]:
                    candidate = row_cells[ri][col]["text"].strip()
                    f.write(f"  Same row col {col}: '{candidate}'\n")
                    if field_name in ("amount_text", "amount_cn"):
                        if any(c.isdigit() for c in candidate):
                            val = candidate
                            f.write(f"    -> Selected (has digits)\n")
                            break
                    elif (candidate != label_text
                          and len(candidate) > 2
                          and not candidate.isdigit()
                          and '*' not in candidate):
                        val = candidate
                        f.write(f"    -> Selected\n")
                        break

        # Prev row check
        if not val and field_name in ("payer", "payee"):
            f.write(f"  Same row failed, checking prev row...\n")
            if lc["col"] == 0 and field_name == "payer":
                prev_ri = ri - 1
                f.write(f"  Payer at col 0, checking row {prev_ri}\n")
                if prev_ri in row_cells:
                    for col in [6, 3, 5]:
                        if col in row_cells[prev_ri]:
                            candidate = row_cells[prev_ri][col]["text"].strip()
                            f.write(f"    Prev row col {col}: '{candidate}'\n")
                            if (candidate and len(candidate) > 2
                                and not candidate.isdigit()
                                and '*' not in candidate):
                                val = candidate
                                f.write(f"      -> Selected\n")
                                break

        f.write(f"  Final val: '{val}'\n\n")

doc.close()
print("Done")
