"""The Python 竖琴清风 (lyre.py) frames the Rust port is compared with: 1920x1080 over the sample lobby.

Run from the root of a checkout: PYTHONPATH=. python rust/scenes/lyre/py_frames.py
Writes rust/scenes/lyre/py_t<t>.png and prints the median frame time at 1920x1080 (scene only, no marks).
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["APPDATA"] = os.environ["HOME"] = tempfile.mkdtemp(prefix="lyre-frames-")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

W, H = 1920, 1080
OUT = Path("rust/scenes/lyre")


def main() -> None:
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from blacklist_detect.love_scenes import lyre, sample_stage

    paint = lyre.make(sample_stage(W, H))
    lobby = QImage("blacklist_detect/assets/sample-lobby.jpg").scaled(W, H, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    lobby = lobby.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    for t in [float(x) for x in sys.argv[1:]] or [0.5, 1.5, 3.0, 4.0, 4.7]:
        image = QImage(lobby)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        paint(painter, t)
        painter.end()
        image.save(str(OUT / f"py_t{t:.1f}.png"))
    spent, t = [], 0.0
    frame = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    while t <= lyre.DURATION:
        frame.fill(Qt.transparent)
        start = time.perf_counter()
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.Antialiasing)
        paint(painter, t)
        painter.end()
        spent.append((time.perf_counter() - start) * 1000)
        t += 1 / 30
    print(f"python lyre: median {statistics.median(spent):.1f} ms, worst {max(spent):.1f} ms at {W}x{H}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
