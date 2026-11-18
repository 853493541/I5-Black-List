"""Writes golden.json beside this file from the Python app itself, for the notices' parity tests.

Run from the checkout's root, with a data folder of its own and no display:
    QT_QPA_PLATFORM=offscreen APPDATA=<tmp> HOME=<tmp> PYTHONPATH=. python rust/app/src/notices/golden.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication

app = QApplication([])

from blacklist_detect import __version__, ui_alert, ui_notice, ui_update, updater  # noqa: E402

out: dict = {"version": __version__}

# The words of the corner cards.
cases = [
    ([], [], 0),
    ([], [], 2),
    ([("示例坏人", ("炸房", "挂机", "骂人", "第四个"))], [], 1),
    ([(f"示例坏人{i}", ()) for i in range(5)], ["心动小鹿"], 0),
    ([(f"示例坏人{i}", ("炸房",)) for i in range(7)], [f"心动星星{i}" for i in range(6)], 3),
    ([], ["心动小鹿", "心动星星"], 0),
]
out["messages"] = [
    {
        "hits": [[name, list(tags)] for name, tags in hits],
        "likes": likes,
        "unclear": unclear,
        "out": [
            {"kind": m.kind, "title": m.title, "note": m.note, "people": [[n, list(t)] for n, t in m.people], "more": m.more}
            for m in ui_notice.result_messages(hits, likes, unclear)
        ],
    }
    for hits, likes, unclear in cases
]
out["timings"] = {name: getattr(ui_notice, name) for name in ("NOTICE_MS", "CHECKING_MS", "_MARGIN", "_GAP", "_RISE", "_RISE_MS", "_NEXT_MS", "_TICK_MS")}
out["timings"]["RESTART_MS"] = ui_update.UpdateDialog.RESTART_MS

# Where the cards stand: the Python app's own sizes and places on the offscreen screen.
notice = ui_notice.CornerNotice()
screen = app.primaryScreen()
area = screen.availableGeometry()
placed = []
for hits, likes, unclear in cases[2:]:
    notice.show_result(hits, likes, unclear, screen)
    end = time.monotonic() + 0.6
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    cards = [c for c in notice.cards() if c.isVisible()]
    placed.append({
        "natural": [c.natural_width() for c in cards],
        "heights": [c.height() for c in cards],
        "width": cards[0].width(),
        "spots": [[c.x(), c.y()] for c in cards],
    })
    notice.hide()
out["area"] = [area.x(), area.y(), area.width(), area.height()]
out["placed"] = placed


# The update dialog, state by state.
def dialog_state(d: ui_update.UpdateDialog) -> dict:
    return {
        "title": d.heading.text(),
        "summary": d.summary.text(),
        "notes": d.notes.text() if d.notes.isVisibleTo(d) else "",
        "status": d.status.text() if d.status.isVisibleTo(d) else "",
        "bar": d.bar.value() if d.bar.isVisibleTo(d) else None,
        "close": d.close_button.isVisibleTo(d),
        "band": d.band.isVisibleTo(d),
        "skip": d.skip.isVisibleTo(d),
        "action": d.action.text(),
        "state": d._state,
    }


def release(**kw) -> updater.Release:
    base = {"version": "v9.9.9", "url": "", "sha256": "", "size": 12_345_678, "base": "v0.0.1", "notes": ("花边铺满整个游戏", "卡片跟着游戏大小", "检查更快")}
    base.update(kw)
    return updater.Release(**base)


updates = {}
root = Path(__file__).resolve().parent
with mock.patch.object(ui_update.Download, "start", lambda *a: None), mock.patch.object(updater, "staged_version", lambda _root: None):
    d = ui_update.UpdateDialog(release(), root, root)
    updates["idle"] = dialog_state(d)
    d.start()
    updates["downloading"] = dialog_state(d)
    d._on_progress(1, 3)
    updates["progress_1_3"] = dialog_state(d)
    d._on_progress(5, 1000)
    updates["progress_5_1000"] = dialog_state(d)
    d._on_failed("下载失败，等会儿再试")
    updates["failed"] = dialog_state(d)
    d._on_done("v9.9.9")
    updates["restarting"] = dialog_state(d)
    updates["full"] = dialog_state(ui_update.UpdateDialog(release(base="v99.0.0"), root, root))
    updates["source"] = dialog_state(ui_update.UpdateDialog(release(), None, root))
    updates["tiny"] = dialog_state(ui_update.UpdateDialog(release(size=10, notes=()), root, root))
out["updates"] = updates

# The glow's rings, read off a painter that only listens.
rings = {}
for w, h in ((1920, 1080), (300, 200), (2560, 1440)):
    seen = []

    class Listen:
        def setBrush(self, *_a): ...  # noqa: N802

        def setPen(self, pen):  # noqa: N802
            seen.append([pen.widthF(), pen.color().alpha()])

        def drawRect(self, rect):  # noqa: N802
            seen[-1].append(rect.x())

    ui_alert.paint_glow(Listen(), w, h)
    rings[f"{w}x{h}"] = seen
out["rings"] = rings

(Path(__file__).resolve().parent / "golden.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("golden.json written")
