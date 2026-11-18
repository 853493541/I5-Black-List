"""The Python frames the Rust port of one scene is compared with: 1920x1080 over the sample lobby.

Run from the root of a checkout: PYTHONPATH=. python rust/scenes/<scene>/py_frames.py [t ...]
Writes rust/scenes/<scene>/py_t<t>.png and lobby_1920.png, and prints the median frame time at
1920x1080 (scene only). For classic it also writes title_mask.png and title.txt: the words 心动嘉宾 as
Qt sets them (the one thing the Rust scene takes from a text engine instead of drawing itself).
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="scene-frames-")
os.environ["HOME"] = os.environ["APPDATA"]

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont, QFontMetricsF, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

W, H = 1920, 1080
OUT = Path(__file__).resolve().parent
SCENE = OUT.name
TIMES = {"lace": [0.5, 1.5, 3.0, 4.2], "classic": [0.5, 1.5, 2.0, 3.0, 4.0]}


def title_mask(classic, u: float) -> None:  # noqa: ANN001
    """The words mask _title_art paints, and the font's height, for the Rust title."""
    import numpy as np

    masks = []
    real = classic.mask
    classic.mask = lambda w, h, draw: masks.append(real(w, h, draw)) or masks[-1]
    classic._title_art(u)
    classic.mask = real
    words = masks[0]
    QImage(np.ascontiguousarray((words * 255 + 0.5).astype(np.uint8)).data, words.shape[1], words.shape[0], words.shape[1],
           QImage.Format_Grayscale8).copy().save(str(OUT / "title_mask.png"))
    font = QFont(classic._title_face())
    font.setPixelSize(max(8, round(classic.TITLE_PX * u * 2)))
    font.setWeight(QFont.Bold)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 7 * u * 2)
    (OUT / "title.txt").write_text(f"{QFontMetricsF(font).height()!r}\n")


def main() -> None:
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from blacklist_detect import love_scenes

    module = love_scenes.load(SCENE)
    stage = love_scenes.sample_stage(W, H)
    if SCENE == "classic":
        title_mask(module, stage.unit())
    lobby = QImage("blacklist_detect/assets/sample-lobby.jpg").scaled(W, H, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    lobby = lobby.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    lobby.save(str(OUT / "lobby_1920.png"))
    for t in [float(x) for x in sys.argv[1:]] or TIMES[SCENE]:
        paint = module.make(stage)
        image = QImage(lobby)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        paint(painter, t)
        painter.end()
        image.save(str(OUT / f"py_t{t:.1f}.png"))
    paint = module.make(stage)
    spent, t = [], 0.0
    frame = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    while t <= module.DURATION:
        frame.fill(Qt.transparent)
        start = time.perf_counter()
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.Antialiasing)
        paint(painter, t)
        painter.end()
        spent.append((time.perf_counter() - start) * 1000)
        t += 1 / 30
    print(f"python {SCENE}: median {statistics.median(spent):.1f} ms, worst {max(spent):.1f} ms at {W}x{H}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
