"""Fetch bounded article text from selected feed links, respecting robots.txt."""

from __future__ import annotations

import urllib.error
import urllib.request
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Iterable
from urllib.parse import urljoin, urlparse

import trafilatura

from .news_models import Story
from .network_safety import NO_REDIRECT_OPENER, validate_public_https_target


USER_AGENT = "Morgonkoll/0.1 (+https://github.com/marbodin/Morgonkoll)"
MAX_ARTICLE_BYTES = 2 * 1024 * 1024
MAX_EXTRACTED_CHARS = 6_000
BOILERPLATE_MARKERS = (
    "Så arbetar vi SVT:s nyheter",
    "KÖP ”Fighting optimists”",
)


def _robots_allows(
    url: str,
    allowed_hosts: Iterable[str],
    timeout_seconds: int = 10,
) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    validate_public_https_target(robots_url, allowed_hosts)
    request = urllib.request.Request(
        robots_url,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with NO_REDIRECT_OPENER.open(request, timeout=timeout_seconds) as response:
            lines = response.read(512_000).decode("utf-8", errors="replace").splitlines()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return False
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(lines)
    return parser.can_fetch(USER_AGENT, url)


def _download_html(
    url: str,
    timeout_seconds: int,
    allowed_hosts: Iterable[str],
) -> str:
    current_url = url
    for _hop in range(5):
        validate_public_https_target(current_url, allowed_hosts)
        if not _robots_allows(current_url, allowed_hosts):
            raise RuntimeError(
                "robots.txt does not permit this fetch or could not be verified"
            )
        request = urllib.request.Request(
            current_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        try:
            response = NO_REDIRECT_OPENER.open(request, timeout=timeout_seconds)
        except urllib.error.HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                location = exc.headers.get("Location")
                if not location:
                    raise RuntimeError("article redirect has no Location") from exc
                current_url = urljoin(current_url, location)
                continue
            raise
        with response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise RuntimeError(f"article returned unsupported content type {content_type}")
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > MAX_ARTICLE_BYTES:
                raise RuntimeError("article response is too large")
            payload = response.read(MAX_ARTICLE_BYTES + 1)
        break
    else:
        raise RuntimeError("article exceeded the redirect limit")
    if len(payload) > MAX_ARTICLE_BYTES:
        raise RuntimeError("article exceeded the byte limit")
    return payload.decode("utf-8", errors="replace")


def extract_article_text(
    url: str,
    allowed_hosts: Iterable[str],
    downloader: Callable[[str, int, Iterable[str]], str] = _download_html,
) -> str:
    html = downloader(url, 20, allowed_hosts)
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        include_images=False,
        include_links=False,
        favor_precision=True,
        output_format="txt",
    )
    if not text:
        raise RuntimeError("no article text could be extracted")
    cleaned = " ".join(text.split())
    for marker in BOILERPLATE_MARKERS:
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0].rstrip()
    if not cleaned:
        raise RuntimeError("only publisher boilerplate remained after extraction")
    return cleaned[:MAX_EXTRACTED_CHARS]


def enrich_stories(
    stories: Iterable[Story],
    extractor: Callable[[str, Iterable[str]], str] = extract_article_text,
    max_workers: int = 6,
) -> Dict[str, str]:
    story_list = list(stories)
    errors: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(story_list))) as executor:
        futures = {
            executor.submit(
                extractor,
                story.source_urls[0],
                story.allowed_article_hosts,
            ): story
            for story in story_list
            if story.source_urls and story.allow_article_fetch
        }
        for future in as_completed(futures):
            story = futures[future]
            try:
                extracted = future.result()
                if extracted not in story.source_material:
                    story.source_material.append(extracted)
            except Exception as exc:
                errors[story.id] = str(exc)
    for story in story_list:
        if not story.source_material:
            story.source_material = [story.summary]
    return errors
