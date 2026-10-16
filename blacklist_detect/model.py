"""Shared records. No UI and no OCR imports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenes:
    """The 场景 a 嘉宾 or a 组合 is greeted with, one of three: keys ticked, one of them at random each
    time, never the one just played twice in a row; random (随机), any scene, ticks kept alongside but
    random wins; or nothing asked for (不放), none for them and the next in line decides."""

    keys: tuple[str, ...] = ()
    random: bool = False

    @property
    def off(self) -> bool:
        """不放: neither random nor any scene ticked."""
        return not self.random and not self.keys


# 随机: any scene.
ANY_SCENE = Scenes(random=True)


@dataclass
class Entry:
    """One listed player: when it was added, the name, tags, and a written reason.

    A 嘉宾 entry has no tags; its nickname, when set, is what a lobby shows for it, and its scenes the
    嘉宾场景 that greet it (none ticked: any scene).
    """

    name: str
    reason: str = ""
    tags: tuple[str, ...] = ()
    added_at: str = ""
    nickname: str = ""
    scenes: Scenes = ANY_SCENE

    def shown(self) -> str:
        """What a lobby shows for this player: the nickname, or the full name."""
        return self.nickname or self.name


@dataclass(frozen=True)
class Combo:
    """嘉宾 who, all in one lobby, are greeted by scenes of their own: their names (two or more, as
    on 嘉宾) and their scenes."""

    names: tuple[str, ...]
    scenes: Scenes = ANY_SCENE


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    box: tuple[float, float, float, float]
