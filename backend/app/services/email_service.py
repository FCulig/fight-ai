"""Outgoing email over SMTP.

Configured by SMTP_HOST, SMTP_PORT, SMTP_SECURITY (`starttls`, the default, for
port 587; `ssl` for port 465; `none` for a local test server), SMTP_USERNAME,
SMTP_PASSWORD and MAIL_FROM (defaults to SMTP_USERNAME). With SMTP_HOST unset,
sending is off and each message is only logged, so dev and tests never send mail.
"""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

log = logging.getLogger("uvicorn.error")


def is_enabled() -> bool:
    return bool(os.getenv("SMTP_HOST"))


def send(to: str, subject: str, body: str) -> None:
    """Send one plain-text email to one recipient. Raises on SMTP errors."""
    if not is_enabled():
        log.info("Email is off (SMTP_HOST unset); not sending %r to %s", subject, to)
        return
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT") or 587)
    security = (os.getenv("SMTP_SECURITY") or "starttls").lower()
    username = os.getenv("SMTP_USERNAME")

    msg = EmailMessage()
    msg["From"] = os.getenv("MAIL_FROM") or username
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    if security == "ssl":
        server = smtplib.SMTP_SSL(host, port, timeout=30, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
    with server:
        if security == "starttls":
            server.starttls(context=context)
        if username:
            server.login(username, os.getenv("SMTP_PASSWORD", ""))
        server.send_message(msg)
