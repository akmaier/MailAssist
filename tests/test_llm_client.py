"""Tests for the OpenAI LLM client wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import pytest

from mailassist.config import LLMSettings
from mailassist.llm_client import LLMClient


class _StubResponse:
    def __init__(self, output_text: str, output: List[Any] | None = None) -> None:
        self.output_text = output_text
        self.output = output or []


class _StubContent:
    def __init__(self, text: str) -> None:
        self.type = "output_text"
        self.text = text


class _StubOutput:
    def __init__(self, content: List[Any]) -> None:
        self.content = content


@dataclass
class _ClientRecorder:
    response: _StubResponse

    def __post_init__(self) -> None:  # pragma: no cover - dataclass hook
        self.captured_kwargs: Dict[str, Any] = {}
        self.responses = self

    def create(self, **kwargs: Any) -> _StubResponse:
        self.captured_kwargs = kwargs
        return self.response


def _install_stub(monkeypatch: pytest.MonkeyPatch, response: _StubResponse) -> _ClientRecorder:
    recorder = _ClientRecorder(response=response)

    def _factory(api_key: str) -> _ClientRecorder:  # pragma: no cover - runtime hook
        assert api_key == "dummy-key"
        return recorder

    monkeypatch.setattr("mailassist.llm_client.OpenAI", _factory)
    return recorder


def test_generate_reply_requests_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _StubResponse(
        output_text="{\"to\":\"a@b.c\",\"subject\":\"Hi\",\"body_text\":\"Body\"}"
    )
    recorder = _install_stub(monkeypatch, response)
    client = LLMClient(LLMSettings(api_key="dummy-key", model="gpt-5"))

    reply = client.generate_reply("hello", [])

    assert recorder.captured_kwargs["response_format"] == {"type": "json_object"}
    assert reply.to == "a@b.c"
    assert reply.subject == "Hi"
    assert reply.body_text == "Body"


def test_generate_reply_falls_back_to_output_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = "{\"to\":\"x@y.z\",\"subject\":\"Subject\",\"body_text\":\"Response\"}"
    response = _StubResponse("", [_StubOutput([_StubContent(payload)])])
    _install_stub(monkeypatch, response)
    client = LLMClient(LLMSettings(api_key="dummy-key", model="gpt-5"))

    reply = client.generate_reply("body", [])

    assert reply.to == "x@y.z"
    assert reply.subject == "Subject"
    assert reply.body_text == "Response"
