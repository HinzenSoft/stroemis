"""E-Mail-Versand. Ohne SMTP_HOST wird die Mail nur ins Log geschrieben (docker logs)."""
import smtplib
from email.message import EmailMessage
from email.utils import formatdate

from flask import current_app


def send_mail(to, subject, body):
    cfg = current_app.config
    host = cfg.get("SMTP_HOST")
    if not host:
        current_app.logger.warning(
            "SMTP nicht konfiguriert – Mail an %s wird nicht verschickt.\nBetreff: %s\n%s", to, subject, body)
        return False

    msg = EmailMessage()
    msg["From"] = cfg["MAIL_FROM"]
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(body)

    port = int(cfg.get("SMTP_PORT") or (465 if cfg.get("SMTP_SSL") else 587))
    if cfg.get("SMTP_SSL"):
        server = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        server = smtplib.SMTP(host, port, timeout=20)
    with server:
        server.ehlo()
        if not cfg.get("SMTP_SSL") and cfg.get("SMTP_STARTTLS", True):
            server.starttls()
            server.ehlo()
        if cfg.get("SMTP_USER"):
            server.login(cfg["SMTP_USER"], cfg.get("SMTP_PASSWORD") or "")
        server.send_message(msg)
    return True
