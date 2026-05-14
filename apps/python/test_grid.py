import sys, glob, io
sys.path.insert(0, "src")
from finance_agent_backend.tools.icbc_receipt_grid_parser import ICBCReceiptGridParser

parser = ICBCReceiptGridParser()
output_path = "test_grid_output.txt"

with io.open(output_path, "w", encoding="utf-8") as out:
    for name in ['363-1', '363-2']:
        pdfs = list(glob.glob(fr'C:\Users\dell\Desktop\finance agent\回单pdf\*{name}*.pdf'))
        result = parser.parse(pdfs[0])
        out.write(f"{'='*80}\n")
        out.write(f"File: {pdfs[0]}\n")
        out.write(f"Transactions: {len(result.transactions)}\n")
        for i, tx in enumerate(result.transactions):
            out.write(f"\n--- Receipt {i} ---\n")
            out.write(f"  date: {tx.date}\n")
            out.write(f"  description: {tx.description}\n")
            out.write(f"  amount: {tx.amount}\n")
            out.write(f"  counterparty: {tx.counterparty}\n")
            out.write(f"  ref: {tx.reference_number}\n")
            out.write(f"  notes: {tx.notes}\n")
print(f"Done: {output_path}")
