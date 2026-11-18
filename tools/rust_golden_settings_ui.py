"""Golden data for the Rust 设置 (rust/app/src/settings): every section, row, wording, control and default as the
Python widgets have them, and the first-run 环境测试 card's steps.

Runs offscreen in a data folder of its own (APPDATA and XDG_CONFIG_HOME pointed at a temp folder, never the player's),
with sound left off. Writes rust/app/src/settings/golden.json, or the path given:

    QT_QPA_PLATFORM=offscreen python tools/rust_golden_settings_ui.py [out.json]
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "rust" / "app" / "src" / "settings" / "golden.json"


def _control(widget) -> dict:  # noqa: ANN001
    from PySide6.QtWidgets import QPushButton

    from blacklist_detect.ui_kit import ChoiceBox

    if isinstance(widget, ChoiceBox):
        labels = [widget.itemText(i) for i in range(widget.count())]
        return {"kind": "choice", "choices": labels, "keys": widget.keys(), "value": widget.currentText()}
    if isinstance(widget, QPushButton):
        return {"kind": "danger" if widget.objectName() == "danger" else "button", "label": widget.text()}
    return {"kind": "note"}


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    data = Path(tempfile.mkdtemp(prefix="golden_settings_ui_"))
    os.environ.update({"APPDATA": str(data), "XDG_CONFIG_HOME": str(data), "HOME": str(data)})
    os.environ.pop("BLACKLIST_DETECT_SOUND", None)
    sys.path.insert(0, str(ROOT))
    from PySide6.QtWidgets import QApplication

    from blacklist_detect import ui, ui_setup

    app = QApplication.instance() or QApplication([])
    window = ui.MainWindow()
    sections = []
    for key, pane in window.settings_sections.items():
        rows = []
        for row in pane.rows:
            controls = [_control(c) for c in row.controls]
            rows.append({"name": row.name.text(), "description": row.description_text(), "controls": controls})
        sections.append({"key": key, "title": pane.heading.text(), "rows": rows})
    card = ui_setup.SetupCheck(window)
    card.start()
    running = card.title.text()
    steps = [label.text() for label in card.card.findChildren(ui.QLabel) if label.text() in ui_setup.STEPS]
    card.succeed(fade=False)
    ok = card.title.text()
    card.fail(0, "示例")
    failed = card.title.text()
    buttons = [card.close_button.text(), card.retry_button.text()]
    golden = {
        "sections": sections,
        "setup": {"steps": steps, "running": running, "ok": ok, "failed": failed, "buttons": buttons},
    }
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    out.write_text(json.dumps(golden, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out)
    window.close()
    app.quit()


if __name__ == "__main__":
    main()
