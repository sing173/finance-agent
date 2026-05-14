"""Quick test with full logging."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath('.')), 'src'))
from finance_agent_backend.tools.icbc_receipt_grid_parser import ICBCReceiptGridParser
import glob

parser = ICBCReceiptGridParser()
pdf_path = glob.glob(r'C:\Users\dell\Desktop\finance agent\回单pdf\*363-1*.pdf')[0]

try:
    result = parser.parse(pdf_path)

    with open('quick_test.txt', 'w', encoding='utf-8') as f:
        f.write(f"Parsing: {pdf_path}\n")
        f.write(f"Total transactions: {len(result.transactions)}\n")
        f.write(f"Errors: {result.errors}\n\n")

        for i, tx in enumerate(result.transactions[:3], 1):
            f.write(f'Receipt {i}:\n')
            f.write(f'  Date: {tx.date}\n')
            f.write(f'  Description: {tx.description}\n')
            f.write(f'  Amount: {tx.amount}\n')
            f.write(f'  Direction: {tx.direction}\n')
            f.write(f'  Counterparty: {tx.counterparty}\n')
            f.write(f'  Ref No: {tx.reference_number}\n\n')

    print("File written successfully")
    print(f"Total transactions: {len(result.transactions)}")
    print(f"Errors: {result.errors}")

    # Print first transaction
    if result.transactions:
        tx = result.transactions[0]
        print(f"\nFirst receipt:")
        print(f"  Counterparty: {tx.counterparty}")
        print(f"  Amount: {tx.amount}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
