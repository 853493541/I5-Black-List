"""A weaker, busier PC like a player's, on this one: whole checks timed beside a stand-in game, to compare versions.

    .venv\\Scripts\\python.exe tools\\slow_pc.py <code> [<code> ...] [--cap 18] [--game 10] [--frame-ms 6]
                                                 [--cpus 2-9,14-17] [--her-cores 6] [--her-cpus 12] [--threads N] [--rounds 2]

<code> is a folder holding a blacklist_detect: a checkout, or a version taken out of git with
`git archive v1.0.0 blacklist_detect | tar -x -C <folder>`. Without the models in it, set BLACKLIST_DETECT_MODEL_DIR.
Each run is a process of its own:
    - on this PC's slowest cores, one CPU for each of hers (--her-cpus), so no thread waits on a faster core;
    - inside a Windows job held to --cap percent of this whole PC: her PC's total speed;
    - with the thread count that version picks on her PC (--her-cores, --her-cpus);
    - beside a stand-in game: --game threads drawing 60 frames a second, each frame busy --frame-ms on this PC.
It prints a check's time, how much of her PC the app and the game used, and how many of the game's frames came on
time before and during the checks. The checks read the sample lobby (made-up names) in a 1538 px window on a
1920x1080 screen, as her MuMu window was. Data goes to a folder of its own, and nothing plays a sound.

The cap stops the whole job in short bursts once its share is used, as Chrome's CPU throttling does: good for comparing
versions on one PC, not a copy of hers (hyperthreads, heat and memory speed are not copied). Compare only runs made
on the same PC with the same settings, never with her own times.
"""

from __future__ import annotations

import argparse
import ctypes
import multiprocessing as mp
import os
import statistics
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

FRAME = 1 / 60
SCREEN, WINDOW = (1920, 1080), (1538, 865)  # her screen, and her MuMu window on it
_job = None  # the job's handle, kept for the life of the run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("code", type=Path, nargs="+", help="folders holding a blacklist_detect")
    parser.add_argument("--cap", type=float, default=18, help="percent of this whole PC the run may use (0: no cap)")
    parser.add_argument("--game", type=int, default=10, help="stand-in game threads (0: no game)")
    parser.add_argument("--frame-ms", type=float, default=6.0, help="busy time of each game frame, uncapped")
    parser.add_argument("--cpus", help="CPUs to run on, like 2-9,14-17 (default: the slowest, one per CPU of hers)")
    parser.add_argument("--her-cores", type=int, default=6)
    parser.add_argument("--her-cpus", type=int, default=12)
    parser.add_argument("--threads", type=int, help="OCR threads, instead of what the version picks on her PC")
    parser.add_argument("--checks", type=int, default=6)
    parser.add_argument("--rounds", type=int, default=1, help="runs of each code, taken in turn")
    parser.add_argument("--one", help=argparse.SUPPRESS)
    args = parser.parse_args()
    cpus = parse_cpus(args.cpus) if args.cpus else slowest_cpus(args.her_cpus)
    if args.one:
        run_one(args, cpus)
        return
    data = Path(tempfile.mkdtemp(prefix="slow_pc_"))
    print(f"her PC on this one: CPUs {args.cpus or cpus}, held to {args.cap:g} % of this PC, "
          f"game {args.game} x {args.frame_ms:g} ms a frame", flush=True)
    env = {k: v for k, v in os.environ.items() if k != "OMP_NUM_THREADS" and not k.startswith("__KMP_REGISTERED_LIB_")}
    env.update(APPDATA=str(data), XDG_CONFIG_HOME=str(data), PYTHONIOENCODING="utf-8")
    for _ in range(args.rounds):
        for code in args.code:
            command = [sys.executable, __file__, *sys.argv[1:], "--one", str(code.resolve())]
            done = subprocess.run(command, env=env, check=False, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace")
            lines = done.stdout.strip().splitlines()  # Paddle prints its own notes before the result
            print(lines[-1] if lines else f"{code}: no output\n{done.stderr[-2000:]}", flush=True)


def run_one(args, cpus: list[int]) -> None:  # noqa: ANN001
    import psutil

    proc = psutil.Process()
    proc.cpu_affinity(cpus)
    sys.path.insert(0, args.one)
    from blacklist_detect import __version__, paths

    # The thread count this version picks on her PC: one per core from 1.0.1, one per CPU before it (OpenMP's own).
    threads = paths.ocr_threads(args.her_cores) if hasattr(paths, "ocr_threads") else str(args.her_cpus)
    threads = str(args.threads) if args.threads else threads
    os.environ["OMP_NUM_THREADS"] = threads  # read once, when Paddle loads
    spins = spins_per_ms()  # the game's frames are sized on this PC's own speed, before the cap
    if args.cap:
        hold_to(args.cap)
    import numpy as np
    from PIL import Image

    from blacklist_detect import ocr_engine, pipeline

    engine = ocr_engine.get_engine()
    engine.warmup()
    crop = np.asarray(Image.open(Path(args.one) / "blacklist_detect" / "assets" / "sample-lobby.jpg").convert("RGB"))
    started = time.perf_counter()
    sample = pipeline.check_rgb(crop, [])  # the app's environment check reads this picture, the game not yet running
    sample_time = time.perf_counter() - started
    left, top, right, bottom = (round(v) for v in sample.game_box)
    pad = ((max(0, -top), max(0, bottom - crop.shape[0])), (max(0, -left), max(0, right - crop.shape[1])), (0, 0))
    game_shot = np.pad(crop, pad, mode="edge")[top + pad[0][0]:bottom + pad[0][0], left + pad[1][0]:right + pad[1][0]]
    canvas = Image.new("RGB", SCREEN, (32, 64, 112))
    canvas.paste(Image.fromarray(game_shot).resize(WINDOW, Image.LANCZOS),
                 ((SCREEN[0] - WINDOW[0]) // 2, (SCREEN[1] - WINDOW[1]) // 2))
    screen = np.asarray(canvas)
    engine.lobby_spot = None
    started = time.perf_counter()
    first = pipeline.check_rgb(screen, [])  # finds the lobby; later checks look where it was, as hotkey checks do
    first_time = time.perf_counter() - started

    ctx = mp.get_context("spawn")
    frames, stop = ctx.Queue(), ctx.Event()
    workers = [ctx.Process(target=game, args=(cpus, spins * args.frame_ms, stop, frames)) for _ in range(args.game)]
    for worker in workers:
        worker.start()
    alone_from = time.time() + 2.0  # the workers start, then the game runs alone for a while
    time.sleep(6.0 if workers else 0.0)
    alone_to = window_from = time.time()
    totals, reads, cpu0 = [], [], sum(proc.cpu_times()[:2])
    for _ in range(args.checks):
        started = time.perf_counter()
        result = pipeline.check_rgb(screen, [])
        totals.append(time.perf_counter() - started)
        reads.append(result.timings.get("read", 0.0))
    window_to = time.time()
    app_cpu = sum(proc.cpu_times()[:2]) - cpu0
    stop.set()
    shown = [frames.get() for _ in workers]
    for worker in workers:
        worker.join()

    span = window_to - window_from
    her_pc = span * (os.cpu_count() * args.cap / 100 if args.cap else len(cpus))  # CPU seconds her PC had
    game_note = ""
    if workers:
        game_cpu = sum(cpu_between(log, window_from, window_to) for log in shown)
        before = on_time([f for log in shown for f in log], alone_from, alone_to)
        during = on_time([f for log in shown for f in log], window_from, window_to)
        game_note = (f" | game: {game_cpu / her_pc * 100:.0f} % of her PC, frames on time {before:.0f} % before, "
                     f"{during:.0f} % during checks")
    print(f"{Path(args.one).name} ({__version__}) on {threads} threads: environment check {sample_time:.2f} s, "
          f"first check {first_time:.2f} s, check {statistics.median(totals):.2f} s "
          f"(read {statistics.median(reads):.2f} s, {sum(1 for s in result.names if s.visible)} names) | app: "
          f"{app_cpu / her_pc * 100:.0f} % of her PC{game_note}", flush=True)
    del first


def game(cpus: list[int], spins: float, stop, out) -> None:  # noqa: ANN001
    """A stand-in game: 60 frames a second, each busy for a set amount of work. A frame not done in its own
    sixtieth of a second, or one never drawn because the last ran over, is late: a stutter the player sees."""
    import psutil

    psutil.Process().cpu_affinity(cpus)
    log = []  # (frame time, on time, CPU seconds used so far)
    tick = time.time()
    while not stop.is_set():
        now = time.time()
        if now < tick:
            time.sleep(tick - now)
        spin(spins)
        done = time.time()
        log.append((tick, done <= tick + FRAME, time.process_time()))
        tick += FRAME
        while tick + FRAME <= done:  # frames that never came
            log.append((tick, False, time.process_time()))
            tick += FRAME
    out.put(log)


def spin(spins: float) -> int:
    total = 0
    for i in range(int(spins)):
        total += i * i
    return total


def spins_per_ms() -> float:
    best = float("inf")
    for _ in range(5):
        started = time.perf_counter()
        spin(200_000)
        best = min(best, time.perf_counter() - started)
    return 200_000 / (best * 1000)


def on_time(log: list[tuple[float, bool, float]], start: float, end: float) -> float:
    inside = [ok for at, ok, _ in log if start <= at < end]
    return 100.0 * sum(inside) / len(inside) if inside else float("nan")


def cpu_between(log: list[tuple[float, bool, float]], start: float, end: float) -> float:
    inside = [cpu for at, _, cpu in log if start <= at < end]
    return inside[-1] - inside[0] if len(inside) > 1 else 0.0


def hold_to(cap: float) -> None:
    """This process, and every one it starts, into a Windows job held to cap percent of the whole PC (a hard cap)."""
    global _job

    class CpuRate(ctypes.Structure):
        _fields_ = [("ControlFlags", wintypes.DWORD), ("CpuRate", wintypes.DWORD)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    _job = wintypes.HANDLE(k32.CreateJobObjectW(None, None))
    rate = CpuRate(0x1 | 0x4, round(cap * 100))  # enabled, hard cap; CpuRate in 1/10,000 of the PC's cycles
    if not k32.SetInformationJobObject(_job, 15, ctypes.byref(rate), ctypes.sizeof(rate)):  # CpuRateControlInformation
        raise OSError(ctypes.get_last_error(), "SetInformationJobObject")
    if not k32.AssignProcessToJobObject(_job, wintypes.HANDLE(k32.GetCurrentProcess())):
        raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject")


def parse_cpus(text: str) -> list[int]:
    return [cpu for part in text.split(",") for cpu in range(int(part.split("-")[0]), int(part.split("-")[-1]) + 1)]


def slowest_cpus(count: int) -> list[int]:
    """count CPUs of the PC's slowest kind (Windows CPU sets: a lower efficiency class is a slower core), so that on a
    PC with fast and slow cores no thread of a run waits on a faster one."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    need = wintypes.ULONG(0)
    k32.GetSystemCpuSetInformation(None, 0, ctypes.byref(need), None, 0)
    records = ctypes.create_string_buffer(need.value)
    if not k32.GetSystemCpuSetInformation(records, need, ctypes.byref(need), None, 0):
        return list(range(min(count, os.cpu_count() or 1)))
    by_class: dict[int, list[int]] = {}
    offset = 0
    while offset < need.value:
        raw = records.raw[offset:offset + 20]
        by_class.setdefault(raw[18], []).append(raw[14])  # efficiency class, logical CPU
        offset += int.from_bytes(raw[0:4], "little")
    for kind in sorted(by_class):
        if len(by_class[kind]) >= count:
            return sorted(by_class[kind])[:count]
    return sorted(cpu for cpus in by_class.values() for cpu in cpus)[:count]


if __name__ == "__main__":
    main()
