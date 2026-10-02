"""Copy the desktop once. Windows only.

One BitBlt of the whole virtual screen. No second capture, no capture
window, and no display-mode change. Borderless and windowed games are in
that copy. This module never looks up a game window, never reads process
memory, and never sends a click or a key.
"""

from __future__ import annotations

import sys

import numpy as np

_SRCCOPY = 0x00CC0020
_BI_RGB = 0
_DIB_RGB_COLORS = 0
_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79


class CaptureUnavailable(RuntimeError):
    """The desktop copy cannot run on this machine."""


def capture_capability_message() -> str:
    if sys.platform != "win32":
        return "这台电脑不能直接检查游戏画面。请用「选择图片」。"
    return ""


# The match-found title sits in the upper part of this lobby. The watch copies
# only that band; the full check still copies the whole desktop.
TITLE_BAND_FRACTION = 0.40


def capture_displays() -> list:
    """Return one RGB uint8 frame of the whole desktop. Raises CaptureUnavailable."""
    if sys.platform != "win32":
        raise CaptureUnavailable(capture_capability_message())
    frame = _grab_screen()
    if frame is None or frame.size == 0:
        raise CaptureUnavailable("没有读到画面，请再试一次。")
    return [frame]


def capture_top_band(fraction: float = TITLE_BAND_FRACTION) -> np.ndarray:
    """Copy the top of the desktop. Raises CaptureUnavailable."""
    if sys.platform != "win32":
        raise CaptureUnavailable(capture_capability_message())
    frame = _grab_screen(height_fraction=fraction)
    if frame is None or frame.size == 0:
        raise CaptureUnavailable("没有读到画面，请再试一次。")
    return frame


def _grab_screen(height_fraction: float = 1.0) -> np.ndarray | None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    left = int(user32.GetSystemMetrics(_SM_XVIRTUALSCREEN))
    top = int(user32.GetSystemMetrics(_SM_YVIRTUALSCREEN))
    width = int(user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN))
    full_height = int(user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN))
    if width <= 0 or full_height <= 0:
        return None
    fraction = min(1.0, max(0.05, float(height_fraction)))
    height = max(1, int(round(full_height * fraction)))
    height = min(height, full_height)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", ctypes.c_long),
            ("biHeight", ctypes.c_long),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", ctypes.c_long),
            ("biYPelsPerMeter", ctypes.c_long),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = width
    info.bmiHeader.biHeight = -height
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = _BI_RGB

    screen = user32.GetDC(0)
    if not screen:
        return None
    memory = gdi32.CreateCompatibleDC(screen)
    bits = ctypes.c_void_p()
    bitmap = gdi32.CreateDIBSection(
        screen,
        ctypes.byref(info),
        _DIB_RGB_COLORS,
        ctypes.byref(bits),
        None,
        0,
    )
    if not memory or not bitmap or not bits:
        if bitmap:
            gdi32.DeleteObject(bitmap)
        if memory:
            gdi32.DeleteDC(memory)
        user32.ReleaseDC(0, screen)
        return None
    selected = gdi32.SelectObject(memory, bitmap)
    ok = gdi32.BitBlt(memory, 0, 0, width, height, screen, left, top, _SRCCOPY)
    rgb = None
    if ok:
        raw = np.ctypeslib.as_array(
            ctypes.cast(bits, ctypes.POINTER(ctypes.c_uint8)),
            shape=(height, width, 4),
        )
        rgb = np.empty((height, width, 3), dtype=np.uint8)
        rgb[:, :, 0] = raw[:, :, 2]
        rgb[:, :, 1] = raw[:, :, 1]
        rgb[:, :, 2] = raw[:, :, 0]
    gdi32.SelectObject(memory, selected)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory)
    user32.ReleaseDC(0, screen)
    return rgb


def lock_foreground(locked: bool) -> None:
    """Stop the hotkey from pulling a window to the front."""
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.user32.LockSetForegroundWindow(1 if locked else 2)
