from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.news_models import GeneratedScript, ScriptSection, Story
from src.news_pipeline import build_news_package
from src.news_script import ScriptGenerationError


class FakeGenerator:
    def generate(self, stories, episode_date):
        return GeneratedScript(
            title=f"Morgonkoll {episode_date}",
            intro="God morgon.",
            sections=[
                ScriptSection(
                    heading=story.title,
                    story_ids=[story.id],
                    body=story.summary,
                )
                for story in stories
            ],
            outro="Tack.",
            generator="fake-generator",
        )


class BrokenGenerator:
    def generate(self, stories, episode_date):
        raise ScriptGenerationError("simulated local model outage")


def test_news_package_writes_source_artifacts(monkeypatch, tmp_path: Path) -> None:
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    stories = [
        Story(
            id=f"story-{index}",
            topic="technology",
            title=f"Rubrik {index}",
            summary=f"Sammanfattning {index}.",
            published_at=now,
            source_ids=[f"source-{index}"],
            source_names=[f"Source {index}"],
            source_urls=[f"https://example.com/{index}"],
            publisher_ids=[f"publisher-{index}"],
        )
        for index in range(6)
    ]
    monkeypatch.setattr("src.news_pipeline.load_news_sources", lambda: [object()])
    monkeypatch.setattr(
        "src.news_pipeline.fetch_all_sources",
        lambda sources, fetched_at: ([], {}),
    )
    monkeypatch.setattr("src.news_pipeline.recent_articles", lambda articles, current: [])
    monkeypatch.setattr(
        "src.news_pipeline.select_stories",
        lambda articles, sources, current: stories,
    )
    monkeypatch.setattr(
        "src.news_pipeline.enrich_stories",
        lambda selected: {},
    )

    build_news_package(
        output_dir=tmp_path,
        episode_date="2026-09-11",
        now=now,
        generator_factory=FakeGenerator,
    )

    day = tmp_path / "2026-09-11"
    assert (day / "script.txt").is_file()
    assert (day / "sources.md").is_file()
    assert (day / "sources.json").is_file()
    assert (day / "selected_stories.json").is_file()
    assert '"generator": "fake-generator"' in (day / "manifest.json").read_text()


def test_news_package_uses_short_fallback_on_model_failure(
    monkeypatch, tmp_path: Path
) -> None:
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    stories = [
        Story(
            id=f"story-{index}",
            topic="general",
            title=f"Rubrik {index}",
            summary=f"Sammanfattning {index}.",
            published_at=now,
            source_ids=[f"source-{index}"],
            source_names=[f"Source {index}"],
            source_urls=[f"https://example.com/{index}"],
            publisher_ids=[f"publisher-{index}"],
        )
        for index in range(6)
    ]
    monkeypatch.setattr("src.news_pipeline.load_news_sources", lambda: [object()])
    monkeypatch.setattr(
        "src.news_pipeline.fetch_all_sources", lambda sources, fetched_at: ([], {})
    )
    monkeypatch.setattr("src.news_pipeline.recent_articles", lambda articles, current: [])
    monkeypatch.setattr(
        "src.news_pipeline.select_stories",
        lambda articles, sources, current: stories,
    )
    monkeypatch.setattr("src.news_pipeline.enrich_stories", lambda selected: {})

    script = build_news_package(
        output_dir=tmp_path,
        episode_date="2026-09-11",
        now=now,
        generator_factory=BrokenGenerator,
    )

    assert script.generator == "deterministic-short-fallback"
    manifest = (tmp_path / "2026-09-11" / "manifest.json").read_text()
    assert "simulated local model outage" in manifest
