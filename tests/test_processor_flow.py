from email.message import EmailMessage
from pathlib import Path
from unittest.mock import MagicMock

from mailassist.attachment_processor import ProcessedAttachment
from mailassist.config import (
    AppConfig,
    AttachmentPolicy,
    IMAPSettings,
    LLMSettings,
    QueuePolicy,
    SMTPSettings,
    StateSettings,
)
from mailassist.llm_client import LLMReply
from mailassist.processor import MailProcessor
from mailassist.imap_client import MessageEnvelope


def build_config(tmp_path: Path, delete_after_success: bool = True) -> AppConfig:
    return AppConfig(
        imap=IMAPSettings(host="imap.example.com", port=993, username="user", password="pass"),
        smtp=SMTPSettings(host="smtp.example.com", port=587, username="user", password="pass"),
        llm=LLMSettings(api_key="test-key", model="gpt-5.0"),
        attachment_policy=AttachmentPolicy(),
        queue_policy=QueuePolicy(delete_after_success=delete_after_success),
        state=StateSettings(
            deleted_record_path=str(tmp_path / "deleted.log"),
            failed_record_path=str(tmp_path / "failed.log"),
        ),
        trusted_senders=["andreas.maier@fau.de"],
    )


def build_envelope() -> MessageEnvelope:
    message = EmailMessage()
    message["From"] = "Andreas Maier <andreas.maier@fau.de>"
    message["Subject"] = "Test"
    message.set_content("Hello there")
    return MessageEnvelope(uid="123", message=message)


def test_successful_processing_deletes_message(tmp_path):
    config = build_config(tmp_path)
    imap_client = MagicMock()
    imap_client.fetch_messages.return_value = [build_envelope()]
    attachment = ProcessedAttachment(
        filename="doc.docx", content_type="application/docx", size=10, text="Doc text"
    )
    attachment_processor = MagicMock()
    attachment_processor.process.return_value = [attachment]
    llm_client = MagicMock()
    llm_client.generate_reply.return_value = LLMReply(
        to="andreas.maier@fau.de", subject="Re: Test", body_text="Response"
    )
    email_sender = MagicMock()

    processor = MailProcessor(
        config,
        imap_client=imap_client,
        attachment_processor=attachment_processor,
        llm_client=llm_client,
        email_sender=email_sender,
    )

    processor.run()

    imap_client.delete_message.assert_called_once_with("123")
    email_sender.send_mail.assert_called_once()
    llm_client.generate_reply.assert_called_once()
    record_path = Path(config.state.deleted_record_path)
    assert record_path.exists()
    assert "uid=123" in record_path.read_text()


def test_failed_processing_retains_message(tmp_path):
    config = build_config(tmp_path)
    imap_client = MagicMock()
    imap_client.fetch_messages.return_value = [build_envelope()]
    attachment_processor = MagicMock()
    attachment_processor.process.return_value = []
    llm_client = MagicMock()
    llm_client.generate_reply.side_effect = RuntimeError("LLM failure")
    email_sender = MagicMock()

    processor = MailProcessor(
        config,
        imap_client=imap_client,
        attachment_processor=attachment_processor,
        llm_client=llm_client,
        email_sender=email_sender,
    )

    processor.run()

    imap_client.delete_message.assert_not_called()
    imap_client.mark_failed.assert_called_once_with("123")
    email_sender.send_mail.assert_not_called()
    failure_path = Path(config.state.failed_record_path)
    assert failure_path.exists()
    contents = failure_path.read_text()
    assert "uid=123" in contents
    assert "reason=LLM failure" in contents


def test_deletion_disabled_by_configuration(tmp_path):
    config = build_config(tmp_path, delete_after_success=False)
    imap_client = MagicMock()
    imap_client.fetch_messages.return_value = [build_envelope()]
    attachment_processor = MagicMock()
    attachment_processor.process.return_value = []
    llm_client = MagicMock()
    llm_client.generate_reply.return_value = LLMReply(
        to="andreas.maier@fau.de", subject="Re: Test", body_text="Response"
    )
    email_sender = MagicMock()

    processor = MailProcessor(
        config,
        imap_client=imap_client,
        attachment_processor=attachment_processor,
        llm_client=llm_client,
        email_sender=email_sender,
    )

    processor.run()

    imap_client.delete_message.assert_not_called()
    imap_client.mark_failed.assert_not_called()
