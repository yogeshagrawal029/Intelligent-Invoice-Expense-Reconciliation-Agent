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
    value = get_secret(secret_name, default)
    try:
        return int(value)
    except Exception:
        return int(default)

