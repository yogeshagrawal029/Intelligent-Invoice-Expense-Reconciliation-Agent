import os
from dotenv import load_dotenv

load_dotenv()


def get_secret(secret_name, default=None, required=False):
    value = None
    try:
        import streamlit as st
        if secret_name in st.secrets:
            value = st.secrets[secret_name]
    except Exception:
        value = None
    if value in (None, ""):
        value = os.getenv(secret_name, default)
    if required and value in (None, ""):
        raise ValueError(f"Required secret '{secret_name}' is missing.")
    return value


def get_int_secret(secret_name, default):
    try:
        return int(get_secret(secret_name, default))
    except Exception:
        return int(default)


def get_timer_config():
    return {
        "PASSWORD_EXPIRY_DAYS": get_int_secret("PASSWORD_EXPIRY_DAYS", 60),
        "LOGIN_OTP_EXPIRY_SECONDS": get_int_secret("LOGIN_OTP_EXPIRY_SECONDS", 60),
        "LOGIN_OTP_RESEND_SECONDS": get_int_secret("LOGIN_OTP_RESEND_SECONDS", 60),
        "LOGIN_OTP_MAX_RESENDS": get_int_secret("LOGIN_OTP_MAX_RESENDS", 5),
        "LOGIN_OTP_LOCKOUT_MINUTES": get_int_secret("LOGIN_OTP_LOCKOUT_MINUTES", 60),
        "RESET_CODE_EXPIRY_SECONDS": get_int_secret("RESET_CODE_EXPIRY_SECONDS", 60),
        "RESET_CODE_RESEND_SECONDS": get_int_secret("RESET_CODE_RESEND_SECONDS", 60),
        "RESET_CODE_MAX_RESENDS": get_int_secret("RESET_CODE_MAX_RESENDS", 5),
        "RESET_CODE_LOCKOUT_MINUTES": get_int_secret("RESET_CODE_LOCKOUT_MINUTES", 60),
        "TEMP_PASSWORD_RESEND_SECONDS": get_int_secret("TEMP_PASSWORD_RESEND_SECONDS", 60),
        "TEMP_PASSWORD_MAX_RESENDS": get_int_secret("TEMP_PASSWORD_MAX_RESENDS", 5),
        "TEMP_PASSWORD_LOCKOUT_MINUTES": get_int_secret("TEMP_PASSWORD_LOCKOUT_MINUTES", 60),
    }

