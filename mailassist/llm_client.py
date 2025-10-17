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
        self.logger.debug("LLM message payload: %s", prompt)
        request_kwargs = {
            "model": self.settings.model,
            "input": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant generating structured email replies. Respond ONLY with JSON matching the schema {to, subject, body_text}.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "max_output_tokens": self.settings.max_tokens,
            "response_format": {"type": "json_object"},
        }

        if self._supports_sampling_controls(self.settings.model):
            if self.settings.temperature is not None:
                request_kwargs["temperature"] = self.settings.temperature
        else:
            self.logger.debug(
                "Omitting sampling controls for model '%s'", self.settings.model
            )

        self.logger.debug("LLM request body: %s", request_kwargs["input"])
        response = self.client.responses.create(**request_kwargs)
        payload = self._extract_text_payload(response)
        if not payload:
            self.logger.error("LLM response did not contain any text payload")
            raise RuntimeError("LLM response did not contain any text payload")
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:  # pragma: no cover - depends on API behaviour
            self.logger.error(
                "LLM returned payload that could not be parsed as JSON: %s",
                payload,
            )
            raise RuntimeError(f"LLM returned invalid JSON: {payload}") from exc
        for key in ("to", "subject", "body_text"):
            if key not in data:
                self.logger.error(
                    "LLM response missing required field '%s'. Full payload: %s",
                    key,
                    data,
                )
                raise RuntimeError(f"LLM response missing '{key}' field: {data}")
        return LLMReply(to=data["to"], subject=data["subject"], body_text=data["body_text"])

    def _extract_text_payload(self, response: object) -> str:
        """Return the concatenated text payload from a Responses API result."""

        text = getattr(response, "output_text", None)
        if text:
            stripped = text.strip()
            if stripped:
                return stripped

        output = getattr(response, "output", None)
        if not output:
            return ""

        chunks: list[str] = []
        for item in output:
            if isinstance(item, dict):
                contents = item.get("content")
            else:
                contents = getattr(item, "content", None)
            if not contents:
                continue
            for content in contents:
                if isinstance(content, dict):
                    text_value = content.get("text")
                else:
                    text_value = getattr(content, "text", None)
                if text_value:
                    chunks.append(text_value)
        return "".join(chunks).strip()

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

    @staticmethod
    def _supports_sampling_controls(model_name: str) -> bool:
        """Return True if the model accepts sampling parameters like temperature."""

        lowered = model_name.lower()
        disallowed_prefixes = ("gpt-5", "gpt-o", "o1", "o3", "realtime")
        return not any(lowered.startswith(prefix) for prefix in disallowed_prefixes)


__all__ = ["LLMClient", "LLMReply"]
