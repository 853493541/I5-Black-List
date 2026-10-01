"""Local blacklist and settings. Nothing is uploaded."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from blacklist_detect.model import Entry
from blacklist_detect.paths import app_dir
from blacklist_detect.match import clean_stored_name

_MAX_NAME = 64
_MAX_NOTE = 200


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
        self.entries: list[Entry] = []
        self.hotkey = ""
        self.muted = False
        self.save_debug_frames = False
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
                    self.entries.append(
                        Entry(
                            name=name[:_MAX_NAME],
                            note=str(item.get("note", ""))[:_MAX_NOTE],
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
                self.save_debug_frames = bool(settings.get("save_debug_frames", False))
            except (OSError, json.JSONDecodeError):
                self.load_warning = (self.load_warning + " 设置文件无法读取。").strip()

    def save_entries(self) -> None:
        _atomic_write(
            self.blacklist_path,
            {
                "entries": [
                    {
                        "name": entry.name,
                        "note": entry.note,
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
                "save_debug_frames": self.save_debug_frames,
            },
        )

    def add(self, name: str, note: str = "", match_from_prefix: bool = False) -> Entry | None:
        cleaned = clean_stored_name(name)[:_MAX_NAME]
        if not cleaned:
            return None
        entry = Entry(
            name=cleaned,
            note=(note or "").strip()[:_MAX_NOTE],
            match_from_prefix=bool(match_from_prefix),
            added_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        self.entries.append(entry)
        self.save_entries()
        return entry

    def remove_at(self, index: int) -> None:
        if 0 <= index < len(self.entries):
            del self.entries[index]
            self.save_entries()

    def set_prefix(self, index: int, enabled: bool) -> None:
        if 0 <= index < len(self.entries):
            self.entries[index].match_from_prefix = bool(enabled)
            self.save_entries()
