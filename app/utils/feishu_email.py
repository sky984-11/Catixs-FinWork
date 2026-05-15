import os
import smtplib
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

SMTP_SERVER = os.getenv("FEISHU_SMTP_SERVER", "smtp.feishu.cn")
SMTP_PORT = int(os.getenv("FEISHU_SMTP_PORT", "465"))
SENDER_EMAIL = os.getenv("FEISHU_SENDER_EMAIL", "noc@cn.catixs.com")
SENDER_PASSWORD = os.getenv("FEISHU_SENDER_PASSWORD", "dNFOfcVzI1xnmR3N")
SENDER_NAME = os.getenv("FEISHU_SENDER_NAME", "工单管理系统")


def send_email(
    to_email: str,
    subject: str,
    content: str,
    cc: str | None = None,
    attachment_data: bytes | None = None,
    attachment_filename: str | None = None,
) -> None:
    msg = MIMEMultipart()
    msg["From"] = formataddr((SENDER_NAME, SENDER_EMAIL))
    msg["To"] = to_email
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = Header(subject, "utf-8")

    msg.attach(MIMEText(content, "plain", "utf-8"))

    if attachment_data:
        part = MIMEApplication(attachment_data)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=Header(attachment_filename or "attachment", "utf-8").encode(),
        )
        msg.attach(part)

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        recipients = [to_email]
        if cc:
            recipients.extend([email.strip() for email in cc.split(",") if email.strip()])
        server.sendmail(SENDER_EMAIL, recipients, msg.as_string())
