"""Надсилання листів через AWS SES — за фіче-флагом `FEATURE_EMAIL_ENABLED`.

Контракт (спільні конвенції):
  • false (default): до AWS не звертатись, лише залогувати; у dev-режимі
    викликач сам повертає токен/посилання у відповіді ендпойнта;
  • true: слати через SES; токени у відповіді не повертати.

`send_email` повертає bool — чи був лист реально відправлений через SES
(False означає, що спрацював fallback-лог і викликач може віддати dev-токен).
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
    """Надсилає лист. Повертає True, якщо лист справді пішов через SES."""
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
    except Exception:  # noqa: BLE001 — у прототипі помилка пошти не валить запит
        logger.exception("EMAIL[failed] to=%s subject=%r", to, subject)
        return False


# --------------------------------------------------------------------------- #
#  Готові шаблони
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
