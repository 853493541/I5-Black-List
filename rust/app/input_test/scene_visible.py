r"""A hotkey check that finds a 嘉宾 plays the 嘉宾's scene over the game (P0-2), and leaves nothing behind (P0-3).

    python -I scene_visible.py <preview folder> <exe name> <work folder> <report folder>

On a Windows runner at 1920x1080, as check_visible.py: the sample lobby (made-up names 示例坏人, 心动小鹿, 心动星星)
full-screen, Notepad in front, Alt+1 by SendInput. likes.json is seeded with 心动小鹿 on 玫瑰花边 (lace), 我 on 不放.
Asserted:
  plays       the log says the scene plays ("Scene lace: playing via ...") after "Check 1 shown"
  on screen   a copy of the desktop mid-scene differs from the copy after it, over the game (the scene's pixels; the
              lace is a border, so a share over 0.5 %)
  lasts       no glance or check stops it early: still on screen 2 s in (the glance runs every 0.4 s)
  click-through  the point under the scene belongs to the lobby window, not the stage's
  gone        after the scene: no visible BlacklistDetectStage window, and the desktop is back to the marks alone
  clicks      SendInput clicks across the main window's header, during the scene and after it, change what it shows
              (a page, a press) and its thread answers (a thread-wide message pump in the scene took them away)
Silent (BLACKLIST_DETECT_SILENT=1), in an APPDATA of its own.
"""

import ctypes
import json
import re
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_visible as cv  # noqa: E402  (its Lobby, App, press, started and SendInput helpers)
from PIL import ImageChops, ImageGrab  # noqa: E402

user32 = cv.user32
user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT,
                                       wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetForegroundWindow.restype = wintypes.HWND
STAGE_CLASS = "BlacklistDetectStage"


class SceneApp(cv.App):
    """check_visible's App with likes.json seeded before the start: 心动小鹿 on lace, 我 on 不放."""

    def __init__(self, exe: Path, home: Path) -> None:
        import os
        import shutil

        shutil.rmtree(home, ignore_errors=True)
        self.data = home / cv.FOLDER
        self.data.mkdir(parents=True)
        settings = {"disclaimer_accepted": True, "consented": ["full"], "safe_mode": False, "auto_capture": False,
                    "hotkey": "Alt+1"}
        (self.data / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        likes = {"likes": [{"name": "心动小鹿", "nickname": "", "reason": "", "added_at": "2026-11-19 08:00:00",
                            "scenes": ["lace"], "random": False}],
                 "combos": [], "me": {"scenes": [], "random": False}}
        (self.data / "likes.json").write_text(json.dumps(likes, ensure_ascii=False), encoding="utf-8")
        env = dict(os.environ, APPDATA=str(home), LOCALAPPDATA=str(home), USERPROFILE=str(home),
                   BLACKLIST_DETECT_SILENT="1")
        self.log = self.data / "logs" / "app.log"
        self.proc = subprocess.Popen([str(exe)], env=env, cwd=str(home))


def class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def stage_windows(pid: int) -> list[int]:
    return [hwnd for hwnd in cv.windows_of(pid) if class_name(hwnd) == STAGE_CLASS and user32.IsWindowVisible(hwnd)]


def changed_share(a, b) -> float:
    """The share of pixels that differ by more than 40 in some channel."""
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).convert("L").point(lambda v: 255 if v > 40 else 0)
    return sum(diff.histogram()[255:]) / (a.width * a.height)


def under(x: int, y: int) -> int:
    return user32.WindowFromPoint(wintypes.POINT(x, y))


def click(x: int, y: int) -> None:
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT), ("pad", ctypes.c_byte * 32)]
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    user32.SetCursorPos(x, y)
    events = [INPUT(type=0, mi=MOUSEINPUT(dwFlags=0x0002)), INPUT(type=0, mi=MOUSEINPUT(dwFlags=0x0004))]
    array = (INPUT * 2)(*events)
    user32.SendInput(2, array, ctypes.sizeof(INPUT))


def main_window(pid: int) -> int:
    """The app's main window, by its title (the marks over the game are a bigger window of the same app)."""
    for hwnd in cv.windows_of(pid):
        if cv.title(hwnd).startswith("模仿者小工具"):
            return hwnd
    return 0


def answers(hwnd: int) -> bool:
    out = ctypes.c_size_t()
    return bool(user32.SendMessageTimeoutW(hwnd, 0, 0, 0, 0x0002, 2000, ctypes.byref(out)))  # WM_NULL, ABORTIFHUNG


def grab(hwnd: int):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True)


def bring_main(app, lobby) -> int:
    """The main window restored, in front of the lobby (which stops being topmost), in the screen's bottom-right."""
    hwnd = main_window(app.proc.pid)
    lobby.tk.attributes("-topmost", False)
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    user32.SetWindowPos(hwnd, -1, width - 960, height - 640, 0, 0, 0x0001 | 0x0040)  # TOPMOST, NOSIZE | SHOWWINDOW
    lobby.pump(0.8)
    return hwnd


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
                ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT)]


def named(hwnd) -> str:
    return f"{class_name(hwnd or 0)!r}/{cv.title(hwnd or 0)!r}" if hwnd else "none"


def thread_state(hwnd: int) -> str:
    """What the main window's UI thread holds: capture, focus, active, menu or move mode; enabled; the foreground."""
    info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    got = user32.GetGUIThreadInfo(tid, ctypes.byref(info))
    flags = {0x1: "caret", 0x2: "in-move-size", 0x4: "in-menu-mode", 0x8: "system-menu", 0x10: "popup-menu"}
    shown = [name for bit, name in flags.items() if info.flags & bit]
    return (f"thread info {bool(got)}: capture {named(info.hwndCapture)}, focus {named(info.hwndFocus)}, "
            f"active {named(info.hwndActive)}, menu owner {named(info.hwndMenuOwner)}, flags {shown or 'none'}; "
            f"main enabled {bool(user32.IsWindowEnabled(hwnd))}; foreground {named(user32.GetForegroundWindow())}")


def clicks_work(hwnd: int, lobby, when: str, report: Path) -> None:
    """SendInput clicks on a 3x3 grid over the window (the title bar's corner left alone): at least one changes what
    it shows (a page, a press), and its thread answers."""
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    changed, points = 0, []
    for i in range(1, 4):
        for j in range(1, 4):
            x = rect.left + (rect.right - rect.left) * i // 5
            y = rect.top + 60 + (rect.bottom - rect.top - 60) * j // 4
            before = grab(hwnd)
            target = under(x, y)
            click(x, y)
            lobby.pump(0.3)
            moved = ImageChops.difference(before.convert("RGB"), grab(hwnd).convert("RGB")).getbbox() is not None
            changed += moved
            mine = target == hwnd or user32.IsChild(hwnd, target)
            points.append(f"({x},{y}){'*' if moved else ''}{'' if mine else ' over ' + named(target)}")
    grab(hwnd).save(report / f"main-{when}.png")
    print(f"  {when}: {thread_state(hwnd)}")
    cv.record(f"clicks on the main window work {when}", changed > 0 and answers(hwnd),
              f"{changed} of 9 clicks changed {cv.title(hwnd)!r}: {' '.join(points)}; answers {answers(hwnd)}; "
              f"IsHungAppWindow {bool(user32.IsHungAppWindow(hwnd))}")


def run(exe: Path, work: Path, report: Path) -> None:
    lobby = cv.Lobby()
    notepad = subprocess.Popen(["notepad.exe"])
    app = SceneApp(exe, work / "scene")
    try:
        cv.record("starts, hotkeys registered", cv.started(app, lobby), cv.tail(app)[-200:])
        start = cv.press(app, lobby, notepad)
        shown = app.wait(r"Check 1 shown: [^\n]*", 240, lobby, start)
        cv.record("the check shows the lobby with a 嘉宾", bool(shown) and "Liked" in shown.group(0),
                  shown.group(0) if shown else cv.tail(app, start)[-400:])
        playing = app.wait(r"Scene lace: playing via [^\n]*", 30, lobby, start)
        cv.record("the 嘉宾's scene plays", playing is not None,
                  playing.group(0) if playing else cv.tail(app, start)[-600:])
        if playing is None:
            return
        lobby.pump(0.6)
        mid = ImageGrab.grab(all_screens=True)
        mid.save(report / "scene-mid.png")
        width, height = mid.size
        # The lace runs round the edges: a point near the top-left corner of the game is under it.
        spot = (width // 2, lobby.top + 12)
        owner = under(*spot)
        cv.record("click-through: the point under the scene is the lobby's", class_name(owner) != STAGE_CLASS,
                  f"window under {spot}: {class_name(owner)!r}")
        lobby.pump(1.6)
        later = ImageGrab.grab(all_screens=True)
        later.save(report / "scene-2s.png")
        cv.record("the scene is still up 2 s in (no glance or check stopped it)", bool(stage_windows(app.proc.pid)),
                  cv.tail(app, start)[-400:])
        hwnd = bring_main(app, lobby)
        clicks_work(hwnd, lobby, "during the scene", report)
        # The lace lasts about five seconds; the marks stay.
        deadline = time.time() + 20
        while stage_windows(app.proc.pid) and time.time() < deadline:
            lobby.pump(0.5)
        lobby.pump(1.0)
        after = ImageGrab.grab(all_screens=True)
        after.save(report / "scene-after.png")
        cv.record("gone: no stage window after the scene", not stage_windows(app.proc.pid),
                  f"{len(stage_windows(app.proc.pid))} still visible")
        # The main window came forward mid-scene: compare the lobby's left half, away from it.
        half = (0, 0, width // 2, height)
        share = changed_share(mid.crop(half), after.crop(half))
        cv.record("on screen: the desktop mid-scene differs from after it", share > 0.005,
                  f"{share:.1%} of the pixels (玫瑰花边 is a border)")
        notes = re.findall(r"Scene [^\n]*", app.text()[start:])
        print("  log:\n    " + "\n    ".join(notes[-8:]))
        clicks_work(hwnd, lobby, "after the scene", report)
    finally:
        (report / "scene-app.log").write_text(app.text(), encoding="utf-8")
        app.stop()
        notepad.kill()


def main() -> int:
    folder, name, work, report = (Path(arg) for arg in sys.argv[1:5])
    report.mkdir(parents=True, exist_ok=True)
    run(folder / f"{name}.exe" if (folder / f"{name}.exe").exists() else next(folder.glob("*.exe")), work, report)
    failed = [result for result in cv.results if not result[1]]
    print(f"{len(cv.results) - len(failed)} of {len(cv.results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
