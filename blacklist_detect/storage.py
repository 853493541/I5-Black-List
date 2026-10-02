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
REASON_TAGS = ("炸房", "贴脸", "其他")


def coerce_reasons(reasons: tuple[str, ...] | list[str], note: str) -> tuple[tuple[str, ...], str]:
    """Keep the three checkboxes. A leftover note is the 其他 description."""
    picked = [tag for tag in REASON_TAGS if tag in set(reasons or ())]
    if picked:
        detail = (note or "").strip() if "其他" in picked else ""
        return tuple(picked), detail[:_MAX_NOTE]
    return reasons_from_note(note)


def reasons_from_note(note: str) -> tuple[tuple[str, ...], str]:
    parts = [part for part in re.split(r"[,，、:：\s]+", note or "") if part]
    found: list[str] = []
    rest: list[str] = []
    for part in parts:
        if part in REASON_TAGS:
            if part not in found:
                found.append(part)
        else:
            rest.append(part)
    if rest and "其他" not in found:
        found.append("其他")
    ordered = tuple(tag for tag in REASON_TAGS if tag in found)
    detail = "".join(rest) if "其他" in ordered else ""
    return ordered, detail[:_MAX_NOTE]


def reason_text(entry: Entry) -> str:
    reasons = entry.reasons
    detail = entry.note
    if not reasons and detail:
        reasons, detail = reasons_from_note(detail)
    bits: list[str] = []
    for tag in REASON_TAGS:
        if tag not in reasons:
            continue
        if tag == "其他" and detail:
            bits.append(f"其他：{detail}")
        else:
            bits.append(tag)
    return "、".join(bits)


def format_blacklist(entries: list[Entry]) -> str:
    """One line per player: name, reason."""
    lines: list[str] = []
    for entry in entries:
        reason = reason_text(entry)
        if reason:
            lines.append(f"{entry.name}, {reason}")
        else:
            lines.append(entry.name)
    return "\n".join(lines)


def parse_blacklist(text: str) -> list[tuple[str, str]]:
    """Each line is one player. The first comma splits the name from the reason."""
    parsed: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        cut = next((index for index, char in enumerate(line) if char in ",，"), None)
        if cut is None:
            name, note = line, ""
        else:
            name, note = line[:cut], line[cut + 1 :]
        parsed.append((name.strip(), note.strip()))
    return parsed


def _stored_seat(item: dict) -> dict:
    return {
        "seat": int(item.get("seat", 0)),
        "name": str(item.get("name") or "")[:_MAX_NAME],
        "unclear": bool(item.get("unclear")),
    }


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


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or app_dir()
        self.blacklist_path = self.root / "blacklist.json"
        self.settings_path = self.root / "settings.json"
        self.history_path = self.root / "history.json"
        self.entries: list[Entry] = []
        self.scans: list[dict] = []
        self.hotkey = ""
        self.muted = False
        self.auto_capture = False
        self.save_debug_frames = False
        self.panel_pos: tuple[int, int] | None = None
        self.load_warning = ""
        self.load()

    def load(self) -> None:
        self.entries = []
        self.load_warning = ""
        if self.blacklist_path.exists():
            try:
                data = json.loads(self.blacklist_path.read_text(encoding="utf-8"))
                for item in data.get("entries", []):
                    name = clean_stored_name(str(item.get("name", "")))
                    if not name:
                        continue
                    reasons, detail = coerce_reasons(item.get("reasons") or (), str(item.get("note", "")))
                    self.entries.append(
                        Entry(
                            name=name[:_MAX_NAME],
                            note=detail,
                            reasons=reasons,
                            match_from_prefix=bool(item.get("match_from_prefix", False)),
                            added_at=str(item.get("added_at", "")),
                        )
                    )
            except (OSError, json.JSONDecodeError, AttributeError) as exc:
                backup = self.blacklist_path.with_name("blacklist.json.bak")
                try:
                    self.blacklist_path.replace(backup)
                except OSError:
                    backup = self.blacklist_path
                self.load_warning = f"黑名单文件无法读取（{exc}），已留作 {backup.name}。"
        if self.settings_path.exists():
            try:
                settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
                self.hotkey = str(settings.get("hotkey", "") or "")
                self.muted = bool(settings.get("muted", False))
                self.auto_capture = bool(settings.get("auto_capture", False))
                self.save_debug_frames = bool(settings.get("save_debug_frames", False))
                self.panel_pos = _panel_pos(settings.get("panel_pos"))
            except (OSError, json.JSONDecodeError):
                self.load_warning = (self.load_warning + " 设置文件无法读取。").strip()
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
        _atomic_write(
            self.blacklist_path,
            {
                "entries": [
                    {
                        "name": entry.name,
                        "note": entry.note,
                        "reasons": list(entry.reasons),
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
                "muted": self.muted,
                "auto_capture": self.auto_capture,
                "save_debug_frames": self.save_debug_frames,
                "panel_pos": None if self.panel_pos is None else [self.panel_pos[0], self.panel_pos[1]],
            },
        )

    def save_scans(self) -> None:
        _atomic_write(self.history_path, {"scans": self.scans[:_MAX_SCANS]})

    def add_scan(self, names: list[dict], elapsed: float | None = None) -> None:
        record = {
            "at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
            "elapsed": None if elapsed is None else round(float(elapsed), 2),
            "names": [_stored_seat(item) for item in names],
        }
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
                return
        self.scans.insert(0, record)
        del self.scans[_MAX_SCANS:]
        self.save_scans()

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
            reasons, detail = reasons_from_note(note)
            old = previous.get(key)
            updated.append(
                Entry(
                    name=cleaned,
                    note=detail,
                    reasons=reasons,
                    match_from_prefix=old.match_from_prefix if old else False,
                    added_at=old.added_at if old else datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                )
            )
        self.entries = updated
        self.save_entries()

    def add(self, name: str, note: str = "", match_from_prefix: bool = False, reasons: tuple[str, ...] | list[str] = ()) -> Entry | None:
        cleaned = clean_stored_name(name)[:_MAX_NAME]
        if not cleaned:
            return None
        chosen, detail = coerce_reasons(reasons, note)
        entry = Entry(
            name=cleaned,
            note=detail,
            reasons=chosen,
            match_from_prefix=bool(match_from_prefix),
            added_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        self.entries.append(entry)
        self.save_entries()
        return entry

    def update_at(self, index: int, name: str, reasons: tuple[str, ...] | list[str], detail: str = "") -> bool:
        if not 0 <= index < len(self.entries):
            return False
        cleaned = clean_stored_name(name)[:_MAX_NAME]
        if not cleaned:
            return False
        key = fold(cleaned)
        for other_index, other in enumerate(self.entries):
            if other_index != index and fold(other.name) == key:
                return False
        chosen, stored_detail = coerce_reasons(reasons, detail)
        current = self.entries[index]
        self.entries[index] = Entry(
            name=cleaned,
            note=stored_detail,
            reasons=chosen,
            match_from_prefix=current.match_from_prefix,
            added_at=current.added_at,
        )
        self.save_entries()
        return True

    def remove_at(self, index: int) -> None:
        if 0 <= index < len(self.entries):
            del self.entries[index]
            self.save_entries()

    def set_prefix(self, index: int, enabled: bool) -> None:
        if 0 <= index < len(self.entries):
            self.entries[index].match_from_prefix = bool(enabled)
            self.save_entries()
