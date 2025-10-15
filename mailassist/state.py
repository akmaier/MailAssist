"""Durable state helpers for MailAssist."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class ProcessorState:
    def __init__(self, deleted_record_path: str, failed_record_path: str) -> None:
        self.deleted_record_path = Path(deleted_record_path).expanduser()
        self.failed_record_path = Path(failed_record_path).expanduser()
        self.deleted_record_path.parent.mkdir(parents=True, exist_ok=True)
        self.failed_record_path.parent.mkdir(parents=True, exist_ok=True)

    def record_deleted(self, uid: str, metadata: Optional[dict] = None) -> None:
        self._write_entry(self.deleted_record_path, uid, metadata)

    def record_failed(self, uid: str, reason: str) -> None:
        metadata = {"reason": reason}
        self._write_entry(self.failed_record_path, uid, metadata)

    def _write_entry(self, path: Path, uid: str, metadata: Optional[dict] = None) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = {
            "timestamp": timestamp,
            "uid": uid,
        }
        if metadata:
            payload.update(metadata)
        line = " | ".join(f"{key}={value}" for key, value in payload.items())
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


__all__ = ["ProcessorState"]
