r"""The marks come down and the window stays clickable (the v3.2 P0s: marks stuck on the game, nothing clickable after).

    python -I marks.py <folder with the exe, onnxruntime.dll, models, assets> <exe name> <work folder> <report folder>

On a Windows runner at 1920x1080, three cases, each a fresh app in an APPDATA of its own, Notepad in front, Alt+1:
  full      the sample lobby full-screen (check_visible.py's frame)
  guest     the same, with 心动小鹿 (in the sample lobby) a 嘉宾: Check shown Liked, its scene plays and ends first
  windowed  the lobby in a 1600x900 window with a title bar, not full-screen (MuMu windowed)
Each case asserts:
  marks up       Check 1 shown, the marks' window (BlacklistDetectMarks) visible, the screen changed where it sits
  click-through  WindowFromPoint at the marks' middle is not the marks' window
  marks down     the lobby closed: polled every 0.4 s for 10 s, the window hidden
                 (v1.0.1: a glance that no longer sees 推演成功 takes them down, ui.py:3691)
  next check     the lobby back, Alt+1 again: Check 2 shown and marks up again
  clicks after   the lobby closed and the marks down: the main window restored, 黑名单 then 嘉宾 clicked with
                 SendInput where UIAutomation puts the tabs, each page shown and the window redrawn
Every topmost visible window (class, ex-style, rect) is listed after each step. Silent.
"""

import ctypes
import json
import re
import subprocess
import sys
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_visible import FOLDER, ROOT, App, Lobby, press, record, results, tail, title, user32, windows_of  # noqa: E402

import uiautomation as auto  # noqa: E402
from PIL import Image, ImageChops, ImageGrab, ImageTk  # noqa: E402

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
    return "; ".join(re.findall(r"[^\n]*(?:step:|Header:|Overlay:|failed|Scene )[^\n]*", app.text()[start:]))[-600:]


class Windowed:
    """The lobby in a 1600x900 window with a title bar at (160, 60), as MuMu shows a game not full-screen; it
    stands in for check_visible's Lobby (same tk, pump, top)."""

    def __init__(self, lobby: Lobby) -> None:
        self.tk = tk.Toplevel(lobby.tk)
        self.lobby = lobby
        width, height = 1600, 900
        crop = Image.open(ROOT / "blacklist_detect" / "assets" / "sample-lobby.jpg").convert("RGB")
        scale = min(width * 0.9 / crop.width, height * 0.82 / crop.height)
        crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
        frame = Image.new("RGB", (width, height))
        frame.paste(crop, ((width - crop.width) // 2, (height - crop.height) // 2))
        self.photo = ImageTk.PhotoImage(frame)
        self.tk.title("MuMu 模拟器 (windowed lobby)")
        self.tk.geometry(f"{width}x{height}+160+60")
        self.tk.attributes("-topmost", True)
        tk.Label(self.tk, image=self.photo, borderwidth=0).pack()
        self.top = 60
        self.pump(1.0)
        print(f"  windowed lobby {width}x{height} at (160, 60), crop {crop.width}x{crop.height}")

    def pump(self, seconds: float) -> None:
        self.lobby.pump(seconds)


def start(exe: Path, home: Path, likes: list[str]) -> App:
    """check_visible's App, with likes.json in place before the exe starts."""
    import shutil

    if not likes:
        return App(exe, home)
    original = subprocess.Popen

    def popen_after_likes(*args, **kwargs):  # noqa: ANN002, ANN003
        data = home / FOLDER
        likes_json = {"likes": [{"name": n, "nickname": "", "reason": ""} for n in likes],
                      "combos": []}
        (data / "likes.json").write_text(json.dumps(likes_json, ensure_ascii=False), encoding="utf-8")
        return original(*args, **kwargs)

    subprocess.Popen = popen_after_likes
    try:
        shutil.rmtree(home, ignore_errors=True)
        return App(exe, home)
    finally:
        subprocess.Popen = original


def check(case: str, app: App, lobby, notepad, number: int, report: Path) -> str:
    start_at = press(app, lobby, notepad)
    shown = app.wait(rf"Check {number} shown: [^\n]*", 180, lobby, start_at)
    record(f"{case}: check {number} shown", shown is not None, shown.group(0) if shown else tail(app, start_at)[-300:])
    lobby.pump(0.5)
    ImageGrab.grab(all_screens=True).save(report / f"{case}-check-{number}.png")
    return shown.group(0) if shown else ""


def wait_down(app: App, lobby, seconds: float) -> float | None:
    began = time.time()
    while time.time() - began < seconds:
        lobby.pump(0.4)
        if not marks_up(app.proc.pid):
            return time.time() - began
    return None


def run(case: str, exe: Path, work: Path, report: Path, root: Lobby, notepad, likes: list[str], windowed: bool) -> None:
    lobby = Windowed(root) if windowed else root
    if windowed:
        root.tk.withdraw()
    else:
        # The case before ended with the lobby closed: each case starts with it up.
        root.tk.deiconify()
        root.tk.attributes("-topmost", True)
        root.pump(1.0)
    app = start(exe, work / case, likes)
    try:
        ok = app.wait(r"Hotkeys registered", 30, root) is not None
        record(f"{case}: starts, hotkeys registered", ok, tail(app)[-200:])
        root.pump(1.0)
        app.minimise()
        lobby.tk.attributes("-topmost", True)
        root.pump(1.0)
        bare = ImageGrab.grab(all_screens=True)
        topmost(f"{case}, before the first check", app.proc.pid)

        # 1. Marks up over the lobby, and click-through.
        line = check(case, app, lobby, notepad, 1, report)
        if likes:
            record(f"{case}: the 嘉宾 greets (Liked)", "Liked" in line, line)
            played = app.wait(r"Scene [^\n]*(playing via|not played)[^\n]*", 20, root)
            print(f"  scene: {played.group(0) if played else 'no scene line'}")
            root.pump(8.0)  # the scene (玫瑰花边, 4.6 s) plays to its end with the lobby still up
            print(f"  after the scene: {errors_since(app, 0)[-300:]}")
        hwnd = marks_window(app.proc.pid)
        box = rect_of(hwnd) if hwnd else (0, 0, 1, 1)
        up = ImageGrab.grab(all_screens=True)
        record(f"{case}: marks up", marks_up(app.proc.pid), f"hwnd {hwnd and hex(hwnd)} rect {box}")
        record(f"{case}: the screen changed where they sit", changed(bare, up, box) > 500, f"{changed(bare, up, box)} pixels")
        middle = wintypes.POINT((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
        under = user32.WindowFromPoint(middle)
        record(f"{case}: marks are click-through", class_of(under) != MARKS, f"WindowFromPoint {under:#x} {class_of(under)!r}")
        topmost(f"{case}, marks up", app.proc.pid)

        # 2. The lobby goes: the marks come down by the glance.
        start_at = len(app.text())
        lobby.tk.withdraw()
        went = wait_down(app, root, 10)
        ImageGrab.grab(all_screens=True).save(report / f"{case}-lobby-closed.png")
        record(f"{case}: marks down once the lobby is gone", went is not None,
               f"after {went:.1f} s" if went is not None else f"still up after 10 s; log: {errors_since(app, start_at) or tail(app, start_at)[-400:]}")
        topmost(f"{case}, lobby closed", app.proc.pid)

        # 3. The next check over the lobby: marks again.
        lobby.tk.deiconify()
        lobby.tk.attributes("-topmost", True)
        root.pump(1.0)
        check(case, app, lobby, notepad, 2, report)
        record(f"{case}: next check, marks up again", marks_up(app.proc.pid), errors_since(app, start_at)[-200:])

        # 4. Lobby gone, marks down, then the main window's tabs by real clicks.
        start_at = len(app.text())
        if likes:
            played = app.wait(r"Scene [^\n]*(playing via|not played)[^\n]*", 20, root, start_at - 2000)
            print(f"  check 2 scene: {played.group(0) if played else 'no scene line'}")
            root.pump(8.0)  # the scene plays to its end with the lobby still up
        lobby.tk.withdraw()
        went = wait_down(app, root, 10)
        record(f"{case}: marks down after check 2{' and its scene' if likes else ''}", went is not None,
               f"after {went:.1f} s" if went is not None else f"still up after 10 s; log: {errors_since(app, start_at) or tail(app, start_at)[-400:]}")
        main_hwnd = next((h for h in windows_of(app.proc.pid) if class_of(h) != MARKS and title(h).startswith("模仿者小工具")), None)
        if main_hwnd is None:
            for h in windows_of(app.proc.pid):
                print(f"  app window {h:#x} {class_of(h)!r} {title(h)!r}")
        else:
            user32.ShowWindow(main_hwnd, 9)  # SW_RESTORE
            user32.keybd_event(0x12, 0, 0, 0)
            user32.SetForegroundWindow(main_hwnd)
            user32.keybd_event(0x12, 0, 2, 0)
        root.pump(1.5)
        topmost(f"{case}, main window restored", app.proc.pid)
        window = auto.ControlFromHandle(main_hwnd) if main_hwnd else None
        # A page's sign: a control only that page has (嘉宾 with no one listed shows its empty state's buttons).
        for tab, signs in (("黑名单", ("批量导入",)), ("嘉宾", ("添加嘉宾", "场景管理"))):
            control = window.TabItemControl(searchDepth=30, Name=tab) if window else None
            if control is None or not control.Exists(3, 0.3):
                record(f"{case}: click after marks: {tab}", False, "UIAutomation does not see the tab")
                continue
            r = control.BoundingRectangle
            x, y = (r.left + r.right) // 2, (r.top + r.bottom) // 2
            point_under = user32.WindowFromPoint(wintypes.POINT(x, y))
            page = rect_of(main_hwnd)
            before = ImageGrab.grab(bbox=page, all_screens=True)
            auto.Click(x, y)
            root.pump(1.0)
            redrawn = ImageChops.difference(before, ImageGrab.grab(bbox=page, all_screens=True)).getbbox() is not None
            seen = [sign for sign in signs if window.Control(searchDepth=30, Name=sign).Exists(2, 0.3)]
            record(f"{case}: click after marks: {tab} shows its page", bool(seen) and redrawn,
                   f"under the click {point_under:#x} {class_of(point_under)!r}; redrawn {redrawn}; seen {seen} of {signs}")
        ImageGrab.grab(all_screens=True).save(report / f"{case}-after-clicks.png")
        print(f"  {case} log tail: {tail(app)[-1200:]}")
    finally:
        app.stop()
        if windowed:
            lobby.tk.destroy()
            root.tk.deiconify()
            root.tk.attributes("-topmost", True)
            root.pump(0.5)


def main() -> int:
    folder, exe_name, work, report = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    report.mkdir(parents=True, exist_ok=True)
    exe = folder / f"{exe_name}.exe"
    print(f"Screen {user32.GetSystemMetrics(0)}x{user32.GetSystemMetrics(1)}")
    root = Lobby()
    notepad = subprocess.Popen(["notepad.exe"])
    try:
        for case, likes, windowed in (("full", [], False), ("guest", ["心动小鹿"], False), ("windowed", [], True)):
            try:
                run(case, exe, work, report, root, notepad, likes, windowed)
            except Exception as error:  # noqa: BLE001
                record(f"{case}: ran to the end", False, f"{type(error).__name__}: {error}")
    finally:
        notepad.kill()
    failed = [name for name, ok, _ in results if not ok]
    summary = f"{len(results) - len(failed)} passed, {len(failed)} failed"
    print(summary + (f": {failed}" if failed else ""))
    (report / "failures.txt").write_text(
        "\n".join([summary] + [f"FAIL {n}: {d}" for n, ok, d in results if not ok]), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
