"""Analyze receipt table line structure for grid-based parsing."""
import fitz, cv2, numpy as np, glob
from itertools import groupby
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

def render_page(doc, page_num, dpi=300):
    page = doc[page_num]
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return img

def detect_lines(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)
    return h_lines, v_lines

def extract_positions(line_img, axis):
    projection = np.sum(line_img, axis=axis) / 255.0
    threshold = max(np.max(projection) * 0.15, 10)
    positions = np.where(projection > threshold)[0]
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

pdfs = list(glob.glob(r'C:\Users\dell\Desktop\finance agent\回单pdf\*363-1*'))
with open(pdfs[0], 'rb') as f:
    pdf_bytes = f.read()
doc = fitz.open('pdf', pdf_bytes)

img = render_page(doc, 0)
h_lines, v_lines = detect_lines(img)
h_pos = extract_positions(h_lines, axis=1)
v_pos = extract_positions(v_lines, axis=0)

print(f"Image: {img.shape[1]}x{img.shape[0]}")
print(f"\nH lines ({len(h_pos)}):")
for i, y in enumerate(h_pos):
    gap = h_pos[i+1]-y if i+1<len(h_pos) else 0
    marker = " [BIG]" if gap > 150 else ""
    print(f"  y={y:4d}  next_gap={gap:3d}px{marker}")

print(f"\nV lines ({len(v_pos)}):")
for i, x in enumerate(v_pos):
    gap = v_pos[i+1]-x if i+1<len(v_pos) else 0
    marker = " [BIG]" if gap > 150 else ""
    print(f"  x={x:4d}  next_gap={gap:3d}px{marker}")

print(f"\nGrid: {len(h_pos)-1} rows x {len(v_pos)-1} cols = {(len(h_pos)-1)*(len(v_pos)-1)} cells")

# Compare page 1
img1 = render_page(doc, 1)
h1, v1 = detect_lines(img1)
hp1 = extract_positions(h1, axis=1)
vp1 = extract_positions(v1, axis=0)
print(f"\nPage 1: {len(hp1)}H x {len(vp1)}V  (Page 0: {len(h_pos)}H x {len(v_pos)}V)")
print(f"  H match: {h_pos[:6]} vs {hp1[:6]}")
print(f"  V match: {v_pos} vs {vp1}")

# OCR blocks in form area (y=200~900)
from rapidocr_onnxruntime import RapidOCR
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
pil_img = Image.fromarray(img_rgb)
img_np = np.array(pil_img.convert('L'))
_, img_bin = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
ocr = RapidOCR()
ocr_result, _ = ocr(img_bin)
blocks = []
for box, text, conf in ocr_result:
    blocks.append({'text': text, 'y0': box[0][1], 'x0': box[0][0],
                   'cx': (box[0][0]+box[2][0])/2, 'cy': (box[0][1]+box[2][1])/2})
blocks.sort(key=lambda b: (b['y0'], b['x0']))

print(f"\nOCR blocks in form area (y=200~900):")
for b in blocks:
    if 200 <= b['y0'] <= 900:
        print(f"  y={b['y0']:.0f}  x={b['x0']:.0f}  cx={b['cx']:.0f}  '{b['text']}'")

doc.close()
