"""IMAP utilities for MailAssist."""

from __future__ import annotations

import imaplib
import logging
from dataclasses import dataclass
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import Iterable, List, Optional

from .config import IMAPSettings

LOGGER = logging.getLogger(__name__)


@dataclass
class MessageEnvelope:
    uid: str
    message: EmailMessage


class ImapClient:
    def __init__(self, settings: IMAPSettings, logger: Optional[logging.Logger] = None) -> None:
        self.settings = settings
        self.logger = logger or LOGGER
        self._conn: Optional[imaplib.IMAP4] = None

    def connect(self) -> None:
        if self._conn is not None:
            return
        if self.settings.use_ssl:
            self._conn = imaplib.IMAP4_SSL(self.settings.host, self.settings.port)
        else:
            self._conn = imaplib.IMAP4(self.settings.host, self.settings.port)
        self.logger.info("IMAP login to %s", self.settings.host)
        self._conn.login(self.settings.username, self.settings.password)
        self._conn.select(self.settings.folder)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # pragma: no cover - defensive
                pass
            finally:
                self._conn.logout()
                self._conn = None

    def fetch_messages(self, trusted_senders: Iterable[str]) -> List[MessageEnvelope]:
        self.connect()
        assert self._conn is not None  # for type checking
        status, data = self._conn.search(None, "ALL")
        if status != "OK":  # pragma: no cover - depends on IMAP server
            raise RuntimeError("Failed to search mailbox")
        senders = {sender.lower() for sender in trusted_senders}
        envelopes: List[MessageEnvelope] = []
        for uid in data[0].split():
            status, message_data = self._conn.fetch(uid, "(RFC822)")
            if status != "OK":
                self.logger.warning("Failed to fetch message UID %s", uid)
                continue
            raw = message_data[0][1]
            email_message = message_from_bytes(raw, policy=policy.default)
            from_header = (email_message.get("From") or "").lower()
            if not any(sender in from_header for sender in senders):
                continue
            envelopes.append(MessageEnvelope(uid=uid.decode("utf-8"), message=email_message))
        return envelopes

    def delete_message(self, uid: str) -> None:
        self.connect()
        assert self._conn is not None
        self.logger.info("Deleting message UID %s", uid)
        self._conn.store(uid, "+FLAGS", "(\\Deleted)")
        self._conn.expunge()

    def mark_failed(self, uid: str) -> None:
        self.logger.warning("Message UID %s marked as failed for future runs", uid)

    def __enter__(self) -> "ImapClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


__all__ = ["ImapClient", "MessageEnvelope"]
