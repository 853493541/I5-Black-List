"""Golden data for the Rust port of diagnostics.py, __main__.py and paths.py (rust/data/src/diag, rust/app/src/cli.rs).

Runs the Python code itself on made-up inputs, with the clock, the version and the hardware stubbed, and writes what
it says to rust/data/tests/golden/diag.json. The Rust tests read that file and must give the same text byte for byte.
Run it from the repository root: python tools/rust_golden_diag.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "rust" / "data" / "tests" / "golden" / "diag.json"


def main() -> None:
    data = Path(tempfile.mkdtemp(prefix="golden-diag-"))
    # A data folder of its own: nothing here touches the player's list or settings.
    os.environ.update({"APPDATA": str(data / "appdata"), "HOME": str(data / "home"), "XDG_CONFIG_HOME": str(data / "xdg")})
    sys.path.insert(0, str(ROOT))
    os.environ.pop("OMP_NUM_THREADS", None)
    from blacklist_detect import diagnostics as diag
    from blacklist_detect import paths

    golden: dict = {"flow": flows(diag), "machine": machines(diag), "screens": screens(diag), "power": powers(diag)}
    golden["ocr_threads"] = [[cores, paths.ocr_threads(cores)] for cores in (1, 2, 4, 6, 8, 12, 16, 64)]
    golden["child_env"] = child_envs(paths)
    golden["cli"] = cli_cases()
    golden["slot_lines"] = slot_lines()
    golden["summary"], golden["export"] = summary_and_export(diag, data)
    golden["sample_names"] = list(diag.SAMPLE_NAMES)
    golden["constants"] = {"speed_fine": diag.SPEED_FINE, "speed_slow": diag.SPEED_SLOW, "lobby_share": diag.LOBBY_SHARE}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(golden, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


FLOWS = [
    {},
    {"error": "无法截屏：no display"},
    {"size": [1920, 1080], "device": "cpu", "glance": 0.123, "auto": {"find": 0.5, "read": 1.25},
     "runs": [{"capture": 0.05, "find": 2.0, "read": 1.2}, {"capture": 0.04, "find": 0.1, "read": 1.0},
              {"capture": 0.06, "find": 0.12, "read": 0.9}], "right": 12},
    {"size": [2560, 1440], "screens": 2, "device": "gpu", "glance": 0.2, "auto": {"find": 2.5, "read": 3.75},
     "runs": [{"capture": 0.1, "find": 4.0, "read": 3.0}, {"capture": 0.1, "find": 1.0, "read": 3.5},
              {"capture": 0.2, "find": 1.0, "read": 3.0}, {"capture": 0.1, "find": 1.1, "read": 3.2}],
     "right": 11, "cpu_busy": 92.5, "cpu_own": 20.4, "power": "on battery 40%, battery saver"},
    {"size": [1366, 768], "glance": 0.05, "auto": {"read": 9.0}, "runs": [{"capture": 0.3, "find": 3.0, "read": 5.0}],
     "right": 3, "cpu_busy": 50.0, "cpu_own": 0.0},
    {"size": [3840, 2160], "screens": 3, "glance": 0.025, "auto": {"find": 0.125, "read": 0.375},
     "runs": [{"capture": 0.5, "find": 1.0, "read": 1.0}, {"capture": 0.5, "find": 1.5, "read": 1.0},
              {"capture": 0.5, "find": 1.5, "read": 1.0}], "right": 0, "cpu_busy": 41.0, "cpu_own": None,
     "power": "on battery 99%"},
    {"size": [1920, 1080], "glance": 0.0, "auto": {}, "runs": [{"capture": 0.01, "find": 0.02, "read": 0.03},
                                                               {"capture": 0.025, "find": 0.035, "read": 0.045}]},
]


def flows(diag) -> list:  # noqa: ANN001
    out = []
    for case in FLOWS:
        test = diag.FlowTest(**{k: tuple(v) if k == "size" else v for k, v in case.items()})
        out.append({"input": case, "text": test.text(), "verdict": test.verdict(), "causes": test.causes(),
                    "hotkey": list(test.hotkey().items()), "hotkey_total": test.hotkey_total(),
                    "auto_total": test.auto_total(), "first_total": test.first_total()})
    return out


MACHINES = [
    {"cpu": "13th Gen Intel(R) Core(TM) i7-13700H", "threads": 20, "memory": [31.69, 12.345], "gpus": ["Intel(R) Iris(R) Xe Graphics", "NVIDIA GeForce RTX 4060 Laptop GPU"],
     "product": "Windows 10 Home China", "display": "23H2", "build": 22631, "version": "10.0.22631", "power": "on battery 57%"},
    {"cpu": "AMD Ryzen 5 5600X 6-Core Processor", "threads": 12, "memory": [15.95, 7.05], "gpus": [], "product": "Windows 10 Pro",
     "display": "22H2", "build": 19045, "version": "10.0.19045", "power": ""},
    {"cpu": "", "threads": 4, "memory": [0.0, 0.0], "gpus": ["Microsoft Basic Display Adapter"], "product": "", "display": "", "build": 0,
     "version": "10.0.17763", "power": "battery saver", "processor": "Intel64 Family 6 Model 158 Stepping 10, GenuineIntel"},
]


def machines(diag) -> list:  # noqa: ANN001
    out = []
    saved = (diag.sys, diag.os, diag.platform, diag._registry, diag._memory_gb, diag._gpus, diag.power_note)
    try:
        for case in MACHINES:
            keys = {"ProcessorNameString": case["cpu"], "ProductName": case["product"], "DisplayVersion": case["display"]}
            diag._registry = lambda path, name, keys=keys: keys[name]
            diag._memory_gb = lambda case=case: tuple(case["memory"])
            diag._gpus = lambda case=case: list(case["gpus"])
            diag.power_note = lambda case=case: case["power"]
            diag.sys = types.SimpleNamespace(platform="win32", getwindowsversion=lambda case=case: types.SimpleNamespace(build=case["build"]))
            diag.os = types.SimpleNamespace(cpu_count=lambda case=case: case["threads"])
            diag.platform = types.SimpleNamespace(processor=lambda case=case: case.get("processor", ""), version=lambda case=case: case["version"])
            out.append({"input": case, "line": diag.machine_line()})
    finally:
        diag.sys, diag.os, diag.platform, diag._registry, diag._memory_gb, diag._gpus, diag.power_note = saved
    return out


SCREENS = [[], [[1920, 1080, 1.0]], [[1280, 720, 1.5], [2560, 1440, 1.0]], [[1536, 864, 1.25], [1707, 960, 2.25]], [[1745.4545, 981.8181, 1.1]]]


def screens(diag) -> list:  # noqa: ANN001
    out = []
    qt = types.ModuleType("PySide6.QtWidgets")
    saved = {name: sys.modules.get(name) for name in ("PySide6", "PySide6.QtWidgets")}
    sys.modules["PySide6"] = types.ModuleType("PySide6")
    sys.modules["PySide6.QtWidgets"] = qt
    try:
        for case in SCREENS:
            def screen(w, h, r):  # noqa: ANN001, ANN202
                geometry = types.SimpleNamespace(width=lambda: w, height=lambda: h)
                return types.SimpleNamespace(geometry=lambda: geometry, devicePixelRatio=lambda: r)

            qt.QApplication = types.SimpleNamespace(screens=lambda case=case: [screen(*s) for s in case])
            out.append({"input": case, "line": diag.screens_line()})
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    return out


def powers(diag) -> list:  # noqa: ANN001
    """power_note's words for each raw SYSTEM_POWER_STATUS, as Python joins them."""
    out = []
    for ac, percent, saver in ((1, 100, 0), (0, 57, 0), (0, 12, 1), (1, 80, 1), (255, 255, 0)):
        notes = []
        if ac == 0:
            notes.append(f"on battery {percent}%")
        if saver == 1:
            notes.append("battery saver")
        out.append({"ac": ac, "percent": percent, "saver": saver, "note": ", ".join(notes)})
    # The same words as power_note itself builds (checked against its source text).
    source = Path(diag.__file__).read_text(encoding="utf-8")
    assert 'notes.append(f"on battery {status.BatteryLifePercent}%")' in source and 'notes.append("battery saver")' in source
    return out


def child_envs(paths) -> list:  # noqa: ANN001
    cases = [
        {"PATH": "C:\\Windows", "OMP_NUM_THREADS": "1", "omp_num_threads": "2", "__KMP_REGISTERED_LIB_1234": "x",
         "__kmp_registered_lib_9": "y", "KMP_AFFINITY": "keep", "APPDATA": "C:\\data", "名字": "心动小鹿"},
        {},
        {"OMP_NUM_THREADSX": "keep", "X__KMP_REGISTERED_LIB_": "keep"},
    ]
    out = []
    saved = dict(os.environ)
    try:
        for case in cases:
            os.environ.clear()
            os.environ.update(case)
            out.append({"input": list(case.items()), "output": list(paths.child_env().items())})
    finally:
        os.environ.clear()
        os.environ.update(saved)
    return out


CLI = [[], ["--background"], ["foo", "--background"], ["--Background"], ["check"], ["check", "a.png"], ["check", "a.png", "b.png"],
       ["download-models"], ["download-models", "x"], ["Check", "a.png"], ["x", "check", "a.png"], ["--help"], ["check", "--background"]]


def cli_cases() -> list:
    """What __main__.main does with each argument list: which way it goes, its exit code, what it prints to stderr."""
    import contextlib
    import io

    stubs = {
        "blacklist_detect.ocr_engine": types.SimpleNamespace(silence_console_children=lambda: None),
        "blacklist_detect.ui": types.SimpleNamespace(run_app=lambda background: ("window", background)),
        "blacklist_detect.single": types.SimpleNamespace(exit_now=lambda code: None),
    }
    saved = {name: sys.modules.get(name) for name in stubs}
    for name, stub in stubs.items():
        sys.modules[name] = stub
    from blacklist_detect import __main__ as entry

    out = []
    try:
        for args in CLI:
            seen: list = []
            entry._check_cli = lambda rest, original=entry._check_cli, seen=seen: seen.append(["check", rest[0]]) or 0 if len(rest) == 1 else original(rest)
            entry._download_models = lambda seen=seen: seen.append(["download-models"]) or 0
            stubs["blacklist_detect.ui"].run_app = lambda background, seen=seen: seen.append(["window", background]) or 0
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = entry.main(list(args))
            out.append({"args": args, "way": seen[0] if seen else None, "code": code, "stderr": err.getvalue()})
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    return out


def slot_lines() -> list:
    """_check_cli's line for each seat, from its own format string."""
    out = []
    for index, state, confidence, raw in ((0, "完整", 0.987, "示例坏人"), (11, "截断", 0.5, "心动小"), (4, "未识别", 0.0, ""),
                                          (9, "完整", 0.125, "心动星星"), (2, "完整", 0.995, "x")):
        slot = types.SimpleNamespace(index=index, confidence=confidence, raw=raw)
        out.append({"index": index, "state": state, "confidence": confidence, "raw": raw,
                    "line": f"{slot.index + 1:2d}  {state:4s}  {slot.confidence:0.2f}  {slot.raw}"})
    source = (ROOT / "blacklist_detect" / "__main__.py").read_text(encoding="utf-8")
    assert 'print(f"{slot.index + 1:2d}  {state:4s}  {slot.confidence:0.2f}  {slot.raw}")' in source
    return out


def summary_and_export(diag, data: Path) -> tuple:  # noqa: ANN001
    clock = time.struct_time((2026, 11, 18, 9, 5, 7, 2, 322, 0))
    store = types.SimpleNamespace(safe_mode=True, auto_capture=False, stream_mode="obs", hotkey="ctrl+alt+b",
                                  entries=[1, 2, 3], likes=[1], scans=[1, 2])
    saved = (diag.machine_line, diag.screens_line, diag.__version__, diag.time)
    diag.machine_line = lambda: MACHINE_LINE
    diag.screens_line = lambda: "1920x1080 at 150%"
    diag.__version__ = "v9.9.9"
    diag.time = types.SimpleNamespace(strftime=lambda fmt: time.strftime(fmt, clock))
    try:
        summaries = [{"input": {"safe_mode": True, "auto_capture": False, "stream_mode": "obs", "hotkey": "ctrl+alt+b",
                                "entries": 3, "likes": 1, "scans": 2, "device": "cpu"}, "text": diag.summary_text(store, "cpu")}]
        store2 = types.SimpleNamespace(safe_mode=False, auto_capture=True, stream_mode="", hotkey="F8", entries=[], likes=[], scans=[])
        summaries.append({"input": {"safe_mode": False, "auto_capture": True, "stream_mode": "", "hotkey": "F8", "entries": 0,
                                    "likes": 0, "scans": 0, "device": "gpu"}, "text": diag.summary_text(store2, "gpu")})
        root = data / "root"
        logs = root / "logs"
        logs.mkdir(parents=True)
        home = "/home/xiaolu"
        os.environ["HOME"] = home
        os.environ["USERNAME"] = "xiaolu"
        files = {"app.log.2": "old line\n", "app.log.1": f"mid line at {home}/x\n", "app.log.10": "oldest\n", "app.log": "  newest 心动小鹿 xiaolu \n",
                 "crash.log": "Traceback in /home/xiaolu/a.py\n", "app.log.bak": "skipped\n", "app.log.": "skipped too\n"}
        for name, text in files.items():
            (logs / name).write_text(text, encoding="utf-8")
        report = diag.FlowTest(**{k: tuple(v) if k == "size" else v for k, v in FLOWS[2].items()}).text()
        target = diag.export_logs(root, summaries[0]["text"], data / "desk", report)
        export = {"files": files, "home": home, "user": "xiaolu", "report": report, "name": target.name,
                  "text": target.read_text(encoding="utf-8")}
    finally:
        diag.machine_line, diag.screens_line, diag.__version__, diag.time = saved
        os.environ["HOME"] = str(data / "home")
        os.environ.pop("USERNAME", None)
    return summaries, export


MACHINE_LINE = "CPU 示例 CPU (8 threads); RAM 16.0 GB (8.0 GB free); GPU ?; Windows 11 Home 23H2 build 10.0.22631"

if __name__ == "__main__":
    main()
