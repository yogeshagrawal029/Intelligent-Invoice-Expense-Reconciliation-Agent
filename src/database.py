import sqlite3
from datetime import datetime

DB_NAME = "invoice_agent.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reconciliation_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            invoice_number TEXT,
            vendor_name TEXT,
            po_number TEXT,
            invoice_date TEXT,
            invoice_amount REAL,
            status TEXT,
            exception_type TEXT,
            issues TEXT,
            matched_po TEXT,
            matched_transaction TEXT,
            duplicate_found TEXT,
            duplicate_match_count INTEGER,
            anomaly_count INTEGER,
            anomalies TEXT,
            requires_human_review TEXT,
            rule_based_explanation TEXT,
            langchain_ai_review TEXT,
            langchain_ai_email TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT,
            decision TEXT,
            comment TEXT,
            decision_time TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT,
            email_to TEXT,
            email_cc TEXT,
            email_bcc TEXT,
            subject TEXT,
            body TEXT,
            send_status TEXT,
            sent_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT,
            password_hash TEXT,
            role TEXT,
            is_active INTEGER,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT,
            reset_code TEXT,
            is_used INTEGER,
            expires_at TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_reconciliation_result(result_record):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reconciliation_results (
            file_name, invoice_number, vendor_name, po_number, invoice_date,
            invoice_amount, status, exception_type, issues, matched_po,
            matched_transaction, duplicate_found, duplicate_match_count,
            anomaly_count, anomalies, requires_human_review,
            rule_based_explanation, langchain_ai_review, langchain_ai_email,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        result_record.get("file_name"),
        result_record.get("invoice_number"),
        result_record.get("vendor_name"),
        result_record.get("po_number"),
        result_record.get("invoice_date"),
        result_record.get("invoice_amount"),
        result_record.get("status"),
        result_record.get("exception_type"),
        result_record.get("issues"),
        result_record.get("matched_po"),
        result_record.get("matched_transaction"),
        str(result_record.get("duplicate_found")),
        result_record.get("duplicate_match_count"),
        result_record.get("anomaly_count"),
        result_record.get("anomalies"),
        str(result_record.get("requires_human_review")),
        result_record.get("rule_based_explanation"),
        result_record.get("langchain_ai_review", ""),
        result_record.get("langchain_ai_email", ""),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    conn.commit()
    conn.close()


def get_all_reconciliation_results():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, file_name, invoice_number, vendor_name, po_number,
               invoice_date, invoice_amount, status, exception_type,
               duplicate_found, anomaly_count, requires_human_review, created_at
        FROM reconciliation_results
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def save_approval_to_db(invoice_number, decision, comment):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO approval_decisions (invoice_number, decision, comment, decision_time)
        VALUES (?, ?, ?, ?)
    """, (invoice_number, decision, comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


def get_approval_records():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, invoice_number, decision, comment, decision_time
        FROM approval_decisions
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def save_email_log(invoice_number, email_to, email_cc, email_bcc, subject, body, send_status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO email_logs (
            invoice_number, email_to, email_cc, email_bcc, subject, body, send_status, sent_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (invoice_number, email_to, email_cc, email_bcc, subject, body, send_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


def get_email_logs():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, invoice_number, email_to, email_cc, email_bcc, subject, body, send_status, sent_at
        FROM email_logs
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_failed_email_logs():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, invoice_number, email_to, email_cc, email_bcc, subject, body, send_status, sent_at
        FROM email_logs
        WHERE send_status LIKE 'FAILED%' OR send_status LIKE 'NOT_SENT%'
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def update_email_log_status(log_id, email_to, email_cc, email_bcc, subject, body, send_status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE email_logs
        SET email_to = ?, email_cc = ?, email_bcc = ?, subject = ?, body = ?, send_status = ?, sent_at = ?
        WHERE id = ?
    """, (email_to, email_cc, email_bcc, subject, body, send_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), log_id))
    conn.commit()
    conn.close()


def create_user(username, email, password_hash, role="Pending", is_active=0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (username, email, password_hash, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (username, email, password_hash, role, is_active, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, password_hash, role, is_active, created_at
        FROM users
        WHERE username = ?
    """, (username,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, password_hash, role, is_active, created_at
        FROM users
        WHERE email = ?
    """, (email,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, role, is_active, created_at
        FROM users
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def update_user_role_and_status(user_id, role, is_active):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET role = ?, is_active = ?
        WHERE id = ?
    """, (role, is_active, user_id))
    conn.commit()
    conn.close()


def update_user_profile(user_id, username, email, role, is_active):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET username = ?, email = ?, role = ?, is_active = ?
        WHERE id = ?
    """, (username, email, role, is_active, user_id))
    conn.commit()
    conn.close()


def delete_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def update_user_password(username, new_password_hash):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET password_hash = ?
        WHERE username = ?
    """, (new_password_hash, username))
    conn.commit()
    conn.close()


def save_password_reset_code(username, email, reset_code, expires_at):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO password_reset_tokens (username, email, reset_code, is_used, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (username, email, reset_code, 0, expires_at, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


def get_valid_password_reset_code(username, reset_code):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, reset_code, is_used, expires_at, created_at
        FROM password_reset_tokens
        WHERE username = ? AND reset_code = ? AND is_used = 0
        ORDER BY id DESC
        LIMIT 1
    """, (username, reset_code))
    row = cursor.fetchone()
    conn.close()
    return row


def mark_reset_code_used(reset_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE password_reset_tokens SET is_used = 1 WHERE id = ?", (reset_id,))
    conn.commit()
    conn.close()

