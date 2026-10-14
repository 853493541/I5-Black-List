"""Shared records. No UI and no OCR imports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Entry:
    """One listed player: when it was added, the name, tags, and a written reason.

    A 嘉宾 entry has no tags; its nickname, when set, is what a lobby shows for it, and its theme,
    when set, is the 嘉宾特效 scene that greets it ("" follows 嘉宾特效's own choice).
    """

    name: str
    reason: str = ""
    tags: tuple[str, ...] = ()
    added_at: str = ""
    nickname: str = ""
    theme: str = ""

    def shown(self) -> str:
        """What a lobby shows for this player: the nickname, or the full name."""
        return self.nickname or self.name


@dataclass(frozen=True)
class Combo:
    """嘉宾 who, all in one lobby, are greeted by a scene of their own: their names (two or more, as
    on 嘉宾) and the scene's key."""

    names: tuple[str, ...]
    theme: str


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    box: tuple[float, float, float, float]
