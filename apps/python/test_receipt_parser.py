"""Test the rewritten icbc_receipt_grid_parser.py on 363-1 and 363-2."""
import sys
import os
# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from finance_agent_backend.tools.icbc_receipt_grid_parser import ICBCReceiptGridParser
import glob, json

parser = ICBCReceiptGridParser()

# Test 363-1 and 363-2
pdf_files = {
    "363-1": glob.glob(r'C:\Users\dell\Desktop\finance agent\回单pdf\*363-1*.pdf')[0],
    "363-2": glob.glob(r'C:\Users\dell\Desktop\finance agent\回单pdf\*363-2*.pdf')[0],
}

for name, pdf_path in pdf_files.items():
    print(f"\n{'='*60}")
    print(f"Parsing: {name}")
    print(f"File: {pdf_path}")
    print(f"{'='*60}")

    # Manually run with debug output
    import fitz
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    doc = fitz.open('pdf', pdf_bytes)

    all_transactions = []
    for page_num in range(len(doc)):
        print(f"\n--- Page {page_num + 1} ---")
        img = parser._render_page(doc, page_num)
        h_coords, v_coords = parser._detect_table_lines(img)
        grid_rows = parser._build_grid(h_coords, v_coords)
        blocks = parser._ocr_page_data(img)
        cell_grid = parser._assign_blocks(blocks, grid_rows)

        # Flatten cells
        all_cells = parser._flatten_cells(cell_grid, h_coords, v_coords)
        print(f"  Non-empty cells: {len(all_cells)}")

        # Split receipts
        receipts = parser._split_receipts(all_cells)
        print(f"  Receipts found: {len(receipts)}")

        # Show title rows
        title_rows = sorted(set(
            c["row"] for c in all_cells
            if "网上银行电子回单" in c["text"] or "电子回单号码" in c["text"]
        ))
        print(f"  Title rows: {title_rows}")

        # Show cells in each receipt
        for ri, receipt_cells in enumerate(receipts):
            print(f"  Receipt {ri+1} rows: {sorted(set(c['row'] for c in receipt_cells))}")

        # Parse each receipt
        for receipt_cells in receipts:
            fields = parser._cells_to_fields(receipt_cells)
            tx = parser._fields_to_transaction(fields)
            if tx:
                all_transactions.append(tx)

    doc.close()

    print(f"\n{'='*60}")
    print(f"Total transactions: {len(all_transactions)}")
    print(f"{'='*60}")

    print(f"\nTransactions:")
    for i, tx in enumerate(all_transactions, 1):
        print(f"\n--- Receipt {i} ---")
        print(f"  Date: {tx.date}")
        print(f"  Description: {tx.description}")
        print(f"  Amount: {tx.amount} {tx.currency}")
        print(f"  Direction: {tx.direction}")
        print(f"  Counterparty: {tx.counterparty}")
        print(f"  Ref No: {tx.reference_number}")
        print(f"  Notes: {tx.notes}")

    # Save to JSON for inspection
    import json
    output_file = f"{name}_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "transactions": [tx.__dict__ for tx in all_transactions],
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✓ Saved to {output_file}")

    print(f"\nTotal transactions: {len(result.transactions)}")
    print(f"Errors: {result.errors}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Statement date: {result.statement_date}")

    print(f"\nTransactions:")
    for i, tx in enumerate(result.transactions, 1):
        print(f"\n--- Receipt {i} ---")
        print(f"  Date: {tx.date}")
        print(f"  Description: {tx.description}")
        print(f"  Amount: {tx.amount} {tx.currency}")
        print(f"  Direction: {tx.direction}")
        print(f"  Counterparty: {tx.counterparty}")
        print(f"  Ref No: {tx.reference_number}")
        print(f"  Notes: {tx.notes}")

    # Save to JSON for inspection
    output_file = f"{name}_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "transactions": [tx.__dict__ for tx in result.transactions],
            "errors": result.errors,
            "confidence": result.confidence,
            "statement_date": str(result.statement_date) if result.statement_date else None,
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✓ Saved to {output_file}")
