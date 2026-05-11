"""Test ICBC parser with real bank statement."""
import sys, os

_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apps", "python", "src")
sys.path.insert(0, _project_root)

from finance_agent_backend.tools.pdf_ocr import PDFOCR
from finance_agent_backend.tools.icbc_parser import ICBCParser

pdf_path = r"C:\Users\dell\Desktop\finance agent\中国工商银行企业网上银行931-2603.pdf"

# Step 1: OCR
print("Running OCR...")
ocr = PDFOCR(dpi=200)
ocr_result = ocr.extract(pdf_path)
print(f"OCR done: {ocr_result['total_pages']} pages, {sum(len(p['blocks']) for p in ocr_result['pages'])} blocks")

# Step 2: Parse
parser = ICBCParser()
result = parser.parse(ocr_result)

# Step 3: Output
out_path = os.path.join(os.path.dirname(__file__), "_icbc_parse_output.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(f"Bank: {result.bank}\n")
    f.write(f"Statement Date: {result.statement_date}\n")
    f.write(f"Confidence: {result.confidence}\n")
    f.write(f"Errors: {result.errors}\n")
    f.write(f"Warnings: {result.warnings}\n")
    f.write(f"\n=== {len(result.transactions)} Transactions ===\n\n")

    for i, t in enumerate(result.transactions):
        f.write(f"{i+1}. [{t.direction:7s}] {t.date}  ¥{t.amount:>14,.2f}")
        if t.counterparty:
            f.write(f"  {t.counterparty}")
        f.write(f"\n    desc: {t.description}")
        if t.reference_number:
            f.write(f"\n    ref: {t.reference_number}")
        if t.notes:
            f.write(f"\n    balance: {t.notes}")
        f.write("\n\n")

print(f"Done. Output: {out_path}")
with open(out_path, "r", encoding="utf-8") as f:
    print(f.read())
