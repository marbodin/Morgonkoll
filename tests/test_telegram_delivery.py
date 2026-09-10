from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path

from src.telegram_delivery import _multipart, send_audio


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return self._body


def test_multipart_contains_fields_and_audio(tmp_path: Path) -> None:
    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"audio-bytes")

    body, content_type = _multipart(
        {"chat_id": "123", "caption": "God morgon"},
        file_field="audio",
        file_path=audio,
    )

    assert b'name="chat_id"' in body
    assert b"God morgon" in body
    assert b"audio-bytes" in body
    assert content_type.startswith("multipart/form-data; boundary=")


def test_send_audio_returns_message_id(monkeypatch, tmp_path: Path) -> None:
    audio = tmp_path / "episode.mp3"
    audio.write_bytes(b"not-inspected-because-probe-is-mocked")
    monkeypatch.setattr(
        "src.telegram_delivery.verify_telegram_audio",
        lambda path: {"tags": {"title": "Morgonkoll 2026-09-10"}},
    )

    def fake_urlopen(request: urllib.request.Request, timeout: int):
        assert request.full_url.endswith("/sendAudio")
        assert "secret-token" in request.full_url
        assert timeout == 120
        return FakeResponse({"ok": True, "result": {"message_id": 42}})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert send_audio(audio, "secret-token", "123", "God morgon") == 42

