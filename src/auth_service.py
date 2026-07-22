import os
import re
import hashlib
import secrets
import random
import string
from datetime import datetime, timedelta

from src.config import get_secret, get_int_secret
from src.database import (
    create_user,
    get_user_by_username,
    get_user_by_email,
    update_user_password,
    update_user_profile,
    get_password_history,
    save_password_reset_code,
    get_valid_password_reset_code,
    mark_reset_code_used,
    save_login_otp,
    get_valid_login_otp,
    mark_login_otp_used,
)
from src.email_sender import send_email_from_app

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 16
PASSWORD_HISTORY_LIMIT = 3
ALLOWED_SPECIALS = "@#!"
ALLOWED_PASSWORD_REGEX = re.compile(r"^[A-Za-z0-9@#!]+$")


def get_password_expiry_days():
    return get_int_secret("PASSWORD_EXPIRY_DAYS", 60)


def get_login_otp_expiry_minutes():
    return get_int_secret("LOGIN_OTP_EXPIRY_MINUTES", 10)


def validate_password_policy(password):
    if not password:
        return False, "Password is required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return False, f"Password must not be more than {MAX_PASSWORD_LENGTH} characters."
    if not ALLOWED_PASSWORD_REGEX.match(password):
        return False, "Password can contain only uppercase letters, lowercase letters, numbers 0-9, and @, #, !."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[@#!]", password):
        return False, "Password must contain at least one special character: @, #, or !."
    if has_repeated_character_run(password):
        return False, "Password must not contain the same character repeated 4 or more times."
    if has_sequential_pattern(password):
        return False, "Password must not contain sequential patterns like 1234, 12345, abcd, or dcba."
    return True, "Password policy validation passed."


def has_repeated_character_run(password, run_length=4):
    normalized = password.lower()
    count = 1
    previous = ""
    for char in normalized:
        if char == previous:
            count += 1
            if count >= run_length:
                return True
        else:
            count = 1
            previous = char
    return False


def has_sequential_pattern(password, sequence_length=4):
    normalized = password.lower()
    sequences = ["0123456789", "9876543210", "abcdefghijklmnopqrstuvwxyz", "zyxwvutsrqponmlkjihgfedcba"]
    for sequence in sequences:
        for i in range(0, len(sequence) - sequence_length + 1):
            if sequence[i:i + sequence_length] in normalized:
                return True
    return False


def password_policy_text():
    return f"""
Password rules:
- Password length must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters.
- Allowed characters: uppercase letters, lowercase letters, numbers 0 through 9, and only these special characters: @, #, !
- Password must contain at least one uppercase letter.
- Password must contain at least one lowercase letter.
- Password must contain at least one number.
- Password must contain at least one special character: @, #, or !
- Password must not contain sequential patterns like 1234, 12345, abcd, or dcba.
- Password must not contain the same character repeated 4 or more times.
- Last {PASSWORD_HISTORY_LIMIT} passwords cannot be reused.
- Password expires after {get_password_expiry_days()} days.
"""


def hash_password(password):
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"{salt}${password_hash}"


def verify_password(password, stored_password_hash):
    try:
        salt, password_hash = stored_password_hash.split("$")
        new_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
        return new_hash == password_hash
    except Exception:
        return False


def password_was_used_recently(username, new_password):
    for old_hash in get_password_history(username, PASSWORD_HISTORY_LIMIT):
        if verify_password(new_password, old_hash):
            return True
    return False


def is_password_expired(password_changed_at):
    if not password_changed_at:
        return True
    try:
        changed_at = datetime.strptime(password_changed_at, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return True
    return datetime.now() >= changed_at + timedelta(days=get_password_expiry_days())


def generate_initial_password(length=12):
    length = max(MIN_PASSWORD_LENGTH, min(length, MAX_PASSWORD_LENGTH))
    while True:
        chars = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice(ALLOWED_SPECIALS),
        ]
        pool = string.ascii_letters + string.digits + ALLOWED_SPECIALS
        chars.extend(secrets.choice(pool) for _ in range(length - len(chars)))
        secrets.SystemRandom().shuffle(chars)
        password = "".join(chars)
        valid, _ = validate_password_policy(password)
        if valid:
            return password


def send_initial_password_email(username, email, temporary_password):
    subject = "Initial Login Password - Invoice Reconciliation Agent"
    body = f"""
Hello {username},

Your account has been created for the Intelligent Invoice & Expense Reconciliation Agent.

Username: {username}
Temporary Password: {temporary_password}

You must change this temporary password during your first login.

{password_policy_text()}

Regards,
Invoice Reconciliation Agent
"""
    try:
        send_email_from_app(email, "", "", subject, body)
        return True, "Initial password email sent successfully."
    except Exception as e:
        return False, f"Initial password email failed: {e}"


def send_password_changed_email(username, email, change_context="password reset"):
    subject = "Password Changed - Invoice Reconciliation Agent"
    body = f"""
Hello {username},

Your password for the Intelligent Invoice & Expense Reconciliation Agent was changed successfully.

Change type: {change_context}

If you did not perform this action, please contact the application administrator immediately.

Regards,
Invoice Reconciliation Agent
"""
    try:
        send_email_from_app(email, "", "", subject, body)
        return True, "Password change notification email sent successfully."
    except Exception as e:
        return False, f"Password changed, but notification email failed: {e}"


def send_login_otp_email(username, email, otp_code):
    expiry_minutes = get_login_otp_expiry_minutes()
    subject = "Login OTP - Invoice Reconciliation Agent"
    body = f"""
Hello {username},

Your login OTP for the Intelligent Invoice & Expense Reconciliation Agent is:

{otp_code}

This OTP will expire in {expiry_minutes} minutes.

If you did not attempt to login, please contact the application administrator immediately.

Regards,
Invoice Reconciliation Agent
"""
    try:
        send_email_from_app(email, "", "", subject, body)
        return True, "Login OTP sent successfully."
    except Exception as e:
        return False, f"Login OTP email failed: {e}"


def request_login_otp(username):
    user = get_user_by_username(username)
    if not user:
        return False, "User not found.", None
    user_id, db_username, email, password_hash, role, is_active, created_at, must_change_password, password_changed_at = user
    otp_code = str(random.randint(100000, 999999))
    expires_at = (datetime.now() + timedelta(minutes=get_login_otp_expiry_minutes())).strftime("%Y-%m-%d %H:%M:%S")
    save_login_otp(db_username, email, otp_code, expires_at)
    email_success, message = send_login_otp_email(db_username, email, otp_code)
    return email_success, message, {"username": db_username, "email": email, "role": role}


def verify_login_otp(username, otp_code):
    record = get_valid_login_otp(username, otp_code)
    if not record:
        return False, "Invalid or already used OTP."
    otp_id, db_username, email, db_otp, is_used, expires_at, created_at = record
    try:
        expires_at_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return False, "Invalid OTP expiry time."
    if datetime.now() > expires_at_dt:
        return False, "OTP has expired. Please login again."
    mark_login_otp_used(otp_id)
    return True, "OTP verified successfully."


def authenticate_user(username, password):
    user = get_user_by_username(username)
    if not user:
        return False, "Invalid username or password.", None
    user_id, db_username, email, password_hash, role, is_active, created_at, must_change_password, password_changed_at = user
    if int(is_active) != 1:
        return False, "User is not active. Please contact admin.", None
    if not verify_password(password, password_hash):
        return False, "Invalid username or password.", None

    password_expired = is_password_expired(password_changed_at)
    user_data = {
        "id": user_id,
        "username": db_username,
        "email": email,
        "role": role,
        "is_active": is_active,
        "must_change_password": must_change_password,
        "password_expired": password_expired,
    }
    return True, "Password verified successfully. OTP is required to continue.", user_data


def create_default_admin():
    admin_username = get_secret("DEFAULT_ADMIN_USERNAME", "admin")
    admin_email = get_secret("DEFAULT_ADMIN_EMAIL", get_secret("SMTP_EMAIL", "admin@example.com")).strip().lower()
    if get_user_by_username(admin_username):
        return
    temporary_password = generate_initial_password(12)
    create_user(admin_username, admin_email, hash_password(temporary_password), role="Admin", is_active=1, must_change_password=1)
    send_initial_password_email(admin_username, admin_email, temporary_password)


def has_permission(role, permission):
    permissions = {
        "Admin": ["view", "edit", "send_email", "manage_users"],
        "Editor": ["view", "edit"],
        "Email Sender": ["view", "send_email"],
        "Viewer": ["view"],
        "Pending": [],
    }
    return permission in permissions.get(role, [])


def generate_reset_code():
    return str(random.randint(100000, 999999))


def request_password_reset(username_or_email):
    user = get_user_by_username(username_or_email.strip()) or get_user_by_email(username_or_email.strip().lower())
    if not user:
        return False, "No user found with this username or email."
    user_id, username, email, password_hash, role, is_active, created_at, must_change_password, password_changed_at = user
    if int(is_active) != 1:
        return False, "User account is inactive. Please contact admin."
    reset_code = generate_reset_code()
    expires_at = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    save_password_reset_code(username, email, reset_code, expires_at)
    subject = "Password Reset Code - Invoice Reconciliation Agent"
    body = f"""
Hello {username},

Your password reset code is:

{reset_code}

This code will expire in 15 minutes.

{password_policy_text()}

Regards,
Invoice Reconciliation Agent
"""
    try:
        send_email_from_app(email, "", "", subject, body)
        return True, "Password reset code has been sent to your registered email."
    except Exception as e:
        return False, f"Reset code generated but email sending failed: {e}"


def reset_password_with_code(username, reset_code, new_password):
    valid, msg = validate_password_policy(new_password)
    if not valid:
        return False, msg
    if password_was_used_recently(username, new_password):
        return False, f"You cannot reuse your last {PASSWORD_HISTORY_LIMIT} passwords."
    reset_record = get_valid_password_reset_code(username, reset_code)
    if not reset_record:
        return False, "Invalid or already used reset code."
    reset_id, db_username, email, db_reset_code, is_used, expires_at, created_at = reset_record
    if datetime.now() > datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S"):
        return False, "Reset code has expired. Please request a new code."
    update_user_password(db_username, hash_password(new_password), must_change_password=0)
    mark_reset_code_used(reset_id)
    send_password_changed_email(db_username, email, "forgot password reset")
    return True, "Password reset successful. Please login with your new password."


def change_password_first_login(username, new_password):
    valid, msg = validate_password_policy(new_password)
    if not valid:
        return False, msg
    if password_was_used_recently(username, new_password):
        return False, f"You cannot reuse your last {PASSWORD_HISTORY_LIMIT} passwords."
    user = get_user_by_username(username)
    if not user:
        return False, "User not found."
    user_id, db_username, email, password_hash, role, is_active, created_at, must_change_password, password_changed_at = user
    update_user_password(db_username, hash_password(new_password), must_change_password=0)
    send_password_changed_email(db_username, email, "first-time or expired password change")
    return True, "Password changed successfully. Please login again."


def send_temporary_password_for_user(username):
    user = get_user_by_username(username)
    if not user:
        return False, "User not found.", None, False, None
    user_id, db_username, email, password_hash, role, is_active, created_at, must_change_password, password_changed_at = user
    if int(is_active) != 1:
        return False, "User account is inactive. Activate the user before sending a temporary password.", email, False, None
    temporary_password = generate_initial_password(12)
    update_user_password(db_username, hash_password(temporary_password), must_change_password=1)
    email_success, email_message = send_initial_password_email(db_username, email, temporary_password)
    if email_success:
        return True, "Temporary password sent successfully. User must reset password on next login.", email, True, None
    return True, f"Temporary password generated and set, but email failed: {email_message}", email, False, temporary_password

