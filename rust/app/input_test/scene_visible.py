r"""A hotkey check that finds a 嘉宾 plays the 嘉宾's scene over the game (P0-2), and leaves nothing behind (P0-3).

    python -I scene_visible.py <preview folder> <exe name> <work folder> <report folder>

On a Windows runner at 1920x1080, as check_visible.py: the sample lobby (made-up names 示例坏人, 心动小鹿, 心动星星)
full-screen, Notepad in front, Alt+1 by SendInput. likes.json is seeded with 心动小鹿 on 玫瑰花边 (lace), 我 on 不放.
Asserted:
  plays       the log says the scene plays ("Scene lace: playing via ...") after "Check 1 shown"
  on screen   a copy of the desktop mid-scene differs from the copy after it, over the game (the scene's pixels)
  lasts       no glance or check stops it early: still on screen 2 s in (the glance runs every 0.4 s)
  click-through  the point under the scene belongs to the lobby window, not the stage's
  gone        after the scene: no visible BlacklistDetectStage window, and the desktop is back to the marks alone
  main window a SendInput click on the app's main window, restored, brings it to the front
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
STAGE_CLASS = "BlacklistDetectStage"


class SceneApp(cv.App):
    """check_visible's App with likes.json seeded before the start: 心动小鹿 on lace, 我 on 不放."""

    def __init__(self, exe: Path, home: Path) -> None:
        import os
        import shutil

        shutil.rmtree(home, ignore_errors=True)
        self.data = home / cv.FOLDER
        self.data.mkdir(parents=True)
        settings = {"disclaimer_accepted": True, "consented": ["full"], "safe_mode": False, "auto_capture": True,
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
    best, area = 0, 0
    for hwnd in cv.windows_of(pid):
        if class_name(hwnd) == STAGE_CLASS:
            continue
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        size = (rect.right - rect.left) * (rect.bottom - rect.top)
        if size > area:
            best, area = hwnd, size
    return best


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
        # The lace lasts about five seconds; the marks stay.
        deadline = time.time() + 20
        while stage_windows(app.proc.pid) and time.time() < deadline:
            lobby.pump(0.5)
        lobby.pump(1.0)
        after = ImageGrab.grab(all_screens=True)
        after.save(report / "scene-after.png")
        cv.record("gone: no stage window after the scene", not stage_windows(app.proc.pid),
                  f"{len(stage_windows(app.proc.pid))} still visible")
        share = changed_share(mid, after)
        cv.record("on screen: the desktop mid-scene differs from after it", share > 0.02, f"{share:.1%} of the pixels")
        notes = re.findall(r"Scene [^\n]*", app.text()[start:])
        print("  log:\n    " + "\n    ".join(notes[-8:]))
        hwnd = main_window(app.proc.pid)
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        lobby.pump(1.0)
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        click((rect.left + rect.right) // 2, rect.top + 12)
        lobby.pump(1.0)
        front = user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(front, ctypes.byref(pid))
        cv.record("a click on the main window works afterwards", pid.value == app.proc.pid,
                  f"foreground: {cv.title(front)!r} (pid {pid.value}, app {app.proc.pid})")
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
