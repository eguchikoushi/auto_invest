import os
import smtplib
import requests
from email.mime.text import MIMEText
from config import settings
import logging

logger = logging.getLogger(__name__)


# --- メール通知 ---
def send_email(subject: str, body: str) -> None:
    if settings is None or not settings.get("mail", {}).get("enabled", False):
        return

    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    smtp_user = os.getenv("MAIL_USER")
    smtp_pass = os.getenv("MAIL_PASS")
    email_to = os.getenv("MAIL_TO")

    if not smtp_user or not smtp_pass or not email_to:
        logger.warning("メール送信設定未定義（MAIL_USER / MAIL_PASS / MAIL_TO）")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = email_to

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info(f"メール送信: 件名: {subject}")
    except Exception as e:
        logger.error(f"メール送信失敗: {e}")


# --- Slack通知 ---
def send_slack(message: str, level: str = "INFO") -> None:
    url = os.getenv("SLACK_WEBHOOK")
    if not url:
        raise ValueError("SLACK_WEBHOOK が未設定です")

    prefix = {
        "INFO": "[INFO]",
        "WARN": "[WARN]",
        "ERROR": "[ERROR]",
        "BUY": "[BUY]",
        "DRY-RUN": "[DRY-RUN]",
    }.get(level.upper(), "[INFO]")

    full_msg = f"{prefix} {message}"

    try:
        resp = requests.post(url, json={"text": full_msg}, timeout=5)
        if not resp.ok:
            logger.error(f"Slack通知失敗: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Slack通知失敗: {e}")
