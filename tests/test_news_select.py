from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.news_models import Article, NewsSource
from src.news_select import cluster_articles, select_stories


def _article(
    number: int,
    source: str,
    topic: str,
    title: str,
    now: datetime,
) -> Article:
    return Article(
        id=f"a{number}",
        source_id=source,
        source_name=source.upper(),
        topic=topic,
        title=title,
        summary=f"Sammanfattning för nyhet {number} med tillräckligt innehåll.",
        url=f"https://{source}.example/{number}",
        published_at=now - timedelta(hours=number),
        fetched_at=now,
    )


def test_clustering_merges_same_story_from_multiple_sources() -> None:
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    articles = [
        _article(1, "one", "technology", "Nytt AI-system lanseras i Sverige", now),
        _article(2, "two", "technology", "Nytt AI-system lanseras i Sverige i dag", now),
    ]

    clusters = cluster_articles(articles)

    assert len(clusters) == 1
    assert {item.source_id for item in clusters[0]} == {"one", "two"}


def test_selection_enforces_source_diversity() -> None:
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    sources = [
        NewsSource(
            id=f"s{index}",
            name=f"Source {index}",
            feed_url=f"https://s{index}.example/rss",
            language="sv",
            topic=topic,
            weight=1.0,
            homepage=f"https://s{index}.example",
        )
        for index, topic in enumerate(
            ["technology", "technology", "general", "economy", "gaming", "general"]
        )
    ]
    articles = [
        _article(
            index,
            source.id,
            source.topic,
            f"Unik morgonnyhet nummer {index} om {source.topic}",
            now,
        )
        for index, source in enumerate(sources, start=1)
    ]

    selected = select_stories(
        articles,
        sources,
        now,
        target_count=6,
        minimum_count=6,
        maximum_per_source=1,
    )

    assert len(selected) == 6
    assert len({story.source_ids[0] for story in selected}) == 6

