"""Semantic text chunking for stable long-form synthesis."""

from __future__ import annotations

import re
from typing import Iterable, List

from .models import NarrationChunk


_ABBREVIATIONS = ("t.ex.", "bl.a.", "d.v.s.", "ca.", "kl.", "dr.", "prof.", "nr.")
_DOT_MARKER = "\u2024"


def _protect_abbreviations(text: str) -> str:
    protected = text
    for abbreviation in _ABBREVIATIONS:
        pattern = re.compile(re.escape(abbreviation), re.IGNORECASE)
        protected = pattern.sub(lambda match: match.group(0).replace(".", _DOT_MARKER), protected)
    return protected


def _sentences(paragraph: str) -> List[str]:
    protected = _protect_abbreviations(paragraph)
    parts = re.split(r'(?<=[.!?])\s+(?=[A-ZÅÄÖ0-9"“])', protected)
    return [part.replace(_DOT_MARKER, ".").strip() for part in parts if part.strip()]


def _split_long_unit(text: str, max_chars: int) -> List[str]:
    if len(text) <= max_chars:
        return [text]

    clauses = [
        part.strip()
        for part in re.split(r"(?<=[,;:])\s+|(?=\s[–—-]\s)", text)
        if part.strip()
    ]
    if len(clauses) == 1:
        clauses = text.split()

    pieces: List[str] = []
    current = ""
    for clause in clauses:
        proposed = f"{current} {clause}".strip()
        if current and len(proposed) > max_chars:
            pieces.append(current)
            current = clause
        else:
            current = proposed
        while len(current) > max_chars:
            split_at = current.rfind(" ", 0, max_chars + 1)
            split_at = split_at if split_at > 0 else max_chars
            pieces.append(current[:split_at].strip())
            current = current[split_at:].strip()
    if current:
        pieces.append(current)
    return pieces


def _pack(units: Iterable[str], max_chars: int) -> List[str]:
    packed: List[str] = []
    current = ""
    for unit in units:
        for piece in _split_long_unit(unit, max_chars):
            proposed = f"{current} {piece}".strip()
            if current and len(proposed) > max_chars:
                packed.append(current)
                current = piece
            else:
                current = proposed
    if current:
        packed.append(current)
    return packed


def semantic_chunks(
    text: str,
    max_chars: int = 280,
    sentence_pause_ms: int = 220,
    paragraph_pause_ms: int = 430,
    section_pause_ms: int = 620,
) -> List[NarrationChunk]:
    if max_chars < 80:
        raise ValueError("max_chars must be at least 80")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("Narration text is empty")

    paragraph_blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    chunks: List[NarrationChunk] = []
    for block in paragraph_blocks:
        raw_lines = [line.strip() for line in block.splitlines() if line.strip()]
        is_heading = len(raw_lines) == 1 and raw_lines[0].startswith("#")
        paragraph = " ".join(raw_lines)
        paragraph = re.sub(r"^#{1,6}\s*", "", paragraph)
        pieces = _pack(_sentences(paragraph), max_chars=max_chars)
        for piece_index, piece in enumerate(pieces):
            is_last = piece_index == len(pieces) - 1
            pause = paragraph_pause_ms if is_last else sentence_pause_ms
            if is_heading:
                pause = section_pause_ms
            chunks.append(
                NarrationChunk(index=len(chunks), text=piece, pause_after_ms=pause)
            )
    return chunks

