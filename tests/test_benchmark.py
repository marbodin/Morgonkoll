from pathlib import Path

import numpy as np
import soundfile as sf

from src.benchmark_metrics import inspect_sample, score_candidate


def test_benchmark_score_penalizes_bad_pacing(tmp_path: Path, candidate_factory) -> None:
    path = tmp_path / "sample.wav"
    sample_rate = 16_000
    sf.write(path, np.full(sample_rate * 60, 0.1, dtype=np.float32), sample_rate)
    reference = "ett två tre fyra fem " * 20
    candidate = candidate_factory("candidate")
    metrics = inspect_sample(path, reference)

    score, breakdown = score_candidate(candidate, metrics, generation_seconds=5.0)

    assert 0 < score < 10
    assert breakdown["prosody"] < 7
    assert metrics.words_per_minute == 100

