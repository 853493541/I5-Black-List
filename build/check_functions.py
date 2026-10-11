"""Check the app's functions on the real Windows desktop, end to end, before a release.

    python build/check_functions.py

The unit tests run without a screen. This drives a real window instead: real OCR, the
overlay over a lobby, the global hotkey, the tray, a second launch, the input method,
and the data on disk. The reference lobby screenshot stands in for the game.

It uses a throwaway settings folder and its own instance name, so a copy of the app
that is open, with its list, records and settings, is not touched. Each check prints
PASS or FAIL; the exit code is 1 when any failed.
"""

from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="blacklist-check-")
os.environ.setdefault("QT_QPA_PLATFORM", "windows")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

LOBBY = REPO / "tests" / "fixtures" / "reference-lobby.png"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""), flush=True)
    return bool(ok)


def pump(seconds: float = 0.2) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def wait_until(predicate, seconds: float) -> bool:  # noqa: ANN001
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return bool(predicate())


user32 = ctypes.windll.user32
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
imm32 = ctypes.windll.imm32
imm32.ImmGetContext.restype = ctypes.c_void_p
imm32.ImmGetContext.argtypes = (wintypes.HWND,)
imm32.ImmReleaseContext.argtypes = (wintypes.HWND, ctypes.c_void_p)


def in_front(widget) -> bool:  # noqa: ANN001
    front = user32.GetForegroundWindow()
    return bool(front) and int(front) == int(widget.winId())


def topmost(widget) -> bool:  # noqa: ANN001
    return bool(user32.GetWindowLongW(int(widget.winId()), -20) & 0x00000008)  # GWL_EXSTYLE, WS_EX_TOPMOST


def main() -> int:
    app = QApplication(sys.argv)
    from blacklist_detect import __version__, ui
    from blacklist_detect.pipeline import load_rgb
    from blacklist_detect.storage import Store
    from blacklist_detect.ui_overlay import RED

    app.setFont(ui.chinese_font())
    ui._apply_theme(app)

    # 1. A first open: the environment check runs with the real OCR, then the guide shows once.
    guides: list[int] = []
    ui.GuideDialog.exec = lambda self: guides.append(1) or QDialog.Accepted
    started = time.monotonic()
    window = ui.MainWindow()
    window.show()
    window.start_warmup()
    window.begin()
    check("first open starts the environment check", window.setup is not None and window.setup.state == "running")
    done = wait_until(lambda: window.setup.state in ("ok", "failed"), 180)
    notes = [note.text() for note in window.setup.notes]
    check(
        "environment check passes with the real OCR",
        done and window.setup.state == "ok",
        f"{window.setup.state} in {time.monotonic() - started:.1f} s, sample {notes[-1] or '-'}",
    )
    wait_until(lambda: bool(guides), 10)
    check("the welcome guide shows once, after it", guides == [1] and not window.store.first_run)
    check("the check is remembered for this version", Store(window.store.root).env_checked == __version__)

    # 2. 截图检查 on the reference lobby, with someone from it on the list.
    window.store.add("gffdsd", "测试", tags=("炸房",))
    window._show_list()
    window._run_picture(str(LOBBY), "截图检查")
    wait_until(lambda: window._picture_dialog is not None and window._picture_dialog.isVisible(), 120)
    dialog = window._picture_dialog
    seats = [seat.text() for seat in dialog.seats] if dialog is not None else []
    check("截图检查 reads twelve seats", len(seats) == 12, "、".join(seats))
    check("截图检查 marks the listed player", dialog is not None and "1 人在黑名单里" in dialog.summary.text(), dialog.summary.text() if dialog else "")
    if dialog is not None:
        dialog.close()

    # 3. A live lobby check, with the reference shot standing in for the screen.
    frame = load_rgb(LOBBY)
    ui.capture_displays = lambda: [frame]
    window._watch_timer.stop()
    scans_before = len(window.store.scans)
    window.check_now()
    wait_until(lambda: len(window.store.scans) > scans_before and window.panel.mode == "hit", 120)
    check("a live check records the lobby", len(window.store.scans) == scans_before + 1)
    check("the red ring covers 准备案件还原", window.panel.isVisible() and window.panel.mode == "hit" and window.panel.ring() == RED)
    check("the hit card shows beside it", window.hit_card.isVisible() and "1 人在黑名单里" == window.hit_card.title.text())
    check("both stay above the game", topmost(window.panel) and topmost(window.hit_card))
    check("the record is marked with its hit", window._scan_hit_counts().get(0, 0) == 1)
    window._panel_hide_timer.stop()
    window.panel.hide()
    window.hit_card.hide()

    # 4. 手动检查 with the global hotkey.
    pressed: list[int] = []
    window._toggle_auto(False)
    window.hotkey.callback = lambda: pressed.append(1)
    check("手动检查 registers Alt+1 with Windows", window.hotkey.active == "Alt+1" and window.hotkey._registered, window.hotkey.error)
    user32.PostThreadMessageW(ctypes.windll.kernel32.GetCurrentThreadId(), 0x0312, window.hotkey._id, 0)
    wait_until(lambda: bool(pressed), 5)
    check("pressing it starts a check", pressed == [1])
    window._toggle_auto(True)
    check("自动检查 lets the hotkey go again", window.hotkey.active == "" and not window.hotkey._registered)
    window._watch_timer.stop()

    # 5. 中文 input stays switchable where nothing takes text.
    window._show_from_tray()
    window.tabs.setCurrentIndex(window.history_tab)
    window.history_list.setFocus(Qt.MouseFocusReason)
    pump(0.3)
    hwnd = wintypes.HWND(int(window.winId()))
    context = imm32.ImmGetContext(hwnd)
    if context:
        imm32.ImmReleaseContext(hwnd, context)
    check("the input method stays on over the record list", bool(context))

    # 6. 关闭到托盘: × hides to the tray; a second launch brings the window back, in front.
    window.store.close_to_tray = True
    key = f"blacklist-detect-check-{os.getpid()}"
    window.instance_server = ui.listen_for_instances(key, window._show_from_tray, window.quit_app)
    user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE, as the title bar's ×
    wait_until(lambda: not window.isVisible(), 5)
    check("× hides the window to the tray", not window.isVisible() and not window._closing and window.tray is not None and window.tray.isVisible())
    ui.notify_running_instance(key, show=True)
    wait_until(lambda: window.isVisible() and in_front(window), 5)
    check("a second launch brings it back in front", window.isVisible() and in_front(window))

    # 7. What was set is on disk for the next start.
    window._set_theme("绿色")
    window._set_appearance("dark")
    window.player_edit.setText("阿强")
    window._save_player_name()
    again = Store(window.store.root)
    check(
        "the list, records and settings are on disk",
        [entry.name for entry in again.entries] == ["gffdsd"]
        and len(again.scans) == len(window.store.scans)
        and (again.theme, again.appearance, again.player_name) == ("绿色", "dark", "阿强"),
    )

    # 8. 退出: everything closes, the hotkey and the tray go, and the instance name is free.
    window.quit_app()
    pump(0.5)
    check("退出 closes everything", window._closing and not window.isVisible() and not window.panel.isVisible() and (window.tray is None or not window.tray.isVisible()))
    check("a new copy could start after it", not ui.notify_running_instance(key, show=False))

    failed = [name for name, ok, _detail in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} passed" + (f"; failed: {', '.join(failed)}" if failed else ""), flush=True)
    sys.stdout.flush()
    os._exit(1 if failed else 0)


if __name__ == "__main__":
    main()
