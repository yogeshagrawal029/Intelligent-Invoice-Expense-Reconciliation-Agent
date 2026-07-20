def draft_vendor_email(invoice_data, recon_row, duplicate_result=None, anomalies=None):
    """
    Draft vendor email based on reconciliation exception type,
    duplicate detection result, and anomaly result.
    """

    vendor_name = invoice_data.get("vendor_name") or "Vendor"
    invoice_number = invoice_data.get("invoice_number") or "N/A"
    po_number = invoice_data.get("po_number") or "N/A"
    invoice_amount = invoice_data.get("total_amount") or 0

    exception_type = recon_row.get("exception_type") or "GENERAL_EXCEPTION"
    issues = recon_row.get("issues") or "No detailed issue description available."

    duplicate_found = False

    if duplicate_result:
        duplicate_found = duplicate_result.get("duplicate_found", False)

    anomaly_types = []

    if anomalies:
        anomaly_types = [
            anomaly.get("type")
            for anomaly in anomalies
            if anomaly.get("type")
        ]

    # ---------------------------------------------------------
    # Case 1: Duplicate Payment
    # ---------------------------------------------------------

    if duplicate_found:
        subject = f"Possible Duplicate Payment for Invoice {invoice_number}"

        body = f"""
Dear {vendor_name} Team,

We are reviewing invoice {invoice_number} linked to purchase order {po_number}.

During payment reconciliation, our system found that this invoice may be associated with multiple bank transactions. This may indicate a duplicate payment or repeated payment reference.

Invoice Details:
Invoice Number: {invoice_number}
PO Number: {po_number}
Invoice Amount: ₹{invoice_amount}

Issue Identified:
Possible duplicate payment detected.

Please confirm whether this invoice was submitted or paid more than once. If there is any correction required, kindly share the updated invoice, credit note, or clarification.

Regards,
Accounts Payable Team
"""

        return subject, body


    # ---------------------------------------------------------
    # Case 2: Amount Mismatch
    # ---------------------------------------------------------

    if exception_type in ["AMOUNT_MISMATCH", "BANK_AMOUNT_MISMATCH"]:
        subject = f"Amount Mismatch Clarification for Invoice {invoice_number}"

        body = f"""
Dear {vendor_name} Team,

We are reviewing invoice {invoice_number} against purchase order {po_number}.

During reconciliation, we found an amount mismatch between the invoice, purchase order, or bank payment record.

Invoice Details:
Invoice Number: {invoice_number}
PO Number: {po_number}
Invoice Amount: ₹{invoice_amount}

Issue Details:
{issues}

Please verify the invoice amount and share a corrected invoice or supporting explanation for the difference.

Regards,
Accounts Payable Team
"""

        return subject, body


    # ---------------------------------------------------------
    # Case 3: Vendor Mismatch
    # ---------------------------------------------------------

    if exception_type == "VENDOR_MISMATCH":
        subject = f"Vendor Name Mismatch for Invoice {invoice_number}"

        body = f"""
Dear {vendor_name} Team,

We are validating invoice {invoice_number} against our approved purchase order records.

During reconciliation, our system found that the vendor name on the invoice does not fully match the vendor name available in the purchase order record.

Invoice Details:
Invoice Number: {invoice_number}
PO Number: {po_number}
Invoice Amount: ₹{invoice_amount}

Issue Details:
{issues}

Please confirm the correct vendor name and provide supporting documentation if the invoice was issued under a different legal entity, branch name, or business name.

Regards,
Accounts Payable Team
"""

        return subject, body


    # ---------------------------------------------------------
    # Case 4: Missing or Invalid PO
    # ---------------------------------------------------------

    if exception_type == "MISSING_OR_INVALID_PO" or "MISSING_PO" in anomaly_types:
        subject = f"Missing or Invalid PO Number for Invoice {invoice_number}"

        body = f"""
Dear {vendor_name} Team,

We are unable to process invoice {invoice_number} because the purchase order reference is missing or invalid.

Invoice Details:
Invoice Number: {invoice_number}
PO Number Found: {po_number}
Invoice Amount: ₹{invoice_amount}

Issue Details:
{issues}

Please share the valid purchase order number or resend the invoice with the correct PO reference so that we can continue processing.

Regards,
Accounts Payable Team
"""

        return subject, body


    # ---------------------------------------------------------
    # Case 5: Payment Not Found
    # ---------------------------------------------------------

    if exception_type == "PAYMENT_NOT_FOUND":
        subject = f"Payment Verification Required for Invoice {invoice_number}"

        body = f"""
Dear {vendor_name} Team,

We are reviewing invoice {invoice_number} against our bank payment records.

At this time, our reconciliation system could not find a matching payment transaction for this invoice.

Invoice Details:
Invoice Number: {invoice_number}
PO Number: {po_number}
Invoice Amount: ₹{invoice_amount}

Issue Details:
{issues}

Please confirm whether payment has already been received at your end or if the invoice is still pending for payment processing.

Regards,
Accounts Payable Team
"""

        return subject, body


    # ---------------------------------------------------------
    # Case 6: High Tax Anomaly
    # ---------------------------------------------------------

    if "HIGH_TAX" in anomaly_types:
        subject = f"Tax Clarification Required for Invoice {invoice_number}"

        body = f"""
Dear {vendor_name} Team,

We are reviewing invoice {invoice_number} and found that the tax amount appears unusually high compared to the invoice subtotal.

Invoice Details:
Invoice Number: {invoice_number}
PO Number: {po_number}
Invoice Amount: ₹{invoice_amount}

Issue Identified:
The tax amount appears higher than the expected threshold.

Please verify the tax calculation and share the tax breakup, corrected invoice, or supporting tax documentation.

Regards,
Accounts Payable Team
"""

        return subject, body


    # ---------------------------------------------------------
    # Case 7: High Value Invoice
    # ---------------------------------------------------------

    if "HIGH_VALUE_INVOICE" in anomaly_types:
        subject = f"High Value Invoice Review Required for {invoice_number}"

        body = f"""
Dear {vendor_name} Team,

Invoice {invoice_number} has been flagged for additional review because the invoice amount is above the high-value review threshold.

Invoice Details:
Invoice Number: {invoice_number}
PO Number: {po_number}
Invoice Amount: ₹{invoice_amount}

Please share supporting documents, approval reference, contract details, or service completion proof for this invoice.

Regards,
Accounts Payable Team
"""

        return subject, body


    # ---------------------------------------------------------
    # Case 8: Unknown Vendor
    # ---------------------------------------------------------

    if "UNKNOWN_VENDOR" in anomaly_types:
        subject = f"Vendor Verification Required for Invoice {invoice_number}"

        body = f"""
Dear {vendor_name} Team,

We are reviewing invoice {invoice_number}, but the vendor name could not be verified against our approved vendor records.

Invoice Details:
Invoice Number: {invoice_number}
PO Number: {po_number}
Invoice Amount: ₹{invoice_amount}

Please share the correct registered vendor name, GST or tax registration details, and any supporting vendor onboarding reference if applicable.

Regards,
Accounts Payable Team
"""

        return subject, body


    # ---------------------------------------------------------
    # Case 9: Invalid Amount
    # ---------------------------------------------------------

    if "INVALID_AMOUNT" in anomaly_types:
        subject = f"Invalid Invoice Amount for Invoice {invoice_number}"

        body = f"""
Dear {vendor_name} Team,

We are unable to process invoice {invoice_number} because the invoice amount appears to be invalid, zero, or negative.

Invoice Details:
Invoice Number: {invoice_number}
PO Number: {po_number}
Invoice Amount: ₹{invoice_amount}

Please verify and resend the invoice with the correct amount.

Regards,
Accounts Payable Team
"""

        return subject, body


    # ---------------------------------------------------------
    # Case 10: Missing Invoice Date
    # ---------------------------------------------------------

    if "MISSING_INVOICE_DATE" in anomaly_types:
        subject = f"Missing Invoice Date for Invoice {invoice_number}"

        body = f"""
Dear {vendor_name} Team,

We are reviewing invoice {invoice_number}, but the invoice date could not be identified.

Invoice Details:
Invoice Number: {invoice_number}
PO Number: {po_number}
Invoice Amount: ₹{invoice_amount}

Please confirm the correct invoice date or resend the invoice with complete invoice details.

Regards,
Accounts Payable Team
"""

        return subject, body


    # ---------------------------------------------------------
    # Default General Exception Email
    # ---------------------------------------------------------

    subject = f"Clarification Required for Invoice {invoice_number}"

    body = f"""
Dear {vendor_name} Team,

We are reviewing invoice {invoice_number} against purchase order {po_number}.

Our reconciliation system identified an exception that requires clarification.

Invoice Details:
Invoice Number: {invoice_number}
PO Number: {po_number}
Invoice Amount: ₹{invoice_amount}

Issue Type:
{exception_type}

Issue Details:
{issues}

Please review and share clarification or supporting documents.

Regards,
Accounts Payable Team
"""

    return subject, body