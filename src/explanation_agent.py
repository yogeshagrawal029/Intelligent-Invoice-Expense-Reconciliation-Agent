def generate_explanation(recon_row, duplicate_result=None, anomalies=None):
    invoice_number = recon_row.get("invoice_number")
    vendor_name = recon_row.get("vendor_name")
    po_number = recon_row.get("po_number")
    invoice_amount = recon_row.get("invoice_amount")
    status = recon_row.get("status")
    exception_type = recon_row.get("exception_type")
    issues = recon_row.get("issues")

    if status == "MATCHED":
        return (
            f"Invoice {invoice_number} from {vendor_name} is successfully matched. "
            f"The invoice is linked to purchase order {po_number}, and the payment amount "
            f"of ₹{invoice_amount} matches the invoice amount. No human review is required."
        )

    explanation = (
        f"Invoice {invoice_number} from {vendor_name} requires review. "
        f"The system found the following issue: {exception_type}. "
        f"Details: {issues} "
    )

    if duplicate_result and duplicate_result.get("duplicate_found"):
        explanation += (
            f"The same invoice appears to match "
            f"{duplicate_result.get('matched_count')} bank transactions, "
            f"which may indicate a duplicate payment. "
        )

    if anomalies:
        anomaly_messages = [a["message"] for a in anomalies]
        explanation += "Additional anomalies found: " + " ".join(anomaly_messages)

    explanation += " Recommended action: route this case to a human approver."

    return explanation