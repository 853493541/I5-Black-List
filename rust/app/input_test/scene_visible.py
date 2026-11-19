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
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
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
        self.exe, self.env, self.home = exe, env, home
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
    user32.ShowWindow(hwnd, 1)  # SW_SHOWNORMAL: shows it when hidden to the tray, restores it when minimised
    user32.PostMessageW(hwnd, 0x0112, 0xF120, 0)  # WM_SYSCOMMAND SC_RESTORE, as the taskbar sends it
    lobby.pump(0.8)
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    # The restore posted above lands after a moment: move it once it is in, then again, and take the foreground (this
    # script owns it through the lobby), so the clicks reach the main window and not the lobby on top.
    for _ in range(2):
        user32.SetWindowPos(hwnd, -1, width - 960, height - 640, 0, 0, 0x0001 | 0x0040)  # TOPMOST, NOSIZE | SHOWWINDOW
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        lobby.pump(0.6)
    print(f"  foreground after bring_main: {named(user32.GetForegroundWindow())}; under the header: "
          f"{named(under(width - 960 + 100, height - 640 + 70))}")
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    print(f"  main window: iconic {bool(user32.IsIconic(hwnd))}, visible {bool(user32.IsWindowVisible(hwnd))}, "
          f"at ({rect.left},{rect.top})-({rect.right},{rect.bottom})")
    return hwnd


def z_order(count: int = 8) -> str:
    """The visible top-level windows from the top, by class (the stage over the lobby, or not)."""
    found: list[str] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        if user32.IsWindowVisible(hwnd) and len(found) < count:
            topmost = bool(user32.GetWindowLongW(hwnd, -20) & 0x8)  # GWL_EXSTYLE, WS_EX_TOPMOST
            found.append(f"{class_name(hwnd)}{' (topmost)' if topmost else ''}")
        return True

    user32.EnumWindows(each, 0)
    return " > ".join(found)


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
    # A blind grid can land on empty space only; the header's page tabs always change the page when another is picked.
    tabs, switched = tab_clicks(hwnd, lobby)
    print(f"  INFO grid clicks {when}: {changed} of 9 changed {cv.title(hwnd)!r}: {' '.join(points)}")
    cv.record(f"clicks on the main window work {when}", switched > 0 and answers(hwnd),
              f"{switched} of {len(tabs)} page tab clicks changed the page: {' '.join(tabs)}; "
              f"grid {changed} of 9; answers {answers(hwnd)}; IsHungAppWindow {bool(user32.IsHungAppWindow(hwnd))}")


def tab_clicks(hwnd: int, lobby) -> tuple[list[str], int]:
    """SendInput clicks on the header's page tabs at their layout places (app/ui/shell/main.slint: the header at 24,24,
    36 px high, 记录 first): 记录 at x 44 and a later tab at x 154 (黑名单 or 嘉宾, as the badges make them wide), in
    turn. The preview has no UIA tree, so the places come from the layout. Returns the clicks and how many changed."""
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    scale = (user32.GetDpiForWindow(hwnd) or 96) / 96
    tabs, switched = [], 0
    for name, x in (("later tab", 154), ("记录", 44), ("later tab", 154)):
        sx, sy = origin.x + round(x * scale), origin.y + round(42 * scale)
        target = under(sx, sy)
        before = grab(hwnd)
        click(sx, sy)
        lobby.pump(0.5)
        moved = ImageChops.difference(before.convert("RGB"), grab(hwnd).convert("RGB")).getbbox() is not None
        switched += moved
        mine = target == hwnd or user32.IsChild(hwnd, target)
        tabs.append(f"{name}({sx},{sy}){'*' if moved else ''}{'' if mine else ' over ' + named(target)}")
    return tabs, switched


def key_input(vk: int, up: bool = False):
    return cv.key(vk, up)


def back_by(path: str, app, hwnd: int) -> str:
    """One of the player's ways back to the minimised app."""
    if path == "second launch":
        # The tray's 显示 takes the same way in the app (Do::ShowWindow); a second launch reaches it from outside.
        # It asks the open copy on the pipe and leaves at once (v1.0.1 too); one still running at 10 s is a hang.
        second = subprocess.Popen([str(app.exe)], env=app.env, cwd=str(app.home))
        began = time.monotonic()
        try:
            code = second.wait(10)
        except subprocess.TimeoutExpired:
            second.kill()
            code = "still running at 10 s, killed"
        took = time.monotonic() - began
        cv.record("a second launch leaves within 3 s", took < 3 and code == 0, f"exit {code} after {took:.1f} s")
        return f"launched again (exit {code} after {took:.1f} s)"
    if path == "taskbar button":
        import uiautomation as auto

        title = cv.title(hwnd)
        bar = auto.PaneControl(ClassName="Shell_TrayWnd", searchDepth=1)
        button = bar.ButtonControl(searchDepth=8, Compare=lambda c, d: c.Name.startswith(title[:6]))
        if not button.Exists(5):
            return f"no taskbar button named like {title[:6]!r}"
        x, y = button.GetClickablePoint()[:2]
        click(x, y)
        return f"clicked its taskbar button at ({x},{y})"
    keys = [key_input(0x12), key_input(0x09), key_input(0x09, True), key_input(0x12, True)]  # Alt+Tab
    array = (cv.INPUT * len(keys))(*keys)
    user32.SendInput(len(keys), array, ctypes.sizeof(cv.INPUT))
    return "Alt+Tab"


def ways_back(app, lobby, hwnd: int, report: Path) -> None:
    """Minimised to go back to the game, then back by each way a player takes: restored, on screen, clickable."""
    for path in ("second launch", "taskbar button", "Alt+Tab"):
        user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        lobby.pump(1.0)
        start = len(app.text())
        done = back_by(path, app, hwnd)
        lobby.pump(2.0)
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        back = not user32.IsIconic(hwnd) and user32.IsWindowVisible(hwnd) and rect.left > -10000
        said = re.findall(r"Window: shown[^\n]*", app.text()[start:])
        detail = f"{done}; iconic {bool(user32.IsIconic(hwnd))}, rect ({rect.left},{rect.top}); log {said}"
        if path == "Alt+Tab":
            # Which window Alt+Tab picks depends on the runner's window order: reported, not gating.
            print(f"  INFO back via Alt+Tab: restored {back}; {detail}")
            continue
        cv.record(f"back via {path}: restored on screen", back, detail)
        if path == "second launch":
            front = user32.GetForegroundWindow()
            cv.record("a second launch brings the open window to the front", bool(front) and int(front) == int(hwnd),
                      f"foreground {front} {cv.title(front)!r}, main {hwnd}")
        if back:
            clicks_work(hwnd, lobby, f"after coming back via {path}", report)


def run(exe: Path, work: Path, report: Path) -> None:
    lobby = cv.Lobby()
    notepad = subprocess.Popen(["notepad.exe"])
    app = SceneApp(exe, work / "scene")
    try:
        cv.record("starts, hotkeys registered", cv.started(app, lobby), cv.tail(app)[-200:])
        # The baseline: the same clicks before any check or scene, so "after" is judged against this run's own window.
        hwnd = bring_main(app, lobby)
        clicks_work(hwnd, lobby, "before any check", report)
        user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # NOTOPMOST, NOSIZE | NOMOVE | NOACTIVATE
        user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE: the player goes back to the game
        lobby.pump(0.5)
        # The game is not topmost on a player's PC: the lobby stays in front but under the stage and the marks.
        lobby.tk.attributes("-topmost", False)
        lobby.tk.lift()
        lobby.pump(0.5)
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
        print(f"  z-order mid-scene: {z_order()}")
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
        ways_back(app, lobby, hwnd, report)
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
