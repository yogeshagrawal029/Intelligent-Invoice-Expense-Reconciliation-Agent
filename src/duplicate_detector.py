import pandas as pd


def normalize_text(value):
    if pd.isna(value):
        return ""
    return str(value).lower().strip()


def normalize_amount(value):
    try:
        return float(value)
    except:
        return 0.0


def detect_duplicate_payment(invoice_data, bank_df):
    invoice_number = normalize_text(invoice_data.get("invoice_number"))
    vendor_name = normalize_text(invoice_data.get("vendor_name"))
    invoice_amount = normalize_amount(invoice_data.get("total_amount"))

    matches = []

    for _, txn in bank_df.iterrows():
        txn_text = " ".join([str(x) for x in txn.values])
        txn_text_norm = normalize_text(txn_text)

        amount = 0

        if "amount" in bank_df.columns:
            amount = normalize_amount(txn.get("amount"))
        elif "debit" in bank_df.columns:
            amount = normalize_amount(txn.get("debit"))

        invoice_found = invoice_number != "" and invoice_number in txn_text_norm
        vendor_found = vendor_name != "" and vendor_name in txn_text_norm
        amount_found = invoice_amount == amount

        if invoice_found or (vendor_found and amount_found):
            matches.append(txn.to_dict())

    duplicate_found = len(matches) > 1

    return {
        "duplicate_found": duplicate_found,
        "matched_count": len(matches),
        "matched_transactions": matches
    }