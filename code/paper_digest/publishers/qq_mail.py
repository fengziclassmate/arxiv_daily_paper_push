from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def publish(config: dict, subject: str, html_content: str) -> bool:
    mail_config = config.get("publishers", {}).get("qq_mail", {})
    if not mail_config.get("enabled", False):
        return False
    sender = mail_config.get("sender")
    receiver = mail_config.get("receiver")
    auth_code = os.getenv("QQ_MAIL_AUTH_CODE")
    if not sender or not receiver or not auth_code:
        print("[WARN] QQ mail skipped: sender, receiver or QQ_MAIL_AUTH_CODE is missing.")
        return False

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=30) as server:
        server.login(sender, auth_code)
        server.sendmail(sender, [receiver], msg.as_string())
    print("[OK] QQ mail sent.")
    return True
