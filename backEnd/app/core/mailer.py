"""Minimal account-recovery mail transport.

Development logs the reset URL so the flow can be tested without an SMTP service.
Staging/production configuration rejects the console backend at application startup.
"""
from email.message import EmailMessage
import logging
import smtplib
import ssl
from urllib.parse import urlencode

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_password_reset_email(email: str, token: str) -> None:
    query = urlencode({"reset_token": token})
    reset_url = f"{settings.public_app_url.rstrip('/')}/?{query}"
    subject = "Reset your FIT PULSE password"
    body = (
        "We received a request to reset the password for your FIT PULSE account.\n\n"
        f"Use this link within {settings.password_reset_token_expire_minutes} minutes:\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    if settings.mail_backend == "console":
        logger.warning("Development-only password reset message for %s:\n%s", email, body)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.mail_from
    message["To"] = email
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
        client.ehlo()
        if settings.smtp_starttls:
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password or "")
        client.send_message(message)
