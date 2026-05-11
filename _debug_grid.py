"""Complete pipeline: table-line detection → grid → OCR → cell assignment → transactions.

Steps 2-5 of the table-line-first approach.
"""
import sys, os
from itertools import groupby

_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apps", "python", "src")
sys.path.insert(0, _project_root)

import fitz
import cv2
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

pdf_path = r"C:\Users\dell\Desktop\finance agent\中国工商银行企业网上银行931-2603.pdf"
output_dir = os.path.dirname(__file__)
DPI = 300

# ── Step 1: Render PDF page to image ──────────────────────────────────
with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()
doc = fitz.open("pdf", pdf_bytes)
page = doc[0]
pix = page.get_pixmap(dpi=DPI)
img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
if pix.n == 4:
    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
elif pix.n == 3:
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
print(f"Image size (DPI={DPI}): {img.shape}")

# ── Step 2: Detect table lines via morphology ─────────────────────────
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1))
h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)

v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80))
v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

# ── Step 3: Extract line coordinates via projection profiles ──────────

def extract_line_positions(line_img, axis, min_gap=5):
    """Extract line positions from binary line image using projection.

    axis=0: horizontal lines (returns y-coordinates)
    axis=1: vertical lines (returns x-coordinates)
    min_gap: minimum pixel gap to consider separate lines
    """
    projection = np.sum(line_img, axis=axis) / 255.0  # sum of white pixels
    threshold = max(np.max(projection) * 0.15, 10)  # at least 10 white pixels
    positions = np.where(projection > threshold)[0]

    if len(positions) == 0:
        return []

    # Group consecutive positions into single lines
    grouped = []
    for k, g in groupby(enumerate(positions), lambda x: x[0] - x[1]):
        group = list(g)
        avg = int(np.mean([x[1] for x in group]))
        grouped.append(avg)

    # Merge lines that are very close (within min_gap pixels)
    merged = []
    for pos in grouped:
        if not merged or pos - merged[-1] > min_gap:
            merged.append(pos)
        else:
            # Average with previous
            merged[-1] = int((merged[-1] + pos) / 2)

    return merged

h_coords = extract_line_positions(h_lines, axis=1)
v_coords = extract_line_positions(v_lines, axis=0)

print(f"\nHorizontal lines ({len(h_coords)}): {h_coords}")
print(f"\nVertical lines ({len(v_coords)}): {v_coords}")

# ── Step 4: Build grid (row boundaries = between consecutive h-lines) ─

def build_grid(h_lines_y, v_lines_x, img_height, img_width):
    """Build cell grid from line coordinates.

    Returns list of rows, each row is list of cells (x0, y0, x1, y1).
    """
    # Add image boundaries if needed
    row_edges = sorted(h_lines_y)
    col_edges = sorted(v_lines_x)

    # Build cells
    rows = []
    for i in range(len(row_edges) - 1):
        y0, y1 = row_edges[i], row_edges[i + 1]
        # Skip very thin rows (likely artifacts)
        if y1 - y0 < 8:
            continue
        cells = []
        for j in range(len(col_edges) - 1):
            x0, x1 = col_edges[j], col_edges[j + 1]
            # Skip very narrow columns
            if x1 - x0 < 5:
                continue
            cells.append((x0, y0, x1, y1))
        rows.append(cells)

    return rows

grid_rows = build_grid(h_coords, v_coords, img.shape[0], img.shape[1])
print(f"\nGrid rows: {len(grid_rows)}")
for i, row in enumerate(grid_rows):
    print(f"  Row {i}: {len(row)} cells, y={row[0][1]}-{row[0][3]}, "
          f"x ranges: [{', '.join(f'{c[0]}-{c[2]}' for c in row)}]")

# ── Step 5: Run OCR at same DPI ───────────────────────────────────────
print("\nRunning OCR...")
# Convert to PIL for RapidOCR
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
pil_img = Image.fromarray(img_rgb)

# Preprocess: grayscale + OTSU (same as pdf_ocr.py)
img_gray = pil_img.convert("L")
img_np = np.array(img_gray)
_, img_bin = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

engine = RapidOCR()
ocr_result, _ = engine(img_bin)

blocks = []
if ocr_result:
    for box, text, confidence in ocr_result:
        blocks.append({
            "text": text,
            "confidence": round(float(confidence), 4),
            "box": [[int(c) for c in pt] for pt in box],
            # Center point for cell assignment
            "cx": (box[0][0] + box[2][0]) / 2,
            "cy": (box[0][1] + box[2][1]) / 2,
        })
print(f"OCR found {len(blocks)} text blocks")

# ── Step 6: Assign OCR blocks to grid cells ───────────────────────────

def assign_blocks_to_cells(blocks, grid_rows):
    """Assign each OCR block to the cell that contains its center point.

    Returns: grid_rows with assigned text per cell.
    """
    # Build result structure: same shape as grid_rows, each cell has a list of blocks
    result = []
    for row in grid_rows:
        result_row = []
        for (cx0, cy0, cx1, cy1) in row:
            result_row.append({"bbox": (cx0, cy0, cx1, cy1), "blocks": []})
        result.append(result_row)

    for b in blocks:
        assigned = False
        for ri, row in enumerate(grid_rows):
            for ci, cell in enumerate(row):
                cx0, cy0, cx1, cy1 = cell
                if cx0 <= b["cx"] <= cx1 and cy0 <= b["cy"] <= cy1:
                    result[ri][ci]["blocks"].append(b)
                    assigned = True
                    break
            if assigned:
                break
        # If not assigned to any cell, try to find closest row/col
        if not assigned:
            # Find closest row by y distance
            best_ri = min(range(len(grid_rows)),
                          key=lambda ri: abs((grid_rows[ri][0][1] + grid_rows[ri][0][3]) / 2 - b["cy"]))
            row = grid_rows[best_ri]
            best_ci = min(range(len(row)),
                          key=lambda ci: abs((row[ci][0] + row[ci][2]) / 2 - b["cx"]))
            result[best_ri][best_ci]["blocks"].append(b)

    return result

cell_grid = assign_blocks_to_cells(blocks, grid_rows)

# ── Step 7: Debug output ──────────────────────────────────────────────
out_path = os.path.join(output_dir, "_grid_debug.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(f"Grid: {len(cell_grid)} rows\n\n")
    for ri, row in enumerate(cell_grid):
        f.write(f"── Row {ri} (y={row[0]['bbox'][1]}-{row[0]['bbox'][3]}) ──\n")
        for ci, cell in enumerate(row):
            x0, y0, x1, y1 = cell["bbox"]
            texts = [blk["text"] for blk in cell["blocks"]]
            joined = " | ".join(texts) if texts else "(empty)"
            f.write(f"  Col {ci} [{x0}-{x1}]: {joined}\n")
        f.write("\n")

print(f"\nDebug output written to: {out_path}")
print("Done.")
doc.close()
