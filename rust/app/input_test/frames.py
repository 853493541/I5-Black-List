"""The windows' frames on the built preview (Windows only): v1.0.1's dialogs are ui_kit.Modal, frameless and laid over
the main window's client area; the Rust ones must be the same, with no native title bar or border around the card.

    python -I rust/app/input_test/frames.py <exe> <home> <out>

Starts the exe as drive.py does (a data folder of its own), checks 使用声明 at the first start and 显示说明 from the
header panel: no non-client area (client rectangle = window rectangle), and the window's rectangle on the main window's client
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
    # winit keeps WS_CAPTION on an undecorated window (Aero snap) and drops the frame in WM_NCCALCSIZE
    # (winit 0.30 platform_impl/windows/window_state.rs adjust_rect), so the style bits do not tell: a frameless
    # window has no non-client area, its client rectangle is its whole window rectangle.
    client, own = client_rect(hwnd), window_rect(hwnd)
    off = max(abs(a - b) for a, b in zip(client, own, strict=True))
    check(f"{name}: no native frame", off == 0, f"client {client}, window {own}; {window_info(hwnd)}")
    main = client_rect(app.hwnd)
    off = max(abs(a - b) for a, b in zip(main, own, strict=True))
    check(f"{name}: lies over the main window's client area", off <= 2, f"main client {main}, dialog {own}")
    shoot(hwnd, app.out, name)


def buttons_in_view(hwnd: int, name: str, labels: list[str]) -> None:
    """The dialog's buttons lie inside its window and on the screen (CLAUDE.md: buttons in view at 672 px)."""
    control = drive.auto.ControlFromHandle(hwnd)
    left, top, right, bottom = window_rect(hwnd)
    screen = (0, 0, user32.GetSystemMetrics(78) or 1 << 15, user32.GetSystemMetrics(79) or 1 << 15)
    for label in labels:
        button = control.ButtonControl(Name=label, searchDepth=30)
        if not button.Exists(3, 0.5):
            check(f"{name}: {label} seen", False, "UIAutomation does not see it")
            continue
        r = button.BoundingRectangle
        inside = left <= r.left and r.right <= right and top <= r.top and r.bottom <= bottom
        on_screen = r.bottom <= screen[3] and r.right <= screen[2] and r.top >= 0 and r.left >= 0
        check(f"{name}: {label} in view", inside and on_screen,
              f"button ({r.left},{r.top},{r.right},{r.bottom}), window ({left},{top},{right},{bottom}), screen {screen[2:]}")


def on_screen(hwnd: int, name: str) -> None:
    """The whole dialog window is on the screen, so the buttons inside it are too (no UIAutomation needed)."""
    left, top, right, bottom = window_rect(hwnd)
    width, height = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    ok = left >= 0 and top >= 0 and right <= width and bottom <= height
    check(f"{name}: the whole window is on the screen", ok, f"window ({left},{top},{right},{bottom}), screen {width}x{height}")


def new_window(app: App, before: set[int], wait: float = 5.0) -> int:
    end = time.time() + wait
    while time.time() < end:
        new = [h for h in own_windows(app.proc.pid) if h not in before and h != app.hwnd]
        if new:
            time.sleep(0.8)  # placed and drawn
            return new[0]
        time.sleep(0.3)
    return 0


def open_by_button(app: App, label: str, name: str, buttons: list[str]) -> None:
    """Clicks `label` in the main window; the window it opens must be frameless over the main window."""
    button = app.main.ButtonControl(Name=label, searchDepth=30)
    if not button.Exists(3, 0.5):
        check(f"{name}: {label} button", False, "UIAutomation does not see it")
        return
    before = set(own_windows(app.proc.pid))
    click(*center(button))
    dialog = new_window(app, before)
    check(f"{name} opens", bool(dialog), "no new window within 5 s")
    if dialog:
        frameless_over_main(app, dialog, name)
        buttons_in_view(dialog, name, buttons)
        user32.PostMessageW(dialog, 0x0010, 0, 0)
        time.sleep(0.8)


def agree(app: App, dialog: int) -> None:
    """同意并继续 on the 使用声明 at the first start (drive.agree waited 1 s; the laid-over window needs longer)."""
    button = drive.auto.ControlFromHandle(dialog).ButtonControl(Name="同意并继续", searchDepth=30)
    if not button.Exists(8, 0.5):
        names = [c.Name for c, _d in drive.auto.WalkControl(drive.auto.ControlFromHandle(dialog), maxDepth=30) if c.Name][:30]
        check("使用声明: 同意并继续 seen", False, f"names under the window: {names}")
        return
    user32.SetForegroundWindow(dialog)
    time.sleep(0.4)
    click(*center(button))
    end, agreed = time.time() + 5, None
    while time.time() < end and agreed is not True:
        agreed = app.settings().get("disclaimer_accepted")
        time.sleep(0.3)
    check("使用声明: 同意并继续 is saved", agreed is True, f"disclaimer_accepted={agreed!r}")


def main() -> int:
    exe, home, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    # --record-only: an older build for comparison; its frames are written down, not checked.
    record_only = "--record-only" in sys.argv[4:]
    home.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    app = App(exe, home, out)
    try:
        if not app.find_main():
            check("main window shows", False, "not found within 60 s")
            return 0 if record_only else len(FAILED)
        time.sleep(3)
        record("main window style (v1.0.1's main window has a native frame)", True, window_info(app.hwnd))
        shoot(app.hwnd, out, "main")
        # The player's build has no accessibility (the `a11y` feature, rust/app/Cargo.toml): UIAutomation sees no
        # controls in it, so without a11y only what window handles tell is checked (frame, place, on screen).
        # The window's own title and the native title bar's buttons show without a11y too: look for the 嘉宾 tab.
        a11y = any(c.Name == "嘉宾" for c, _d in drive.auto.WalkControl(app.main, maxDepth=30))
        record("UIAutomation sees the controls (an a11y build)", True, str(a11y))
        others = [h for h in own_windows(app.proc.pid) if h != app.hwnd and "使用声明" in window_info(h)]
        check("使用声明 opens at the first start", bool(others), f"windows: {[window_info(h) for h in own_windows(app.proc.pid)]}")
        if others:
            frameless_over_main(app, others[0], "使用声明")
            on_screen(others[0], "使用声明")
            if not a11y:
                record("显示说明, 添加嘉宾, 场景管理", True, "skipped: opening them needs an a11y build (rust-input.yml builds one)")
                return 0 if record_only else len(FAILED)
            buttons_in_view(others[0], "使用声明", ["同意并继续", "不同意"])
            agree(app, others[0])
        user32.SetForegroundWindow(app.hwnd)
        time.sleep(0.5)
        app.front()
        if app.open_panel():
            open_by_button(app, "显示说明", "显示说明", ["知道了"])
        else:
            check("显示说明: 检查 panel opens", False, "the panel under the 检查 pill did not open")
        if drive.open_tab(app, "嘉宾"):
            open_by_button(app, "添加嘉宾", "添加嘉宾", [])
            open_by_button(app, "场景管理", "场景管理", [])
        else:
            check("嘉宾 tab", False, "could not open it")
        # 设置 is a page of the main window (tab 设置), not a window of its own: nothing to check there.
    finally:
        app.proc.kill()
    return 0 if record_only else len(FAILED)


if __name__ == "__main__":
    sys.exit(main())
