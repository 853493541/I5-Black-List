"""Where the game is drawn on screen, so the flower border and the red glow can fit it.

The game may fill the screen, or sit in a window: a windowed client, or an emulator such as
MuMu with its own title bar and side bar. This asks Windows one thing: the rectangle of the
window under the lobby's button, the innermost one that draws there, the app's own marks left
out. It never opens the game's process, reads what it draws or holds, or sends it anything;
it is the same window-position question a screen recorder asks. Windows only.

A check takes a moment, and by its end something else may be in front of the button (the
streaming app, a popup, another window). So the order of the windows is noted with the
screenshot (window_order), and the window under the button is found in that order.
"""

from __future__ import annotations

import os
import sys

_GW_HWNDNEXT = 2
_WS_EX_TRANSPARENT = 0x20
_WS_EX_LAYERED = 0x80000
_GWL_EXSTYLE = -20
_CWP_SKIPINVISIBLE = 0x1
_CWP_SKIPTRANSPARENT = 0x4
_DWMWA_CLOAKED = 14


def window_order() -> tuple[int, ...]:
    """The top-level windows, front to back, as they are now: noted with each screenshot."""
    if sys.platform != "win32":
        return ()
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetTopWindow.restype = wintypes.HWND
    user32.GetTopWindow.argtypes = (wintypes.HWND,)
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    order = []
    hwnd = user32.GetTopWindow(None)
    while hwnd and len(order) < 4096:
        order.append(int(hwnd))
        hwnd = user32.GetWindow(hwnd, _GW_HWNDNEXT)
    return tuple(order)


def window_rect_at(
    x: int, y: int, order: tuple[int, ...] = (), innermost: bool = True
) -> tuple[int, int, int, int] | None:
    """(left, top, right, bottom) in screen pixels of what draws at (x, y): the client area of
    the innermost window there, this app's windows passed over. order: the windows front to back
    when the screenshot was taken (window_order); without it, as they are now. innermost=False
    stops at the top-level window: the whole emulator, what a streaming app's 窗口捕捉 captures.
    None when nothing is found."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetTopWindow.restype = wintypes.HWND
    user32.GetTopWindow.argtypes = (wintypes.HWND,)
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsIconic.argtypes = (wintypes.HWND,)
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
    user32.ScreenToClient.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.ChildWindowFromPointEx.restype = wintypes.HWND
    user32.ChildWindowFromPointEx.argtypes = (wintypes.HWND, wintypes.POINT, wintypes.UINT)
    own = os.getpid()

    def cloaked(hwnd) -> bool:  # noqa: ANN001
        value = ctypes.c_int(0)
        try:
            ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, _DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value))
        except (AttributeError, OSError):
            return False
        return bool(value.value)

    def takes(hwnd) -> bool:  # noqa: ANN001
        """Shown, not this app's, not a see-through window clicks pass through, and over the point."""
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd) or cloaked(hwnd):
            return False
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == own:
            return False
        style = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        if style & _WS_EX_TRANSPARENT and style & _WS_EX_LAYERED:
            return False
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return rect.left <= x < rect.right and rect.top <= y < rect.bottom

    user32.IsWindow.argtypes = (wintypes.HWND,)
    if order:
        # Front to back as at the screenshot; a window closed since is passed over.
        hwnd = next((wintypes.HWND(h) for h in order if user32.IsWindow(wintypes.HWND(h)) and takes(wintypes.HWND(h))), None)
    else:
        hwnd = user32.GetTopWindow(None)
        while hwnd and not takes(hwnd):
            hwnd = user32.GetWindow(hwnd, _GW_HWNDNEXT)
    if not hwnd:
        return None
    # Down to the innermost window that draws there: an emulator's game surface, not its frame.
    for _ in range(16 if innermost else 0):
        point = wintypes.POINT(x, y)
        user32.ScreenToClient(hwnd, ctypes.byref(point))
        child = user32.ChildWindowFromPointEx(hwnd, point, _CWP_SKIPINVISIBLE | _CWP_SKIPTRANSPARENT)
        if not child or child == hwnd:
            break
        hwnd = child
    client = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(client))
    corner = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(corner))
    left, top = corner.x, corner.y
    right, bottom = left + client.right, top + client.bottom
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


# How far a window's top and bottom may be from where the lobby puts the game screen, in the
# game's height, for the window to be the game's own: an emulator's game surface or a full-screen
# game. A program showing a picture of the lobby (照片, 媒体播放器, 资源管理器) is bigger, by its
# toolbars and the bars round the picture. The lobby's own estimate is good to about 2%.
FIT = 0.04


def game_rect(window, estimate):  # noqa: ANN001, ANN201
    """The game's screen, in desktop pixels: the window under the lobby when it fits the lobby,
    else where the lobby puts it, inside that window. Either may be None."""
    if estimate is None:
        return window
    left, top, right, bottom = estimate
    height = bottom - top
    if height <= 0:
        return window
    if window is None:
        return tuple(int(round(value)) for value in estimate)
    w_left, w_top, w_right, w_bottom = window
    if (
        abs(w_top - top) <= FIT * height
        and abs(w_bottom - bottom) <= FIT * height
        and w_right - w_left <= right - left + 2 * FIT * height
    ):
        return window
    inside = (max(w_left, left), max(w_top, top), min(w_right, right), min(w_bottom, bottom))
    if inside[2] - inside[0] < height / 2 or inside[3] - inside[1] < height / 2:
        # The window is not around the lobby at all: keep what was found.
        return window
    return tuple(int(round(value)) for value in inside)


_QUNS_RUNNING_D3D_FULL_SCREEN = 3


def exclusive_fullscreen() -> bool:
    """Whether a Direct3D program holds the screen in exclusive full screen, as Windows tells it.

    Windows draws no other window over such a game: the marks over it would not be seen. A game
    in borderless 全屏 (the usual kind now) is not this, and shows them. Asks Windows only."""
    if sys.platform != "win32":
        return False
    import ctypes

    state = ctypes.c_int(0)
    try:
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
            return False
    except (AttributeError, OSError):
        return False
    return state.value == _QUNS_RUNNING_D3D_FULL_SCREEN
