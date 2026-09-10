"""Adapter for the pinned Swedish Kokoro model and neural G2P."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import soundfile as sf
from huggingface_hub import model_info

from ..errors import VoiceUnavailableError
from ..models import Candidate
from .base import VoiceEngine


class KokoroSwedishEngine(VoiceEngine):
    def __init__(self, candidate: Candidate) -> None:
        super().__init__(candidate)
        self._voice: Optional[Any] = None

    def _verify_revision(self, repo_id: str, expected: str) -> None:
        actual = model_info(repo_id=repo_id).sha
        if actual != expected:
            raise VoiceUnavailableError(
                f"{repo_id} moved from reviewed revision {expected} to {actual}; "
                "update the registry after reviewing the new model instead of "
                "silently downloading mutable weights"
            )

    def prepare(self) -> None:
        try:
            source = self.candidate.source
            self._verify_revision(
                str(source["voice_repository"]), str(source["voice_revision"])
            )
            self._verify_revision(
                str(source["g2p_repository"]), str(source["g2p_revision"])
            )
            from kokoro_sv import SwedishKokoro

            self._voice = SwedishKokoro(
                voices_repo=str(source["voice_repository"]), device="cpu"
            )
            if self.candidate.voice not in self._voice.voices:
                raise VoiceUnavailableError(
                    f"Voice {self.candidate.voice!r} is absent from the pinned pack"
                )
        except VoiceUnavailableError:
            raise
        except Exception as exc:
            raise VoiceUnavailableError(
                f"Could not load {self.candidate.label}: {exc}"
            ) from exc

    def synthesize(self, text: str, output_path: Path) -> None:
        if self._voice is None:
            raise VoiceUnavailableError(f"{self.candidate.label} was not prepared")
        try:
            samples = self._voice.synthesize(
                text,
                voice=self.candidate.voice,
                speed=self.candidate.speaking_rate,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(
                output_path,
                np.asarray(samples, dtype=np.float32),
                24_000,
            )
        except Exception as exc:
            raise VoiceUnavailableError(
                f"{self.candidate.label} failed to synthesize a segment: {exc}"
            ) from exc

    def close(self) -> None:
        self._voice = None

