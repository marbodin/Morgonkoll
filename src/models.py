"""Typed data structures shared by the voice pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Candidate:
    id: str
    label: str
    engine: str
    model: str
    voice: str
    status: str
    license: str
    code_license: str
    approximate_download_mb: int
    minimum_ram_gb: float
    github_actions: bool
    speaking_rate: float
    source: Dict[str, Any] = field(default_factory=dict)
    evidence_scores: Dict[str, float] = field(default_factory=dict)
    notes: str = ""
    excluded_reason: Optional[str] = None

    @property
    def automatic_eligible(self) -> bool:
        return self.status == "production" and self.github_actions

    @property
    def audition_eligible(self) -> bool:
        return self.status in {"production", "audition"} and self.github_actions


@dataclass(frozen=True)
class NarrationChunk:
    index: int
    text: str
    pause_after_ms: int


@dataclass
class HealthResult:
    candidate_id: str
    healthy: bool
    detail: str
    elapsed_seconds: float = 0.0


@dataclass
class TechnicalMetrics:
    duration_seconds: float
    words_per_minute: float
    peak_dbfs: float
    rms_dbfs: float
    silence_ratio: float
    clipping_ratio: float
    sample_rate: int
    channels: int
    transcription: Optional[str] = None
    transcription_similarity: Optional[float] = None


@dataclass
class BenchmarkResult:
    candidate: Candidate
    sample_path: Optional[Path]
    generated: bool
    generation_seconds: float
    metrics: Optional[TechnicalMetrics]
    weighted_score: float
    score_breakdown: Dict[str, float]
    error: Optional[str] = None


@dataclass
class PipelineResult:
    output_path: Path
    candidate_id: str
    duration_seconds: float
    chunk_count: int
    narration_path: Path
    attempts: List[HealthResult]

