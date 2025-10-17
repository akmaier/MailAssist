"""Core processing orchestrator."""

from __future__ import annotations

import logging
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Optional

from .attachment_processor import AttachmentProcessor, ProcessedAttachment
from .config import AppConfig
from .email_sender import EmailSender
from .imap_client import ImapClient, MessageEnvelope
from .llm_client import LLMClient, LLMReply
from .state import ProcessorState

LOGGER = logging.getLogger(__name__)


def extract_plain_text(message: EmailMessage) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    try:
                        return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    except LookupError:
                        return payload.decode("utf-8", errors="replace")
    text = message.get_body(preferencelist=("plain",))
    if text:
        return text.get_content()
    return message.get_content()


class MailProcessor:
    def __init__(
        self,
        config: AppConfig,
        imap_client: Optional[ImapClient] = None,
        attachment_processor: Optional[AttachmentProcessor] = None,
        llm_client: Optional[LLMClient] = None,
        email_sender: Optional[EmailSender] = None,
        state: Optional[ProcessorState] = None,
        logger: Optional[logging.Logger] = None,
        safe_mode: bool = False,
    ) -> None:
        self.config = config
        self.logger = logger or LOGGER
        self.imap_client = imap_client or ImapClient(config.imap, logger=self.logger)
        self.attachment_processor = attachment_processor or AttachmentProcessor(config.attachment_policy, logger=self.logger)
        self.llm_client = llm_client or LLMClient(config.llm, logger=self.logger)
        self.email_sender = email_sender or EmailSender(config.smtp, logger=self.logger)
        state_settings = config.state
        self.state = state or ProcessorState(
            state_settings.deleted_record_path,
            state_settings.failed_record_path,
        )
        self.safe_mode = safe_mode

    def run(self) -> None:
        self.logger.info("Fetching messages from IMAP mailbox")
        envelopes = self.imap_client.fetch_messages(self.config.trusted_senders)
        self.logger.info("Fetched %s message(s) from trusted senders", len(envelopes))
        for envelope in envelopes:
            self._process_envelope(envelope)

    def _process_envelope(self, envelope: MessageEnvelope) -> None:
        uid = envelope.uid
        message = envelope.message
        subject = message.get("Subject", "(no subject)")
        self.logger.info("Processing message UID %s subject '%s'", uid, subject)
        try:
            body_text = self._extract_plain_text(message)
            attachments = self.attachment_processor.process(message)
            reply = self.llm_client.generate_reply(body_text, attachments)
            recipient = self._determine_recipient(message, reply)
            if self.safe_mode:
                self.logger.info("Safe mode active: overriding LLM recipient with %s", recipient)
            self.email_sender.send_mail(recipient, reply.subject, reply.body_text)
            self.logger.info("Reply sent for UID %s", uid)
            self._handle_post_send(uid, attachments)
        except Exception as exc:
            self.logger.error("Processing failed for UID %s: %s", uid, exc)
            self.state.record_failed(uid, reason=str(exc))
            self.imap_client.mark_failed(uid)

    def _handle_post_send(self, uid: str, attachments: list[ProcessedAttachment]) -> None:
        if self.config.queue_policy.delete_after_success:
            self.imap_client.delete_message(uid)
            attachment_summary = {
                "attachments": ",".join(att.filename for att in attachments if not att.skipped)
            }
            self.state.record_deleted(uid, metadata=attachment_summary)
            self.logger.info("Deleted message UID %s after successful processing", uid)
        else:
            self.logger.info("Deletion disabled by configuration; retaining message UID %s", uid)

    def _extract_plain_text(self, message: EmailMessage) -> str:
        return extract_plain_text(message)

    def _determine_recipient(self, message: EmailMessage, reply: LLMReply) -> str:
        if not self.safe_mode:
            return reply.to
        sender_address = parseaddr(message.get("From", ""))[1]
        if sender_address:
            return sender_address
        return self.config.trusted_senders[0]


__all__ = ["MailProcessor", "extract_plain_text"]
