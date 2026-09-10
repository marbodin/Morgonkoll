"""Lightweight selected-model load checks with free-only fallback reporting."""

from __future__ import annotations

import argparse
import gc
import json
import time
from typing import Iterable, List, Optional

from .engines import create_engine
from .models import Candidate, HealthResult
from .voice_registry import resolve_voice_order


SAFE_FAILURE_MESSAGE = (
    "No compatible free TTS voice is currently available. No paid service was used."
)


def check_candidate(candidate: Candidate) -> HealthResult:
    started = time.monotonic()
    engine = None
    try:
        engine = create_engine(candidate)
        engine.prepare()
        return HealthResult(
            candidate_id=candidate.id,
            healthy=True,
            detail="Engine and pinned model loaded successfully",
            elapsed_seconds=time.monotonic() - started,
        )
    except Exception as exc:
        return HealthResult(
            candidate_id=candidate.id,
            healthy=False,
            detail=str(exc),
            elapsed_seconds=time.monotonic() - started,
        )
    finally:
        if engine is not None:
            engine.close()
        gc.collect()


def find_healthy_voice(
    candidates: Optional[Iterable[Candidate]] = None,
) -> tuple[Optional[Candidate], List[HealthResult]]:
    ordered = list(candidates) if candidates is not None else resolve_voice_order()
    attempts: List[HealthResult] = []
    for candidate in ordered:
        result = check_candidate(candidate)
        attempts.append(result)
        if result.healthy:
            return candidate, attempts
    return None, attempts


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable results")
    args = parser.parse_args(argv)

    candidate, attempts = find_healthy_voice()
    if args.json:
        print(
            json.dumps(
                {
                    "healthy_candidate": candidate.id if candidate else None,
                    "attempts": [attempt.__dict__ for attempt in attempts],
                    "message": None if candidate else SAFE_FAILURE_MESSAGE,
                },
                indent=2,
            )
        )
    else:
        for attempt in attempts:
            state = "OK" if attempt.healthy else "FAILED"
            print(f"{state}: {attempt.candidate_id} - {attempt.detail}")
        if candidate:
            print(f"Selected healthy voice: {candidate.id}")
        else:
            print(SAFE_FAILURE_MESSAGE)
    return 0 if candidate else 2


if __name__ == "__main__":
    raise SystemExit(main())

