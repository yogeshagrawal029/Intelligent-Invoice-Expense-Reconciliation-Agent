import smtplib
from email.message import EmailMessage
from src.config import get_secret


def parse_email_list(email_string):
    if not email_string:
        return []
    return [email.strip() for email in str(email_string).split(",") if email.strip()]


def send_email_from_app(to_emails, cc_emails, bcc_emails, subject, body):
    smtp_server = get_secret("SMTP_SERVER", required=True)
    smtp_port = int(get_secret("SMTP_PORT", "587"))
    smtp_email = get_secret("SMTP_EMAIL", required=True)
    smtp_password = get_secret("SMTP_PASSWORD", required=True)
    to_list = parse_email_list(to_emails)
    cc_list = parse_email_list(cc_emails)
    bcc_list = parse_email_list(bcc_emails)
    if not to_list:
        raise ValueError("At least one recipient email is required in TO field.")
    msg = EmailMessage()
    msg["From"] = smtp_email
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(msg, from_addr=smtp_email, to_addrs=to_list + cc_list + bcc_list)
    return {"status": "success", "message": "Email sent successfully.", "to": to_list, "cc": cc_list, "bcc": bcc_list}

