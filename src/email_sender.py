import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(
        smtp_server,
        smtp_port,
        sender_email,
        sender_password,
        to_emails,
        cc_emails,
        bcc_emails,
        subject,
        body
):

    msg = MIMEMultipart()

    msg["From"] = sender_email
    msg["To"] = ", ".join(to_emails)
    msg["Cc"] = ", ".join(cc_emails)
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    recipients = (
        to_emails +
        cc_emails +
        bcc_emails
    )

    server = smtplib.SMTP(smtp_server, smtp_port)

    server.starttls()

    server.login(
        sender_email,
        sender_password
    )

    server.sendmail(
        sender_email,
        recipients,
        msg.as_string()
    )

    server.quit()

    return {
        "status": "SUCCESS",
        "sent_to": recipients
    }