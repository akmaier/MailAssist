"""SMTP email sending helper."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from .config import SMTPSettings

LOGGER = logging.getLogger(__name__)


class EmailSender:
    def __init__(self, settings: SMTPSettings, logger: Optional[logging.Logger] = None) -> None:
        self.settings = settings
        self.logger = logger or LOGGER

    def send_mail(self, to_address: str, subject: str, body_text: str) -> None:
        sender = self.settings.sender or self.settings.username
        message = EmailMessage()
        message["From"] = sender
        message["To"] = to_address
        message["Subject"] = subject
        message.set_content(body_text)

        self.logger.info("Sending email to %s", to_address)
        if self.settings.use_tls:
            with smtplib.SMTP(self.settings.host, self.settings.port) as smtp:
                smtp.starttls()
                smtp.login(self.settings.username, self.settings.password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP_SSL(self.settings.host, self.settings.port) as smtp:
                smtp.login(self.settings.username, self.settings.password)
                smtp.send_message(message)


__all__ = ["EmailSender"]
