"""Render a 心动 scene over the sample lobby at full size, and time its frames at 1920x1080.

Run from the root of a checkout:
    PYTHONPATH=. python tools/love_frames.py <key> <out_dir> [t1 t2 ...]
    PYTHONPATH=. python tools/love_frames.py <key> <out_dir> anim
The second writes <out_dir>/<key>.webp instead: the whole scene playing at 20 fps, 960 px wide, in full
color (an animated WebP: a GIF's 256 colors band the glows and it is four times the size).
Writes <out_dir>/<key>_t<t>.png (1635x848 lobby with the scene and the button gap outlined faintly),
and prints the median and worst frame time at 1920x1080 over the whole scene (30 fps).
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

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPen  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def main() -> None:
    key, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from blacklist_detect.love_scenes import DESIGN, sample_stage

    module = importlib.import_module(f"blacklist_detect.love_scenes.{key}")
    if sys.argv[3:] == ["anim"]:
        _anim(key, module, out)
        sys.stdout.flush()
        os._exit(0)
    times = [float(x) for x in sys.argv[3:]] or [0.3, 0.8, 1.5, 2.5, 3.5, module.DURATION - 0.4]
    lobby = QImage(str(Path("blacklist_detect/assets/sample-lobby.jpg")))
    stage = sample_stage()
    paint = module.make(stage)
    for t in times:
        image = lobby.scaled(round(DESIGN[0]), round(DESIGN[1]), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        image = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        paint(painter, t)
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(stage.gap)
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
    sys.stdout.flush()
    os._exit(0)


def _anim(key: str, module, out: Path) -> None:  # noqa: ANN001
    """The scene over the sample lobby, start to finish, as an animation a person can watch."""
    from PIL import Image

    from blacklist_detect.love_scenes import DESIGN, sample_stage

    fps, wide = 20, 960
    lobby = QImage(str(Path("blacklist_detect/assets/sample-lobby.jpg")))
    lobby = lobby.scaled(round(DESIGN[0]), round(DESIGN[1]), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    lobby = lobby.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    paint = module.make(sample_stage())
    frames = []
    count = int((module.DURATION + 0.4) * fps)
    for i in range(count):
        image = QImage(lobby)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        paint(painter, min(module.DURATION, i / fps))
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
