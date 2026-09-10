"""Voice adapter construction without importing optional stacks eagerly."""

from __future__ import annotations

from ..errors import ConfigurationError
from ..models import Candidate
from .base import VoiceEngine


def create_engine(candidate: Candidate) -> VoiceEngine:
    if candidate.engine == "kokoro_sv":
        from .kokoro_sv import KokoroSwedishEngine

        return KokoroSwedishEngine(candidate)
    if candidate.engine == "piper":
        from .piper import PiperEngine

        return PiperEngine(candidate)
    if candidate.engine == "mms":
        from .mms import MmsEngine

        return MmsEngine(candidate)
    if candidate.engine == "chatterbox":
        from .chatterbox import ChatterboxEngine

        return ChatterboxEngine(candidate)
    raise ConfigurationError(
        f"No runnable adapter is implemented for engine {candidate.engine!r}"
    )
