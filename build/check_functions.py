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
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

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
    from blacklist_detect.hotkey import parse_hotkey
    from blacklist_detect.pipeline import check_image, load_rgb
    from blacklist_detect.storage import Store
    from blacklist_detect.ui_overlay import RED

    app.setFont(ui.chinese_font())
    ui._apply_theme(app)

    # 1. A first open: 使用声明 is asked and agreed to, as a player does (a check is refused until it is), the
    #    environment check runs with the real OCR, then the guide shows once.
    asked: list[int] = []
    ui.DisclaimerDialog.open = lambda self: (asked.append(1), self.accept())
    guides: list[int] = []
    ui.GuideDialog.open = lambda self: guides.append(1)
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
    check("使用声明 is asked once and agreed to", asked == [1] and Store(window.store.root).disclaimer_accepted)
    # 完整模式, as a player picks it after its risk is told: the red ring and the card below are drawn over the game
    # only there (基础模式, the default, shows the result in a corner box).
    window.store.consented = ["full"]
    window._on_display_mode("full")
    check("完整模式 is on", not window.store.safe_mode)

    # 2. The reader on the reference lobby, with someone from it on the list: a picture read the way a
    #    live check reads the screen (用截图检查 is gone from the app).
    window.store.add("gffdsd", "测试", tags=("炸房",))
    window._show_list()
    result = check_image(LOBBY, list(window.store.entries))
    seats = [slot.raw for slot in result.names]
    check("the reader finds twelve seats in the reference lobby", len(seats) == 12, "、".join(seats))
    found = [hit.entry_name for hit in result.hits]
    check("the listed player is found", found == ["gffdsd"], "、".join(found))

    # 3. A live lobby check, with the reference shot standing in for the screen.
    frame = load_rgb(LOBBY)
    ui.capture_displays = lambda: [frame]
    window._watch_timer.stop()
    scans_before = len(window.store.scans)
    window.check_now()
    wait_until(lambda: len(window.store.scans) > scans_before and window.panel.mode == "hit", 120)
    check("a live check records the lobby", len(window.store.scans) == scans_before + 1)
    check("the red ring covers 准备案件还原", window.panel.isVisible() and window.panel.mode == "hit" and window.panel.ring() == RED)
    names = [label.text() for label in window.hit_card.findChildren(QLabel, "hitName")]
    check("the hit card shows beside it", window.hit_card.isVisible() and names == ["gffdsd"], ", ".join(names))
    check("both stay above the game", topmost(window.panel) and topmost(window.hit_card))
    check("the record is marked with its hit", window._scan_hit_counts().get(0, 0) == 1)
    window._panel_hide_timer.stop()
    window.panel.hide()
    window.hit_card.hide()

    # 4. 手动检查 with the global hotkey: one of its own, since the copy the player has open holds Alt+1.
    pressed: list[int] = []
    window.store.hotkey = "Ctrl+Alt+F9"
    window._toggle_auto(False)
    window.hotkey.callback = lambda: pressed.append(1)
    key = parse_hotkey(window.store.hotkey).display
    check(f"手动检查 registers {key} with Windows", window.hotkey.active == key and window.hotkey._registered, window.hotkey.error)
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
