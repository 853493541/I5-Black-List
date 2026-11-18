"""Golden data for the Rust store (rust/data/src/store): the Python Store driven through a scripted set of changes.

Runs in a data folder of its own under /tmp (APPDATA and XDG_CONFIG_HOME pointed there, never the player's), with the
clock frozen, so the Rust port can replay the same steps and must write the same bytes. Writes:

    rust/data/tests/golden/store/<case>/input/   the files as an older version left them (what the case starts from)
    rust/data/tests/golden/store/<case>/output/  every file the Python Store left after the steps

Run from the checkout's root: python tools/rust_golden_store.py
"""

from __future__ import annotations

import os
import shutil
import struct
import sys
import tempfile
import time
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "rust" / "data" / "tests" / "golden" / "store"
FROZEN = datetime(2026, 11, 18, 9, 30, 5, tzinfo=timezone.utc)


def _stub_qt() -> None:
    """storage needs love_scenes' keys only; its module imports Qt for the stage, which this script never draws."""
    try:
        import PySide6.QtCore  # noqa: F401
    except ImportError:
        qt = types.ModuleType("PySide6")
        core = types.ModuleType("PySide6.QtCore")
        core.QPointF = core.QRectF = object
        qt.QtCore = core
        sys.modules.update({"PySide6": qt, "PySide6.QtCore": core})


class _Frozen(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ANN001
        return FROZEN.astimezone(tz) if tz is not None else FROZEN.replace(tzinfo=None)


def _wav(path: Path, seconds: float) -> None:
    rate, frames = 8000, int(8000 * seconds)
    data = b"\x00\x00" * frames
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(data)) + data
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def _write(path: Path, text: str, bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def _old_files(folder: Path) -> None:
    """A data folder as v0.9.14 / v0.9.15 left it: old keys, a BOM, two songs not listed, one lobby saved twice."""
    _write(folder / "blacklist.json", """{"entries": [
 {"name": "示例坏人...", "reasons": ["炸房", "演戏", "挂机"], "note": "开局就走", "added_at": "2026-01-02T03:04:05+00:00"},
 {"name": "Bad Guy", "tags": ["贴脸"], "reason": "  场外 报点 ", "added_at": "2026-01-03T00:00:00+00:00"},
 {"name": "。。。", "tags": []},
 {"name": 12345, "tags": "场外"}
]}""", bom=True)
    _write(folder / "likes.json", """{"likes": [
 {"name": "心动小鹿", "nickname": "  小  鹿 ", "reason": "好人", "added_at": "2026-02-01T00:00:00+00:00", "theme": "champagne"},
 {"name": "心动星星", "added_at": "2026-02-02T00:00:00+00:00", "theme": ""},
 {"name": "心动星星", "added_at": "dup"},
 {"name": "示例嘉宾", "scenes": ["ice", "stars", "ice"], "no_scene": true}
],
"combos": [{"names": ["心动小鹿", "心动星星"], "scenes": ["lace"]}, {"names": ["心动小鹿", "心动小鹿"]}],
"me": {"scenes": ["neon"], "random": false}}""")
    _write(folder / "settings.json", """{"hotkey": "Ctrl+Alt+F11", "effect_hotkey": "Ctrl+S", "auto_capture": true,
 "panel_pos": [10, "20"], "window_size": [800, 700], "theme": "紫色", "appearance": "dark", "player_name": "心动星星…",
 "custom_tags": ["演戏", "其他", "a,b"], "hidden_tags": ["挂机", "nope"], "column_order": [1, 0, 2, 3],
 "column_widths": [100, "150", 300, 2001], "sound_volume": 47, "love_scene": "off", "love_music": "off",
 "scene_sounds": {"champagne": {"volume": 80, "file": "angel-1.wav", "name": "歌.mp3", "start": 1, "length": 2.5},
                  "ice": {"volume": 3}, "lace": {"volume": 100}},
 "quick_scene": "champagne", "stream_mode": "key", "consented": ["auto", "full", "x"], "safe_mode": false,
 "welcomed": true, "disclaimer_accepted": true}""")
    _write(folder / "history.json", """{"scans": [
 {"at": "2026-11-17T20:00:00+00:00", "elapsed": 1.234, "names": [
  {"seat": 1, "name": "心动小鹿"}, {"seat": 2, "name": "示例坏人", "unclear": false}, {"seat": 3, "name": "", "unclear": true}]},
 {"at": "2026-11-17T19:00:00+00:00", "elapsed": 2, "names": [
  {"seat": 1, "name": "心动小鹿"}, {"seat": 2, "name": "示例坏人"}]},
 {"at": "2026-11-16T19:00:00+00:00", "elapsed": null, "names": [{"seat": "4", "name": "心动星星"}]}
]}""")
    sounds = folder / "custom_sounds"
    sounds.mkdir(parents=True, exist_ok=True)
    _wav(sounds / "angel-1.wav", 0.5)
    _wav(sounds / "angel-2.wav", 1.25)
    _wav(sounds / "ice-1.wav", 0.75)
    (sounds / "ice-x.wav").write_bytes(b"not a wav")


def _steps(store, model) -> None:  # noqa: ANN001
    """The same steps rust/data/tests/store_golden.rs replays."""
    store.add("示例坏人二号", "炸房，开局就走", ("炸房", "新标签"))
    store.add("示例坏人二号")  # there already
    store.add("。。")  # no letters
    store.update_at(1, "Bad Guy Two", ("贴脸", "场外"), "又见到了")
    store.remove_at(2)
    store.rename_tag("演戏", "演员")
    store.remove_custom_tag("炸房")
    store.import_rows([("示例坏人三号", ("贴脸",), "新来的", -1), ("示例坏人二号加长", ("挂机",), "又一个原因", 2)])
    store.recheck_tags()
    store.add_like("心动小鹿")  # there already
    store.add_like("新的嘉宾", "  昵 称 ", "好人", model.Scenes(("lyre", "champagne"), False))
    store.update_like(0, "心动小鹿改名", "鹿", "更好", model.Scenes((), True))
    store.move_like(0, 2)
    store.set_me(model.Scenes(("classic",), True))
    store.set_scene_volume("stars", 35)
    store.choose_scene_song("angel", "angel-2.wav")
    store.add_scan([{"seat": i, "name": f"示例玩家{i}", "unclear": i == 5} for i in range(1, 13)], 1.005)
    store.add_scan([{"seat": 5, "name": "心动小鹿改名"}], 0.5)
    store.hotkey, store.theme, store.names_hidden = "Ctrl+F9", "绿色", True
    store.save_settings()


def main() -> None:
    _stub_qt()
    sys.path.insert(0, str(ROOT))
    work = Path(tempfile.mkdtemp(prefix="rust-golden-store-"))
    os.environ.update({"APPDATA": str(work), "XDG_CONFIG_HOME": str(work), "TZ": "UTC"})
    time.tzset()
    from blacklist_detect import model, storage

    storage.datetime = _Frozen
    shutil.rmtree(GOLDEN, ignore_errors=True)
    for case in ("migrate", "fresh"):
        folder = work / case
        if case == "migrate":
            _old_files(folder)
        else:
            folder.mkdir(parents=True)
        shutil.copytree(folder, GOLDEN / case / "input")
        store = storage.Store(folder)
        _steps(store, model)
        shutil.copytree(folder, GOLDEN / case / "output")
        (GOLDEN / case / "load_warning.txt").write_text(store.load_warning, encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    print("golden store data in", GOLDEN.relative_to(ROOT))


if __name__ == "__main__":
    main()
