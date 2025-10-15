"""Configuration loading for MailAssist without external dependencies."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:  # pragma: no cover - optional dependency import
    import yaml
except Exception:  # pragma: no cover - fallback when PyYAML is unavailable
    yaml = None


ENV_CONFIG_KEY = "MAILASSIST_CONFIG"


@dataclass
class IMAPSettings:
    host: str
    port: int = 993
    username: str = ""
    password: str = ""
    folder: str = "INBOX"
    use_ssl: bool = True


@dataclass
class SMTPSettings:
    host: str
    port: int = 587
    username: str = ""
    password: str = ""
    sender: Optional[str] = None
    use_tls: bool = True


@dataclass
class LLMSettings:
    api_key: str
    model: str = "gpt-5.0"
    temperature: float = 0.2
    max_tokens: int = 1500
    request_timeout: int = 60


@dataclass
class AttachmentPolicy:
    include_pdf_docx: bool = True
    max_attachment_size_mb: int = 10
    text_extraction_timeout: int = 30

    @property
    def max_attachment_size_bytes(self) -> int:
        return self.max_attachment_size_mb * 1024 * 1024


@dataclass
class QueuePolicy:
    delete_after_success: bool = True
    archive_before_delete: Optional[str] = None


@dataclass
class StateSettings:
    deleted_record_path: str = "deleted_uids.log"
    failed_record_path: str = "failed_uids.log"


@dataclass
class AppConfig:
    imap: IMAPSettings
    smtp: SMTPSettings
    llm: LLMSettings
    trusted_senders: List[str] = field(default_factory=lambda: ["andreas.maier@fau.de"])
    attachment_policy: AttachmentPolicy = field(default_factory=AttachmentPolicy)
    queue_policy: QueuePolicy = field(default_factory=QueuePolicy)
    state: StateSettings = field(default_factory=StateSettings)

    def __post_init__(self) -> None:
        if not self.trusted_senders:
            raise ValueError("trusted_senders must contain at least one entry")
        self.trusted_senders = [sender.lower() for sender in self.trusted_senders]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        def build(model, values: Dict[str, Any]):
            return model(**values) if values is not None else model()

        return cls(
            imap=build(IMAPSettings, data.get("imap", {})),
            smtp=build(SMTPSettings, data.get("smtp", {})),
            llm=build(LLMSettings, data.get("llm", {})),
            trusted_senders=data.get("trusted_senders", ["andreas.maier@fau.de"]),
            attachment_policy=build(AttachmentPolicy, data.get("attachment_policy", {})),
            queue_policy=build(QueuePolicy, data.get("queue_policy", {})),
            state=build(StateSettings, data.get("state", {})),
        )


def load_app_config(path: Optional[str] = None) -> AppConfig:
    config_path = _resolve_config_path(path)
    raw = config_path.read_text(encoding="utf-8")
    expanded = _expand_env_placeholders(raw)
    data = _parse_config_text(expanded, suffix=config_path.suffix)
    return AppConfig.from_dict(data)


def _resolve_config_path(path: Optional[str]) -> Path:
    candidate = path or os.environ.get(ENV_CONFIG_KEY)
    if not candidate:
        raise RuntimeError(
            f"Configuration file path must be provided via argument or {ENV_CONFIG_KEY} environment variable."
        )
    config_path = Path(candidate).expanduser().resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    return config_path


def _expand_env_placeholders(text: str) -> str:
    pattern = re.compile(r"\$\{([^}]+)\}")

    def replacer(match: re.Match[str]) -> str:
        var = match.group(1)
        value = os.environ.get(var)
        if value is None:
            raise RuntimeError(f"Environment variable '{var}' not set for configuration placeholder")
        return value

    return pattern.sub(replacer, text)


def _parse_config_text(text: str, suffix: str) -> Dict[str, Any]:
    lowered = suffix.lower()
    if lowered in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load YAML configuration files")
        return yaml.safe_load(text) or {}
    if lowered == ".json":
        return json.loads(text)
    raise RuntimeError(f"Unsupported configuration format: {suffix}")


def iter_trusted_senders(config: AppConfig) -> Iterable[str]:
    return config.trusted_senders


__all__ = [
    "AppConfig",
    "IMAPSettings",
    "SMTPSettings",
    "LLMSettings",
    "AttachmentPolicy",
    "QueuePolicy",
    "StateSettings",
    "ENV_CONFIG_KEY",
    "load_app_config",
    "iter_trusted_senders",
]
