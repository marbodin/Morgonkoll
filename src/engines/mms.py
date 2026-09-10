"""Transformers adapter for Meta's Swedish MMS VITS checkpoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import soundfile as sf

from ..errors import VoiceUnavailableError
from ..models import Candidate
from .base import VoiceEngine


class MmsEngine(VoiceEngine):
    def __init__(self, candidate: Candidate) -> None:
        super().__init__(candidate)
        self._model: Optional[Any] = None
        self._tokenizer: Optional[Any] = None

    def prepare(self) -> None:
        try:
            from transformers import AutoTokenizer, VitsModel

            revision = self.candidate.source["revision"]
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.candidate.model, revision=revision
            )
            self._model = VitsModel.from_pretrained(
                self.candidate.model, revision=revision
            )
            self._model.speaking_rate = self.candidate.speaking_rate
            self._model.eval()
        except Exception as exc:
            raise VoiceUnavailableError(
                f"Could not load {self.candidate.label}: {exc}"
            ) from exc

    def synthesize(self, text: str, output_path: Path) -> None:
        if self._model is None or self._tokenizer is None:
            raise VoiceUnavailableError(f"{self.candidate.label} was not prepared")
        try:
            import torch

            torch.manual_seed(1947)
            inputs = self._tokenizer(text, return_tensors="pt")
            with torch.inference_mode():
                waveform = self._model(**inputs).waveform.squeeze().cpu().numpy()
            sample_rate = int(self._model.config.sampling_rate)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, np.asarray(waveform, dtype=np.float32), sample_rate)
        except Exception as exc:
            raise VoiceUnavailableError(
                f"{self.candidate.label} failed to synthesize a segment: {exc}"
            ) from exc

    def close(self) -> None:
        self._model = None
        self._tokenizer = None
