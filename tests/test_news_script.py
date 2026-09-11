from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from src.news_models import GeneratedScript, ScriptSection, Story
from src.news_script import (
    LlamaScriptGenerator,
    ScriptGenerationError,
    deterministic_short_script,
    validate_script,
)


def _stories() -> list[Story]:
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    return [
        Story(
            id=f"story-{index}",
            topic="technology",
            title=f"Nyhet {index}",
            summary=f"Företaget uppger resultat {index}.",
            published_at=now,
            source_ids=[f"source-{index}"],
            source_names=[f"Source {index}"],
            source_urls=[f"https://example.com/{index}"],
        )
        for index in range(1, 7)
    ]


def test_validation_rejects_unknown_numbers_and_story_ids() -> None:
    stories = _stories()
    repeated = " ".join(["saklig sammanfattning"] * 520)
    script = GeneratedScript(
        title="Morgonkoll",
        intro=repeated,
        sections=[
            ScriptSection("Teknik", [story.id], "Källnära text.")
            for story in stories
        ]
        + [ScriptSection("Fel", ["story-unknown"], "En investering på 999 miljarder.")],
        outro="Tack.",
        generator="test",
    )

    problems = validate_script(script, stories)

    assert any("okända story_ids" in problem for problem in problems)
    assert any("999" in problem for problem in problems)


def test_deterministic_fallback_preserves_source_mapping() -> None:
    stories = _stories()

    script = deterministic_short_script(stories, "2026-09-11")

    assert script.generator == "deterministic-short-fallback"
    assert {section.story_ids[0] for section in script.sections} == {
        story.id for story in stories
    }
    assert "kort" in script.intro


def test_hub_transport_failure_becomes_generation_error(monkeypatch) -> None:
    generator = LlamaScriptGenerator(
        {
            "repository": "example/model",
            "revision": "revision",
            "base_repository": "example/base",
            "base_revision": "base-revision",
        }
    )
    monkeypatch.setattr(
        "src.news_script.model_info",
        lambda **kwargs: (_ for _ in ()).throw(httpx.ConnectError("offline")),
    )

    with pytest.raises(ScriptGenerationError, match="resolve or download"):
        generator._load()
