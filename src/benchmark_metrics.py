"""Transparent technical metrics for voice samples."""

from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from .models import Candidate, TechnicalMetrics


def _dbfs(value: float) -> float:
    return 20.0 * math.log10(max(value, 1e-12))


def normalized_text(text: str) -> str:
    return " ".join(re.findall(r"[0-9a-zåäö]+", text.casefold()))


def transcription_similarity(reference: str, transcription: str) -> float:
    return SequenceMatcher(
        None, normalized_text(reference), normalized_text(transcription)
    ).ratio()


def inspect_sample(
    path: Path,
    reference_text: str,
    spoken_text: Optional[str] = None,
    transcription: Optional[str] = None,
) -> TechnicalMetrics:
    audio, sample_rate = sf.read(path, always_2d=True, dtype="float32")
    if audio.shape[0] == 0:
        raise ValueError(f"Audio sample is empty: {path}")
    mono = np.mean(audio, axis=1)
    absolute = np.abs(mono)
    peak = float(np.max(absolute))
    rms = float(np.sqrt(np.mean(np.square(mono, dtype=np.float64))))
    silence_threshold = 10 ** (-45.0 / 20.0)
    pacing_text = spoken_text if spoken_text is not None else reference_text
    word_count = len(re.findall(r"\b[\wÅÄÖåäö]+\b", pacing_text, flags=re.UNICODE))
    duration = len(mono) / float(sample_rate)
    return TechnicalMetrics(
        duration_seconds=duration,
        words_per_minute=word_count / duration * 60.0,
        peak_dbfs=_dbfs(peak),
        rms_dbfs=_dbfs(rms),
        silence_ratio=float(np.mean(absolute < silence_threshold)),
        clipping_ratio=float(np.mean(absolute >= 0.999)),
        sample_rate=int(sample_rate),
        channels=int(audio.shape[1]),
        transcription=transcription,
        transcription_similarity=(
            transcription_similarity(pacing_text, transcription)
            if transcription is not None
            else None
        ),
    )


def score_candidate(
    candidate: Candidate,
    metrics: TechnicalMetrics,
    generation_seconds: float,
) -> tuple[float, dict[str, float]]:
    prior = candidate.evidence_scores
    naturalness = prior.get("swedish_naturalness", 0.0)
    pronunciation = prior.get("pronunciation", 0.0)
    if metrics.transcription_similarity is not None:
        asr_score = 10.0 * metrics.transcription_similarity
        pronunciation = 0.6 * pronunciation + 0.4 * asr_score

    target_wpm = 155.0
    pacing_score = max(0.0, 10.0 - abs(metrics.words_per_minute - target_wpm) / 8.0)
    prosody = 0.75 * prior.get("prosody", 0.0) + 0.25 * pacing_score
    pleasantness = prior.get("pleasantness", 0.0)

    clipping_penalty = min(10.0, metrics.clipping_ratio * 10_000.0)
    silence_penalty = max(0.0, metrics.silence_ratio - 0.35) * 12.0
    consistency = max(
        0.0,
        min(
            10.0,
            prior.get("consistency", 0.0) - clipping_penalty - silence_penalty,
        ),
    )
    reliability = prior.get("reliability", 0.0)
    realtime_factor = generation_seconds / max(metrics.duration_seconds, 0.001)
    measured_practicality = max(0.0, 10.0 - max(0.0, realtime_factor - 1.0) * 0.6)
    practicality = 0.5 * prior.get("practicality", 0.0) + 0.5 * measured_practicality

    breakdown = {
        "swedish_naturalness": naturalness,
        "pronunciation": pronunciation,
        "prosody": prosody,
        "pleasantness": pleasantness,
        "consistency": consistency,
        "reliability": reliability,
        "practicality": practicality,
    }
    weights = {
        "swedish_naturalness": 0.40,
        "pronunciation": 0.20,
        "prosody": 0.15,
        "pleasantness": 0.10,
        "consistency": 0.05,
        "reliability": 0.05,
        "practicality": 0.05,
    }
    total = sum(breakdown[key] * weight for key, weight in weights.items())
    return total, breakdown
