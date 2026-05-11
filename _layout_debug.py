"""Diagnostic: extract block coordinates from ICBC PDF to understand column layout."""
import sys, os, json
_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apps", "python", "src")
sys.path.insert(0, _project_root)

from finance_agent_backend.tools.pdf_ocr import PDFOCR

pdf_path = r"C:\Users\dell\Desktop\finance agent\中国工商银行企业网上银行931-2603.pdf"
ocr = PDFOCR(dpi=200)
result = ocr.extract(pdf_path)

# Write blocks with coordinates for layout analysis
out_path = os.path.join(os.path.dirname(__file__), "_layout_analysis.txt")
with open(out_path, "w", encoding="utf-8") as f:
    for page in result["pages"]:
        f.write(f"\n=== Page {page['page']} ({page['width']}x{page['height']}) ===\n")
        # Sort blocks by y then x to see row structure
        sorted_blocks = sorted(page["blocks"], key=lambda b: (round(b["box"][0][1] / 50) * 50, b["box"][0][0]))
        for b in sorted_blocks:
            box = b["box"]
            x0, y0 = box[0]
            x1, y1 = box[2]
            f.write(f"  x={x0:4d}-{x1:4d} y={y0:4d}-{y1:4d} [{b['confidence']:.4f}] {b['text']}\n")

print(f"Layout analysis written to {out_path}")
with open(out_path, "r", encoding="utf-8") as f:
    content = f.read()
print(content[:8000])
