"""批量导入: read a pasted list into people, and say what each one does to the list.

Friends send lists as 名字（原因）, one per line, often copied out of a notes app:

    挖野菜养你吖（纯粹的傻逼）
    小小丑不会输，少主薇（狼能赢的送双排顾问）
    翻箱震慑是北城（讲了行为狼、轨迹狼、身份撞了，还给狼弃
    票，弱智来着）

The rules, line by line:

* 名字（原因）. A 原因 may run onto the next lines until its ）. The 标签 written in it
  are picked out; the 原因 itself is kept whole.
* Several names in front of one （原因） share it.
* A line without brackets is names, or one name with 标签 and 原因 after it:
  名字，标签，原因 · 名字：原因 · 名字-原因 · 名字 原因. A word that is a 标签, or holds one,
  starts the part after the name; until then each word is another name.
* A list number or bullet in front is not part of a name: 1. 1、 ① - •.
* A line with a date or a time is a chat's 谁 and 何时, not a player: its names start unchecked.
* A list copied with 复制名单 keeps its own 标签, even ones this list has not seen.

Nothing is dropped without a word. A line that does not look like a name, such as a
title, is kept but left unchecked. A name already on the list, or the start of one
(the game cuts names short), is merged into it instead of added twice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from blacklist_detect.match import clean_stored_name, fold
from blacklist_detect.model import Entry
from blacklist_detect.storage import TAGS, is_shared, merge_reason, order_tags, parse_shared, tags_and_reason

# Longer than this is not a player name: the game's names are short.
NAME_MAX = 8
# A name this long or longer that starts another is the same person, cut short by the game.
_SAME_PREFIX = 4
_MAX_NAME = 64
_MAX_NOTE = 200

NEW = "new"
MERGE = "merge"
SAME = "same"
ODD = "odd"
# On the other list (黑名单 when importing into 心动, and the other way round).
ELSEWHERE = "elsewhere"

_OPEN = "（"
_CLOSE = "）"
_BRACKETS = str.maketrans({"(": _OPEN, ")": _CLOSE, "【": _OPEN, "】": _CLOSE})
# 1. 1、 1) ① - • in front of a line, or a number and a space.
_LIST_MARK = re.compile(r"^\s*(?:\d{1,3}\s*[.、．)）:：]\s*|[①-⑳]\s*[.、．)）:：]?\s*|\d{1,3}\s+(?=\S)|[-•·*●▪]\s*)")
# A date or a clock time: a line copied from a chat with who said it and when.
_STAMP = re.compile(r"\d{4}\s*[/.\-年]\s*\d{1,2}\s*[/.\-月]\s*\d{1,2}日?|\d{1,2}:\d{2}(?::\d{2})?")
_NAME_SPLIT = re.compile(r"[，,、；;/|\s]+")
# 名字：原因 and 名字-原因.
_NAME_NOTE = re.compile(r"^\s*([^:：\-—－~～\s，,、；;/|]+)\s*[:：\-—－~～]+\s*(.+)$")
# 其他：说明 in an old list is only the 原因.
_OTHER = re.compile(r"^其他[:：]?")


@dataclass
class ImportRow:
    """One person from a paste, and what importing them would do."""

    name: str
    tags: tuple[str, ...] = ()
    reason: str = ""
    status: str = NEW
    # The entry a MERGE or SAME row matches.
    target: int = -1
    checked: bool = True
    # Names the paste gave this person more than once, kept for the preview.
    also: list[str] = field(default_factory=list)


def _clean(name: str) -> str:
    return clean_stored_name(name)[:_MAX_NAME]


def _looks_odd(name: str) -> bool:
    return len(name) > NAME_MAX or name.isdigit()


def _pieces(text: str) -> list[tuple[str, str | None, bool]]:
    """(names, 原因 or None) in the order the paste has them.

    A 原因 left open runs on only when a later line closes it before any new （ opens;
    otherwise it ends with its own line, and the lines after it are read as their own.
    """
    lines = text.translate(_BRACKETS).splitlines()
    pieces: list[tuple[str, str | None, bool]] = []
    index = 0
    while index < len(lines):
        rest = _LIST_MARK.sub("", lines[index], count=1)
        header = bool(_STAMP.search(rest))
        if header:
            rest = _STAMP.sub(" ", rest)
        index += 1
        while rest.strip():
            opening = rest.find(_OPEN)
            if opening < 0:
                pieces.append((rest, None, header))
                break
            names = rest[:opening]
            closing = rest.find(_CLOSE, opening + 1)
            if closing >= 0:
                note = rest[opening + 1 : closing]
                rest = rest[closing + 1 :]
            else:
                note = rest[opening + 1 :]
                rest = ""
                # Look ahead for the ） that closes it.
                ahead = index
                while ahead < len(lines) and _OPEN not in lines[ahead] and _CLOSE not in lines[ahead]:
                    ahead += 1
                line = lines[ahead] if ahead < len(lines) else ""
                close_at = line.find(_CLOSE)
                open_at = line.find(_OPEN)
                if close_at >= 0 and (open_at < 0 or close_at < open_at):
                    note += "".join(lines[index:ahead]) + line[:close_at]
                    rest = line[close_at + 1 :]
                    index = ahead + 1
            if not names.strip(_CLOSE + " \t") and pieces and pieces[-1][1] is not None:
                # 名字（原因）（还有） is one person with a longer 原因.
                last_names, last_note, last_header = pieces[-1]
                pieces[-1] = (last_names, f"{last_note}，{note}", last_header)
                continue
            pieces.append((names, note, header))
    return pieces


def _read_plain(text: str, catalog: tuple[str, ...]) -> list[tuple[str, tuple[str, ...], str]]:
    """A line without brackets: names, or one name with 标签 and 原因 after it."""
    matched = _NAME_NOTE.match(text)
    if matched and _clean(matched.group(1)):
        tags, reason = tags_and_reason(matched.group(2), catalog)
        return [(_clean(matched.group(1)), tags, reason)]
    words = [word for word in _NAME_SPLIT.split(text.strip(_CLOSE)) if word]
    names: list[str] = []
    tags: list[str] = []
    notes: list[str] = []
    for word in words:
        detail = bool(tags or notes)
        if word in catalog:
            if word not in tags:
                tags.append(word)
        elif names and (detail or ":" in word or "：" in word or any(tag in word for tag in catalog) or len(_clean(word)) > NAME_MAX):
            note = _OTHER.sub("", word).strip(":： ")
            if note:
                notes.append(note)
        else:
            names.append(word)
    reason = "，".join(notes)
    found, _kept = tags_and_reason(reason, catalog)
    picked = order_tags(list(dict.fromkeys([*tags, *found])), catalog)
    return [(_clean(name), picked, reason[:_MAX_NOTE]) for name in names if _clean(name)]


def _read(text: str, catalog: tuple[str, ...]) -> list[tuple[str, tuple[str, ...], str, bool]]:
    """(name, 标签, 原因, from a chat header line) for every person, in the paste's order."""
    if is_shared(text):
        return [(name, tags, reason, False) for name, tags, reason in parse_shared(text)]
    people: list[tuple[str, tuple[str, ...], str, bool]] = []
    for names, note, header in _pieces(text or ""):
        if note is None:
            people.extend((name, tags, reason, header) for name, tags, reason in _read_plain(names, catalog))
            continue
        tags, reason = tags_and_reason(note, catalog)
        for name in _NAME_SPLIT.split(names.strip(" :：-—－~～\t" + _CLOSE)):
            if _clean(name):
                people.append((_clean(name), tags, reason, header))
    return people


def read_paste(text: str, catalog: tuple[str, ...] = TAGS) -> list[tuple[str, tuple[str, ...], str]]:
    """Every person in a paste, as (name, 标签, 原因), in the paste's order."""
    return [(name, tags, reason) for name, tags, reason, _header in _read(text, catalog)]


def _find(name: str, entries: list[Entry]) -> int:
    """The entry this name is: the same name, or one of the two is the other cut short."""
    key = fold(name)
    for index, entry in enumerate(entries):
        if fold(entry.name) == key:
            return index
    for index, entry in enumerate(entries):
        other = fold(entry.name)
        short, long = sorted((key, other), key=len)
        if len(short) >= _SAME_PREFIX and long.startswith(short):
            return index
    return -1


def _adds_to(row: ImportRow, entry: Entry) -> bool:
    longer = len(fold(row.name)) > len(fold(entry.name))
    return bool(set(row.tags) - set(entry.tags)) or merge_reason(entry.reason, row.reason) != entry.reason or longer


def plan_import(
    text: str, entries: list[Entry], catalog: tuple[str, ...] = TAGS, elsewhere: list[Entry] = ()
) -> list[ImportRow]:
    """What 导入 would do with this paste: one row per person, checked if it changes the list.

    A name on the other list (elsewhere) is shown but unchecked: a player is on one list.
    """
    rows: list[ImportRow] = []
    by_key: dict[str, ImportRow] = {}
    headers: set[str] = set()
    for name, tags, reason, header in _read(text, catalog):
        key = fold(name)
        if not key:
            continue
        twin = by_key.get(key)
        if twin is not None:
            # The same person twice in one paste: one row with both 原因.
            twin.tags = order_tags(list(dict.fromkeys([*twin.tags, *tags])), catalog)
            twin.reason = merge_reason(twin.reason, reason)
            continue
        row = ImportRow(name, tuple(tags), reason[:_MAX_NOTE])
        by_key[key] = row
        rows.append(row)
        if header:
            headers.add(key)
    for row in rows:
        if _looks_odd(row.name) or fold(row.name) in headers:
            row.status, row.checked = ODD, False
            continue
        if any(fold(other.name) == fold(row.name) for other in elsewhere):
            row.status, row.checked = ELSEWHERE, False
            continue
        row.target = _find(row.name, entries)
        if row.target >= 0:
            changes = _adds_to(row, entries[row.target])
            row.status, row.checked = (MERGE, True) if changes else (SAME, False)
    return rows
