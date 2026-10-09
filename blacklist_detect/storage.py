"""Local blacklist and settings. Nothing is uploaded."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from blacklist_detect.model import Entry
from blacklist_detect.paths import app_dir
from blacklist_detect.match import MIN_PREFIX_CHARS, clean_stored_name, fold

_MAX_NAME = 64
_MAX_NOTE = 200
_MAX_SCANS = 40
# A later check of this 12-player lobby still misreads a few seats.
# Eight shared names is the same match, so the time is updated.
_SAME_MATCH_COUNT = 8
TAGS = ("炸房", "贴脸", "挂机", "场外", "不尊重底牌")
_MAX_TAG = 12
_MAX_CUSTOM_TAGS = 24


def clean_tag(raw: str) -> str:
    """A tag is a short label. Commas would break the line format, so they are removed."""
    text = "".join(ch for ch in str(raw).strip() if ch not in ",，、:： \t\r\n")
    if not text or text == "其他":
        return ""
    return text[:_MAX_TAG]


def order_tags(tags: list[str] | tuple[str, ...], catalog: tuple[str, ...] = TAGS) -> tuple[str, ...]:
    """Built-in tags first, then the user's own tags, in catalog order."""
    chosen = [tag for tag in catalog if tag in tags]
    chosen.extend(tag for tag in tags if tag not in chosen)
    return tuple(chosen)


def coerce_tags(tags: tuple[str, ...] | list[str], reason: str) -> tuple[tuple[str, ...], str]:
    """Keep each tag the user stored. 其他 is not a tag. The written reason stays text."""
    picked: list[str] = []
    for raw in tags or ():
        tag = clean_tag(str(raw))
        if tag and tag not in picked:
            picked.append(tag)
    return order_tags(picked), (reason or "").strip()[:_MAX_NOTE]


def tag_text(entry: Entry) -> str:
    return "、".join(order_tags(entry.tags))


def describe_entry(entry: Entry) -> str:
    """Tags, then the written reason, for a warning line."""
    tags = tag_text(entry)
    reason = entry.reason.strip()
    if tags and reason:
        return f"{tags}。原因：{reason}"
    if reason:
        return f"原因：{reason}"
    return tags


def format_blacklist(entries: list[Entry]) -> str:
    """One line per player: 名字，炸房，贴脸，挂机，原因."""
    lines: list[str] = []
    for entry in entries:
        bits = [entry.name]
        bits.extend(order_tags(entry.tags))
        if entry.reason.strip():
            bits.append(entry.reason.strip())
        lines.append("，".join(bits))
    return "\n".join(lines)


# First line of a list copied with 分享. 批量添加 reads such a paste with parse_shared.
SHARE_MARK = "#黑名单检测 名单"
_REASON_MARK = "原因："


def share_text(entries: list[Entry]) -> str:
    """名字，炸房，贴脸，原因：说明 — one line per player, under SHARE_MARK.

    The reason is marked, so a friend's own tags are kept as tags even when the
    receiving list has never seen them.
    """
    lines = [f"{SHARE_MARK} {len(entries)}人"]
    for entry in entries:
        bits = [entry.name, *order_tags(entry.tags)]
        reason = " ".join(entry.reason.split())
        if reason:
            bits.append(_REASON_MARK + reason)
        lines.append("，".join(bits))
    return "\n".join(lines)


def is_shared(text: str) -> bool:
    return any(line.strip().startswith(SHARE_MARK) for line in (text or "").splitlines())


def parse_shared(text: str) -> list[tuple[str, tuple[str, ...], str]]:
    """Read a 分享 paste. Every part before 原因： is a tag."""
    rows: list[tuple[str, tuple[str, ...], str]] = []
    seen: set[str] = set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in re.split(r"[,，]", line)]
        name = clean_stored_name(parts[0])[:_MAX_NAME]
        key = fold(name)
        if not key or key in seen:
            continue
        seen.add(key)
        tags: list[str] = []
        reason = ""
        for index, part in enumerate(parts[1:], start=1):
            if part.startswith(_REASON_MARK):
                reason = "，".join([part[len(_REASON_MARK):], *parts[index + 1 :]]).strip()
                break
            tag = clean_tag(part)
            if tag and tag not in tags:
                tags.append(tag)
        rows.append((name, tuple(tags), reason[:_MAX_NOTE]))
    return rows


def names_from_block(text: str) -> list[str]:
    """Names from one paste. Spaces, tabs, and new lines separate them."""
    found: list[str] = []
    seen: set[str] = set()
    for part in text.split():
        cleaned = clean_stored_name(part)[:_MAX_NAME]
        key = fold(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        found.append(cleaned)
    return found


def tags_and_reason(text: str, catalog: tuple[str, ...] = TAGS) -> tuple[tuple[str, ...], str]:
    """Pull known tags out of an explanation. The rest stays the reason."""
    raw = "".join(part.strip() for part in (text or "").splitlines()).strip()
    if not raw:
        return (), ""
    found: list[str] = []
    for tag in sorted(catalog, key=len, reverse=True):
        if tag and tag in raw and tag not in found:
            found.append(tag)
    ordered = order_tags(found, catalog)
    stripped = raw
    for tag in ordered:
        stripped = stripped.replace(tag, "")
    stripped = re.sub(r"[,，、:：\s]+", "", stripped)
    if not stripped:
        return ordered, ""
    return ordered, raw[:_MAX_NOTE]


def _split_names(prefix: str) -> list[str]:
    """A comma in the friend's note is two names, not one name that contains a comma."""
    line = prefix.strip().splitlines()[-1].strip() if prefix.strip() else ""
    names: list[str] = []
    seen: set[str] = set()
    for chunk in re.split(r"[,，]", line):
        cleaned = clean_stored_name(chunk)[:_MAX_NAME]
        key = fold(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        names.append(cleaned)
    return names


def annotated_from_block(text: str, catalog: tuple[str, ...] = TAGS) -> list[tuple[str, tuple[str, ...], str]] | None:
    """Each 名字（说明） is one person. Commas in front of the note are more names.

    A line break inside the note is still that note. Returns None when the paste
    is not this form, so a space-separated list still works.
    """
    normalized = text.replace("(", "（").replace(")", "）")
    if "（" not in normalized:
        return None
    found: list[tuple[str, tuple[str, ...], str]] = []
    seen: set[str] = set()
    for match in re.finditer(r"([^（）]*)（(.*?)）", normalized, re.DOTALL):
        tags, reason = tags_and_reason(match.group(2), catalog)
        for name in _split_names(match.group(1)):
            key = fold(name)
            if key in seen:
                continue
            seen.add(key)
            found.append((name, tags, reason))
    return found


def parse_blacklist(text: str, catalog: tuple[str, ...] = TAGS) -> list[tuple[str, tuple[str, ...], str]]:
    """One line is 名字，炸房，贴脸，挂机，原因. 其他:说明 is only the reason text."""
    parsed: list[tuple[str, tuple[str, ...], str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        raw_parts = re.split(r"[,，]", line)
        if not raw_parts or not raw_parts[0].strip():
            continue
        parts = [part.strip() for part in raw_parts if part.strip()]
        name = clean_stored_name(parts[0])[:_MAX_NAME]
        tags: list[str] = []
        reason_bits: list[str] = []
        for part in parts[1:]:
            if part.startswith("其他"):
                detail = re.sub(r"^其他[:：]?", "", part).strip()
                if detail:
                    reason_bits.append(detail)
                continue
            if part in catalog and part not in tags:
                tags.append(part)
                continue
            reason_bits.append(part)
        if not name:
            continue
        parsed.append((name, order_tags(tags, catalog), "，".join(reason_bits)[:_MAX_NOTE]))
    return parsed


def _stored_seat(item: dict) -> dict:
    return {
        "seat": int(item.get("seat", 0)),
        "name": str(item.get("name") or "")[:_MAX_NAME],
        "unclear": bool(item.get("unclear")),
    }


def _seat_clear(item: dict) -> bool:
    return not item.get("unclear") and bool(str(item.get("name") or "").strip())


def _fill_unclear(existing: list[dict], incoming: list[dict]) -> list[dict] | None:
    """Fill blank seats from a later read of the same lobby. Keep the first clear name."""
    if not any(not _seat_clear(item) for item in existing):
        return None
    old = {int(item.get("seat", 0)): item for item in existing}
    new = {int(item.get("seat", 0)): item for item in incoming}
    for seat, prev in old.items():
        nxt = new.get(seat)
        if not _seat_clear(prev) or nxt is None or not _seat_clear(nxt):
            continue
        left = fold(clean_stored_name(str(prev.get("name") or "")))
        right = fold(clean_stored_name(str(nxt.get("name") or "")))
        if left and right and not _same_person(left, right):
            return None
    merged: list[dict] = []
    changed = False
    for seat in sorted(set(old) | set(new)):
        prev = old.get(seat)
        nxt = new.get(seat)
        if prev is not None and _seat_clear(prev):
            merged.append(prev)
            continue
        if nxt is not None and _seat_clear(nxt):
            merged.append(_stored_seat(nxt))
            changed = True
            continue
        if prev is not None:
            merged.append(prev)
        elif nxt is not None:
            merged.append(_stored_seat(nxt))
    if not changed:
        return None
    return merged


def _readable_names(names: list[dict]) -> list[str]:
    members: list[str] = []
    for item in names:
        if item.get("unclear"):
            continue
        name = fold(clean_stored_name(str(item.get("name") or "")))
        if name:
            members.append(name)
    return members


def _same_person(left: str, right: str) -> bool:
    if left == right:
        return True
    short, long = (left, right) if len(left) <= len(right) else (right, left)
    return len(short) >= MIN_PREFIX_CHARS and long.startswith(short)


def _shared_names(left: list[str], right: list[str]) -> int:
    pool = list(right)
    shared = 0
    for name in left:
        exact = next((index for index, other in enumerate(pool) if other == name), None)
        if exact is not None:
            del pool[exact]
            shared += 1
            continue
        close = next((index for index, other in enumerate(pool) if _same_person(name, other)), None)
        if close is None:
            continue
        del pool[close]
        shared += 1
    return shared


def _same_clock_minute(stamp: str, now: datetime) -> bool:
    try:
        then = datetime.fromisoformat(str(stamp))
    except ValueError:
        return False
    if then.tzinfo is None:
        then = then.replace(tzinfo=now.tzinfo)
    then = then.astimezone(now.tzinfo)
    return (then.year, then.month, then.day, then.hour, then.minute) == (
        now.year,
        now.month,
        now.day,
        now.hour,
        now.minute,
    )


def _is_same_recording(left: list[dict], right: list[dict]) -> bool:
    """Same lobby at another time, even when a few seats were read differently."""
    seen = _readable_names(left)
    other = _readable_names(right)
    if not seen or not other:
        return False
    if _shared_names(seen, other) >= _SAME_MATCH_COUNT:
        return True
    return sorted(seen) == sorted(other)


def _collapse(scans: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for scan in scans:
        names = scan.get("names", [])
        if any(_is_same_recording(names, earlier.get("names", [])) for earlier in kept):
            continue
        kept.append(scan)
    return kept


def _panel_pos(value) -> tuple[int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return (int(value[0]), int(value[1]))
    except (TypeError, ValueError):
        return None


def _window_size(value) -> tuple[int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        width, height = int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return (max(900, width), max(560, height))


# Name, tags, reason, last met. Tags fit about three short pills; the reason takes the spare width.
DEFAULT_COLUMN_WIDTHS = [200, 176, 340, 120]
DEFAULT_HOTKEY = "Alt+1"


def _column_widths(value) -> list[int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    widths: list[int] = []
    for item in value:
        try:
            width = int(item)
        except (TypeError, ValueError):
            return None
        if not 72 <= width <= 2000:
            return None
        widths.append(width)
    return widths


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


# One copy of the list per day it changed, so a wrong 清空 or a bad edit can be undone by hand.
_BACKUP_DAYS = 7


def _daily_backup(path: Path) -> None:
    """Copy the list as it was before today's first change. Keeps the last week of copies."""
    if not path.exists():
        return
    folder = path.parent / "backups"
    target = folder / f"{path.stem}-{datetime.now():%Y-%m-%d}{path.suffix}"
    if target.exists():
        return
    try:
        folder.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        for old in sorted(folder.glob(f"{path.stem}-*{path.suffix}"))[:-_BACKUP_DAYS]:
            old.unlink()
    except OSError:
        pass


def _set_aside(path: Path) -> Path:
    """Move an unreadable file out of the way under a new name. Earlier ones are never overwritten."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.stem}.unreadable-{stamp}{path.suffix}")
    try:
        path.replace(target)
    except OSError:
        return path
    return target


class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or app_dir()
        self.blacklist_path = self.root / "blacklist.json"
        self.settings_path = self.root / "settings.json"
        self.history_path = self.root / "history.json"
        self.entries: list[Entry] = []
        self.scans: list[dict] = []
        self.hotkey = DEFAULT_HOTKEY
        self.auto_capture = True
        self.save_debug_frames = False
        self.panel_pos: tuple[int, int] | None = None
        self.window_size: tuple[int, int] | None = None
        self.theme = "蓝色"
        self.player_name = ""
        self.custom_tags: list[str] = []
        self.hidden_tags: list[str] = []
        self.column_order: list[int] = [0, 1, 2, 3]
        self.column_widths: list[int] = list(DEFAULT_COLUMN_WIDTHS)
        self.names_hidden = False
        self.hit_sound = False
        self.load_warning = ""
        # No settings file yet: this PC has not opened the app before (or it was reset).
        self.first_run = not self.settings_path.exists()
        self.load()

    def _known_tags(self) -> list[str]:
        names = [tag for tag in TAGS if tag not in self.hidden_tags]
        for tag in self.custom_tags:
            if tag not in names:
                names.append(tag)
        return names

    def tag_catalog(self) -> tuple[str, ...]:
        return tuple(self._known_tags())

    def add_custom_tag(self, raw: str) -> bool:
        tag = clean_tag(raw)
        if not tag or tag in self.tag_catalog():
            return False
        if tag in TAGS:
            self.hidden_tags.remove(tag)
        elif len(self.custom_tags) >= _MAX_CUSTOM_TAGS:
            return False
        else:
            self.custom_tags.append(tag)
        return True

    def remove_custom_tag(self, raw: str) -> bool:
        """Drop a tag, including a default. Names that used it lose that tag."""
        tag = clean_tag(raw)
        if tag not in self.tag_catalog():
            return False
        if tag in TAGS:
            self.hidden_tags.append(tag)
        else:
            self.custom_tags.remove(tag)
        changed = False
        for entry in self.entries:
            if tag not in entry.tags:
                continue
            entry.tags = tuple(item for item in entry.tags if item != tag)
            changed = True
        self.save_settings()
        if changed:
            self.save_entries()
        return True

    def rename_tag(self, old_raw: str, new_raw: str) -> str:
        """Rename a tag on the list and on every name. Returns renamed, same, missing, empty, or taken."""
        old = clean_tag(old_raw)
        new = clean_tag(new_raw)
        if not old or old not in self.tag_catalog():
            return "missing"
        if not new:
            return "empty"
        if new == old:
            return "same"
        if new in self.tag_catalog():
            return "taken"
        if old in TAGS:
            self.hidden_tags.append(old)
        else:
            self.custom_tags.remove(old)
        if new in TAGS:
            self.hidden_tags.remove(new)
        elif len(self.custom_tags) >= _MAX_CUSTOM_TAGS:
            if old in TAGS:
                self.hidden_tags.remove(old)
            else:
                self.custom_tags.append(old)
            return "taken"
        else:
            self.custom_tags.append(new)
        changed = False
        catalog = self.tag_catalog()
        for entry in self.entries:
            if old not in entry.tags:
                continue
            replaced: list[str] = []
            for item in entry.tags:
                name = new if item == old else item
                if name not in replaced:
                    replaced.append(name)
            entry.tags = order_tags(replaced, catalog)
            changed = True
        self.save_settings()
        if changed:
            self.save_entries()
        return "renamed"

    def _remember_tags(self, tags: tuple[str, ...]) -> tuple[str, ...]:
        changed = False
        for tag in tags:
            if self.add_custom_tag(tag):
                changed = True
        if changed:
            self.save_settings()
        return order_tags(tags, self.tag_catalog())

    def load(self) -> None:
        self.entries = []
        self.custom_tags = []
        self.hidden_tags = []
        self.column_order = [0, 1, 2, 3]
        self.column_widths = list(DEFAULT_COLUMN_WIDTHS)
        self.load_warning = ""
        self._load_settings()
        if self.blacklist_path.exists():
            try:
                data = json.loads(self.blacklist_path.read_text(encoding="utf-8"))
                for item in data.get("entries", []):
                    name = clean_stored_name(str(item.get("name", "")))
                    if not name:
                        continue
                    tags, reason = coerce_tags(
                        item.get("tags", item.get("reasons") or ()),
                        str(item.get("reason", item.get("note", ""))),
                    )
                    self.entries.append(
                        Entry(
                            name=name[:_MAX_NAME],
                            reason=reason,
                            tags=tags,
                            match_from_prefix=bool(item.get("match_from_prefix", False)),
                            added_at=str(item.get("added_at", "")),
                        )
                    )
            except (OSError, ValueError, AttributeError, TypeError) as exc:
                self.entries = []
                backup = _set_aside(self.blacklist_path)
                self.load_warning = f"黑名单文件无法读取（{exc}），已留作 {backup.name}。"
        discovered = False
        stripped = False
        for entry in self.entries:
            kept = tuple(tag for tag in entry.tags if tag not in self.hidden_tags)
            if kept != entry.tags:
                entry.tags = kept
                stripped = True
            for tag in entry.tags:
                if tag not in TAGS and self.add_custom_tag(tag):
                    discovered = True
            entry.tags = order_tags(entry.tags, self.tag_catalog())
        if discovered:
            self.save_settings()
        if stripped:
            self.save_entries()
        self.scans = []
        if self.history_path.exists():
            try:
                saved = json.loads(self.history_path.read_text(encoding="utf-8"))
                for item in saved.get("scans", []):
                    names = []
                    for seat in item.get("names", []):
                        names.append(
                            {
                                "seat": int(seat.get("seat", 0)),
                                "name": str(seat.get("name", ""))[:_MAX_NAME],
                                "unclear": bool(seat.get("unclear", False)),
                            }
                        )
                    self.scans.append(
                        {
                            "at": str(item.get("at", "")),
                            "elapsed": item.get("elapsed"),
                            "names": names,
                        }
                    )
            except (OSError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
                self.scans = []
        collapsed = _collapse(self.scans)
        if len(collapsed) != len(self.scans):
            self.scans = collapsed
            self.save_scans()
        else:
            self.scans = collapsed

    def save_entries(self) -> None:
        _daily_backup(self.blacklist_path)
        _atomic_write(
            self.blacklist_path,
            {
                "entries": [
                    {
                        "name": entry.name,
                        "reason": entry.reason,
                        "tags": list(entry.tags),
                        "match_from_prefix": entry.match_from_prefix,
                        "added_at": entry.added_at,
                    }
                    for entry in self.entries
                ]
            },
        )

    def save_settings(self) -> None:
        _atomic_write(
            self.settings_path,
            {
                "hotkey": self.hotkey,
                "auto_capture": self.auto_capture,
                "save_debug_frames": self.save_debug_frames,
                "panel_pos": None if self.panel_pos is None else [self.panel_pos[0], self.panel_pos[1]],
                "window_size": None if self.window_size is None else [self.window_size[0], self.window_size[1]],
                "theme": self.theme,
                "player_name": self.player_name,
                "custom_tags": list(self.custom_tags),
                "hidden_tags": list(self.hidden_tags),
                "column_order": list(self.column_order),
                "column_widths": list(self.column_widths),
                "names_hidden": self.names_hidden,
                "hit_sound": self.hit_sound,
            },
        )

    def _load_settings(self) -> None:
        if not self.settings_path.exists():
            return
        try:
            settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
            self.hotkey = str(settings.get("hotkey", "") or "") or DEFAULT_HOTKEY
            self.auto_capture = bool(settings.get("auto_capture", True))
            self.save_debug_frames = bool(settings.get("save_debug_frames", False))
            self.panel_pos = _panel_pos(settings.get("panel_pos"))
            self.window_size = _window_size(settings.get("window_size"))
            theme = str(settings.get("theme", "") or "")
            if theme in ("蓝色", "棕色", "紫色", "绿色", "红色"):
                self.theme = theme
            self.player_name = clean_stored_name(str(settings.get("player_name", "") or ""))[:_MAX_NAME]
            self.custom_tags = []
            self.hidden_tags = []
            order = settings.get("column_order")
            if isinstance(order, list) and sorted(order) == [0, 1, 2, 3]:
                self.column_order = [int(index) for index in order]
            widths = _column_widths(settings.get("column_widths"))
            if widths is not None:
                self.column_widths = widths
            self.names_hidden = bool(settings.get("names_hidden", False))
            self.hit_sound = bool(settings.get("hit_sound", False))
            for raw in settings.get("hidden_tags") or []:
                tag = clean_tag(str(raw))
                if tag in TAGS and tag not in self.hidden_tags:
                    self.hidden_tags.append(tag)
            for raw in settings.get("custom_tags") or []:
                self.add_custom_tag(str(raw))
        except (OSError, ValueError, AttributeError, TypeError):
            self.load_warning = (self.load_warning + " 设置文件无法读取，没读到的设置用了默认值。").strip()

    def save_scans(self) -> None:
        _atomic_write(self.history_path, {"scans": self.scans[:_MAX_SCANS]})

    def add_scan(self, names: list[dict], elapsed: float | None = None) -> str:
        """Return added, refreshed, filled, or skipped. The same minute keeps the first record."""
        now = datetime.now().astimezone().replace(microsecond=0)
        record = {
            "at": now.isoformat(),
            "elapsed": None if elapsed is None else round(float(elapsed), 2),
            "names": [_stored_seat(item) for item in names],
        }
        if self.scans and _same_clock_minute(str(self.scans[0].get("at", "")), now):
            merged = _fill_unclear(list(self.scans[0].get("names", [])), record["names"])
            if merged is None:
                return "skipped"
            self.scans[0]["names"] = merged
            self.save_scans()
            return "filled"
        key_names = record["names"]
        if _readable_names(key_names):
            for index, existing in enumerate(self.scans):
                if not _is_same_recording(key_names, existing.get("names", [])):
                    continue
                existing["at"] = record["at"]
                existing["elapsed"] = record["elapsed"]
                existing["names"] = record["names"]
                self.scans.insert(0, self.scans.pop(index))
                self.scans = _collapse(self.scans)
                self.save_scans()
                return "refreshed"
        self.scans.insert(0, record)
        del self.scans[_MAX_SCANS:]
        self.save_scans()
        return "added"

    def remove_scan(self, index: int) -> None:
        if 0 <= index < len(self.scans):
            del self.scans[index]
            self.save_scans()

    def clear_scans(self) -> None:
        self.scans = []
        self.save_scans()

    def contains_name(self, name: str) -> bool:
        target = fold(clean_stored_name(name))
        if not target:
            return False
        return any(fold(entry.name) == target for entry in self.entries)

    def remove_name(self, name: str) -> None:
        target = fold(clean_stored_name(name))
        if not target:
            return
        kept = [entry for entry in self.entries if fold(entry.name) != target]
        if len(kept) == len(self.entries):
            return
        self.entries = kept
        self.save_entries()

    def replace_entries(self, pairs: list[tuple[str, str]]) -> None:
        """Replace the list from edited lines. The same name keeps its old settings."""
        previous = {fold(entry.name): entry for entry in self.entries}
        order: list[str] = []
        chosen: dict[str, tuple[str, str]] = {}
        for name, note in pairs:
            cleaned = clean_stored_name(name)[:_MAX_NAME]
            if not cleaned:
                continue
            key = fold(cleaned)
            if key not in chosen:
                order.append(key)
            chosen[key] = (cleaned, (note or "").strip()[:_MAX_NOTE])
        updated: list[Entry] = []
        for key in order:
            cleaned, note = chosen[key]
            old = previous.get(key)
            updated.append(
                Entry(
                    name=cleaned,
                    reason=note,
                    match_from_prefix=old.match_from_prefix if old else False,
                    added_at=old.added_at if old else datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                )
            )
        self.entries = updated
        self.save_entries()

    def recheck_tags(self) -> int:
        """Add any current tag whose word is already in a saved reason. Existing tags stay."""
        catalog = self.tag_catalog()
        changed = 0
        for entry in self.entries:
            found, _kept = tags_and_reason(entry.reason, catalog)
            merged = list(entry.tags)
            grew = False
            for tag in found:
                if tag not in merged:
                    merged.append(tag)
                    grew = True
            if not grew:
                continue
            entry.tags = order_tags(merged, catalog)
            changed += 1
        if changed:
            self.save_entries()
        return changed

    def add(self, name: str, reason: str = "", match_from_prefix: bool = False, tags: tuple[str, ...] | list[str] = ()) -> Entry | None:
        """Add one name. Returns None when it has no letters or digits, or is already on the list."""
        cleaned = clean_stored_name(name)[:_MAX_NAME]
        if not cleaned or self.contains_name(cleaned):
            return None
        chosen, detail = coerce_tags(tags, reason)
        chosen = self._remember_tags(chosen)
        entry = Entry(
            name=cleaned,
            reason=detail,
            tags=chosen,
            match_from_prefix=bool(match_from_prefix),
            added_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        self.entries.append(entry)
        self.save_entries()
        return entry

    def add_names(self, names: list[str]) -> int:
        existing = {fold(entry.name) for entry in self.entries}
        added = 0
        for name in names:
            cleaned = clean_stored_name(name)[:_MAX_NAME]
            key = fold(cleaned)
            if not key or key in existing:
                continue
            existing.add(key)
            self.entries.append(
                Entry(
                    name=cleaned,
                    added_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                )
            )
            added += 1
        if added:
            self.save_entries()
        return added

    def add_annotated(self, rows: list[tuple[str, tuple[str, ...], str]]) -> int:
        """Add 名字（说明） rows. A name already on the list is skipped."""
        existing = {fold(entry.name) for entry in self.entries}
        added = 0
        for name, tags, reason in rows:
            cleaned = clean_stored_name(name)[:_MAX_NAME]
            key = fold(cleaned)
            if not key or key in existing:
                continue
            existing.add(key)
            chosen, detail = coerce_tags(tags, reason)
            chosen = self._remember_tags(chosen)
            self.entries.append(
                Entry(
                    name=cleaned,
                    reason=detail,
                    tags=chosen,
                    added_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                )
            )
            added += 1
        if added:
            self.save_entries()
        return added

    def update_at(self, index: int, name: str, tags: tuple[str, ...] | list[str], reason: str = "") -> bool:
        if not 0 <= index < len(self.entries):
            return False
        cleaned = clean_stored_name(name)[:_MAX_NAME]
        if not cleaned:
            return False
        key = fold(cleaned)
        for other_index, other in enumerate(self.entries):
            if other_index != index and fold(other.name) == key:
                return False
        chosen, stored_reason = coerce_tags(tags, reason)
        chosen = self._remember_tags(chosen)
        current = self.entries[index]
        self.entries[index] = Entry(
            name=cleaned,
            reason=stored_reason,
            tags=chosen,
            match_from_prefix=current.match_from_prefix,
            added_at=current.added_at,
        )
        self.save_entries()
        return True

    def remove_at(self, index: int) -> None:
        if 0 <= index < len(self.entries):
            del self.entries[index]
            self.save_entries()

    def restore_entries(self, entries: list[Entry]) -> None:
        """Put back the list as it was before an add, delete, or clear. Used by 撤销."""
        self.entries = [
            Entry(entry.name, entry.reason, tuple(entry.tags), entry.match_from_prefix, entry.added_at)
            for entry in entries
        ]
        self.save_entries()

    def snapshot_entries(self) -> list[Entry]:
        return [Entry(entry.name, entry.reason, tuple(entry.tags), entry.match_from_prefix, entry.added_at) for entry in self.entries]

    def clear_entries(self) -> None:
        self.entries = []
        self.save_entries()

    def reset(self) -> None:
        """Drop every saved name, record, and setting. The next open is a new app."""
        self.entries = []
        self.scans = []
        self.hotkey = DEFAULT_HOTKEY
        self.auto_capture = True
        self.save_debug_frames = False
        self.panel_pos = None
        self.window_size = None
        self.theme = "蓝色"
        self.player_name = ""
        self.custom_tags = []
        self.hidden_tags = []
        self.column_order = [0, 1, 2, 3]
        self.column_widths = list(DEFAULT_COLUMN_WIDTHS)
        self.names_hidden = False
        self.hit_sound = False
        self.load_warning = ""
        self.save_entries()
        self.save_scans()
        self.save_settings()

    def set_prefix(self, index: int, enabled: bool) -> None:
        if 0 <= index < len(self.entries):
            self.entries[index].match_from_prefix = bool(enabled)
            self.save_entries()
