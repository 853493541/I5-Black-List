"""Why a check was slow, the 环境测试 that measures it, and one text file of the logs a friend can send.

The log says where each check's time went. This adds what explains it: how busy the computer was
while the check ran (and how much of that was this app), whether a laptop ran on battery or
battery saver, and once at each start, what the computer is. FlowTest times the two ways a check
starts, 自动检查 and the hotkey, step by step on the bundled sample lobby. The export puts the
summary, the last 环境测试 and the logs in one text file on the Desktop. Nothing here holds a
player's name or the lists.
"""

from __future__ import annotations

import base64
import os
import platform
import re
import sys
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from blacklist_detect import __version__
from blacklist_detect.logs import log_dir


class CpuWindow:
    """How busy the whole computer was between start() and stop(), and how much was this app."""

    def __init__(self) -> None:
        self._system = _system_times()
        self._own = time.process_time()
        self._wall = time.perf_counter()

    def numbers(self) -> tuple[float, float] | None:
        """(whole computer, this app) busy percent since start(), or None when Windows does not say."""
        now = _system_times()
        if self._system is None or now is None:
            return None
        idle = now[0] - self._system[0]
        total = (now[1] - self._system[1]) + (now[2] - self._system[2])  # kernel time includes idle
        if total <= 0:
            return None
        wall = max(1e-6, time.perf_counter() - self._wall)
        own = 100 * (time.process_time() - self._own) / wall / max(1, os.cpu_count() or 1)
        return 100 * (total - idle) / total, own

    def stop(self) -> str:
        """'CPU 85% (this app 20%)', or '' when Windows does not say."""
        numbers = self.numbers()
        return "" if numbers is None else f"CPU {numbers[0]:.0f}% (this app {numbers[1]:.0f}%)"


def _system_times() -> tuple[int, int, int] | None:
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        return None

    def ticks(value) -> int:  # noqa: ANN001
        return value.dwHighDateTime << 32 | value.dwLowDateTime

    return ticks(idle), ticks(kernel), ticks(user)


def power_note() -> str:
    """'on battery', 'battery saver', or '' when plugged in or a desktop."""
    if sys.platform != "win32":
        return ""
    import ctypes

    class Status(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte), ("BatteryLifePercent", ctypes.c_ubyte),
            ("SystemStatusFlag", ctypes.c_ubyte), ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong),
        ]  # fmt: skip

    status = Status()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return ""
    notes = []
    if status.ACLineStatus == 0:
        notes.append(f"on battery {status.BatteryLifePercent}%")
    if status.SystemStatusFlag == 1:
        notes.append("battery saver")
    return ", ".join(notes)


def _registry(path: str, name: str) -> str:
    if sys.platform != "win32":
        return ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            return str(winreg.QueryValueEx(key, name)[0]).strip()
    except OSError:
        return ""


def _memory_gb() -> tuple[float, float]:
    """(total, free) in GB, or (0, 0)."""
    if sys.platform != "win32":
        return 0.0, 0.0
    import ctypes

    class Memory(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong)
            for name in ("total", "free", "pagefile", "pagefile_free", "virtual", "virtual_free", "extended")
        ]

    memory = Memory()
    memory.dwLength = ctypes.sizeof(Memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        return 0.0, 0.0
    return memory.total / 2**30, memory.free / 2**30


def _gpus() -> list[str]:
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    class Device(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR * 32), ("DeviceString", wintypes.WCHAR * 128),
                    ("StateFlags", wintypes.DWORD), ("DeviceID", wintypes.WCHAR * 128), ("DeviceKey", wintypes.WCHAR * 128)]  # fmt: skip

    found: list[str] = []
    index = 0
    while index < 16:
        device = Device()
        device.cb = ctypes.sizeof(Device)
        if not ctypes.windll.user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
            break
        if device.DeviceString and device.DeviceString not in found:
            found.append(device.DeviceString)
        index += 1
    return found


def machine_line() -> str:
    """The computer in one line, for the log at each start."""
    total, free = _memory_gb()
    cpu = _registry(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString") or platform.processor()
    product = _registry(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "ProductName")
    build = sys.getwindowsversion().build if sys.platform == "win32" else 0
    if build >= 22000:
        # Windows 11 still names itself Windows 10 here.
        product = product.replace("Windows 10", "Windows 11")
    windows = " ".join(
        part
        for part in (
            product,
            _registry(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "DisplayVersion"),
            f"build {platform.version()}",
        )
        if part
    )
    parts = [
        f"CPU {cpu} ({os.cpu_count()} threads)",
        f"RAM {total:.1f} GB ({free:.1f} GB free)",
        f"GPU {' / '.join(_gpus()) or '?'}",
        windows,
    ]
    power = power_note()
    if power:
        parts.append(power)
    return "; ".join(parts)


def screens_line() -> str:
    try:
        from PySide6.QtWidgets import QApplication

        return ", ".join(
            f"{s.geometry().width() * s.devicePixelRatio():.0f}x{s.geometry().height() * s.devicePixelRatio():.0f}"
            f" at {s.devicePixelRatio() * 100:.0f}%"
            for s in QApplication.screens()
        )
    except Exception:  # noqa: BLE001 - only for the summary
        return "?"


# What the bundled sample lobby says, seat by seat: made-up names, read right on a working PC.
# 检查 reads the sample and counts the names it gets right.
SAMPLE_NAMES = ("小林同学", "白日梦想家", "路过的猫", "一只团子", "夏天的风", "心动小鹿",
                "晚风吹过", "摸鱼大师", "示例坏人", "心动星星", "柠檬汽水", "棉花糖")  # fmt: skip


# A hotkey check, warm, in seconds: up to the first is fine, up to the second slow, beyond very slow.
SPEED_FINE = 3.0
SPEED_SLOW = 6.0
# Steps the report draws as bars: (key, words).
STEPS = (("capture", "截屏"), ("glance", "发现大厅"), ("find", "找名单"), ("read", "读名字"))


@dataclass
class FlowTest:
    """环境测试's timings: the two ways a check starts, each step, on the sample lobby laid in the
    real screen copy. 自动检查: a glance at the top of the screen sees 推演成功, then the lobby is
    found and read. The hotkey: the screen is copied, then the lobby is found and read; three
    times, the first searching for the lobby, the others finding it where it was."""

    size: tuple[int, int] = (0, 0)
    screens: int = 1
    device: str = "cpu"
    capture: float = 0.0
    glance: float = 0.0
    glance_found: bool = False
    auto: dict[str, float] = field(default_factory=dict)
    runs: list[dict[str, float]] = field(default_factory=list)
    right: int = 0
    error: str = ""
    cpu_busy: float | None = None
    cpu_own: float | None = None
    power: str = ""

    def hotkey(self) -> dict[str, float]:
        """A warm hotkey check, step by step: the middle of the later runs."""
        warm = self.runs[1:] or self.runs
        if not warm:
            return {}
        ordered = sorted(warm, key=lambda run: sum(run.values()))
        return ordered[len(ordered) // 2]

    def hotkey_total(self) -> float:
        return sum(self.hotkey().values())

    def auto_total(self) -> float:
        return self.glance + sum(self.auto.values())

    def first_total(self) -> float:
        return sum(self.runs[0].values()) if self.runs else 0.0

    def verdict(self) -> str:
        seconds = self.hotkey_total()
        if seconds <= SPEED_FINE:
            return "正常"
        if seconds <= SPEED_SLOW:
            return "有点慢"
        return "很慢"

    def causes(self) -> list[str]:
        """Why it took as long as it did, in plain words, the biggest reason first."""
        if self.error:
            return [self.error]
        out = []
        others = None if self.cpu_busy is None or self.cpu_own is None else self.cpu_busy - self.cpu_own
        if others is not None and others >= 40:
            out.append(f"电脑很忙：CPU 用了 {self.cpu_busy:.0f}%，其中别的程序占 {others:.0f}%（比如游戏），关掉一些会更快")
        if "battery" in self.power:
            out.append("笔记本在用电池，接上电源会更快")
        steps = self.hotkey()
        if steps and self.verdict() != "正常":
            slowest = max(steps, key=steps.get)
            words = dict(STEPS)[slowest]
            out.append(f"最慢的一步是「{words}」：{steps[slowest]:.1f} 秒")
        if self.runs and self.first_total() > 1.5 * max(self.hotkey_total(), 0.1) and self.first_total() > 1:
            out.append(f"第一次检查要先找大厅（{self.first_total():.1f} 秒）；窗口不动，之后每次约 {self.hotkey_total():.1f} 秒")
        return out

    def text(self) -> str:
        """The report for the log and the export, with the numbers behind it."""
        if self.error:
            return f"环境测试：没完成，{self.error}"
        lines = [
            f"环境测试：检查一次约 {self.hotkey_total():.1f} 秒，{self.verdict()}",
            f"  手动检查（快捷键）：{self.hotkey_total():.2f} s = " + " + ".join(f"{dict(STEPS)[k]} {v:.2f}" for k, v in self.hotkey().items()),
            f"  自动检查：{self.auto_total():.2f} s = 发现大厅 {self.glance:.2f}" + "".join(f" + {dict(STEPS)[k]} {v:.2f}" for k, v in self.auto.items()),
            "  每次手动检查：" + ", ".join(f"{sum(run.values()):.2f}" for run in self.runs) + " s",
            f"  示例大厅的 12 个名字读对 {self.right} 个；识别用 {self.device}；屏幕 {self.size[0]}x{self.size[1]}"
            + (f"，{self.screens} 块" if self.screens != 1 else ""),
        ]
        if self.cpu_busy is not None:
            lines.append(f"  CPU {self.cpu_busy:.0f}%（本工具 {self.cpu_own or 0:.0f}%）" + (f"；{self.power}" if self.power else ""))
        lines += [f"  · {cause}" for cause in self.causes()]
        return "\n".join(lines)


# How wide the sample lobby is laid on the screen copy: a game window, as in an emulator, not the whole screen.
LOBBY_SHARE = 0.64


def run_flow_test(sample: Path, rounds: int = 3) -> FlowTest:
    """Runs on the worker thread: the screen copied as a check copies it, then 自动检查 and the
    hotkey on that copy with the sample lobby laid in the middle of it, the size of a game window.
    Whatever else is on the screen is still there around it, so finding the lobby costs what it
    costs here."""
    import numpy as np
    from PIL import Image

    from blacklist_detect.capture import capture_displays
    from blacklist_detect.ocr_engine import get_engine, inference_device
    from blacklist_detect.pipeline import check_rgb, glance_title

    engine = get_engine()
    # Each way starts by searching for the lobby, as a first check does.
    engine.lobby_spot = None
    test = FlowTest(device=inference_device(), power=power_note())
    window = CpuWindow()
    width, height = 1920, 1080
    try:
        started = time.perf_counter()
        frames = capture_displays()
        test.capture = time.perf_counter() - started
        height, width = frames[0].shape[:2]
        test.screens = len(frames)
    except Exception as exc:  # noqa: BLE001 - the report says it, whatever went wrong
        test.error = f"无法截屏：{exc}"
        return test
    test.size = (width, height)
    lobby = Image.open(sample).convert("RGB")
    scale = min(width * LOBBY_SHARE / lobby.width, height * LOBBY_SHARE / lobby.height)
    lobby = lobby.resize((round(lobby.width * scale), round(lobby.height * scale)), Image.LANCZOS)
    screen = Image.fromarray(frames[0]).convert("RGB")
    screen.paste(lobby, ((width - lobby.width) // 2, (height - lobby.height) // 2))
    rgb = np.asarray(screen)
    try:
        # 自动检查: the glance at the top of the screen, as the watch takes it, then the check.
        from blacklist_detect.capture import TITLE_BAND_FRACTION

        band = rgb[: max(1, int(height * TITLE_BAND_FRACTION))]
        started = time.perf_counter()
        test.glance_found = glance_title(band)
        test.glance = time.perf_counter() - started
        result = check_rgb(rgb, [])
        test.auto = {key: result.timings[key] for key in ("find", "read") if key in result.timings}
        # The hotkey: a screen copy each time, then the check; the first searches, the others find
        # the lobby where it was.
        engine.lobby_spot = None
        for _ in range(rounds):
            started = time.perf_counter()
            capture_displays()
            copy = time.perf_counter() - started
            result = check_rgb(rgb, [])
            run = {"capture": copy}
            run.update({key: result.timings[key] for key in ("find", "read") if key in result.timings})
            test.runs.append(run)
        # 识别测试 counts the names read right, on the sample at full size (the window sets test.right).
    except Exception as exc:  # noqa: BLE001
        test.error = f"无法识别：{exc}"
    # The sample is not where a real lobby will be.
    engine.lobby_spot = None
    numbers = window.numbers()
    if numbers is not None:
        test.cpu_busy, test.cpu_own = numbers
    return test


def summary_text(store, device: str) -> str:  # noqa: ANN001
    """What the export says about this computer and the app's settings. Counts only, no names."""
    lines = [
        f"模仿者小工具 {__version__}",
        f"导出于 {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        machine_line(),
        f"Screens: {screens_line()}",
        f"Recognition on {device}",
        f"基础模式 {store.safe_mode}, 自动检查 {store.auto_capture}, 直播模式 {bool(store.stream_mode)}, hotkey {store.hotkey}",
        f"黑名单 {len(store.entries)} people, 嘉宾 {len(store.likes)} people, 记录 {len(store.scans)} lobbies",
    ]
    return "\n".join(lines) + "\n"


def export_logs(root: Path, summary: str, folder: Path | None = None, report: str = "") -> Path:
    """One text file on the Desktop (unless told where): the computer, the last 环境测试, then the
    logs, oldest first, and the dumps of copies found stuck (dumps_in reads them back). Returns its path."""
    folder = folder or desktop()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"模仿者小工具_日志_{time.strftime('%Y%m%d-%H%M')}.txt"
    parts = ["==== 电脑和设置 ====", summary]
    if report:
        parts += ["==== 最近一次环境测试 ====", report, ""]
    logs = log_dir(root)
    # app.log.3 is the oldest, app.log the newest; crash.log last.
    files: list[Path] = []
    if logs.is_dir():
        rotated = [path for path in logs.glob("app.log.*") if path.suffix[1:].isdigit()]
        files = sorted(rotated, key=lambda path: -int(path.suffix[1:]))
        files += [path for path in (logs / "app.log", logs / "crash.log") if path.is_file()]
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if text:
            parts += [f"==== {path.name} ====", text, ""]
    # Last, outside _without_user: a dump is bytes, so its account name is hidden byte for byte instead.
    target.write_text(_without_user("\n".join(parts)) + "\n" + _dumps_text(logs), encoding="utf-8")
    return target


# A stuck copy's dump in the export (single.write_dump), compressed and written as text: one file to send.
DUMP_HEADER = "==== {name} (zlib, base64) ===="
DUMP_LINE = 100
DUMP_MAX = 8_000_000


def _dumps_text(logs: Path) -> str:
    parts: list[str] = []
    dumps = sorted(logs.glob("stuck-*.dmp"), key=lambda path: path.stat().st_mtime) if logs.is_dir() else []
    for path in dumps:
        try:
            coded = base64.b64encode(zlib.compress(_dump_without_user(path.read_bytes()), 9)).decode("ascii")
        except OSError:
            continue
        if len(coded) > DUMP_MAX:
            parts += [f"==== {path.name} ====", f"(left out: {len(coded):,} characters)", ""]
            continue
        lines = [coded[start : start + DUMP_LINE] for start in range(0, len(coded), DUMP_LINE)]
        parts += [DUMP_HEADER.format(name=path.name), *lines, ""]
    return "\n".join(parts)


def _dump_without_user(data: bytes) -> bytes:
    """A dump lists the files the copy had loaded, and their paths name the Windows account, as the
    logs' do: the account's folder becomes x's of the same length, so the dump keeps its size and opens."""
    names = {os.environ.get("USERNAME", ""), Path(os.path.expanduser("~")).name} - {""}
    for name in names:
        for sep in ("\\", "/"):
            for encoding in ("utf-16-le", "utf-8", "mbcs"):
                try:
                    found = f"Users{sep}{name}".encode(encoding)
                    hidden = f"Users{sep}".encode(encoding)
                except (LookupError, UnicodeEncodeError):
                    continue
                pad = "x".encode(encoding) * len(name) if encoding == "utf-16-le" else b"x" * (len(found) - len(hidden))
                data = data.replace(found, hidden + pad)
    return data


def dumps_in(text: str) -> dict[str, bytes]:
    """The dumps an export carries, by file name, as they were written (to open in WinDbg or Visual Studio)."""
    found: dict[str, bytes] = {}
    for match in re.finditer(r"^==== (stuck-\d+\.dmp) \(zlib, base64\) ====\n([A-Za-z0-9+/=\n]+)", text, re.MULTILINE):
        found[match.group(1)] = zlib.decompress(base64.b64decode(match.group(2).replace("\n", "")))
    return found


def _without_user(text: str) -> str:
    """Paths in error messages name the Windows account: the export says ~ instead."""
    home = os.path.expanduser("~")
    user = os.environ.get("USERNAME", "")
    for value, mark in ((home, "~"), (home.replace("\\", "/"), "~"), (user, "<user>")):
        if value and len(value) > 2:
            text = text.replace(value, mark)
    return text


def desktop() -> Path:
    """The Desktop, wherever Windows keeps it (it may be in OneDrive)."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        buffer = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0000, None, 0, buffer) == 0 and buffer.value:
            return Path(buffer.value)
    return Path.home() / "Desktop"
