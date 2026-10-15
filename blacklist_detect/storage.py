"""Local blacklist and settings. Nothing is uploaded."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from blacklist_detect.hotkey import two_keys
from blacklist_detect.match import MIN_PREFIX_CHARS, clean_stored_name, fold
from blacklist_detect.model import Combo, Entry
from blacklist_detect.paths import app_dir

# What changed in each list, as counts: never a name.
_log = logging.getLogger("blacklist_detect.storage")

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


# First line of a list copied with 分享. 批量添加 reads such a paste with parse_shared.
SHARE_MARK = "#模仿者小工具 黑名单"
# Lists copied before the rename start with this.
OLD_SHARE_MARKS = ("#黑名单检测 名单",)
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
    marks = (SHARE_MARK, *OLD_SHARE_MARKS)
    return any(line.strip().startswith(marks) for line in (text or "").splitlines())


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


def _clean_nickname(raw: str) -> str:
    """A nickname is shown as typed, on one line and short."""
    return " ".join((raw or "").split())[:_MAX_NAME]


def merge_reason(old: str, new: str) -> str:
    """Two reasons as one: a reason already said is not said twice."""
    old, new = (old or "").strip(), (new or "").strip()
    if not new or new in old:
        return old
    if not old or old in new:
        return new[:_MAX_NOTE]
    return f"{old}；{new}"[:_MAX_NOTE]


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


def _log_set_aside(exc: Exception, backup: Path) -> None:
    from blacklist_detect.logs import log

    log.warning("The blacklist file could not be read (%s); kept as %s", exc, backup)


def _set_aside(path: Path) -> Path:
    """Move an unreadable file out of the way under a new name. Earlier ones are never overwritten."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.stem}.unreadable-{stamp}{path.suffix}")
    try:
        path.replace(target)
    except OSError:
        return path
    return target



def _theme(value: object) -> str:
    """A 嘉宾's or a combination's theme as saved: a scene's key, or "" to follow 嘉宾特效. Whether this
    version still has the scene is the player's business (guests.lobby_choice skips one it has not)."""
    return value.strip()[:40] if isinstance(value, str) else ""


def _choice(value: object, default: str) -> str:
    """A 嘉宾特效 choice as saved: a key, "random" or "off". Anything else is the default; the
    scene and the music each fall back on their own when a key they do not know comes in."""
    return value if isinstance(value, str) and value.strip() else default

class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or app_dir()
        self.blacklist_path = self.root / "blacklist.json"
        self.likes_path = self.root / "likes.json"
        self.settings_path = self.root / "settings.json"
        self.history_path = self.root / "history.json"
        self.entries: list[Entry] = []
        # 嘉宾: players worth meeting again. No tags; a nickname to show instead of the name, and a
        # 嘉宾特效 theme of their own. The last is the top of the list, which decides between them.
        self.likes: list[Entry] = []
        # 嘉宾 who, all in one lobby, get a scene of their own (guests.lobby_choice).
        self.combos: list[Combo] = []
        self.scans: list[dict] = []
        self.hotkey = DEFAULT_HOTKEY
        # 方式: 自动检查 watches for the lobby; 手动检查 (the default) checks on the hotkey.
        self.auto_capture = False
        # 自动检查 was on when 安全模式 turned it off: 完整模式 turns it back on.
        self.auto_resume = False
        self.save_debug_frames = False
        self.panel_pos: tuple[int, int] | None = None
        self.window_size: tuple[int, int] | None = None
        # Where and how the window was last left (Qt's own record, base64), so it opens there again.
        self.window_geometry = ""
        self.theme = "蓝色"
        # 浅色, 深色, or 跟随系统 (light, dark, system); the accent color is self.theme.
        self.appearance = "light"
        self.player_name = ""
        self.custom_tags: list[str] = []
        self.hidden_tags: list[str] = []
        self.column_order: list[int] = [0, 1, 2, 3]
        self.column_widths: list[int] = list(DEFAULT_COLUMN_WIDTHS)
        self.names_hidden = False
        # The app version that last passed the environment check; it runs again after an update.
        self.env_checked = ""
        # × hides the window to the tray (the app keeps checking), or quits.
        self.close_to_tray = True
        # 显示: 安全模式 marks nothing on the game, the result comes as messages at the bottom right
        # of the screen; 完整模式 (False) draws the marks over it. On unless turned off, also for old settings.
        self.safe_mode = True
        # 嘉宾特效: the scene over the game, a key of love_scenes.SCENES, "random" or "off" (经典 until
        # another is chosen); and its music, which follows the scene ("theme") or is "off"
        # (ui_music.MUSIC_CHOICES).
        self.love_scene = "classic"
        self.love_music = "theme"
        # 直播模式: a window for a streaming app with the 嘉宾 marks only, clear behind them. "" off, "on" on.
        self.stream_mode = ""
        # 直播模式's 测试框: the red frame round the game in that window while no mark shows.
        self.stream_test_frame = True
        # 提醒: which lists a check tells about, 黑名单 and 嘉宾; one stays on.
        self.check_blacklist = True
        self.check_likes = True
        # What the player agreed to after being told the risk: "full" (完整模式). "auto" (自动检查) was
        # asked about before v0.8.1 and is kept, but no longer needed.
        self.consented: list[str] = []
        # 使用声明: read and agreed to before the app is used, once per PC.
        self.disclaimer_accepted = False
        # 直播模式's guide: shown by itself the first time it is turned on.
        self.stream_guided = False
        self.load_warning = ""
        # Whether the welcome guide has been shown. A settings file from before this was saved
        # counts as welcomed; no settings file at all is a first open.
        self.welcomed = False
        self.load()

    @property
    def first_run(self) -> bool:
        """The app opens as new: on a new PC, or after 清空数据."""
        return not self.welcomed

    @first_run.setter
    def first_run(self, value: bool) -> None:
        self.welcomed = not value

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
        # 完整模式 only once agreed to; settings from before the question fall back.
        if "full" not in self.consented:
            self.safe_mode = True
        # 安全模式 checks on the hotkey only. 自动检查 is not asked about since v0.8.1.
        if self.safe_mode:
            self.auto_resume = self.auto_resume or self.auto_capture
            self.auto_capture = False
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
                            added_at=str(item.get("added_at", "")),
                        )
                    )
            except (OSError, ValueError, AttributeError, TypeError) as exc:
                self.entries = []
                backup = _set_aside(self.blacklist_path)
                _log_set_aside(exc, backup)
                self.load_warning = "黑名单文件坏了，已备份，先用空名单"
        self._load_likes()
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

    def _load_likes(self) -> None:
        self.likes = []
        self.combos = []
        if not self.likes_path.exists():
            return
        try:
            data = json.loads(self.likes_path.read_text(encoding="utf-8"))
            for item in data.get("likes", []):
                name = clean_stored_name(str(item.get("name", "")))
                if not name or any(fold(like.name) == fold(name) for like in self.likes):
                    continue
                self.likes.append(
                    Entry(
                        name=name[:_MAX_NAME],
                        reason=str(item.get("reason", "")).strip()[:_MAX_NOTE],
                        added_at=str(item.get("added_at", "")),
                        nickname=_clean_nickname(str(item.get("nickname", ""))),
                        theme=_theme(item.get("theme")),
                    )
                )
            for item in data.get("combos", []):
                names = tuple(dict.fromkeys(clean_stored_name(str(name))[:_MAX_NAME] for name in item.get("names", []) if str(name).strip()))
                theme = _theme(item.get("theme"))
                if len({fold(name) for name in names}) >= 2 and theme:
                    self.combos.append(Combo(names, theme))
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            self.likes = []
            self.combos = []
            backup = _set_aside(self.likes_path)
            _log_set_aside(exc, backup)
            self.load_warning = "嘉宾文件坏了，已备份，先用空列表"

    def save_likes(self) -> None:
        _daily_backup(self.likes_path)
        _atomic_write(
            self.likes_path,
            {
                "likes": [
                    {"name": like.name, "nickname": like.nickname, "reason": like.reason, "added_at": like.added_at, "theme": like.theme}
                    for like in self.likes
                ],
                "combos": [{"names": list(combo.names), "theme": combo.theme} for combo in self.combos],
            },
        )

    def like_index(self, name: str) -> int:
        """Where this name is on 嘉宾, or -1."""
        key = fold(clean_stored_name(name))
        return next((index for index, like in enumerate(self.likes) if key and fold(like.name) == key), -1)

    def entry_index(self, name: str) -> int:
        """Where this name is on 黑名单, or -1."""
        key = fold(clean_stored_name(name))
        return next((index for index, entry in enumerate(self.entries) if key and fold(entry.name) == key), -1)

    def add_like(self, name: str, nickname: str = "", reason: str = "", theme: str = "") -> Entry | None:
        """Add one name to 嘉宾. None when it has no letters or digits, or is there already."""
        cleaned = clean_stored_name(name)[:_MAX_NAME]
        if not cleaned or self.like_index(cleaned) >= 0:
            return None
        like = Entry(
            name=cleaned,
            reason=(reason or "").strip()[:_MAX_NOTE],
            added_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            nickname=_clean_nickname(nickname),
            theme=_theme(theme),
        )
        self.likes.append(like)
        self.save_likes()
        _log.info("嘉宾: 1 added, %d in all.", len(self.likes))
        return like

    def update_like(self, index: int, name: str, nickname: str = "", reason: str = "", theme: str = "") -> bool:
        if not 0 <= index < len(self.likes):
            return False
        cleaned = clean_stored_name(name)[:_MAX_NAME]
        found = self.like_index(cleaned)
        if not cleaned or found not in (-1, index):
            return False
        current = self.likes[index]
        self.likes[index] = Entry(
            name=cleaned,
            reason=(reason or "").strip()[:_MAX_NOTE],
            added_at=current.added_at,
            nickname=_clean_nickname(nickname),
            theme=_theme(theme),
        )
        # A new name for a 嘉宾 in a combination: the combination follows it.
        if fold(current.name) != fold(cleaned):
            self.combos = [
                Combo(tuple(cleaned if fold(member) == fold(current.name) else member for member in combo.names), combo.theme)
                for combo in self.combos
            ]
        self.save_likes()
        _log.info("嘉宾: 1 edited.")
        return True

    def remove_like(self, index: int) -> None:
        if 0 <= index < len(self.likes):
            del self.likes[index]
            self.save_likes()
            _log.info("嘉宾: 1 deleted, %d left.", len(self.likes))

    def move_like(self, index: int, to: int) -> bool:
        """Move a 嘉宾 to another place on the list (indexes as saved: the last is the top)."""
        if not 0 <= index < len(self.likes) or not 0 <= to < len(self.likes) or index == to:
            return False
        self.likes.insert(to, self.likes.pop(index))
        self.save_likes()
        _log.info("嘉宾: 1 moved.")
        return True

    def set_combos(self, combos: list[Combo]) -> None:
        """Save the combinations as they are now."""
        self.combos = list(combos)
        self.save_likes()
        _log.info("嘉宾 combinations: %d.", len(self.combos))

    def snapshot_likes(self) -> list[Entry]:
        return [replace(like, tags=()) for like in self.likes]

    def restore_likes(self, likes: list[Entry]) -> None:
        """Put 嘉宾 back as it was before an add, delete, or clear. Used by 撤销."""
        self.likes = [replace(like, tags=()) for like in likes]
        self.save_likes()
        _log.info("嘉宾: put back as it was (撤销), %d in all.", len(self.likes))

    def clear_likes(self) -> None:
        self.likes = []
        self.save_likes()
        _log.info("嘉宾: cleared.")

    def import_likes(self, rows: list[tuple[str, tuple[str, ...], str, int]]) -> tuple[int, int]:
        """Like import_rows, for 嘉宾: each (name, _, 原因, -1) is added; (…, index) folds into it."""
        stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        taken = {fold(like.name) for like in self.likes}
        added = merged = 0
        for name, _tags, reason, target in rows:
            cleaned = clean_stored_name(name)[:_MAX_NAME]
            key = fold(cleaned)
            if not key:
                continue
            if 0 <= target < len(self.likes):
                like = self.likes[target]
                old = fold(like.name)
                fuller = len(key) > len(old) and key.startswith(old) and key not in taken
                self.likes[target] = replace(like, name=cleaned if fuller else like.name, reason=merge_reason(like.reason, reason))
                taken.add(key)
                merged += 1
                continue
            if key in taken:
                continue
            taken.add(key)
            self.likes.append(Entry(name=cleaned, reason=(reason or "").strip()[:_MAX_NOTE], added_at=stamp))
            added += 1
        if added or merged:
            self.save_likes()
        _log.info("嘉宾: %d imported, %d merged, %d in all.", added, merged, len(self.likes))
        return added, merged

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
                "auto_resume": self.auto_resume,
                "save_debug_frames": self.save_debug_frames,
                "panel_pos": None if self.panel_pos is None else [self.panel_pos[0], self.panel_pos[1]],
                "window_size": None if self.window_size is None else [self.window_size[0], self.window_size[1]],
                "window_geometry": self.window_geometry,
                "theme": self.theme,
                "appearance": self.appearance,
                "player_name": self.player_name,
                "custom_tags": list(self.custom_tags),
                "hidden_tags": list(self.hidden_tags),
                "column_order": list(self.column_order),
                "column_widths": list(self.column_widths),
                "names_hidden": self.names_hidden,
                "env_checked": self.env_checked,
                "welcomed": self.welcomed,
                "close_to_tray": self.close_to_tray,
                "safe_mode": self.safe_mode,
                "love_scene": self.love_scene,
                "love_music": self.love_music,
                "stream_mode": self.stream_mode,
                "stream_test_frame": self.stream_test_frame,
                "check_blacklist": self.check_blacklist,
                "check_likes": self.check_likes,
                "consented": list(self.consented),
                "disclaimer_accepted": self.disclaimer_accepted,
                "stream_guided": self.stream_guided,
            },
        )

    def _load_settings(self) -> None:
        if not self.settings_path.exists():
            return
        try:
            settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
            saved = str(settings.get("hotkey", "") or "") or DEFAULT_HOTKEY
            # Two keys at most since v0.9.0: Ctrl+Alt+F11 is kept as Ctrl+F11.
            self.hotkey = two_keys(saved)
            if self.hotkey != saved:
                _log.info("Hotkey %s cut to %s: two keys at most.", saved, self.hotkey)
            self.auto_capture = bool(settings.get("auto_capture", False))
            self.auto_resume = bool(settings.get("auto_resume", False))
            self.save_debug_frames = bool(settings.get("save_debug_frames", False))
            self.panel_pos = _panel_pos(settings.get("panel_pos"))
            self.window_size = _window_size(settings.get("window_size"))
            self.window_geometry = str(settings.get("window_geometry", "") or "")
            theme = str(settings.get("theme", "") or "")
            if theme in ("蓝色", "棕色", "紫色", "绿色", "红色"):
                self.theme = theme
            appearance = str(settings.get("appearance", "") or "")
            if appearance in ("light", "dark", "system"):
                self.appearance = appearance
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
            self.env_checked = str(settings.get("env_checked", "") or "")
            self.welcomed = bool(settings.get("welcomed", True))
            self.close_to_tray = bool(settings.get("close_to_tray", True))
            self.safe_mode = bool(settings.get("safe_mode", True))
            self.love_scene = _choice(settings.get("love_scene"), "classic")
            # The five wedding tunes and 随机 that came before follow the theme now; 无 stays off.
            self.love_music = "off" if settings.get("love_music") == "off" else "theme"
            # v0.6.0 saved "key" (green) or "alpha" (clear), v0.6.1 "key": each is on, and clear now.
            self.stream_mode = "on" if settings.get("stream_mode") in ("on", "key", "alpha") else ""
            self.stream_test_frame = settings.get("stream_test_frame") is not False
            self.check_blacklist = settings.get("check_blacklist") is not False
            self.check_likes = settings.get("check_likes") is not False
            if not (self.check_blacklist or self.check_likes):
                self.check_blacklist = self.check_likes = True
            self.disclaimer_accepted = settings.get("disclaimer_accepted") is True
            self.stream_guided = settings.get("stream_guided") is True
            agreed = settings.get("consented") or []
            self.consented = [mode for mode in ("full", "auto") if isinstance(agreed, list) and mode in agreed]
            for raw in settings.get("hidden_tags") or []:
                tag = clean_tag(str(raw))
                if tag in TAGS and tag not in self.hidden_tags:
                    self.hidden_tags.append(tag)
            for raw in settings.get("custom_tags") or []:
                self.add_custom_tag(str(raw))
        except (OSError, ValueError, AttributeError, TypeError):
            self.load_warning = "；".join(part for part in (self.load_warning, "设置文件坏了，已恢复默认") if part)

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
            _log.info("记录: 1 deleted, %d left.", len(self.scans))

    def clear_scans(self) -> None:
        self.scans = []
        self.save_scans()
        _log.info("记录: cleared.")

    def contains_name(self, name: str) -> bool:
        target = fold(clean_stored_name(name))
        if not target:
            return False
        return any(fold(entry.name) == target for entry in self.entries)

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

    def add(self, name: str, reason: str = "", tags: tuple[str, ...] | list[str] = ()) -> Entry | None:
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
            added_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        self.entries.append(entry)
        self.save_entries()
        _log.info("黑名单: 1 added, %d in all.", len(self.entries))
        return entry

    def import_rows(self, rows: list[tuple[str, tuple[str, ...], str, int]]) -> tuple[int, int]:
        """Add each (name, 标签, 原因, -1); fold each (name, 标签, 原因, index) into that entry.

        A merge keeps the entry's 标签 and adds the new ones, adds a 原因 it did not say yet,
        and takes the longer name when the list had it cut short. Returns (added, merged).
        """
        stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        taken = {fold(entry.name) for entry in self.entries}
        added = merged = 0
        for name, tags, reason, target in rows:
            cleaned = clean_stored_name(name)[:_MAX_NAME]
            key = fold(cleaned)
            if not key:
                continue
            chosen, detail = coerce_tags(tags, reason)
            chosen = self._remember_tags(chosen)
            if 0 <= target < len(self.entries):
                entry = self.entries[target]
                old = fold(entry.name)
                fuller = len(key) > len(old) and key.startswith(old) and key not in taken
                self.entries[target] = Entry(
                    name=cleaned if fuller else entry.name,
                    reason=merge_reason(entry.reason, detail),
                    tags=order_tags(list(dict.fromkeys([*entry.tags, *chosen])), self.tag_catalog()),
                    added_at=entry.added_at,
                )
                taken.add(key)
                merged += 1
                continue
            if key in taken:
                continue
            taken.add(key)
            self.entries.append(Entry(name=cleaned, reason=detail, tags=chosen, added_at=stamp))
            added += 1
        if added or merged:
            self.save_entries()
        _log.info("黑名单: %d imported, %d merged, %d in all.", added, merged, len(self.entries))
        return added, merged

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
            added_at=current.added_at,
        )
        self.save_entries()
        _log.info("黑名单: 1 edited.")
        return True

    def remove_at(self, index: int) -> None:
        if 0 <= index < len(self.entries):
            del self.entries[index]
            self.save_entries()
            _log.info("黑名单: 1 deleted, %d left.", len(self.entries))

    def restore_entries(self, entries: list[Entry]) -> None:
        """Put back the list as it was before an add, delete, or clear. Used by 撤销."""
        self.entries = [
            Entry(entry.name, entry.reason, tuple(entry.tags), entry.added_at)
            for entry in entries
        ]
        self.save_entries()
        _log.info("黑名单: put back as it was (撤销), %d in all.", len(self.entries))

    def snapshot_entries(self) -> list[Entry]:
        return [Entry(entry.name, entry.reason, tuple(entry.tags), entry.added_at) for entry in self.entries]

    def clear_entries(self) -> None:
        self.entries = []
        self.save_entries()
        _log.info("黑名单: cleared.")

    def reset(self) -> None:
        """Drop every saved name, record, and setting. The next open is a new app."""
        _log.info("清空数据: every list, record and setting dropped.")
        self.entries = []
        self.likes = []
        self.combos = []
        self.scans = []
        self.hotkey = DEFAULT_HOTKEY
        # 安全模式 and 手动检查 again, until agreed to otherwise.
        self.auto_capture = False
        self.auto_resume = False
        self.save_debug_frames = False
        self.panel_pos = None
        self.window_size = None
        self.window_geometry = ""
        self.theme = "蓝色"
        self.appearance = "light"
        self.player_name = ""
        self.custom_tags = []
        self.hidden_tags = []
        self.column_order = [0, 1, 2, 3]
        self.column_widths = list(DEFAULT_COLUMN_WIDTHS)
        self.names_hidden = False
        # The next open is a first open: the environment check and the welcome guide run again.
        self.env_checked = ""
        self.welcomed = False
        self.close_to_tray = True
        self.safe_mode = True
        self.love_scene = "classic"
        self.love_music = "theme"
        self.stream_mode = ""
        self.stream_test_frame = True
        self.check_blacklist = True
        self.check_likes = True
        self.consented = []
        self.disclaimer_accepted = False
        self.stream_guided = False
        self.load_warning = ""
        self.save_entries()
        self.save_likes()
        self.save_scans()
        self.save_settings()

