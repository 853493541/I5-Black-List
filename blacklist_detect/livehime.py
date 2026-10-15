"""哔哩哔哩直播姬: is 直播模式's window in the stream? Read from 直播姬's own log, nothing else.

直播姬 (v8.2) writes a line to its log (bililive_debug.log) when it starts, on a scene switch and
when a source is added: `game_and_widnow_info : [...]`, the current scene's window and game
captures, bottom to top, each with "process_info" ("title:class:exe", the window it is set to) and
"is_visible". The last one since 直播姬 last started is what its stream shows.

Not every change writes one. Hiding a source with the eye, 置顶 / 置底, and deleting one are seen
at the next scene switch or start, so a warning about those asks for a switch once it is fixed.

The log is never cut and grows by megabytes, so it is read from the end, and after that only
what was added since.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

PROCESS = "livehime.exe"
SCENE = b"game_and_widnow_info :"
START = b"--- Application Startup ---"
# Read back a block at a time, this far at most, for the last scene line.
BLOCK = 256 * 1024
REACH = 16 * 1024 * 1024

# What the status says, for 直播模式's row in 设置.
OK = "ok"  # the current scene shows 直播画面, nothing of the game's over it
MISSING = "missing"  # the current scene has no capture of 直播画面
HIDDEN = "hidden"  # it is there, hidden (the eye in 直播姬's list)
BEHIND = "behind"  # the game's capture is over it, so the marks are under the game
CLOSED = "closed"  # 直播姬 is not running
WORDS = {
    OK: "✓ 已连上直播姬",
    MISSING: "直播姬当前场景里还没有「直播画面」",
    HIDDEN: "「直播画面」被隐藏了，显示后切换一次场景",
    BEHIND: "「直播画面」被游戏挡住了，置顶后切换一次场景",
    CLOSED: "直播姬没有打开",
}


def log_path() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "bililive" / "User Data" / "bililive_debug.log"


@dataclass(frozen=True)
class Capture:
    """One window capture in the scene: the window it is set to, and whether it shows."""

    title: str
    window_class: str
    exe: str
    visible: bool


def _unescape(part: str) -> str:
    # OBS keeps ":" and "#" inside a field as #3A and #22.
    return part.replace("#3A", ":").replace("#22", "#")


def parse_scene(line: str) -> list[Capture] | None:
    """The captures in one game_and_widnow_info line, bottom to top. None when it is not one."""
    marker = SCENE.decode()
    at = line.find(marker)
    if at < 0:
        return None
    try:
        items = json.loads(line[at + len(marker):].strip())
    except ValueError:
        return None
    if not isinstance(items, list):
        return None
    captures = []
    for item in items:
        if not isinstance(item, dict):
            continue
        parts = str(item.get("process_info", "")).split(":")
        title, window_class, exe = ([*map(_unescape, parts), "", ""])[:3]
        captures.append(Capture(title, window_class, exe, item.get("is_visible") is not False))
    return captures


class SceneWatch:
    """The current scene as 直播姬 last logged it, kept up to date by reading only what was added
    to the log since the last look. None: no log, or nothing logged since 直播姬 last started."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._size = -1
        self._scene: list[Capture] | None = None

    def scene(self) -> list[Capture] | None:
        path = self.path or log_path()
        try:
            size = path.stat().st_size
            if size == self._size:
                return self._scene
            with open(path, "rb") as log:
                if self._size < 0 or size < self._size:
                    self._scene, self._size = _from_end(log, size)
                else:
                    self._read_on(log, size)
        except OSError:
            self._size, self._scene = -1, None
        return self._scene

    def _read_on(self, log, size: int) -> None:  # noqa: ANN001
        log.seek(self._size)
        data = log.read(size - self._size)
        whole = data.rfind(b"\n") + 1  # a line still being written waits for the next look
        for line in data[:whole].split(b"\n"):
            if START in line:
                self._scene = None
            elif SCENE in line:
                self._scene = parse_scene(line.decode("utf-8", "replace"))
        self._size += whole


def _from_end(log, size: int) -> tuple[list[Capture] | None, int]:  # noqa: ANN001
    """The last scene line, looking back from the end; and where the whole lines end."""
    log.seek(max(0, size - BLOCK))
    last = log.read()
    end = size - len(last) + last.rfind(b"\n") + 1
    pos, carry = end, b""
    while pos > 0 and end - pos < REACH:
        start = max(0, pos - BLOCK)
        log.seek(start)
        lines = (log.read(pos - start) + carry).split(b"\n")
        carry = lines.pop(0) if start > 0 else b""
        for line in reversed(lines):
            if START in line:
                return None, end
            if SCENE in line:
                return parse_scene(line.decode("utf-8", "replace")), end
        pos = start
    return None, end


def status(title: str, running: bool, scene: list[Capture] | None, covers: Callable[[Capture], bool] | None = None) -> str:
    """OK, MISSING, HIDDEN, BEHIND or CLOSED for the window titled title; "" when not known yet.
    covers says whether a capture is of the game's window; without it, the order is not judged."""
    if not running:
        return CLOSED
    if scene is None:
        return ""
    ours = [index for index, capture in enumerate(scene) if capture.title == title]
    if not ours:
        return MISSING
    shown = [index for index in ours if scene[index].visible]
    if not shown:
        return HIDDEN
    above = scene[max(shown) + 1:]
    if covers is not None and any(capture.visible and capture.title != title and covers(capture) for capture in above):
        return BEHIND
    return OK


def window_over(capture: Capture, point: tuple[int, int]) -> bool:
    """Whether the window a capture is set to is shown at this desktop point (the game's button)."""
    if sys.platform != "win32" or not capture.title:
        return False
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    hwnd = user32.FindWindowW(capture.window_class or None, capture.title)
    if not hwnd or not user32.IsWindowVisible(hwnd):
        return False
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left <= point[0] < rect.right and rect.top <= point[1] < rect.bottom


def game_capture(scene: list[Capture] | None, title: str) -> Capture | None:
    """The capture the stream shows the game with: the top visible window capture under the one of
    直播画面 (titled title), or the top visible one when the scene has no 直播画面."""
    if not scene:
        return None
    ours = [index for index, capture in enumerate(scene) if capture.title == title]
    under = scene[: min(ours)] if ours else scene
    for capture in reversed(under):
        if capture.visible and capture.title and capture.title != title:
            return capture
    return None


def window_of(capture: Capture) -> int:
    """The window a capture is set to, or 0 when it is not open."""
    if sys.platform != "win32" or not capture.title:
        return 0
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    return int(user32.FindWindowW(capture.window_class or None, capture.title) or 0)


def client_rect(capture: Capture) -> tuple[int, int, int, int] | None:
    """(left, top, right, bottom) in desktop pixels of the window a capture is set to, its client
    area as 直播姬 captures it; None when it is not open, hidden or minimized."""
    hwnd = window_of(capture)
    if not hwnd:
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return None
    client = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(client))
    corner = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(corner))
    if client.right <= 0 or client.bottom <= 0:
        return None
    return corner.x, corner.y, corner.x + client.right, corner.y + client.bottom
