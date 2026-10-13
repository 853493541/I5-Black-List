"""Why a check was slow, and one text file of the logs a friend can send.

The log says where each check's time went. This adds what explains it: how busy the computer was
while the check ran (and how much of that was this app), whether a laptop ran on battery or
battery saver, and once at each start, what the computer is. The export puts that summary and the
logs in one text file on the Desktop. Nothing here holds a player's name or the lists; the summary
is for whoever reads the file, and is never shown in the app.
"""

from __future__ import annotations

import os
import platform
import sys
import time
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


def summary_text(store, device: str) -> str:  # noqa: ANN001
    """What the export says about this computer and the app's settings. Counts only, no names."""
    lines = [
        f"模仿者小工具 {__version__}",
        f"导出于 {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        machine_line(),
        f"Screens: {screens_line()}",
        f"Recognition on {device}",
        f"安全模式 {store.safe_mode}, 自动检查 {store.auto_capture}, 直播模式 {bool(store.stream_mode)}, hotkey {store.hotkey}",
        f"黑名单 {len(store.entries)} people, 心动 {len(store.likes)} people, 记录 {len(store.scans)} lobbies",
    ]
    return "\n".join(lines) + "\n"


def export_logs(root: Path, summary: str, folder: Path | None = None) -> Path:
    """One text file on the Desktop (unless told where): the computer, then the logs, oldest first.
    Returns its path."""
    folder = folder or desktop()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"模仿者小工具_日志_{time.strftime('%Y%m%d-%H%M')}.txt"
    parts = ["==== 电脑和设置 ====", summary]
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
    target.write_text(_without_user("\n".join(parts)) + "\n", encoding="utf-8")
    return target


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
