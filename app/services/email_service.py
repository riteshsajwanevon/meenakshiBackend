import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_password_reset(to_email: str, full_name: str, token: str) -> None:
    """Email a reset token. Without SMTP configured, the token is logged instead (development only)."""
    if not settings.SMTP_HOST:
        logger.warning("SMTP is not configured. Password reset token for %s: %s", to_email, token)
        return

    link = f"{settings.PASSWORD_RESET_URL}?token={token}" if settings.PASSWORD_RESET_URL else None
    message = EmailMessage()
    message["Subject"] = "Reset your Meenakshi Quality password"
    message["From"] = settings.SMTP_FROM
    message["To"] = to_email
    message.set_content(
        f"Hello {full_name},\n\n"
        "We received a request to reset your password.\n\n"
        + (f"Open this link to choose a new password:\n{link}\n\n" if link else f"Your reset code is:\n{token}\n\n")
        + f"This expires in {settings.PASSWORD_RESET_MINUTES} minutes. "
        "If you did not request a reset, you can ignore this email.\n"
    )

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            if settings.SMTP_STARTTLS:
                smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
            smtp.send_message(message)
        logger.info("Password reset email sent to %s", to_email)
    except (OSError, smtplib.SMTPException):
        # Never fail the request: the API always answers the same way so it can't be used to probe accounts.
        logger.exception("Failed to send password reset email to %s", to_email)
