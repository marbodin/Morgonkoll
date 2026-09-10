from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
import pytest

from src.audio import probe_audio, verify_telegram_audio
from src.engines.base import VoiceEngine
from src.errors import VoiceUnavailableError
from src.pipeline import run_pipeline


class FakeEngine(VoiceEngine):
    def prepare(self) -> None:
        if self.candidate.id == "broken":
            raise VoiceUnavailableError("simulated model failure")

    def synthesize(self, text: str, output_path: Path) -> None:
        sample_rate = 22_050
        tone_duration = max(0.35, len(text.split()) / 16.0)
        tone_frames = int(sample_rate * tone_duration)
        tone = np.sin(2 * math.pi * 220 * np.arange(tone_frames) / sample_rate) * 0.12
        # An internal pause must survive edge trimming; otherwise words after a
        # natural pause would disappear from real TTS chunks.
        samples = np.concatenate(
            [tone, np.zeros(int(sample_rate * 0.3), dtype=np.float64), tone]
        )
        pcm = np.asarray(samples * 32767, dtype=np.int16)
        with wave.open(str(output_path), "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(sample_rate)
            target.writeframes(pcm.tobytes())


def test_pipeline_falls_back_and_creates_tagged_mp3(tmp_path, candidate_factory) -> None:
    script = tmp_path / "script.txt"
    original = "God morgon. Microsoft och GitHub bygger AI. Det här är dagens andra nyhet."
    script.write_text(original, encoding="utf-8")
    output = tmp_path / "morgonkoll-2026-09-10.mp3"
    cover = tmp_path / "cover.ppm"
    cover.write_bytes(b"P6\n2 2\n255\n" + bytes([30, 70, 120]) * 4)
    candidates = [candidate_factory("broken"), candidate_factory("working")]

    result = run_pipeline(
        script_path=script,
        output_path=output,
        episode_date="2026-09-10",
        cover_path=cover,
        candidates=candidates,
        engine_factory=FakeEngine,
        build_dir=tmp_path / "build",
    )

    assert result.candidate_id == "working"
    assert [attempt.healthy for attempt in result.attempts] == [False, True]
    assert script.read_text(encoding="utf-8") == original
    assert "Majkrosoft" in result.narration_path.read_text(encoding="utf-8")
    verification = verify_telegram_audio(output)
    assert verification["telegram_container_compatible"] is True
    assert verification["codec"] == "mp3"
    assert "working" in probe_audio(output)["format"]["tags"]["comment"]
    assert verification["duration_seconds"] >= 1.0
    cover_streams = [
        stream
        for stream in probe_audio(output)["streams"]
        if stream.get("disposition", {}).get("attached_pic") == 1
    ]
    assert len(cover_streams) == 1


def test_pipeline_fails_without_paid_fallback(tmp_path, candidate_factory) -> None:
    script = tmp_path / "script.txt"
    script.write_text("God morgon.", encoding="utf-8")

    with pytest.raises(VoiceUnavailableError, match="No paid service was used"):
        run_pipeline(
            script_path=script,
            output_path=tmp_path / "never.mp3",
            episode_date="2026-09-10",
            candidates=[candidate_factory("broken")],
            engine_factory=FakeEngine,
            build_dir=tmp_path / "build",
        )
