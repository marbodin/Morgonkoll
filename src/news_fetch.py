"""Bounded concurrent fetching and normalization of reviewed RSS/Atom feeds."""

from __future__ import annotations

import calendar
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import feedparser

from .errors import MorgonkollError
from .news_models import Article, NewsSource
from .network_safety import NO_REDIRECT_OPENER, validate_public_https_target
from .paths import feed_cache_dir


MAX_FEED_BYTES = 3 * 1024 * 1024
MAX_SUMMARY_CHARS = 2_000
CACHE_FALLBACK_SECONDS = 6 * 60 * 60


class FeedFetchError(MorgonkollError):
    """Raised when a reviewed feed cannot be safely normalized."""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_text(value: str, limit: int = MAX_SUMMARY_CHARS) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    text = html.unescape(" ".join(parser.parts))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].strip()


def _entry_datetime(entry: object) -> Optional[datetime]:
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        value = getattr(entry, field, None)
        if value:
            return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc)
    return None


def _article_id(source_id: str, identity: str) -> str:
    digest = hashlib.sha256(f"{source_id}\0{identity}".encode("utf-8")).hexdigest()
    return digest[:16]


def _default_loader(
    url: str,
    timeout_seconds: int,
    allowed_hosts: Iterable[str],
) -> bytes:
    feed_cache = feed_cache_dir()
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    body_path = feed_cache / f"{cache_key}.xml"
    metadata_path = feed_cache / f"{cache_key}.json"
    metadata: Dict[str, str] = {}
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            metadata = {}
    headers = {
        "User-Agent": "Morgonkoll/0.1 (+https://github.com/marbodin/Morgonkoll)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
    }
    if metadata.get("etag"):
        headers["If-None-Match"] = metadata["etag"]
    if metadata.get("last_modified"):
        headers["If-Modified-Since"] = metadata["last_modified"]
    current_url = url
    try:
        for _hop in range(5):
            validate_public_https_target(current_url, allowed_hosts)
            request = urllib.request.Request(current_url, headers=headers)
            try:
                response = NO_REDIRECT_OPENER.open(request, timeout=timeout_seconds)
            except urllib.error.HTTPError as exc:
                if exc.code == 304 and body_path.is_file():
                    return body_path.read_bytes()
                if exc.code in {301, 302, 303, 307, 308}:
                    location = exc.headers.get("Location")
                    if not location:
                        raise FeedFetchError("Feed redirect has no Location") from exc
                    current_url = urljoin(current_url, location)
                    continue
                if (
                    exc.code in {429, 500, 502, 503, 504}
                    and body_path.is_file()
                    and time.time() - body_path.stat().st_mtime <= CACHE_FALLBACK_SECONDS
                ):
                    return body_path.read_bytes()
                raise FeedFetchError(f"Feed returned HTTP {exc.code}") from exc
            with response:
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > MAX_FEED_BYTES:
                    raise FeedFetchError(f"Feed is larger than {MAX_FEED_BYTES} bytes")
                response_headers = response.headers
                payload = response.read(MAX_FEED_BYTES + 1)
            break
        else:
            raise FeedFetchError("Feed exceeded the redirect limit")
    except urllib.error.URLError as exc:
        if (
            body_path.is_file()
            and time.time() - body_path.stat().st_mtime <= CACHE_FALLBACK_SECONDS
        ):
            return body_path.read_bytes()
        raise FeedFetchError(f"Feed request failed: {exc.reason}") from exc
    if len(payload) > MAX_FEED_BYTES:
        raise FeedFetchError(f"Feed exceeded the {MAX_FEED_BYTES}-byte limit")
    temporary_body = body_path.with_suffix(".tmp")
    temporary_body.write_bytes(payload)
    temporary_body.replace(body_path)
    metadata_path.write_text(
        json.dumps(
            {
                "url": url,
                "etag": response_headers.get("ETag", ""),
                "last_modified": response_headers.get("Last-Modified", ""),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return payload


def fetch_source(
    source: NewsSource,
    fetched_at: datetime,
    loader: Callable[[str, int, Iterable[str]], bytes] = _default_loader,
    timeout_seconds: int = 20,
    max_entries: int = 25,
) -> List[Article]:
    payload = loader(source.feed_url, timeout_seconds, source.allowed_article_hosts)
    parsed = feedparser.parse(payload)
    if parsed.bozo and not parsed.entries:
        raise FeedFetchError(f"{source.name} returned malformed feed data")

    articles: List[Article] = []
    for entry in parsed.entries[:max_entries]:
        title = clean_text(str(entry.get("title", "")), limit=500)
        summary = clean_text(
            str(entry.get("summary") or entry.get("description") or ""),
            limit=MAX_SUMMARY_CHARS,
        )
        url = str(entry.get("link", "")).strip()
        if any(pattern in title.casefold() for pattern in source.exclude_title_patterns):
            continue
        if not summary and not source.allow_article_fetch:
            continue
        if not title or urlparse(url).scheme not in {"https", "http"}:
            continue
        identity = str(entry.get("id") or entry.get("guid") or url)
        published_at = _entry_datetime(entry)
        if published_at is None:
            continue
        articles.append(
            Article(
                id=_article_id(source.id, identity),
                source_id=source.id,
                source_name=source.name,
                topic=source.topic,
                title=title,
                summary=summary,
                url=url,
                published_at=published_at,
                fetched_at=fetched_at,
                source_type=source.source_type,
                allow_article_fetch=source.allow_article_fetch,
                publisher_id=source.publisher_id,
                allowed_article_hosts=source.allowed_article_hosts,
            )
        )
    return articles


def fetch_all_sources(
    sources: Iterable[NewsSource],
    fetched_at: Optional[datetime] = None,
    loader: Callable[[str, int, Iterable[str]], bytes] = _default_loader,
    max_workers: int = 6,
) -> Tuple[List[Article], Dict[str, str]]:
    now = fetched_at or datetime.now(timezone.utc)
    source_list = list(sources)
    articles: List[Article] = []
    errors: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(source_list))) as executor:
        futures = {
            executor.submit(fetch_source, source, now, loader): source
            for source in source_list
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                articles.extend(future.result())
            except Exception as exc:
                errors[source.id] = str(exc)
    return articles, errors


def recent_articles(
    articles: Iterable[Article],
    now: datetime,
    maximum_age_hours: int = 36,
) -> List[Article]:
    cutoff = now - timedelta(hours=maximum_age_hours)
    future_limit = now + timedelta(minutes=15)
    return [
        article
        for article in articles
        if cutoff <= article.published_at <= future_limit
    ]
