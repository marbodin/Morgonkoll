from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.models import Candidate


@pytest.fixture
def candidate_factory():
    def make(candidate_id: str, engine: str = "fake", **overrides: Any) -> Candidate:
        values = {
            "id": candidate_id,
            "label": candidate_id,
            "engine": engine,
            "model": f"{candidate_id}-model",
            "voice": "default",
            "status": "production",
            "license": "MIT",
            "code_license": "MIT",
            "approximate_download_mb": 1,
            "minimum_ram_gb": 1.0,
            "github_actions": True,
            "speaking_rate": 1.0,
            "source": {},
            "evidence_scores": {
                "swedish_naturalness": 7,
                "pronunciation": 7,
                "prosody": 7,
                "pleasantness": 7,
                "consistency": 7,
                "reliability": 7,
                "practicality": 7,
            },
        }
        values.update(overrides)
        return Candidate(**values)

    return make

