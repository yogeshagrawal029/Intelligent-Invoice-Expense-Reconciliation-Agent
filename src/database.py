import sqlite3
from datetime import datetime

DB_NAME = "invoice_agent.db"


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_connection():
    return sqlite3.connect(DB_NAME)


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return column_name in [row[1] for row in cursor.fetchall()]


def initialize_database():
    conn = get_connection(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, email TEXT UNIQUE, password_hash TEXT, role TEXT, is_active INTEGER, must_change_password INTEGER DEFAULT 0, password_changed_at TEXT, created_at TEXT)""")
    if not column_exists(c, "users", "must_change_password"):
        c.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0")
    if not column_exists(c, "users", "password_changed_at"):
        c.execute("ALTER TABLE users ADD COLUMN password_changed_at TEXT")
    c.execute("""CREATE TABLE IF NOT EXISTS password_history (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password_hash TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS password_reset_tokens (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, email TEXT, reset_code TEXT, is_used INTEGER, expires_at TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS login_otp_tokens (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, email TEXT, otp_code TEXT, is_used INTEGER, expires_at TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS action_rate_limits (id INTEGER PRIMARY KEY AUTOINCREMENT, action_key TEXT UNIQUE, category TEXT, identifier TEXT, resend_count INTEGER, cooldown_until TEXT, locked_until TEXT, updated_at TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS reconciliation_results (id INTEGER PRIMARY KEY AUTOINCREMENT, file_name TEXT, invoice_number TEXT, vendor_name TEXT, po_number TEXT, invoice_date TEXT, invoice_amount REAL, status TEXT, exception_type TEXT, issues TEXT, matched_po TEXT, matched_transaction TEXT, duplicate_found TEXT, duplicate_match_count INTEGER, anomaly_count INTEGER, anomalies TEXT, requires_human_review TEXT, rule_based_explanation TEXT, langchain_ai_review TEXT, langchain_ai_email TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS approval_decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_number TEXT, decision TEXT, comment TEXT, approved_by TEXT, decision_time TEXT)""")
    if not column_exists(c, "approval_decisions", "approved_by"):
        c.execute("ALTER TABLE approval_decisions ADD COLUMN approved_by TEXT")
    c.execute("""CREATE TABLE IF NOT EXISTS email_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_number TEXT, email_to TEXT, email_cc TEXT, email_bcc TEXT, subject TEXT, body TEXT, send_status TEXT, sent_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_activity_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, actor_username TEXT, target_username TEXT, target_email TEXT, actor_role TEXT, status TEXT, ip_address TEXT, user_agent TEXT, details TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS chatbot_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, role TEXT, user_message TEXT, bot_response TEXT, action_taken TEXT, created_at TEXT)""")
    conn.commit(); conn.close()


def normalize_user_row(row):
    if row is None: return None
    if len(row) == 7:
        uid, username, email, password_hash, role, is_active, created_at = row
        return (uid, username, email, password_hash, role, is_active, created_at, 0, None)
    if len(row) == 8:
        uid, username, email, password_hash, role, is_active, created_at, must_change = row
        return (uid, username, email, password_hash, role, is_active, created_at, must_change, None)
    return row


def create_user(username, email, password_hash, role="Pending", is_active=0, must_change_password=0, password_changed_at=None):
    changed_at = password_changed_at or now()
    conn = get_connection(); c = conn.cursor()
    c.execute("INSERT INTO users (username,email,password_hash,role,is_active,must_change_password,password_changed_at,created_at) VALUES (?,?,?,?,?,?,?,?)", (username.strip(), email.strip().lower(), password_hash, role, is_active, must_change_password, changed_at, now()))
    conn.commit(); conn.close(); save_password_history(username, password_hash)


def get_user_by_username(username):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT id, username, email, password_hash, role, is_active, created_at, must_change_password, password_changed_at FROM users WHERE username=?", (username.strip(),))
    row = normalize_user_row(c.fetchone()); conn.close(); return row


def get_user_by_email(email):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT id, username, email, password_hash, role, is_active, created_at, must_change_password, password_changed_at FROM users WHERE lower(email)=lower(?)", (email.strip().lower(),))
    row = normalize_user_row(c.fetchone()); conn.close(); return row


def get_all_users():
    conn = get_connection(); c = conn.cursor(); c.execute("SELECT id, username, email, role, is_active, created_at FROM users ORDER BY id DESC"); rows=c.fetchall(); conn.close(); return rows


def update_user_profile(user_id, username, email, role, is_active):
    conn=get_connection(); c=conn.cursor(); c.execute("UPDATE users SET username=?, email=?, role=?, is_active=? WHERE id=?", (username.strip(), email.strip().lower(), role, is_active, user_id)); conn.commit(); conn.close()


def delete_user_by_id(user_id):
    conn=get_connection(); c=conn.cursor(); c.execute("DELETE FROM users WHERE id=?", (user_id,)); conn.commit(); conn.close()


def update_user_password(username, new_password_hash, must_change_password=0):
    conn=get_connection(); c=conn.cursor(); c.execute("UPDATE users SET password_hash=?, must_change_password=?, password_changed_at=? WHERE username=?", (new_password_hash, must_change_password, now(), username.strip())); conn.commit(); conn.close(); save_password_history(username, new_password_hash)


def save_password_history(username, password_hash):
    conn=get_connection(); c=conn.cursor(); c.execute("INSERT INTO password_history (username,password_hash,created_at) VALUES (?,?,?)", (username.strip(), password_hash, now())); conn.commit(); conn.close()


def get_password_history(username, limit=3):
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT password_hash FROM password_history WHERE username=? ORDER BY id DESC LIMIT ?", (username.strip(), limit)); rows=c.fetchall(); conn.close(); return [r[0] for r in rows]


def save_password_reset_code(username, email, reset_code, expires_at):
    conn=get_connection(); c=conn.cursor(); c.execute("INSERT INTO password_reset_tokens (username,email,reset_code,is_used,expires_at,created_at) VALUES (?,?,?,?,?,?)", (username,email,reset_code,0,expires_at,now())); conn.commit(); conn.close()


def get_valid_password_reset_code(username, reset_code):
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id,username,email,reset_code,is_used,expires_at,created_at FROM password_reset_tokens WHERE username=? AND reset_code=? AND is_used=0 ORDER BY id DESC LIMIT 1", (username.strip(), reset_code.strip())); row=c.fetchone(); conn.close(); return row


def mark_reset_code_used(reset_id):
    conn=get_connection(); c=conn.cursor(); c.execute("UPDATE password_reset_tokens SET is_used=1 WHERE id=?", (reset_id,)); conn.commit(); conn.close()


def save_login_otp(username, email, otp_code, expires_at):
    conn=get_connection(); c=conn.cursor(); c.execute("INSERT INTO login_otp_tokens (username,email,otp_code,is_used,expires_at,created_at) VALUES (?,?,?,?,?,?)", (username,email,otp_code,0,expires_at,now())); conn.commit(); conn.close()


def get_valid_login_otp(username, otp_code):
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id,username,email,otp_code,is_used,expires_at,created_at FROM login_otp_tokens WHERE username=? AND otp_code=? AND is_used=0 ORDER BY id DESC LIMIT 1", (username.strip(), otp_code.strip())); row=c.fetchone(); conn.close(); return row


def mark_login_otp_used(otp_id):
    conn=get_connection(); c=conn.cursor(); c.execute("UPDATE login_otp_tokens SET is_used=1 WHERE id=?", (otp_id,)); conn.commit(); conn.close()


def get_rate_limit(category, identifier):
    action_key=f"{category}:{identifier}"; conn=get_connection(); c=conn.cursor(); c.execute("SELECT action_key, category, identifier, resend_count, cooldown_until, locked_until, updated_at, created_at FROM action_rate_limits WHERE action_key=?", (action_key,)); row=c.fetchone(); conn.close(); return row


def upsert_rate_limit(category, identifier, resend_count, cooldown_until=None, locked_until=None):
    action_key=f"{category}:{identifier}"; conn=get_connection(); c=conn.cursor()
    existing=get_rate_limit(category, identifier)
    if existing:
        c.execute("UPDATE action_rate_limits SET resend_count=?, cooldown_until=?, locked_until=?, updated_at=? WHERE action_key=?", (resend_count, cooldown_until, locked_until, now(), action_key))
    else:
        c.execute("INSERT INTO action_rate_limits (action_key,category,identifier,resend_count,cooldown_until,locked_until,updated_at,created_at) VALUES (?,?,?,?,?,?,?,?)", (action_key,category,identifier,resend_count,cooldown_until,locked_until,now(),now()))
    conn.commit(); conn.close()


def reset_rate_limit(category, identifier):
    conn=get_connection(); c=conn.cursor(); c.execute("DELETE FROM action_rate_limits WHERE action_key=?", (f"{category}:{identifier}",)); conn.commit(); conn.close()

# Reconciliation / approval / email / audit helpers
def reconciliation_result_exists(file_name, invoice_number):
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id FROM reconciliation_results WHERE file_name=? AND invoice_number=? LIMIT 1", (file_name, invoice_number)); row=c.fetchone(); conn.close(); return row is not None

def save_reconciliation_result(r):
    conn=get_connection(); c=conn.cursor(); c.execute("INSERT INTO reconciliation_results (file_name,invoice_number,vendor_name,po_number,invoice_date,invoice_amount,status,exception_type,issues,matched_po,matched_transaction,duplicate_found,duplicate_match_count,anomaly_count,anomalies,requires_human_review,rule_based_explanation,langchain_ai_review,langchain_ai_email,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (r.get('file_name'),r.get('invoice_number'),r.get('vendor_name'),r.get('po_number'),r.get('invoice_date'),r.get('invoice_amount'),r.get('status'),r.get('exception_type'),r.get('issues'),r.get('matched_po'),r.get('matched_transaction'),str(r.get('duplicate_found')),r.get('duplicate_match_count'),r.get('anomaly_count'),r.get('anomalies'),str(r.get('requires_human_review')),r.get('rule_based_explanation'),r.get('langchain_ai_review',''),r.get('langchain_ai_email',''),now())); conn.commit(); conn.close()

def get_all_reconciliation_results():
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id,file_name,invoice_number,vendor_name,po_number,invoice_date,invoice_amount,status,exception_type,duplicate_found,anomaly_count,requires_human_review,created_at FROM reconciliation_results ORDER BY id DESC"); rows=c.fetchall(); conn.close(); return rows

def get_invoice_by_number(invoice_number):
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id,file_name,invoice_number,vendor_name,po_number,invoice_date,invoice_amount,status,exception_type,duplicate_found,anomaly_count,requires_human_review,created_at FROM reconciliation_results WHERE invoice_number=? ORDER BY id DESC LIMIT 1", (invoice_number.strip(),)); row=c.fetchone(); conn.close(); return row

def get_reconciliation_summary():
    conn=get_connection(); c=conn.cursor();
    c.execute("SELECT COUNT(*) FROM reconciliation_results"); total=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM reconciliation_results WHERE status='MATCHED'"); matched=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM reconciliation_results WHERE status='EXCEPTION'"); exceptions=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM reconciliation_results WHERE requires_human_review='True'"); review=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM reconciliation_results WHERE duplicate_found='True'"); duplicates=c.fetchone()[0]
    conn.close(); return {"total":total,"matched":matched,"exceptions":exceptions,"human_review":review,"duplicates":duplicates}

def get_duplicate_invoices():
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id,invoice_number,vendor_name,invoice_amount,duplicate_found,created_at FROM reconciliation_results WHERE duplicate_found='True' ORDER BY id DESC"); rows=c.fetchall(); conn.close(); return rows

def get_human_review_invoices():
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id,invoice_number,vendor_name,invoice_amount,status,exception_type,created_at FROM reconciliation_results WHERE requires_human_review='True' ORDER BY id DESC"); rows=c.fetchall(); conn.close(); return rows

def save_approval_to_db(invoice_number, decision, comment, approved_by):
    conn=get_connection(); c=conn.cursor(); c.execute("INSERT INTO approval_decisions (invoice_number,decision,comment,approved_by,decision_time) VALUES (?,?,?,?,?)", (invoice_number,decision,comment,approved_by,now())); conn.commit(); conn.close()

def get_approval_records():
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id,invoice_number,decision,comment,approved_by,decision_time FROM approval_decisions ORDER BY id DESC"); rows=c.fetchall(); conn.close(); return rows

def get_latest_approval_for_invoice(invoice_number):
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id,invoice_number,decision,comment,approved_by,decision_time FROM approval_decisions WHERE invoice_number=? ORDER BY id DESC LIMIT 1", (invoice_number.strip(),)); row=c.fetchone(); conn.close(); return row

def save_email_log(invoice_number,email_to,email_cc,email_bcc,subject,body,send_status):
    conn=get_connection(); c=conn.cursor(); c.execute("INSERT INTO email_logs (invoice_number,email_to,email_cc,email_bcc,subject,body,send_status,sent_at) VALUES (?,?,?,?,?,?,?,?)", (invoice_number,email_to,email_cc,email_bcc,subject,body,send_status,now())); conn.commit(); conn.close()

def get_email_logs():
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id,invoice_number,email_to,email_cc,email_bcc,subject,body,send_status,sent_at FROM email_logs ORDER BY id DESC"); rows=c.fetchall(); conn.close(); return rows

def get_failed_email_logs():
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id,invoice_number,email_to,email_cc,email_bcc,subject,body,send_status,sent_at FROM email_logs WHERE send_status LIKE 'FAILED%' OR send_status LIKE 'NOT_SENT%' ORDER BY id DESC"); rows=c.fetchall(); conn.close(); return rows

def get_email_log_by_id(log_id):
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id,invoice_number,email_to,email_cc,email_bcc,subject,body,send_status,sent_at FROM email_logs WHERE id=?", (log_id,)); row=c.fetchone(); conn.close(); return row

def update_email_log_status(log_id,email_to,email_cc,email_bcc,subject,body,send_status):
    conn=get_connection(); c=conn.cursor(); c.execute("UPDATE email_logs SET email_to=?,email_cc=?,email_bcc=?,subject=?,body=?,send_status=?,sent_at=? WHERE id=?", (email_to,email_cc,email_bcc,subject,body,send_status,now(),log_id)); conn.commit(); conn.close()

def save_user_activity(event_type,actor_username='',target_username='',target_email='',actor_role='',status='',ip_address='',user_agent='',details=''):
    conn=get_connection(); c=conn.cursor(); c.execute("INSERT INTO user_activity_audit (event_type,actor_username,target_username,target_email,actor_role,status,ip_address,user_agent,details,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (event_type,actor_username,target_username,target_email,actor_role,status,ip_address,user_agent,details,now())); conn.commit(); conn.close()

def get_user_activity_audit(limit=200):
    conn=get_connection(); c=conn.cursor(); c.execute("SELECT id,event_type,actor_username,target_username,target_email,actor_role,status,ip_address,user_agent,details,created_at FROM user_activity_audit ORDER BY id DESC LIMIT ?", (limit,)); rows=c.fetchall(); conn.close(); return rows

def save_chatbot_message(username,role,user_message,bot_response,action_taken=''):
    conn=get_connection(); c=conn.cursor(); c.execute("INSERT INTO chatbot_messages (username,role,user_message,bot_response,action_taken,created_at) VALUES (?,?,?,?,?,?)", (username,role,user_message,bot_response,action_taken,now())); conn.commit(); conn.close()

