"""Writes stream.json: what the Python app says and computes for 直播模式, for the Rust side to match.

Run from the checkout's root with APPDATA/HOME at a data folder of its own and QT_QPA_PLATFORM=offscreen:
    python rust/app/src/stream/golden/make.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from PySide6.QtCore import QPoint, QRect  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect import livehime, ui_stream  # noqa: E402
from blacklist_detect.ui import _said_first  # noqa: E402
from blacklist_detect.ui_widgets import masked_name  # noqa: E402

app = QApplication.instance() or QApplication([])
title = ui_stream.TITLE
cap = livehime.Capture
scenes = {
    "closed": (False, None),
    "unknown": (True, None),
    "missing": (True, [cap("原神", "", "", True)]),
    "hidden": (True, [cap(title, "", "", False)]),
    "behind": (True, [cap(title, "", "", True), cap("游戏", "", "", True)]),
    "ok": (True, [cap("游戏", "", "", True), cap(title, "", "", True)]),
}
status = {}
for case, (running, scene) in scenes.items():
    state = livehime.status(title, running, scene, lambda capture: capture.title == "游戏")
    words = livehime.WORDS.get(state, "")
    status[case] = {"state": state, "words": words, "row": _said_first(words), "tone": "ok" if state == livehime.OK else "warn"}


class _Window:
    class panel:  # noqa: N801
        @staticmethod
        def isVisible() -> bool:  # noqa: N802
            return False


fits = []
mirror = ui_stream.StreamMirror(_Window())
for size, area in [((1920, 1080), (0, 0, 1920, 1080)), ((1920, 1080), (100, 50, 1280, 720)),
                   ((2560, 1440), (0, 0, 1600, 1200)), ((1366, 768), (10, 20, 800, 600)), ((1920, 1080), (0, 0, 0, 0))]:
    mirror.resize(*size)
    mirror._area = QRect(*area)
    scale, offset = mirror._fit()
    point = mirror.to_window(QPoint(area[0] + 40, area[1] + 30))
    fits.append({"window": size, "area": area, "scale": scale, "offset": [offset.x(), offset.y()],
                 "point": [point.x(), point.y()]})
screen = app.primaryScreen().geometry()
places = []
for spot in ui_stream.SPOTS:
    mirror.spot = spot
    mirror._place(QRect(10, 10, 300, 200))
    g = mirror.geometry()
    places.append({"spot": spot, "rect": [g.x(), g.y(), g.width(), g.height()]})
names = ["示例坏人", "心动小鹿", "a", "", "心动星星呀呀", "Ab"]
out = {
    "title": title, "frame_ms": ui_stream.FRAME_MS, "ask_ms": ui_stream.ASK_MS, "follow_ms": ui_stream.FOLLOW_MS,
    "spots": list(ui_stream.SPOTS), "words": livehime.WORDS, "status": status,
    "masked": {name: masked_name(name) for name in names},
    "fits": fits,
    "screen": [screen.x(), screen.y(), screen.width(), screen.height()], "places": places,
}
Path(__file__).with_name("stream.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("wrote stream.json")
