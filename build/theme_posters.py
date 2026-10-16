"""Draw each 嘉宾特效 scene's picture for its thumbnails (ui_guests.thumbnail): the scene at its best moment
over the fake-name sample lobby, with the app's 嘉宾 marks in its look, as a lobby would show it.

    python build/theme_posters.py [key ...]

Writes blacklist_detect/assets/posters/<key>.jpg for every scene in love_scenes.SCENES (or the ones named),
WIDTH pixels wide. Run it again when a scene changes or a new one is added (a new one is caught at POSTER_SHARE of
its length until it gets a moment of its own here); tests/test_love_scenes.py checks every scene has one.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows" if sys.platform == "win32" else "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

OUT = ROOT / "blacklist_detect" / "assets" / "posters"
# 场景管理's preview (480 points) at 200%: sharp there and in every card, on any screen the app runs on.
WIDTH = 960
# Each scene's best moment, in seconds: its lightning, its fireworks, its claw with the notice in place, the
# lyre's second strum with the band full.
POSTER_AT = {
    "classic": 2.0,
    "lace": 2.5,
    "ice": 2.75,
    "stars": 2.75,
    "cyber": 2.82,
    "neon": 3.5,
    "angel": 4.2,
    "equation": 3.5,
    "fluffy": 2.75,
    "claw": 3.4,
    "lyre": 2.95,
}
POSTER_SHARE = 0.55
# The marks come up a moment after the scene starts, as in a lobby.
MARKS_AT = 0.2


def main() -> None:
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from blacklist_detect import love_scenes
    from blacklist_detect.love_scenes import DESIGN, sample_stage
    from blacklist_detect.ui_love_pick import SAMPLE_LOBBY, SampleMarks

    OUT.mkdir(parents=True, exist_ok=True)
    lobby = QImage(str(SAMPLE_LOBBY)).scaled(round(DESIGN[0]), round(DESIGN[1]), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    for key, name in love_scenes.SCENES:
        if sys.argv[1:] and key not in sys.argv[1:]:
            continue
        module = love_scenes.load(key)
        t = POSTER_AT.get(key, module.DURATION * POSTER_SHARE)
        image = lobby.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        module.make(sample_stage())(painter, t)
        marks = SampleMarks(key)
        for pixmap, at in marks.at(max(0.0, t - MARKS_AT)):
            painter.drawPixmap(QPointF(at), pixmap)
        marks.close()
        painter.end()
        height = round(WIDTH * DESIGN[1] / DESIGN[0])
        poster = image.scaled(WIDTH, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGB32)
        poster.save(str(OUT / f"{key}.jpg"), "JPG", 88)
        print(f"{key} ({name}) at {t:.2f} s")


if __name__ == "__main__":
    main()
