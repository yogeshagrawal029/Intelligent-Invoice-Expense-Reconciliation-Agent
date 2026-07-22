import json
from datetime import datetime
import streamlit as st
import pandas as pd

from src.po_parser import load_purchase_orders, validate_po_columns
from src.bank_parser import load_bank_statement, validate_bank_columns
from src.reconciliation_service import process_invoice
from src.matcher import match_records
from src.email_sender import send_email_from_app
from src.ai_agent import generate_langchain_review, generate_langchain_email
from src.chatbot_service import handle_chatbot_message, chatbot_help
from src.auth_service import (
    authenticate_user, create_default_admin, has_permission,
    request_password_reset, reset_password_with_code, change_password_first_login,
    request_login_otp, verify_login_otp, get_rate_limit_status,
    get_login_otp_expiry_seconds, get_login_otp_resend_seconds, get_login_otp_max_resends, get_login_otp_lockout_minutes,
    get_reset_code_expiry_seconds, get_reset_code_resend_seconds, get_reset_code_max_resends, get_reset_code_lockout_minutes,
    get_temp_password_resend_seconds, get_temp_password_max_resends, get_temp_password_lockout_minutes,
    get_password_expiry_days, password_policy_text, hash_password, generate_initial_password,
    send_initial_password_email, send_temporary_password_for_user,
)
from src.database import (
    initialize_database, save_reconciliation_result, reconciliation_result_exists, get_all_reconciliation_results,
    save_approval_to_db, get_approval_records, save_email_log, get_email_logs, get_failed_email_logs,
    update_email_log_status, get_all_users, update_user_profile, create_user, get_user_by_username,
    get_user_by_email, delete_user_by_id, save_user_activity, get_user_activity_audit,
)

st.set_page_config(page_title="Invoice Reconciliation Agent", page_icon="📄", layout="wide")
initialize_database()
create_default_admin()

st.markdown("""
<style>
.main .block-container { padding-top: 1.25rem; max-width: 100%; }
section[data-testid="stSidebar"], div[data-testid="collapsedControl"] { display: none; }
header[data-testid="stHeader"] { height: 0rem; }
.main-title { font-size: 32px; font-weight: 800; color: black; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.user-table-header { font-weight: 700; background-color: #f5f5f5; padding: 8px; border-radius: 6px; }
.user-table-cell { padding: 6px 0px; border-bottom: 1px solid #eeeeee; }
div[data-testid="stPopover"] button, div[data-testid="stButton"] button { box-shadow:none !important; }
.chatbot-wrapper { position: fixed; right: 26px; bottom: 26px; z-index: 999999; }
.chatbot-wrapper button { border-radius: 999px !important; background: #6d28d9 !important; color: white !important; border: none !important; }
</style>
""", unsafe_allow_html=True)


def seconds_remaining(ts):
    if not ts:
        return 0
    try:
        end = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return max(0, int((end - datetime.now()).total_seconds()))
    except Exception:
        return 0


def fmt_seconds(sec):
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def get_client_ip():
    try:
        headers = st.context.headers
        for name in ["x-forwarded-for", "x-real-ip", "client-ip", "x-client-ip", "forwarded"]:
            val = headers.get(name)
            if val:
                return val.split(",")[0].strip()
    except Exception:
        pass
    return "UNKNOWN"


def get_user_agent():
    try:
        return st.context.headers.get("user-agent", "UNKNOWN")
    except Exception:
        return "UNKNOWN"


def audit_log(event_type, actor_username="", target_username="", target_email="", actor_role="", status="", details=None):
    try:
        save_user_activity(event_type, actor_username, target_username, target_email, actor_role, status, get_client_ip(), get_user_agent(), json.dumps(details or {}, default=str))
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
                    audit_log("LOGOUT", current_user.get("username"), current_user.get("username"), current_user.get("email"), current_user.get("role"), "SUCCESS")
                    st.session_state.logged_in = False
                    st.session_state.user = None
                    st.rerun()


def timer_message(label, remaining):
    if remaining > 0:
        st.info(f"⏳ {label} expires in {fmt_seconds(remaining)}")
    else:
        st.error(f"{label} expired.")


def show_rate_message(status, label):
    if status.get("locked_remaining", 0) > 0:
        st.error(f"Maximum {label} resend attempts reached. Try again after {fmt_seconds(status['locked_remaining'])}.")
        return False
    if status.get("cooldown_remaining", 0) > 0:
        st.warning(f"Resend available in {fmt_seconds(status['cooldown_remaining'])}.")
    return True


def auth_page():
    app_header()
    if st.session_state.get("auth_message"):
        st.success(st.session_state.auth_message)
        st.session_state.auth_message = ""

    if st.session_state.get("force_password_reset") and st.session_state.get("force_reset_user"):
        u = st.session_state.force_reset_user
        st.warning(f"Password reset required. Passwords expire after {get_password_expiry_days()} days.")
        st.info(password_policy_text())
        with st.form("forced_password_reset_form"):
            p1 = st.text_input("New Password", type="password")
            p2 = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Reset Password", use_container_width=True):
                if not p1 or not p2:
                    st.error("Both password fields are required.")
                elif p1 != p2:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = change_password_first_login(u.get("username"), p1)
                    audit_log("FORCED_PASSWORD_RESET", u.get("username"), u.get("username"), u.get("email"), u.get("role"), "SUCCESS" if ok else "FAILED", {"message": msg})
                    if ok:
                        st.session_state.force_password_reset = False
                        st.session_state.force_reset_user = None
                        st.session_state.pending_otp_user = None
                        st.session_state.auth_message = "Password reset successful. Please login again."
                        st.rerun()
                    else:
                        st.error(msg)
        st.stop()

    if st.session_state.get("pending_otp_user"):
        u = st.session_state.pending_otp_user
        st.subheader("Login OTP Verification")
        timer_message("OTP", seconds_remaining(st.session_state.get("login_otp_expires_at")))
        status = get_rate_limit_status("LOGIN_OTP", u.get("username"))
        show_rate_message(status, "OTP")
        with st.form("login_otp_form"):
            otp = st.text_input("Enter OTP", max_chars=6, placeholder="123456")
            c1, c2 = st.columns(2)
            with c1:
                verify = st.form_submit_button("Verify OTP", use_container_width=True)
            with c2:
                cancel = st.form_submit_button("Cancel Login", use_container_width=True)
            if verify:
                ok, msg = verify_login_otp(u.get("username"), otp)
                audit_log("LOGIN_OTP_VERIFY", u.get("username"), u.get("username"), u.get("email"), u.get("role"), "SUCCESS" if ok else "FAILED", {"message": msg})
                if ok:
                    st.session_state.logged_in = True
                    st.session_state.user = u
                    st.session_state.pending_otp_user = None
                    st.rerun()
                else:
                    st.error(msg)
            if cancel:
                st.session_state.pending_otp_user = None
                st.rerun()
        if st.button("Resend OTP"):
            ok, msg, meta = request_login_otp(u.get("username"), is_resend=True)
            audit_log("LOGIN_OTP_RESEND", u.get("username"), u.get("username"), u.get("email"), u.get("role"), "SUCCESS" if ok else "FAILED", {"message": msg})
            if ok:
                st.session_state.login_otp_expires_at = meta.get("otp_expires_at")
                st.success("OTP resent successfully.")
                st.rerun()
            else:
                st.error(msg)
        st.caption(f"Max resend attempts: {get_login_otp_max_resends()} | Cooldown: {get_login_otp_resend_seconds()}s | Lockout: {get_login_otp_lockout_minutes()} min")
        st.stop()

    login_tab, forgot_tab = st.tabs(["Login", "Forgot Password"])
    with login_tab:
        st.subheader("User Login")
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login", use_container_width=True):
                ok, msg, user_data = authenticate_user(username, password)
                if ok:
                    audit_log("LOGIN_PASSWORD_VERIFIED", user_data.get("username"), user_data.get("username"), user_data.get("email"), user_data.get("role"), "SUCCESS", {"password_expired": user_data.get("password_expired"), "must_change_password": user_data.get("must_change_password")})
                    if int(user_data.get("must_change_password", 0)) == 1 or bool(user_data.get("password_expired")):
                        st.session_state.force_password_reset = True
                        st.session_state.force_reset_user = user_data
                        st.rerun()
                    otp_ok, otp_msg, meta = request_login_otp(user_data.get("username"))
                    audit_log("LOGIN_OTP_SENT", user_data.get("username"), user_data.get("username"), user_data.get("email"), user_data.get("role"), "SUCCESS" if otp_ok else "FAILED", {"message": otp_msg})
                    if otp_ok:
                        st.session_state.pending_otp_user = user_data
                        st.session_state.login_otp_expires_at = meta.get("otp_expires_at")
                        st.rerun()
                    else:
                        st.error(otp_msg)
                else:
                    audit_log("LOGIN_FAILED", username, username, "", "UNKNOWN", "FAILED", {"message": msg})
                    st.error(msg)
    with forgot_tab:
        st.subheader("Forgot Password")
        with st.form("forgot_password_form"):
            reset_user = st.text_input("Username or Email", placeholder="Enter username or email")
            if st.form_submit_button("Send Reset Code", use_container_width=True):
                ok, msg, meta = request_password_reset(reset_user)
                audit_log("PASSWORD_RESET_CODE_REQUEST", reset_user, reset_user, "", "UNKNOWN", "SUCCESS" if ok else "FAILED", {"message": msg})
                if ok:
                    st.session_state.reset_username_or_email = reset_user
                    st.session_state.reset_code_expires_at = meta.get("reset_expires_at")
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        if st.session_state.get("reset_username_or_email"):
            timer_message("Reset code", seconds_remaining(st.session_state.get("reset_code_expires_at")))
            # Use normalized value when available after user sends code again.
            status = get_rate_limit_status("RESET_CODE", st.session_state.get("reset_username_or_email"))
            show_rate_message(status, "reset code")
            if st.button("Resend Reset Code"):
                ok, msg, meta = request_password_reset(st.session_state.get("reset_username_or_email"), is_resend=True)
                audit_log("PASSWORD_RESET_CODE_RESEND", st.session_state.get("reset_username_or_email"), st.session_state.get("reset_username_or_email"), "", "UNKNOWN", "SUCCESS" if ok else "FAILED", {"message": msg})
                if ok:
                    st.session_state.reset_code_expires_at = meta.get("reset_expires_at")
                    st.success("Reset code resent successfully.")
                    st.rerun()
                else:
                    st.error(msg)
        st.divider()
        st.info(password_policy_text())
        with st.form("reset_password_form"):
            reset_username = st.text_input("Username", key="reset_username")
            reset_code = st.text_input("Reset Code", key="reset_code")
            new_password = st.text_input("New Password", type="password", key="new_reset_password")
            confirm_password = st.text_input("Confirm New Password", type="password", key="confirm_reset_password")
            if st.form_submit_button("Reset Password", use_container_width=True):
                if new_password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = reset_password_with_code(reset_username, reset_code, new_password)
                    audit_log("PASSWORD_RESET", reset_username, reset_username, "", "UNKNOWN", "SUCCESS" if ok else "FAILED", {"message": msg})
                    if ok:
                        st.session_state.auth_message = msg
                        st.session_state.reset_username_or_email = None
                        st.rerun()
                    else:
                        st.error(msg)

for k, v in {"logged_in":False,"user":None,"bulk_results":[],"force_password_reset":False,"force_reset_user":None,"pending_otp_user":None,"auth_message":"","user_mgmt_message":"","user_mgmt_message_type":"success","chat_history":[],"reset_username_or_email":None,"reset_code_expires_at":None,"login_otp_expires_at":None}.items():
    if k not in st.session_state: st.session_state[k]=v

if not st.session_state.logged_in:
    auth_page(); st.stop()

current_user=st.session_state.user; current_role=current_user.get("role")
app_header(current_user)
can_view=has_permission(current_role,"view"); can_edit=has_permission(current_role,"edit"); can_send_email=has_permission(current_role,"send_email")
can_modify_users=str(current_user.get("username","")).lower()=="admin"; can_view_user_management=can_modify_users or current_role=="Admin"; can_send_user_password=current_role=="Admin"

# Floating chatbot
st.markdown('<div class="chatbot-wrapper">', unsafe_allow_html=True)
with st.popover("💬 Ask me anything"):
    st.subheader("Finance Assistant")
    for item in st.session_state.chat_history[-6:]:
        with st.chat_message(item["role"]): st.markdown(item["content"])
    q=st.text_input("Ask me anything", key="chat_q", placeholder="summary")
    if st.button("Ask", key="chat_ask") and q:
        st.session_state.chat_history.append({"role":"user","content":q})
        from src.chatbot_service import handle_chatbot_message
        resp, action = handle_chatbot_message(q,current_user,{"can_view":can_view,"can_edit":can_edit,"can_send_email":can_send_email,"can_modify_users":can_modify_users,"can_view_user_management":can_view_user_management})
        audit_log("CHATBOT_INTERACTION", current_user.get("username"), "", "", current_user.get("role"), "SUCCESS", {"question":q,"action":action})
        st.session_state.chat_history.append({"role":"assistant","content":resp}); st.rerun()
    if st.button("Help", key="chat_help"):
        from src.chatbot_service import chatbot_help
        st.session_state.chat_history.append({"role":"assistant","content":chatbot_help()}); st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

if can_view_user_management:
    tab1,tab2,tab3,tab4,tab5,tab6=st.tabs(["Recon Section","Data Section","Approval Section","Email Section","User Management","Audit Logs"])
else:
    tab1,tab2,tab3,tab4=st.tabs(["Recon Section","Data Section","Approval Section","Email Section"])

with tab1:
    st.header("Reconciliation")
    if not can_edit: st.warning("You do not have permission to process invoices.")
    else:
        po_file=st.file_uploader("Upload Purchase Order CSV",type=["csv"]); bank_file=st.file_uploader("Upload Bank Statement CSV",type=["csv"]); invoice_file=st.file_uploader("Upload Invoice",type=["txt","pdf","png","jpg","jpeg"])
        if po_file and bank_file and invoice_file:
            po_df=load_purchase_orders(po_file); bank_df=load_bank_statement(bank_file)
            if validate_po_columns(po_df) or validate_bank_columns(bank_df): st.error("CSV columns are missing. Please check upload format.")
            else:
                st.dataframe(match_records(po_df,bank_df), use_container_width=True)
                result=process_invoice(invoice_file,po_df,bank_df)
                if not reconciliation_result_exists(result.get("file_name"), result.get("invoice_number") or "UNKNOWN"):
                    save_reconciliation_result(result)
                st.json({k: result.get(k) for k in ["invoice_number","vendor_name","po_number","invoice_amount","status","exception_type","requires_human_review"]})

with tab2:
    st.header("Reconciliation Records")
    df=pd.DataFrame(get_all_reconciliation_results(),columns=["ID","File Name","Invoice Number","Vendor","PO Number","Invoice Date","Amount","Status","Exception","Duplicate","Anomaly Count","Human Review","Created At"])
    if df.empty: st.info("No reconciliation records found yet.")
    else: st.dataframe(df,use_container_width=True,hide_index=True)

with tab3:
    st.header("Approval Records")
    df=pd.DataFrame(get_approval_records(),columns=["Approval ID","Invoice Number","Decision","Comment","Approved By","Approval Time"])
    if df.empty: st.info("No approval records found yet.")
    else: st.dataframe(df,use_container_width=True,hide_index=True)

with tab4:
    st.header("Email Records")
    df=pd.DataFrame(get_email_logs(),columns=["Email ID","Invoice","To","CC","BCC","Subject","Body","Status","Sent At"])
    if df.empty: st.info("No email logs found yet.")
    else: st.dataframe(df[["Email ID","Invoice","To","Subject","Status","Sent At"]],use_container_width=True,hide_index=True)

if can_view_user_management:
    with tab5:
        st.header("User Management")
        if st.session_state.user_mgmt_message:
            (st.success if st.session_state.user_mgmt_message_type=="success" else st.warning)(st.session_state.user_mgmt_message)
            st.session_state.user_mgmt_message=""; st.session_state.user_mgmt_message_type="success"
        users_df=pd.DataFrame(get_all_users(),columns=["id","username","email","role","is_active","created_at"])
        if users_df.empty: st.info("No users found.")
        else:
            st.dataframe(users_df.rename(columns={"id":"ID","username":"Username","email":"Email","role":"Role","is_active":"Active","created_at":"Created At"}), use_container_width=True, hide_index=True)
            selected=st.selectbox("Select user for action", users_df["username"].tolist())
            selected_row=users_df[users_df["username"]==selected].iloc[0]
            c1, c2, c3 = st.columns(3)
            with c1:
                can_edit_selected_user = (
                    can_modify_users
                    and selected.lower() != "admin"
                )

                if can_edit_selected_user:
                    if st.button(
                        "Edit selected user",
                        key=f"edit_user_btn_{selected_row['id']}"
                    ):
                        st.session_state.edit_user_id = int(selected_row["id"])
                        st.rerun()
                else:
                    st.button(
                        "Edit selected user",
                        disabled=True,
                        key=f"edit_user_disabled_btn_{selected_row['id']}"
                    )

            with c2:
                can_delete_selected_user = (
                    can_modify_users
                    and selected.lower() != "admin"
                )

                if can_delete_selected_user:
                    if st.button(
                        "Delete selected user",
                        key=f"delete_user_btn_{selected_row['id']}"
                    ):
                        delete_user_by_id(int(selected_row["id"]))

                        audit_log(
                            "USER_DELETED",
                            current_user.get("username"),
                            selected,
                            selected_row["email"],
                            current_user.get("role"),
                            "SUCCESS"
                        )

                        st.session_state.user_mgmt_message = (
                            f"User '{selected}' deleted successfully."
                        )
                        st.session_state.user_mgmt_message_type = "success"
                        st.rerun()
                else:
                    st.button(
                        "Delete selected user",
                        disabled=True,
                        key=f"delete_user_disabled_btn_{selected_row['id']}"
                    )

            with c3:
                status = get_rate_limit_status("TEMP_PASSWORD", selected)

                locked_remaining = int(status.get("locked_remaining", 0) or 0)
                cooldown_remaining = int(status.get("cooldown_remaining", 0) or 0)

                can_send_temp_password = (
                    can_send_user_password
                    and locked_remaining <= 0
                    and cooldown_remaining <= 0
                    and not (
                        selected.lower() == "admin"
                        and current_user.get("username", "").lower() != "admin"
                    )
                )

                if locked_remaining > 0:
                    st.error(
                        f"Send password locked for {fmt_seconds(locked_remaining)}"
                    )
                    st.button(
                        "Send temporary password",
                        disabled=True,
                        key=f"send_temp_pwd_locked_btn_{selected_row['id']}"
                    )

                elif cooldown_remaining > 0:
                    st.warning(
                        f"Send password available in {fmt_seconds(cooldown_remaining)}"
                    )
                    st.button(
                        "Send temporary password",
                        disabled=True,
                        key=f"send_temp_pwd_cooldown_btn_{selected_row['id']}"
                    )

                elif can_send_temp_password:
                    if st.button(
                        "Send temporary password",
                        key=f"send_temp_pwd_btn_{selected_row['id']}"
                    ):
                        ok, msg, email, email_success, temp_pwd = (
                            send_temporary_password_for_user(selected)
                        )

                        audit_log(
                            "TEMP_PASSWORD_SENT",
                            current_user.get("username"),
                            selected,
                            email,
                            current_user.get("role"),
                            "SUCCESS" if ok else "FAILED",
                            {"message": msg}
                        )

                        if ok and email_success:
                            st.session_state.user_mgmt_message = (
                                "Temporary password sent successfully on email."
                            )
                            st.session_state.user_mgmt_message_type = "success"
                            st.rerun()

                        elif ok:
                            st.warning(msg)
                            st.code(temp_pwd, language="text")

                        else:
                            st.error(msg)

                else:
                    st.button(
                        "Send temporary password",
                        disabled=True,
                        key=f"send_temp_pwd_disabled_btn_{selected_row['id']}"
                    )
        if "edit_user_id" in st.session_state and can_modify_users:
            row=users_df[users_df["id"]==st.session_state.edit_user_id]
            if not row.empty:
                r=row.iloc[0]
                with st.form("edit_user_form"):
                    eu=st.text_input("Username", value=r["username"]); ee=st.text_input("Email", value=r["email"]); er=st.selectbox("Role",["Admin","Editor","Email Sender","Viewer","Pending"], index=["Admin","Editor","Email Sender","Viewer","Pending"].index(r["role"]) if r["role"] in ["Admin","Editor","Email Sender","Viewer","Pending"] else 0); es=st.selectbox("Status",["Active","Inactive"], index=0 if int(r["is_active"])==1 else 1)
                    if st.form_submit_button("Save Changes"):
                        update_user_profile(st.session_state.edit_user_id,eu,ee,er,1 if es=="Active" else 0); st.session_state.user_mgmt_message=f"User '{eu}' edited successfully."; del st.session_state.edit_user_id; st.rerun()
                    if st.form_submit_button("Cancel"):
                        st.session_state.user_mgmt_message="No editing done in role."; st.session_state.user_mgmt_message_type="warning"; del st.session_state.edit_user_id; st.rerun()
        if can_modify_users:
            with st.expander("Create New User"):
                with st.form("create_user_form"):
                    nu=st.text_input("Username"); ne=st.text_input("Email"); nr=st.selectbox("Role",["Admin","Editor","Email Sender","Viewer"]); ns=st.selectbox("Status",["Active","Inactive"])
                    if st.form_submit_button("Create User"):
                        if get_user_by_username(nu): st.error("Username already exists.")
                        elif get_user_by_email(ne): st.error("Email already exists.")
                        else:
                            pwd=generate_initial_password(12); create_user(nu,ne,hash_password(pwd),nr,1 if ns=="Active" else 0,1); ok,msg=send_initial_password_email(nu,ne,pwd); st.session_state.user_mgmt_message=f"Username '{nu}' created successfully."; st.rerun()
    with tab6:
        st.header("User Activity Audit Logs")
        df=pd.DataFrame(get_user_activity_audit(), columns=["Audit ID","Activity Type","Performed By","Impacted User","Impacted Email","User Role","Status","Source IP","Used Browser / Device","Activity Details","Activity Time"])
        if df.empty: st.info("No user activity audit logs found yet.")
        else: st.dataframe(df,use_container_width=True,hide_index=True)

