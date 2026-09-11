from __future__ import annotations

from datetime import datetime, timezone

from src.news_fetch import clean_text, fetch_source, recent_articles
from src.news_models import NewsSource


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test News</title>
    <item>
      <guid>story-1</guid>
      <title>Ny svensk AI-modell lanseras</title>
      <description><![CDATA[<p>Modellen presenterades i Stockholm.</p>]]></description>
      <link>https://example.com/story-1</link>
      <pubDate>Thu, 10 Sep 2026 22:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

UNDATED_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Test</title><item>
<guid>undated</guid><title>Odaterad gammal post</title>
<description>Ingen verifierbar publiceringstid.</description>
<link>https://example.com/undated</link>
</item></channel></rss>"""


def test_fetch_source_normalizes_rss_and_html() -> None:
    source = NewsSource(
        id="example",
        name="Example",
        feed_url="https://example.com/rss.xml",
        language="sv",
        topic="technology",
        weight=1.0,
        homepage="https://example.com",
    )
    now = datetime(2026, 9, 10, 23, 0, tzinfo=timezone.utc)

    articles = fetch_source(
        source,
        now,
        loader=lambda url, timeout, allowed_hosts: RSS,
    )

    assert len(articles) == 1
    assert articles[0].summary == "Modellen presenterades i Stockholm."
    assert articles[0].published_at.hour == 22
    assert recent_articles(articles, now) == articles


def test_clean_text_removes_markup_and_collapses_space() -> None:
    assert clean_text("<p>Hej&nbsp; <b>världen</b></p>") == "Hej världen"


def test_undated_entries_are_not_treated_as_current() -> None:
    source = NewsSource(
        id="example",
        name="Example",
        feed_url="https://example.com/rss.xml",
        language="sv",
        topic="general",
        weight=1.0,
        homepage="https://example.com",
    )

    articles = fetch_source(
        source,
        datetime(2026, 9, 11, tzinfo=timezone.utc),
        loader=lambda url, timeout, allowed_hosts: UNDATED_RSS,
    )

    assert articles == []
