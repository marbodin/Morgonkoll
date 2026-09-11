"""Load and validate the reviewed news-source allowlist."""

from __future__ import annotations

from pathlib import Path
from typing import List
from urllib.parse import urlparse

import yaml

from .errors import ConfigurationError
from .news_models import NewsSource
from .paths import CONFIG_DIR


DEFAULT_PATH = CONFIG_DIR / "news_sources.yml"
TOPICS = {"technology", "general", "economy", "gaming"}
SOURCE_TYPES = {"public_broadcaster", "editorial", "primary"}


def load_news_sources(path: Path = DEFAULT_PATH) -> List[NewsSource]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Could not read news sources {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ConfigurationError(f"Unsupported news-source schema in {path}")

    sources: List[NewsSource] = []
    seen = set()
    for raw in payload.get("sources", []):
        source_id = str(raw.get("id", "")).strip()
        feed_url = str(raw.get("feed_url", "")).strip()
        parsed = urlparse(feed_url)
        if not source_id or source_id in seen:
            raise ConfigurationError(f"News source id is missing or duplicated: {source_id!r}")
        if parsed.scheme != "https" or not parsed.hostname:
            raise ConfigurationError(f"News feed must use an absolute HTTPS URL: {feed_url}")
        topic = str(raw.get("topic", ""))
        if topic not in TOPICS:
            raise ConfigurationError(f"Unknown topic {topic!r} for source {source_id}")
        weight = float(raw.get("weight", 1.0))
        if not 0.1 <= weight <= 2.0:
            raise ConfigurationError(f"Source weight must be between 0.1 and 2.0: {source_id}")
        source_type = str(raw.get("source_type", "editorial"))
        if source_type not in SOURCE_TYPES:
            raise ConfigurationError(
                f"Unknown source_type {source_type!r} for source {source_id}"
            )
        homepage = str(raw["homepage"])
        default_hosts = {
            host
            for host in (
                urlparse(feed_url).hostname,
                urlparse(homepage).hostname,
            )
            if host
        }
        allowed_hosts = tuple(
            sorted(
                str(host).casefold().strip(".")
                for host in raw.get("allowed_article_hosts", default_hosts)
            )
        )
        if not allowed_hosts:
            raise ConfigurationError(
                f"At least one allowed article host is required: {source_id}"
            )
        seen.add(source_id)
        sources.append(
            NewsSource(
                id=source_id,
                name=str(raw["name"]),
                feed_url=feed_url,
                language=str(raw.get("language", "sv")),
                topic=topic,
                weight=weight,
                homepage=homepage,
                source_type=source_type,
                allow_article_fetch=bool(raw.get("allow_article_fetch", True)),
                exclude_title_patterns=tuple(
                    str(item).casefold()
                    for item in raw.get("exclude_title_patterns", [])
                ),
                publisher_id=str(raw.get("publisher_id", source_id)),
                allowed_article_hosts=allowed_hosts,
            )
        )
    if not sources:
        raise ConfigurationError("At least one news source is required")
    return sources
