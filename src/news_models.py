"""Typed records for the current-news pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class NewsSource:
    id: str
    name: str
    feed_url: str
    language: str
    topic: str
    weight: float
    homepage: str
    source_type: str = "editorial"
    allow_article_fetch: bool = True
    exclude_title_patterns: Tuple[str, ...] = ()
    publisher_id: str = ""
    allowed_article_hosts: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Article:
    id: str
    source_id: str
    source_name: str
    topic: str
    title: str
    summary: str
    url: str
    published_at: datetime
    fetched_at: datetime
    source_type: str = "editorial"
    allow_article_fetch: bool = True
    publisher_id: str = ""
    allowed_article_hosts: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["published_at"] = self.published_at.isoformat()
        payload["fetched_at"] = self.fetched_at.isoformat()
        return payload


@dataclass
class Story:
    id: str
    topic: str
    title: str
    summary: str
    published_at: datetime
    source_ids: List[str] = field(default_factory=list)
    source_names: List[str] = field(default_factory=list)
    source_types: List[str] = field(default_factory=list)
    publisher_ids: List[str] = field(default_factory=list)
    source_urls: List[str] = field(default_factory=list)
    source_material: List[str] = field(default_factory=list, repr=False)
    allow_article_fetch: bool = True
    allowed_article_hosts: Tuple[str, ...] = ()
    score: float = 0.0

    def to_dict(self, include_material: bool = False) -> Dict[str, Any]:
        payload = asdict(self)
        payload["published_at"] = self.published_at.isoformat()
        if not include_material:
            payload.pop("source_material", None)
        return payload


@dataclass(frozen=True)
class ScriptSection:
    heading: str
    story_ids: List[str]
    body: str


@dataclass(frozen=True)
class GeneratedScript:
    title: str
    intro: str
    sections: List[ScriptSection]
    outro: str
    generator: str

    @property
    def text(self) -> str:
        parts = [f"# {self.title}", "", self.intro.strip()]
        for section in self.sections:
            parts.extend(["", f"# {section.heading}", "", section.body.strip()])
        parts.extend(["", "# Avslutning", "", self.outro.strip(), ""])
        return "\n".join(parts)
