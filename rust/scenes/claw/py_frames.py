"""The Python 演说家遇袭 (claw.py) frames the Rust port is compared with: 1920x1080 over the sample lobby,
the marks on their own, and the glyph outlines the Rust port fills (??? and the notes).

Run from the root of a checkout: PYTHONPATH=. python rust/scenes/claw/py_frames.py
Writes rust/scenes/claw/py_t<t>.png, py_marks.png and rust/scenes/src/claw/glyphs.rs, and prints the
median frame time at 1920x1080 (scene only, no marks). The glyphs are the faces Qt finds for
"Microsoft YaHei" (bold) and "Segoe UI Symbol"; run it on Windows to bake the faces the app shows.
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="claw-frames-")
os.environ["HOME"] = os.environ["APPDATA"]

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontInfo, QImage, QPainter, QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

W, H = 1920, 1080
OUT = Path("rust/scenes/claw")
TIMES = [0.5, 1.5, 3.0, 3.1, 3.4, 4.0, 5.3]
# The marks' boxes in py_marks.png (and in the Rust bin): ring cover, badge box, card rect.
RING = (40.0, 40.0, 300.0, 80.0)
BADGE = (380.0, 50.0, 60.0, 60.0)
CARD = (40.0, 150.0, 260.0, 140.0)
MARKS_T = 2.0


def contours(path: QPainterPath) -> list[list[tuple[float, float]]]:
    return [[(p.x(), p.y()) for p in poly] for poly in path.toSubpathPolygons()]


def rust_shape(name: str, polys: list[list[tuple[float, float]]]) -> str:
    rows = ",\n".join("    &[" + ", ".join(f"[{x:.3f}, {y:.3f}]" for x, y in poly) + "]" for poly in polys)
    return f"pub const {name}: &[&[[f32; 2]]] = &[\n{rows},\n];\n"


def glyphs() -> None:
    """The outlines at 100 pixels: ? in the names' face (bold) and its advance, the four notes."""
    bold = QFont("Microsoft YaHei")
    bold.setPixelSize(100)
    bold.setWeight(QFont.Weight.Bold)
    one, two = QPainterPath(), QPainterPath()
    one.addText(QPointF(0, 0), bold, "?")
    two.addText(QPointF(0, 0), bold, "??")
    advance = two.boundingRect().right() - one.boundingRect().right()
    symbol = QFont("Segoe UI Symbol")
    symbol.setPixelSize(100)
    text = [
        "//! Glyph outlines at 100 pixels, baked by rust/scenes/claw/py_frames.py from the faces Qt found",
        f"//! (names: {QFontInfo(bold).family()} bold, notes: {QFontInfo(symbol).family()}). Generated: do not edit.",
        "",
        f"pub const QUESTION_ADVANCE: f32 = {advance:.4f};",
        rust_shape("QUESTION", contours(one)),
    ]
    for i, glyph in enumerate("♪♫♩♬"):
        path = QPainterPath()
        path.addText(QPointF(0, 0), symbol, glyph)
        text.append(rust_shape(f"NOTE_{i}", contours(path)))
    text.append("pub const NOTES: [&[&[[f32; 2]]]; 4] = [NOTE_0, NOTE_1, NOTE_2, NOTE_3];\n")
    Path("rust/scenes/src/claw/glyphs.rs").write_text("\n".join(text), encoding="utf-8")


def marks(claw) -> None:  # noqa: ANN001
    image = QImage(480, 320, QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor("#30343c"))
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    for draw, box in ((claw.ring, RING), (claw.badge, BADGE), (claw.card, CARD)):
        p.save()
        draw(p, QRectF(*box), MARKS_T)
        p.restore()
    for i in range(2):
        p.drawPixmap(QPointF(330 + 40 * i, 200), claw.lead(24.0, i))
    p.end()
    image.save(str(OUT / "py_marks.png"))


def main() -> None:
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from blacklist_detect.love_scenes import claw, sample_stage

    glyphs()
    marks(claw)
    paint = claw.make(sample_stage(W, H))
    lobby = QImage("rust/scenes/spike/lobby_1920.png").convertToFormat(QImage.Format_ARGB32_Premultiplied)
    for t in [float(x) for x in sys.argv[1:]] or TIMES:
        image = QImage(lobby)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        paint(painter, t)
        painter.end()
        image.save(str(OUT / f"py_t{t:.1f}.png"))
    spent, t = [], 0.0
    frame = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    while t <= claw.DURATION:
        frame.fill(Qt.transparent)
        start = time.perf_counter()
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.Antialiasing)
        paint(painter, t)
        painter.end()
        spent.append((time.perf_counter() - start) * 1000)
        t += 1 / 30
    print(f"python claw: median {statistics.median(spent):.1f} ms, worst {max(spent):.1f} ms at {W}x{H}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
