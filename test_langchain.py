from src.ai_agent import generate_langchain_review


invoice_data = {
    "invoice_number": "INV9002",
    "vendor_name": "Global Stationery",
    "po_number": "PO1002",
    "total_amount": 16000
}

recon_row = {
    "status": "EXCEPTION",
    "exception_type": "AMOUNT_MISMATCH",
    "issues": "Invoice amount 16000 does not match PO amount 15000."
}

duplicate_result = {
    "duplicate_found": False,
    "matched_count": 1
}

anomalies = []

result = generate_langchain_review(
    invoice_data,
    recon_row,
    duplicate_result,
    anomalies
)

print(result)