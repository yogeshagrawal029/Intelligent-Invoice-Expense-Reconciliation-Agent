import streamlit as st
import pandas as pd
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.po_parser import load_purchase_orders, validate_po_columns
from src.bank_parser import load_bank_statement, validate_bank_columns
from src.invoice_parser import parse_invoice
from src.matcher import match_records, three_way_match
from src.duplicate_detector import detect_duplicate_payment
from src.anomaly_detector import detect_anomalies
from src.explanation_agent import generate_explanation
from src.approval_workflow import save_approval_decision
from src.email_drafter import draft_vendor_email
from src.ai_agent import generate_langchain_review, generate_langchain_email


# ---------------------------------------------------------
# Email Sending Helper Functions
# ---------------------------------------------------------

def parse_email_list(email_text):
    """
    Converts comma-separated email text into a clean Python list.

    Example:
    vendor@test.com, manager@test.com

    Output:
    ["vendor@test.com", "manager@test.com"]
    """

    if not email_text:
        return []

    return [
        email.strip()
        for email in email_text.split(",")
        if email.strip()
    ]


def send_email_via_smtp(
        smtp_server,
        smtp_port,
        sender_email,
        sender_password,
        to_emails,
        cc_emails,
        bcc_emails,
        subject,
        body
):
    """
    Sends email using SMTP with TLS.

    Works with:
    - Gmail SMTP
    - Outlook SMTP
    - Microsoft 365 SMTP
    - Company SMTP relay
    """

    if not to_emails:
        raise ValueError("Please enter at least one recipient in To field.")

    if not sender_email:
        raise ValueError("Sender email is required.")

    if not sender_password:
        raise ValueError("Sender password or app password is required.")

    if not subject:
        raise ValueError("Email subject is required.")

    if not body:
        raise ValueError("Email body is required.")

    msg = MIMEMultipart()

    msg["From"] = sender_email
    msg["To"] = ", ".join(to_emails)
    msg["Cc"] = ", ".join(cc_emails)
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    recipients = to_emails + cc_emails + bcc_emails

    with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(
            sender_email,
            recipients,
            msg.as_string()
        )

    return {
        "status": "SUCCESS",
        "sent_to": to_emails,
        "cc": cc_emails,
        "bcc": bcc_emails
    }


def get_secret_value(key, default_value=""):
    """
    Reads Streamlit secrets safely.

    If .streamlit/secrets.toml is not available,
    it returns the default value.
    """

    try:
        return st.secrets.get(key, default_value)
    except Exception:
        return default_value


def render_send_email_section(
        section_key,
        default_subject="",
        default_body="",
        default_to=""
):
    """
    Reusable email sender UI.

    Includes:
    - To
    - CC
    - BCC
    - Subject
    - Body
    - SMTP settings
    - Send Email button
    """

    st.subheader("Send Email")

    with st.expander("Recipient Details", expanded=True):

        to_email = st.text_input(
            "To",
            value=default_to,
            placeholder="vendor@example.com",
            key=f"{section_key}_to"
        )

        cc_email = st.text_input(
            "CC",
            placeholder="manager@example.com, finance@example.com",
            key=f"{section_key}_cc"
        )

        bcc_email = st.text_input(
            "BCC",
            placeholder="audit@example.com",
            key=f"{section_key}_bcc"
        )

    email_subject = st.text_input(
        "Email Subject",
        value=default_subject or "",
        key=f"{section_key}_subject"
    )

    email_body = st.text_area(
        "Email Body",
        value=default_body or "",
        height=300,
        key=f"{section_key}_body"
    )

    with st.expander("SMTP Settings", expanded=False):

        st.info(
            "For Gmail use smtp.gmail.com and an App Password. "
            "For Microsoft 365 or Outlook use smtp.office365.com and port 587."
        )

        smtp_server = st.text_input(
            "SMTP Server",
            value=get_secret_value("SMTP_SERVER", "smtp.office365.com"),
            key=f"{section_key}_smtp_server"
        )

        smtp_port = st.number_input(
            "SMTP Port",
            min_value=1,
            max_value=65535,
            value=int(get_secret_value("SMTP_PORT", 587)),
            key=f"{section_key}_smtp_port"
        )

        sender_email = st.text_input(
            "Sender Email",
            value=get_secret_value("SMTP_EMAIL", ""),
            key=f"{section_key}_sender_email"
        )

        sender_password = st.text_input(
            "Sender Password / App Password",
            value=get_secret_value("SMTP_PASSWORD", ""),
            type="password",
            key=f"{section_key}_sender_password"
        )

    if st.button("Send Email", key=f"{section_key}_send_button"):

        try:
            result = send_email_via_smtp(
                smtp_server=smtp_server,
                smtp_port=smtp_port,
                sender_email=sender_email,
                sender_password=sender_password,
                to_emails=parse_email_list(to_email),
                cc_emails=parse_email_list(cc_email),
                bcc_emails=parse_email_list(bcc_email),
                subject=email_subject,
                body=email_body
            )

            st.success("Email sent successfully.")
            st.json(result)

        except Exception as e:
            st.error(f"Email sending failed: {e}")


# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------

st.set_page_config(
    page_title="Invoice Reconciliation Agent",
    page_icon="📄",
    layout="wide"
)


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.title("Intelligent Invoice & Expense Reconciliation Agent")

st.write(
    "This application automates invoice reconciliation using purchase orders, "
    "bank statements, invoice parsing, duplicate detection, anomaly detection, "
    "human approval workflow, email sending, and LangChain-powered AI review."
    " Designed by: Yogesh Agrawal"
)


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------

st.sidebar.title("Project Workflow")

st.sidebar.markdown(
    """
    ### Workflow

    1. Upload Purchase Order CSV 
    2. Upload Bank Statement CSV 
    3. Select Single or Multiple Invoice Mode 
    4. Upload Invoice File or Files 
    5. Extract Invoice Data 
    6. Perform Three-Way Matching 
    7. Detect Duplicate Payments 
    8. Detect Anomalies 
    9. Generate Rule-Based Explanation 
    10. Generate LangChain AI Review 
    11. Human Approval 
    12. Generate Vendor Email Draft 
    13. Send Email with To, CC, BCC 
    14. Download Report 
    """
)

st.sidebar.info("Supported invoice files: TXT, PDF, PNG, JPG, JPEG")


# ---------------------------------------------------------
# Session State
# ---------------------------------------------------------

if "approval_saved" not in st.session_state:
    st.session_state.approval_saved = False

if "last_decision" not in st.session_state:
    st.session_state.last_decision = None

if "single_ai_review" not in st.session_state:
    st.session_state.single_ai_review = ""

if "single_ai_email" not in st.session_state:
    st.session_state.single_ai_email = ""

if "bulk_results" not in st.session_state:
    st.session_state.bulk_results = []

if "bulk_ai_review" not in st.session_state:
    st.session_state.bulk_ai_review = {}

if "bulk_ai_email" not in st.session_state:
    st.session_state.bulk_ai_email = {}


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

def show_required_column_help():
    with st.expander("Required CSV Format Help"):
        st.markdown(
            """
            ### Purchase Order CSV required columns

            ```text
            po_number,vendor_name,total_amount,status
            ```

            Example:

            ```csv
            po_number,vendor_name,total_amount,status
            PO1001,ABC Technologies,100000,Approved
            PO1002,Global Stationery,15000,Approved
            ```

            ### Bank Statement CSV required columns

            ```text
            transaction_id,vendor_name,amount,description,date
            ```

            Example:

            ```csv
            transaction_id,vendor_name,amount,description,date
            TXN001,ABC Technologies,100000,Payment INV9001,2026-07-10
            TXN002,Global Stationery,16000,Payment INV9002,2026-07-11
            ```
            """
        )


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


def process_one_invoice(invoice_file, po_df, bank_df):
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
        "anomalies": " | ".join(
            [a.get("type", "") for a in anomalies]
        ) if anomalies else "NONE",
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


def show_dashboard(results_df):
    total_invoices = len(results_df)
    matched_count = len(results_df[results_df["status"] == "MATCHED"])
    exception_count = len(results_df[results_df["status"] == "EXCEPTION"])
    error_count = len(results_df[results_df["status"] == "ERROR"])
    duplicate_count = len(results_df[results_df["duplicate_found"] == True])
    anomaly_count = len(results_df[results_df["anomaly_count"] > 0])
    human_review_count = len(results_df[results_df["requires_human_review"] == True])

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Invoices", total_invoices)

    with col2:
        st.metric("Matched", matched_count)

    with col3:
        st.metric("Exceptions", exception_count)

    with col4:
        st.metric("Human Review", human_review_count)

    col5, col6, col7 = st.columns(3)

    with col5:
        st.metric("Duplicates", duplicate_count)

    with col6:
        st.metric("Anomalies", anomaly_count)

    with col7:
        st.metric("Processing Errors", error_count)


# ---------------------------------------------------------
# Upload Section
# ---------------------------------------------------------

st.header("1. Upload Input Files")

col1, col2 = st.columns(2)

with col1:
    po_file = st.file_uploader(
        "Upload Purchase Order CSV",
        type=["csv"],
        key="po_file"
    )

with col2:
    bank_file = st.file_uploader(
        "Upload Bank Statement CSV",
        type=["csv"],
        key="bank_file"
    )


upload_mode = st.radio(
    "Select Invoice Upload Mode",
    ["Single Invoice", "Multiple Invoices"]
)


if upload_mode == "Single Invoice":
    invoice_file = st.file_uploader(
        "Upload Single Invoice File",
        type=["txt", "pdf", "png", "jpg", "jpeg"],
        key="single_invoice_file"
    )

    invoice_files = None

else:
    invoice_files = st.file_uploader(
        "Upload Multiple Invoice Files",
        type=["txt", "pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="multiple_invoice_files"
    )

    invoice_file = None


# ---------------------------------------------------------
# Initialize Variables
# ---------------------------------------------------------

po_df = None
bank_df = None
po_valid = False
bank_valid = False


# ---------------------------------------------------------
# Purchase Order Processing
# ---------------------------------------------------------

if po_file is not None:
    st.header("2. Purchase Order Data")

    try:
        po_df = load_purchase_orders(po_file)
        missing_po_columns = validate_po_columns(po_df)

        if missing_po_columns:
            st.error(
                f"Purchase Order CSV is missing required columns: {missing_po_columns}"
            )
            show_required_column_help()
        else:
            po_valid = True
            st.success("Purchase Order file loaded successfully.")
            st.dataframe(po_df, use_container_width=True)
            st.write("Total Purchase Orders:", len(po_df))

    except Exception as e:
        st.error(f"Error while reading Purchase Order file: {e}")


# ---------------------------------------------------------
# Bank Statement Processing
# ---------------------------------------------------------

if bank_file is not None:
    st.header("3. Bank Statement Data")

    try:
        bank_df = load_bank_statement(bank_file)
        missing_bank_columns = validate_bank_columns(bank_df)

        if missing_bank_columns:
            st.error(
                f"Bank Statement CSV is missing required columns: {missing_bank_columns}"
            )
            show_required_column_help()
        else:
            bank_valid = True
            st.success("Bank Statement file loaded successfully.")
            st.dataframe(bank_df, use_container_width=True)
            st.write("Total Bank Transactions:", len(bank_df))

    except Exception as e:
        st.error(f"Error while reading Bank Statement file: {e}")


# ---------------------------------------------------------
# Basic PO vs Bank Matching
# ---------------------------------------------------------

if po_valid and bank_valid and po_df is not None and bank_df is not None:
    st.header("4. Basic PO vs Bank Matching")

    try:
        basic_result = match_records(po_df, bank_df)
        st.dataframe(basic_result, use_container_width=True)

    except Exception as e:
        st.error(f"Error during basic PO vs Bank matching: {e}")


# ---------------------------------------------------------
# Single Invoice Mode
# ---------------------------------------------------------

if (
    upload_mode == "Single Invoice"
    and po_valid
    and bank_valid
    and invoice_file is not None
    and po_df is not None
    and bank_df is not None
):

    st.header("5. Single Invoice Reconciliation")

    try:
        result_record = process_one_invoice(
            invoice_file,
            po_df,
            bank_df
        )

        invoice_data = result_record["invoice_data"]
        recon_row = result_record["recon_row"]
        duplicate_result = result_record["duplicate_result"]
        anomalies = result_record["anomaly_list"]
        requires_human_review = result_record["requires_human_review"]
        explanation = result_record["rule_based_explanation"]

        st.subheader("Extracted Invoice Data")

        invoice_display = pd.DataFrame(
            [
                {
                    "file_name": result_record.get("file_name"),
                    "invoice_number": result_record.get("invoice_number"),
                    "vendor_name": result_record.get("vendor_name"),
                    "po_number": result_record.get("po_number"),
                    "invoice_date": result_record.get("invoice_date"),
                    "subtotal": result_record.get("subtotal"),
                    "tax": result_record.get("tax"),
                    "invoice_amount": result_record.get("invoice_amount"),
                }
            ]
        )

        st.dataframe(invoice_display, use_container_width=True)

        with st.expander("Show Raw Extracted Invoice Text"):
            st.text(result_record.get("raw_text", ""))

        st.header("6. Dashboard Summary")

        single_df = pd.DataFrame(
            [
                {
                    "status": result_record.get("status"),
                    "duplicate_found": result_record.get("duplicate_found"),
                    "anomaly_count": result_record.get("anomaly_count"),
                    "requires_human_review": result_record.get("requires_human_review")
                }
            ]
        )

        show_dashboard(single_df)

        st.header("7. Three-Way Reconciliation Result")

        recon_df = pd.DataFrame([recon_row])
        st.dataframe(recon_df, use_container_width=True)

        if recon_row.get("status") == "MATCHED":
            st.success("Invoice, Purchase Order, and Bank Payment are matched successfully.")
        else:
            st.error(f"Exception found: {recon_row.get('exception_type')}")

        st.header("8. Duplicate Payment Detection")

        if duplicate_result.get("duplicate_found"):
            st.error(
                f"Duplicate payment detected. "
                f"{duplicate_result.get('matched_count')} bank transactions may match this invoice."
            )

            duplicate_df = pd.DataFrame(
                duplicate_result.get("matched_transactions", [])
            )

            st.dataframe(duplicate_df, use_container_width=True)
        else:
            st.success("No duplicate payment found.")

        st.header("9. Anomaly Detection")

        if anomalies:
            anomaly_df = pd.DataFrame(anomalies)
            st.warning("One or more anomalies were detected.")
            st.dataframe(anomaly_df, use_container_width=True)
        else:
            st.success("No anomaly found.")

        st.header("10. Exception Summary")

        exception_summary = result_record.get("exception_summary", [])

        if exception_summary:
            st.dataframe(
                pd.DataFrame(exception_summary),
                use_container_width=True
            )
        else:
            st.success("No exception found for this invoice.")

        st.header("11. Rule-Based Explanation")
        st.info(explanation)

        st.header("12. LangChain AI Reconciliation Review")

        if st.button("Generate LangChain AI Review"):
            try:
                ai_review = generate_langchain_review(
                    invoice_data,
                    recon_row,
                    duplicate_result,
                    anomalies
                )

                st.session_state.single_ai_review = ai_review

            except Exception as e:
                st.error(f"LangChain AI Review failed: {e}")

        if st.session_state.single_ai_review:
            st.info(st.session_state.single_ai_review)

        st.header("13. Human Approval Queue")

        if requires_human_review:
            st.warning("This invoice requires human review.")
        else:
            st.success("This invoice does not require human review.")

        decision = st.selectbox(
            "Select Review Decision",
            [
                "Pending",
                "Approve",
                "Reject",
                "Ask Vendor",
                "Escalate to Finance Manager",
                "Mark as Duplicate"
            ],
            key="single_decision"
        )

        comment = st.text_area(
            "Reviewer Comment",
            key="single_comment"
        )

        if st.button("Save Approval Decision", key="single_save_decision"):
            try:
                saved_record = save_approval_decision(
                    invoice_data.get("invoice_number"),
                    decision,
                    comment
                )

                st.session_state.approval_saved = True
                st.session_state.last_decision = saved_record

                st.success("Approval decision saved successfully.")
                st.json(saved_record)

            except Exception as e:
                st.error(f"Error while saving approval decision: {e}")

        if st.session_state.approval_saved and st.session_state.last_decision:
            st.info("Last saved approval decision:")
            st.json(st.session_state.last_decision)

        st.header("14. Vendor Email Draft and Send Email")

        if requires_human_review:
            st.subheader("Rule-Based Vendor Email")

            subject, body = draft_vendor_email(
                invoice_data,
                recon_row,
                duplicate_result,
                anomalies
            )

            st.text_input(
                "Rule-Based Email Subject",
                value=subject,
                key="single_rule_email_subject"
            )

            st.text_area(
                "Rule-Based Email Body",
                value=body,
                height=250,
                key="single_rule_email_body"
            )

            st.subheader("LangChain AI Vendor Email")

            if st.button("Generate LangChain AI Email"):
                try:
                    ai_email = generate_langchain_email(
                        invoice_data,
                        recon_row,
                        duplicate_result,
                        anomalies
                    )

                    st.session_state.single_ai_email = ai_email

                except Exception as e:
                    st.error(f"LangChain AI Email failed: {e}")

            if st.session_state.single_ai_email:
                st.text_area(
                    "AI Generated Email",
                    value=st.session_state.single_ai_email,
                    height=300,
                    key="single_ai_email_text"
                )

            email_body_to_send = (
                st.session_state.single_ai_email
                if st.session_state.single_ai_email
                else body
            )

            render_send_email_section(
                section_key="single_invoice_email",
                default_subject=subject,
                default_body=email_body_to_send,
                default_to=""
            )

        else:
            st.success("No vendor email required because this invoice has no exception.")

        st.header("15. Download Single Invoice Report")

        download_record = result_record.copy()

        download_record.pop("invoice_data", None)
        download_record.pop("recon_row", None)
        download_record.pop("duplicate_result", None)
        download_record.pop("anomaly_list", None)
        download_record.pop("exception_summary", None)
        download_record.pop("raw_text", None)

        download_record["langchain_ai_review"] = st.session_state.single_ai_review
        download_record["langchain_ai_email"] = st.session_state.single_ai_email

        download_df = pd.DataFrame([download_record])

        csv_data = download_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download Single Invoice Reconciliation Report",
            data=csv_data,
            file_name="single_invoice_reconciliation_report.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"Error while processing single invoice: {e}")


# ---------------------------------------------------------
# Multiple Invoice Mode
# ---------------------------------------------------------

if (
    upload_mode == "Multiple Invoices"
    and po_valid
    and bank_valid
    and invoice_files
    and po_df is not None
    and bank_df is not None
):

    st.header("5. Multiple Invoice Reconciliation")

    st.write(
        f"You uploaded {len(invoice_files)} invoice file(s). "
        "Click the button below to process all invoices."
    )

    if st.button("Run Bulk Reconciliation"):
        bulk_results = []

        for current_invoice_file in invoice_files:
            try:
                record = process_one_invoice(
                    current_invoice_file,
                    po_df,
                    bank_df
                )

                bulk_results.append(record)

            except Exception as e:
                error_record = {
                    "file_name": current_invoice_file.name,
                    "invoice_number": None,
                    "vendor_name": None,
                    "po_number": None,
                    "invoice_date": None,
                    "subtotal": 0,
                    "tax": 0,
                    "invoice_amount": 0,
                    "status": "ERROR",
                    "exception_type": "PROCESSING_ERROR",
                    "issues": str(e),
                    "matched_po": None,
                    "matched_transaction": None,
                    "duplicate_found": False,
                    "duplicate_match_count": 0,
                    "anomaly_count": 0,
                    "anomalies": "NONE",
                    "requires_human_review": True,
                    "rule_based_explanation": f"Invoice file could not be processed. Error: {e}",
                    "raw_text": "",
                    "invoice_data": {},
                    "recon_row": {},
                    "duplicate_result": {
                        "duplicate_found": False,
                        "matched_count": 0,
                        "matched_transactions": []
                    },
                    "anomaly_list": [],
                    "exception_summary": [
                        {
                            "source": "Processing",
                            "issue": "PROCESSING_ERROR",
                            "details": str(e)
                        }
                    ]
                }

                bulk_results.append(error_record)

        st.session_state.bulk_results = bulk_results
        st.success("Bulk reconciliation completed successfully.")

    if st.session_state.bulk_results:
        results_df = pd.DataFrame(st.session_state.bulk_results)

        st.header("6. Bulk Dashboard Summary")
        show_dashboard(results_df)

        st.header("7. Consolidated Reconciliation Results")

        display_columns = [
            "file_name",
            "invoice_number",
            "vendor_name",
            "po_number",
            "invoice_date",
            "invoice_amount",
            "status",
            "exception_type",
            "duplicate_found",
            "duplicate_match_count",
            "anomaly_count",
            "anomalies",
            "requires_human_review"
        ]

        st.dataframe(
            results_df[display_columns],
            use_container_width=True
        )

        st.subheader("Status Distribution")

        status_summary = results_df["status"].value_counts().reset_index()
        status_summary.columns = ["status", "count"]

        st.bar_chart(
            status_summary.set_index("status")
        )

        st.subheader("Exception Type Distribution")

        exception_summary_df = results_df["exception_type"].value_counts().reset_index()
        exception_summary_df.columns = ["exception_type", "count"]

        st.bar_chart(
            exception_summary_df.set_index("exception_type")
        )

        st.header("8. Invoice Detail View")

        selected_file = st.selectbox(
            "Select invoice to view details",
            results_df["file_name"].tolist()
        )

        selected_row = results_df[
            results_df["file_name"] == selected_file
        ].iloc[0].to_dict()

        st.subheader("Selected Invoice Details")

        selected_detail_df = pd.DataFrame(
            [
                {
                    "file_name": selected_row.get("file_name"),
                    "invoice_number": selected_row.get("invoice_number"),
                    "vendor_name": selected_row.get("vendor_name"),
                    "po_number": selected_row.get("po_number"),
                    "invoice_date": selected_row.get("invoice_date"),
                    "invoice_amount": selected_row.get("invoice_amount"),
                    "status": selected_row.get("status"),
                    "exception_type": selected_row.get("exception_type"),
                    "duplicate_found": selected_row.get("duplicate_found"),
                    "anomaly_count": selected_row.get("anomaly_count"),
                    "requires_human_review": selected_row.get("requires_human_review")
                }
            ]
        )

        st.dataframe(selected_detail_df, use_container_width=True)

        st.subheader("Rule-Based Explanation")
        st.info(selected_row.get("rule_based_explanation"))

        st.subheader("Exception Summary")

        selected_exception_summary = selected_row.get("exception_summary", [])

        if selected_exception_summary:
            st.dataframe(
                pd.DataFrame(selected_exception_summary),
                use_container_width=True
            )
        else:
            st.success("No exception found for this invoice.")

        with st.expander("Show Raw Extracted Invoice Text"):
            st.text(selected_row.get("raw_text", ""))

        st.header("9. LangChain AI Review for Selected Invoice")

        selected_invoice_number = (
            selected_row.get("invoice_number")
            or selected_row.get("file_name")
        )

        if st.button("Generate LangChain AI Review for Selected Invoice"):
            try:
                ai_review = generate_langchain_review(
                    selected_row.get("invoice_data"),
                    selected_row.get("recon_row"),
                    selected_row.get("duplicate_result"),
                    selected_row.get("anomaly_list")
                )

                st.session_state.bulk_ai_review[selected_invoice_number] = ai_review

            except Exception as e:
                st.error(f"LangChain AI Review failed: {e}")

        if selected_invoice_number in st.session_state.bulk_ai_review:
            st.info(st.session_state.bulk_ai_review[selected_invoice_number])

        st.header("10. Human Approval Queue for Selected Invoice")

        if selected_row.get("requires_human_review"):
            st.warning("This invoice requires human review.")
        else:
            st.success("This invoice does not require human review.")

        bulk_decision = st.selectbox(
            "Select Review Decision",
            [
                "Pending",
                "Approve",
                "Reject",
                "Ask Vendor",
                "Escalate to Finance Manager",
                "Mark as Duplicate"
            ],
            key="bulk_decision"
        )

        bulk_comment = st.text_area(
            "Reviewer Comment",
            key="bulk_comment"
        )

        if st.button("Save Selected Invoice Approval Decision"):
            try:
                saved_record = save_approval_decision(
                    selected_row.get("invoice_number"),
                    bulk_decision,
                    bulk_comment
                )

                st.success("Approval decision saved successfully.")
                st.json(saved_record)

            except Exception as e:
                st.error(f"Error while saving approval decision: {e}")

        st.header("11. Vendor Email Draft and Send Email for Selected Invoice")

        if selected_row.get("requires_human_review"):
            st.subheader("Rule-Based Vendor Email")

            try:
                subject, body = draft_vendor_email(
                    selected_row.get("invoice_data"),
                    selected_row.get("recon_row"),
                    selected_row.get("duplicate_result"),
                    selected_row.get("anomaly_list")
                )

                st.text_input(
                    "Rule-Based Email Subject",
                    value=subject,
                    key="bulk_rule_email_subject"
                )

                st.text_area(
                    "Rule-Based Email Body",
                    value=body,
                    height=250,
                    key="bulk_rule_email_body"
                )

            except Exception as e:
                subject = "Invoice reconciliation clarification required"

                body = (
                    f"Dear Vendor,\n\n"
                    f"We need clarification for invoice {selected_invoice_number}.\n\n"
                    f"Error while drafting rule-based email: {e}\n\n"
                    f"Regards,\n"
                    f"Finance Team"
                )

                st.error(f"Rule-based email draft failed: {e}")

            st.subheader("LangChain AI Vendor Email")

            if st.button("Generate LangChain AI Email for Selected Invoice"):
                try:
                    ai_email = generate_langchain_email(
                        selected_row.get("invoice_data"),
                        selected_row.get("recon_row"),
                        selected_row.get("duplicate_result"),
                        selected_row.get("anomaly_list")
                    )

                    st.session_state.bulk_ai_email[selected_invoice_number] = ai_email

                except Exception as e:
                    st.error(f"LangChain AI Email failed: {e}")

            if selected_invoice_number in st.session_state.bulk_ai_email:
                st.text_area(
                    "AI Generated Email",
                    value=st.session_state.bulk_ai_email[selected_invoice_number],
                    height=300,
                    key="bulk_ai_email_text"
                )

            bulk_email_body_to_send = st.session_state.bulk_ai_email.get(
                selected_invoice_number,
                body
            )

            safe_selected_key = str(selected_invoice_number).replace(" ", "_").replace(".", "_")

            render_send_email_section(
                section_key=f"bulk_invoice_email_{safe_selected_key}",
                default_subject=subject,
                default_body=bulk_email_body_to_send,
                default_to=""
            )

        else:
            st.success("No vendor email required because this invoice has no exception.")

        st.header("12. Download Bulk Report")

        download_df = results_df.drop(
            columns=[
                "raw_text",
                "invoice_data",
                "recon_row",
                "duplicate_result",
                "anomaly_list",
                "exception_summary"
            ],
            errors="ignore"
        )

        csv_data = download_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download Bulk Reconciliation Report",
            data=csv_data,
            file_name="bulk_reconciliation_report.csv",
            mime="text/csv"
        )


# ---------------------------------------------------------
# Final Info Message
# ---------------------------------------------------------

if not po_valid or not bank_valid:
    st.info(
        "Please upload valid Purchase Order CSV and Bank Statement CSV to start reconciliation."
    )

elif upload_mode == "Single Invoice" and invoice_file is None:
    st.info("Please upload one invoice file for single invoice reconciliation.")

elif upload_mode == "Multiple Invoices" and not invoice_files:
    st.info("Please upload one or more invoice files for bulk reconciliation.")