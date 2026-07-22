import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from src.po_parser import load_purchase_orders, validate_po_columns
from src.bank_parser import load_bank_statement, validate_bank_columns
from src.matcher import match_records
from src.reconciliation_service import process_invoice
from src.email_sender import send_email_from_app
from src.ai_agent import generate_langchain_review, generate_langchain_email
from src.auth_service import (
    authenticate_user,
    create_default_admin,
    has_permission,
    request_password_reset,
    reset_password_with_code,
    change_password_first_login,
    request_login_otp,
    verify_login_otp,
    hash_password,
    generate_initial_password,
    send_initial_password_email,
    send_temporary_password_for_user,
    password_policy_text,
    get_password_expiry_days,
    get_login_otp_expiry_minutes,
)
from src.database import (
    initialize_database,
    save_reconciliation_result,
    reconciliation_result_exists,
    get_all_reconciliation_results,
    save_approval_to_db,
    get_approval_records,
    save_email_log,
    get_email_logs,
    get_failed_email_logs,
    update_email_log_status,
    get_all_users,
    update_user_profile,
    create_user,
    get_user_by_username,
    get_user_by_email,
    delete_user_by_id,
    save_user_activity,
    get_user_activity_audit,
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
        .user-table-header { font-weight: 700; background-color: #f5f5f5; padding: 8px; border-radius: 6px; }
        .user-table-cell { padding: 6px 0px; border-bottom: 1px solid #eeeeee; }
        div[data-testid="stPopover"] button { border: none !important; background: transparent !important; box-shadow: none !important; }
        button[aria-label^="Edit user"], button[aria-label^="Delete user"], button[aria-label^="Generate and send"],
        button[title^="Edit user"], button[title^="Delete user"], button[title^="Generate and send"],
        button[title^="Only user"], button[title^="Default admin"], button[title^="Only Admin"], button[title^="Only default admin"] {
            border: 0px !important; outline: none !important; background: transparent !important; box-shadow: none !important;
            padding: 0.05rem 0.15rem !important; min-width: 1rem !important; min-height: 1rem !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_client_ip():
    try:
        headers = st.context.headers
        for header_name in ["x-forwarded-for", "x-real-ip", "client-ip", "x-client-ip", "forwarded"]:
            header_value = headers.get(header_name)
            if header_value:
                return header_value.split(",")[0].strip()
    except Exception:
        pass
    return "UNKNOWN"


def get_user_agent():
    try:
        return st.context.headers.get("user-agent", "UNKNOWN")
    except Exception:
        return "UNKNOWN"


def audit_log(event_type, actor_username="", target_username="", target_email="", actor_role="", status="", details=None):
    if details is None:
        details = {}
    try:
        save_user_activity(event_type, actor_username, target_username, target_email, actor_role, status, get_client_ip(), get_user_agent(), json.dumps(details, default=str))
    except Exception:
        pass


def app_header(current_user=None):
    col1, col2 = st.columns([20, 1])
    with col1:
        st.markdown("<div class='main-title'>🤖 Intelligent Invoice & Expense Reconciliation Agent</div>", unsafe_allow_html=True)
    with col2:
        if current_user:
            with st.popover("👤"):
                st.markdown(f"**User:** {current_user.get('username')}  \n**Role:** {current_user.get('role')}")
                if st.button("Logout", key="top_logout", use_container_width=True):
                    audit_log("LOGOUT", current_user.get("username"), current_user.get("username"), current_user.get("email"), current_user.get("role"), "SUCCESS", {"message": "User logged out"})
                    st.session_state.logged_in = False
                    st.session_state.user = None
                    st.rerun()


def show_required_column_help():
    with st.expander("Required CSV Format Help"):
        st.markdown("""
        ### Purchase Order CSV required columns
        ```text
        po_number,vendor_name,total_amount,status
        ```
        ### Bank Statement CSV required columns
        ```text
        transaction_id,vendor_name,amount,description,date
        ```
        """)


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
    subject = default_subject
    body_lines = []
    body_started = False
    for line in ai_email_text.splitlines():
        clean = line.strip()
        if clean.lower().startswith("subject:"):
            subject = clean.split(":", 1)[1].strip() or default_subject
            continue
        if clean.lower().startswith("body:"):
            body_started = True
            continue
        if body_started:
            body_lines.append(line)
    body = "\n".join(body_lines).strip() or ai_email_text
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
                send_email_from_app(email_to, email_cc, email_bcc, final_subject, final_body)
                save_email_log(invoice_number, email_to, email_cc, email_bcc, final_subject, final_body, "SUCCESS")
                st.success("Email sent successfully.")
            except Exception as e:
                save_email_log(invoice_number, email_to, email_cc, email_bcc, final_subject, final_body, f"FAILED: {e}")
                st.error(f"Email sending failed: {e}")
    with draft_col:
        if st.button("Save As Draft", key=f"{key_prefix}_save_not_sent"):
            save_email_log(invoice_number, email_to, email_cc, email_bcc, final_subject, final_body, "NOT_SENT")
            st.success("Email draft saved as NOT_SENT in database.")


def authentication_page():
    app_header()
    if st.session_state.get("auth_message"):
        st.success(st.session_state.auth_message)
        st.session_state.auth_message = ""

    if st.session_state.get("force_password_reset") and st.session_state.get("force_reset_user"):
        reset_user = st.session_state.force_reset_user
        if reset_user.get("password_expired"):
            st.warning(f"Your password has expired. Passwords expire every {get_password_expiry_days()} days. Please set a new password.")
        else:
            st.warning("First login detected. Please reset your temporary password, then login again.")
        st.info(password_policy_text())
        with st.form("forced_password_reset_form", clear_on_submit=False):
            new_password = st.text_input("New Password", type="password", key="forced_new_password")
            confirm_password = st.text_input("Confirm New Password", type="password", key="forced_confirm_password")
            reset_clicked = st.form_submit_button("Reset Password", use_container_width=True)
            if reset_clicked:
                if not new_password or not confirm_password:
                    st.error("New password and confirm password are required.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    success, message = change_password_first_login(reset_user.get("username"), new_password)
                    audit_log("FORCED_PASSWORD_RESET", reset_user.get("username"), reset_user.get("username"), reset_user.get("email"), reset_user.get("role"), "SUCCESS" if success else "FAILED", {"message": message})
                    if success:
                        st.session_state.auth_message = "Password reset successful. Please login again with your new password."
                        st.session_state.force_password_reset = False
                        st.session_state.force_reset_user = None
                        st.session_state.pending_otp_user = None
                        st.rerun()
                    else:
                        st.error(message)
        st.stop()

    if st.session_state.get("pending_otp_user"):
        otp_user = st.session_state.pending_otp_user
        st.subheader("Login OTP Verification")
        st.info(f"An OTP has been sent to the registered email for user '{otp_user.get('username')}'. OTP expires in {get_login_otp_expiry_minutes()} minutes.")
        with st.form("login_otp_form", clear_on_submit=False):
            otp_code = st.text_input(
                "Enter OTP",
                max_chars=6,
                key="login_otp_code",
                placeholder="Enter 6 digit OTP"
            )
            components.html(
            """
            <script>
                function focusOtp() {
                    const inputs = window.parent.document.querySelectorAll('input');

                    for (let i = 0; i < inputs.length; i++) {
                        let placeholder = inputs[i].getAttribute('placeholder');
                        if (placeholder &&
                            placeholder.includes('Enter 6 digit OTP')) {

                            inputs[i].focus();
                            inputs[i].select();
                            break;
                        }
                    }
                }

                setTimeout(focusOtp, 500);
                setTimeout(focusOtp, 1000);
                setTimeout(focusOtp, 1500);
            </script>
            """,
            height=0,
            )
            c1, c2 = st.columns(2)
            with c1:
                verify_clicked = st.form_submit_button("Verify OTP", use_container_width=True)
            with c2:
                cancel_clicked = st.form_submit_button("Cancel Login", use_container_width=True)
            if verify_clicked:
                success, message = verify_login_otp(otp_user.get("username"), otp_code)
                audit_log("LOGIN_OTP_VERIFY", otp_user.get("username"), otp_user.get("username"), otp_user.get("email"), otp_user.get("role"), "SUCCESS" if success else "FAILED", {"message": message})
                if success:
                    st.session_state.logged_in = True
                    st.session_state.user = otp_user
                    st.session_state.pending_otp_user = None
                    st.success("Login successful.")
                    st.rerun()
                else:
                    st.error(message)
            if cancel_clicked:
                st.session_state.pending_otp_user = None
                st.rerun()
        st.stop()

    auth_tab1, auth_tab2 = st.tabs(["Login", "Forgot Password"])
    with auth_tab1:
        st.subheader("User Login")
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", key="login_username" ,placeholder="Enter username")
            components.html(
                """
                <script>
                    function focusUsername() {
                        const inputs =
                            window.parent.document.querySelectorAll(
                                'input[type="text"]'
                            );

                        if (inputs.length > 0) {
                            inputs[0].focus();
                            inputs[0].select();
                        }
                    }

                    setTimeout(focusUsername, 500);
                    setTimeout(focusUsername, 1000);
                </script>
                """,
                height=0,
            )
            password = st.text_input("Password", type="password", key="login_password")
            login_clicked = st.form_submit_button("Login", use_container_width=True)
            if login_clicked:
                success, message, user_data = authenticate_user(username, password)
                if success:
                    audit_log("LOGIN_PASSWORD_VERIFIED", user_data.get("username"), user_data.get("username"), user_data.get("email"), user_data.get("role"), "SUCCESS", {"password_expired": user_data.get("password_expired"), "must_change_password": user_data.get("must_change_password")})
                    if int(user_data.get("must_change_password", 0)) == 1 or bool(user_data.get("password_expired")):
                        st.session_state.force_password_reset = True
                        st.session_state.force_reset_user = user_data
                        st.rerun()
                    otp_success, otp_message, otp_meta = request_login_otp(user_data.get("username"))
                    audit_log("LOGIN_OTP_SENT", user_data.get("username"), user_data.get("username"), user_data.get("email"), user_data.get("role"), "SUCCESS" if otp_success else "FAILED", {"message": otp_message})
                    if otp_success:
                        st.session_state.pending_otp_user = user_data
                        st.rerun()
                    else:
                        st.error(otp_message)
                else:
                    audit_log("LOGIN_FAILED", username, username, "", "UNKNOWN", "FAILED", {"message": message})
                    st.error(message)
    with auth_tab2:
        st.subheader("Forgot Password")
        st.write("Enter your username or registered email. A reset code will be sent to your registered email.")
        with st.form("forgot_password_form", clear_on_submit=False):
            reset_username_or_email = st.text_input("Username or Email", key="forgot_username_or_email", placeholder="Enter username or email")
            components.html(
                """
                <script>
                    function focusForgotPassword() {

                        const inputs =
                            window.parent.document.querySelectorAll("input");

                        for (let i = 0; i < inputs.length; i++) {

                            let placeholder =
                                inputs[i].getAttribute("placeholder");

                            if (
                                placeholder &&
                                placeholder.includes(
                                    "Enter username or email"
                                )
                            ) {
                                inputs[i].focus();
                                inputs[i].select();
                                break;
                            }
                        }
                    }

                    setTimeout(focusForgotPassword, 500);
                    setTimeout(focusForgotPassword, 1000);
                    setTimeout(focusForgotPassword, 1500);

                </script>
                """,
                height=0,
            )
            send_code_clicked = st.form_submit_button("Send Reset Code", use_container_width=True)
            if send_code_clicked:
                if not reset_username_or_email:
                    st.error("Please enter username or email.")
                else:
                    success, message = request_password_reset(reset_username_or_email)
                    audit_log("PASSWORD_RESET_CODE_REQUEST", reset_username_or_email, reset_username_or_email, "", "UNKNOWN", "SUCCESS" if success else "FAILED", {"message": message})
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
        st.divider()
        st.subheader("Reset Password")
        st.info(password_policy_text())
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
                    audit_log("PASSWORD_RESET", reset_username, reset_username, "", "UNKNOWN", "SUCCESS" if success else "FAILED", {"message": message})
                    if success:
                        st.session_state.auth_message = "Password reset successful. Please login with your new password."
                        st.rerun()
                    else:
                        st.error(message)


for key, default_value in {
    "logged_in": False,
    "user": None,
    "bulk_results": [],
    "force_password_reset": False,
    "force_reset_user": None,
    "pending_otp_user": None,
    "auth_message": "",
    "user_mgmt_message": "",
    "user_mgmt_message_type": "success",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

if not st.session_state.logged_in:
    authentication_page()
    st.stop()

current_user = st.session_state.user
current_role = current_user.get("role")
app_header(current_user)

can_view = has_permission(current_role, "view")
can_edit = has_permission(current_role, "edit")
can_send_email = has_permission(current_role, "send_email")
can_modify_users = str(current_user.get("username", "")).lower() == "admin"
can_view_user_management = can_modify_users or current_role == "Admin"
can_send_user_password = current_role == "Admin"


def render_result_sections(result_record, key_prefix, can_edit, can_send_email):
    invoice_data = result_record["invoice_data"]
    recon_row = result_record["recon_row"]
    duplicate_result = result_record["duplicate_result"]
    anomalies = result_record["anomaly_list"]
    requires_human_review = result_record["requires_human_review"]
    st.subheader("Extracted Invoice Data")
    st.dataframe(pd.DataFrame([{k: result_record.get(k) for k in ["file_name", "invoice_number", "vendor_name", "po_number", "invoice_date", "subtotal", "tax", "invoice_amount"]}]), use_container_width=True)
    with st.expander("Show Raw Extracted Invoice Text"):
        st.text(result_record.get("raw_text", ""))
    st.header("Dashboard Summary")
    show_dashboard(pd.DataFrame([{"status": result_record.get("status"), "duplicate_found": result_record.get("duplicate_found"), "anomaly_count": result_record.get("anomaly_count"), "requires_human_review": result_record.get("requires_human_review")}]))
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
                save_approval_to_db(invoice_data.get("invoice_number"), decision, comment, current_user.get("username"))
                audit_log("INVOICE_APPROVAL_SAVED", current_user.get("username"), "", "", current_user.get("role"), "SUCCESS", {"invoice_number": invoice_data.get("invoice_number"), "decision": decision, "approved_by": current_user.get("username")})
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


if can_view_user_management:
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Recon Section", "Data Section", "Approval Section", "Email Section", "User Management", "Audit Logs"])
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
        invoice_file = None
        invoice_files = None
        if upload_mode == "Single Invoice":
            invoice_file = st.file_uploader("Upload Single Invoice File", type=["txt", "pdf", "png", "jpg", "jpeg"], key="single_invoice_file")
        else:
            invoice_files = st.file_uploader("Upload Multiple Invoice Files", type=["txt", "pdf", "png", "jpg", "jpeg"], accept_multiple_files=True, key="multiple_invoice_files")
        po_df = bank_df = None
        po_valid = bank_valid = False
        if po_file is not None:
            st.header("2. Purchase Order Data")
            try:
                po_df = load_purchase_orders(po_file)
                missing = validate_po_columns(po_df)
                if missing:
                    st.error(f"Purchase Order CSV is missing required columns: {missing}")
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
                missing = validate_bank_columns(bank_df)
                if missing:
                    st.error(f"Bank Statement CSV is missing required columns: {missing}")
                    show_required_column_help()
                else:
                    bank_valid = True
                    st.success("Bank Statement file loaded successfully.")
                    st.dataframe(bank_df, use_container_width=True)
            except Exception as e:
                st.error(f"Error while reading Bank Statement file: {e}")
        if po_valid and bank_valid:
            st.header("4. Basic PO vs Bank Matching")
            try:
                st.dataframe(match_records(po_df, bank_df), use_container_width=True)
            except Exception as e:
                st.error(f"Error during basic PO vs Bank matching: {e}")
        if upload_mode == "Single Invoice" and po_valid and bank_valid and invoice_file is not None:
            st.header("5. Single Invoice Reconciliation")
            try:
                result_record = process_invoice(invoice_file, po_df, bank_df)
                file_name = result_record.get("file_name")
                invoice_number = result_record.get("invoice_number") or "UNKNOWN"
                if not reconciliation_result_exists(file_name, invoice_number):
                    save_reconciliation_result(result_record)
                    st.success("Reconciliation result saved.")
                else:
                    st.info("This invoice result already exists in database. Duplicate entry skipped.")
                render_result_sections(result_record, "single", can_edit, can_send_email)
            except Exception as e:
                st.error(f"Error while processing single invoice: {e}")
        if upload_mode == "Multiple Invoices" and po_valid and bank_valid and invoice_files:
            st.header("5. Multiple Invoice Reconciliation")
            if st.button("Run Bulk Reconciliation"):
                bulk_results = []
                for current_invoice_file in invoice_files:
                    try:
                        record = process_invoice(current_invoice_file, po_df, bank_df)
                        file_name = record.get("file_name")
                        invoice_number = record.get("invoice_number") or "UNKNOWN"
                        if not reconciliation_result_exists(file_name, invoice_number):
                            save_reconciliation_result(record)
                        bulk_results.append(record)
                    except Exception as e:
                        st.error(f"Error processing {current_invoice_file.name}: {e}")
                st.session_state.bulk_results = bulk_results
                st.success("Bulk reconciliation completed and saved into database.")
            if st.session_state.bulk_results:
                results_df = pd.DataFrame(st.session_state.bulk_results)
                st.header("6. Bulk Dashboard")
                show_dashboard(results_df)
                display_columns = ["file_name", "invoice_number", "vendor_name", "po_number", "invoice_date", "invoice_amount", "status", "exception_type", "duplicate_found", "duplicate_match_count", "anomaly_count", "anomalies", "requires_human_review"]
                st.header("7. Consolidated Results")
                st.dataframe(results_df[display_columns], use_container_width=True)
                selected_file = st.selectbox("Select invoice", results_df["file_name"].tolist())
                selected_row = results_df[results_df["file_name"] == selected_file].iloc[0].to_dict()
                selected_invoice_number = selected_row.get("invoice_number") or selected_row.get("file_name")
                render_result_sections(selected_row, f"bulk_{selected_invoice_number}", can_edit, can_send_email)

with tab2:
    if not can_view:
        st.warning("You do not have permission to view records.")
    else:
        st.header("Reconciliation Records")
        rows = get_all_reconciliation_results()
        df = pd.DataFrame(rows, columns=["id", "file_name", "invoice_number", "vendor_name", "po_number", "invoice_date", "invoice_amount", "status", "exception_type", "duplicate_found", "anomaly_count", "requires_human_review", "created_at"])
        if df.empty:
            st.info("No reconciliation records found yet.")
        else:
            st.dataframe(df, use_container_width=True)

with tab3:
    if not can_view:
        st.warning("You do not have permission to view approval records.")
    else:
        st.header("Approval Records")
        rows = get_approval_records()
        df = pd.DataFrame(rows, columns=["id", "invoice_number", "decision", "comment", "approved_by", "decision_time"])
        if df.empty:
            st.info("No approval records found yet.")
        else:
            st.dataframe(df, use_container_width=True)

with tab4:
    if not can_view:
        st.warning("You do not have permission to view email records.")
    else:
        st.header("Email Records")
        rows = get_email_logs()
        df = pd.DataFrame(rows, columns=["id", "invoice_number", "email_to", "email_cc", "email_bcc", "subject", "body", "send_status", "sent_at"])
        if df.empty:
            st.info("No email logs found yet.")
        else:
            st.subheader("All Email Logs")
            st.dataframe(df[["id", "invoice_number", "email_to", "subject", "send_status", "sent_at"]], use_container_width=True)
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
                options = [f"Log ID {row['id']} | Invoice {row['invoice_number']} | To: {row['email_to']} | Status: {row['send_status']}" for _, row in failed_df.iterrows()]
                selected = st.selectbox("Select failed or unsent email", options)
                selected_email = failed_df.iloc[options.index(selected)].to_dict()
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

if can_view_user_management:
    with tab5:
        st.header("User Management")
        if st.session_state.get("user_mgmt_message"):
            if st.session_state.get("user_mgmt_message_type") == "success":
                st.success(st.session_state.user_mgmt_message)
            else:
                st.warning(st.session_state.user_mgmt_message)
            st.session_state.user_mgmt_message = ""
            st.session_state.user_mgmt_message_type = "success"
        users_df = pd.DataFrame(get_all_users(), columns=["id", "username", "email", "role", "is_active", "created_at"])
        if users_df.empty:
            st.info("No users found.")
        else:
            st.subheader("All Users")
            header_cols = st.columns([1, 3, 5, 1.8, 1.4, 3, 1.2, 1.5, 3])
            headers = ["ID", "Username", "Email", "Role", "Active", "Created At", "Edit", "Delete", "Send Password"]
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
                row_cols = st.columns([1, 3, 5, 1.8, 1.4, 3, 1.2, 1.5, 3])
                values = [user_id, username, email, role, "Yes" if is_active == 1 else "No", created_at]
                for idx, value in enumerate(values):
                    with row_cols[idx]:
                        st.markdown(f"<div class='user-table-cell'>{value}</div>", unsafe_allow_html=True)
                with row_cols[6]:
                    if not can_modify_users:
                        st.button("✏️", key=f"edit_disabled_{user_id}", disabled=True, help="Only user 'admin' can edit users.")
                    elif username.lower() == "admin":
                        st.button("🔒", key=f"admin_edit_disabled_{user_id}", disabled=True, help="Default admin user cannot be edited.")
                    else:
                        if st.button("✏️", key=f"edit_user_{user_id}", help=f"Edit user {username}"):
                            st.session_state.edit_user_id = user_id
                            st.rerun()
                with row_cols[7]:
                    if not can_modify_users:
                        st.button("🗑️", key=f"delete_disabled_{user_id}", disabled=True, help="Only user 'admin' can delete users.")
                    elif username.lower() == "admin":
                        st.write("")
                    else:
                        if st.button("🗑️", key=f"delete_user_{user_id}", help=f"Delete user {username}"):
                            delete_user_by_id(user_id)
                            audit_log("USER_DELETED", current_user.get("username"), username, email, current_user.get("role"), "SUCCESS", {"deleted_user_id": user_id, "deleted_role": role})
                            st.session_state.user_mgmt_message = f"User '{username}' deleted successfully."
                            st.session_state.user_mgmt_message_type = "success"
                            st.rerun()
                with row_cols[8]:
                    if not can_send_user_password:
                        st.button("🔑", key=f"send_password_disabled_{user_id}", disabled=True, help="Only Admin role users can send temporary password.")
                    elif username.lower() == "admin" and current_user.get("username", "").lower() != "admin":
                        st.button("🔑", key=f"send_password_admin_disabled_{user_id}", disabled=True, help="Only default admin can reset default admin password.")
                    else:
                        if st.button("🔑", key=f"send_password_{user_id}", help=f"Generate and send temporary password to {username}"):
                            success, message, target_email, email_success, temporary_password = send_temporary_password_for_user(username)
                            audit_log("TEMPORARY_PASSWORD_SENT_FROM_USER_MANAGEMENT", current_user.get("username"), username, target_email or email, current_user.get("role"), "SUCCESS" if success else "FAILED", {"message": message, "email_success": email_success, "temporary_password_visible_to_admin_once": bool(temporary_password)})
                            if success and email_success:
                                st.session_state.user_mgmt_message = "Temporary password sent successfully on email."
                                st.session_state.user_mgmt_message_type = "success"
                                st.rerun()
                            elif success and not email_success:
                                st.warning(message)
                                st.error("Email failed. Copy this temporary password now. It will not be shown again after refresh.")
                                st.code(temporary_password, language="text")
                                st.info("User must use this temporary password once and reset it at next login.")
                            else:
                                st.error(message)
        if "edit_user_id" in st.session_state and can_modify_users:
            edit_user_id = st.session_state.edit_user_id
            edit_rows = users_df[users_df["id"] == edit_user_id]
            if not edit_rows.empty:
                edit_row = edit_rows.iloc[0]
                if str(edit_row["username"]).lower() == "admin":
                    st.warning("Default admin user cannot be edited.")
                    del st.session_state.edit_user_id
                    st.rerun()
                st.subheader(f"Edit User: {edit_row['username']}")
                with st.form("inline_edit_user_form", clear_on_submit=False):
                    edit_username = st.text_input("Username", value=str(edit_row["username"]), key="edit_username")
                    edit_email = st.text_input("Email", value=str(edit_row["email"]), key="edit_email")
                    role_options = ["Admin", "Editor", "Email Sender", "Viewer", "Pending"]
                    current_role_index = role_options.index(edit_row["role"]) if edit_row["role"] in role_options else 0
                    edit_role = st.selectbox("Role", role_options, index=current_role_index, key="edit_role")
                    edit_status = st.selectbox("Status", ["Active", "Inactive"], index=0 if int(edit_row["is_active"]) == 1 else 1, key="edit_status")
                    c1, c2 = st.columns(2)
                    with c1:
                        save_edit = st.form_submit_button("💾 Save Changes", use_container_width=True)
                    with c2:
                        cancel_edit = st.form_submit_button("❌ Cancel", use_container_width=True)
                    if save_edit:
                        edit_username = edit_username.strip()
                        edit_email = edit_email.strip().lower()
                        duplicate_username = get_user_by_username(edit_username)
                        duplicate_email = get_user_by_email(edit_email)
                        if duplicate_username and int(duplicate_username[0]) != int(edit_user_id):
                            st.error("Username already exists. Please use a different username.")
                        elif duplicate_email and int(duplicate_email[0]) != int(edit_user_id):
                            st.error("Email address already exists. Please use a different email address.")
                        else:
                            update_user_profile(edit_user_id, edit_username, edit_email, edit_role, 1 if edit_status == "Active" else 0)
                            audit_log("USER_UPDATED", current_user.get("username"), edit_username, edit_email, current_user.get("role"), "SUCCESS", {"old_username": str(edit_row["username"]), "new_username": edit_username, "old_role": str(edit_row["role"]), "new_role": edit_role})
                            st.session_state.user_mgmt_message = f"User '{edit_username}' edited successfully."
                            st.session_state.user_mgmt_message_type = "success"
                            del st.session_state.edit_user_id
                            st.rerun()
                    if cancel_edit:
                        st.session_state.user_mgmt_message = "No editing done in role."
                        st.session_state.user_mgmt_message_type = "warning"
                        del st.session_state.edit_user_id
                        st.rerun()
        if can_modify_users:
            st.subheader("Create New User")
            with st.form("admin_create_user_form", clear_on_submit=False):
                admin_new_username = st.text_input("Username", key="admin_create_username")
                admin_new_email = st.text_input("Email", key="admin_create_email")
                admin_new_role = st.selectbox("Role", ["Admin", "Editor", "Email Sender", "Viewer"], key="admin_create_role")
                admin_new_status = st.selectbox("Status", ["Active", "Inactive"], key="admin_create_status")
                create_user_clicked = st.form_submit_button("Create User", use_container_width=True)
                if create_user_clicked:
                    admin_new_username = admin_new_username.strip()
                    admin_new_email = admin_new_email.strip().lower()
                    if not admin_new_username or not admin_new_email:
                        st.error("Username and email are required.")
                    elif get_user_by_username(admin_new_username):
                        st.error("Username already exists. Please use a different username.")
                    elif get_user_by_email(admin_new_email):
                        st.error("Email address already exists. Please use a different email address.")
                    else:
                        temp_password = generate_initial_password(12)
                        create_user(admin_new_username, admin_new_email, hash_password(temp_password), admin_new_role, 1 if admin_new_status == "Active" else 0, must_change_password=1)
                        email_success, email_message = send_initial_password_email(admin_new_username, admin_new_email, temp_password)
                        audit_log("USER_CREATED", current_user.get("username"), admin_new_username, admin_new_email, current_user.get("role"), "SUCCESS", {"assigned_role": admin_new_role, "assigned_status": admin_new_status})
                        audit_log("INITIAL_PASSWORD_SENT", current_user.get("username"), admin_new_username, admin_new_email, current_user.get("role"), "SUCCESS" if email_success else "FAILED", {"message": email_message})
                        if email_success:
                            st.session_state.user_mgmt_message = f"Username '{admin_new_username}' created successfully. Initial password was sent to the user's email."
                            st.session_state.user_mgmt_message_type = "success"
                        else:
                            st.session_state.user_mgmt_message = f"Username '{admin_new_username}' created successfully, but initial password email failed: {email_message}"
                            st.session_state.user_mgmt_message_type = "warning"
                        st.rerun()
        else:
            st.info("User Management is view-only for Admin role users. Only username 'admin' can create, edit, delete, or update users.")

if can_view_user_management:
    with tab6:
        st.header("User Activity Audit Logs")
        rows = get_user_activity_audit()
        df = pd.DataFrame(rows, columns=["Audit ID", "Activity Type", "Performed By", "Impacted User", "Impacted Email", "User Role", "Status", "Source IP", "Used Browser / Device", "Activity Details", "Activity Logged-in Time"])
        if df.empty:
            st.info("No user activity audit logs found yet.")
        else:
            st.dataframe(df, use_container_width=True ,hide_index=True)


