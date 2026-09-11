from __future__ import annotations

from datetime import datetime, timezone
import socket

import pytest

from src.network_safety import validate_public_https_target
from src.news_enrich import enrich_stories, extract_article_text
from src.news_models import Story


def test_extract_article_text_removes_navigation_markup() -> None:
    markup = """
    <html><body><nav>Menu</nav><article><h1>Rubrik</h1>
    <p>Det här är den viktiga artikeltexten med flera tydliga meningar.</p>
    <p>Ytterligare källmaterial finns i denna paragraf.</p>
    <p>Så arbetar vi SVT:s nyheter ska stå för saklighet och opartiskhet.</p>
    </article></body></html>
    """

    result = extract_article_text(
        "https://example.com/story",
        allowed_hosts=("example.com",),
        downloader=lambda url, timeout, allowed_hosts: markup,
    )

    assert "viktiga artikeltexten" in result
    assert "Ytterligare källmaterial" in result
    assert "Så arbetar vi" not in result


def test_enrichment_uses_summary_when_article_fetch_is_disabled() -> None:
    story = Story(
        id="story-1",
        topic="technology",
        title="Rubrik",
        summary="Källans korta sammanfattning.",
        published_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
        source_ids=["source"],
        source_names=["Source"],
        source_urls=["https://example.com/story"],
        allow_article_fetch=False,
    )

    errors = enrich_stories(
        [story],
        extractor=lambda url, allowed_hosts: (
            _ for _ in ()
        ).throw(AssertionError("must not fetch")),
    )

    assert errors == {}
    assert story.source_material == [story.summary]


def test_target_validation_rejects_unreviewed_redirect_host() -> None:
    with pytest.raises(RuntimeError, match="outside the reviewed allowlist"):
        validate_public_https_target(
            "https://attacker.example/article",
            allowed_hosts=("publisher.example",),
        )


def test_target_validation_rejects_private_dns(monkeypatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )

    with pytest.raises(RuntimeError, match="non-public"):
        validate_public_https_target(
            "https://publisher.example/article",
            allowed_hosts=("publisher.example",),
        )
