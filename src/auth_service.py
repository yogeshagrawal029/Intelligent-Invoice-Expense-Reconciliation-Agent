import os
import hashlib
import secrets
import random
from datetime import datetime, timedelta

from src.database import (
    create_user,
    get_user_by_username,
    get_user_by_email,
    update_user_password,
    save_password_reset_code,
    get_valid_password_reset_code,
    mark_reset_code_used,
)
from src.email_sender import send_email_from_app


def hash_password(password):
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    ).hex()
    return f"{salt}${password_hash}"


def verify_password(password, stored_password_hash):
    try:
        salt, password_hash = stored_password_hash.split("$")
        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        ).hex()
        return new_hash == password_hash
    except Exception:
        return False


def register_user(username, email, password):
    existing_user = get_user_by_username(username)
    if existing_user:
        return False, "Username already exists."
    hashed_password = hash_password(password)
    create_user(username=username, email=email, password_hash=hashed_password, role="Pending", is_active=0)
    return True, "Registration successful. Please wait for admin approval."


def authenticate_user(username, password):
    user = get_user_by_username(username)
    if not user:
        return False, "Invalid username or password.", None
    user_id, db_username, email, password_hash, role, is_active, created_at = user
    if int(is_active) != 1:
        return False, "User is not active. Please contact admin.", None
    if not verify_password(password, password_hash):
        return False, "Invalid username or password.", None
    user_data = {"id": user_id, "username": db_username, "email": email, "role": role, "is_active": is_active}
    return True, "Login successful.", user_data


def create_default_admin():

    admin_username = os.getenv(
        "DEFAULT_ADMIN_USERNAME",
        "admin"
    )

    admin_email = os.getenv(
        "DEFAULT_ADMIN_EMAIL",
        "admin@example.com"
    )

    admin_password = os.getenv(
        "DEFAULT_ADMIN_PASSWORD",
        "admin123"
    )

    existing_admin = get_user_by_username(
        admin_username
    )

    if existing_admin:
        return

    hashed_password = hash_password(
        admin_password
    )

    create_user(
        username=admin_username,
        email=admin_email,
        password_hash=hashed_password,
        role="Admin",
        is_active=1
    )

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
    user = get_user_by_username(username_or_email)
    if not user:
        user = get_user_by_email(username_or_email)
    if not user:
        return False, "No user found with this username or email."
    user_id, username, email, password_hash, role, is_active, created_at = user
    if int(is_active) != 1:
        return False, "User account is inactive. Please contact admin."
    reset_code = generate_reset_code()
    expires_at = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    save_password_reset_code(username=username, email=email, reset_code=reset_code, expires_at=expires_at)
    subject = "Password Reset Code - Invoice Reconciliation Agent"
    body = f"""
Hello {username},

You requested to reset your password for the Intelligent Invoice & Expense Reconciliation Agent.

Your password reset code is:

{reset_code}

This code will expire in 15 minutes.

If you did not request this reset, please ignore this email.

Regards,
Invoice Reconciliation Agent
"""
    try:
        send_email_from_app(to_emails=email, cc_emails="", bcc_emails="", subject=subject, body=body)
        return True, "Password reset code has been sent to your registered email."
    except Exception as e:
        return False, f"Reset code generated but email sending failed: {e}"


def reset_password_with_code(username, reset_code, new_password):
    reset_record = get_valid_password_reset_code(username, reset_code)
    if not reset_record:
        return False, "Invalid or already used reset code."
    reset_id, db_username, email, db_reset_code, is_used, expires_at, created_at = reset_record
    expires_at_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expires_at_dt:
        return False, "Reset code has expired. Please request a new code."
    new_password_hash = hash_password(new_password)
    update_user_password(username=db_username, new_password_hash=new_password_hash)
    mark_reset_code_used(reset_id)
    return True, "Password reset successful. You can now login with your new password."

