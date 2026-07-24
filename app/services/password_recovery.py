from __future__ import annotations

import asyncio
from email.message import EmailMessage
import hashlib
import secrets
import smtplib
import ssl


def create_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _send_smtp_message(settings, recipient: str, display_name: str, reset_url: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Restablece tu contraseña de Paul AI Trader"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        "\n".join(
            [
                f"Hola {display_name},",
                "",
                "Recibimos una solicitud para restablecer tu contraseña.",
                "Abre el siguiente enlace para crear una nueva:",
                reset_url,
                "",
                f"El enlace vence en {settings.password_reset_token_minutes} minutos y solo puede utilizarse una vez.",
                "Si no solicitaste el cambio, puedes ignorar este mensaje.",
                "",
                "Paul AI Trader",
            ]
        )
    )

    with smtplib.SMTP(
        settings.smtp_host,
        settings.smtp_port,
        timeout=settings.smtp_timeout_seconds,
    ) as client:
        client.ehlo()
        if settings.smtp_use_tls:
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)


async def send_password_reset_email(
    settings,
    recipient: str,
    display_name: str,
    reset_url: str,
) -> None:
    if not settings.smtp_configured:
        raise RuntimeError("El servicio de correo no está configurado.")
    await asyncio.to_thread(
        _send_smtp_message,
        settings,
        recipient,
        display_name,
        reset_url,
    )
