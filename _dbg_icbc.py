"""Deep-debug the bleeds: "公司" near tx4/tx16."""
import sys, os, re
_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apps", "python", "src")
sys.path.insert(0, _project_root)

from finance_agent_backend.tools.pdf_ocr import PDFOCR
from finance_agent_backend.tools.icbc_parser import ICBCParser

pdf_path = r"C:\Users\dell\Desktop\finance agent\中国工商银行企业网上银行931-2603.pdf"
ocr = PDFOCR(dpi=200)
result = ocr.extract(pdf_path)
blocks = result["pages"][0]["blocks"]
parser = ICBCParser()

sorted_blocks = sorted(blocks, key=lambda b: (b["box"][0][1], b["box"][0][0]))

date_items = []
for i, b in enumerate(sorted_blocks):
    if parser._is_date_prefix(b):
        yc = (b["box"][0][1] + b["box"][2][1]) / 2
        date_items.append((i, yc, b))

# Examine the "problematic" blocks — those in counterparty/purpose cols with y between dates
print("Counterparty/purpose blocks near date boundaries:")
for b in sorted_blocks:
    x0 = b["box"][0][0]
    col = parser._classify_column(x0)
    if col not in ("counterparty", "purpose"):
        continue
    y0, y1 = b["box"][0][1], b["box"][2][1]
    yc = (y0 + y1) / 2

    # Find enclosing dates
    above, below = None, None
    for gi, (_, dyc, _) in enumerate(date_items):
        if dyc <= yc:
            above = (gi, dyc)
        elif below is None:
            below = (gi, dyc)
            break

    if above and below:
        dist_above = yc - above[1]
        dist_below = below[1] - yc
        ratio = dist_below / dist_above if dist_above > 0 else 999
        if ratio < 1.0:  # closer to next than current
            print(f"  BLEED: {b['text']!r} yc={yc:.1f} col={col} "
                  f"above_d{above[0]}({dist_above:.0f}) below_d{below[0]}({dist_below:.0f}) "
                  f"ratio={ratio:.2f}")

print("\nFull block sequence around tx3-tx6 boundary:")
for b in sorted_blocks[date_items[2][0]:date_items[5][0]+5]:
    x0 = b["box"][0][0]
    y0 = b["box"][0][1]
    yc = (y0 + b["box"][2][1]) / 2
    col = parser._classify_column(x0)
    is_date = parser._is_date_prefix(b)
    marker = " <== DATE" if is_date else ""
    print(f"  yc={yc:6.1f} x={x0:4d} col={col or '--':15s} {b['text']!r}{marker}")
