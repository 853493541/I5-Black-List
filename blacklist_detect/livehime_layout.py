"""Where 直播姬 puts each window capture on its canvas, and whether the game and 直播画面 line up there.

For the log: a stream whose marks miss the game says where each side lands and by how much.

直播姬 is built on OBS. Its scene collection (%LOCALAPPDATA%\\bililive\\User Data\\<account>\\Scene
Collection\\*.json) keeps every scene's sources with where each sits: OBS's pos, scale, crop and bounds,
and for a 窗口捕获 the window it is set to and whether it takes only the client area. 直播姬 writes it
as things change. Its log (livehime.log_path) says the canvas size, whether 横竖双屏 is on, when the
two-canvas mode (预览 and 直播 apart) turns on or off, when 同步至直播 is pressed, and when a source is
added to or removed from a scene. In the two-canvas mode viewers see what was last synced: a source
changed after that is only in the streamer's preview.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

# OBS's alignment bits (align, bounds_align); neither left nor right is the middle, and so on.
LEFT, RIGHT, TOP, BOTTOM = 1, 2, 4, 8
# OBS's bounds types.
NO_BOUNDS, STRETCH, INNER, OUTER, TO_WIDTH, TO_HEIGHT, MAX_ONLY = range(7)
# How far back the log is read for the canvas and the two-canvas mode.
REACH = 8 * 1024 * 1024


@dataclass(frozen=True)
class Placement:
    """One 窗口捕获 in one scene: the window it is set to, how it captures, and where it sits."""

    scene: str
    name: str
    title: str
    window_class: str
    exe: str
    client_area: bool
    whole_screen: bool  # 窗口区域模式: the screen where the window is, not the window
    visible: bool
    pos: tuple[float, float]
    scale: tuple[float, float]
    crop: tuple[int, int, int, int]  # left, top, right, bottom
    bounds_type: int
    bounds: tuple[float, float]
    bounds_align: int
    align: int
    rotation: float

    def on_canvas(self, width: float, height: float) -> tuple[float, float, float, float]:
        """(x, y, w, h) on the canvas of a captured frame width by height pixels, as OBS draws it."""
        left, top, right, bottom = self.crop
        w, h = max(1.0, width - left - right), max(1.0, height - top - bottom)
        if self.bounds_type == NO_BOUNDS:
            sw, sh = w * self.scale[0], h * self.scale[1]
            return _anchor(self.pos[0], sw, self.align), _anchor(self.pos[1], sh, self.align >> 2), sw, sh
        bx, by = self.bounds
        fits = {
            STRETCH: (bx / w, by / h),
            INNER: (min(bx / w, by / h),) * 2,
            OUTER: (max(bx / w, by / h),) * 2,
            TO_WIDTH: (bx / w,) * 2,
            TO_HEIGHT: (by / h,) * 2,
            MAX_ONLY: (min(1.0, bx / w, by / h),) * 2,
        }
        kx, ky = fits.get(self.bounds_type, (1.0, 1.0))
        sw, sh = w * kx, h * ky
        box_x, box_y = _anchor(self.pos[0], bx, self.align), _anchor(self.pos[1], by, self.align >> 2)
        return box_x + _inside(bx - sw, self.bounds_align), box_y + _inside(by - sh, self.bounds_align >> 2), sw, sh


def _anchor(at: float, size: float, bits: int) -> float:
    """Where a span starts, given the point it is aligned by (bits: LEFT and RIGHT, shifted for TOP
    and BOTTOM)."""
    if bits & LEFT:
        return at
    if bits & RIGHT:
        return at - size
    return at - size / 2


def _inside(room: float, bits: int) -> float:
    if bits & LEFT:
        return 0.0
    if bits & RIGHT:
        return room
    return room / 2


def collection_path(root: Path | None = None) -> Path | None:
    """The scene collection 直播姬 last wrote: the newest one of any account."""
    base = root or Path(os.environ.get("LOCALAPPDATA", "")) / "bililive" / "User Data"
    found = [path for path in base.glob("*/Scene Collection/*.json") if path.is_file()]
    return max(found, key=lambda path: path.stat().st_mtime) if found else None


def _unescape(part: str) -> str:
    return part.replace("#3A", ":").replace("#22", "#")


def placements(path: Path) -> tuple[str, list[Placement]]:
    """The scene 直播姬 shows, and every 窗口捕获 in every scene, each scene's bottom to top."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = [source for source in data.get("sources", []) if isinstance(source, dict)]
    by_uuid = {source.get("uuid"): source for source in sources}
    by_name = {source.get("name"): source for source in sources}
    out: list[Placement] = []
    for scene in sources:
        if scene.get("id") != "scene":
            continue
        for item in (scene.get("settings") or {}).get("items", []):
            source = by_uuid.get(item.get("source_uuid")) or by_name.get(item.get("name")) or {}
            if source.get("id") != "window_capture":
                continue
            settings = source.get("settings") or {}
            title, window_class, exe = [*map(_unescape, str(settings.get("window", "")).split(":")), "", ""][:3]
            pos, scale, bounds = item.get("pos") or {}, item.get("scale") or {}, item.get("bounds") or {}
            out.append(
                Placement(
                    scene=str(scene.get("name", "")),
                    name=str(item.get("name", "")),
                    title=title,
                    window_class=window_class,
                    exe=exe,
                    client_area=settings.get("client_area") is not False,
                    whole_screen=settings.get("capture_from_whole_screen") is True,
                    visible=item.get("visible") is not False,
                    pos=(float(pos.get("x", 0)), float(pos.get("y", 0))),
                    scale=(float(scale.get("x", 1)), float(scale.get("y", 1))),
                    crop=tuple(int(item.get(f"crop_{side}", 0) or 0) for side in ("left", "top", "right", "bottom")),
                    bounds_type=int(item.get("bounds_type", 0) or 0),
                    bounds=(float(bounds.get("x", 0)), float(bounds.get("y", 0))),
                    bounds_align=int(item.get("bounds_align", 0) or 0),
                    align=int(item.get("align", LEFT | TOP) or 0),
                    rotation=float(item.get("rot", 0) or 0),
                )
            )
    return str(data.get("current_scene", "")), out


@dataclass
class Studio:
    """What 直播姬's log says of its canvas and its two-canvas mode; None where it says nothing."""

    canvas: tuple[int, int] | None = None
    double_screen: bool | None = None
    two_canvas: bool | None = None
    # When 同步至直播 was last pressed, and a source last added to or removed from a scene, as
    # "MMDD HHMMSS"; "" when not seen.
    synced: str = ""
    edited: str = ""

    def unsynced(self) -> bool:
        """In the two-canvas mode, a source changed since 同步至直播: viewers do not see it yet."""
        return bool(self.two_canvas and self.edited and self.edited > self.synced)


# 直播姬 8.2: [17476:1014/002232.668:INFO:...]; 7.64: [tid:...:2026-10-14/14-39-08:...]
_STAMP_82 = re.compile(r"^\[\d+:(\d{4})/(\d{6})")
_STAMP_764 = re.compile(r"\d{4}-(\d{2})-(\d{2})/(\d{2})-(\d{2})-(\d{2})")
_CANVAS = re.compile(r"is_double_screen-(\d) main_width-(\d+) main_height-(\d+)")
_PROGRAM = re.compile(r"BililiveOBSView::OnLiveProgramModeChanged : (\d)")
_EDIT = re.compile(r"scene '.*' (?:add|remove) item : ")


def _stamp(line: str) -> str:
    found = _STAMP_82.match(line)
    if found:
        return f"{found.group(1)} {found.group(2)}"
    found = _STAMP_764.search(line[:80])
    if found:
        month, day, hour, minute, second = found.groups()
        return f"{month}{day} {hour}{minute}{second}"
    return ""


def _read(found: Studio, text: str) -> Studio:
    """found, brought up to date with these log lines; a new start of 直播姬 begins afresh."""
    for line in text.splitlines():
        if "--- Application Startup ---" in line:
            found = Studio()
            continue
        canvas = _CANVAS.search(line)
        if canvas:
            found.double_screen = canvas.group(1) == "1"
            found.canvas = (int(canvas.group(2)), int(canvas.group(3)))
        program = _PROGRAM.search(line)
        if program:
            found.two_canvas = program.group(1) == "1"
        if "[ProgramMode] ButtonPressed OpenProgramView" in line:
            found.synced = _stamp(line) or found.synced
        elif _EDIT.search(line):
            found.edited = _stamp(line) or found.edited
    return found


def studio(path: Path, reach: int = REACH) -> Studio:
    """The canvas and the two-canvas mode, from the end of 直播姬's log, back to its last start."""
    return StudioWatch(path, reach).studio()


class StudioWatch:
    """studio(), kept up to date by reading only what 直播姬 added to its log since the last look."""

    def __init__(self, path: Path | None = None, reach: int = REACH) -> None:
        self.path = path
        self.reach = reach
        self._size = -1
        self._found = Studio()

    def studio(self) -> Studio:
        from blacklist_detect import livehime

        path = self.path or livehime.log_path()
        try:
            size = path.stat().st_size
            if size != self._size:
                with open(path, "rb") as log:
                    if self._size < 0 or size < self._size:
                        self._found, start = Studio(), max(0, size - self.reach)
                    else:
                        start = self._size
                    log.seek(start)
                    data = log.read(size - start)
                # A line still being written waits for the next look.
                whole = data.rfind(b"\n") + 1
                self._found = _read(self._found, data[:whole].decode("utf-8", "replace"))
                self._size = start + whole
        except OSError:
            self._size, self._found = -1, Studio()
        return self._found


def captured_rect(placement: Placement) -> tuple[int, int, int, int] | None:
    """(left, top, right, bottom) in desktop pixels of what a 窗口捕获 takes of its window: the client
    area, or the window as the desktop draws it (without its invisible resize border). None when the
    window is not open."""
    from blacklist_detect import livehime

    capture = livehime.Capture(placement.title, placement.window_class, placement.exe, placement.visible)
    if placement.client_area:
        return livehime.client_rect(capture)
    hwnd = livehime.window_of(capture)
    return window_rect(hwnd) if hwnd else None


def window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """A window's bounds in desktop pixels as the desktop draws it; None where there is no such window."""
    import sys

    if sys.platform != "win32" or not hwnd:
        return None
    import ctypes
    from ctypes import wintypes

    rect = wintypes.RECT()
    if ctypes.WinDLL("dwmapi").DwmGetWindowAttribute(wintypes.HWND(hwnd), 9, ctypes.byref(rect), ctypes.sizeof(rect)) != 0:
        if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None
    if rect.right <= rect.left or rect.bottom <= rect.top:
        return None
    return rect.left, rect.top, rect.right, rect.bottom
