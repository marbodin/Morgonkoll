"""Domain-specific failures with actionable messages."""


class MorgonkollError(RuntimeError):
    """Base class for expected pipeline failures."""


class ConfigurationError(MorgonkollError):
    """Raised when checked-in configuration is invalid."""


class VoiceUnavailableError(MorgonkollError):
    """Raised when a free local voice cannot be prepared or used."""


class AudioProcessingError(MorgonkollError):
    """Raised when ffmpeg or ffprobe rejects generated audio."""

