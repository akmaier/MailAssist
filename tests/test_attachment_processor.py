import io
import zipfile
from email.message import EmailMessage

from mailassist.attachment_processor import AttachmentProcessor, attachments_to_prompt
from mailassist.config import AttachmentPolicy


def build_docx(text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        xml = (
            "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
            "<w:body><w:p><w:r><w:t>" + text + "</w:t></w:r></w:p></w:body></w:document>"
        )
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def create_message_with_attachment(filename: str, content: bytes, maintype: str, subtype: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = "andreas.maier@fau.de"
    msg["To"] = "processor@example.com"
    msg.set_content("Body text")
    msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
    return msg


def test_docx_extraction_returns_text():
    policy = AttachmentPolicy()
    processor = AttachmentProcessor(policy)
    docx_bytes = build_docx("Hello World")
    msg = create_message_with_attachment("example.docx", docx_bytes, "application", "vnd.openxmlformats-officedocument.wordprocessingml.document")
    attachments = processor.process(msg)
    assert len(attachments) == 1
    assert attachments[0].text == "Hello World"
    prompt = attachments_to_prompt(attachments)
    assert prompt[0]["filename"] == "example.docx"


def test_attachment_larger_than_limit_is_skipped():
    policy = AttachmentPolicy(max_attachment_size_mb=0)
    processor = AttachmentProcessor(policy)
    content = b"x" * (policy.max_attachment_size_bytes + 1)
    msg = create_message_with_attachment("large.docx", content, "application", "vnd.openxmlformats-officedocument.wordprocessingml.document")
    attachments = processor.process(msg)
    assert attachments[0].skipped is True
    assert "size" in attachments[0].reason.lower()


def test_non_supported_attachment_is_skipped():
    policy = AttachmentPolicy()
    processor = AttachmentProcessor(policy)
    msg = create_message_with_attachment("image.png", b"binary", "image", "png")
    attachments = processor.process(msg)
    assert attachments[0].skipped is True
    assert attachments[0].reason == "Unsupported file type"
