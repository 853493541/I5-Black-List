"""The 毛茸茸 (fluffy.py) shapes the Rust port takes from Qt: every path built with Qt's path booleans,
strokers or text, as polygons at unit size (a cat's head width, a star's radius, the scene's unit u),
written to rust/scenes/src/fluffy/shapes.txt. Everything else the Rust scene works out itself.

Run from the root of a checkout: PYTHONPATH=. python rust/scenes/fluffy/gen_shapes.py

Each item is `item <key> <color> <a> <width> <min width>` (a: a part's lift or a fill's alpha), then
its polygons, `poly <sign> x y x y ...`: outline items keep Qt's own subpaths (their start and order
set how the ink wobbles), fill items are simplified, sign +1/-1 so that summed windings fill them.
"""

from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="fluffy-shapes-")

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QFont, QPainterPath, QPainterPathStroker, QPen, QPolygonF, QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

S = 100.0  # shapes are built this big, then divided down, so Qt's curves are finely cut
OUT = Path("rust/scenes/src/fluffy/shapes.txt")
lines: list[str] = []


def polys(path: QPainterPath, norm: float, fill: bool) -> list[tuple[int, list[QPointF]]]:
    if fill:
        path = path.simplified()
    raw = [list(poly) for poly in path.toSubpathPolygons()]
    raw = [poly for poly in raw if len(poly) >= 3]
    out = []
    for poly in raw:
        sign = 1
        if fill:
            area = sum(a.x() * b.y() - b.x() * a.y() for a, b in zip(poly, poly[1:] + poly[:1]))
            depth = sum(QPolygonF(other).containsPoint(poly[0], Qt.OddEvenFill) for other in raw if other is not poly)
            sign = (1 if area > 0 else -1) * (1 if depth % 2 == 0 else -1)
        out.append((sign, [QPointF(p.x() / norm, p.y() / norm) for p in poly]))
    return out


def item(key: str, path: QPainterPath, norm: float, fill: bool, color: str = "#000000", a: float = 0.0, width: float = 0.0, least: float = 0.0) -> None:
    lines.append(f"item {key} {color} {a!r} {width / norm!r} {least!r}")
    for sign, poly in polys(path, norm, fill):
        lines.append(f"poly {sign} " + " ".join(f"{p.x():.6g} {p.y():.6g}" for p in poly))


def point(key: str, *pts: QPointF, norm: float = S) -> None:
    lines.append(f"item {key} #000000 0 0 0")
    lines.append("poly 1 " + " ".join(f"{p.x() / norm:.9g} {p.y() / norm:.9g}" for p in pts))


def stroked(path: QPainterPath, pen: QPen) -> QPainterPath:
    stroker = QPainterPathStroker(pen)
    return stroker.createStroke(path)


class Recorder:
    """Stands in for the QPainter the cats' features are drawn with: keeps what it is asked to fill."""

    def __init__(self, key: str) -> None:
        self.key, self.n, self.transform, self.brush, self.saved = key, 0, QTransform(), None, []

    def save(self) -> None:
        self.saved.append(self.transform)

    def restore(self) -> None:
        self.transform = self.saved.pop()

    def setTransform(self, t: QTransform, combine: bool = False) -> None:  # noqa: N802
        self.transform = t * self.transform if combine else t

    def _fill(self, path: QPainterPath, color) -> None:  # noqa: ANN001
        item(f"{self.key}.feat{self.n}", self.transform.map(path), S, True, color.name(), color.alphaF())
        self.n += 1

    def fillPath(self, path: QPainterPath, color) -> None:  # noqa: N802, ANN001
        self._fill(path, color)

    def strokePath(self, path: QPainterPath, pen: QPen) -> None:  # noqa: N802
        self._fill(stroked(path, pen), pen.color())

    def setPen(self, _pen) -> None:  # noqa: N802, ANN001
        pass

    def setBrush(self, color) -> None:  # noqa: N802, ANN001
        self.brush = color

    def drawEllipse(self, c: QPointF, rx: float, ry: float) -> None:  # noqa: N802
        path = QPainterPath()
        path.addEllipse(c, rx, ry)
        self._fill(path, self.brush)


def main() -> None:
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from blacklist_detect.love_scenes import fluffy as f

    captured = {}
    real_fur = f._fur

    def fake_fur(box, scale, parts, soft, outline, *, middle=None, blush=None, cut=None, seed=1, shadow=0.0, after=None):  # noqa: ANN001, ANN202
        captured.update(box=box, parts=parts, outline=outline, middle=middle, blush=blush, after=after)
        return None

    f._fur = fake_fur
    turns = (0.0, 90.0, 0.0, 0.0)
    for index, coat in enumerate((0, 1, 2, 3)):
        for face in f.FACES:
            f._cat(S, 1.0, coat, -0.82 * turns[index], face)
            key = f"cat{index}.{face}"
            for k, (path, tint, lift) in enumerate(captured["parts"]):
                item(f"{key}.part{k}", path, S, True, tint, lift)
            for k, (path, width, tint) in enumerate(captured["outline"]):
                item(f"{key}.out{k}", path, S, False, tint, 0.0, width, 0.0)
            item(f"{key}.blush", captured["blush"], S, True)
            box = captured["box"]
            point(f"{key}.box", box.topLeft(), box.bottomRight(), captured["middle"])
            captured["after"](Recorder(key))
        f._cat_paws(S, 1.0, coat)
        (path, tint, _lift), = captured["parts"]
        item(f"paws{index}.part0", path, S, True, tint, 0.0)
        item(f"paws{index}.out0", captured["outline"][0][0], S, False, "#2b6268", 0.0, captured["outline"][0][1])
        captured["after"](Recorder(f"paws{index}"))
        point(f"paws{index}.box", captured["box"].topLeft(), captured["box"].bottomRight())
        f._cat_tail(S, 1.0, coat)
        for k, (path, tint, lift) in enumerate(captured["parts"]):
            item(f"tail{index}.part{k}", path, S, True, tint, lift)
        item(f"tail{index}.out0", captured["outline"][0][0], S, False, "#2b6268", 0.0, captured["outline"][0][1])
        point(f"tail{index}.box", captured["box"].topLeft(), captured["box"].bottomRight())
    f._fur = real_fur
    star = f._star_path(S)
    item("star.part0", star, S, True)
    item("star.out0", star, S, False)
    palm, toes = f._paw_shapes(S)
    turn = QTransform().rotate(90)
    item("paw.part0", turn.map(palm).united(turn.map(toes)), S, True)
    rim = QPainterPath()
    rim.addEllipse(QPointF(0, 0), S, S)
    rim.addEllipse(QPointF(0, 0), S * 0.44, S * 0.44)
    item("binder.out0", rim, S, False)
    # The tab, at the size it has on a 1920x1080 screen (its words' pixel size is rounded).
    u = min(1920 / 1635, 1080 / 848)
    tab = QRectF(0, 0, 330 * u, 44 * u)
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(-tab.width() / 2, -tab.height() / 2, tab.width(), tab.height()), 12 * u, 12 * u)
    stars = QPainterPath()
    for x in (-tab.width() / 2 + 22 * u, tab.width() / 2 - 22 * u):
        stars.addPath(QTransform().translate(x, 0).map(f._star_path(10 * u)))
    stars = stars.simplified()
    item("tab.part0", shape, u, True)
    item("tab.part1", stars, u, True)
    item("tab.out0", shape, u, False)
    item("tab.out1", stars, u, False)
    font = QFont()
    font.setFamilies(["YouYuan", "Microsoft YaHei", "Microsoft YaHei UI"])
    font.setPixelSize(max(1, round(20 * u)))
    font.setWeight(QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 7 * u)
    from PySide6.QtGui import QFontMetricsF

    text = "毛茸茸保护协会"
    metrics = QFontMetricsF(font)
    words_box = QRectF(-tab.width() / 2, -tab.height() / 2, tab.width() + 7 * u, tab.height())
    # Where drawText puts the words: the box QPainter lays them out in, its baseline an ascent down.
    from PySide6.QtGui import QImage, QPainter

    image = QImage(8, 8, QImage.Format_ARGB32_Premultiplied)
    q = QPainter(image)
    q.setFont(font)
    laid = q.boundingRect(words_box, Qt.AlignCenter, text)
    q.end()
    base = QPointF(laid.left(), laid.top() + metrics.ascent())
    words = QPainterPath()
    words.addText(base, font, text)
    item("tab.words", words, u, True, "#2b6268", 1.0)
    OUT.write_text("\n".join(lines) + "\n")
    print(f"{OUT}: {len(lines)} lines, {OUT.stat().st_size // 1024} KB")
    os._exit(0)


if __name__ == "__main__":
    main()
