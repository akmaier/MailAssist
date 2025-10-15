"""OpenAI GPT-5 client wrapper."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Iterable, Optional

try:  # pragma: no cover - optional dependency import
    from openai import OpenAI
except Exception:  # pragma: no cover - fallback when OpenAI package is unavailable
    OpenAI = None

from .attachment_processor import ProcessedAttachment
from .config import LLMSettings

LOGGER = logging.getLogger(__name__)


@dataclass
class LLMReply:
    to: str
    subject: str
    body_text: str


class LLMClient:
    """Thin wrapper around the OpenAI Responses API."""

    def __init__(self, settings: LLMSettings, logger: Optional[logging.Logger] = None) -> None:
        self.settings = settings
        if OpenAI is None:
            raise RuntimeError("openai package is required to use the GPT client")
        self.client = OpenAI(api_key=settings.api_key)
        self.logger = logger or LOGGER

    def generate_reply(self, body_text: str, attachments: Iterable[ProcessedAttachment]) -> LLMReply:
        prompt = self._build_prompt(body_text, attachments)
        self.logger.debug("Submitting prompt to GPT-5 (model=%s)", self.settings.model)
        response = self.client.responses.create(
            model=self.settings.model,
            input=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant generating structured email replies. Respond ONLY with JSON matching the schema {to, subject, body_text}.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=self.settings.temperature,
            max_output_tokens=self.settings.max_tokens,
        )
        payload = response.output_text
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:  # pragma: no cover - depends on API behaviour
            raise RuntimeError(f"LLM returned invalid JSON: {payload}") from exc
        for key in ("to", "subject", "body_text"):
            if key not in data:
                raise RuntimeError(f"LLM response missing '{key}' field: {data}")
        return LLMReply(to=data["to"], subject=data["subject"], body_text=data["body_text"])

    def _build_prompt(self, body_text: str, attachments: Iterable[ProcessedAttachment]) -> str:
        attachment_sections = []
        for attachment in attachments:
            base = [
                f"Filename: {attachment.filename}",
                f"Content-Type: {attachment.content_type}",
                f"Size: {attachment.size} bytes",
                f"Skipped: {attachment.skipped}",
                f"Reason: {attachment.reason or 'n/a'}",
            ]
            if attachment.text:
                base.append("Content:\n" + attachment.text)
            attachment_sections.append("\n".join(base))
        attachment_block = "\n\n".join(attachment_sections) if attachment_sections else "(no attachments)"
        return (
            "Trusted sender email body:\n"
            f"{body_text}\n\n"
            "Attachment summaries:\n"
            f"{attachment_block}\n\n"
            "Respond with JSON containing keys to, subject, body_text."
        )


__all__ = ["LLMClient", "LLMReply"]
