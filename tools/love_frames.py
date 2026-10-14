"""Render a 心动 scene over the sample lobby at full size, with its 心动 marks, and time its frames at 1920x1080.

Run from the root of a checkout:
    PYTHONPATH=. python tools/love_frames.py <key> <out_dir> [t1 t2 ...]
    PYTHONPATH=. python tools/love_frames.py <key> <out_dir> anim
The second writes <out_dir>/<key>.webp instead: the whole scene playing at 20 fps, 960 px wide, in full
color (an animated WebP: a GIF's 256 colors band the glows and it is four times the size).
Writes <out_dir>/<key>_t<t>.png (1635x848 lobby with the scene and the button gap outlined faintly),
and prints the median and worst frame time at 1920x1080 over the whole scene (30 fps), then the time
one paint of each mark takes there.
Both draw the marks as the app shows them by the sample lobby's button, from MARKS_AT on: the ring on
the button, the badge right of it and the card with 心动小鹿 and 心动星星 left of it, in the scene's look
or drawn by the scene itself (see love_scenes), moving if it makes them move.
The scene is loaded from blacklist_detect/love_scenes/<key>.py; it need not be in SCENES yet.
"""

from __future__ import annotations

import importlib
import os
import statistics
import sys
import time
from pathlib import Path

# Windows' own fonts (the offscreen platform has none); only pictures are drawn, no window opens.
os.environ.setdefault("QT_QPA_PLATFORM", "windows" if sys.platform == "win32" else "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QRegion  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

# The marks come up a moment after the scene starts, as in a lobby.
MARKS_AT = 0.2


def main() -> None:
    key, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from blacklist_detect.love_scenes import DESIGN, sample_stage
    from blacklist_detect.ui_love_pick import SampleMarks

    module = importlib.import_module(f"blacklist_detect.love_scenes.{key}")
    if sys.argv[3:] == ["anim"]:
        _anim(key, module, out)
        sys.stdout.flush()
        os._exit(0)
    times = [float(x) for x in sys.argv[3:]] or [0.3, 0.8, 1.5, 2.5, 3.5, module.DURATION - 0.4]
    lobby = QImage(str(Path("blacklist_detect/assets/sample-lobby.jpg")))
    stage = sample_stage()
    paint = module.make(stage)
    marks = SampleMarks(key)
    for t in times:
        image = lobby.scaled(round(DESIGN[0]), round(DESIGN[1]), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        image = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        paint(painter, t)
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(stage.gap)
        _marks(painter, marks, t)
        painter.end()
        image.save(str(out / f"{key}_t{t:.1f}.png"))
    # Timing at 1920x1080, as the border window plays it (scaled from the design size).
    width, height = 1920, round(1920 * DESIGN[1] / DESIGN[0])
    big = sample_stage(width, height)
    paint = module.make(big)
    ratio = getattr(module, "MAX_RATIO", None)
    spent = []
    frame = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    t = 0.0
    while t <= module.DURATION:
        frame.fill(Qt.transparent)
        start = time.perf_counter()
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.Antialiasing)
        paint(painter, t)
        painter.end()
        spent.append((time.perf_counter() - start) * 1000)
        t += 1 / 30
    spent.sort()
    print(
        f"{key}: median {statistics.median(spent):.1f} ms, 90% {spent[int(len(spent) * 0.9)]:.1f} ms, "
        f"worst {spent[-1]:.1f} ms at {width}x{height} (MAX_RATIO {ratio}); frames in {out}"
    )
    print(f"{key} marks: {_time_marks(SampleMarks(key, width / DESIGN[0]), module.DURATION)} at {width}x{height}, 1 px per point")
    sys.stdout.flush()
    os._exit(0)


def _marks(painter: QPainter, marks, t: float) -> None:  # noqa: ANN001
    """The 心动 marks by the button, as they are t seconds into the scene."""
    if t < MARKS_AT:
        return
    for pixmap, at in marks.at(t - MARKS_AT):
        painter.drawPixmap(QPointF(at), pixmap)


def _time_marks(marks, duration: float) -> str:  # noqa: ANN001
    """The median time one paint of each mark takes, over the scene at 30 fps: the ring, the badge
    and the card, each with what is on it."""
    names = ("ring", "badge", "card")
    spent: dict[str, list[float]] = {name: [] for name in names}
    t = 0.0
    while t <= duration:
        for name, widget in zip(names, marks.widgets, strict=True):
            widget.set_time(t if marks.moving else 0.0)
            image = QImage(widget.size(), QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
            start = time.perf_counter()
            widget.render(image, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
            spent[name].append((time.perf_counter() - start) * 1000)
        t += 1 / 30
    each = ", ".join(f"{name} {statistics.median(spent[name]):.2f} ms" for name in names)
    return f"median {each} ({'moving' if marks.moving else 'still'})"


def _anim(key: str, module, out: Path) -> None:  # noqa: ANN001
    """The scene over the sample lobby, start to finish, as an animation a person can watch."""
    from PIL import Image

    from blacklist_detect.love_scenes import DESIGN, sample_stage
    from blacklist_detect.ui_love_pick import SampleMarks

    fps, wide = 20, 960
    lobby = QImage(str(Path("blacklist_detect/assets/sample-lobby.jpg")))
    lobby = lobby.scaled(round(DESIGN[0]), round(DESIGN[1]), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    lobby = lobby.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    paint = module.make(sample_stage())
    marks = SampleMarks(key)
    frames = []
    count = int((module.DURATION + 0.4) * fps)
    for i in range(count):
        image = QImage(lobby)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        paint(painter, min(module.DURATION, i / fps))
        _marks(painter, marks, i / fps)
        painter.end()
        small = image.scaledToWidth(wide, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGB888)
        data = bytes(small.constBits())[: small.bytesPerLine() * small.height()]
        frame = Image.frombytes("RGB", (small.width(), small.height()), data, "raw", "RGB", small.bytesPerLine())
        frames.append(frame)
    target = out / f"{key}.webp"
    frames[0].save(target, save_all=True, append_images=frames[1:], duration=round(1000 / fps), loop=0, quality=85, method=4)
    print(f"{key}: {len(frames)} frames, {target.stat().st_size / 1e6:.1f} MB -> {target}")


if __name__ == "__main__":
    main()
