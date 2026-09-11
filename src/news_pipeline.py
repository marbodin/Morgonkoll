"""Fetch current stories and create a source-audited Swedish narration script."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from .errors import MorgonkollError
from .news_fetch import fetch_all_sources, recent_articles
from .news_enrich import enrich_stories
from .news_models import GeneratedScript, Story
from .news_script import (
    LlamaScriptGenerator,
    ScriptGenerationError,
    deterministic_short_script,
)
from .news_select import select_stories
from .news_sources import load_news_sources
from .paths import ROOT


STOCKHOLM = ZoneInfo("Europe/Stockholm")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _sources_markdown(
    stories: List[Story],
    errors: Dict[str, str],
    episode_date: str,
) -> str:
    lines = [
        f"# Morgonkoll sources — {episode_date}",
        "",
        "The podcast script is a short original summary. Follow these links for "
        "the publishers' full reporting and context.",
        "",
    ]
    for index, story in enumerate(stories, start=1):
        lines.extend(
            [
                f"## {index}. {story.title}",
                "",
                f"- Topic: `{story.topic}`",
                f"- Published: {story.published_at.isoformat()}",
                f"- Sources: {', '.join(story.source_names)}",
            ]
        )
        lines.extend(
            f"- [{name}]({url})"
            for name, url in zip(story.source_names, story.source_urls)
        )
        lines.append("")
    if errors:
        lines.extend(["## Feed errors", ""])
        lines.extend(f"- `{source_id}`: {detail}" for source_id, detail in sorted(errors.items()))
        lines.append("")
    return "\n".join(lines)


def build_news_package(
    output_dir: Path,
    episode_date: str,
    now: Optional[datetime] = None,
    generator_factory: Callable[[], LlamaScriptGenerator] = LlamaScriptGenerator,
    allow_short_fallback: bool = True,
) -> GeneratedScript:
    started = time.monotonic()
    current = now or datetime.now(timezone.utc)
    sources = load_news_sources()
    articles, errors = fetch_all_sources(sources, fetched_at=current)
    recent = recent_articles(articles, current)
    stories = select_stories(recent, sources, current)
    enrichment_errors = enrich_stories(stories)
    represented_sources = {
        publisher_id for story in stories for publisher_id in story.publisher_ids
    }
    if len(represented_sources) < 4:
        raise MorgonkollError(
            f"Only {len(represented_sources)} independent sources were represented; "
            "at least 4 are required"
        )

    day_dir = output_dir / episode_date
    day_dir.mkdir(parents=True, exist_ok=True)
    _write_json(day_dir / "raw_articles.json", [article.to_dict() for article in articles])
    _write_json(day_dir / "selected_stories.json", [story.to_dict() for story in stories])
    _write_json(
        day_dir / "sources.json",
        [
            {
                "story_id": story.id,
                "topic": story.topic,
                "title": story.title,
                "published_at": story.published_at.isoformat(),
                "source_names": story.source_names,
                "source_types": story.source_types,
                "publisher_ids": story.publisher_ids,
                "source_urls": story.source_urls,
            }
            for story in stories
        ],
    )
    (day_dir / "sources.md").write_text(
        _sources_markdown(stories, errors, episode_date),
        encoding="utf-8",
    )

    try:
        script = generator_factory().generate(stories, episode_date)
        fallback_reason = None
    except ScriptGenerationError as exc:
        if not allow_short_fallback:
            raise
        script = deterministic_short_script(stories, episode_date)
        fallback_reason = str(exc)

    script_path = day_dir / "script.txt"
    script_path.write_text(script.text, encoding="utf-8")
    word_count = len(script.text.split())
    _write_json(
        day_dir / "manifest.json",
        {
            "episode_date": episode_date,
            "created_at": current.isoformat(),
            "generator": script.generator,
            "fallback_reason": fallback_reason,
            "article_count": len(articles),
            "recent_article_count": len(recent),
            "selected_story_count": len(stories),
            "represented_source_count": len(represented_sources),
            "feed_errors": errors,
            "article_enrichment_errors": enrichment_errors,
            "script_word_count": word_count,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "artifacts": {
                "script": str(script_path),
                "sources": str(day_dir / "sources.md"),
                "sources_json": str(day_dir / "sources.json"),
            },
        },
    )
    print(f"Created {script_path} with {script.generator}: {word_count} words")
    return script


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        default=datetime.now(STOCKHOLM).date().isoformat(),
        dest="episode_date",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "build" / "news",
    )
    parser.add_argument(
        "--no-short-fallback",
        action="store_true",
        help="Fail instead of emitting a shorter source-near script when the local model fails",
    )
    args = parser.parse_args(argv)
    try:
        build_news_package(
            output_dir=args.output_dir,
            episode_date=args.episode_date,
            allow_short_fallback=not args.no_short_fallback,
        )
    except MorgonkollError as exc:
        print(f"ERROR: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
