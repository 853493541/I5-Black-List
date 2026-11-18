"""The preview check's measurements and report, run on GitHub's Windows runners (docs/dev/preview-check.md).

    python tools/preview_check/check.py bench <name> <out.json> -- <command...>
    python tools/preview_check/check.py start <name> <out.json> [--env K=V ...] -- <command...>
    python tools/preview_check/check.py scenes <out.json> <rust scene_times exe> <python> <v1.0.1 tree>
    python tools/preview_check/check.py sides <python shots dir> <rust shots dir> <out dir>
    python tools/preview_check/check.py report <results dir> <out.md>
    python tools/preview_check/check.py gate <results dir>

Nothing here keeps a player name: the corpus bench keeps per frame only a hash of the names read, and the frames
themselves are never copied, uploaded or printed. Every command runs silent (BLACKLIST_DETECT_SOUND is removed).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

import psutil

BUDGET_MS = 20.0
KEYS = ["classic", "lace", "stars", "ice", "cyber", "neon", "angel", "equation", "fluffy", "claw", "lyre"]


def _env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("BLACKLIST_DETECT_SOUND", "OMP_NUM_THREADS")}
    env["BLACKLIST_DETECT_SILENT"] = "1"
    env.update(extra or {})
    return env


def _tree_rss(proc: psutil.Process) -> int:
    total = 0
    for p in [proc, *proc.children(recursive=True)]:
        try:
            total += p.memory_info().rss
        except psutil.Error:
            pass
    return total


def _tree_cpu(proc: psutil.Process) -> float:
    total = 0.0
    for p in [proc, *proc.children(recursive=True)]:
        try:
            t = p.cpu_times()
            total += t.user + t.system
        except psutil.Error:
            pass
    return total


def bench(name: str, out: Path, command: list[str]) -> None:
    """Runs a `--bench-check`-style command: READY, one line per frame, DONE, then it waits for stdin."""
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, env=_env(),
                            text=True, encoding="utf-8", errors="replace")
    ps = psutil.Process(proc.pid)
    frames, rss10, cpu_start, rss_ready, peak = [], None, None, None, 0
    started = time.perf_counter()
    for line in proc.stdout:
        line = line.rstrip("\n")
        peak = max(peak, _tree_rss(ps))
        if line.startswith("READY"):
            rss_ready, cpu_start = _tree_rss(ps), _tree_cpu(ps)
            wall_start = time.perf_counter()
            continue
        if line == "DONE":
            break
        parts = line.split("\t")
        if len(parts) < 2 or not re.fullmatch(r"[\d.]+", parts[0]):
            continue
        names = parts[2:]
        frames.append({
            "ms": float(parts[0]),
            "header": parts[1] == "1",
            "names": hashlib.sha256("\t".join(names).encode()).hexdigest()[:16],
            "read": sum(1 for n in names if n.strip()),
        })
        if len(frames) == 10:
            rss10 = _tree_rss(ps)
    cpu = _tree_cpu(ps) - (cpu_start or 0.0)
    wall = time.perf_counter() - (wall_start if cpu_start is not None else started)
    rss_end = _tree_rss(ps)
    try:
        proc.stdin.write("\n")
        proc.stdin.close()
    except OSError:
        pass
    proc.wait(timeout=60)
    ms = [f["ms"] for f in frames]
    result = {
        "name": name, "frames": frames, "count": len(frames), "exit": proc.returncode,
        "median_ms": statistics.median(ms) if ms else None, "mean_ms": statistics.fmean(ms) if ms else None,
        "cpu_s": round(cpu, 2), "wall_s": round(wall, 2),
        "rss_ready_mb": round((rss_ready or 0) / 2**20, 1), "rss_10_mb": round((rss10 or 0) / 2**20, 1),
        "rss_end_mb": round(rss_end / 2**20, 1), "rss_peak_mb": round(peak / 2**20, 1),
    }
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: v for k, v in result.items() if k != "frames"})


def _visible_window(pids: set[int]) -> bool:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if rect.right - rect.left > 200 and rect.bottom - rect.top > 150:
                found.append(hwnd)
        return True

    user32.EnumWindows(each, 0)
    return bool(found)


def start(name: str, out: Path, command: list[str], extra: dict[str, str], runs: int = 3) -> None:
    """Time from launch to the first visible top-level window of the app (or a child), and its memory 5 s later."""
    times, rss = [], []
    for _ in range(runs):
        began = time.perf_counter()
        proc = subprocess.Popen(command, env=_env(extra), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ps = psutil.Process(proc.pid)
        shown = None
        while time.perf_counter() - began < 90 and proc.poll() is None:
            pids = {proc.pid, *(c.pid for c in ps.children(recursive=True))}
            if _visible_window(pids):
                shown = time.perf_counter() - began
                break
            time.sleep(0.02)
        if shown is not None:
            time.sleep(5)
            rss.append(_tree_rss(ps) / 2**20)
        times.append(shown)
        for p in [*ps.children(recursive=True), ps]:
            try:
                p.kill()
            except psutil.Error:
                pass
        proc.wait(timeout=30)
        time.sleep(1)
    ok = [t for t in times if t is not None]
    result = {"name": name, "runs": times, "median_s": round(statistics.median(ok), 2) if ok else None,
              "rss_mb": round(statistics.median(rss), 1) if rss else None}
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(result)


def scenes(out: Path, rust_exe: str, python: str, tree: Path) -> None:
    result = {"adapter": None, "rust": {}, "python": {}}
    lines = []
    for key in KEYS:
        try:
            done = subprocess.run([rust_exe, key], capture_output=True, text=True, encoding="utf-8", errors="replace", env=_env(),
                                  timeout=300)
        except subprocess.TimeoutExpired:
            lines.append(f"{key}\tskipped\ttimed out after 300 s")
            continue
        print(done.stdout, done.stderr[-1500:])
        lines += done.stdout.splitlines() or [f"{key}\tskipped\t{(done.stderr.strip().splitlines() or ['no output'])[-1][:160]}"]
    for line in lines:
        parts = line.split("\t")
        if parts[0] == "adapter":
            result["adapter"] = parts[1]
        elif len(parts) >= 5 and parts[1] != "skipped":
            result["rust"][parts[0]] = {"frames": int(parts[1]), "median": float(parts[2]), "p95": float(parts[3]), "worst": float(parts[4])}
        elif len(parts) >= 2:
            result["rust"][parts[0]] = {"skipped": parts[2] if len(parts) > 2 else "?"}
    frames_dir = Path(os.environ.get("RUNNER_TEMP", ".")) / "py-frames"
    for key in KEYS:
        try:
            done = subprocess.run([python, "tools/love_frames.py", key, str(frames_dir), "1.0"], cwd=tree, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", env=_env({"PYTHONPATH": str(tree)}), timeout=240)
        except subprocess.TimeoutExpired:
            result["python"][key] = {"skipped": "timed out"}
            continue
        found = re.search(r"median ([\d.]+) ms, 90% ([\d.]+) ms, worst ([\d.]+) ms", done.stdout)
        if found:
            result["python"][key] = {"median": float(found[1]), "p90": float(found[2]), "worst": float(found[3])}
        else:
            result["python"][key] = {"skipped": (done.stderr.strip().splitlines() or ["no output"])[-1][:160]}
        print(key, result["python"][key])
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


def sides(py_dir: Path, rust_dir: Path, out: Path) -> None:
    from PIL import Image, ImageDraw

    out.mkdir(parents=True, exist_ok=True)
    rust = {p.stem: p for p in rust_dir.glob("*.png")}
    # ui_shots numbers its pictures in the order it takes them ("00_page_记录"); the name is what is compared.
    python = {re.sub(r"^\d+_", "", p.stem): p for p in py_dir.glob("*.png")}
    for name in sorted(rust.keys() | python.keys()):
        left = Image.open(python[name]).convert("RGB") if name in python else None
        right = Image.open(rust[name]).convert("RGB") if name in rust else None
        w = (left.width if left else 0) + (right.width if right else 0) + (24 if left and right else 0)
        h = max(i.height for i in (left, right) if i) + 28
        canvas = Image.new("RGB", (max(w, 400), h), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        x = 0
        for label, img in (("Python v1.0.1", left), ("Rust preview", right)):
            if img is None:
                draw.text((x + 6, 6), f"{label}: none", fill=(200, 0, 0))
                x += 200
                continue
            draw.text((x + 6, 6), label, fill=(0, 0, 0))
            canvas.paste(img, (x, 28))
            x += img.width + 24
        canvas.save(out / f"{name}.png", optimize=True)
    listing = {"both": sorted(rust.keys() & python.keys()), "python_only": sorted(python.keys() - rust.keys()),
               "rust_only": sorted(rust.keys() - python.keys()), "diff": {}}
    for name in listing["both"]:
        listing["diff"][name] = _difference(Image.open(python[name]).convert("RGB"), Image.open(rust[name]).convert("RGB"))
    (out / "index.json").write_text(json.dumps(listing, ensure_ascii=False, indent=1), encoding="utf-8")
    print(listing)


def _difference(left, right) -> dict:
    """Numbers for a Python / Rust pair (the pictures are not looked at by eye on CI): whether the sizes match, the mean
    difference per channel (0-255) and the share of pixels differing by more than 24/255 in any channel, the Rust picture
    scaled to the Python one's size when they differ."""
    from PIL import ImageChops

    same = left.size == right.size
    if not same:
        right = right.resize(left.size)
    diff = ImageChops.difference(left, right)
    channels = diff.split()
    mean = sum(sum(i * n for i, n in enumerate(c.histogram())) for c in channels) / (3 * left.size[0] * left.size[1])
    worst = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    over = sum(worst.histogram()[25:]) / (left.size[0] * left.size[1])
    return {"size": f"{left.size[0]}x{left.size[1]}" + ("" if same else f" vs {right.size[0]}x{right.size[1]}"),
            "same_size": same, "mean": round(mean, 1), "over24": round(over * 100, 1)}


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def report(results: Path, out: Path) -> None:
    runner = os.environ.get("CHECK_RUNNER", "?")
    lines = [f"# Rust preview vs Python v1.0.1 on `{runner}`", ""]
    rs, py = _load(results / "start-rust.json"), _load(results / "start-python.json")
    rb, pb = _load(results / "bench-rust.json"), _load(results / "bench-python.json")

    def cell(value, unit=""):
        return "n/a" if value in (None, "") else f"{value}{unit}"

    lines += ["| Measure | Python v1.0.1 | Rust preview |", "|---|---|---|",
              f"| Start to window shown (median of 3) | {cell(py.get('median_s'), ' s')} | {cell(rs.get('median_s'), ' s')} |",
              f"| Memory 5 s after start (app + children) | {cell(py.get('rss_mb'), ' MB')} | {cell(rs.get('rss_mb'), ' MB')} |",
              f"| OCR engine ready, memory | {cell(pb.get('rss_ready_mb'), ' MB')} | {cell(rb.get('rss_ready_mb'), ' MB')} |",
              f"| Memory after 10 checks (engine process) | {cell(pb.get('rss_10_mb'), ' MB')} | {cell(rb.get('rss_10_mb'), ' MB')} |",
              f"| Memory after all frames / peak | {cell(pb.get('rss_end_mb'))} / {cell(pb.get('rss_peak_mb'), ' MB')} | "
              f"{cell(rb.get('rss_end_mb'))} / {cell(rb.get('rss_peak_mb'), ' MB')} |",
              f"| Corpus frames checked | {cell(pb.get('count'))} | {cell(rb.get('count'))} |",
              f"| Time per lobby, median / mean | {cell(pb.get('median_ms'))} / {cell(round(pb['mean_ms'], 1) if pb.get('mean_ms') else None, ' ms')} | "
              f"{cell(rb.get('median_ms'))} / {cell(round(rb['mean_ms'], 1) if rb.get('mean_ms') else None, ' ms')} |",
              f"| CPU time, whole corpus (wall) | {cell(pb.get('cpu_s'), ' s')} ({cell(pb.get('wall_s'), ' s')}) | "
              f"{cell(rb.get('cpu_s'), ' s')} ({cell(rb.get('wall_s'), ' s')}) |"]
    pf, rf = pb.get("frames", []), rb.get("frames", [])
    if pf and rf and len(pf) == len(rf):
        same = sum(a["names"] == b["names"] for a, b in zip(pf, rf, strict=True))
        head = sum(a["header"] == b["header"] for a, b in zip(pf, rf, strict=True))
        lines.append(f"| Names identical per frame | {same} of {len(pf)} | (lobby found the same: {head} of {len(pf)}) |")
        diff = [i for i, (a, b) in enumerate(zip(pf, rf, strict=True)) if a["names"] != b["names"]]
        if diff:
            shown = ", ".join(str(i) + ":" + str(pf[i]["read"]) + "/" + str(rf[i]["read"]) for i in diff[:30])
            lines.append(f"| Frames that differ (index in name order: seats read Python/Rust) | {shown} | |")
    else:
        lines.append(f"| Names identical per frame | not comparable ({len(pf)} vs {len(rf)} frames) | |")
    sc = _load(results / "scenes.json")
    lines += ["", f"## Scene frame time at 1920x1080 (budget {BUDGET_MS:.0f} ms)", "",
              f"Rust adapter: `{sc.get('adapter')}`. The runner has no GPU: WARP (Direct3D 12 in software) stands in, so these "
              "times are far above what a real graphics chip gives; they compare scenes with each other, not with the budget.", "",
              "| Scene | Rust median / p95 / worst ms | Python median / 90% / worst ms (QPainter, CPU) |", "|---|---|---|"]
    for key in ["classic", "lace", "stars", "ice", "cyber", "neon", "angel", "equation", "fluffy", "claw", "lyre"]:
        r, p = sc.get("rust", {}).get(key, {}), sc.get("python", {}).get(key, {})
        rt = r.get("skipped") or f"{r.get('median')} / {r.get('p95')} / {r.get('worst')}" if r else "n/a"
        if "p95" in r:
            rt += " (within 20 ms)" if r["p95"] <= BUDGET_MS else " (over 20 ms on WARP)"
        pt = p.get("skipped") or f"{p.get('median')} / {p.get('p90')} / {p.get('worst')}" if p else "n/a"
        lines.append(f"| {key} | {rt} | {pt} |")
    for scale in ("125", "150"):
        index = _load(results / f"sides-{scale}" / "index.json")
        if index:
            lines += ["", f"## Pictures at {scale} %", "",
                      f"- side by side (Python left, Rust right): {len(index['both'])}; checked by numbers on the runner, "
                      "not by eye (high = mean difference over 20 or more than 30 % of pixels off by over 24/255)",
                      f"- Python only: {', '.join(index['python_only']) or 'none'}",
                      f"- Rust only: {', '.join(index['rust_only']) or 'none'}", "",
                      "| Picture | Size (Python vs Rust) | Mean diff /255 | Pixels off >24 | |", "|---|---|---|---|---|"]
            for name, d in sorted(index.get("diff", {}).items()):
                high = d["mean"] > 20 or d["over24"] > 30
                lines.append(f"| {name} | {d['size']} | {d['mean']} | {d['over24']} % | {'**high**' if high else ''} |")
    lines += ["", "## What this runner cannot test", "",
              "- No graphics chip: scenes run on WARP (software); the overlay's real frame time is not measured here.",
              f"- Windows Server ({runner}), not Windows 10 Home 22H2; no real 125 % monitor (scale is set per process: "
              "BLACKLIST_DETECT_SCALE / SLINT_SCALE_FACTOR for Rust, QT_SCALE_FACTOR for Python).",
              "- No game, no MuMu, no 直播姬: the on-game cards are drawn over the sample lobby picture, not over the game; "
              "hotkeys, screen capture of the game window and the live overlay are not exercised.",
              "- Corpus checks run in a bench process with the app's engine, not through the app's hotkey.",
              f"- Fonts: {os.environ.get('CHECK_FONTS', 'see the job log')}."]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def gate(results: Path) -> None:
    """Fails the job unless the Rust app started, drew every picture, read every lobby as Python did and ran every scene."""
    problems = []
    rs = _load(results / "start-rust.json")
    if not rs.get("median_s"):
        problems.append("the Rust window never showed")
    for scale in ("125", "150"):
        index = _load(results / f"sides-{scale}" / "index.json")
        rust = len(index.get("both", [])) + len(index.get("rust_only", []))
        if rust < 16:
            problems.append(f"{scale} %: only {rust} Rust pictures")
    rb, pb = _load(results / "bench-rust.json"), _load(results / "bench-python.json")
    corpus = int(os.environ.get("CORPUS_FRAMES", "85"))
    if rb.get("count") != corpus:
        problems.append(f"Rust read {rb.get('count')} of {corpus} lobbies")
    if pb.get("count") != corpus:
        problems.append(f"Python read {pb.get('count')} of {corpus} lobbies")
    elif rb.get("count") == corpus:
        differ = sum(a["names"] != b["names"] for a, b in zip(pb["frames"], rb["frames"], strict=True))
        if differ:
            problems.append(f"names differ on {differ} of {corpus} lobbies")
    sc = _load(results / "scenes.json").get("rust", {})
    for key in ["classic", "lace", "stars", "ice", "cyber", "neon", "angel", "equation", "fluffy", "claw", "lyre"]:
        if "median" not in sc.get(key, {}):
            problems.append(f"scene {key} did not run")
    for problem in problems:
        print(f"::error::{problem}")
    print("gate:", "pass" if not problems else f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


def main() -> None:
    args = sys.argv[1:]
    command = args[args.index("--") + 1:] if "--" in args else []
    head = args[: args.index("--")] if "--" in args else args
    what = head[0]
    if what == "bench":
        bench(head[1], Path(head[2]), command)
    elif what == "start":
        extra = dict(item.split("=", 1) for item in head[4::2]) if len(head) > 3 else {}
        start(head[1], Path(head[2]), command, extra)
    elif what == "scenes":
        scenes(Path(head[1]), head[2], head[3], Path(head[4]))
    elif what == "sides":
        sides(Path(head[1]), Path(head[2]), Path(head[3]))
    elif what == "report":
        report(Path(head[1]), Path(head[2]))
    elif what == "gate":
        gate(Path(head[1]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
