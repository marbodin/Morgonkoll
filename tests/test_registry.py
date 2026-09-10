import json
from pathlib import Path

import pytest

from src.errors import ConfigurationError
from src.voice_registry import resolve_voice_order


def _selected(path: Path, primary: str, fallbacks: list[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidate_id": primary,
                "fallbacks": fallbacks,
            }
        ),
        encoding="utf-8",
    )


def test_selection_keeps_explicit_fallback_order(tmp_path, candidate_factory) -> None:
    selected = tmp_path / "selected.json"
    _selected(selected, "first", ["second"])
    candidates = [candidate_factory("first"), candidate_factory("second")]

    result = resolve_voice_order(selected, candidates=candidates, environment={})

    assert [candidate.id for candidate in result] == ["first", "second"]


def test_environment_override_must_be_unambiguous(tmp_path, candidate_factory) -> None:
    selected = tmp_path / "selected.json"
    _selected(selected, "first", [])
    candidates = [
        candidate_factory("first", engine="same"),
        candidate_factory("second", engine="same"),
    ]

    with pytest.raises(ConfigurationError, match="exactly one"):
        resolve_voice_order(
            selected,
            candidates=candidates,
            environment={"TTS_ENGINE": "same"},
        )

