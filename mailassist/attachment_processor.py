"""Attachment handling for MailAssist."""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, List, Optional
from xml.etree import ElementTree

from .config import AttachmentPolicy

try:  # pragma: no cover - optional dependency import handled at runtime
    from pypdf import PdfReader
except Exception:  # pragma: no cover - fallback if library missing
    PdfReader = None


LOGGER = logging.getLogger(__name__)


@dataclass
class ProcessedAttachment:
    """Represents a parsed attachment ready for LLM input."""

    filename: str
    content_type: str
    size: int
    text: Optional[str]
    skipped: bool = False
    reason: Optional[str] = None

    def to_prompt_dict(self) -> dict:
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "skipped": self.skipped,
            "reason": self.reason,
            "text": self.text,
        }


class AttachmentProcessor:
    """Processes attachments based on configuration policy."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx"}

    def __init__(self, policy: AttachmentPolicy, logger: Optional[logging.Logger] = None) -> None:
        self.policy = policy
        self.logger = logger or LOGGER

    def process(self, message: EmailMessage) -> List[ProcessedAttachment]:
        attachments: List[ProcessedAttachment] = []
        for part in message.iter_attachments():
            filename = part.get_filename() or "unnamed"
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True) or b""
            size = len(payload)

            metadata = ProcessedAttachment(
                filename=filename,
                content_type=content_type,
                size=size,
                text=None,
            )

            if not self.policy.include_pdf_docx:
                metadata.skipped = True
                metadata.reason = "Attachment forwarding disabled by configuration"
                self.logger.info("Skipping attachment %s: forwarding disabled", filename)
                attachments.append(metadata)
                continue

            extension = self._infer_extension(filename)
            if extension not in self.SUPPORTED_EXTENSIONS:
                metadata.skipped = True
                metadata.reason = "Unsupported file type"
                self.logger.info("Skipping attachment %s: unsupported type %s", filename, extension)
                attachments.append(metadata)
                continue

            if size > self.policy.max_attachment_size_bytes:
                metadata.skipped = True
                metadata.reason = "Attachment exceeds configured size limit"
                self.logger.warning(
                    "Skipping attachment %s: size %s exceeds limit %s", filename, size, self.policy.max_attachment_size_bytes
                )
                attachments.append(metadata)
                continue

            try:
                text = self._extract_text(extension, payload)
                if not text:
                    metadata.skipped = True
                    metadata.reason = "No textual content extracted"
                    self.logger.warning("No text extracted from %s", filename)
                else:
                    metadata.text = text
                attachments.append(metadata)
            except Exception as exc:  # pragma: no cover - error handling path
                metadata.skipped = True
                metadata.reason = f"Extraction failed: {exc}"
                self.logger.warning("Failed to extract attachment %s: %s", filename, exc)
                attachments.append(metadata)
        return attachments

    def _extract_text(self, extension: str, payload: bytes) -> str:
        if extension == ".docx":
            return self._extract_docx_text(payload)
        if extension == ".pdf":
            return self._extract_pdf_text(payload)
        raise ValueError(f"Unsupported extension: {extension}")

    def _extract_docx_text(self, payload: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            document = archive.read("word/document.xml")
        root = ElementTree.fromstring(document)
        namespaces = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        }
        paragraphs: List[str] = []
        for para in root.findall(".//w:p", namespaces):
            texts = [node.text for node in para.findall(".//w:t", namespaces) if node.text]
            if texts:
                paragraphs.append("".join(texts))
        return "\n".join(paragraphs)

    def _extract_pdf_text(self, payload: bytes) -> str:
        if PdfReader is None:
            raise RuntimeError("pypdf library is required to extract PDF text")
        reader = PdfReader(io.BytesIO(payload))
        texts = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            texts.append(extracted.strip())
        return "\n".join(filter(None, texts))

    @staticmethod
    def _infer_extension(filename: str) -> str:
        lower = filename.lower()
        for ext in AttachmentProcessor.SUPPORTED_EXTENSIONS:
            if lower.endswith(ext):
                return ext
        return Path(filename).suffix.lower() if "." in filename else ""


def attachments_to_prompt(attachments: Iterable[ProcessedAttachment]) -> List[dict]:
    return [attachment.to_prompt_dict() for attachment in attachments]


__all__ = [
    "AttachmentProcessor",
    "ProcessedAttachment",
    "attachments_to_prompt",
]
