"""Reproducible candidate discovery and selected-voice resolution."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

import yaml

from .errors import ConfigurationError
from .models import Candidate
from .paths import CONFIG_DIR


REGISTRY_PATH = CONFIG_DIR / "voice_candidates.yml"
SELECTED_PATH = CONFIG_DIR / "selected_voice.json"
AUTOMATIC_PATH = CONFIG_DIR / "automatic_voice.json"


def load_registry(path: Path = REGISTRY_PATH) -> List[Candidate]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Could not read voice registry {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ConfigurationError(f"Unsupported or missing schema_version in {path}")

    candidates: List[Candidate] = []
    seen = set()
    for raw in payload.get("candidates", []):
        candidate_id = raw.get("id")
        if not candidate_id or candidate_id in seen:
            raise ConfigurationError(f"Voice candidate id is missing or duplicated: {candidate_id!r}")
        seen.add(candidate_id)
        try:
            candidates.append(
                Candidate(
                    id=candidate_id,
                    label=raw["label"],
                    engine=raw["engine"],
                    model=raw["model"],
                    voice=raw["voice"],
                    status=raw["status"],
                    license=raw["license"],
                    code_license=raw["code_license"],
                    approximate_download_mb=int(raw["approximate_download_mb"]),
                    minimum_ram_gb=float(raw["minimum_ram_gb"]),
                    github_actions=bool(raw["github_actions"]),
                    speaking_rate=float(raw.get("speaking_rate", 1.0)),
                    source=dict(raw.get("source", {})),
                    evidence_scores={
                        str(key): float(value)
                        for key, value in dict(raw.get("evidence_scores", {})).items()
                    },
                    notes=str(raw.get("notes", "")),
                    excluded_reason=raw.get("excluded_reason"),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigurationError(f"Invalid registry entry {candidate_id!r}: {exc}") from exc
    return candidates


def registry_by_id(candidates: Optional[Iterable[Candidate]] = None) -> Dict[str, Candidate]:
    values = list(candidates) if candidates is not None else load_registry()
    return {candidate.id: candidate for candidate in values}


def discover_candidates(mode: str = "automatic") -> List[Candidate]:
    candidates = load_registry()
    if mode == "automatic":
        return [candidate for candidate in candidates if candidate.automatic_eligible]
    if mode == "audition":
        return [candidate for candidate in candidates if candidate.audition_eligible]
    if mode == "all":
        return candidates
    raise ConfigurationError(f"Unknown discovery mode: {mode}")


def load_selected(path: Path = SELECTED_PATH) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Could not read selected voice {path}: {exc}") from exc
    if payload.get("schema_version") != 1:
        raise ConfigurationError(f"Unsupported selected voice schema in {path}")
    return payload


def resolve_voice_order(
    selected_path: Path = SELECTED_PATH,
    candidates: Optional[Iterable[Candidate]] = None,
    environment: Optional[Mapping[str, str]] = None,
) -> List[Candidate]:
    available = registry_by_id(candidates)
    selected = load_selected(selected_path)
    env = environment if environment is not None else os.environ

    requested_engine = env.get("TTS_ENGINE")
    requested_model = env.get("TTS_MODEL")
    requested_voice = env.get("TTS_VOICE")
    if requested_engine or requested_model or requested_voice:
        matches = [
            candidate
            for candidate in available.values()
            if (not requested_engine or candidate.engine == requested_engine)
            and (not requested_model or candidate.model == requested_model)
            and (not requested_voice or candidate.voice == requested_voice)
            and candidate.audition_eligible
        ]
        if len(matches) != 1:
            raise ConfigurationError(
                "TTS_ENGINE/TTS_MODEL/TTS_VOICE must identify exactly one viable registry candidate"
            )
        primary_id = matches[0].id
    else:
        primary_id = str(selected.get("candidate_id", ""))

    fallback_ids = [str(item) for item in selected.get("fallbacks", [])]
    order: List[Candidate] = []
    for candidate_id in [primary_id] + fallback_ids:
        candidate = available.get(candidate_id)
        if candidate is None:
            raise ConfigurationError(f"Selected voice references unknown candidate {candidate_id!r}")
        if candidate.status not in {"production", "audition"}:
            raise ConfigurationError(f"Selected voice {candidate_id!r} is not viable")
        if candidate not in order:
            order.append(candidate)
    return order


def save_selection(
    candidate: Candidate,
    reason: str,
    fallback_ids: List[str],
    benchmark_date: str,
    path: Path = SELECTED_PATH,
) -> None:
    payload = {
        "schema_version": 1,
        "selection_mode": "automatic",
        "candidate_id": candidate.id,
        "engine": candidate.engine,
        "model": candidate.model,
        "voice": candidate.voice,
        "speaking_rate": candidate.speaking_rate,
        "reason": reason,
        "license": candidate.license,
        "benchmark_date": benchmark_date,
        "fallbacks": fallback_ids,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def restore_automatic_selection(
    automatic_path: Path = AUTOMATIC_PATH, selected_path: Path = SELECTED_PATH
) -> None:
    load_selected(automatic_path)
    shutil.copyfile(automatic_path, selected_path)

