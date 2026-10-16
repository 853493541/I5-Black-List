"""Local blacklist and settings. Nothing is uploaded."""

from __future__ import annotations

import json
import logging
import re
import shutil
import wave
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from blacklist_detect import love_scenes
from blacklist_detect.hotkey import parse_hotkey, two_keys
from blacklist_detect.match import MIN_PREFIX_CHARS, clean_stored_name, fold
from blacklist_detect.model import ANY_SCENE, Combo, Entry, Scenes
from blacklist_detect.paths import app_dir, custom_sound_dir

# What changed in each list, as counts: never a name.
_log = logging.getLogger("blacklist_detect.storage")

_MAX_NAME = 64
_MAX_NOTE = 200
# The most scenes a 嘉宾 or a 组合 keeps ticked: far more than there are.
_MAX_SCENES = 64
# The most songs of the player's a 场景 keeps beside its 默认 (场景管理).
MAX_SONGS = 3
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
# The 场景 hotkey, which plays the 场景 picked on 场景管理 at once, with no check.
DEFAULT_EFFECT_HOTKEY = "Alt+F12"


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


def _log_set_aside(exc: Exception, path: Path, backup: Path | None) -> None:
    from blacklist_detect.logs import log

    if backup is None:
        log.warning("A file could not be read (%s); left as %s, it could not be moved either", exc, path)
    else:
        log.warning("A file could not be read (%s); kept as %s", exc, backup)


def _set_aside(path: Path) -> Path | None:
    """Move an unreadable file out of the way under a new name. Earlier ones are never overwritten. None when
    it cannot be moved (another program holds it open): it is not known to be broken, and it is not saved over."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.stem}.unreadable-{stamp}{path.suffix}")
    try:
        path.replace(target)
    except OSError:
        return None
    return target



def _volume(value: object) -> int:
    """A 音量 as saved: a percent from 0 to 100 in steps of 5, else 100."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 100:
        return 100
    return round(value / 5) * 5


def _scene_volume(value: object) -> int:
    """A 场景's 音量 as saved: as _volume, but 1 to 4 kept as they are, which only folding in the 声音 of v0.9.14
    and before leaves (see _folded)."""
    if isinstance(value, int) and not isinstance(value, bool) and 0 < value < 5:
        return value
    return _volume(value)


def _folded(own: int, sound: int) -> int:
    """A 场景's 音量 with the 声音 设置 had up to v0.9.14 taken in: the one times the other, down to a step of 5
    so it is never louder than it was. Below 5 it is what was heard then, never 0 when both were above 0: 5% of
    5% played at 1%, and stays 1%."""
    level = own * sound // 500 * 5
    if level == 0 and own > 0 and sound > 0:
        return max(round(own * sound / 100), 1)
    return level


def _scenes(keys: object, random: object = False) -> Scenes:
    """A 嘉宾's or a combination's scenes as saved: the keys ticked, each once (one replaced is its
    replacement), and whether they are on 随机. Whether this version still has a scene is the player's
    business (guests.lobby_choice skips one it has not). Never raises: what is not a key is dropped."""
    if not isinstance(keys, list | tuple):
        keys = ()
    cleaned = (love_scenes.shown(key.strip()[:40]) for key in keys if isinstance(key, str) and key.strip())
    return Scenes(tuple(dict.fromkeys(cleaned))[:_MAX_SCENES], random is True)


def _saved_scenes(item: dict) -> Scenes:
    """The scenes of a 嘉宾, a combination or 我 in likes.json: "scenes" and "random" (随机; false with none
    ticked is 不放). Up to v0.9.14 there was no "random": "no_scene" true was 不放 and none ticked was any
    scene, now 随机; up to v0.9.13 one "theme", a key (that one ticked) or "" for any scene."""
    if "random" in item:
        return _scenes(item.get("scenes"), item.get("random"))
    if "scenes" not in item:
        theme = item.get("theme")
        item = {"scenes": [theme] if isinstance(theme, str) else []}
    if item.get("no_scene") is True:
        return Scenes()
    scenes = _scenes(item.get("scenes"))
    return scenes if scenes.keys else ANY_SCENE


def _scenes_saved(scenes: Scenes) -> dict:
    """Scenes as likes.json keeps them; "no_scene" still written so v0.9.14 reads the file back the same."""
    return {"scenes": list(scenes.keys), "random": scenes.random, "no_scene": scenes.off}


def _seconds(value: object) -> float | None:
    """Where a 场景's own sound was cut from the file it came from, or how long: seconds, else None."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value < 24 * 3600:
        return None
    return float(value)


def _scene_song(value: object, folder: Path) -> dict | None:
    """One of a 场景's songs as saved: its file, still in folder, the name of the file it came from, and the
    part of it kept. None when it is not one."""
    if not isinstance(value, dict):
        return None
    file = value.get("file")
    # A name in folder only, never a path elsewhere.
    if not (isinstance(file, str) and file and file == Path(file).name and ":" not in file and (folder / file).is_file()):
        return None
    name = value.get("name")
    song: dict = {"file": file, "name": name.strip()[:_MAX_NAME * 4] if isinstance(name, str) else ""}
    for field in ("start", "length"):
        seconds = _seconds(value.get(field))
        if seconds is not None:
            song[field] = seconds
    return song


def _scene_sound(value: object, folder: Path) -> dict | None:
    """One 场景's sound as saved: its own 音量 and the player's songs (_scene_song, each file once, the first
    MAX_SONGS), with the one chosen ("" for 默认, the scene's own; one that is not a song is 默认). Up to v0.9.15 a
    场景 had one song, its "file", always chosen. None when all is the default (100%, no songs) or not a sound."""
    if not isinstance(value, dict):
        return None
    entry: dict = {"volume": _scene_volume(value.get("volume"))}
    saved = value.get("songs") if "songs" in value else [value]
    songs: list[dict] = []
    for song in saved if isinstance(saved, list) else ():
        song = _scene_song(song, folder)
        if song is not None and all(song["file"] != kept["file"] for kept in songs):
            songs.append(song)
    if songs:
        entry["songs"] = songs[:MAX_SONGS]
        chosen = value.get("chosen") if "songs" in value else songs[0]["file"]
        entry["chosen"] = chosen if any(song["file"] == chosen for song in entry["songs"]) else ""
    return entry if entry != {"volume": 100} else None


def _scene_sound_saved(entry: dict) -> dict:
    """A 场景's sound as settings.json keeps it: with the chosen song's file, name, start and length copied beside
    the songs, so v0.9.15 reads the file back playing the same."""
    saved = {"volume": entry.get("volume", 100)}
    songs = entry.get("songs") or []
    if songs:
        saved.update(next((song for song in songs if song["file"] == entry.get("chosen")), {}))
        saved["songs"] = [dict(song) for song in songs]
        saved["chosen"] = entry.get("chosen", "")
    return saved


def _scene_sounds(value: object, folder: Path, unlisted: bool = False) -> dict[str, dict]:
    """场景管理 as saved: by scene key, each 场景's own 音量 and sound (_scene_sound). A key this version does
    not have is kept for the one that has; a replaced scene's is its replacement's, unless that has its own.
    unlisted: saved by v0.9.15, which kept only the chosen song of each, so the rest come back (_unlisted_songs).
    Never raises: a bad entry is dropped, not the rest of the settings."""
    sounds: dict[str, dict] = {}
    if isinstance(value, dict):
        for raw, saved in value.items():
            try:
                key = love_scenes.shown(str(raw).strip()[:40])
                entry = _scene_sound(saved, folder)
                if key and entry is not None and not (key != raw and key in value):
                    sounds[key] = entry
            except Exception:
                _log.info("场景管理: the saved sound of %r dropped.", raw)
    if unlisted:
        try:
            _unlisted_songs(sounds, folder)
        except Exception:
            _log.info("场景管理: songs not in the list left out.", exc_info=True)
    return sounds


_SONG_FILE = re.compile(r"([a-z]+)-(\d+)\.wav")


def _wav_seconds(path: Path) -> float | None:
    """How long the WAV at path is, None when it cannot be read."""
    try:
        with wave.open(str(path)) as wav:
            return _seconds(wav.getnframes() / wav.getframerate())
    except (OSError, EOFError, ZeroDivisionError, wave.Error):
        return None


def _unlisted_songs(sounds: dict[str, dict], folder: Path) -> None:
    """Songs in folder (<key>-<n>.wav) that sounds does not list, back in their 场景's, by n after the song v0.9.15
    had: it saved a 场景's chosen song only, and none with 默认 chosen. The file each came from is not known, so
    its row shows its own name. Up to MAX_SONGS, the chosen one kept."""
    found: dict[str, list[tuple[int, str]]] = {}
    for path in folder.glob("*-*.wav") if folder.is_dir() else ():
        match = _SONG_FILE.fullmatch(path.name)
        if match and match[1] in love_scenes.KEYS:
            found.setdefault(match[1], []).append((int(match[2]), path.name))
    for key, numbered in found.items():
        entry = dict(sounds.get(key) or {"volume": 100})
        songs = list(entry.get("songs", ()))
        for _number, file in sorted(numbered):
            if all(song["file"] != file for song in songs):
                song = _scene_song({"file": file, "length": _wav_seconds(folder / file)}, folder)
                if song is not None:
                    songs.append(song)
        order = {file: number for number, file in numbered}
        songs.sort(key=lambda song: order.get(song["file"], -1))
        chosen = entry.get("chosen", "")
        while len(songs) > MAX_SONGS:
            songs.remove(next(song for song in reversed(songs) if song["file"] != chosen))
        if songs:
            entry["songs"] = songs
            entry["chosen"] = chosen
            sounds[key] = entry


class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or app_dir()
        self.blacklist_path = self.root / "blacklist.json"
        self.likes_path = self.root / "likes.json"
        self.settings_path = self.root / "settings.json"
        self.history_path = self.root / "history.json"
        self.entries: list[Entry] = []
        # 嘉宾: players worth meeting again. No tags; a nickname to show instead of the name, and the
        # 嘉宾场景 that greet them. The last is the top of the list, which decides between them.
        self.likes: list[Entry] = []
        # 嘉宾 who, all in one lobby, get a scene of their own (guests.lobby_choice).
        self.combos: list[Combo] = []
        # 我: the 场景 the player asked for themselves (none, 不放, unless set). The name is player_name.
        self.me = Scenes()
        self.scans: list[dict] = []
        self.hotkey = DEFAULT_HOTKEY
        # 方式: 自动检查 watches for the lobby; 手动检查 (the default) checks on the hotkey.
        self.auto_capture = False
        # 自动检查 was on when 基础模式 turned it off: 完整模式 turns it back on.
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
        # 显示: 基础模式 marks nothing on the game, the result comes as messages at the bottom right
        # of the screen; 完整模式 (False) draws the marks over it. On unless turned off, also for old settings.
        self.safe_mode = True
        # 设置 › 声音 › 静音: no sound at all.
        self.sound_muted = False
        # Up to v0.9.14 设置 had 声音, how loud every sound was, and a 嘉宾 › 场景 switch to turn every scene
        # off, as saved: folded into what took their place as this version first opens (_fold_old_settings).
        self._old_volume = 100
        self._old_scenes_off = False
        # 场景管理: by scene key, a 场景's own 音量 (percent of its loudness, steps of 5) and the player's songs for it,
        # if any, with the one it plays: {"volume": 100, "songs": [{"file": "<key>-<n>.wav" in custom_sounds, "name":
        # the file it came from, "start" and "length": the part of it kept, in seconds}], "chosen": a song's file, or
        # "" for 默认, the scene's own}. A 场景 with neither has no entry.
        self.scene_sounds: dict[str, dict] = {}
        # 场景管理: the scene the 场景 hotkey plays (a love_scenes key), and that hotkey; it never equals 检查's.
        self.quick_scene = "classic"
        self.effect_hotkey = DEFAULT_EFFECT_HOTKEY
        # A hotkey saved by an earlier version that is none now (Shift+Q, Ctrl+S: parse_hotkey), as it was
        # saved, so the player is told it was replaced. Never saved.
        self.dropped_hotkey = ""
        self.dropped_effect_hotkey = ""
        # 直播模式: a window for a streaming app with the 嘉宾 marks only, clear behind them. "" off, "on" on.
        self.stream_mode = ""
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

    def scene_sound(self, key: str) -> tuple[Path | None, int]:
        """A 场景's sound as 场景管理 sets it: the song chosen (None for 默认, the scene's own) and its 音量."""
        entry = self.scene_sounds.get(key) or {}
        file = entry.get("chosen")
        return (custom_sound_dir(self.root) / file if file else None), _scene_volume(entry.get("volume", 100))

    def scene_songs(self, key: str) -> list[dict]:
        """A 场景's songs, the player's, oldest first."""
        return [dict(song) for song in (self.scene_sounds.get(key) or {}).get("songs", ())]

    def _set_scene_sound(self, key: str, entry: dict) -> None:
        """A 场景's entry, or none when it is all default (100%, no songs)."""
        if entry.get("songs") or entry.get("volume", 100) != 100:
            self.scene_sounds[key] = entry
        else:
            self.scene_sounds.pop(key, None)

    def set_scene_volume(self, key: str, volume: int) -> None:
        """A 场景's 音量, not saved yet: 场景管理's slider saves it as it is let go."""
        entry = dict(self.scene_sounds.get(key) or {})
        entry["volume"] = _scene_volume(volume)
        self._set_scene_sound(key, entry)

    def add_scene_song(self, key: str, song: dict) -> None:
        """A song kept for a 场景 (its file already in custom_sounds), the one it plays from now on. Saved. The
        page lets no more than MAX_SONGS in; one more drops the oldest, its file too."""
        entry = dict(self.scene_sounds.get(key) or {})
        songs = [*(kept for kept in entry.get("songs", ()) if kept["file"] != song["file"]), dict(song)]
        for gone in songs[:-MAX_SONGS]:
            try:
                (custom_sound_dir(self.root) / gone["file"]).unlink(missing_ok=True)
            except OSError:
                _log.info("场景管理: %s, dropped from the list, is held.", gone["file"])
        entry["songs"] = songs[-MAX_SONGS:]
        entry["chosen"] = song["file"]
        entry.setdefault("volume", 100)
        self._set_scene_sound(key, entry)
        self.save_settings()
        _log.info("场景管理: a song added for %s.", key)

    def remove_scene_song(self, key: str, file: str) -> None:
        """A 场景's song gone from its list (its file is the caller's), 默认 playing if it was the one chosen. Saved."""
        entry = dict(self.scene_sounds.get(key) or {})
        songs = [song for song in entry.get("songs", ()) if song["file"] != file]
        if songs:
            entry["songs"] = songs
            entry["chosen"] = entry.get("chosen") if entry.get("chosen") != file else ""
        else:
            entry.pop("songs", None)
            entry.pop("chosen", None)
        self._set_scene_sound(key, entry)
        self.save_settings()
        _log.info("场景管理: a song of %s removed.", key)

    def choose_scene_song(self, key: str, file: str) -> None:
        """The sound a 场景 plays: one of its songs by its file, or "" (or one that is none) for 默认. Saved."""
        entry = dict(self.scene_sounds.get(key) or {})
        if not entry.get("songs"):
            return
        entry["chosen"] = file if any(song["file"] == file for song in entry["songs"]) else ""
        self._set_scene_sound(key, entry)
        self.save_settings()

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
        # Files that could not be read and are still where they were: saved over, what is in them would be gone.
        self._unread: set[Path] = set()
        self._old_volume, self._old_scenes_off = 100, False
        self._load_settings()
        # 完整模式 only once agreed to; settings from before the question fall back.
        if "full" not in self.consented:
            self.safe_mode = True
        # 基础模式 checks on the hotkey only. 自动检查 is not asked about since v0.8.1.
        if self.safe_mode:
            self.auto_resume = self.auto_resume or self.auto_capture
            self.auto_capture = False
        if self.blacklist_path.exists():
            try:
                data = json.loads(self.blacklist_path.read_text(encoding="utf-8-sig"))
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
                _log_set_aside(exc, self.blacklist_path, backup)
                self._warn(self.blacklist_path, backup, "黑名单文件坏了，已备份，先用空名单", "黑名单文件读不了，这次改动不保存")
        self._load_likes()
        self._fold_old_settings()
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
        try:
            if discovered:
                self.save_settings()
            if stripped:
                self.save_entries()
        except OSError as exc:
            _log.info("Tags found at open could not be saved (%s): again the next open.", exc)
        self.scans = []
        if self.history_path.exists():
            try:
                saved = json.loads(self.history_path.read_text(encoding="utf-8-sig"))
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
            except (OSError, json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
                self.scans = []
                backup = _set_aside(self.history_path)
                _log_set_aside(exc, self.history_path, backup)
                self._warn(self.history_path, backup, "记录文件坏了，已备份，先用空记录", "记录文件读不了，这次记录不保存")
        collapsed = _collapse(self.scans)
        if len(collapsed) != len(self.scans):
            self.scans = collapsed
            self.save_scans()
        else:
            self.scans = collapsed

    def _load_likes(self) -> None:
        self.likes = []
        self.combos = []
        self.me = Scenes()
        if not self.likes_path.exists():
            return
        try:
            data = json.loads(self.likes_path.read_text(encoding="utf-8-sig"))
            me = data.get("me")
            if isinstance(me, dict):
                self.me = _saved_scenes(me)
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
                        scenes=_saved_scenes(item),
                    )
                )
            for item in data.get("combos", []):
                names = tuple(dict.fromkeys(clean_stored_name(str(name))[:_MAX_NAME] for name in item.get("names", []) if str(name).strip()))
                if len({fold(name) for name in names}) >= 2:
                    self.combos.append(Combo(names, _saved_scenes(item)))
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            self.likes = []
            self.combos = []
            self.me = Scenes()
            backup = _set_aside(self.likes_path)
            _log_set_aside(exc, self.likes_path, backup)
            self._warn(self.likes_path, backup, "嘉宾文件坏了，已备份，先用空列表", "嘉宾文件读不了，这次改动不保存")

    def _fold_old_settings(self) -> None:
        """Settings saved up to v0.9.14, once, into what took their place: 声音 below 100 into every 场景's own
        音量 (nothing is heard louder than it was), and 嘉宾 › 场景 off into 不放 for every 嘉宾 and 组合. Saved,
        the old ones are gone: the next open changes nothing. Not saved (a file that cannot be written), it is
        done again from them the next open."""
        folding = self._old_volume < 100
        if folding:
            for key in dict.fromkeys([*love_scenes.KEYS, *self.scene_sounds]):
                entry = dict(self.scene_sounds.get(key) or {})
                entry["volume"] = _folded(_scene_volume(entry.get("volume", 100)), self._old_volume)
                self.scene_sounds[key] = entry
            _log.info("声音 %d%% folded into every 场景's own 音量.", self._old_volume)
        try:
            if self._old_scenes_off:
                self.likes = [replace(like, scenes=Scenes()) for like in self.likes]
                self.combos = [Combo(combo.names, Scenes()) for combo in self.combos]
                if self.likes or self.combos:
                    self.save_likes()
                _log.info("嘉宾 › 场景 was off: every 嘉宾 and 组合 on 不放.")
            if folding or self._old_scenes_off:
                self.save_settings()
        except OSError as exc:
            _log.info("The old settings, folded in, could not be saved (%s): again the next open.", exc)
        self._old_volume, self._old_scenes_off = 100, False

    def _warn(self, path: Path, backup: Path | None, kept: str, held: str) -> None:
        """Say a file could not be read: kept aside, or, still where it was, not saved over until the next open."""
        if backup is None:
            self._unread.add(path)
        self.load_warning = "；".join(part for part in (self.load_warning, kept if backup is not None else held) if part)

    def _saves(self, path: Path) -> bool:
        """False for a file not read at open and still there (another program held it): it waits for the next open."""
        if path in self._unread:
            _log.info("%s was not read at open: not saved over.", path.name)
            return False
        return True

    def save_likes(self) -> None:
        if not self._saves(self.likes_path):
            return
        _daily_backup(self.likes_path)
        _atomic_write(
            self.likes_path,
            {
                "likes": [
                    {
                        "name": like.name, "nickname": like.nickname, "reason": like.reason, "added_at": like.added_at,
                        **_scenes_saved(like.scenes),
                    }  # fmt: skip
                    for like in self.likes
                ],
                "combos": [{"names": list(combo.names), **_scenes_saved(combo.scenes)} for combo in self.combos],
                "me": _scenes_saved(self.me),
            },
        )

    def set_me(self, scenes: Scenes) -> None:
        """Save the 场景 of 我."""
        self.me = _scenes(scenes.keys, scenes.random)
        self.save_likes()
        _log.info("我: 场景 set.")

    def like_index(self, name: str) -> int:
        """Where this name is on 嘉宾, or -1."""
        key = fold(clean_stored_name(name))
        return next((index for index, like in enumerate(self.likes) if key and fold(like.name) == key), -1)

    def entry_index(self, name: str) -> int:
        """Where this name is on 黑名单, or -1."""
        key = fold(clean_stored_name(name))
        return next((index for index, entry in enumerate(self.entries) if key and fold(entry.name) == key), -1)

    def add_like(self, name: str, nickname: str = "", reason: str = "", scenes: Scenes = ANY_SCENE) -> Entry | None:
        """Add one name to 嘉宾. None when it has no letters or digits, or is there already."""
        cleaned = clean_stored_name(name)[:_MAX_NAME]
        if not cleaned or self.like_index(cleaned) >= 0:
            return None
        like = Entry(
            name=cleaned,
            reason=(reason or "").strip()[:_MAX_NOTE],
            added_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            nickname=_clean_nickname(nickname),
            scenes=_scenes(scenes.keys, scenes.random),
        )
        self.likes.append(like)
        self.save_likes()
        _log.info("嘉宾: 1 added, %d in all.", len(self.likes))
        return like

    def update_like(self, index: int, name: str, nickname: str = "", reason: str = "", scenes: Scenes = ANY_SCENE) -> bool:
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
            scenes=_scenes(scenes.keys, scenes.random),
        )
        # A new name for a 嘉宾 in a combination: the combination follows it.
        if fold(current.name) != fold(cleaned):
            self.combos = [
                Combo(tuple(cleaned if fold(member) == fold(current.name) else member for member in combo.names), combo.scenes)
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

    def save_entries(self) -> None:
        if not self._saves(self.blacklist_path):
            return
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
        if not self._saves(self.settings_path):
            return
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
                "sound_muted": self.sound_muted,
                "scene_sounds": {
                    key: _scene_sound_saved(entry)
                    for key, entry in self.scene_sounds.items()
                    if entry.get("songs") or entry.get("volume", 100) != 100
                },
                # Every song is in scene_sounds. v0.9.15 drops this as it saves, with all but the chosen songs.
                "scene_songs": True,
                "quick_scene": self.quick_scene,
                "effect_hotkey": self.effect_hotkey,
                "stream_mode": self.stream_mode,
                "consented": list(self.consented),
                "disclaimer_accepted": self.disclaimer_accepted,
                "stream_guided": self.stream_guided,
            },
        )

    def _load_settings(self) -> None:
        if not self.settings_path.exists():
            return
        try:
            settings = json.loads(self.settings_path.read_text(encoding="utf-8-sig"))
            saved = str(settings.get("hotkey", "") or "") or DEFAULT_HOTKEY
            # Two keys at most since v0.9.0: Ctrl+Alt+F11 is kept as Ctrl+F11.
            self.hotkey = two_keys(saved)
            if self.hotkey != saved:
                _log.info("Hotkey %s cut to %s: two keys at most.", saved, self.hotkey)
            # Up to v0.9.11 检查 took any key, Q, Shift+A or Ctrl+S too: one that is no hotkey now is the
            # default again (or none, below, when the 场景 hotkey has that).
            check = parse_hotkey(self.hotkey)
            self.dropped_hotkey = saved if check is None else ""
            self.hotkey = check.display if check is not None else DEFAULT_HOTKEY
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
            # Up to v0.9.12 设置 › 嘉宾特效 › 音乐 turned the sound on or off: its 无 is 静音 now.
            muted = settings.get("sound_muted", settings.get("love_music") == "off")
            self.sound_muted = muted is True
            self.scene_sounds = _scene_sounds(
                settings.get("scene_sounds"), custom_sound_dir(self.root), unlisted=settings.get("scene_songs") is not True
            )
            # A scene this version has (one replaced is its replacement), else 经典.
            scene = love_scenes.shown(str(settings.get("quick_scene", "") or ""))
            self.quick_scene = scene if scene in love_scenes.KEYS else "classic"
            # None saved stays none (turned off, or it was 检查's); a key that is no hotkey (one in everyday
            # use too, Shift+A or Ctrl+C: parse_hotkey) is the default again; the same as 检查's is none. When 检查 had none,
            # or one that is none now, the 场景 hotkey may have taken the key 检查 comes back to: it keeps it, 检查 stays none.
            saved_effect = settings.get("effect_hotkey", DEFAULT_EFFECT_HOTKEY)
            effect = parse_hotkey(two_keys(str(saved_effect or "")))
            self.effect_hotkey = "" if saved_effect == "" else effect.display if effect is not None else DEFAULT_EFFECT_HOTKEY
            self.dropped_effect_hotkey = str(saved_effect or "") if effect is None else ""
            if self.hotkey == self.effect_hotkey:
                if settings.get("hotkey") and not self.dropped_hotkey:
                    self.effect_hotkey = ""
                else:
                    self.hotkey = ""
            if self.dropped_hotkey:
                _log.info("Hotkey %s is no hotkey now: %s instead.", self.dropped_hotkey, self.hotkey or "none")
            if self.dropped_effect_hotkey:
                _log.info("场景 hotkey %s is no hotkey now: %s instead.", self.dropped_effect_hotkey, self.effect_hotkey or "none")
            # v0.6.0 saved "key" (green) or "alpha" (clear), v0.6.1 "key": each is on, and clear now.
            self.stream_mode = "on" if settings.get("stream_mode") in ("on", "key", "alpha") else ""
            # Up to v0.9.14 直播模式 had a 测试框 (stream_test_frame), a red frame in 直播画面: gone, and not read.
            # Up to v0.9.14 检查 › 提醒 could leave 黑名单 or 嘉宾 out (check_blacklist, check_likes): every check
            # looks for both now, and what was saved is not read.
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
            # Up to v0.9.14: 声音 (none saved is 100) and 嘉宾 › 场景 ("off" when off, as 无 was before it). Taken
            # from a file read whole only, for _fold_old_settings.
            self._old_volume = _volume(settings.get("sound_volume"))
            self._old_scenes_off = settings.get("love_scene") == "off"
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            backup = _set_aside(self.settings_path)
            _log_set_aside(exc, self.settings_path, backup)
            # The songs uploaded in 场景管理 are still in their folder: back in their 场景's, as for a file of v0.9.15's.
            # Saved without them, they would be gone for good.
            unlisted = _scene_sounds(None, custom_sound_dir(self.root), unlisted=True)
            self.scene_sounds = {**unlisted, **self.scene_sounds}
            self._warn(self.settings_path, backup, "设置文件坏了，已备份，先用默认设置", "设置文件读不了，这次改动不保存")

    def save_scans(self) -> None:
        """Never raises: 记录 are the least of the files, and one that cannot be saved must not cost a check its marks."""
        if not self._saves(self.history_path):
            return
        try:
            _atomic_write(self.history_path, {"scans": self.scans[:_MAX_SCANS]})
        except OSError as exc:
            _log.warning("记录 could not be saved: %s", exc)

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
        self.me = Scenes()
        self.scans = []
        self.hotkey = DEFAULT_HOTKEY
        # 基础模式 and 手动检查 again, until agreed to otherwise.
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
        self.sound_muted = False
        # The player's own sounds go with the rest.
        self.scene_sounds = {}
        shutil.rmtree(custom_sound_dir(self.root), ignore_errors=True)
        self.quick_scene = "classic"
        self.effect_hotkey = DEFAULT_EFFECT_HOTKEY
        self.dropped_hotkey = ""
        self.dropped_effect_hotkey = ""
        self.stream_mode = ""
        self.consented = []
        self.disclaimer_accepted = False
        self.stream_guided = False
        self.load_warning = ""
        self.save_entries()
        self.save_likes()
        self.save_scans()
        self.save_settings()

