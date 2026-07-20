import streamlit as st
import pandas as pd

from src.po_parser import load_purchase_orders, validate_po_columns
from src.bank_parser import load_bank_statement, validate_bank_columns
from src.matcher import match_records
from src.reconciliation_service import process_invoice
from src.email_sender import send_email_from_app
from src.ai_agent import generate_langchain_review, generate_langchain_email
from src.auth_service import (
    register_user,
    authenticate_user,
    create_default_admin,
    has_permission,
    request_password_reset,
    reset_password_with_code,
    hash_password,
)
from src.database import (
    initialize_database,
    save_reconciliation_result,
    get_all_reconciliation_results,
    save_approval_to_db,
    get_approval_records,
    save_email_log,
    get_email_logs,
    get_failed_email_logs,
    update_email_log_status,
    get_all_users,
    update_user_role_and_status,
    update_user_profile,
    create_user,
    get_user_by_username,
    delete_user_by_id,
)


st.set_page_config(page_title="Invoice Reconciliation Agent", page_icon="📄", layout="wide")
initialize_database()
create_default_admin()

st.markdown(
    """
    <style>
        .main .block-container { padding-top: 1.25rem; padding-bottom: 1rem; max-width: 100%; }
        section[data-testid="stSidebar"] { display: none; }
        div[data-testid="collapsedControl"] { display: none; }
        header[data-testid="stHeader"] { height: 0rem; }
        .main-title { font-size: 32px; font-weight: 800; color: black; line-height: 1.15; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        #.sub-title { text-align: center; color: gray; font-size: 18px; font-weight: 600; margin-top: 5px; margin-bottom: 5px; }
        .user-table-header { font-weight: 700; background-color: #f5f5f5; padding: 8px; border-radius: 6px; }
        .user-table-cell { padding: 6px 0px; border-bottom: 1px solid #eeeeee; }
    </style>
    """,
    unsafe_allow_html=True,
)


def app_header(current_user=None):
    col1, col2 = st.columns([20, 1])
    with col1:
        st.markdown(
            """
            <div class='main-title'>🤖 Intelligent Invoice & Expense Reconciliation Agent</div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        if current_user:
            with st.popover("👤"):
                st.markdown(f"**User:** {current_user.get('username')}  \n**Role:** {current_user.get('role')}")
                if st.button("Logout", key="top_logout", use_container_width=True):
                    st.session_state.logged_in = False
                    st.session_state.user = None
                    st.rerun()
    #st.markdown(
    #    """
    #    <div class='sub-title'>3-Tier Application | LangChain AI | SQLite Database | SMTP Email Automation</div>
    #    <hr style="margin-top:5px;">
    #    """,
    #    unsafe_allow_html=True,
    #)


def show_required_column_help():
    with st.expander("Required CSV Format Help"):
        st.markdown(
            """
            ### Purchase Order CSV required columns
            ```text
            po_number,vendor_name,total_amount,status
            ```
            ### Bank Statement CSV required columns
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Invoices", total_invoices)
    c2.metric("Matched", matched_count)
    c3.metric("Exceptions", exception_count)
    c4.metric("Human Review", human_review_count)
    c5, c6, c7 = st.columns(3)
    c5.metric("Duplicates", duplicate_count)
    c6.metric("Anomalies", anomaly_count)
    c7.metric("Processing Errors", error_count)


def parse_langchain_email(ai_email_text):
    default_subject = "Invoice Review Required"
    if not ai_email_text:
        return default_subject, ""
    lines = ai_email_text.splitlines()
    subject = default_subject
    body_lines = []
    body_started = False
    for line in lines:
        clean_line = line.strip()
        if clean_line.lower().startswith("subject:"):
            subject = clean_line.split(":", 1)[1].strip() or default_subject
            continue
        if clean_line.lower().startswith("body:"):
            body_started = True
            continue
        if body_started:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    if not body:
        body = ai_email_text
    return subject, body


def render_email_sender(default_subject, default_body, key_prefix, invoice_number):
    st.subheader("Send Email from Application")
    email_to = st.text_input("To", placeholder="vendor@example.com", key=f"{key_prefix}_email_to")
    email_cc = st.text_input("CC", placeholder="manager@example.com, finance@example.com", key=f"{key_prefix}_email_cc")
    email_bcc = st.text_input("BCC", placeholder="audit@example.com", key=f"{key_prefix}_email_bcc")
    final_subject = st.text_input("Final Email Subject", value=default_subject, key=f"{key_prefix}_final_subject")
    final_body = st.text_area("Final Email Body", value=default_body, height=280, key=f"{key_prefix}_final_body")

    send_col, draft_col = st.columns(2)
    with send_col:
        if st.button("Send Email", key=f"{key_prefix}_send_email"):
            try:
                send_result = send_email_from_app(email_to, email_cc, email_bcc, final_subject, final_body)
                save_email_log(invoice_number, email_to, email_cc, email_bcc, final_subject, final_body, "SUCCESS")
                st.success("Email sent successfully.")
                st.json(send_result)
            except Exception as e:
                save_email_log(invoice_number, email_to, email_cc, email_bcc, final_subject, final_body, f"FAILED: {e}")
                st.error(f"Email sending failed: {e}")
    with draft_col:
        if st.button("Save As Draft", key=f"{key_prefix}_save_not_sent"):
            save_email_log(invoice_number, email_to, email_cc, email_bcc, final_subject, final_body, "NOT_SENT")
            st.success("Email draft saved as NOT_SENT in database.")


def build_download_df(records):
    df = pd.DataFrame(records)
    return df.drop(columns=["raw_text", "invoice_data", "recon_row", "duplicate_result", "anomaly_list", "exception_summary"], errors="ignore")


def authentication_page():
    app_header()
    auth_tab1, auth_tab2 = st.tabs(["Login", "Forgot Password"])

    with auth_tab1:
        st.subheader("User Login")
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            login_clicked = st.form_submit_button("Login", use_container_width=True)
            if login_clicked:
                success, message, user_data = authenticate_user(username, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.user = user_data
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    #with auth_tab2:
    #    st.subheader("New User Registration")
    #    with st.form("register_form", clear_on_submit=False):
    #        new_username = st.text_input("Choose Username", key="register_username")
    #        new_email = st.text_input("Email", key="register_email")
    #        new_password = st.text_input("Choose Password", type="password", key="register_password")
    #        confirm_password = st.text_input("Confirm Password", type="password", key="register_confirm_password")
    #        register_clicked = st.form_submit_button("Register", use_container_width=True)
    #        if register_clicked:
    #            if not new_username or not new_email or not new_password:
    #                st.error("All fields are required.")
    #            elif new_password != confirm_password:
    #                st.error("Passwords do not match.")
    #            else:
    #                success, message = register_user(new_username, new_email, new_password)
    #                if success:
    #                    st.success(message)
    #                    st.info("Admin must activate and assign your role before login.")
    #                else:
    #                    st.error(message)

    with auth_tab2:
        st.subheader("Forgot Password")
        st.write("Enter your username or registered email. A reset code will be sent to your registered email.")
        with st.form("forgot_password_form", clear_on_submit=False):
            reset_username_or_email = st.text_input("Username or Email", key="forgot_username_or_email")
            send_code_clicked = st.form_submit_button("Send Reset Code", use_container_width=True)
            if send_code_clicked:
                if not reset_username_or_email:
                    st.error("Please enter username or email.")
                else:
                    success, message = request_password_reset(reset_username_or_email)
                if success:
                    st.success(message)
                else:
                    st.error(message)

        st.divider()
        st.subheader("Reset Password")
        with st.form("reset_password_form", clear_on_submit=False):
            reset_username = st.text_input("Username", key="reset_username")
            reset_code = st.text_input("Reset Code", key="reset_code")
            new_reset_password = st.text_input("New Password", type="password", key="reset_new_password")
            confirm_reset_password = st.text_input("Confirm New Password", type="password", key="reset_confirm_password")
            reset_clicked = st.form_submit_button("Reset Password", use_container_width=True)
            if reset_clicked:
                if not reset_username or not reset_code or not new_reset_password:
                    st.error("All fields are required.")
                elif new_reset_password != confirm_reset_password:
                    st.error("Passwords do not match.")
                else:
                    success, message = reset_password_with_code(reset_username, reset_code, new_reset_password)
                    
                if success:
                    st.success(message)
                else:
                    st.error(message)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "bulk_results" not in st.session_state:
    st.session_state.bulk_results = []

if not st.session_state.logged_in:
    authentication_page()
    st.stop()

current_user = st.session_state.user
current_role = current_user.get("role")
app_header(current_user)

can_view = has_permission(current_role, "view")
can_edit = has_permission(current_role, "edit")
can_send_email = has_permission(current_role, "send_email")
can_manage_users = has_permission(current_role, "manage_users")


def render_result_sections(result_record, key_prefix, can_edit, can_send_email):
    invoice_data = result_record["invoice_data"]
    recon_row = result_record["recon_row"]
    duplicate_result = result_record["duplicate_result"]
    anomalies = result_record["anomaly_list"]
    requires_human_review = result_record["requires_human_review"]

    st.subheader("Extracted Invoice Data")
    st.dataframe(pd.DataFrame([{
        "file_name": result_record.get("file_name"),
        "invoice_number": result_record.get("invoice_number"),
        "vendor_name": result_record.get("vendor_name"),
        "po_number": result_record.get("po_number"),
        "invoice_date": result_record.get("invoice_date"),
        "subtotal": result_record.get("subtotal"),
        "tax": result_record.get("tax"),
        "invoice_amount": result_record.get("invoice_amount"),
    }]), use_container_width=True)

    with st.expander("Show Raw Extracted Invoice Text"):
        st.text(result_record.get("raw_text", ""))

    st.header("Dashboard Summary")
    show_dashboard(pd.DataFrame([{
        "status": result_record.get("status"),
        "duplicate_found": result_record.get("duplicate_found"),
        "anomaly_count": result_record.get("anomaly_count"),
        "requires_human_review": result_record.get("requires_human_review"),
    }]))

    st.header("Three-Way Reconciliation Result")
    st.dataframe(pd.DataFrame([recon_row]), use_container_width=True)

    st.header("Duplicate Payment Detection")
    if duplicate_result.get("duplicate_found"):
        st.error(f"Duplicate payment detected. {duplicate_result.get('matched_count')} bank transactions may match this invoice.")
        st.dataframe(pd.DataFrame(duplicate_result.get("matched_transactions", [])), use_container_width=True)
    else:
        st.success("No duplicate payment found.")

    st.header("Anomaly Detection")
    if anomalies:
        st.warning("Anomalies detected.")
        st.dataframe(pd.DataFrame(anomalies), use_container_width=True)
    else:
        st.success("No anomaly found.")

    st.header("Exception Summary")
    exception_summary = result_record.get("exception_summary", [])
    if exception_summary:
        st.dataframe(pd.DataFrame(exception_summary), use_container_width=True)
    else:
        st.success("No exception found for this invoice.")

    st.header("LangChain AI Review")
    review_state_key = f"{key_prefix}_ai_review"
    if review_state_key not in st.session_state:
        st.session_state[review_state_key] = ""
    if st.button("Generate LangChain AI Review", key=f"{key_prefix}_review_button"):
        try:
            st.session_state[review_state_key] = generate_langchain_review(invoice_data, recon_row, duplicate_result, anomalies)
        except Exception as e:
            st.error(f"LangChain AI Review failed: {e}")
    if st.session_state[review_state_key]:
        st.info(st.session_state[review_state_key])

    st.header("Human Approval")
    if requires_human_review:
        if can_edit:
            st.warning("This invoice requires human review.")
            decision = st.selectbox("Select Review Decision", ["Pending", "Approve", "Reject", "Ask Vendor", "Escalate to Finance Manager", "Mark as Duplicate"], key=f"{key_prefix}_decision")
            comment = st.text_area("Reviewer Comment", key=f"{key_prefix}_comment")
            if st.button("Save Approval Decision", key=f"{key_prefix}_save_approval"):
                save_approval_to_db(invoice_data.get("invoice_number"), decision, comment)
                st.success("Approval decision saved.")
        else:
            st.warning("This invoice requires human review, but your role does not allow approval action.")
    else:
        st.success("This invoice does not require human review.")
        st.info("Approval action is not required because no exception, duplicate, or anomaly was found.")

    st.header("Vendor Email Draft and Send")
    if requires_human_review:
        if not can_send_email:
            st.warning("You do not have permission to generate or send vendor emails.")
        else:
            email_state_key = f"{key_prefix}_ai_email"
            if email_state_key not in st.session_state:
                st.session_state[email_state_key] = ""
            st.subheader("LangChain AI Vendor Email")
            if st.button("Generate LangChain AI Email", key=f"{key_prefix}_email_button"):
                try:
                    st.session_state[email_state_key] = generate_langchain_email(invoice_data, recon_row, duplicate_result, anomalies)
                except Exception as e:
                    st.error(f"LangChain AI Email failed: {e}")
            if st.session_state[email_state_key]:
                ai_subject, ai_body = parse_langchain_email(st.session_state[email_state_key])
                render_email_sender(ai_subject, ai_body, key_prefix, invoice_data.get("invoice_number"))
            else:
                st.info("Click 'Generate LangChain AI Email' to generate vendor communication.")
    else:
        st.success("No vendor email required because this invoice has no exception.")


if can_manage_users:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Recon Section", "Data Section", "Approval Section", "Email Section", "User Management"])
else:
    tab1, tab2, tab3, tab4 = st.tabs(["Recon Section", "Data Section", "Approval Section", "Email Section"])

with tab1:
    if not can_edit:
        st.warning("You do not have permission to process invoices.")
    else:
        st.header("1. Upload Input Files")
        col1, col2 = st.columns(2)
        with col1:
            po_file = st.file_uploader("Upload Purchase Order CSV", type=["csv"], key="po_file")
        with col2:
            bank_file = st.file_uploader("Upload Bank Statement CSV", type=["csv"], key="bank_file")
        upload_mode = st.radio("Select Invoice Upload Mode", ["Single Invoice", "Multiple Invoices"])
        if upload_mode == "Single Invoice":
            invoice_file = st.file_uploader("Upload Single Invoice File", type=["txt", "pdf", "png", "jpg", "jpeg"], key="single_invoice_file")
            invoice_files = None
        else:
            invoice_files = st.file_uploader("Upload Multiple Invoice Files", type=["txt", "pdf", "png", "jpg", "jpeg"], accept_multiple_files=True, key="multiple_invoice_files")
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
                    st.error(f"Purchase Order CSV is missing required columns: {missing_po_columns}")
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
                    st.error(f"Bank Statement CSV is missing required columns: {missing_bank_columns}")
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

        if upload_mode == "Single Invoice" and po_valid and bank_valid and invoice_file is not None:
            st.header("5. Single Invoice Reconciliation")
            try:
                result_record = process_invoice(invoice_file, po_df, bank_df)
                save_reconciliation_result(result_record)
                st.success("Reconciliation result saved.")
                render_result_sections(result_record, "single", can_edit, can_send_email)
            except Exception as e:
                st.error(f"Error while processing single invoice: {e}")

        if upload_mode == "Multiple Invoices" and po_valid and bank_valid and invoice_files:
            st.header("5. Multiple Invoice Reconciliation")
            st.write(f"You uploaded {len(invoice_files)} invoice file(s). Click the button below to process all invoices.")
            if st.button("Run Bulk Reconciliation"):
                bulk_results = []
                for current_invoice_file in invoice_files:
                    try:
                        record = process_invoice(current_invoice_file, po_df, bank_df)
                        save_reconciliation_result(record)
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
                            "duplicate_result": {"duplicate_found": False, "matched_count": 0, "matched_transactions": []},
                            "anomaly_list": [],
                            "exception_summary": [{"source": "Processing", "issue": "PROCESSING_ERROR", "details": str(e)}],
                        }
                        save_reconciliation_result(error_record)
                        bulk_results.append(error_record)
                st.session_state.bulk_results = bulk_results
                st.success("Bulk reconciliation completed and saved into database.")

            if st.session_state.bulk_results:
                results_df = pd.DataFrame(st.session_state.bulk_results)
                st.header("6. Bulk Dashboard")
                show_dashboard(results_df)
                display_columns = ["file_name", "invoice_number", "vendor_name", "po_number", "invoice_date", "invoice_amount", "status", "exception_type", "duplicate_found", "duplicate_match_count", "anomaly_count", "anomalies", "requires_human_review"]
                st.header("7. Consolidated Results")
                st.dataframe(results_df[display_columns], use_container_width=True)
                st.header("8. Select Invoice for Detail / Approval / Email")
                selected_file = st.selectbox("Select invoice", results_df["file_name"].tolist())
                selected_row = results_df[results_df["file_name"] == selected_file].iloc[0].to_dict()
                selected_invoice_number = selected_row.get("invoice_number") or selected_row.get("file_name")
                render_result_sections(selected_row, f"bulk_{selected_invoice_number}", can_edit, can_send_email)

with tab2:
    if not can_view:
        st.warning("You do not have permission to view records.")
    else:
        st.header("Reconciliation Records")
        db_rows = get_all_reconciliation_results()
        db_df = pd.DataFrame(db_rows, columns=["id", "file_name", "invoice_number", "vendor_name", "po_number", "invoice_date", "invoice_amount", "status", "exception_type", "duplicate_found", "anomaly_count", "requires_human_review", "created_at"])
        if db_df.empty:
            st.info("No reconciliation records found yet.")
        else:
            st.dataframe(
                db_df,
                use_container_width=True
            )

with tab3:
    if not can_view:
        st.warning("You do not have permission to view approval records.")
    else:
        st.header("Approval Records")
        approval_rows = get_approval_records()
        approval_df = pd.DataFrame(approval_rows, columns=["id", "invoice_number", "decision", "comment", "decision_time"])
        if approval_df.empty:
            st.info("No approval records found yet.")
        else:
            st.dataframe(
                approval_df,
                use_container_width=True
            )

with tab4:
    if not can_view:
        st.warning("You do not have permission to view email records.")
    else:
        st.header("Email Records")
        email_rows = get_email_logs()
        email_df = pd.DataFrame(email_rows, columns=["id", "invoice_number", "email_to", "email_cc", "email_bcc", "subject", "body", "send_status", "sent_at"])
        if email_df.empty:
            st.info("No email logs found yet.")
        else:
            st.subheader("All Email Logs")
            st.dataframe(email_df[["id", "invoice_number", "email_to", "subject", "send_status", "sent_at"]], use_container_width=True)
        st.divider()
        st.subheader("Retry Failed / Not Sent Emails")
        if not can_send_email:
            st.warning("You do not have permission to retry or send emails.")
        else:
            failed_rows = get_failed_email_logs()
            failed_df = pd.DataFrame(failed_rows, columns=["id", "invoice_number", "email_to", "email_cc", "email_bcc", "subject", "body", "send_status", "sent_at"])
            if failed_df.empty:
                st.success("No failed or unsent emails found.")
            else:
                failed_options = [f"Log ID {row['id']} | Invoice {row['invoice_number']} | To: {row['email_to']} | Status: {row['send_status']}" for _, row in failed_df.iterrows()]
                selected_option = st.selectbox("Select failed or unsent email", failed_options)
                selected_index = failed_options.index(selected_option)
                selected_email = failed_df.iloc[selected_index].to_dict()
                retry_to = st.text_input("To", value=selected_email.get("email_to") or "", key="retry_to")
                retry_cc = st.text_input("CC", value=selected_email.get("email_cc") or "", key="retry_cc")
                retry_bcc = st.text_input("BCC", value=selected_email.get("email_bcc") or "", key="retry_bcc")
                retry_subject = st.text_input("Subject", value=selected_email.get("subject") or "", key="retry_subject")
                retry_body = st.text_area("Body", value=selected_email.get("body") or "", height=300, key="retry_body")
                if st.button("Retry Send Email", key="retry_send_button"):
                    try:
                        send_email_from_app(retry_to, retry_cc, retry_bcc, retry_subject, retry_body)
                        update_email_log_status(selected_email.get("id"), retry_to, retry_cc, retry_bcc, retry_subject, retry_body, "SUCCESS")
                        st.success("Email resent successfully. Removing from retry list...")
                        st.rerun()
                    except Exception as e:
                        update_email_log_status(selected_email.get("id"), retry_to, retry_cc, retry_bcc, retry_subject, retry_body, f"FAILED: {e}")
                        st.error(f"Retry email sending failed: {e}")

if can_manage_users:
    with tab5:
        st.header("User Management")

        user_rows = get_all_users()
        users_df = pd.DataFrame(user_rows, columns=["id", "username", "email", "role", "is_active", "created_at"])

        if users_df.empty:
            st.info("No users found.")
        else:
            st.subheader("All Users")
            header_cols = st.columns([1, 3, 5, 2, 1.5, 3, 1.4])
            headers = ["ID", "Username", "Email", "Role", "Active", "Created At", "Action"]
            for col, header in zip(header_cols, headers):
                with col:
                    st.markdown(f"<div class='user-table-header'>{header}</div>", unsafe_allow_html=True)

            for _, row in users_df.iterrows():
                user_id = int(row["id"])
                username = row["username"]
                email = row["email"]
                role = row["role"]
                is_active = int(row["is_active"])
                created_at = row["created_at"]

                row_cols = st.columns([1, 3, 5, 2, 1.5, 3, 1.4])
                values = [user_id, username, email, role, "Yes" if is_active == 1 else "No", created_at]
                for idx, value in enumerate(values):
                    with row_cols[idx]:
                        st.markdown(f"<div class='user-table-cell'>{value}</div>", unsafe_allow_html=True)

                with row_cols[6]:
                    edit_col, delete_col = st.columns(2)
                    with edit_col:
                        if username.lower() == "admin":

                            st.button(
                                "🔒",
                                key=f"admin_edit_disabled_{user_id}",
                                disabled=True,
                                help="Admin user cannot be edited"
                            )

                        else:

                            if st.button(
                                "✏️",
                                key=f"edit_user_{user_id}",
                                help=f"Edit user {username}"
                            ):
                                st.session_state.edit_user_id = user_id
                                st.rerun()
                    with delete_col:
                        if username.lower() == "admin":
                            st.write("")
                        else:
                            if st.button("🗑️", key=f"delete_user_{user_id}", help=f"Delete user {username}"):
                                delete_user_by_id(user_id)
                                st.success(f"User '{username}' deleted successfully.")
                                st.rerun()


            if "edit_user_id" in st.session_state:
                edit_user_id = st.session_state.edit_user_id
                edit_rows = users_df[users_df["id"] == edit_user_id]

                if not edit_rows.empty:
                    edit_row = edit_rows.iloc[0]

                    st.subheader(f"Edit User: {edit_row['username']}")

                    with st.form("inline_edit_user_form", clear_on_submit=False):

                        edit_username = st.text_input(
                            "Username",
                            value=str(edit_row["username"]),
                            key="edit_username"
                        )

                        edit_email = st.text_input(
                            "Email",
                            value=str(edit_row["email"]),
                            key="edit_email"
                        )

                        role_options = [
                            "Admin",
                            "Editor",
                            "Email Sender",
                            "Viewer",
                            "Pending"
                        ]

                        current_role_index = (
                            role_options.index(edit_row["role"])
                            if edit_row["role"] in role_options
                            else 0
                        )

                        edit_role = st.selectbox(
                            "Role",
                            role_options,
                            index=current_role_index,
                            key="edit_role"
                        )

                        edit_status = st.selectbox(
                            "Status",
                            [
                                "Active",
                                "Inactive"
                            ],
                            index=0 if int(edit_row["is_active"]) == 1 else 1,
                            key="edit_status"
                        )

                        btn_col1, btn_col2 = st.columns(2)

                        with btn_col1:
                            save_edit = st.form_submit_button(
                                "Save Changes",
                                use_container_width=True
                            )

                        with btn_col2:
                            cancel_edit = st.form_submit_button(
                                "Cancel",
                                use_container_width=True
                            )

                        if save_edit:
                            update_user_profile(
                                user_id=edit_user_id,
                                username=edit_username,
                                email=edit_email,
                                role=edit_role,
                                is_active=1 if edit_status == "Active" else 0
                            )

                            st.success("User updated successfully.")

                            del st.session_state.edit_user_id

                            st.rerun()

                        if cancel_edit:
                            del st.session_state.edit_user_id

                            st.rerun()
        
        st.subheader("Create New User")
        with st.form("admin_create_user_form", clear_on_submit=False):
            admin_new_username = st.text_input("Username", key="admin_create_username")
            admin_new_email = st.text_input("Email", key="admin_create_email")
            admin_new_password = st.text_input("Temporary Password", type="password", key="admin_create_password")
            admin_new_role = st.selectbox("Role", ["Admin", "Editor", "Email Sender", "Viewer"], key="admin_create_role")
            admin_new_status = st.selectbox("Status", ["Active", "Inactive"], key="admin_create_status")
            create_user_clicked = st.form_submit_button("Create User", use_container_width=True)
            if create_user_clicked:
                if not admin_new_username or not admin_new_email or not admin_new_password:
                    st.error("Username, email, and temporary password are required.")
                elif get_user_by_username(admin_new_username):
                    st.error("Username already exists.")
                else:
                    create_user(
                        username=admin_new_username,
                        email=admin_new_email,
                        password_hash=hash_password(admin_new_password),
                        role=admin_new_role,
                        is_active=1 if admin_new_status == "Active" else 0,
                    )
                    st.success(f"User '{admin_new_username}' created successfully.")
                    st.rerun()
