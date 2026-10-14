"""Why Windows will not capture 直播画面: facts and experiments for the log.

On a friend's Windows 10 (22H2, build 19045) Windows refused 直播模式's window with E_INVALIDARG
wherever it was (off the screen, at its edge, on it behind every window) while 直播姬 captured the
game beside it. Where it is refused everywhere, this runs once, in a process of its own, and reports:

- facts: Windows' build, the window's styles and state, its DPI mode, who runs as administrator;
- controls: the window 直播姬 captures for the game (taken there; when it is open), and the taskbar,
  always there and Explorer's; then plain windows made here;
- one difference at a time: windows made here like 直播画面, each without one of its properties;

then what the answers point at. The windows are made by the app's own program (模仿者小工具.exe, as
直播画面 is), and one plain window by pythonw.exe, so the report tells the program from the window.
Every window is asked about from one more process, as 直播姬 asks from its own, and from where it
was made too. They sit behind every window for about a second.

    python -m blacklist_detect.wgc_diagnose <hwnd> [<control hwnd>]    prints the report, a line each
    python -m blacklist_detect.wgc_diagnose --plain                    one plain window, and its answer

Lines start with "fact: ", "test: ", "verdict: " or "fix: " (a property that can go without harm).
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from blacklist_detect import wgc

# Extended window styles, by the names the report uses.
EX_STYLES = (
    (0x00000008, "TOPMOST"),
    (0x00000020, "TRANSPARENT"),
    (0x00000080, "TOOLWINDOW"),
    (0x00040000, "APPWINDOW"),
    (0x00080000, "LAYERED"),
    (0x00200000, "NOREDIRECTIONBITMAP"),
    (0x08000000, "NOACTIVATE"),
)
STYLES = (
    (0x80000000, "POPUP"),
    (0x10000000, "VISIBLE"),
    (0x08000000, "DISABLED"),
    (0x00C00000, "CAPTION"),
    (0x40000000, "CHILD"),
)
# Properties of 直播画面 that can go without changing what viewers see: the window is off the
# screen or behind every window, so it needs no click-through, no-focus or stay-at-bottom.
HARMLESS = ("click-through", "no-focus", "on-bottom")


@dataclass
class Test:
    name: str
    hwnd: int
    # Windows' answer asked from another process, and from this one.
    there: int | None = None
    here: int | None = None


def _flags(value: int, names) -> str:  # noqa: ANN001
    found = [name for bit, name in names if value & bit == bit]
    return "|".join(found) or "none"


def _user32():  # noqa: ANN202
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = (
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    )  # fmt: skip
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT)
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = (wintypes.HWND,)
    user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
    user32.GetWindowDpiAwarenessContext.restype = ctypes.c_void_p
    user32.GetWindowDpiAwarenessContext.argtypes = (wintypes.HWND,)
    user32.GetAwarenessFromDpiAwarenessContext.argtypes = (ctypes.c_void_p,)
    user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    user32.SetThreadDpiAwarenessContext.argtypes = (ctypes.c_void_p,)
    user32.GetDpiForWindow.argtypes = (wintypes.HWND,)
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsIconic.argtypes = (wintypes.HWND,)
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.GetLayeredWindowAttributes.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(wintypes.DWORD))
    user32.SetLayeredWindowAttributes.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_ubyte, wintypes.DWORD)
    user32.GetWindowDisplayAffinity.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.DestroyWindow.argtypes = (wintypes.HWND,)
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    user32.UpdateLayeredWindow.argtypes = (
        wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT), ctypes.POINTER(wintypes.SIZE), wintypes.HDC,
        ctypes.POINTER(wintypes.POINT), wintypes.COLORREF, ctypes.c_void_p, wintypes.DWORD,
    )  # fmt: skip
    return user32


# ---------------------------------------------------------------- facts


def _process_of(user32, hwnd: int) -> int:  # noqa: ANN001
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def program(pid: int) -> str:
    """The file name of a process's program, or "?"."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    process = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not process:
        return "?"
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
            return buffer.value.replace("\\", "/").rsplit("/", 1)[-1]
        return "?"
    finally:
        kernel32.CloseHandle(process)


def elevated(pid: int) -> str:
    """"administrator", "not administrator", or why it cannot be told."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    process = kernel32.OpenProcess(0x1000, False, pid)
    if not process:
        return f"unknown (cannot open it: {ctypes.get_last_error()})"
    token = wintypes.HANDLE()
    try:
        if not advapi32.OpenProcessToken(process, 0x0008, ctypes.byref(token)):  # TOKEN_QUERY
            # A program run as administrator keeps its token from one that is not.
            return "unknown (its token is closed to this app: likely administrator)"
        value, size = wintypes.DWORD(), wintypes.DWORD()
        if not advapi32.GetTokenInformation(token, 20, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(size)):  # TokenElevation
            return "unknown"
        return "administrator" if value.value else "not administrator"
    finally:
        if token:
            kernel32.CloseHandle(token)
        kernel32.CloseHandle(process)


def window_facts(hwnd: int) -> list[str]:
    """What Windows says of a window: its class, styles, state, place, DPI mode and process."""
    user32 = _user32()
    if not user32.IsWindow(hwnd):
        return [f"window {hwnd}: no such window"]
    name = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, name, 256)
    style = user32.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF
    ex = user32.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    out = [
        f"class {name.value}; style 0x{style:08X} ({_flags(style, STYLES)}); "
        f"extended 0x{ex:08X} ({_flags(ex, EX_STYLES)})",
        f"visible {bool(user32.IsWindowVisible(hwnd))}, minimized {bool(user32.IsIconic(hwnd))}, "
        f"top-level {user32.GetAncestor(hwnd, 2) == hwnd}, owned {bool(user32.GetWindow(hwnd, 4))}; "
        f"at ({rect.left}, {rect.top}) {rect.right - rect.left}x{rect.bottom - rect.top}",
    ]
    dwm = ctypes.WinDLL("dwmapi")
    cloaked = wintypes.DWORD()
    bounds = wintypes.RECT()
    cloak = dwm.DwmGetWindowAttribute(wintypes.HWND(hwnd), 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    framed = dwm.DwmGetWindowAttribute(wintypes.HWND(hwnd), 9, ctypes.byref(bounds), ctypes.sizeof(bounds))
    awareness = user32.GetAwarenessFromDpiAwarenessContext(user32.GetWindowDpiAwarenessContext(hwnd))
    dpi_mode = {0: "unaware", 1: "system", 2: "per monitor"}.get(awareness, str(awareness))
    out.append(
        f"cloaked {cloaked.value if cloak == 0 else f'? (0x{cloak & 0xFFFFFFFF:08X})'}; DWM bounds "
        + (f"({bounds.left}, {bounds.top}) {bounds.right - bounds.left}x{bounds.bottom - bounds.top}" if framed == 0 else "?")
        + f"; DPI {user32.GetDpiForWindow(hwnd)} ({dpi_mode})"
    )
    if ex & 0x00080000:
        key, alpha, how = wintypes.DWORD(), ctypes.c_ubyte(), wintypes.DWORD()
        if user32.GetLayeredWindowAttributes(hwnd, ctypes.byref(key), ctypes.byref(alpha), ctypes.byref(how)):
            out.append(f"layered with one alpha {alpha.value} (flags {how.value})")
        else:
            out.append("layered per pixel (UpdateLayeredWindow)")
    affinity = wintypes.DWORD()
    if user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(affinity)):
        out.append(f"display affinity {affinity.value}" + (" (kept out of captures)" if affinity.value else ""))
    pid = _process_of(user32, hwnd)
    out.append(f"process {pid} {program(pid)}, {elevated(pid)}")
    return out


def system_facts() -> list[str]:
    """Windows' version and update, the desktop composition, and 直播姬's processes."""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:

            def value(name: str) -> str:
                try:
                    return str(winreg.QueryValueEx(key, name)[0])
                except OSError:
                    return "?"

            # ProductName says Windows 10 on Windows 11 too: the build (22000 and up is 11) tells them apart.
            version = f"{value('ProductName')} {value('DisplayVersion')}, build {value('CurrentBuild')}.{value('UBR')}"
    except OSError:
        version = "?"
    composed = wintypes.BOOL()
    ctypes.WinDLL("dwmapi").DwmIsCompositionEnabled(ctypes.byref(composed))
    remote = ctypes.windll.user32.GetSystemMetrics(0x1000)
    out = [f"{version}; desktop composition {bool(composed.value)}; remote session {bool(remote)}"]
    from blacklist_detect.single import _processes

    live = [pid for pid, name in _processes() if name.lower() == "livehime.exe"]
    out.append("直播姬: " + ("; ".join(f"process {pid}, {elevated(pid)}" for pid in live) if live else "not running"))
    return out


# ---------------------------------------------------------------- windows made here


class _Blend(ctypes.Structure):
    _fields_ = [("op", ctypes.c_ubyte), ("flags", ctypes.c_ubyte), ("alpha", ctypes.c_ubyte), ("format", ctypes.c_ubyte)]


def _per_pixel(user32, hwnd: int, x: int, y: int, w: int, h: int, pixel: bytes) -> None:  # noqa: ANN001
    """Fill a layered window by UpdateLayeredWindow with one premultiplied BGRA pixel, as Qt fills a
    see-through window."""
    gdi32 = ctypes.WinDLL("gdi32")
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = (wintypes.HDC,)
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = (wintypes.HDC, wintypes.HGDIOBJ)
    gdi32.DeleteObject.argtypes = (wintypes.HGDIOBJ,)
    gdi32.DeleteDC.argtypes = (wintypes.HDC,)

    class Header(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD), ("width", ctypes.c_long), ("height", ctypes.c_long), ("planes", wintypes.WORD),
            ("bits", wintypes.WORD), ("compression", wintypes.DWORD), ("image", wintypes.DWORD), ("xppm", ctypes.c_long),
            ("yppm", ctypes.c_long), ("used", wintypes.DWORD), ("important", wintypes.DWORD),
        ]  # fmt: skip

    header = Header(ctypes.sizeof(Header), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    screen = user32.GetDC(None)
    memory = gdi32.CreateCompatibleDC(screen)
    bits = ctypes.c_void_p()
    gdi32.CreateDIBSection.argtypes = (wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD)
    bitmap = gdi32.CreateDIBSection(memory, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
    old = gdi32.SelectObject(memory, bitmap)
    ctypes.memmove(bits, pixel * (w * h), w * h * 4)
    where, size, origin = wintypes.POINT(x, y), wintypes.SIZE(w, h), wintypes.POINT(0, 0)
    blend = _Blend(0, 0, 255, 1)
    user32.UpdateLayeredWindow(hwnd, screen, ctypes.byref(where), ctypes.byref(size), memory, ctypes.byref(origin), 0, ctypes.byref(blend), 2)
    gdi32.SelectObject(memory, old)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory)
    user32.ReleaseDC(None, screen)


# Plain windows made here: (name, style, extended style, how it is filled, off the screen).
WIN32 = (
    ("plain window", 0x80000000, 0, "paint", False),
    ("titled window", 0x00CF0000, 0, "paint", False),
    ("plain window, DPI unaware", 0x80000000, 0, "paint", False),
    ("plain window, off the screen", 0x80000000, 0, "paint", True),
    ("layered, one alpha", 0x80000000, 0x00080000, "alpha", False),
    ("layered per pixel, half see-through", 0x80000000, 0x00080000, "half", False),
    ("layered per pixel, all clear", 0x80000000, 0x00080000, "clear", False),
    ("click-through (layered + transparent)", 0x80000000, 0x00080020, "alpha", False),
    ("no-activate", 0x80000000, 0x08000000, "paint", False),
    ("styled like 直播画面 (no-activate + layered + transparent, per pixel)", 0x80000000, 0x08080020, "half", False),
)
HALF = bytes((0, 0, 112, 128))  # half see-through red, premultiplied
CLEAR = bytes(4)


def _spot() -> tuple[int, int, int, int]:
    """A small place on the main screen, in its bottom right corner."""
    user32 = ctypes.windll.user32
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    return max(0, width - 260), max(0, height - 200), 240, 135


def make_win32(made: list, only: tuple[str, ...] = ()) -> list[Test]:  # noqa: ANN001
    """The plain windows (those named in only, when given), shown behind every window. made keeps
    what must live until they are asked."""
    user32 = _user32()
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    instance = kernel32.GetModuleHandleW(None)
    procedure = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WndClass(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.UINT), ("style", wintypes.UINT), ("proc", procedure), ("extra", ctypes.c_int),
            ("window_extra", ctypes.c_int), ("instance", wintypes.HINSTANCE), ("icon", wintypes.HICON),
            ("cursor", wintypes.HANDLE), ("background", wintypes.HBRUSH), ("menu", wintypes.LPCWSTR),
            ("name", wintypes.LPCWSTR), ("small_icon", wintypes.HICON),
        ]  # fmt: skip

    default = procedure(ctypes.cast(user32.DefWindowProcW, ctypes.c_void_p).value)
    made.append(default)
    gdi32 = ctypes.WinDLL("gdi32")
    gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
    gray = gdi32.CreateSolidBrush(0x00D0D0D0)
    klass = WndClass(ctypes.sizeof(WndClass), 0, default, 0, 0, instance, None, None, gray, None, "模仿者小工具·测试窗口", None)
    user32.RegisterClassExW(ctypes.byref(klass))
    made.append(klass)
    x, y, w, h = _spot()
    metrics = ctypes.windll.user32.GetSystemMetrics
    beyond = metrics(76) + metrics(78) + 200  # right of every screen: SM_XVIRTUALSCREEN + SM_CXVIRTUALSCREEN
    tests = []
    for name, style, ex, fill, off in WIN32:
        if only and name not in only:
            continue
        left = beyond if off else x
        unaware = "unaware" in name
        before = user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-1)) if unaware else None  # DPI_AWARENESS_CONTEXT_UNAWARE
        hwnd = user32.CreateWindowExW(ex, "模仿者小工具·测试窗口", f"模仿者小工具·测试 {name}", style, left, y, w, h, None, None, instance, None)
        if unaware:
            user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(before))
        if not hwnd:
            tests.append(Test(name, 0))
            continue
        if fill == "alpha":
            user32.SetLayeredWindowAttributes(hwnd, 0, 255, 2)
        elif fill in ("half", "clear"):
            _per_pixel(user32, hwnd, left, y, w, h, HALF if fill == "half" else CLEAR)
        user32.SetWindowPos(hwnd, wintypes.HWND(1), left, y, w, h, 0x0010 | 0x0040)  # HWND_BOTTOM; NOACTIVATE | SHOWWINDOW
        tests.append(Test(name, int(hwnd)))
    return tests


# Windows made with Qt like 直播画面, each without one of its properties: (name, what it leaves out).
QT = (
    ("Qt, like 直播画面", ()),
    ("Qt, like 直播画面, nothing drawn", ("drawn",)),
    ("Qt, without see-through background", ("see-through",)),
    ("Qt, without click-through", ("click-through",)),
    ("Qt, without no-focus", ("no-focus",)),
    ("Qt, without on-bottom", ("on-bottom",)),
    ("Qt, not layered (no see-through, no click-through)", ("see-through", "click-through")),
    ("Qt, plain window", ("see-through", "click-through", "no-focus", "on-bottom")),
)


def make_qt(made: list) -> list[Test]:  # noqa: ANN001
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QPainter, QPen
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication.instance() or QApplication([])
    made.append(app)

    class Probe(QWidget):
        def __init__(self, without: tuple[str, ...]) -> None:
            flags = Qt.FramelessWindowHint | Qt.Window
            if "on-bottom" not in without:
                flags |= Qt.WindowStaysOnBottomHint
            if "no-focus" not in without:
                flags |= Qt.WindowDoesNotAcceptFocus
            if "click-through" not in without:
                flags |= Qt.WindowTransparentForInput
            super().__init__(None, flags)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            if "see-through" not in without:
                self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.drawn = "drawn" not in without

        def paintEvent(self, _event) -> None:  # noqa: ANN001
            if self.drawn:
                painter = QPainter(self)
                painter.setPen(QPen(QColor(225, 38, 52), 4))
                painter.drawRect(self.rect().adjusted(2, 2, -2, -2))
                painter.end()

    x, y, w, h = _spot()
    tests = []
    for name, without in QT:
        probe = Probe(without)
        probe.setWindowTitle(f"模仿者小工具·测试 {name}")
        probe.setGeometry(QRect(x, y, w, h))
        probe.show()
        probe.lower()
        made.append(probe)
        tests.append(Test(name, int(probe.winId())))
    return tests


def settle(seconds: float = 0.4) -> None:
    """Let the windows made here be shown and drawn."""
    end = time.monotonic() + seconds
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        QApplication = None  # noqa: N806
    user32 = ctypes.windll.user32
    message = wintypes.MSG()
    while time.monotonic() < end:
        if QApplication is not None and QApplication.instance() is not None:
            QApplication.processEvents()
        while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        time.sleep(0.02)


def plain_by_pythonw() -> int | None:
    """Windows' answer for a plain window made by pythonw.exe (the program that asks), asked there."""
    program, _arguments, folder = wgc.command(0)
    try:
        done = subprocess.run(
            [program, "-m", "blacklist_detect.wgc_diagnose", "--plain"],
            cwd=folder, capture_output=True, text=True, timeout=60, check=False, creationflags=0x08000000,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None
    return wgc.read(done.stdout)


def ask_elsewhere(hwnds: list[int]) -> list[int | None]:
    """Windows' answer for each window, asked from one more process, as 直播姬 asks from its own."""
    program, arguments, folder = wgc.command(0)
    try:
        done = subprocess.run(
            [program, *arguments[:-1], *(str(hwnd) for hwnd in hwnds)],
            cwd=folder, capture_output=True, text=True, timeout=60, check=False, creationflags=0x08000000,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return [None] * len(hwnds)
    answers = [wgc.read(line) for line in done.stdout.splitlines()]
    return answers + [None] * (len(hwnds) - len(answers))


# ---------------------------------------------------------------- what it points at


def verdict(tests: list[Test]) -> tuple[str, str]:
    """What the answers point at, and a harmless property to leave out ("" when none would help)."""
    taken = {test.name: test.there == wgc.ACCEPTED for test in tests if test.there is not None}
    if not taken:
        return "Windows could not be asked (no Windows.Graphics.Capture, or the asking process failed).", ""
    if taken.get("直播画面 itself"):
        return "Windows takes 直播画面 now.", ""
    controls = [test.name for test in tests if test.name.startswith("control") and test.there is not None]
    if controls and not any(taken[name] for name in controls):
        return "Windows refuses even the control windows: the asking is blocked on this PC, not 直播画面.", ""
    if taken.get("plain window") is False and taken.get("titled window") is False:
        if taken.get(BY_PYTHONW):
            return ("Windows takes a plain window made by pythonw.exe and none made by 模仿者小工具.exe: it is about the "
                    "app's program file (its name or what it says of itself), not how the window is made."), ""  # fmt: skip
        return ("Windows takes other programs' windows but no window made by this app: it is about the app's "
                "programs, not how the window is made."), ""  # fmt: skip
    plain_names = {name for name, *_rest in WIN32}
    refused = [test.name for test in tests if test.name in plain_names and taken.get(test.name) is False]
    plain = f" Windows also refuses these plain windows: {', '.join(refused)}." if refused else ""
    if taken.get("Qt, like 直播画面"):
        return "A fresh window like 直播画面 is taken: something about the running 直播画面 differs (its state or what it shows)." + plain, ""
    flips = [without for name, without in QT[2:] if taken.get(name)]
    if not flips:
        return "No single difference from 直播画面 made Windows take it." + plain, ""
    smallest = min(flips, key=len)
    named = " and ".join(smallest)
    fix = next((single[0] for single in flips if len(single) == 1 and single[0] in HARMLESS), "")
    return f"Without {named} Windows takes it: {named} is what Windows refuses here." + plain, fix


BY_PYTHONW = "plain window made by pythonw.exe"
TASKBAR = "control: the taskbar (Explorer's)"


def report(hwnd: int, control: int) -> list[str]:
    lines = [f"fact: {line}" for line in system_facts()]
    lines.append(f"fact: the windows below are made by {Path(sys.executable).name}, administrator: {elevated(os.getpid())}")
    lines += [f"fact: 直播画面: {line}" for line in window_facts(hwnd)]
    tests = [Test("直播画面 itself", hwnd)]
    if control:
        lines += [f"fact: control (the game window 直播姬 captures): {line}" for line in window_facts(control)]
        tests.append(Test("control: the game window 直播姬 captures", control))
    taskbar = _user32().FindWindowW("Shell_TrayWnd", None)
    if taskbar:
        tests.append(Test(TASKBAR, int(taskbar)))
    made: list = []
    tests += make_win32(made)
    try:
        tests += make_qt(made)
    except ImportError:
        lines.append("fact: Qt windows could not be made here")
    settle()
    asked = [test for test in tests if test.hwnd > 0]
    for test, answer in zip(asked, ask_elsewhere([test.hwnd for test in asked]), strict=True):
        test.there = answer
        test.here = wgc.answer(test.hwnd)
    tests.append(Test(BY_PYTHONW, -1, there=plain_by_pythonw()))
    for test in tests:
        shown = wgc.words(test.there) if test.hwnd else "could not be made"
        if test.hwnd > 0 and test.here != test.there:
            shown += f" (asked from where it was made: {wgc.words(test.here)})"
        lines.append(f"test: {test.name}: {shown}")
    found, fix = verdict(tests)
    lines.append(f"verdict: {found}")
    if fix:
        lines.append(f"fix: {fix}")
    return lines


def command(hwnd: int, control: int) -> tuple[str, list[str], str]:
    """Program, arguments and folder that run the report from a process of its own, with no console:
    the app's own program, as 直播画面's window is made by (pythonw.exe where that is python.exe)."""
    program = Path(sys.executable)
    if program.name.lower() == "python.exe" and program.with_name("pythonw.exe").is_file():
        program = program.with_name("pythonw.exe")
    _program, _arguments, folder = wgc.command(hwnd)
    return str(program), ["-m", "blacklist_detect.wgc_diagnose", str(hwnd), str(control)], folder


if __name__ == "__main__":
    # The app reads the report as UTF-8, whatever the console's code page.
    sys.stdout.reconfigure(encoding="utf-8")
    # Per-monitor DPI awareness, as the app's windows have (Qt asks for it too, and says it was set).
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    if sys.argv[1:] == ["--plain"]:
        kept: list = []
        window = make_win32(kept, only=("plain window",))[0]
        settle()
        result = wgc.answer(window.hwnd) if window.hwnd else None
        print("none" if result is None else f"0x{result:08X}")
    else:
        for line in report(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 0):
            print(line, flush=True)
