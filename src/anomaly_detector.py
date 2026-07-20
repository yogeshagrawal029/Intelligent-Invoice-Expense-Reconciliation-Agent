def detect_anomalies(invoice_data):
    anomalies = []

    total_amount = invoice_data.get("total_amount", 0)
    subtotal = invoice_data.get("subtotal", 0)
    tax = invoice_data.get("tax", 0)
    po_number = invoice_data.get("po_number")
    vendor_name = invoice_data.get("vendor_name")
    invoice_date = invoice_data.get("invoice_date")

    if total_amount <= 0:
        anomalies.append({
            "type": "INVALID_AMOUNT",
            "message": "Invoice total amount is zero or negative."
        })

    if not po_number:
        anomalies.append({
            "type": "MISSING_PO",
            "message": "Invoice does not contain a purchase order number."
        })

    if not vendor_name:
        anomalies.append({
            "type": "MISSING_VENDOR",
            "message": "Vendor name could not be extracted from invoice."
        })

    if not invoice_date:
        anomalies.append({
            "type": "MISSING_INVOICE_DATE",
            "message": "Invoice date could not be extracted."
        })

    if subtotal > 0:
        tax_percentage = (tax / subtotal) * 100

        if tax_percentage > 30:
            anomalies.append({
                "type": "HIGH_TAX",
                "message": f"Tax percentage is unusually high: {tax_percentage:.2f}%."
            })

    if total_amount > 1000000:
        anomalies.append({
            "type": "HIGH_VALUE_INVOICE",
            "message": "Invoice amount is unusually high and needs review."
        })

    return anomalies