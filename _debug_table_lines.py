"""Step 1: Render ICBC PDF to image and detect table lines."""
import sys, os
_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apps", "python", "src")
sys.path.insert(0, _project_root)

import fitz
import cv2
import numpy as np

pdf_path = r"C:\Users\dell\Desktop\finance agent\中国工商银行企业网上银行931-2603.pdf"
output_dir = os.path.dirname(__file__)

# Render page 0 at high DPI
with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()
doc = fitz.open("pdf", pdf_bytes)
page = doc[0]
pix = page.get_pixmap(dpi=300)
img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
if pix.n == 4:
    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
elif pix.n == 3:
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

# Save original
cv2.imwrite(os.path.join(output_dir, "_debug_original.png"), img)
print(f"Image size: {img.shape}")

# Convert to grayscale
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Binarize (invert so lines are white on black for morphology)
_, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
cv2.imwrite(os.path.join(output_dir, "_debug_binary.png"), binary)

# Detect horizontal lines
h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1))
h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
cv2.imwrite(os.path.join(output_dir, "_debug_hlines.png"), h_lines)

# Detect vertical lines
v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80))
v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)
cv2.imwrite(os.path.join(output_dir, "_debug_vlines.png"), v_lines)

# Combine
table_lines = cv2.add(h_lines, v_lines)
cv2.imwrite(os.path.join(output_dir, "_debug_table_lines.png"), table_lines)

# Optional: dilate to connect small gaps
kernel_merge = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
table_lines_dilated = cv2.dilate(table_lines, kernel_merge, iterations=1)
cv2.imwrite(os.path.join(output_dir, "_debug_table_lines_dilated.png"), table_lines_dilated)

# Overlay on original for visual check
overlay = img.copy()
overlay[table_lines_dilated > 0] = [0, 0, 255]
cv2.imwrite(os.path.join(output_dir, "_debug_overlay.png"), overlay)

print("Done. Check _debug_*.png for results.")
doc.close()
