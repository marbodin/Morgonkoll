"""Deduplicate, rank and diversify candidate news stories."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Mapping, Sequence, Set

from .errors import MorgonkollError
from .news_models import Article, NewsSource, Story


STOPWORDS = {
    "att", "av", "de", "den", "det", "en", "ett", "för", "från", "har",
    "i", "med", "och", "om", "på", "som", "till", "under", "vid", "är",
    "a", "an", "and", "as", "at", "for", "from", "in", "is", "of", "on",
    "the", "to", "with",
}

TOPIC_SHARES = {
    "technology": 0.40,
    "general": 0.25,
    "economy": 0.20,
    "gaming": 0.15,
}

TOPIC_KEYWORDS = {
    "technology": {
        "ai", "artificiell", "intelligence", "model", "openai", "anthropic",
        "nvidia", "microsoft", "google", "apple", "chip", "robot", "quantum",
        "cyber", "security", "software", "cloud", "data", "startup", "tech",
    },
    "economy": {
        "ekonomi", "economy", "inflation", "ränta", "rate", "bank", "marknad",
        "market", "krona", "euro", "dollar", "jobb", "jobs", "gdp", "bnp",
    },
    "gaming": {
        "spel", "game", "gaming", "xbox", "playstation", "nintendo", "steam",
        "studio", "developer", "release", "lansering",
    },
}


def title_tokens(title: str) -> Set[str]:
    tokens = set(re.findall(r"[0-9a-zåäö]{3,}", title.casefold()))
    return tokens - STOPWORDS


def title_similarity(left: str, right: str) -> float:
    left_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", left))
    right_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", right))
    if left_numbers and right_numbers and left_numbers != right_numbers:
        return 0.0
    left_tokens = title_tokens(left)
    right_tokens = title_tokens(right)
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, left.casefold(), right.casefold()).ratio()
    return max(jaccard, sequence * 0.8)


def cluster_articles(
    articles: Iterable[Article],
    similarity_threshold: float = 0.52,
) -> List[List[Article]]:
    clusters: List[List[Article]] = []
    for article in sorted(articles, key=lambda item: item.published_at, reverse=True):
        match = next(
            (
                cluster
                for cluster in clusters
                if title_similarity(article.title, cluster[0].title) >= similarity_threshold
            ),
            None,
        )
        if match is None:
            clusters.append([article])
        else:
            match.append(article)
    return clusters


def _cluster_story(
    cluster: Sequence[Article],
    source_weights: Mapping[str, float],
    now: datetime,
) -> Story:
    representative = max(
        cluster,
        key=lambda article: (
            source_weights.get(article.source_id, 1.0),
            len(article.summary),
            article.published_at,
        ),
    )
    age_hours = max(0.0, (now - representative.published_at).total_seconds() / 3600.0)
    recency = math.exp(-age_hours / 24.0)
    corroboration = min(0.8, 0.2 * (len({item.source_id for item in cluster}) - 1))
    substance = min(0.6, len(representative.summary) / 1_000.0)
    context_tokens = title_tokens(
        f"{representative.title} {representative.summary[:500]}"
    )
    relevance_matches = len(
        context_tokens & TOPIC_KEYWORDS.get(representative.topic, set())
    )
    relevance = min(1.0, relevance_matches * 0.25)
    score = (
        2.0 * source_weights.get(representative.source_id, 1.0)
        + 2.0 * recency
        + corroboration
        + substance
        + relevance
    )
    ordered = sorted(
        cluster,
        key=lambda article: (
            source_weights.get(article.source_id, 1.0),
            article.published_at,
        ),
        reverse=True,
    )
    return Story(
        id=f"story-{representative.id}",
        topic=representative.topic,
        title=representative.title,
        summary=representative.summary,
        published_at=max(item.published_at for item in cluster),
        source_ids=list(dict.fromkeys(item.source_id for item in ordered)),
        source_names=list(dict.fromkeys(item.source_name for item in ordered)),
        source_types=list(dict.fromkeys(item.source_type for item in ordered)),
        publisher_ids=list(
            dict.fromkeys(item.publisher_id or item.source_id for item in ordered)
        ),
        source_urls=list(dict.fromkeys(item.url for item in ordered)),
        allow_article_fetch=representative.allow_article_fetch,
        allowed_article_hosts=representative.allowed_article_hosts,
        score=score,
    )


def _topic_limits(total: int) -> Dict[str, int]:
    limits = {
        topic: max(1, round(total * share))
        for topic, share in TOPIC_SHARES.items()
    }
    while sum(limits.values()) > total:
        largest = max(limits, key=lambda topic: limits[topic] - total * TOPIC_SHARES[topic])
        if limits[largest] > 1:
            limits[largest] -= 1
        else:
            break
    while sum(limits.values()) < total:
        topic = max(
            limits,
            key=lambda item: total * TOPIC_SHARES[item] - limits[item],
        )
        limits[topic] += 1
    return limits


def select_stories(
    articles: Iterable[Article],
    sources: Iterable[NewsSource],
    now: datetime,
    target_count: int = 12,
    minimum_count: int = 6,
    maximum_per_source: int = 2,
) -> List[Story]:
    source_weights = {source.id: source.weight for source in sources}
    candidates = sorted(
        (
            _cluster_story(cluster, source_weights, now)
            for cluster in cluster_articles(articles)
        ),
        key=lambda story: story.score,
        reverse=True,
    )
    limits = _topic_limits(target_count)
    topic_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    selected: List[Story] = []

    for story in candidates:
        if len(selected) >= target_count:
            break
        if topic_counts[story.topic] >= limits.get(story.topic, 1):
            continue
        primary_publisher = story.publisher_ids[0]
        if source_counts[primary_publisher] >= maximum_per_source:
            continue
        selected.append(story)
        topic_counts[story.topic] += 1
        source_counts[primary_publisher] += 1

    if len(selected) < target_count:
        for story in candidates:
            if len(selected) >= target_count:
                break
            if story in selected:
                continue
            primary_publisher = story.publisher_ids[0]
            if source_counts[primary_publisher] >= maximum_per_source:
                continue
            selected.append(story)
            source_counts[primary_publisher] += 1

    if len(selected) < minimum_count:
        raise MorgonkollError(
            f"Only {len(selected)} sufficiently recent, diverse stories were available; "
            f"at least {minimum_count} are required"
        )
    return selected
