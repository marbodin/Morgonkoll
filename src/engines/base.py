"""Interface implemented by every local voice adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import Candidate


class VoiceEngine(ABC):
    def __init__(self, candidate: Candidate) -> None:
        self.candidate = candidate

    @abstractmethod
    def prepare(self) -> None:
        """Download (through normal caches) and load the configured model."""

    @abstractmethod
    def synthesize(self, text: str, output_path: Path) -> None:
        """Write one mono WAV segment."""

    def close(self) -> None:
        """Release heavyweight model state when an adapter needs cleanup."""

