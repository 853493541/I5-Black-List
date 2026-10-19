"""Her evening on this PC: the real app's checks, from F1 to the marks, beside a stand-in game, held to her laptop's speed.

    .venv\\Scripts\\python.exe tools\\her_flow.py <code> [<code> ...] [--cap 18] [--game 10] [--frame-ms 6]
                                                  [--checks 6] [--idle 60] [--rounds 1] [--table <file>]

<code> is a folder holding a blacklist_detect, as for tools/slow_pc.py (set BLACKLIST_DETECT_MODEL_DIR without models).
Each run is a process of its own, held to her PC's speed as slow_pc holds it (its CPUs, cap, thread count and game),
with the real MainWindow on Qt's offscreen platform, on a 1920x1080 screen at 125 %, set up as she has it: 完整模式,
手动, 直播模式 on, two 嘉宾 with a scene and one 黑名单 player in the lobby, and 350 more 黑名单 entries. The screen copy
is the sample lobby (made-up names) in her 1538x914 MuMu window; 直播姬's scene file is a copy of her layout. Checks are
pressed as F1 does (MainWindow.check_now), 5 s apart and once after --idle seconds, each shown until its scene is done.
Per check: F1 to the marks, the game's frames on time during the check and the scene, the longest stall of the app's
screen thread, the app's share of her PC, memory, names read and where the mirror is. One line per run here, every
check in --table. Data goes to folders of its own; no window is put on the screen, no key taken, no sound played.

Compare only runs made in one go on the same PC (they alternate, as slow_pc's do), never with her own times.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slow_pc import cpu_between, game, hold_to, on_time, parse_cpus, slowest_cpus, spins_per_ms  # noqa: E402

SCREEN = (1920, 1080)  # her screen, in pixels
SCALE = 1.25  # at 125 %
GAME = (191, 107, 1729, 972)  # her MuMu window's game, 1538x865, in the middle of the screen
BAR = 49  # MuMu's own bar over the game: its window is 1538x914
CANVAS = (1280, 720)  # 直播姬's canvas, and where her「Scene 1」draws the game's window on it: dragged to the left
ON_CANVAS = (0, -42, 1.04 * 720 / 914)  # edge, 42 up and 4 % bigger than 直播姬's fit (her scene file, test_stream)
GAP, SCENE_S = 5.0, 5.0  # seconds between checks, and a 嘉宾 scene's length
FILLER = 350
BLACK, GUESTS = "示例坏人", ("心动小鹿", "心动星星")  # made-up names in assets/sample-lobby.jpg
# What the proposed targets ask of a version: (summary key, most or least, limit).
TARGETS = (
    ("marks", "max", 1.5),
    ("marks_idle", "max", 2.2),
    ("frames_check", "min", 90.0),
    ("frames_scene", "min", 95.0),
    ("stall_ms", "max", 100.0),
    ("idle_cpu", "max", 2.0),
    ("memory_mb", "max", 20.0),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("code", type=Path, nargs="*", help="folders holding a blacklist_detect")
    parser.add_argument("--cap", type=float, default=18, help="percent of this whole PC the run may use (0: no cap)")
    parser.add_argument("--game", type=int, default=10, help="stand-in game threads (0: no game)")
    parser.add_argument("--frame-ms", type=float, default=6.0, help="busy time of each game frame, uncapped")
    parser.add_argument("--cpus", help="CPUs to run on, like 2-9,14-17 (default: the slowest, one per CPU of hers)")
    parser.add_argument("--her-cores", type=int, default=6)
    parser.add_argument("--her-cpus", type=int, default=12)
    parser.add_argument("--checks", type=int, default=6)
    parser.add_argument("--idle", type=float, default=60, help="seconds before the last check, the app left alone")
    parser.add_argument("--rounds", type=int, default=1, help="runs of each code, taken in turn")
    parser.add_argument("--table", type=Path, help="file for every check's numbers (default: in the temp folder)")
    parser.add_argument("--one", help=argparse.SUPPRESS)
    parser.add_argument("--frame", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    cpus = parse_cpus(args.cpus) if args.cpus else slowest_cpus(args.her_cpus)
    if args.one:
        run_one(args, cpus)
        return
    if args.frame:
        make_frame(args.frame)
        return
    if not args.code:
        parser.error("name at least one code folder")
    data = Path(tempfile.mkdtemp(prefix="her_flow_"))
    table = (args.table or data / "checks.jsonl").resolve()
    print(f"her PC on this one: CPUs {args.cpus or cpus}, held to {args.cap:g} % of this PC, "
          f"game {args.game} x {args.frame_ms:g} ms a frame; every check in {table}", flush=True)
    env = {k: v for k, v in os.environ.items()
           if k not in ("OMP_NUM_THREADS", "QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS", "QT_ENABLE_HIGHDPI_SCALING",
                        "BLACKLIST_DETECT_SOUND") and not k.startswith("__KMP_REGISTERED_LIB_")}
    local = data / "local"
    (data / "screen.json").write_text(json.dumps(offscreen_config()), encoding="utf-8")
    # Qt splits the platform's arguments at ":", so C:\... would end at the drive: the runs start in data, and
    # the file is named from there. Cut short, Qt stops the run with exit 0xC0000409 and nothing on stderr.
    env.update(LOCALAPPDATA=str(local), XDG_CONFIG_HOME=str(data), PYTHONIOENCODING="utf-8",
               QT_QPA_PLATFORM="offscreen:configfile=screen.json")
    script, frame = str(Path(__file__).resolve()), data / "lobby.npy"
    done = subprocess.run([sys.executable, script, "--frame", str(frame)], env={**env, "APPDATA": str(data / "frame")},
                          check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not frame.is_file():
        print(f"the screen copy could not be made:\n{done.stderr[-2000:]}", flush=True)
        return
    for turn in range(args.rounds):
        for code in args.code:
            run_env = {**env, "APPDATA": tempfile.mkdtemp(prefix="appdata_", dir=data)}
            command = [sys.executable, script, *sys.argv[1:], "--table", str(table), "--frame", str(frame),
                       "--one", str(code.resolve())]
            done = subprocess.run(command, env={**run_env, "HER_FLOW_ROUND": str(turn + 1)}, cwd=data, check=False,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace")
            lines = [line for line in done.stdout.strip().splitlines() if line.startswith("her_flow: ")]
            said = data / f"{code.resolve().name}-{turn + 1}.txt"
            said.write_text(done.stdout + "\n" + done.stderr, encoding="utf-8")
            print("\n".join(line[10:] for line in lines) if lines else f"{code}: no result (exit {done.returncode}), see {said}",
                  flush=True)


def offscreen_config() -> dict:
    """Qt's offscreen platform, configfile=: one screen of her size, at 120 dpi as Windows has it at 125 %."""
    return {"synchronousWindowSystemEvents": False, "windowFrameMargins": False,
            "screens": [{"name": "her screen", "x": 0, "y": 0, "width": SCREEN[0], "height": SCREEN[1],
                         "logicalDpi": 96 * SCALE, "logicalBaseDpi": 96, "dpr": 1}]}


def mumu_window() -> tuple[int, int, int, int]:
    """Her MuMu window in desktop pixels: the game with MuMu's bar over it."""
    left, top, right, bottom = GAME
    return left, top - BAR, right, bottom


def logical(rect: tuple[int, int, int, int], scale: float = SCALE) -> tuple[int, int, int, int]:
    """A rectangle in desktop pixels as (x, y, width, height) in Qt's units on her screen."""
    left, top, right, bottom = rect
    return round(left / scale), round(top / scale), round((right - left) / scale), round((bottom - top) / scale)


def screen_frame(crop, game_box, fill=None):  # noqa: ANN001, ANN201
    """Her whole screen: the game screen the lobby crop places (game_box), in her MuMu window on a blue desktop, as
    slow_pc builds it; fill paints the game one colour instead (the lobby gone, the game on)."""
    import numpy as np
    from PIL import Image

    left, top, right, bottom = (round(v) for v in game_box)
    pad = ((max(0, -top), max(0, bottom - crop.shape[0])), (max(0, -left), max(0, right - crop.shape[1])), (0, 0))
    shot = np.pad(crop, pad, mode="edge")[top + pad[0][0]:bottom + pad[0][0], left + pad[1][0]:right + pad[1][0]]
    size = (GAME[2] - GAME[0], GAME[3] - GAME[1])
    canvas = Image.new("RGB", SCREEN, (32, 64, 112))
    picture = Image.new("RGB", size, fill) if fill else Image.fromarray(shot).resize(size, Image.LANCZOS)
    canvas.paste(picture, GAME[:2])
    canvas.paste(Image.new("RGB", (size[0], BAR), (238, 240, 244)), mumu_window()[:2])
    return np.asarray(canvas)


def make_frame(out: Path) -> None:
    """The lobby screen, made once with this checkout's code so that every version reads the same picture."""
    import numpy as np
    from PIL import Image

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from blacklist_detect import pipeline

    crop = np.asarray(Image.open(Path(pipeline.__file__).parent / "assets" / "sample-lobby.jpg").convert("RGB"))
    np.save(out, screen_frame(crop, pipeline.check_rgb(crop, []).game_box))


def livehime_files(local: Path, mirror: str) -> None:
    """A copy of her 直播姬 for the app to read, under a LOCALAPPDATA of the run's own: its log naming the scene's
    captures (the game, then mirror, the app's 直播画面), and its scene collection with her「Scene 1」. Her real
    直播姬 files are never read."""
    folder = local / "bililive" / "User Data"
    (folder / "10001" / "Scene Collection").mkdir(parents=True, exist_ok=True)
    mumu = "MuMu模拟器12:Qt5156QWindowIcon:MuMuPlayer.exe"  # title:class:exe, as 直播姬 writes a window
    ours = f"{mirror}:Qt6110QWindowIcon:python.exe"
    scene = [{"process_info": mumu, "is_visible": True}, {"process_info": ours, "is_visible": True}]
    (folder / "bililive_debug.log").write_text(
        "--- Application Startup ---\n[0000/000000.000:INFO] game_and_widnow_info : " + json.dumps(scene) + "\n",
        encoding="utf-8")
    x, y, zoom = ON_CANVAS
    collection = {"current_scene": "Scene 1", "sources": [
        {"id": "scene", "name": "Scene 1", "settings": {"items": [
            {"name": "MuMu", "pos": {"x": x, "y": y}, "scale": {"x": zoom, "y": zoom}, "align": 5,
             "bounds_type": 0, "visible": True},
            {"name": "直播画面", "pos": {"x": 0, "y": 0}, "scale": {"x": 1, "y": 1}, "align": 5, "bounds_type": 2,
             "bounds": {"x": CANVAS[0], "y": CANVAS[1]}, "bounds_align": 0, "visible": True}]}},
        {"id": "window_capture", "name": "MuMu", "settings": {"window": mumu, "client_area": False}},
        {"id": "window_capture", "name": "直播画面", "settings": {"window": ours, "client_area": True}}]}
    (folder / "10001" / "Scene Collection" / "her.json").write_text(json.dumps(collection, ensure_ascii=False),
                                                                    encoding="utf-8")


def seed_store(store, scene: str, filler: int = FILLER) -> None:  # noqa: ANN001
    """Her list and settings: 完整模式, 手动, 直播模式 on, two 嘉宾 with a scene, one 黑名单 player in the lobby
    and filler more. Every name made up; none of the filler is like a name in the lobby."""
    from blacklist_detect.model import Scenes

    for number in range(filler):
        store.add(f"zq{number:04d}xv")
    store.add(BLACK)
    for name in GUESTS:
        store.add_like(name, scenes=Scenes(keys=(scene,)))
    if "full" not in store.consented:  # 完整模式 agreed to, as she did
        store.consented = type(store.consented)([*store.consented, "full"])
    store.safe_mode = False
    store.auto_capture = False
    store.stream_mode = "on"
    store.stream_guided = True
    store.disclaimer_accepted = True
    store.first_run = False
    store.save_entries()
    store.save_likes()
    store.save_settings()


def longest_stall(ticks: list[float], start: float, end: float, every: float = 0.016) -> float:
    """The longest the screen's thread was kept from a tick due every `every` seconds, between start and end, in
    seconds: the gap between ticks beyond the interval. A gap that spans start or end counts."""
    inside = [at for at in ticks if start <= at <= end]
    before = [at for at in ticks if at < start][-1:]
    after = [at for at in ticks if at > end][:1]
    edges = before + inside + after
    gaps = [b - a for a, b in zip(edges, edges[1:], strict=False)]
    return max(0.0, max(gaps, default=end - start) - every)


def her_share(cpu_seconds: float, span: float, cap: float, cpu_count: int, cpus: int) -> float:
    """CPU seconds as a percent of what her PC had in span seconds: cap percent of this PC, or the CPUs given."""
    have = span * (cpu_count * cap / 100 if cap else cpus)
    return 100.0 * cpu_seconds / have if have > 0 else float("nan")


def summarize(rows: list[dict]) -> dict:
    """One run's checks in a few numbers: the idle one is the last, the rest are the short gaps. CPU between checks
    is over each gap's quiet part only (after the result panel's lobby lookups stop); a gap without one is left out."""
    short, last = rows[:-1] or rows, rows[-1]
    median = lambda key, of=short: statistics.median(row[key] for row in of)  # noqa: E731
    quiet = [row for row in rows if row["quiet_s"] > 0 and not math.isnan(row["idle_cpu"])]
    rss = [row["rss_mb"] for row in rows]
    return {
        "marks": median("marks"),
        "marks_idle": last["marks"],
        "frames_check": median("frames_check", rows),
        "frames_scene": median("frames_scene", rows),
        "stall_ms": max(row["stall_ms"] for row in rows),
        "check_cpu": median("check_cpu", rows),
        "idle_cpu": median("idle_cpu", quiet) if quiet else float("nan"),
        "quiet_s": median("quiet_s", [row for row in quiet if row is not last] or [{"quiet_s": 0.0}]),
        "quiet_idle_s": last["quiet_s"],
        "memory_mb": rss[-1] - rss[min(2, len(rss) - 1)],
        "names": min(row["names"] for row in rows),
        "mirror": ",".join(sorted({row["mirror"] for row in rows})),
    }


def summary_line(label: str, threads: str, first: dict, summary: dict, idle: float, screen: tuple) -> str:
    """One run in one line, named by its code's folder (versions under work all say the last release's number)."""
    (_x, _y, width, height), ratio = screen
    return (f"her_flow: {label} on {threads} threads, screen {width}x{height} at {ratio:g}: first check "
            f"{first['marks']:.2f} s | F1 to marks {summary['marks']:.2f} s, {summary['marks_idle']:.2f} s after {idle:g} s "
            f"idle ({summary['names']} names) | frames on time {summary['frames_check']:.0f} % in checks, "
            f"{summary['frames_scene']:.0f} % in scenes | longest stall {summary['stall_ms']:.0f} ms | app "
            f"{summary['check_cpu']:.0f} % of her PC in checks, {summary['idle_cpu']:.1f} % between (over the last "
            f"{summary['quiet_s']:.1f} s of each {GAP:g} s gap and {summary['quiet_idle_s']:.0f} s of the idle one, after the "
            f"lobby lookups stop) | memory {summary['memory_mb']:+.0f} MB from check 3 | mirror {summary['mirror']}")


def verdicts(summary: dict) -> list[str]:
    """PASS or FAIL against each proposed target."""
    said = []
    for key, way, limit in TARGETS:
        value = summary[key]
        ok = value <= limit if way == "max" else value >= limit
        said.append(f"{key} {'PASS' if ok else 'FAIL'}")
    return said


def stub(ui, state, local: Path) -> None:  # noqa: ANN001
    """Everything that would reach this PC's screen, windows, keys, network or 直播姬, in every module that has it:
    the screen copy is state.frame, no window is in front of another, nothing is pinned or brought forward."""
    from PySide6.QtCore import QRect

    from blacklist_detect import hotkey, livehime, livehime_layout, single, ui_stream, updater

    band = getattr(sys.modules.get("blacklist_detect.capture"), "TITLE_BAND_FRACTION", 0.4)
    fakes = {
        "capture_displays": lambda: [state.frame],  # STUB: the screen copy is her screen
        "capture_top_band": lambda fraction=band: state.frame[:max(1, round(SCREEN[1] * fraction))],  # STUB
        "window_order": lambda: (),  # STUB: no window order; the game's window is _window_frame's
        "lock_foreground": lambda locked: None,  # STUB: the foreground lock does nothing
        "allow_any_foreground": lambda: None,  # STUB
        "virtual_origin": lambda: (0, 0),  # STUB: her one screen
        "exclusive_fullscreen": lambda: False,  # STUB: MuMu is a window
        "_pin_topmost": lambda widget: None,  # STUB: offscreen windows have no real handle to pin
        "_round_corners": lambda widget, edge: None,  # STUB
        "_caption_color": lambda widget: None,  # STUB
        "bring_to_front": lambda hwnd: None,  # STUB
    }
    for name, module in list(sys.modules.items()):
        if module is not None and (name == "blacklist_detect" or name.startswith("blacklist_detect.")):
            for attribute, fake in fakes.items():
                if hasattr(module, attribute):
                    setattr(module, attribute, fake)
    updater.app_root = lambda: None  # STUB: never looks for an update (as when run from source)

    def apply(self, spec) -> bool:  # noqa: ANN001 - STUB: no real hotkey; F1 is check_now
        self.clear()
        self.active = spec.display if spec is not None else ""
        return True

    hotkey.GlobalHotkey.apply = apply
    running = single.running
    single.running = lambda name: True if name == livehime.PROCESS else running(name)  # STUB: 直播姬 is running
    mumu = mumu_window()
    livehime_layout.captured_rect = lambda placement: mumu if "MuMu" in placement.title else None  # STUB
    livehime_layout.window_rect = lambda hwnd: None  # STUB: the mirror's place is Qt's
    ui_stream.StreamMirror.ask_windows = lambda self: None  # STUB: Windows' capture check needs a real window
    ui_stream.StreamMirror.diagnose = lambda self: None  # STUB
    livehime_files(local, ui_stream.TITLE)

    def window_frame(self, screen, innermost: bool) -> QRect:  # noqa: ANN001 - STUB: the MuMu window
        return QRect(*logical(GAME if innermost else mumu))

    ui.MainWindow._window_frame = window_frame


def run_one(args, cpus: list[int]) -> None:  # noqa: ANN001, C901, PLR0915
    import faulthandler

    import numpy as np
    import psutil

    faulthandler.enable()  # a crash in Paddle or Qt says where, in the run's own output
    proc = psutil.Process()
    proc.cpu_affinity(cpus)
    sys.path.insert(0, args.one)
    from blacklist_detect import __version__, paths

    threads = paths.ocr_threads(args.her_cores) if hasattr(paths, "ocr_threads") else str(args.her_cpus)
    os.environ["OMP_NUM_THREADS"] = threads  # read once, when Paddle loads
    spins = spins_per_ms()
    if args.cap:
        hold_to(args.cap)
    from PySide6.QtCore import QEventLoop, Qt, QTimer
    from PySide6.QtWidgets import QApplication

    from blacklist_detect import love_scenes, ui
    from blacklist_detect.storage import Store

    lobby = np.load(args.frame)
    in_game = lobby.copy()
    in_game[GAME[1]:GAME[3], GAME[0]:GAME[2]] = (40, 90, 60)  # the lobby gone, the game on

    class State:
        frame = lobby
        marks_at = 0.0
        result = None

    state = State()
    scene = "classic" if "classic" in love_scenes.KEYS else love_scenes.KEYS[0]
    seed_store(Store(), scene)
    app = QApplication(sys.argv[:1])
    stub(ui, state, Path(os.environ["LOCALAPPDATA"]))
    checked = ui.MainWindow._on_checked

    def on_checked(self, status, value) -> None:  # noqa: ANN001 - the marks are up when this returns
        checked(self, status, value)
        state.marks_at = time.time()
        state.result = value if status == "ok" else None

    ui.MainWindow._on_checked = on_checked
    window = ui.MainWindow()
    ticks: list[float] = []
    probe = QTimer()
    probe.setTimerType(Qt.PreciseTimer)
    probe.setInterval(16)
    probe.timeout.connect(lambda: ticks.append(time.time()))

    def pump(seconds: float, until=None) -> None:  # noqa: ANN001
        loop, end = QEventLoop(), time.time() + seconds
        look = QTimer()
        look.setInterval(20)
        look.timeout.connect(lambda: loop.quit() if time.time() >= end or (until is not None and until()) else None)
        look.start()
        loop.exec()
        look.stop()

    def check() -> dict:
        state.frame, state.marks_at, state.result = lobby, 0.0, None
        pressed, cpu0 = time.time(), sum(proc.cpu_times()[:2])
        window.check_now()
        pump(30, lambda: state.marks_at > 0)
        cpu1 = sum(proc.cpu_times()[:2])
        shown = state.marks_at or time.time()
        pump(SCENE_S + 10, lambda: time.time() > shown + 0.5 and not window.love.playing())
        ended = time.time()
        result = state.result
        follows = getattr(window.stream, "_follows", None)
        mirror = "none" if window.stream._frame.isEmpty() else "follows" if follows is not None else "fitted"
        state.frame = in_game  # the game starts: the lobby is gone and the marks go with it
        return {"pressed": pressed, "shown": shown, "ended": ended, "marks": shown - pressed,
                "check_cpu_s": cpu1 - cpu0, "rss_mb": proc.memory_info().rss / 2**20, "mirror": mirror,
                "names": sum(1 for slot in result.names if slot.visible) if result is not None else 0,
                "read": result.timings.get("read", 0.0) if result is not None else 0.0}

    window.start_warmup()
    pump(120, lambda: window._warm_state in ("ready", "failed"))
    probe.start()
    first = check()  # finds the lobby; later checks look where it was, as hotkey checks do
    pump(GAP)

    import multiprocessing as mp

    ctx = mp.get_context("spawn")
    frames, stop = ctx.Queue(), ctx.Event()
    workers = [ctx.Process(target=game, args=(cpus, spins * args.frame_ms, stop, frames)) for _ in range(args.game)]
    for worker in workers:
        worker.start()
    pump(6.0 if workers else 0.0)
    rows, gaps = [], []
    for number in range(args.checks):
        wait = args.idle if number == args.checks - 1 else GAP
        end = time.time() + wait
        # The result panel looks for the lobby every 400 ms until it is gone; CPU between checks is what follows.
        pump(wait, lambda: not window._watch_timer.isActive())
        cpu0, since = sum(proc.cpu_times()[:2]), time.time()
        pump(end - since)
        gaps.append((since, time.time(), sum(proc.cpu_times()[:2]) - cpu0))
        rows.append(check())
    stop.set()
    shown = [frames.get() for _ in workers]
    for worker in workers:
        worker.join()
    probe.stop()

    log = [frame for each in shown for frame in each]
    share = lambda seconds, span: her_share(seconds, span, args.cap, os.cpu_count(), len(cpus))  # noqa: E731
    for row, (since, until, cpu) in zip(rows, gaps, strict=True):
        row["frames_check"] = on_time(log, row["pressed"], row["shown"]) if log else float("nan")
        row["frames_scene"] = on_time(log, row["shown"], row["ended"]) if log else float("nan")
        row["stall_ms"] = 1000 * longest_stall(ticks, row["pressed"], row["ended"])
        row["check_cpu"] = share(row["check_cpu_s"], row["shown"] - row["pressed"])
        row["idle_cpu"] = share(cpu, until - since) if until - since >= 0.5 else float("nan")
        row["quiet_s"] = max(0.0, until - since) if until - since >= 0.5 else 0.0
        row["game_cpu"] = share(sum(cpu_between(each, row["pressed"], row["shown"]) for each in shown),
                                row["shown"] - row["pressed"])
        row["gap"] = until - since
    summary = summarize(rows)
    name = Path(args.one).name
    with open(args.table, "a", encoding="utf-8") as table:
        for number, row in enumerate(rows, 1):
            table.write(json.dumps({"code": name, "package": __version__, "round": os.environ.get("HER_FLOW_ROUND"),
                                    "check": number, **{k: round(v, 3) if isinstance(v, float) else v
                                                        for k, v in row.items()}}) + "\n")
    shown_on = app.primaryScreen()
    geometry = shown_on.geometry()
    screen = ((geometry.x(), geometry.y(), geometry.width(), geometry.height()), shown_on.devicePixelRatio())
    print(summary_line(name, threads, first, summary, args.idle, screen), flush=True)
    print(f"her_flow:   targets: {', '.join(verdicts(summary))}", flush=True)
    print(f"her_flow:   直播画面: {window.stream._follow_note}", flush=True)
    window._closing = True
    window.stream.enable("")
    app.quit()


if __name__ == "__main__":
    main()
