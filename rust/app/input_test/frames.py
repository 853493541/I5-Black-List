"""The windows' frames on the built preview (Windows only): v1.0.1's dialogs are ui_kit.Modal, frameless and laid over
the main window's client area; the Rust ones must be the same, with no native title bar or border around the card.

    python -I rust/app/input_test/frames.py <exe> <home> <out>

Starts the exe as drive.py does (a data folder of its own), checks 使用声明 at the first start and 显示说明 from the
header panel: no WS_CAPTION, no WS_THICKFRAME, no WS_BORDER, and the window's rectangle on the main window's client
area. Each window is saved as a PNG in <out>; the main window's own style is recorded for comparison with v1.0.1.
Exit code: the number of failed checks.
"""

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drive  # noqa: E402
from drive import App, center, click, own_windows, record, user32, window_info  # noqa: E402
from PIL import ImageGrab  # noqa: E402

WS_CAPTION, WS_THICKFRAME, WS_BORDER = 0x00C00000, 0x00040000, 0x00800000
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    record(name, ok, detail)
    if not ok:
        FAILED.append(name)


def client_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect, corner = wintypes.RECT(), wintypes.POINT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    user32.ClientToScreen(hwnd, ctypes.byref(corner))
    return corner.x, corner.y, corner.x + rect.right, corner.y + rect.bottom


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def shoot(hwnd: int, out: Path, name: str) -> None:
    left, top, right, bottom = window_rect(hwnd)
    if right > left and bottom > top:
        ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True).save(out / f"{name}.png")


def frameless_over_main(app: App, hwnd: int, name: str) -> None:
    style = user32.GetWindowLongPtrW(hwnd, -16) & 0xFFFFFFFF
    native = [flag for bit, flag in ((WS_CAPTION, "WS_CAPTION"), (WS_THICKFRAME, "WS_THICKFRAME"), (WS_BORDER, "WS_BORDER"))
              if style & bit == bit]
    check(f"{name}: no native frame", not native, f"{', '.join(native) or 'none'}; {window_info(hwnd)}")
    main, own = client_rect(app.hwnd), window_rect(hwnd)
    off = max(abs(a - b) for a, b in zip(main, own))
    check(f"{name}: lies over the main window's client area", off <= 2, f"main client {main}, dialog {own}")
    shoot(hwnd, app.out, name)


def new_window(app: App, before: set[int], wait: float = 5.0) -> int:
    end = time.time() + wait
    while time.time() < end:
        new = [h for h in own_windows(app.proc.pid) if h not in before and h != app.hwnd]
        if new:
            time.sleep(0.5)  # placed and drawn
            return new[0]
        time.sleep(0.3)
    return 0


def main() -> int:
    exe, home, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    home.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    app = App(exe, home, out)
    try:
        if not app.find_main():
            check("main window shows", False, "not found within 60 s")
            return len(FAILED)
        time.sleep(3)
        record("main window style (v1.0.1's main window has a native frame)", True, window_info(app.hwnd))
        shoot(app.hwnd, out, "main")
        others = [h for h in own_windows(app.proc.pid) if h != app.hwnd]
        disclaimer = next((h for h in others if "使用声明" in drive.window_info(h)), others[0] if others else 0)
        check("使用声明 opens at the first start", bool(disclaimer), f"other windows: {[window_info(h) for h in others]}")
        if disclaimer:
            frameless_over_main(app, disclaimer, "使用声明")
        drive.agree(app)
        user32.SetForegroundWindow(app.hwnd)
        time.sleep(0.5)
        app.front()
        app.open_panel()
        button = app.main.ButtonControl(Name="显示说明", searchDepth=30)
        if button.Exists(3, 0.5):
            before = set(own_windows(app.proc.pid))
            click(*center(button))
            dialog = new_window(app, before)
            check("显示说明 opens", bool(dialog), "no new window within 5 s")
            if dialog:
                frameless_over_main(app, dialog, "显示说明")
                user32.PostMessageW(dialog, 0x0010, 0, 0)
        else:
            check("显示说明 button", False, "UIAutomation does not see it")
    finally:
        app.proc.kill()
    return len(FAILED)


if __name__ == "__main__":
    sys.exit(main())
