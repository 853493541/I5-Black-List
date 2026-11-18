"""Golden data for the Rust tray (rust/win/src/tray): the Python tray menu, read offscreen.

Writes rust/win/tests/golden/tray.json: per app state (close to tray on / off, light / dark), the menu items in
order (text, enabled, checkable, checked, separator, what each one does), the tooltip, which click on the icon
brings the window back, what the window's X does, and the sha1 of the icon file. Run from the checkout root:

    APPDATA=<temp> HOME=<temp> QT_QPA_PLATFORM=offscreen PYTHONPATH=. python tools/rust_golden_tray.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "rust" / "win" / "tests" / "golden" / "tray.json"


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if "APPDATA" not in os.environ or Path(os.environ["APPDATA"]).resolve() == Path.home():
        os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tray-golden-")
    sys.path.insert(0, str(ROOT))
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    from blacklist_detect import ui

    app = QApplication.instance() or QApplication([])
    # Offscreen Qt has no tray; the menu is built the same either way.
    ui.QSystemTrayIcon_available = lambda: True
    calls: list[str] = []
    ui.MainWindow._show_from_tray = lambda self: calls.append("show")
    real_close = ui.MainWindow.close
    ui.MainWindow.close = lambda self: calls.append("close") or True

    states = []
    for close_to_tray in (True, False):
        for appearance in ("light", "dark"):
            window = ui.MainWindow()
            window._watch_timer.stop()
            window.store.close_to_tray = close_to_tray
            window.store.appearance = appearance
            window._restyle()
            items = []
            for action in window.tray_menu.actions():
                calls.clear()
                if not action.isSeparator():
                    action.trigger()
                items.append({
                    "text": action.text(),
                    "enabled": action.isEnabled(),
                    "checkable": action.isCheckable(),
                    "checked": action.isChecked(),
                    "separator": action.isSeparator(),
                    "does": list(calls),
                })
            clicks = {}
            for reason in QSystemTrayIcon.ActivationReason:
                calls.clear()
                window._on_tray(reason)
                clicks[reason.name] = list(calls)
            # The X on the window, while the tray icon shows: spontaneous() is True for a click by the player.
            window.tray.isVisible = lambda: True
            event = QCloseEvent()
            event.spontaneous = lambda: True
            window.isVisible()
            ui.MainWindow.closeEvent(window, event)
            x_button = "hide" if not event.isAccepted() else "quit"
            states.append({
                "close_to_tray": close_to_tray,
                "appearance": appearance,
                "tooltip": window.tray.toolTip(),
                "items": items,
                "clicks": clicks,
                "x_button": x_button,
            })
            ui.MainWindow.close = real_close
            window.tray.hide()
            window.close()
            ui.MainWindow.close = lambda self: calls.append("close") or True
    ui.MainWindow.close = real_close
    icon = ROOT / "blacklist_detect" / "assets" / "app.ico"
    data = {"icon_sha1": hashlib.sha1(icon.read_bytes()).hexdigest(), "states": states}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(states)} states")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
