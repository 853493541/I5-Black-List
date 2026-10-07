"""Shared records. No UI and no OCR imports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Entry:
    """One blacklist row: when it was added, the name, tags, and a written reason."""

    name: str
    reason: str = ""
    tags: tuple[str, ...] = ()
    match_from_prefix: bool = False
    added_at: str = ""


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    box: tuple[float, float, float, float]
