"""A/B of the preview builds on one runner (.github/workflows/rust-ab.yml): each build's bench_check (rust/app/examples)
run in turn, interleaved (every build once per round), so a busy or quiet spell on the runner falls on all of them.

    python tools/preview_check/ab.py <frames> <builds dir> <out.json> <rounds> <name>...

<builds dir>/<name>/bench_check.exe is each build's folder (with its onnxruntime.dll and models). A first pass of the
first build, untimed, warms the disk cache and picks the made-up 黑名单 (30 seats it read, seed 20261118; the names stay
on the runner). Per build and round: CPU seconds and wall ms per check, cold (85 first checks) and hot (one frame, the
spot kept), and peak memory. Parity is checked against the first build by the gate's rule: names and marks identical on
every lobby both find, none it finds missed. Names are compared by hash; none are written out.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

import psutil


def _cpu(ps: psutil.Process) -> float:
    t = ps.cpu_times()
    return t.user + t.system


def run(exe: Path, frames: Path, blacklist: Path | None) -> dict:
    env = dict(os.environ, BLACKLIST_DETECT_SILENT="1")
    command = [str(exe), str(frames)] + ([str(blacklist)] if blacklist else [])
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
                            text=True, encoding="utf-8", errors="replace")
    ps = psutil.Process(proc.pid)
    out = {"cold": [], "hot": [], "names": [], "raw": []}
    phase, file, peak = "cold", "", 0
    cpu = {}
    wall = {}
    for line in proc.stdout:
        line = line.rstrip("\n")
        try:
            peak = max(peak, ps.memory_info().rss)
        except psutil.Error:
            pass
        if line.startswith("READY"):
            out["readers"] = line.split("\t")[-1]
            cpu["ready"], wall["ready"] = _cpu(ps), time.perf_counter()
            continue
        if line == "PHASE\thot":
            cpu["cold"], wall["cold"] = _cpu(ps), time.perf_counter()
            phase = "hot"
            continue
        if line == "DONE":
            cpu["hot"], wall["hot"] = _cpu(ps), time.perf_counter()
            break
        if line.startswith("FILE\t"):
            file = line[5:]
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        out[phase].append(float(parts[0]))
        if phase == "cold":
            names = parts[3:]
            out["names"].append({"file": hashlib.sha256(file.encode()).hexdigest()[:16], "header": parts[1] == "1",
                                 "names": hashlib.sha256("\t".join(names).encode()).hexdigest()[:16],
                                 "hits": sorted(int(i) for i in parts[2].split(",") if i.strip().isdigit())})
            out["raw"].append(names)
    out["peak_mb"] = round(peak / 2**20, 1)
    try:
        proc.stdin.write("\n")
        proc.stdin.close()
    except OSError:
        pass
    proc.wait(timeout=60)
    cold_n, hot_n = len(out["cold"]), len(out["hot"])
    out["cold_cpu_s"] = round((cpu["cold"] - cpu["ready"]) / max(cold_n, 1), 4)
    out["hot_cpu_s"] = round((cpu["hot"] - cpu["cold"]) / max(hot_n, 1), 4)
    out["cold_ms"] = round(statistics.median(out["cold"]), 1) if cold_n else None
    out["hot_ms"] = round(statistics.median(out["hot"]), 1) if hot_n else None
    out["cold_wall_s"] = round(wall["cold"] - wall["ready"], 2)
    return out


def parity(base: list[dict], other: list[dict]) -> dict:
    """The gate's rule against the first build: names and marks identical where both find the lobby, none missed."""
    if [f["file"] for f in base] != [f["file"] for f in other]:
        return {"error": "frames in another order"}
    shared = names = marks = missed = only = 0
    for b, o in zip(base, other, strict=True):
        if b["header"] and o["header"]:
            shared += 1
            names += b["names"] != o["names"]
            marks += b["hits"] != o["hits"]
        elif b["header"]:
            missed += 1
        elif o["header"]:
            only += 1
    return {"shared": shared, "names_differ": names, "marks_differ": marks, "missed": missed, "only_this": only}


def main() -> None:
    frames, builds, out_path, rounds = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4])
    names = sys.argv[5:]
    exe = {name: builds / name / "bench_check.exe" for name in names}
    private = Path(os.environ.get("RUNNER_TEMP", ".")) / "ab-private"
    private.mkdir(parents=True, exist_ok=True)
    # Warm-up and the made-up list: the first build, untimed.
    warm = run(exe[names[0]], frames, None)
    seats = [(f, i) for f, row in enumerate(warm["raw"]) for i, n in enumerate(row) if n.strip()]
    picked = random.Random(20261118).sample(seats, min(30, len(seats)))
    blacklist = private / "list.txt"
    blacklist.write_text("\n".join(warm["raw"][f][i] for f, i in picked), encoding="utf-8")
    results: dict = {name: [] for name in names}
    for r in range(rounds):
        for name in names:
            res = run(exe[name], frames, blacklist)
            print(f"round {r + 1} {name}: cold {res['cold_cpu_s']} s CPU / {res['cold_ms']} ms, "
                  f"hot {res['hot_cpu_s']} s / {res['hot_ms']} ms, peak {res['peak_mb']} MB, {res['readers']}", flush=True)
            res.pop("raw")
            results[name].append(res)
    base = results[names[0]][0]["names"]
    summary = {}
    for name in names:
        rows = results[name]

        def stat(key, rows=rows):
            values = [row[key] for row in rows if row.get(key) is not None]
            return {"median": round(statistics.median(values), 4), "min": min(values), "max": max(values)} if values else None

        summary[name] = {key: stat(key) for key in ("cold_cpu_s", "hot_cpu_s", "cold_ms", "hot_ms", "peak_mb")}
        summary[name]["readers"] = rows[0]["readers"]
        summary[name]["parity_vs_" + names[0]] = parity(base, rows[0]["names"])
        summary[name]["stable_across_rounds"] = all(row["names"] == rows[0]["names"] for row in rows)
    out_path.write_text(json.dumps({"rounds": rounds, "builds": names, "summary": summary,
                                    "per_round": {n: [{k: v for k, v in row.items() if k not in ("names", "cold", "hot")}
                                                      for row in results[n]] for n in names}}, indent=1), encoding="utf-8")
    lines = [f"## A/B on `{os.environ.get('CHECK_RUNNER', '?')}`: {rounds} rounds, interleaved, 85 lobbies cold + "
             f"{os.environ.get('BENCH_HOT', '20')} hot", "",
             "| Build | Readers | CPU s/check cold | CPU s/check hot | Wall ms cold | Wall ms hot | Peak MB | "
             f"Parity vs {names[0]} (shared / names / marks / missed / only this) |", "|---|---|---|---|---|---|---|---|"]
    for name in names:
        s = summary[name]

        def cell(key, s=s):
            v = s[key]
            return f"{v['median']} ({v['min']}–{v['max']})" if v else "n/a"

        p = s["parity_vs_" + names[0]]
        par = p.get("error") or f"{p['shared']} / {p['names_differ']} / {p['marks_differ']} / {p['missed']} / {p['only_this']}"
        lines.append(f"| {name} | {s['readers']} | {cell('cold_cpu_s')} | {cell('hot_cpu_s')} | {cell('cold_ms')} | "
                     f"{cell('hot_ms')} | {cell('peak_mb')} | {par}{'' if s['stable_across_rounds'] else ' (rounds differ!)'} |")
    text = "\n".join(lines) + "\n"
    print(text)
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
