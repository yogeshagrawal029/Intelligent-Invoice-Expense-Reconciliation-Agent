import streamlit as st
import pandas as pd

from src.po_parser import load_purchase_orders, validate_po_columns
from src.bank_parser import load_bank_statement, validate_bank_columns
from src.matcher import match_records
from src.reconciliation_service import process_invoice
from src.email_drafter import draft_vendor_email
from src.email_sender import send_email_from_app
from src.ai_agent import generate_langchain_review, generate_langchain_email

from src.database import (
    initialize_database,
    save_reconciliation_result,
    get_all_reconciliation_results,
    save_approval_to_db,
    save_email_log,
    get_email_logs
)


st.set_page_config(
    page_title="Invoice Reconciliation Agent",
    page_icon="📄",
    layout="wide"
)


initialize_database()


st.title("Intelligent Invoice & Expense Reconciliation Agent")

st.write(
    "This is a 3-tier local application with Streamlit frontend, Python backend service layer, "
    "and SQLite local database."
)


st.sidebar.title("3-Tier Application")

st.sidebar.markdown(
    """
    ### Tier 1: Frontend
    - Streamlit UI
    - File upload
    - Dashboard
    - Approval screen
    - Email section

    ### Tier 2: Backend
    - Invoice parsing
    - Matching engine
    - Duplicate detection
    - Anomaly detection
    - LangChain review
    - Email draft

    ### Tier 3: Database
    - Local SQLite database
    - Stores reconciliation results
    - Stores approvals
    - Stores email logs
    """
)


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


def show_required_column_help():
    with st.expander("Required CSV Format Help"):
        st.markdown(
            """
            ### Purchase Order CSV

            ```text
            po_number,vendor_name,total_amount,status
            ```

            ### Bank Statement CSV

            ```text
            transaction_id,vendor_name,amount,description,date
            ```
            """
        )


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


def render_email_sender(default_subject, default_body, key_prefix, invoice_number):
    st.subheader("Send Email from Application")

    email_to = st.text_input(
        "To",
        placeholder="vendor@example.com",
        key=f"{key_prefix}_email_to"
    )

    email_cc = st.text_input(
        "CC",
        placeholder="manager@example.com, finance@example.com",
        key=f"{key_prefix}_email_cc"
    )

    email_bcc = st.text_input(
        "BCC",
        placeholder="audit@example.com",
        key=f"{key_prefix}_email_bcc"
    )

    final_subject = st.text_input(
        "Final Email Subject",
        value=default_subject,
        key=f"{key_prefix}_final_subject"
    )

    final_body = st.text_area(
        "Final Email Body",
        value=default_body,
        height=300,
        key=f"{key_prefix}_final_body"
    )

    if st.button("Send Email", key=f"{key_prefix}_send_email"):
        try:
            send_result = send_email_from_app(
                to_emails=email_to,
                cc_emails=email_cc,
                bcc_emails=email_bcc,
                subject=final_subject,
                body=final_body
            )

            save_email_log(
                invoice_number=invoice_number,
                email_to=email_to,
                email_cc=email_cc,
                email_bcc=email_bcc,
                subject=final_subject,
                body=final_body,
                send_status="SUCCESS"
            )

            st.success("Email sent successfully.")
            st.json(send_result)

        except Exception as e:
            save_email_log(
                invoice_number=invoice_number,
                email_to=email_to,
                email_cc=email_cc,
                email_bcc=email_bcc,
                subject=final_subject,
                body=final_body,
                send_status=f"FAILED: {e}"
            )

            st.error(f"Email sending failed: {e}")


tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Reconciliation",
        "Database Records",
        "Approval Records",
        "Email Logs"
    ]
)


with tab1:
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

    po_df = None
    bank_df = None
    po_valid = False
    bank_valid = False

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

        except Exception as e:
            st.error(f"Error while reading Purchase Order file: {e}")

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

        except Exception as e:
            st.error(f"Error while reading Bank Statement file: {e}")

    if po_valid and bank_valid and po_df is not None and bank_df is not None:
        st.header("4. Basic PO vs Bank Matching")

        try:
            basic_result = match_records(po_df, bank_df)
            st.dataframe(basic_result, use_container_width=True)

        except Exception as e:
            st.error(f"Error during basic PO vs Bank matching: {e}")

    if (
        upload_mode == "Single Invoice"
        and po_valid
        and bank_valid
        and invoice_file is not None
    ):
        st.header("5. Single Invoice Reconciliation")

        try:
            result_record = process_invoice(
                invoice_file,
                po_df,
                bank_df
            )

            invoice_data = result_record["invoice_data"]
            recon_row = result_record["recon_row"]
            duplicate_result = result_record["duplicate_result"]
            anomalies = result_record["anomaly_list"]
            requires_human_review = result_record["requires_human_review"]

            save_reconciliation_result(result_record)

            st.success("Reconciliation result saved into local SQLite database.")

            st.subheader("Extracted Invoice Data")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "file_name": result_record.get("file_name"),
                            "invoice_number": result_record.get("invoice_number"),
                            "vendor_name": result_record.get("vendor_name"),
                            "po_number": result_record.get("po_number"),
                            "invoice_date": result_record.get("invoice_date"),
                            "subtotal": result_record.get("subtotal"),
                            "tax": result_record.get("tax"),
                            "invoice_amount": result_record.get("invoice_amount")
                        }
                    ]
                ),
                use_container_width=True
            )

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

            st.header("7. Three-Way Result")
            st.dataframe(pd.DataFrame([recon_row]), use_container_width=True)

            st.header("8. Exception Summary")

            exception_summary = result_record.get("exception_summary", [])

            if exception_summary:
                st.dataframe(pd.DataFrame(exception_summary), use_container_width=True)
            else:
                st.success("No exception found for this invoice.")

            st.header("9. Rule-Based Explanation")
            st.info(result_record.get("rule_based_explanation"))

            st.header("10. LangChain AI Review")

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

            st.header("11. Human Approval")

            decision = st.selectbox(
                "Select Review Decision",
                [
                    "Pending",
                    "Approve",
                    "Reject",
                    "Ask Vendor",
                    "Escalate to Finance Manager",
                    "Mark as Duplicate"
                ]
            )

            comment = st.text_area("Reviewer Comment")

            if st.button("Save Approval Decision"):
                save_approval_to_db(
                    invoice_number=invoice_data.get("invoice_number"),
                    decision=decision,
                    comment=comment
                )

                st.success("Approval decision saved into database.")

            st.header("12. Vendor Email Draft and Send")

            if requires_human_review:
                subject, body = draft_vendor_email(
                    invoice_data,
                    recon_row,
                    duplicate_result,
                    anomalies
                )

                st.subheader("Rule-Based Vendor Email")
                st.text_input(
                    "Rule-Based Email Subject",
                    value=subject
                )

                st.text_area(
                    "Rule-Based Email Body",
                    value=body,
                    height=250
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
                        height=300
                    )

                body_to_send = (
                    st.session_state.single_ai_email
                    if st.session_state.single_ai_email
                    else body
                )

                render_email_sender(
                    default_subject=subject,
                    default_body=body_to_send,
                    key_prefix="single",
                    invoice_number=invoice_data.get("invoice_number")
                )

            else:
                st.success("No vendor email required because this invoice has no exception.")

            st.header("13. Download Single Invoice Report")

            download_record = result_record.copy()

            for key in [
                "invoice_data",
                "recon_row",
                "duplicate_result",
                "anomaly_list",
                "exception_summary",
                "raw_text"
            ]:
                download_record.pop(key, None)

            download_record["langchain_ai_review"] = st.session_state.single_ai_review
            download_record["langchain_ai_email"] = st.session_state.single_ai_email

            csv_data = pd.DataFrame([download_record]).to_csv(index=False).encode("utf-8")

            st.download_button(
                label="Download Single Invoice Reconciliation Report",
                data=csv_data,
                file_name="single_invoice_reconciliation_report.csv",
                mime="text/csv"
            )

        except Exception as e:
            st.error(f"Error while processing single invoice: {e}")

    if (
        upload_mode == "Multiple Invoices"
        and po_valid
        and bank_valid
        and invoice_files
    ):
        st.header("5. Multiple Invoice Reconciliation")

        if st.button("Run Bulk Reconciliation"):
            bulk_results = []

            for current_invoice_file in invoice_files:
                try:
                    record = process_invoice(
                        current_invoice_file,
                        po_df,
                        bank_df
                    )

                    save_reconciliation_result(record)
                    bulk_results.append(record)

                except Exception as e:
                    error_record = {
                        "file_name": current_invoice_file.name,
                        "invoice_number": None,
                        "vendor_name": None,
                        "po_number": None,
                        "invoice_date": None,
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
                        "invoice_data": {},
                        "recon_row": {},
                        "duplicate_result": {},
                        "anomaly_list": [],
                        "exception_summary": []
                    }

                    save_reconciliation_result(error_record)
                    bulk_results.append(error_record)

            st.session_state.bulk_results = bulk_results
            st.success("Bulk reconciliation completed and saved into database.")

        if st.session_state.bulk_results:
            results_df = pd.DataFrame(st.session_state.bulk_results)

            st.header("6. Bulk Dashboard")
            show_dashboard(results_df)

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

            st.header("7. Consolidated Results")
            st.dataframe(results_df[display_columns], use_container_width=True)

            st.header("8. Select Invoice for Email / Approval")

            selected_file = st.selectbox(
                "Select invoice",
                results_df["file_name"].tolist()
            )

            selected_row = results_df[
                results_df["file_name"] == selected_file
            ].iloc[0].to_dict()

            selected_invoice_number = selected_row.get("invoice_number") or selected_row.get("file_name")

            st.subheader("Selected Invoice Details")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "file_name": selected_row.get("file_name"),
                            "invoice_number": selected_row.get("invoice_number"),
                            "vendor_name": selected_row.get("vendor_name"),
                            "status": selected_row.get("status"),
                            "exception_type": selected_row.get("exception_type"),
                            "requires_human_review": selected_row.get("requires_human_review")
                        }
                    ]
                ),
                use_container_width=True
            )

            st.subheader("Explanation")
            st.info(selected_row.get("rule_based_explanation"))

            st.subheader("Approval")

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

            if st.button("Save Selected Invoice Approval"):
                save_approval_to_db(
                    invoice_number=selected_row.get("invoice_number"),
                    decision=bulk_decision,
                    comment=bulk_comment
                )

                st.success("Approval saved into database.")

            st.subheader("Vendor Email Draft and Send")

            if selected_row.get("requires_human_review"):
                subject, body = draft_vendor_email(
                    selected_row.get("invoice_data"),
                    selected_row.get("recon_row"),
                    selected_row.get("duplicate_result"),
                    selected_row.get("anomaly_list")
                )

                st.text_input(
                    "Rule-Based Email Subject",
                    value=subject,
                    key="bulk_rule_subject"
                )

                st.text_area(
                    "Rule-Based Email Body",
                    value=body,
                    height=250,
                    key="bulk_rule_body"
                )

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
                        height=300
                    )

                body_to_send = st.session_state.bulk_ai_email.get(
                    selected_invoice_number,
                    body
                )

                render_email_sender(
                    default_subject=subject,
                    default_body=body_to_send,
                    key_prefix="bulk",
                    invoice_number=selected_row.get("invoice_number")
                )

            else:
                st.success("No vendor email required.")

            st.header("9. Download Bulk Report")

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


with tab2:
    st.header("Stored Reconciliation Results from SQLite DB")

    db_rows = get_all_reconciliation_results()

    db_df = pd.DataFrame(
        db_rows,
        columns=[
            "id",
            "file_name",
            "invoice_number",
            "vendor_name",
            "po_number",
            "invoice_date",
            "invoice_amount",
            "status",
            "exception_type",
            "duplicate_found",
            "anomaly_count",
            "requires_human_review",
            "created_at"
        ]
    )

    st.dataframe(db_df, use_container_width=True)


with tab3:
    st.header("Approval Records")

    st.info(
        "Approval decisions are stored in the local SQLite database table: approval_decisions."
    )


with tab4:
    st.header("Email Logs")

    email_rows = get_email_logs()

    email_df = pd.DataFrame(
        email_rows,
        columns=[
            "id",
            "invoice_number",
            "email_to",
            "subject",
            "send_status",
            "sent_at"
        ]
    )

    st.dataframe(email_df, use_container_width=True)