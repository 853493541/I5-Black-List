"""The Python 竖琴清风 marks (lyre.py's card, ring, badge, lead) the Rust ones are compared with.

Run from the root of a checkout: PYTHONPATH=. python rust/scenes/lyre/py_marks.py
Writes rust/scenes/lyre/mark_<name>.png at one pixel a point (the lead at its own three).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["APPDATA"] = os.environ["HOME"] = tempfile.mkdtemp(prefix="lyre-marks-")

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

OUT = Path("rust/scenes/lyre")


def main() -> None:
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from blacklist_detect.love_scenes import lyre

    lyre._card_art(QRectF(100, 200, 150, 40), 1.0).save(str(OUT / "mark_card.png"))
    lyre._ring_art(QRectF(500, 600, 300, 64), 1.0)[1].save(str(OUT / "mark_ring.png"))
    lyre._badge_art(QRectF(0, 0, 64, 64), 1.0).save(str(OUT / "mark_badge.png"))
    for index in (0, 1):
        lyre.lead(18, index).toImage().save(str(OUT / f"mark_lead{index}.png"))
    os._exit(0)


if __name__ == "__main__":
    main()
