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


def find_po_match(invoice_data, po_df):
    po_number = normalize_text(invoice_data.get("po_number"))

    if po_number == "":
        return None

    po_df = po_df.copy()
    po_df["po_number_norm"] = po_df["po_number"].apply(normalize_text)

    matched_po = po_df[po_df["po_number_norm"] == po_number]

    if matched_po.empty:
        return None

    return matched_po.iloc[0].to_dict()


def find_bank_match(invoice_data, bank_df):
    invoice_number = normalize_text(invoice_data.get("invoice_number"))
    vendor_name = normalize_text(invoice_data.get("vendor_name"))
    invoice_amount = normalize_amount(invoice_data.get("total_amount"))

    possible_matches = []

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

        if invoice_found or vendor_found or amount_found:
            possible_matches.append(txn.to_dict())

    if len(possible_matches) == 0:
        return None

    return possible_matches[0]


def three_way_match(invoice_data, po_df, bank_df):
    results = []

    po_match = find_po_match(invoice_data, po_df)
    bank_match = find_bank_match(invoice_data, bank_df)

    status = "MATCHED"
    exception_type = "NONE"
    requires_review = False
    issues = []

    invoice_amount = normalize_amount(invoice_data.get("total_amount"))
    invoice_vendor = normalize_text(invoice_data.get("vendor_name"))

    if po_match is None:
        status = "EXCEPTION"
        exception_type = "MISSING_OR_INVALID_PO"
        requires_review = True
        issues.append("No matching purchase order was found for this invoice.")
    else:
        po_amount = normalize_amount(po_match.get("total_amount"))
        po_vendor = normalize_text(po_match.get("vendor_name"))

        if invoice_amount != po_amount:
            status = "EXCEPTION"
            exception_type = "AMOUNT_MISMATCH"
            requires_review = True
            issues.append(
                f"Invoice amount {invoice_amount} does not match PO amount {po_amount}."
            )

        if invoice_vendor not in po_vendor and po_vendor not in invoice_vendor:
            status = "EXCEPTION"
            exception_type = "VENDOR_MISMATCH"
            requires_review = True
            issues.append(
                f"Invoice vendor '{invoice_data.get('vendor_name')}' does not match PO vendor '{po_match.get('vendor_name')}'."
            )

    if bank_match is None:
        status = "EXCEPTION"
        if exception_type == "NONE":
            exception_type = "PAYMENT_NOT_FOUND"
        requires_review = True
        issues.append("No matching bank payment was found for this invoice.")
    else:
        bank_amount = 0

        if "amount" in bank_match:
            bank_amount = normalize_amount(bank_match.get("amount"))
        elif "debit" in bank_match:
            bank_amount = normalize_amount(bank_match.get("debit"))

        if invoice_amount != bank_amount:
            status = "EXCEPTION"
            exception_type = "BANK_AMOUNT_MISMATCH"
            requires_review = True
            issues.append(
                f"Invoice amount {invoice_amount} does not match bank payment amount {bank_amount}."
            )

    if not issues:
        issues.append("Invoice, purchase order, and bank payment are matching correctly.")

    result = {
        "invoice_number": invoice_data.get("invoice_number"),
        "vendor_name": invoice_data.get("vendor_name"),
        "po_number": invoice_data.get("po_number"),
        "invoice_amount": invoice_amount,
        "matched_po": po_match.get("po_number") if po_match else None,
        "matched_transaction": bank_match.get("transaction_id") if bank_match else None,
        "status": status,
        "exception_type": exception_type,
        "requires_review": requires_review,
        "issues": " | ".join(issues)
    }

    results.append(result)

    return pd.DataFrame(results)


def match_records(po_df, bank_df):
    results = []

    for _, po in po_df.iterrows():

        vendor = po["vendor_name"]

        matches = bank_df[
            bank_df["vendor_name"] == vendor
        ]

        if matches.empty:

            results.append({
                "vendor": vendor,
                "status": "NO PAYMENT FOUND"
            })

        else:

            payment = matches.iloc[0]

            if po["total_amount"] == payment["amount"]:

                status = "MATCHED"

            else:

                status = "AMOUNT MISMATCH"

            results.append({
                "vendor": vendor,
                "status": status
            })

    return pd.DataFrame(results)