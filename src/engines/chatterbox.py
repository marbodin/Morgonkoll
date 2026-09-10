"""Pinned Chatterbox Multilingual V3 CPU adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import soundfile as sf
from huggingface_hub import snapshot_download

from ..errors import VoiceUnavailableError
from ..models import Candidate
from .base import VoiceEngine


class ChatterboxEngine(VoiceEngine):
    def __init__(self, candidate: Candidate) -> None:
        super().__init__(candidate)
        self._model: Optional[Any] = None

    def prepare(self) -> None:
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            source = self.candidate.source
            t3_filename = "t3_mtl23ls_v3.safetensors"
            checkpoint_dir = snapshot_download(
                repo_id=source["repository"],
                revision=source["revision"],
                allow_patterns=[
                    "ve.pt",
                    t3_filename,
                    "s3gen.pt",
                    "grapheme_mtl_merged_expanded_v1.json",
                    "conds.pt",
                    "Cangjie5_TC.json",
                ],
            )
            self._model = ChatterboxMultilingualTTS.from_local(
                checkpoint_dir, device="cpu", t3_model=source.get("t3_model", "v3")
            )
        except Exception as exc:
            raise VoiceUnavailableError(
                f"Could not load {self.candidate.label}: {exc}"
            ) from exc

    def synthesize(self, text: str, output_path: Path) -> None:
        if self._model is None:
            raise VoiceUnavailableError(f"{self.candidate.label} was not prepared")
        try:
            import torch

            torch.manual_seed(1947)
            waveform = self._model.generate(
                text,
                language_id=str(self.candidate.source.get("language", "sv")),
                exaggeration=0.45,
                cfg_weight=0.45,
                temperature=0.75,
            )
            samples = waveform.squeeze().detach().cpu().numpy()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(
                output_path,
                np.asarray(samples, dtype=np.float32),
                int(self._model.sr),
            )
        except Exception as exc:
            raise VoiceUnavailableError(
                f"{self.candidate.label} failed to synthesize a segment: {exc}"
            ) from exc

    def close(self) -> None:
        self._model = None

