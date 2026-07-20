from src.invoice_parser import parse_invoice
from src.matcher import three_way_match
from src.duplicate_detector import detect_duplicate_payment
from src.anomaly_detector import detect_anomalies
from src.explanation_agent import generate_explanation


def prepare_exception_summary(recon_row, duplicate_result, anomalies):
    exception_summary = []

    if recon_row and recon_row.get("status") == "EXCEPTION":
        exception_summary.append(
            {
                "source": "Three-Way Match",
                "issue": recon_row.get("exception_type"),
                "details": recon_row.get("issues")
            }
        )

    if duplicate_result and duplicate_result.get("duplicate_found"):
        exception_summary.append(
            {
                "source": "Duplicate Detection",
                "issue": "DUPLICATE_PAYMENT",
                "details": f"{duplicate_result.get('matched_count')} matching bank transactions found."
            }
        )

    if anomalies:
        for anomaly in anomalies:
            exception_summary.append(
                {
                    "source": "Anomaly Detection",
                    "issue": anomaly.get("type"),
                    "details": anomaly.get("message")
                }
            )

    return exception_summary


def calculate_human_review_flag(recon_row, duplicate_result, anomalies):
    if recon_row and recon_row.get("status") == "EXCEPTION":
        return True

    if duplicate_result and duplicate_result.get("duplicate_found"):
        return True

    if anomalies:
        return True

    return False


def process_invoice(invoice_file, po_df, bank_df):
    invoice_data = parse_invoice(invoice_file)

    recon_result = three_way_match(
        invoice_data,
        po_df,
        bank_df
    )

    recon_row = recon_result.iloc[0].to_dict()

    duplicate_result = detect_duplicate_payment(
        invoice_data,
        bank_df
    )

    anomalies = detect_anomalies(invoice_data)

    requires_human_review = calculate_human_review_flag(
        recon_row,
        duplicate_result,
        anomalies
    )

    explanation = generate_explanation(
        recon_row,
        duplicate_result,
        anomalies
    )

    exception_summary = prepare_exception_summary(
        recon_row,
        duplicate_result,
        anomalies
    )

    result_record = {
        "file_name": invoice_file.name,
        "invoice_number": invoice_data.get("invoice_number"),
        "vendor_name": invoice_data.get("vendor_name"),
        "po_number": invoice_data.get("po_number"),
        "invoice_date": invoice_data.get("invoice_date"),
        "subtotal": invoice_data.get("subtotal"),
        "tax": invoice_data.get("tax"),
        "invoice_amount": invoice_data.get("total_amount"),
        "status": recon_row.get("status"),
        "exception_type": recon_row.get("exception_type"),
        "issues": recon_row.get("issues"),
        "matched_po": recon_row.get("matched_po"),
        "matched_transaction": recon_row.get("matched_transaction"),
        "duplicate_found": duplicate_result.get("duplicate_found"),
        "duplicate_match_count": duplicate_result.get("matched_count"),
        "anomaly_count": len(anomalies),
        "anomalies": " | ".join([a.get("type", "") for a in anomalies]) if anomalies else "NONE",
        "requires_human_review": requires_human_review,
        "rule_based_explanation": explanation,
        "raw_text": invoice_data.get("raw_text", ""),
        "invoice_data": invoice_data,
        "recon_row": recon_row,
        "duplicate_result": duplicate_result,
        "anomaly_list": anomalies,
        "exception_summary": exception_summary
    }

    return result_record