"""Run inside a staged release, with its own Python, before it is zipped.

Builds the window and dialogs on the real Windows platform, reads the reference
lobby, and reports every module and DLL that was loaded. make_release.py checks
the report. Nothing here writes to the user's real settings folder.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    fixture, report = sys.argv[1], sys.argv[2]
    from blacklist_detect.ocr_engine import silence_console_children

    silence_console_children()
    from PySide6.QtWidgets import QApplication

    from blacklist_detect import ui

    app = QApplication([])
    app.setFont(ui.chinese_font())
    app.setWindowIcon(ui._icon())
    ui._apply_theme(app)
    window = ui.MainWindow()
    for index in range(window.tabs.count()):
        window.tabs.setCurrentIndex(index)
        window.grab()
    ui.AddNameDialog(catalog=window.store.tag_catalog(), parent=window).grab()
    ui.BatchAddDialog(window.store.tag_catalog(), parent=window).grab()
    window.panel.set_mode("clear", "没有黑名单")
    window.panel.grab()
    window.hit_card.set_people([("名字", ("炸房",))], 60)
    window.hit_card.grab()
    key = ui.instance_key() + "-verify"
    server = ui.listen_for_instances(key, lambda: None)
    single_instance = ui.notify_running_instance(key)
    server.close()

    from blacklist_detect.capture import capture_top_band
    from blacklist_detect.model import Entry
    from blacklist_detect.pipeline import check_image, glance_title, load_rgb

    result = check_image(fixture, [Entry("gffdsd")])
    sample = check_image(ui.SAMPLE_LOBBY, [])
    rgb = load_rgb(fixture)
    glanced = glance_title(rgb[: int(rgb.shape[0] * 0.4)])
    capture_top_band()

    import psutil

    payload = {
        "platform": app.platformName(),
        "style": app.style().name(),
        "icon": not app.windowIcon().isNull(),
        "header": result.header_found,
        "names": [(slot.visible, slot.truncated) for slot in result.names],
        "sample_names": [(slot.visible, slot.truncated) for slot in sample.names],
        "hits": [hit.entry_name for hit in result.hits],
        "glance": glanced,
        "single_instance": single_instance,
        "modules": sorted({getattr(m, "__file__", None) or "" for m in list(sys.modules.values())} - {""}),
        "dlls": sorted({item.path for item in psutil.Process().memory_maps()}),
    }
    with open(report, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
    window.hide()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
