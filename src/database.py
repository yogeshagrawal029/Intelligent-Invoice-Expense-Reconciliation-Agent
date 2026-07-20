import sqlite3
from datetime import datetime


DB_NAME = "invoice_agent.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
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
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS approval_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT,
            decision TEXT,
            comment TEXT,
            decision_time TEXT
        )
        """
    )

    cursor.execute(
        """
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
        """
    )

    conn.commit()
    conn.close()


def save_reconciliation_result(result_record):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO reconciliation_results (
            file_name,
            invoice_number,
            vendor_name,
            po_number,
            invoice_date,
            invoice_amount,
            status,
            exception_type,
            issues,
            matched_po,
            matched_transaction,
            duplicate_found,
            duplicate_match_count,
            anomaly_count,
            anomalies,
            requires_human_review,
            rule_based_explanation,
            langchain_ai_review,
            langchain_ai_email,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
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
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    conn.commit()
    conn.close()


def get_all_reconciliation_results():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            file_name,
            invoice_number,
            vendor_name,
            po_number,
            invoice_date,
            invoice_amount,
            status,
            exception_type,
            duplicate_found,
            anomaly_count,
            requires_human_review,
            created_at
        FROM reconciliation_results
        ORDER BY id DESC
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return rows


def save_approval_to_db(invoice_number, decision, comment):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO approval_decisions (
            invoice_number,
            decision,
            comment,
            decision_time
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            invoice_number,
            decision,
            comment,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    conn.commit()
    conn.close()


def save_email_log(invoice_number, email_to, email_cc, email_bcc, subject, body, send_status):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO email_logs (
            invoice_number,
            email_to,
            email_cc,
            email_bcc,
            subject,
            body,
            send_status,
            sent_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            invoice_number,
            email_to,
            email_cc,
            email_bcc,
            subject,
            body,
            send_status,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    conn.commit()
    conn.close()


def get_email_logs():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            invoice_number,
            email_to,
            subject,
            send_status,
            sent_at
        FROM email_logs
        ORDER BY id DESC
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return rows