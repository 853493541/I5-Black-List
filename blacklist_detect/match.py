"""Blacklist comparison. Names are not corrected against a dictionary."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from blacklist_detect.model import Entry

MIN_PREFIX_CHARS = 4

_ELLIPSIS_RE = re.compile(r"(?:…|⋯|\.{2,}|·{2,}|。{2,})+$")
_SINGLE_DOT_RE = re.compile(r"[.。·]$")
_COUNTDOWN_RE = re.compile(r"^倒计时[:：]?\d+秒$")


def normalize_text(raw: str) -> str:
    """NFKC, drop whitespace. Full-width Latin becomes half-width. Case is kept."""
    text = unicodedata.normalize("NFKC", raw or "")
    text = text.replace("\u3000", "")
    return re.sub(r"\s+", "", text)


def split_ellipsis(raw: str) -> tuple[str, bool]:
    """Return the visible text and whether a trailing ellipsis was removed."""
    text = normalize_text(raw)
    truncated = False
    while _ELLIPSIS_RE.search(text):
        text = _ELLIPSIS_RE.sub("", text)
        truncated = True
    # This lobby's ellipsis is sometimes read as a single dot.
    if _SINGLE_DOT_RE.search(text):
        text = _SINGLE_DOT_RE.sub("", text)
        truncated = True
    return text, truncated


def with_game_ellipsis(visible: str, truncated: bool) -> str:
    """Keep the cutoff the lobby prints. Matching still uses the letters in front of it."""
    if truncated and visible and not visible.endswith("..."):
        return f"{visible}..."
    return visible


def strip_noise(text: str) -> str:
    """Drop punctuation and symbols. A backtick in the middle of a name is not part of it."""
    text = normalize_text(text)
    kept = [ch for ch in text if unicodedata.category(ch)[:1] in ("L", "N")]
    return "".join(kept)


@lru_cache(maxsize=32768)
def fold(text: str) -> str:
    """Comparison form. Latin letters compare case-insensitively. Chinese is unchanged.

    Pure, so its answers are kept: a long list folds the same names on every check.
    """
    return strip_noise(text).casefold()


def listed_tail(read: str, listed: str) -> str | None:
    """What the list adds after a name the game cut short: 破轮蜡像 + 金婚99.

    "" when the two are the same name, None when they differ in more than the cut,
    such as 破轮蜡像金婚88 read against 破轮蜡像金婚99.
    """
    if fold(read) == fold(listed):
        return ""
    cut = len(read)
    if len(listed) > cut and fold(listed[:cut]) == fold(read):
        return listed[cut:]
    return None


def clean_stored_name(raw: str) -> str:
    """Name as saved. A trailing ellipsis or a stray mark is not part of the name."""
    text, _truncated = split_ellipsis(raw)
    return strip_noise(text)


@lru_cache(maxsize=32768)
def is_lobby_chrome(text: str) -> bool:
    """Lobby status, not a player name. 准备就绪 is one of these lines."""
    folded = normalize_text(text)
    if not folded:
        return False
    if folded.startswith("准备就绪"):
        return True
    if "准备案件还原" in folded:
        return True
    if folded == "推演成功":
        return True
    if "模仿者狂欢" in folded and "12人" in folded:
        return True
    if _COUNTDOWN_RE.fullmatch(folded):
        return True
    return False


@dataclass(frozen=True)
class NameLabel:
    raw: str
    visible: str
    truncated: bool
    unclear: bool = False


@dataclass(frozen=True)
class NameMatch:
    entry: Entry
    visible: str
    truncated: bool
    kind: str


def match_label(label: NameLabel, entries: list[Entry]) -> list[NameMatch]:
    """Match the first four characters. A cut-off name is the usual case.

    A name shorter than four characters matches only when the whole name is the same.
    The middle of a name never matches. Stray marks are already gone from fold().
    """
    if label.unclear or not label.visible or is_lobby_chrome(label.raw) or is_lobby_chrome(label.visible):
        return []
    folded_visible = fold(label.visible)
    if not folded_visible:
        return []
    hits: list[NameMatch] = []
    head = folded_visible[:MIN_PREFIX_CHARS]
    for entry in entries:
        folded_entry = fold(entry.name)
        if not folded_entry or is_lobby_chrome(entry.name):
            continue
        same = folded_visible == folded_entry
        if same:
            hits.append(NameMatch(entry, label.visible, label.truncated, "exact"))
            continue
        if len(folded_visible) >= MIN_PREFIX_CHARS and len(folded_entry) >= MIN_PREFIX_CHARS:
            if folded_entry.startswith(head):
                hits.append(NameMatch(entry, label.visible, True, "prefix"))
    return hits


def last_seen(entries: list[Entry], scans: list[dict]) -> tuple[dict[int, str], dict[int, int]]:
    """When each listed name was last in a record, and how many listed names each record held.

    Records are newest first, so the first record a name is found in is its latest. A seat can
    only match a name that starts with the same four folded characters (or, for a short name,
    is the same); grouping by that leaves match_label, which still decides, a handful to check.
    """
    found: dict[int, str] = {}
    hits: dict[int, int] = {}
    by_id = {id(entry): index for index, entry in enumerate(entries)}
    groups: dict[str, list[Entry]] = {}
    for entry in entries:
        folded = fold(entry.name)
        if folded:
            groups.setdefault(folded[:MIN_PREFIX_CHARS], []).append(entry)
    for number, scan in enumerate(scans):
        for seat in scan.get("names", []):
            if seat.get("unclear") or not str(seat.get("name") or ""):
                continue
            shown = str(seat["name"])
            candidates = groups.get(fold(shown)[:MIN_PREFIX_CHARS], [])
            if not candidates:
                continue
            matches = match_label(NameLabel(raw=shown, visible=shown, truncated=False), candidates)
            if matches:
                hits[number] = hits.get(number, 0) + 1
            for match in matches:
                index = by_id.get(id(match.entry))
                if index is not None and index not in found:
                    found[index] = str(scan.get("at", ""))
    return found, hits


def seat_number(index: int) -> int:
    """Top row, left to right, is 1–6. Bottom row, left to right, is 7–12."""
    return index + 1


def format_hit(index: int, read_text: str, truncated: bool, entry_name: str, note: str) -> str:
    del index, truncated
    line = f"画面是「{read_text}」，黑名单里有「{entry_name}」"
    if note.strip():
        line += f"。{note.strip()}"
    return line
