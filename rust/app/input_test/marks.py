r"""The marks come down and the window stays clickable (the v3.2 P0s: marks stuck on the game, nothing clickable after).

    python -I marks.py <folder with the exe, onnxruntime.dll, models, assets> <exe name> <work folder> <report folder>

On a Windows runner at 1920x1080: the sample lobby full-screen (check_visible.py's frame), Notepad in front, Alt+1.
  marks up       Check 1 shown, the marks' window (BlacklistDetectMarks) visible, the screen changed where it sits
  click-through  WindowFromPoint at the marks' middle is not the marks' window
  marks down     the lobby frame closed: polled every 0.4 s for 10 s, the window hidden and the screen back
                 (v1.0.1: a glance that no longer sees 推演成功 takes them down, ui.py:3691)
  next check     the frame back, Alt+1 again: Check 2 shown and marks up again
  clicks after   the frame closed and the marks down: the main window restored, 黑名单 then 嘉宾 clicked with
                 SendInput where UIAutomation puts them, each page shown
Every topmost visible window (class, ex-style, rect) is listed after each step. Silent; an APPDATA of its own.
"""

import ctypes
import re
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_visible import App, Lobby, press, record, results, tail, title, user32, windows_of  # noqa: E402

import uiautomation as auto  # noqa: E402
from PIL import ImageChops, ImageGrab  # noqa: E402

MARKS = "BlacklistDetectMarks"
WS_EX_TOPMOST = 0x8


def class_of(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def rect_of(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def ex_style(hwnd: int) -> int:
    return user32.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF


def topmost(note: str, pid: int) -> None:
    """Every visible topmost window on the desktop, the app's marked with *."""
    rows: list[str] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):  # noqa: ANN001
        if user32.IsWindowVisible(hwnd) and ex_style(hwnd) & WS_EX_TOPMOST:
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            mine = "*" if owner.value == pid else " "
            rows.append(f"    {mine} {hwnd:#x} {class_of(hwnd)!r} {title(hwnd)[:30]!r} ex {ex_style(hwnd):#010x} {rect_of(hwnd)}")
        return True

    user32.EnumWindows(each, 0)
    print(f"  topmost windows, {note}:")
    print("\n".join(rows) or "    (none)")


def marks_window(pid: int) -> int | None:
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):  # noqa: ANN001
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and class_of(hwnd) == MARKS:
            found.append(hwnd)
        return True

    user32.EnumWindows(each, 0)
    return found[0] if found else None


def marks_up(pid: int) -> bool:
    hwnd = marks_window(pid)
    return bool(hwnd and user32.IsWindowVisible(hwnd))


def changed(before, after, box) -> int:
    """How many pixels in `box` differ by more than a little."""
    diff = ImageChops.difference(before.crop(box), after.crop(box)).convert("L").point(lambda v: 255 if v > 24 else 0)
    return sum(diff.histogram()[1:])


def errors_since(app: App, start: int) -> str:
    return "; ".join(re.findall(r"[^\n]*(?:step:|Header:|Overlay:|failed)[^\n]*", app.text()[start:]))[-500:]


def check(app: App, lobby: Lobby, notepad, number: int, report: Path) -> bool:
    start = press(app, lobby, notepad)
    shown = app.wait(rf"Check {number} shown: [^\n]*", 180, lobby, start)
    record(f"check {number} shown", shown is not None, shown.group(0) if shown else tail(app, start)[-300:])
    lobby.pump(0.5)
    ImageGrab.grab(all_screens=True).save(report / f"check-{number}.png")
    return shown is not None


def main() -> int:
    folder, exe_name, work, report = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    report.mkdir(parents=True, exist_ok=True)
    print(f"Screen {user32.GetSystemMetrics(0)}x{user32.GetSystemMetrics(1)}")
    lobby = Lobby()
    import subprocess

    notepad = subprocess.Popen(["notepad.exe"])
    app = App(folder / f"{exe_name}.exe", work / "marks")
    try:
        ok = app.wait(r"Hotkeys registered", 30, lobby) is not None
        record("starts, hotkeys registered", ok, tail(app)[-200:])
        lobby.pump(1.0)
        app.minimise()
        lobby.tk.attributes("-topmost", True)
        lobby.pump(1.0)
        bare = ImageGrab.grab(all_screens=True)
        topmost("before the first check", app.proc.pid)

        # 1. Marks up over the lobby, and click-through.
        check(app, lobby, notepad, 1, report)
        hwnd = marks_window(app.proc.pid)
        box = rect_of(hwnd) if hwnd else (0, 0, 1, 1)
        up = ImageGrab.grab(all_screens=True)
        record("marks up: the marks' window visible", marks_up(app.proc.pid), f"hwnd {hwnd and hex(hwnd)} rect {box}")
        record("marks up: the screen changed where they sit", changed(bare, up, box) > 500, f"{changed(bare, up, box)} pixels")
        middle = wintypes.POINT((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
        under = user32.WindowFromPoint(middle)
        record("marks are click-through", class_of(under) != MARKS, f"WindowFromPoint {under:#x} {class_of(under)!r}")
        topmost("marks up", app.proc.pid)

        # 2. The lobby goes: the marks come down by the glance.
        start = len(app.text())
        lobby.tk.withdraw()
        went = None
        began = time.time()
        while time.time() - began < 10:
            lobby.pump(0.4)
            if not marks_up(app.proc.pid):
                went = time.time() - began
                break
        gone = ImageGrab.grab(all_screens=True)
        gone.save(report / "lobby-closed.png")
        record("marks down once the lobby is gone", went is not None,
               f"after {went:.1f} s" if went is not None else f"still up after 10 s; log: {errors_since(app, start) or tail(app, start)[-400:]}")
        topmost("lobby closed", app.proc.pid)

        # 3. The next check over the lobby: marks again.
        lobby.tk.deiconify()
        lobby.tk.attributes("-topmost", True)
        lobby.pump(1.0)
        check(app, lobby, notepad, 2, report)
        record("next check: marks up again", marks_up(app.proc.pid), errors_since(app, 0)[-200:])

        # 4. Lobby gone, marks down, then the main window's buttons by real clicks.
        lobby.tk.withdraw()
        for _ in range(25):
            lobby.pump(0.4)
            if not marks_up(app.proc.pid):
                break
        main_hwnd = next((h for h in windows_of(app.proc.pid) if class_of(h) != MARKS and title(h).startswith("模仿者小工具")), None)
        if main_hwnd is None:
            for h in windows_of(app.proc.pid):
                print(f"  app window {h:#x} {class_of(h)!r} {title(h)!r}")
        for h in [main_hwnd] if main_hwnd else []:
            user32.ShowWindow(h, 9)  # SW_RESTORE
            user32.keybd_event(0x12, 0, 0, 0)
            user32.SetForegroundWindow(h)
            user32.keybd_event(0x12, 0, 2, 0)
        lobby.pump(1.5)
        topmost("main window restored", app.proc.pid)
        window = auto.ControlFromHandle(main_hwnd) if main_hwnd else None
        for tab, sign in (("黑名单", "批量导入"), ("嘉宾", "添加嘉宾")):
            control = window.TabItemControl(searchDepth=30, Name=tab) if window else None
            if control is None or not control.Exists(3, 0.3):
                record(f"click after marks: {tab}", False, "UIAutomation does not see it")
                continue
            r = control.BoundingRectangle
            x, y = (r.left + r.right) // 2, (r.top + r.bottom) // 2
            point_under = user32.WindowFromPoint(wintypes.POINT(x, y))
            page = rect_of(main_hwnd)
            before = ImageGrab.grab(bbox=page, all_screens=True)
            auto.Click(x, y)
            lobby.pump(1.0)
            redrawn = ImageChops.difference(before, ImageGrab.grab(bbox=page, all_screens=True)).getbbox() is not None
            seen = window.ButtonControl(searchDepth=30, Name=sign).Exists(3, 0.3)
            record(f"click after marks: {tab} shows its page", seen and redrawn,
                   f"under the click {point_under:#x} {class_of(point_under)!r}; redrawn {redrawn}; {sign} seen {seen}")
        ImageGrab.grab(all_screens=True).save(report / "after-clicks.png")
        print(f"  log tail: {tail(app)[-1500:]}")
    finally:
        app.stop()
        notepad.kill()
    failed = [name for name, ok, _ in results if not ok]
    summary = f"{len(results) - len(failed)} passed, {len(failed)} failed"
    print(summary + (f": {failed}" if failed else ""))
    (report / "failures.txt").write_text(
        "\n".join([summary] + [f"FAIL {n}: {d}" for n, ok, d in results if not ok]), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
