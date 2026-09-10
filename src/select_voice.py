"""Apply or restore a deliberate voice selection without editing JSON by hand."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import List, Optional

from .errors import ConfigurationError
from .voice_registry import (
    AUTOMATIC_PATH,
    SELECTED_PATH,
    load_selected,
    registry_by_id,
    restore_automatic_selection,
)


def select_human_override(candidate_id: str, path: Path = SELECTED_PATH) -> None:
    candidates = registry_by_id()
    candidate = candidates.get(candidate_id)
    if candidate is None:
        raise ConfigurationError(f"Unknown candidate {candidate_id!r}")
    if not candidate.audition_eligible:
        raise ConfigurationError(f"Candidate {candidate_id!r} is not approved for audition")

    automatic = load_selected(AUTOMATIC_PATH)
    fallback_ids = [
        str(automatic["candidate_id"]),
        *[str(item) for item in automatic.get("fallbacks", [])],
    ]
    fallback_ids = [item for item in fallback_ids if item != candidate_id]
    payload = {
        "schema_version": 1,
        "selection_mode": "human",
        "candidate_id": candidate.id,
        "engine": candidate.engine,
        "model": candidate.model,
        "voice": candidate.voice,
        "speaking_rate": candidate.speaking_rate,
        "reason": "Human override selected after listening to the fixed Morgonkoll audition sample.",
        "license": candidate.license,
        "benchmark_date": date.today().isoformat(),
        "fallbacks": fallback_ids,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_id", nargs="?")
    parser.add_argument("--restore-automatic", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.restore_automatic:
            restore_automatic_selection()
            print("Restored the automatic voice selection.")
            return 0
        if not args.candidate_id:
            parser.error("candidate_id is required unless --restore-automatic is used")
        select_human_override(args.candidate_id)
    except ConfigurationError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Selected {args.candidate_id}. The automatic selection remains available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

