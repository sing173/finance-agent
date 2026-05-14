"""Analyze ICBC receipt PDF using icbc_parser.py pipeline (render+OCR+structure detection)."""
import fitz, os, cv2, numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
from itertools import groupby

receipt_dir = r'C:\Users\dell\Desktop\finance agent\回单pdf'
files = [f for f in os.listdir(receipt_dir) if 'ICBC' in f or '工商' in f or '931' in f or '363' in f]
print('=== ICBC receipt files ===')
for f in sorted(files):
    print(f"  {f}")

target = [f for f in files if '931回单1' in f]
if not target:
    target = [files[0]]
target_path = os.path.join(receipt_dir, target[0])
print(f'\nAnalyzing: {target[0]}')

with open(target_path, 'rb') as fh:
    doc = fitz.open('pdf', fh.read())
print(f'Pages: {len(doc)}')

ocr = RapidOCR()
out_dir = r'D:\git\finance-agent\.claude\worktrees\pdf-ocr-experiment'

for pg in range(min(2, len(doc))):
    page = doc[pg]
    pix = page.get_pixmap(dpi=300)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    h, w = img.shape[:2]
    print(f'\n=== Page {pg}: {w}x{h} ===')

    # --- Table line detection (same as icbc_parser) ---
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

    h_proj = np.sum(h_lines, axis=1) / 255.0
    v_proj = np.sum(v_lines, axis=0) / 255.0
    h_thresh = max(np.max(h_proj) * 0.15, 10)
    v_thresh = max(np.max(v_proj) * 0.15, 10)
    h_pos = np.where(h_proj > h_thresh)[0]
    v_pos = np.where(v_proj > v_thresh)[0]

    print(f'H lines: raw={len(h_pos)}, V lines: raw={len(v_pos)}')
    print(f'H proj max={np.max(h_proj):.1f}, threshold={h_thresh:.1f}')
    print(f'V proj max={np.max(v_proj):.1f}, threshold={v_thresh:.1f}')

    def extract_pos(positions):
        if len(positions) == 0:
            return []
        grouped = []
        for k, g in groupby(enumerate(positions), lambda x: x[0] - x[1]):
            group = list(g)
            grouped.append(int(np.mean([x[1] for x in group])))
        merged = []
        for pos in grouped:
            if not merged or pos - merged[-1] > 5:
                merged.append(pos)
            else:
                merged[-1] = int((merged[-1] + pos) / 2)
        return merged

    h_coords = extract_pos(h_pos)
    v_coords = extract_pos(v_pos)
    print(f'H coords (merged): {len(h_coords)}')
    print(f'V coords (merged): {len(v_coords)}')
    if h_coords:
        print(f'  H: {h_coords[:20]}...' if len(h_coords) > 20 else f'  H: {h_coords}')
    if v_coords:
        print(f'  V: {v_coords[:20]}...' if len(v_coords) > 20 else f'  V: {v_coords}')

    # --- Try to build grid and see if table structure exists ---
    if len(h_coords) >= 3 and len(v_coords) >= 3:
        rows = []
        for i in range(len(h_coords) - 1):
            y0, y1 = h_coords[i], h_coords[i + 1]
            if y1 - y0 < 8:
                continue
            cells = []
            for j in range(len(v_coords) - 1):
                x0, x1 = v_coords[j], v_coords[j + 1]
                if x1 - x0 < 5:
                    continue
                cells.append((x0, y0, x1, y1))
            if cells:
                rows.append(cells)
        print(f'Grid rows built: {len(rows)}, cells/row: {len(rows[0]) if rows else 0}')
    else:
        print('GRID: Not enough lines for table grid (< 3 H or < 3 V lines)')

    # --- OCR (same as icbc_parser) ---
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    img_np = np.array(pil_img.convert('L'))
    _, img_bin = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    ocr_result, _ = ocr(img_bin)
    print(f'OCR blocks found: {len(ocr_result) if ocr_result else 0}')

    if ocr_result:
        blocks = []
        for box, text, conf in ocr_result:
            x0, y0 = box[0]
            x1, y1 = box[2]
            blocks.append({
                'x0': float(x0), 'y0': float(y0),
                'x1': float(x1), 'y1': float(y1),
                'cx': (x0 + x1) / 2, 'cy': (y0 + y1) / 2,
                'text': text, 'conf': float(conf) if conf else 0.0,
            })
        blocks.sort(key=lambda b: (b['y0'], b['x0']))

        print(f'\n--- ALL OCR TEXT (top-down, left-right) ---')
        for b in blocks:
            print(f'  y={b["y0"]:6.0f} x={b["x0"]:6.0f} ({b["x1"]-b["x0"]:4.0f}x{b["y1"]-b["y0"]:4.0f}) conf={b["conf"]:.2f} |{b["text"]}|')

        # --- Group into horizontal bands (potential receipt blocks) ---
        print(f'\n--- TEXT GROUPED BY Y-BANDS (gap > 30px = new band) ---')
        bands = []
        current_band = [blocks[0]]
        for i in range(1, len(blocks)):
            if blocks[i]['y0'] - blocks[i-1]['y0'] > 30:
                bands.append(current_band)
                current_band = [blocks[i]]
            else:
                current_band.append(blocks[i])
        bands.append(current_band)

        for bi, band in enumerate(bands):
            band_texts = ' | '.join(b['text'] for b in band)
            y_range = f"{band[0]['y0']:.0f}-{band[-1]['y0']:.0f}"
            print(f'  Band {bi} (y={y_range}): {band_texts[:200]}')

        # Annotated debug image
        debug = img.copy()
        for b in blocks:
            cv2.rectangle(debug, (int(b['x0']), int(b['y0'])),
                         (int(b['x1']), int(b['y1'])), (0, 255, 0), 1)
        for y in h_coords:
            cv2.line(debug, (0, y), (w, y), (255, 0, 0), 1)
        for x in v_coords:
            cv2.line(debug, (x, 0), (x, h), (0, 0, 255), 1)
        out_path = os.path.join(out_dir, f'debug_receipt_pg{pg}.png')
        cv2.imwrite(out_path, debug)
        print(f'\nDebug image saved: {out_path}')
    else:
        print('NO OCR TEXT FOUND!')

doc.close()
print('\n=== ANALYSIS COMPLETE ===')
