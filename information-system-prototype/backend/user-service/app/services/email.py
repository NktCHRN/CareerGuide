"""Sending emails via AWS SES — gated by the `FEATURE_EMAIL_ENABLED` feature flag.

Contract (shared conventions):
  • false (default): do not call AWS, only log; in dev mode the caller itself
    returns the token/link in the endpoint response;
  • true: send via SES; do not return tokens in the response.

`send_email` returns a bool — whether the email was actually sent via SES
(False means the fallback log fired and the caller may return a dev token).
"""
from __future__ import annotations

import asyncio
import logging

import boto3

from app.config import settings

logger = logging.getLogger("user-service.email")


def _send_via_ses(to: str, subject: str, html: str) -> None:
    client = boto3.client(
        "ses",
        region_name=settings.AWS_SES_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )
    client.send_email(
        Source=settings.SES_FROM_EMAIL,
        Destination={"ToAddresses": [to]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Html": {"Data": html, "Charset": "UTF-8"}},
        },
    )


async def send_email(
    to: str,
    subject: str,
    html: str,
    *,
    dev_context: str | None = None,
) -> bool:
    """Sends an email. Returns True if the email was actually sent via SES."""
    if not settings.FEATURE_EMAIL_ENABLED:
        logger.info(
            "EMAIL[disabled] to=%s subject=%r%s",
            to,
            subject,
            f" dev_context={dev_context}" if dev_context else "",
        )
        return False

    try:
        await asyncio.to_thread(_send_via_ses, to, subject, html)
        logger.info("EMAIL[sent] to=%s subject=%r", to, subject)
        return True
    except Exception:  # noqa: BLE001 — in the prototype an email failure does not break the request
        logger.exception("EMAIL[failed] to=%s subject=%r", to, subject)
        return False


# --------------------------------------------------------------------------- #
#  Ready-made templates
# --------------------------------------------------------------------------- #
def verify_email_html(token: str) -> tuple[str, str]:
    link = f"{settings.FRONTEND_BASE_URL}/verify-email?token={token}"
    subject = "CareerGuide — підтвердження електронної пошти"
    html = (
        "<p>Вітаємо у CareerGuide!</p>"
        f'<p>Підтвердьте пошту, перейшовши за <a href="{link}">посиланням</a>.</p>'
        f"<p>Або скористайтесь токеном: <code>{token}</code></p>"
    )
    return subject, html


def reset_password_html(token: str) -> tuple[str, str]:
    link = f"{settings.FRONTEND_BASE_URL}/reset-password?token={token}"
    subject = "CareerGuide — скидання пароля"
    html = (
        "<p>Ви запросили скидання пароля.</p>"
        f'<p>Встановіть новий пароль за <a href="{link}">посиланням</a>.</p>'
        f"<p>Токен: <code>{token}</code>. Дійсний обмежений час.</p>"
    )
    return subject, html
