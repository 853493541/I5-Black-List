"""Shared records. No UI and no OCR imports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Entry:
    name: str
    note: str = ""
    match_from_prefix: bool = False
    added_at: str = ""


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    box: tuple[float, float, float, float]
