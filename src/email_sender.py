import os
import smtplib
from dotenv import load_dotenv
from email.message import EmailMessage

load_dotenv()


def parse_email_list(email_string):
    if not email_string:
        return []
    return [email.strip() for email in email_string.split(",") if email.strip()]


def send_email_from_app(to_emails, cc_emails, bcc_emails, subject, body):
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")
    if not smtp_server:
        raise ValueError("SMTP_SERVER is missing in .env file.")
    if not smtp_email:
        raise ValueError("SMTP_EMAIL is missing in .env file.")
    if not smtp_password:
        raise ValueError("SMTP_PASSWORD is missing in .env file.")
    to_list = parse_email_list(to_emails)
    cc_list = parse_email_list(cc_emails)
    bcc_list = parse_email_list(bcc_emails)
    if not to_list:
        raise ValueError("At least one recipient email is required in TO field.")
    all_recipients = to_list + cc_list + bcc_list
    message = EmailMessage()
    message["From"] = smtp_email
    message["To"] = ", ".join(to_list)
    if cc_list:
        message["Cc"] = ", ".join(cc_list)
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(message, from_addr=smtp_email, to_addrs=all_recipients)
    return {"status": "success", "message": "Email sent successfully.", "to": to_list, "cc": cc_list, "bcc": bcc_list}

