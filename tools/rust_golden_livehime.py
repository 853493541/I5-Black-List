"""Golden data for the Rust 直播模式 code (rust/win/src/livehime): what the Python code makes of 直播姬's scene
files and logs, and where 直播画面 draws the game.

    QT_QPA_PLATFORM=offscreen python tools/rust_golden_livehime.py rust/win/tests/golden/livehime.json

Every case is made up here from a fixed seed (window titles are made-up: 心动小鹿的游戏, never a player's):
- on_canvas: OBS placements of every bounds type and alignment over many captured window sizes;
- placements: scene collections parsed (livehime_layout.placements);
- studio: 直播姬 logs grown a piece at a time and read by StudioWatch;
- scene: game_and_widnow_info lines grown a piece at a time and read by SceneWatch, with status() and game_capture();
- follow: StreamMirror._where_livehime_has_it and _fit run on a stand-in window, the scene file, the game's window and
  the screens given;
- masked: ui_widgets.masked_name;
- wgc: wgc.read / wgc.words on answers, and wgc_diagnose.verdict on made-up sets of answers, with each test's report line.
Runs in a data folder of its own and makes no sound.
"""

from __future__ import annotations

import json
import os
import random
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("APPDATA", tempfile.mkdtemp(prefix="golden-appdata-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, QRect  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect import livehime, livehime_layout, ui_overlay, ui_stream, wgc, wgc_diagnose  # noqa: E402
from blacklist_detect.livehime_layout import Placement  # noqa: E402
from blacklist_detect.ui_widgets import masked_name  # noqa: E402

TITLE = ui_stream.TITLE
GAMES = ("心动小鹿的游戏", "MuMu模拟器12", "心动星星#3A副本")
SIZES = [(1920, 1080), (1280, 720), (2560, 1440), (1600, 900), (800, 450), (3840, 2160), (1366, 768), (1, 1), (1922, 1112),
         (1440, 1080), (720, 1280)]  # fmt: skip
ALIGNS = (0, 1, 2, 4, 5, 6, 8, 9, 10)
rand = random.Random(20261118)


def placement(**changes) -> Placement:  # noqa: ANN003
    base = dict(scene="场景1", name="窗口捕获", title=GAMES[0], window_class="Qt51517QWindowIcon", exe="game.exe", client_area=True,
                whole_screen=False, visible=True, pos=(0.0, 0.0), scale=(1.0, 1.0), crop=(0, 0, 0, 0), bounds_type=0,
                bounds=(0.0, 0.0), bounds_align=0, align=5, rotation=0.0)  # fmt: skip
    base.update(changes)
    return Placement(**base)


def random_placement(**changes) -> Placement:  # noqa: ANN003
    crop = tuple(rand.choice((0, 0, 0, rand.randint(0, 400))) for _ in range(4))
    base = dict(
        pos=(round(rand.uniform(-500, 2500), 3), round(rand.uniform(-500, 1500), 3)),
        scale=(round(rand.uniform(0.1, 3), 5), round(rand.uniform(0.1, 3), 5)),
        crop=crop, bounds_type=rand.choice((0, 1, 2, 3, 4, 5, 6, 9)),
        bounds=(round(rand.uniform(0, 2500), 2), round(rand.uniform(0, 1500), 2)),
        bounds_align=rand.choice(ALIGNS), align=rand.choice(ALIGNS),
    )  # fmt: skip
    base.update(changes)
    return placement(**base)


def on_canvas_cases() -> list:
    out = []
    for _ in range(400):
        item = random_placement()
        width, height = rand.choice(SIZES)
        out.append({"placement": asdict(item), "size": [width, height], "rect": list(item.on_canvas(width, height))})
    return out


def item_json(item: Placement, uuid: str) -> dict:
    out = {"name": item.name, "source_uuid": uuid, "visible": item.visible, "pos": {"x": item.pos[0], "y": item.pos[1]},
           "scale": {"x": item.scale[0], "y": item.scale[1]}, "bounds_type": item.bounds_type,
           "bounds": {"x": item.bounds[0], "y": item.bounds[1]}, "bounds_align": item.bounds_align, "align": item.align,
           "rot": item.rotation}  # fmt: skip
    for side, value in zip(("left", "top", "right", "bottom"), item.crop, strict=True):
        out[f"crop_{side}"] = value
    return out


def collection(scenes: dict[str, list[Placement]], current: str, extras: bool = False) -> str:
    sources, count = [], 0
    for scene, items in scenes.items():
        listed = []
        for item in items:
            count += 1
            uuid = f"u{count}"
            window = ":".join(part.replace("#", "#22").replace(":", "#3A") for part in (item.title, item.window_class, item.exe))
            settings = {"window": window}
            if not item.client_area:
                settings["client_area"] = False
            if item.whole_screen:
                settings["capture_from_whole_screen"] = True
            sources.append({"id": "window_capture", "name": item.name + str(count), "uuid": uuid, "settings": settings})
            entry = item_json(item, uuid)
            entry["name"] = item.name + str(count)
            if extras and count % 3 == 0:
                del entry["source_uuid"]  # found by name
            if extras and count % 4 == 0:
                for key in ("align", "bounds", "rot", "crop_left"):
                    entry.pop(key, None)
            listed.append(entry)
        if extras:
            sources.append({"id": "image_source", "name": "背景", "uuid": "img"})
            listed.insert(0, {"name": "背景", "source_uuid": "img"})
        sources.append({"id": "scene", "name": scene, "uuid": f"s-{scene}", "settings": {"items": listed}})
    return json.dumps({"current_scene": current, "sources": sources}, ensure_ascii=False)


def scene_of(rand_items: int) -> list[Placement]:
    items = [random_placement(title=rand.choice((*GAMES, TITLE, "")), visible=rand.random() > 0.2,
                              client_area=rand.random() > 0.3, whole_screen=rand.random() < 0.1,
                              rotation=rand.choice((0.0, 0.0, 0.0, 90.0))) for _ in range(rand_items)]  # fmt: skip
    return items


def placements_cases(folder: Path) -> list:
    out = []
    for index in range(12):
        scenes = {f"场景{n}": scene_of(rand.randint(0, 5)) for n in range(rand.randint(1, 3))}
        text = collection(scenes, rand.choice([*scenes, "别的"]), extras=index % 2 == 1)
        path = folder / f"collection{index}.json"
        path.write_text(text, encoding="utf-8")
        current, placed = livehime_layout.placements(path)
        out.append({"text": text, "current": current, "placed": [asdict(item) for item in placed]})
    return out


STUDIO_LINES = [
    "[17476:1014/002232.668:INFO:obs.cc(12)] is_double_screen-0 main_width-1920 main_height-1080",
    "[17476:1014/002240.001:INFO:view.cc(3)] BililiveOBSView::OnLiveProgramModeChanged : 1",
    "[17476:1014/002301.500:INFO:scene.cc(9)] scene '场景1' add item : 窗口捕获2",
    "[17476:1014/002330.120:INFO:program.cc(4)] [ProgramMode] ButtonPressed OpenProgramView",
    "[tid:8:2026-10-14/14-39-08:INFO] scene 'x' remove item : 图片",
    "[tid:8:2026-10-14/14-39-09:INFO] is_double_screen-1 main_width-1080 main_height-1920",
    "something else entirely, no stamp, scene '' add item : y",
    "--- Application Startup ---",
    "[17476:1015/101010.000:INFO:view.cc(3)] BililiveOBSView::OnLiveProgramModeChanged : 0",
    "垃圾   is_double_screen-1 main_width-2560 main_height-1440",
    "[1:1015/111111.111:INFO] scene 'a' add item : b\r[2:1015/121212.000:INFO] [ProgramMode] ButtonPressed OpenProgramView",
]


def studio_cases(folder: Path) -> list:
    out = []
    for index in range(6):
        path = folder / f"livehime{index}.log"
        path.write_bytes(b"")
        watch = livehime_layout.StudioWatch(path, reach=rand.choice((8 * 1024 * 1024, 300)))
        steps = []
        for _ in range(8):
            if rand.random() < 0.1:
                data = b""
                path.write_bytes(data)  # 直播姬 started a new log
                mode = "reset"
            else:
                lines = rand.sample(STUDIO_LINES, rand.randint(1, 4))
                data = ("\n".join(lines) + ("\n" if rand.random() < 0.8 else "")).encode()
                with open(path, "ab") as log:
                    log.write(data)
                mode = "append"
            found = watch.studio()
            steps.append({"mode": mode, "data": data.decode(), "studio": {**asdict(found), "unsynced": found.unsynced()}})
        out.append({"reach": watch.reach, "steps": steps})
    return out


def scene_line(items: list[tuple[str, bool]]) -> str:
    body = [{"process_info": f"{title}:Qt5QWindow:game.exe", "is_visible": shown} for title, shown in items]
    return "[1:1014/002232.668:INFO] game_and_widnow_info : " + json.dumps(body, ensure_ascii=False)


def scene_cases(folder: Path) -> list:
    out = []
    for index in range(6):
        path = folder / f"bililive{index}.log"
        path.write_bytes(b"x\n" * rand.randint(0, 200_000))
        watch = livehime.SceneWatch(path)
        steps = []
        for _ in range(8):
            pick = rand.random()
            if pick < 0.15:
                data = livehime.START + b"\n"
            elif pick < 0.25:
                data = b"no newline yet " + scene_line([(TITLE, True)]).encode()
            elif pick < 0.3:
                data = b"[1:1014/0:INFO] game_and_widnow_info : not json\n"
            else:
                items = [(rand.choice((*GAMES, TITLE)), rand.random() > 0.2) for _ in range(rand.randint(0, 4))]
                data = (scene_line(items) + "\n").encode()
            with open(path, "ab") as log:
                log.write(data)
            restart = rand.random() < 0.1
            if restart:
                watch = livehime.SceneWatch(path)  # the app started again: read from the end
            scene = watch.scene()
            covers = set(rand.sample(GAMES, rand.randint(0, 2)))
            judged = livehime.status(TITLE, True, scene, lambda capture, covers=covers: capture.title in covers)
            game = livehime.game_capture(scene, TITLE)
            steps.append({
                "data": data.decode(), "restart": restart, "scene": None if scene is None else [asdict(c) for c in scene],
                "covers": sorted(covers), "status": judged, "status_no_covers": livehime.status(TITLE, True, scene),
                "game": None if game is None else asdict(game),
            })  # fmt: skip
        out.append({"start_size": path.stat().st_size, "steps": steps})
    return out


class Screen:
    def __init__(self, x: int, y: int, w: int, h: int, ratio: float) -> None:
        self.box, self.ratio = QRect(x, y, w, h), ratio

    def geometry(self) -> QRect:
        return self.box

    def devicePixelRatio(self) -> float:  # noqa: N802
        return self.ratio


def follow_cases() -> list:
    out = []
    real_native_to_logical = ui_overlay.native_to_logical
    kinds = ["fine"] * 10 + ["no file", "no ours", "no game", "turned", "closed", "stretched", "outside", "hidden ours", "region"]
    for index in range(160):
        kind = kinds[index % len(kinds)] if index < 60 else "fine"
        ratio = rand.choice((1.0, 1.25, 1.5, 2.0))
        screens = [Screen(0, 0, round(1920 / ratio), round(1080 / ratio), ratio), Screen(round(1920 / ratio), 0, 1280, 720, 1.0)]
        fw, fh = rand.choice(SIZES[:7])
        fx, fy = rand.randint(0, 600), rand.randint(0, 300)
        frame = None if kind == "closed" else (fx, fy, fx + fw, fy + fh)
        mw = rand.choice((1920, 2560, 1280))
        mine = (rand.randint(1900, 4000), 0, 0, round(mw * 9 / 16))
        mine = (mine[0], 0, mine[0] + mw, mine[3])
        logical = (round(mw / ratio), round(mine[3] / ratio))
        canvas = rand.choice(((1920, 1080), (1280, 720)))
        fit = min(canvas[0] / fw, canvas[1] / fh) if kind != "outside" else 0.3
        game = placement(title=rand.choice(GAMES), bounds_type=2, bounds=canvas, pos=(0.0, 0.0), align=5, bounds_align=0,
                         client_area=rand.random() > 0.3)  # fmt: skip
        if rand.random() < 0.5 and kind == "fine":
            game = placement(title=game.title, pos=(rand.uniform(0, 200), rand.uniform(0, 100)), scale=(fit, fit), align=5)
        ours = placement(title=TITLE, bounds_type=2, bounds=canvas, align=5)
        if kind == "outside":
            ours = placement(title=TITLE, pos=(5000.0, 5000.0), scale=(0.3, 0.3))
        if kind == "stretched":
            game = placement(title=game.title, scale=(1.0, 1.4))
        if kind == "turned":
            game = placement(title=game.title, rotation=90.0)
        if kind == "region":
            ours = placement(title=TITLE, whole_screen=True)
        if kind == "hidden ours":
            ours = placement(title=TITLE, visible=False)
        items = [placement(title="", name="图片"), game, ours] if kind != "no game" else [ours]
        if kind == "no ours":
            items = [game]
        current = "场景1"
        placed = [Placement(**{**asdict(item), "scene": current}) for item in items] + [placement(scene="别的", title=TITLE)]
        stand_in = SimpleNamespace(
            _my_rect=lambda mine=mine: mine, width=lambda w=logical[0]: w, height=lambda h=logical[1]: h,
            rect=lambda w=logical[0], h=logical[1]: QRect(0, 0, w, h),
        )  # fmt: skip
        livehime_layout.collection_path = (lambda: None) if kind == "no file" else (lambda: Path("scene.json"))
        livehime_layout.placements = lambda _path, current=current, placed=placed: (current, placed)
        livehime_layout.captured_rect = lambda _item, frame=frame: frame
        ui_overlay.native_to_logical = lambda x, y, screens=screens: real_native_to_logical(x, y, screens)
        follows, note = ui_stream.StreamMirror._where_livehime_has_it(stand_in)
        area = (round(fx / ratio), round(fy / ratio), round(fw / ratio), round(fh / ratio))
        fitted = SimpleNamespace(_area=QRect(*area), _follows=follows, width=stand_in.width, height=stand_in.height)
        scale, offset = ui_stream.StreamMirror._fit(fitted)
        plain = SimpleNamespace(_area=QRect(*area), _follows=None, width=stand_in.width, height=stand_in.height)
        plain_scale, plain_offset = ui_stream.StreamMirror._fit(plain)
        fitted._fit = lambda fitted=fitted: ui_stream.StreamMirror._fit(fitted)
        point = QPoint(area[0] + rand.randint(0, area[2]), area[1] + rand.randint(0, area[3]))
        drawn = ui_stream.StreamMirror.to_window(fitted, point)
        out.append({
            "kind": kind, "current": current, "placed": [asdict(item) for item in placed], "has_file": kind != "no file",
            "frame": frame, "mine": mine, "logical": logical,
            "screens": [[s.box.x(), s.box.y(), s.box.width(), s.box.height(), s.ratio] for s in screens],
            "follows": None if follows is None else [follows[0], follows[1].x(), follows[1].y(), follows[2].x(), follows[2].y()],
            "note": note, "area": area, "fit": [scale, offset.x(), offset.y()], "plain_fit": [plain_scale, plain_offset.x(), plain_offset.y()],
            "point": [point.x(), point.y()], "to_window": [drawn.x(), drawn.y()],
        })  # fmt: skip
    return out


def wgc_cases() -> dict:
    pick = random.Random(7)
    names = [wgc_diagnose.Test("直播画面 itself", 1).name, "control: the game window 直播姬 captures", wgc_diagnose.TASKBAR,
             *(name for name, *_rest in wgc_diagnose.WIN32), *(name for name, _without in wgc_diagnose.QT), wgc_diagnose.BY_PYTHONW]
    answers = (None, wgc.ACCEPTED, wgc.REFUSED, 0x80004005)
    sets = []
    for index in range(300):
        chosen = pick.sample(names, pick.randint(0, len(names))) if index % 3 else names
        bias = pick.random()
        tests = []
        for name in chosen:
            there = wgc.ACCEPTED if pick.random() < bias else pick.choice(answers)
            hwnd = pick.choice((0, -1, 5, 5, 5)) if name != wgc_diagnose.BY_PYTHONW else -1
            tests.append(wgc_diagnose.Test(name, hwnd, there=there, here=pick.choice((there, there, *answers))))
        owned = pick.random() < 0.5
        lines = []
        for test in tests:  # the report's own wording for each test (wgc_diagnose.report)
            shown = wgc.words(test.there) if test.hwnd else "could not be made"
            if test.hwnd > 0 and test.here != test.there:
                shown += f" (asked from where it was made: {wgc.words(test.here)})"
            if test.hwnd > 0 and test.name.endswith("(no taskbar button)"):
                shown += f"; owned {owned}"
            lines.append(f"test: {test.name}: {shown}")
        sets.append({"tests": [asdict(test) for test in tests], "owned": owned, "lines": lines, "verdict": list(wgc_diagnose.verdict(tests))})
    texts = ["0x00000000", " 0x80070057\n", "none", "", "80070057", "0X1f", "-0x1", "1_0", "zz"]
    return {"read": [[text, wgc.read(text)] for text in texts], "words": [[code, wgc.words(code)] for code in answers], "sets": sets}


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "rust/win/tests/golden/livehime.json")
    app = QApplication.instance() or QApplication([])  # noqa: F841 - native_to_logical's primary screen
    assert isinstance(QPointF(0, 0), QPointF)
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        data = {
            "title": TITLE,
            "words": livehime.WORDS,
            "on_canvas": on_canvas_cases(),
            "placements": placements_cases(work),
            "studio": studio_cases(work),
            "scene": scene_cases(work),
            "follow": follow_cases(),
            "wgc": wgc_cases(),
            "masked": [[name, masked_name(name)] for name in ("", "示", "示例坏人", "心动小鹿", "ab", "😀x", "a😀😀")],
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=None), encoding="utf-8")
    print(f"wrote {target}: " + ", ".join(f"{key} {len(value)}" for key, value in data.items() if isinstance(value, list)))


if __name__ == "__main__":
    main()
