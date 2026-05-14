"""Comprehensive test of icbc_receipt_grid_parser on 363-1 and 363-2."""
import sys
sys.path.insert(0, 'src')
from finance_agent_backend.tools.icbc_receipt_grid_parser import ICBCReceiptGridParser
import glob, json

parser = ICBCReceiptGridParser()

test_files = {
    "363-1": glob.glob(r'C:\Users\dell\Desktop\finance agent\回单pdf\*363-1*.pdf')[0],
    "363-2": glob.glob(r'C:\Users\dell\Desktop\finance agent\回单pdf\*363-2*.pdf')[0],
}

all_results = {}

for name, pdf_path in test_files.items():
    result = parser.parse(pdf_path)

    all_results[name] = {
        "total_transactions": len(result.transactions),
        "errors": result.errors,
        "confidence": result.confidence,
        "statement_date": str(result.statement_date) if result.statement_date else None,
        "transactions": []
    }

    for tx in result.transactions:
        all_results[name]["transactions"].append({
            "date": str(tx.date),
            "description": tx.description,
            "amount": str(tx.amount),
            "currency": tx.currency,
            "direction": tx.direction,
            "counterparty": tx.counterparty,
            "reference_number": tx.reference_number,
            "notes": tx.notes,
        })

# Save to JSON
with open('final_test_results.json', 'w', encoding='utf-8') as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

print("Test complete. Results saved to final_test_results.json")
print(f"\n363-1: {all_results['363-1']['total_transactions']} transactions")
print(f"363-2: {all_results['363-2']['total_transactions']} transactions")
