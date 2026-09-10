"""Piper ONNX adapter for the native Swedish NST voice."""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Any, Optional

from huggingface_hub import hf_hub_download

from ..errors import VoiceUnavailableError
from ..models import Candidate
from .base import VoiceEngine


class PiperEngine(VoiceEngine):
    def __init__(self, candidate: Candidate) -> None:
        super().__init__(candidate)
        self._voice: Optional[Any] = None

    def prepare(self) -> None:
        try:
            from piper import PiperVoice

            source = self.candidate.source
            common = {
                "repo_id": source["repository"],
                "revision": source["revision"],
            }
            model_path = hf_hub_download(filename=source["model_path"], **common)
            config_path = hf_hub_download(filename=source["config_path"], **common)
            self._voice = PiperVoice.load(model_path, config_path=config_path, use_cuda=False)
        except Exception as exc:
            raise VoiceUnavailableError(
                f"Could not load {self.candidate.label}: {exc}"
            ) from exc

    def synthesize(self, text: str, output_path: Path) -> None:
        if self._voice is None:
            raise VoiceUnavailableError(f"{self.candidate.label} was not prepared")
        try:
            from piper import SynthesisConfig

            output_path.parent.mkdir(parents=True, exist_ok=True)
            synthesis = SynthesisConfig(
                length_scale=1.0 / self.candidate.speaking_rate,
                normalize_audio=True,
            )
            with wave.open(str(output_path), "wb") as wav_file:
                self._voice.synthesize_wav(text, wav_file, syn_config=synthesis)
        except Exception as exc:
            raise VoiceUnavailableError(
                f"{self.candidate.label} failed to synthesize a segment: {exc}"
            ) from exc

    def close(self) -> None:
        self._voice = None

