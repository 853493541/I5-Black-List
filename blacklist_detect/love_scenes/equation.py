"""数学: the blueprint night of 数学 with a quieter heart and more of its equations.

The edges darken to blueprint navy with faint graph paper in them, fading toward the middle. Across
the top right the heart's own parametric equations write themselves in chalk, braced as a system:
x(t) = 16 sin³t and y(t) = 13 cos t − 5 cos 2t − 2 cos 3t − cos 4t. Under them, on labelled axes, a
chain of rotating circles (the curve's Fourier series) traces the heart in one lap while a readout
t = 0.00 … 6.28 ticks beside it and dashed lines drop from the pen to both axes. The circles fade, the
traced line lights up, and a light, quiet fill grows from the middle out; it beats once and a line
ripples away. Equations write themselves down the left side and in the corners, a cardioid plots
itself in gold on a polar grid in the top left, a golden spiral grows through its Fibonacci squares
in the bottom right, and math symbols drift up the sides. At the end the equations crumble into
chalk dust and everything fades.

Its marks are drafting work: the ring is the button drawn to scale, a ruler along its top with a pink
cursor sliding on it and dimension lines with arrowheads round its sides and bottom; the badge an
enamel dial with ∞ on it, a point of light running round the lemniscate; the card a sheet of
blueprint paper with a fine grid, its axes ticked, headed { 心动 } in set notation, a plotted point
before each name.
"""

from __future__ import annotations

import cmath
import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QRadialGradient,
    QTransform,
)

from blacklist_detect.love_scenes.draw import (
    Wash,
    clamp,
    col,
    ease_in,
    ease_in_out,
    ease_out,
    gradient,
    heart_path,
    polyline,
    soft_dot,
    win,
)
from blacklist_detect.love_scenes.light import bloom, blur, glow, mask, noise, picture, rgb

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
CHALK = "#7fd8ff"
INK = "#eaf6ff"
PINK = "#ff9fc4"
ROSE = "#e0507f"
NAVY = "#0f2440"
DEEP = "#06142a"
GOLD = "#f3cf7a"
PHI = (1 + 5 ** 0.5) / 2
# The equations' glow is soft: worked out at this share of the stage's size and laid on scaled up.
SOFT = 0.5
SYMBOLS = "πΣ∞√θ∫φ∂Δ"
DIGITS = "0123456789."

LOOK = {
    "glow": (127, 216, 255),
    "rim": CHALK,
    "band": (CHALK, PINK),
    "card": ("#14335c", "#0a1c38"),
    "edge": "#5fb8e6",
    "ink": INK,
    "flowers": (("#f2fbff", "#9fe1ff", "#3fa9e0"), ("#fff0f6", PINK, ROSE)),
    "disc": ("#13304f", "#0a1a30"),
    "heart": (PINK, ROSE),
    "deep": ROSE,
    "deep_glow": (255, 110, 160),
}
MARKS_ANIMATED = True
# Room above the card's paper for its { 心动 } heading, which sits on the paper's top edge.
CARD_TOP = 11
CARD_PAD = (12, 11, 14, 9)
CARD_FONT = "KaiTi"


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(23)
    paper = Wash(lambda q, w, h: _paper(q, w, h, u))
    # The system of the heart's equations along the top right, the = signs one above the other.
    px = 23 * u
    t_ = _it("t")
    lower = _formula(
        [("t", _it("y") + "("), ("t", t_, True), ("t", ") = 13 cos "), ("t", t_, True), ("t", " − 5 cos 2"), ("t", t_, True),
         ("t", " − 2 cos 3"), ("t", t_, True), ("t", " − cos 4"), ("t", t_, True)],
        px, QPointF(width - 22 * u, 66 * u), 0.8, 1.65, CHALK, rnd, ends=True,
    )
    upper = _formula(
        [("t", _it("x") + "("), ("t", t_, True), ("t", ") = 16 sin"), ("sup", "3"), ("t", t_, True)],
        px, QPointF(lower.left, 35 * u), 0.45, 0.95, CHALK, rnd,
    )
    brace = _lit(_brace(lower.left - px * 0.22, 35 * u - px * 0.86, 66 * u + px * 0.3, px), QPainterPath(), px, 0.3, 0.5, CHALK, rnd)
    # The heart under them, on its own axes, a little left of the corner.
    heart_at = QPointF(width * 0.873, height * 0.177)
    size = 152 * u
    k = size / 34
    origin = QPointF(heart_at.x(), heart_at.y() + 2.5 * k)
    readout = _Readout(QPointF(origin.x() - 21 * k - 16 * u, origin.y() + 8 * u), px * 1.05, rnd)
    formulas = [
        brace,
        upper,
        lower,
        readout.name,
        _formula([("t", _it("e")), ("sup", _it("iπ")), ("t", " + 1 = 0")], 30 * u, QPointF(24 * u, height * 0.44), 1.1, 1.75, CHALK, rnd),
        _formula([("t", "∫"), ("sup", "∞"), ("sub", "−∞"), ("t", " " + _it("e")), ("sup", "−" + _it("x") + "²"), ("t", " d" + _it("x") + " = "), ("root", _it("π"))], 26 * u, QPointF(22 * u, height * 0.62), 1.85, 2.6, CHALK, rnd),
        _formula([("t", _it("r") + " = 1 − sin " + _it("θ"))], 27 * u, QPointF(width * 0.19, height * 0.085), 1.0, 1.6, GOLD, rnd),
        _formula([("t", _it("φ") + " = "), ("frac", "1 + √5", "2")], 28 * u, QPointF(width * 0.718, height * 0.91), 2.05, 2.7, GOLD, rnd),
        _formula([("t", "lim"), ("under", _it("t") + "→∞"), ("t", " "), ("han", "心动", True), ("t", "(" + _it("t") + ") = "), ("t", "∞", True)], 31 * u, QPointF(30 * u, height * 0.915), 2.85, 3.6, PINK, rnd, mark=PINK),
    ]
    # Each crumbles to chalk dust in turn at the end, the last written last.
    for index, formula in enumerate(formulas):
        formula.leaves = 4.1 + 0.05 * index
    # The readout goes with the circles it counts for.
    readout.name.leaves = 2.45
    polar = (QPointF(width * 0.1, height * 0.12), 46 * u)
    golden = QRectF(width - 14 * u - 136 * u * PHI, height - 10 * u - 136 * u, 136 * u * PHI, 136 * u)
    spiral = _spiral(golden)
    glyphs = _glyphs(u)
    # Where the drifting symbols keep out of the way: the equations, the heart, the polar plot, the spiral.
    boxes = [formula.box.adjusted(-14 * u, -14 * u, 14 * u, 14 * u) for formula in formulas]
    boxes += [
        QRectF(origin.x() - 130 * u, 0, 260 * u, origin.y() + 100 * u),
        QRectF(polar[0].x() - 104 * u, 0, 208 * u, polar[0].y() + 104 * u),
        golden.adjusted(-10 * u, -10 * u, 0, 0),
    ]
    drift = []
    for i in range(22):
        left = i % 3 == 0
        x = (rnd.uniform(0.012, 0.1) if left else rnd.uniform(0.952, 0.988)) * width
        drift.append((rnd.choice(SYMBOLS), x, rnd.uniform(0.25, 1.05) * height, rnd.uniform(18, 34) * u, rnd.uniform(0.6, 1.1), rnd.uniform(0, 6.28), rnd.uniform(0.0, 1.2)))
    heart = _Heart(heart_at, size, u)

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.3, 5.0))
        p.save()
        p.setOpacity(life)
        paper.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.8)) * (1 - leave))
        _drift(p, t, drift, glyphs, boxes, u, (1 - leave) * ease_out(win(t, 0.2, 1.0)))
        _spiral_paint(p, t, spiral, u, 1 - leave)
        _polar(p, t, *polar, u, 1 - leave)
        heart.paint(p, t)
        readout.paint(p, t, u, 2 * math.pi * heart.lap(t))
        for formula in formulas:
            formula.paint(p, t, u)
        p.restore()

    return paint


def _it(text: str) -> str:
    """Letters as Cambria Math sets variables: in math italic, from Unicode's own alphabet."""
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append("ℎ" if ch == "h" else chr(0x1D44E + ord(ch) - ord("a")))
        elif ch in "θπφ":
            out.append({"θ": "\U0001d703", "π": "\U0001d70b", "φ": "\U0001d711"}[ch])
        else:
            out.append(ch)
    return "".join(out)


def _font(px: float, han: bool = False) -> QFont:
    font = QFont()
    font.setFamilies(["KaiTi", "STKaiti", "Microsoft YaHei"] if han else ["Cambria Math", "Cambria"])
    font.setPixelSize(max(1, round(px)))
    return font


@dataclass
class _Formula:
    """An equation in chalk: its letters (ink, and accent in its mark color), the glow round them
    drawn once, the chalk dust it crumbles into, and when it is written."""

    ink: QPainterPath
    accent: QPainterPath
    box: QRectF
    glow: QImage
    glow_box: QRectF
    motes: list[tuple]
    start: float
    end: float
    tint: str
    mark: str
    left: float = 0.0
    leaves: float = 4.2

    def paint(self, p: QPainter, t: float, u: float) -> None:
        write = win(t, self.start, self.end)
        if write <= 0:
            return
        gone = ease_in_out(win(t, self.leaves, self.leaves + 0.6))
        if gone < 1:
            feather = 26 * u
            front = self.glow_box.left() + (self.glow_box.width() + feather) * ease_in_out(write)

            def letters(lift: float) -> None:
                p.save()
                base = p.opacity() * (1 - gone)
                p.setOpacity(base * (0.85 + 0.15 * math.sin(t * 2.2 + self.start * 3)))
                p.setRenderHint(QPainter.SmoothPixmapTransform)
                p.drawImage(self.glow_box.translated(0, -lift), self.glow)
                p.setOpacity(base)
                p.translate(0, -lift)
                p.setPen(Qt.NoPen)
                p.setBrush(col(INK, 0.95))
                p.drawPath(self.ink)
                p.setBrush(col(self.mark, 0.98))
                p.drawPath(self.accent)
                p.restore()

            # Rising a little as it crumbles.
            _written(p, letters, self.glow_box, front, feather, 6 * u * gone)
            nib = max(self.box.left(), front - feather * 0.6)
            if write < 1 and nib < self.box.right():
                # The nib: a point of chalk light where the letters are coming, bobbing as a hand does.
                y = self.box.top() + self.box.height() * (0.5 + 0.3 * math.sin(t * 31 + self.start * 7))
                soft_dot(p, nib, y, 15 * u, self.tint, 0.55)
                soft_dot(p, nib, y, 4 * u, "#ffffff", 0.9)
        if gone > 0:
            p.setPen(Qt.NoPen)
            for x, y, rise, sway, r, delay in self.motes:
                k = clamp((gone - delay) / (1 - delay))
                if k <= 0 or k >= 1:
                    continue
                a = math.sin(math.pi * k) * (1 - k * 0.4)
                px, py = x + sway * k, y - rise * ease_out(k)
                p.setBrush(col(INK, 0.8 * a))
                p.drawEllipse(QPointF(px, py), r, r)
                if r > 1.3 * u:
                    soft_dot(p, px, py, r * 4, self.tint, 0.35 * a)


def _written(p: QPainter, draw, box: QRectF, front: float, feather: float, lift: float) -> None:  # noqa: ANN001
    """What draw paints, up to front only, the last of it fading in as fresh chalk does."""
    done = front - feather
    if done >= box.right():
        draw(lift)
        return
    if done > box.left():
        p.save()
        p.setClipRect(QRectF(box.left(), box.top() - lift, done - box.left(), box.height()))
        draw(lift)
        p.restore()
    slices = 4
    for i in range(slices):
        left = done + feather * i / slices
        right = left + feather / slices
        if right <= box.left() or left >= box.right():
            continue
        p.save()
        p.setOpacity(p.opacity() * (1 - (i + 0.5) / slices))
        p.setClipRect(QRectF(max(left, box.left()), box.top() - lift, right - max(left, box.left()), box.height()))
        draw(lift)
        p.restore()


def _formula(items: list[tuple], px: float, at: QPointF, start: float, end: float, tint: str, rnd: random.Random, ends: bool = False, mark: str = PINK) -> _Formula:
    """An equation set in Cambria Math, px high, its baseline starting at at (ending there, if
    ends). Each item is (kind, text, accent?): t text, big a large operator, under a small line
    centered beneath the one before, sup and sub, root a square root with its bar, frac a fraction
    (kind, top, bottom), han Chinese in a brush hand."""
    ink, accent = QPainterPath(), QPainterPath()
    big, small = _font(px), _font(px * 0.62)
    x = 0.0
    last = (0.0, 0.0, 0.0)
    script = None
    for item in items:
        kind = item[0]
        out = accent if item[-1] is True else ink
        if kind in ("t", "han", "big"):
            font = _font(px, han=True) if kind == "han" else _font(px * 1.45) if kind == "big" else big
            advance = QFontMetricsF(font).horizontalAdvance(item[1])
            out.addText(QPointF(x, px * 0.13 if kind == "big" else 0.0), font, item[1])
            # What goes under it: below a big operator's foot, or just under the line.
            last = (x, x + advance, px * 0.9 if kind == "big" else px * 0.66)
            x += advance
        elif kind in ("sup", "sub"):
            advance = QFontMetricsF(small).horizontalAdvance(item[1])
            # A sub straight after a sup sits under it, as an integral's limits do.
            stacked = script is not None and script[0] != kind
            left = script[1] if stacked else x
            out.addText(QPointF(left + px * 0.03, -px * 0.42 if kind == "sup" else px * 0.24), small, item[1])
            x = max(x, left + px * 0.03 + advance)
            script = (kind, left)
            continue
        elif kind == "under":
            advance = QFontMetricsF(small).horizontalAdvance(item[1])
            middle = (last[0] + last[1]) / 2
            out.addText(QPointF(middle - advance / 2, last[2]), small, item[1])
            x = max(x, middle + advance / 2)
        elif kind == "root":
            sign = QPainterPath()
            sign.addText(QPointF(x, 0.0), big, "√")
            top = sign.boundingRect().top() if not sign.isEmpty() else -px * 0.8
            out.addPath(sign)
            x += QFontMetricsF(big).horizontalAdvance("√")
            advance = QFontMetricsF(big).horizontalAdvance(item[1])
            out.addRect(QRectF(x - px * 0.04, top, advance + px * 0.1, px * 0.055))
            out.addText(QPointF(x + px * 0.03, 0.0), big, item[1])
            x += advance + px * 0.1
        elif kind == "frac":
            frac = _font(px * 0.74)
            metrics = QFontMetricsF(frac)
            top, bottom = metrics.horizontalAdvance(item[1]), metrics.horizontalAdvance(item[2])
            span = max(top, bottom) + px * 0.24
            axis = -px * 0.3
            out.addRect(QRectF(x + px * 0.04, axis - px * 0.03, span - px * 0.08, px * 0.055))
            out.addText(QPointF(x + (span - top) / 2, axis - px * 0.16), frac, item[1])
            out.addText(QPointF(x + (span - bottom) / 2, axis + px * 0.16 + metrics.ascent() * 0.78), frac, item[2])
            x += span
        script = None
    if ends:
        at = QPointF(at.x() - x, at.y())
    ink.translate(at)
    accent.translate(at)
    formula = _lit(ink, accent, px, start, end, tint, rnd, mark)
    if formula.box.isEmpty() or ink.isEmpty() and accent.isEmpty():
        formula.box = QRectF(at.x(), at.y() - px, max(1.0, x), px * 1.3)
    formula.left = at.x()
    return formula


def _lit(ink: QPainterPath, accent: QPainterPath, px: float, start: float, end: float, tint: str, rnd: random.Random, mark: str = PINK) -> _Formula:
    """Letters already set as paths, lit in chalk: the glow round them, and the dust they crumble into."""
    box = ink.boundingRect().united(accent.boundingRect())
    if box.isEmpty():
        box = QRectF(ink.currentPosition(), ink.currentPosition()).adjusted(0, -px, px, 0)
    glow_box = box.adjusted(-px * 0.7, -px * 0.7, px * 0.7, px * 0.7)
    w, h = max(1, round(glow_box.width() * SOFT)), max(1, round(glow_box.height() * SOFT))

    def draw(q: QPainter) -> None:
        q.scale(SOFT, SOFT)
        q.translate(-glow_box.left(), -glow_box.top())
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(ink)
        q.drawPath(accent)

    shape = mask(w, h, draw)
    halo = blur(shape, px * SOFT * 0.1) * 0.9 + blur(shape, px * SOFT * 0.4) * 0.75
    lit = glow(halo[..., None] * rgb(tint))
    # The chalk dust it crumbles into: specks from its own letters.
    ys, xs = np.nonzero(shape > 0.5)
    motes = []
    for i in rnd.sample(range(len(xs)), min(len(xs), 34)):
        x0 = glow_box.left() + (xs[i] + 0.5) / SOFT
        y0 = glow_box.top() + (ys[i] + 0.5) / SOFT
        motes.append((x0, y0, rnd.uniform(18, 46) * px / 26, rnd.uniform(-12, 12) * px / 26, rnd.uniform(0.7, 1.9) * px / 26, rnd.uniform(0, 0.45)))
    return _Formula(ink, accent, box, lit, glow_box, motes, start, end, tint, mark)


def _brace(x: float, top: float, bottom: float, px: float) -> QPainterPath:
    """A left curly brace in a chalk line, its point at x's left, from top to bottom."""
    wide = px * 0.34
    middle = (top + bottom) / 2
    bend = min(wide * 0.9, (bottom - top) / 6)
    stem, tip = x - wide * 0.5, x - wide
    line = QPainterPath(QPointF(x, top))
    line.quadTo(QPointF(stem, top), QPointF(stem, top + bend))
    line.lineTo(QPointF(stem, middle - bend))
    line.quadTo(QPointF(stem, middle), QPointF(tip, middle))
    line.quadTo(QPointF(stem, middle), QPointF(stem, middle + bend))
    line.lineTo(QPointF(stem, bottom - bend))
    line.quadTo(QPointF(stem, bottom), QPointF(x, bottom))
    pen = QPainterPathStroker()
    pen.setWidth(px * 0.065)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen.createStroke(line)


class _Readout:
    """t = 0.00 … 6.28 beside the heart's axes, ticking as the circles turn: its name written in
    chalk like the equations, its digits lit once each and set in place every frame."""

    def __init__(self, at: QPointF, px: float, rnd: random.Random) -> None:
        font = _font(px)
        metrics = QFontMetricsF(font)
        # Digits are all one width in Cambria, so the number does not shuffle as it ticks.
        self.step = max((metrics.horizontalAdvance(ch) for ch in "0123456789"), default=px * 0.5) or px * 0.5
        self.dot = metrics.horizontalAdvance(".") or px * 0.25
        number = self.step * 3 + self.dot
        name = [("t", _it("t"), True), ("t", " = ")]
        prefix = sum(metrics.horizontalAdvance(text) for _kind, text, *_rest in name)
        self.left = at.x() - number
        self.base = at.y()
        self.name = _formula(name, px, QPointF(self.left - prefix, at.y()), 0.45, 0.72, CHALK, rnd)
        self.px = px
        self.glyphs: dict[str, tuple[QPainterPath, QImage, QRectF]] = {}
        for ch in DIGITS:
            path = QPainterPath()
            path.addText(QPointF(0, 0), font, ch)
            box = path.boundingRect().adjusted(-px * 0.5, -px * 0.5, px * 0.5, px * 0.5) if not path.isEmpty() else QRectF(0, -px, px, px)
            w, h = max(1, round(box.width() * SOFT)), max(1, round(box.height() * SOFT))

            def draw(q: QPainter, path: QPainterPath = path, box: QRectF = box) -> None:
                q.scale(SOFT, SOFT)
                q.translate(-box.left(), -box.top())
                q.setPen(Qt.NoPen)
                q.setBrush(Qt.white)
                q.drawPath(path)

            shape = mask(w, h, draw)
            halo = blur(shape, px * SOFT * 0.1) * 0.9 + blur(shape, px * SOFT * 0.4) * 0.75
            self.glyphs[ch] = (path, glow(halo[..., None] * rgb(PINK)), box)

    def paint(self, p: QPainter, t: float, u: float, value: float) -> None:
        a = ease_out(win(t, 0.55, 0.8)) * (1 - ease_in_out(win(t, 2.45, 2.95)))
        if a <= 0:
            return
        p.save()
        p.setOpacity(p.opacity() * a)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        x = self.left
        for ch in f"{value:.2f}":
            path, lit, box = self.glyphs[ch]
            wide = self.dot if ch == "." else self.step
            # Each figure centred in its cell.
            shift = (wide - path.boundingRect().width()) / 2 - path.boundingRect().left() if not path.isEmpty() else 0.0
            p.drawImage(box.translated(x + shift, self.base), lit)
            p.save()
            p.translate(x + shift, self.base)
            p.setPen(Qt.NoPen)
            p.setBrush(col("#fff2f7", 0.97))
            p.drawPath(path)
            p.restore()
            x += wide
        p.restore()


def _paper(p: QPainter, width: float, height: float, u: float) -> None:
    """Blueprint navy at the edges, deepest at the top, and graph paper in it that fades out
    before the names: fine squares, every fifth line stronger."""
    top = height * 0.34
    p.fillRect(QRectF(0, 0, width, top), gradient(QPointF(0, 0), QPointF(0, top), ((0, DEEP, 0.84), (0.5, NAVY, 0.42), (1, NAVY, 0))))
    side = 215 * u
    for start, end, rect in (
        (QPointF(0, 0), QPointF(side, 0), QRectF(0, 0, side, height)),
        (QPointF(width, 0), QPointF(width - side, 0), QRectF(width - side, 0, side, height)),
        (QPointF(0, height), QPointF(0, height - side * 0.8), QRectF(0, height - side * 0.8, width, side * 0.8)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, DEEP, 0.78), (0.45, NAVY, 0.4), (1, NAVY, 0))))
    grid = QImage(max(1, round(width)), max(1, round(height)), QImage.Format_ARGB32_Premultiplied)
    grid.fill(Qt.transparent)
    q = QPainter(grid)
    step = 22 * u
    for i in range(int(max(width, height) / step) + 2):
        strong = i % 5 == 0
        q.setPen(QPen(col(CHALK, 0.2 if strong else 0.085), (1.1 if strong else 0.8) * u))
        q.drawLine(QPointF(i * step, 0), QPointF(i * step, height))
        q.drawLine(QPointF(0, i * step), QPointF(width, i * step))
    # Rubbed out over the names, softly: an oval hole, gone in the middle, fading out to the edges.
    q.setCompositionMode(QPainter.CompositionMode_DestinationOut)
    hole = QRadialGradient(QPointF(0, 0), 1.0)
    hole.setColorAt(0, col("#000000", 1))
    hole.setColorAt(0.62, col("#000000", 1))
    hole.setColorAt(1, col("#000000", 0))
    brush = QBrush(hole)
    brush.setTransform(QTransform().scale(width * 0.6, height * 0.5).translate(0.535 / 0.6, 0.565 / 0.5))
    q.fillRect(QRectF(0, 0, width, height), brush)
    q.end()
    p.drawImage(QRectF(0, 0, width, height), grid)
    # A little chalk-blue light behind the heart and the polar plot.
    for x, y, r in ((0.873, 0.17, 300), (0.1, 0.14, 240)):
        soft_dot(p, width * x, height * y, r * u, "#2d6fa8", 0.32)


def _terms() -> list[tuple[int, complex]]:
    """The heart curve's Fourier series, largest circle first: (turns per lap, its arm), in heart
    units with y down, so the sum of arm · e^{i·turns·s} is the point at s."""
    count = 64
    s = np.linspace(0, 2 * np.pi, count, endpoint=False)
    x = 16 * np.sin(s) ** 3
    y = 13 * np.cos(s) - 5 * np.cos(2 * s) - 2 * np.cos(3 * s) - np.cos(4 * s)
    coeffs = np.fft.fft(x - 1j * y) / count
    turns = np.fft.fftfreq(count, 1 / count).astype(int)
    terms = [(int(k), complex(c)) for k, c in zip(turns, coeffs, strict=True) if abs(c) > 1e-6]
    return sorted(terms, key=lambda term: -abs(term[1]))


def _chain(terms: list[tuple[int, complex]], s: float) -> list[complex]:
    """The circles' centres along the chain, and its tip last, for a lap s in radians."""
    out = [0j]
    for k, c in terms:
        out.append(out[-1] + c * cmath.exp(1j * k * s))
    return out


def _scaled(path: QPainterPath, about: QPointF, scale: float) -> QPainterPath:
    return QTransform().translate(about.x(), about.y()).scale(scale, scale).translate(-about.x(), -about.y()).map(path)


class _Heart:
    """The hero: labelled axes, the circles tracing the heart in one lap, then the traced line lit
    and a quiet fill grown from the middle out; one beat, a line rippling away, a fade at the end.
    Its light is worked out per pixel once, in points; soft, it scales up on a sharper screen."""

    def __init__(self, centre: QPointF, size: float, u: float) -> None:
        self.centre, self.size, self.u = centre, size, u
        self.k = k = size / 34
        # The series' own origin (heart_points draws the curve 2.5 units lower), and the middle the fill grows from.
        self.origin = QPointF(centre.x(), centre.y() + 2.5 * k)
        self.middle = QPointF(centre.x(), centre.y() + 3.5 * k)
        self.terms = _terms()
        # The traced heart, one lap of the series, in heart units with y down.
        self.curve = [_chain(self.terms, 2 * math.pi * i / 240)[-1] for i in range(241)]
        self.outline = heart_path(centre.x(), centre.y(), size)
        self.box = QRectF(centre.x() - 22 * k, centre.y() - 15 * k, 44 * k, 35 * k)
        self.fill, self.line = self._light()
        self.labels = self._labels()

    def lap(self, t: float) -> float:
        return ease_in_out(win(t, 0.6, 2.45))

    def _light(self) -> tuple[QImage, QImage]:
        """The fill (pink, lighter toward its edge and on the upper left lobe, a faint rose halo
        round it) and the traced line's bloom, both at one pixel a point."""
        box, k, u = self.box, self.k, self.u
        w, h = max(8, round(box.width())), max(8, round(box.height()))

        def shape(q: QPainter) -> None:
            q.translate(-box.left(), -box.top())
            q.setPen(Qt.NoPen)
            q.setBrush(Qt.white)
            q.drawPath(self.outline)

        def stroke(q: QPainter) -> None:
            q.translate(-box.left(), -box.top())
            q.setPen(QPen(Qt.white, 2.4 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.setBrush(Qt.NoBrush)
            q.drawPath(self.outline)

        within = mask(w, h, shape)
        rim = np.clip((within - blur(within, 5 * k)) * 2.2, 0, 1) * within
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        # Heart units from its middle, for a soft light on the upper left lobe.
        hx = (xs + box.left() - self.centre.x()) / k
        hy = (ys + box.top() - self.centre.y()) / k
        sheen = np.exp(-((hx + 7) ** 2 + (hy + 2) ** 2) / 40) * within
        light = (
            rgb(ROSE)[None, None] * (0.07 * within)[..., None]
            + rgb(PINK)[None, None] * (0.05 * within + 0.3 * rim ** 1.4)[..., None]
            + rgb("#fff2f7")[None, None] * (0.09 * sheen)[..., None]
        )
        light += rgb(ROSE)[None, None] * (blur(within, 4 * k) * (1 - within) * 0.22)[..., None]
        line = mask(w, h, stroke)
        return glow(light.astype(np.float32)), bloom(line, PINK, ((2.5 * u, 0.9), (7 * u, 0.6), (16 * u, 0.35)), white=0.8)

    def _labels(self) -> list[tuple[QPainterPath, QPointF]]:
        """The axes' names and the numbers at their ticks, as chalk paths."""
        k, u, o = self.k, self.u, self.origin
        small, letter = _font(12 * u), _font(17 * u)
        out = []

        def put(text: str, font: QFont, x: float, y: float, align: str) -> None:
            path = QPainterPath()
            path.addText(QPointF(0, 0), font, text)
            r = path.boundingRect()
            dx = {"left": 0.0, "centre": -r.width() / 2, "right": -r.width()}[align] - r.left()
            path.translate(x + dx, y - r.top() - r.height() / 2)
            out.append((path, QPointF(x, y)))

        for value in (-8, 8):
            put(str(value).replace("-", "−"), small, o.x() + value * k, o.y() + 11 * u, "centre")
            put(str(value).replace("-", "−"), small, o.x() - 7 * u, o.y() - value * k, "right")
        put(_it("x"), letter, o.x() + 21 * k + 2 * u, o.y() - 11 * u, "centre")
        put(_it("y"), letter, o.x() + 9 * u, o.y() - 16 * k + 2 * u, "left")
        return out

    def paint(self, p: QPainter, t: float) -> None:
        fade = 1 - ease_in_out(win(t, 4.25, 4.85))
        if fade <= 0:
            return
        u = self.u
        lap = self.lap(t)
        self._axes(p, t, fade)
        grow = ease_out(win(t, 2.45, 3.3))
        lit = ease_out(win(t, 2.35, 2.6))
        beat = 1 + 0.06 * math.sin(math.pi * win(t, 3.3, 3.62))
        p.save()
        p.translate(self.middle)
        p.scale(beat, beat)
        p.translate(-self.middle.x(), -self.middle.y())
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if grow > 0:
            # The fill, from the middle out, its front a fine white line.
            front = _scaled(self.outline, self.middle, 0.04 + 0.98 * grow)
            p.save()
            p.setOpacity(p.opacity() * fade)
            if grow < 1:
                p.setClipPath(front)
            p.drawImage(self.box, self.fill)
            p.restore()
            if grow < 1:
                p.setBrush(Qt.NoBrush)
                for w, color, alpha in ((6, PINK, 0.2), (1.4, "#ffffff", 0.6)):
                    p.setPen(QPen(col(color, alpha * fade * (1 - grow)), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    p.drawPath(front)
        if lit > 0:
            # The line lights up as the lap closes: a flash, settling to a steady glow.
            flash = 1 + 0.5 * math.sin(math.pi * win(t, 2.4, 3.0))
            p.save()
            p.setOpacity(p.opacity() * clamp(lit * fade * 0.75 * flash))
            p.drawImage(self.box, self.line)
            p.restore()
        if lap > 0:
            done = lap * (len(self.curve) - 1)
            trail = [self._point(z) for z in self.curve[: int(done) + 1]]
            if lap < 1:
                trail.append(self._point(_chain(self.terms, lap * 2 * math.pi)[-1]))
            if len(trail) > 1:
                path = polyline(trail)
                p.setBrush(Qt.NoBrush)
                for w, color, alpha in ((14, ROSE, 0.1 * (1 - lit)), (7, PINK, 0.2 * (1 - lit)), (3, "#ffc4da", 0.7), (1.2, "#ffffff", 0.95)):
                    if alpha > 0.005:
                        p.setPen(QPen(col(color, alpha * fade), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                        p.drawPath(path)
        p.restore()
        # A line rippling away as it beats.
        ripple = win(t, 3.32, 4.1)
        if 0 < ripple < 1:
            ring = _scaled(self.outline, self.middle, 1 + 0.36 * ease_out(ripple))
            p.setBrush(Qt.NoBrush)
            for w, color, alpha in ((6, PINK, 0.16), (1.3, "#ffe0ec", 0.6)):
                p.setPen(QPen(col(color, alpha * (1 - ripple) * fade), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawPath(ring)
        self._epicycles(p, t, lap * 2 * math.pi)

    def _point(self, z: complex, k: float | None = None) -> QPointF:
        k = self.k if k is None else k
        return QPointF(self.origin.x() + z.real * k, self.origin.y() + z.imag * k)

    def _axes(self, p: QPainter, t: float, fade: float) -> None:
        """x and y axes through the series' origin, ticked every four units, numbered every eight
        and named; strong while the circles turn, then faint under the heart."""
        a = ease_out(win(t, 0.3, 0.8)) * (1 - 0.45 * ease_in_out(win(t, 2.5, 3.1))) * fade
        if a <= 0:
            return
        u, k, o = self.u, self.k, self.origin
        draw = ease_out(win(t, 0.3, 0.9))
        reach_x, up, down = 21 * k * draw, 16 * k * draw, 16 * k * draw
        p.setPen(QPen(col(CHALK, 0.5 * a), 1 * u))
        p.drawLine(QPointF(o.x() - reach_x, o.y()), QPointF(o.x() + reach_x, o.y()))
        p.drawLine(QPointF(o.x(), o.y() - up), QPointF(o.x(), o.y() + down))
        for i in range(-5, 6):
            if i == 0:
                continue
            tick = (4.5 if i % 2 == 0 else 2.5) * u
            x = o.x() + i * 4 * k
            if abs(i * 4 * k) < reach_x:
                p.drawLine(QPointF(x, o.y() - tick), QPointF(x, o.y() + tick))
            y = o.y() + i * 4 * k
            if -up < i * 4 * k < down:
                p.drawLine(QPointF(o.x() - tick, y), QPointF(o.x() + tick, y))
        # Arrowheads at the positive ends.
        p.setBrush(col(CHALK, 0.65 * a))
        p.setPen(Qt.NoPen)
        for tip, back in (
            (QPointF(o.x() + reach_x, o.y()), QPointF(-7 * u, 0)),
            (QPointF(o.x(), o.y() - up), QPointF(0, 7 * u)),
        ):
            side = QPointF(back.y() * 0.4, back.x() * 0.4)
            arrow = QPainterPath(tip)
            arrow.lineTo(tip + back + side)
            arrow.lineTo(tip + back - side)
            arrow.closeSubpath()
            p.drawPath(arrow)
        names = ease_out(win(t, 0.6, 1.1))
        if names > 0:
            p.setBrush(col(INK, 0.6 * a * names))
            for path, _at in self.labels:
                p.drawPath(path)

    def _epicycles(self, p: QPainter, t: float, s: float) -> None:
        """The chain of circles, each turning on the rim of the one before: thin chalk circles,
        white arms, a glowing pink tip, and dashed lines from it to both axes, where x(t) and y(t) are."""
        a = ease_out(win(t, 0.3, 0.75)) * (1 - ease_in_out(win(t, 2.45, 2.95)))
        if a <= 0:
            return
        u, k, o = self.u, self.k, self.origin
        grow = ease_out(win(t, 0.3, 0.75))
        chain = [self._point(z, k * grow) for z in _chain(self.terms, s)]
        tip = chain[-1]
        # The tip's x and y, dropped to the axes.
        p.setPen(QPen(col(PINK, 0.42 * a), 1 * u, Qt.DashLine))
        p.drawLine(tip, QPointF(tip.x(), o.y()))
        p.drawLine(tip, QPointF(o.x(), tip.y()))
        for foot in (QPointF(tip.x(), o.y()), QPointF(o.x(), tip.y())):
            soft_dot(p, foot.x(), foot.y(), 9 * u, PINK, 0.55 * a)
            soft_dot(p, foot.x(), foot.y(), 2.4 * u, "#ffffff", 0.85 * a)
        p.setBrush(Qt.NoBrush)
        for (_turns, c), centre in zip(self.terms, chain, strict=False):
            r = abs(c) * k * grow
            if r < 1.5 * u:
                continue
            for w, color, alpha in ((4.5, CHALK, 0.1), (1.1, CHALK, 0.55)):
                p.setPen(QPen(col(color, alpha * a), w * u))
                p.drawEllipse(centre, r, r)
        arms = polyline(chain)
        for w, color, alpha in ((4, CHALK, 0.18), (1.4, INK, 0.9)):
            p.setPen(QPen(col(color, alpha * a), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(arms)
        p.setPen(Qt.NoPen)
        for centre in chain[:-1]:
            p.setBrush(col(INK, 0.9 * a))
            p.drawEllipse(centre, 2.1 * u, 2.1 * u)
        soft_dot(p, tip.x(), tip.y(), 22 * u, PINK, 0.8 * a)
        soft_dot(p, tip.x(), tip.y(), 5 * u, "#ffffff", a)


def _polar(p: QPainter, t: float, origin: QPointF, s: float, u: float, fade: float) -> None:
    """A polar grid, and the cardioid r = 1 − sin θ plotting itself on it in gold: a point runs
    round, the radius out to it, and the curve left behind; then the point keeps going."""
    a = ease_out(win(t, 0.45, 1.0)) * fade
    if a <= 0:
        return
    p.setBrush(Qt.NoBrush)
    for i in range(1, 5):
        r = s * 0.5 * i
        p.setPen(QPen(col(CHALK, (0.3 if i % 2 == 0 else 0.16) * a), 0.9 * u))
        p.drawEllipse(origin, r, r)
    for i in range(12):
        angle = i * math.pi / 6
        p.setPen(QPen(col(CHALK, (0.3 if i % 3 == 0 else 0.14) * a), 0.9 * u))
        p.drawLine(origin, QPointF(origin.x() + math.cos(angle) * s * 2.15, origin.y() - math.sin(angle) * s * 2.15))

    def at(theta: float) -> QPointF:
        r = (1 - math.sin(theta)) * s
        return QPointF(origin.x() + r * math.cos(theta), origin.y() - r * math.sin(theta))

    plot = ease_in_out(win(t, 0.95, 2.6))
    if plot <= 0:
        return
    # From the bottom of the curve, θ = −π/2, round once.
    start = -math.pi / 2
    count = max(2, round(200 * plot))
    curve = polyline([at(start + 2 * math.pi * plot * i / (count - 1)) for i in range(count)])
    for w, color, alpha in ((7, GOLD, 0.16), (2.6, GOLD, 0.6), (1.1, "#fff6dc", 0.95)):
        p.setPen(QPen(col(color, alpha * a), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(curve)
    theta = start + 2 * math.pi * plot + (max(0.0, t - 2.6) * 1.6 if plot >= 1 else 0.0)
    point = at(theta)
    p.setPen(QPen(col("#fff6dc", 0.6 * a), 1.1 * u, Qt.DashLine))
    p.drawLine(origin, point)
    # The angle θ swept from the axis, as a small arc.
    sweep = math.degrees(theta) % 360
    p.setPen(QPen(col(GOLD, 0.55 * a), 1.1 * u))
    p.drawArc(QRectF(origin.x() - s * 0.3, origin.y() - s * 0.3, s * 0.6, s * 0.6), 0, round(sweep * 16))
    soft_dot(p, point.x(), point.y(), 16 * u, GOLD, 0.8 * a)
    soft_dot(p, point.x(), point.y(), 3.6 * u, "#ffffff", a)


def _spiral(rect: QRectF) -> list[tuple[QRectF, QPointF, float]]:
    """The Fibonacci tiling of a golden rectangle, largest square first: (square, the corner its
    quarter of the spiral turns about, the angle the quarter starts at going inward)."""
    out = []
    x, y, w, h = rect.left(), rect.top(), rect.width(), rect.height()
    for i in range(9):
        side = min(w, h)
        cut = i % 4
        if cut == 0:  # off the right; the spiral turns about its bottom left
            square = QRectF(x + w - side, y, side, side)
            pivot = square.bottomLeft()
            w -= side
        elif cut == 1:  # off the top; about its bottom right
            square = QRectF(x, y, side, side)
            pivot = square.bottomRight()
            y += side
            h -= side
        elif cut == 2:  # off the left; about its top right
            square = QRectF(x, y, side, side)
            pivot = square.topRight()
            x += side
            w -= side
        else:  # off the bottom; about its top left
            square = QRectF(x, y + h - side, side, side)
            pivot = square.topLeft()
            h -= side
        out.append((square, pivot, -cut * math.pi / 2))
    return out


def _spiral_paint(p: QPainter, t: float, tiles: list, u: float, fade: float) -> None:
    """The golden spiral growing out of its eye, a quarter turn a square, each square drawn as it
    reaches it, with its Fibonacci number in the largest."""
    grow = ease_in_out(win(t, 0.9, 3.0))
    if grow <= 0 or fade <= 0:
        return
    n = len(tiles)
    reached = grow * n
    numbers = ("21", "13", "8")
    p.setBrush(Qt.NoBrush)
    arc = []
    # From the smallest square out.
    for index in range(n - 1, -1, -1):
        square, pivot, angle = tiles[index]
        k = clamp(reached - (n - 1 - index))
        if k <= 0:
            break
        p.setPen(QPen(col(CHALK, 0.42 * fade * min(1.0, k * 3)), 1.0 * u))
        p.drawRect(square)
        if index < len(numbers) and k >= 1:
            font = _font(square.width() * 0.2)
            p.setFont(font)
            p.setPen(col(INK, 0.38 * fade))
            p.drawText(square, Qt.AlignCenter, numbers[index])
        r = square.width()
        # Outward the quarter runs from the angle a quarter turn on, back to the start.
        steps = 24
        for j in range(steps + 1):
            s = j / steps * k
            theta = angle - math.pi / 2 * (1 - s)
            arc.append(QPointF(pivot.x() + r * math.cos(theta), pivot.y() + r * math.sin(theta)))
    if len(arc) < 2:
        return
    path = polyline(arc)
    for w, color, alpha in ((8, GOLD, 0.14), (3, GOLD, 0.55), (1.2, "#fff6dc", 0.95)):
        p.setPen(QPen(col(color, alpha * fade), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
    if grow < 1:
        tip = arc[-1]
        soft_dot(p, tip.x(), tip.y(), 14 * u, GOLD, 0.8 * fade)


def _glyphs(u: float) -> dict[str, QImage]:
    """Each drifting symbol lit once in chalk, a soft glow round a fine core."""
    out = {}
    side = max(8, round(44 * u))
    font = _font(30 * u)
    for glyph in SYMBOLS:
        def draw(q: QPainter, glyph: str = glyph) -> None:
            q.setFont(font)
            q.setPen(Qt.white)
            q.drawText(QRectF(0, 0, side, side), Qt.AlignCenter, glyph)

        shape = mask(side, side, draw)
        light = (blur(shape, 2.5)[..., None] * 0.8 + (shape ** 1.2)[..., None] * 0.9) * rgb(CHALK)
        out[glyph] = glow(light.astype(np.float32))
    return out


def _drift(p: QPainter, t: float, drift: list[tuple], glyphs: dict, boxes: list[QRectF], u: float, a: float) -> None:
    """Symbols drifting up the sides and twinkling, dimmed where an equation is."""
    if a <= 0:
        return
    side = 44 * u
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for glyph, x, y0, speed, scale, phase, born in drift:
        y = y0 - speed * t
        on = ease_out(win(t, born, born + 0.6))
        twinkle = 0.55 + 0.45 * math.sin(t * 2.3 + phase)
        near = min((max(abs(x - box.center().x()) - box.width() / 2, abs(y - box.center().y()) - box.height() / 2) for box in boxes), default=99 * u)
        clear = clamp(near / (24 * u))
        alpha = 0.5 * a * on * twinkle * clear
        if alpha <= 0.01:
            continue
        p.setOpacity(alpha)
        r = side * scale
        p.drawImage(QRectF(x - r / 2, y - r / 2, r, r), glyphs[glyph])
    p.restore()


# The marks. Their still parts are worked out per pixel once for each size and screen sharpness, and
# laid on every frame under what moves.
_MADE: dict[tuple, object] = {}


def _ratio(p: QPainter) -> float:
    """Pixels per point where p draws, at least 1."""
    device = p.device()
    return max(1.0, device.devicePixelRatioF() if device is not None else 1.0)


def _made(key: tuple, build):  # noqa: ANN001, ANN202
    if key not in _MADE:
        if len(_MADE) > 24:
            _MADE.clear()
        _MADE[key] = build()
    return _MADE[key]


def _arrow(p: QPainter, tip: QPointF, toward: QPointF, length: float, color: str, alpha: float) -> None:
    """A slim drafting arrowhead at tip, pointing along toward (a unit vector)."""
    side = QPointF(-toward.y(), toward.x()) * (length * 0.3)
    back = tip - toward * length
    head = QPainterPath(tip)
    head.lineTo(back + side)
    head.lineTo(back - side)
    head.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(col(color, alpha))
    p.drawPath(head)


def _ring_lines(cover: QRectF) -> list[tuple[QPointF, QPointF, float]]:
    """The ring's drafting lines round cover: (from, to, strength). The button's edge, its edges
    run on past the corners as extension lines, a ruler of ticks along the top and the dimension
    lines down the sides and along the bottom."""
    left, top, right, bottom = cover.left() + 0.5, cover.top() + 0.5, cover.right() - 0.5, cover.bottom() - 0.5
    reach = 7.5
    out = [
        (QPointF(left - reach, top), QPointF(right + reach, top), 1.0),
        (QPointF(left - reach, bottom), QPointF(right + reach, bottom), 1.0),
        (QPointF(left, top - reach), QPointF(left, bottom + reach), 1.0),
        (QPointF(right, top - reach), QPointF(right, bottom + reach), 1.0),
        # The dimension lines, 4.5 points out.
        (QPointF(left - 4.5, top + 1), QPointF(left - 4.5, bottom - 1), 0.75),
        (QPointF(right + 4.5, top + 1), QPointF(right + 4.5, bottom - 1), 0.75),
        (QPointF(left + 1, bottom + 4.5), QPointF(right - 1, bottom + 4.5), 0.75),
    ]
    # The ruler: a tick every so often along the top, longer every fifth and tenth.
    count = max(10, round((right - left) / 5.5 / 10) * 10)
    for i in range(1, count):
        x = left + (right - left) * i / count
        length = 6.0 if i % 10 == 0 else 4.0 if i % 5 == 0 else 2.2
        out.append((QPointF(x, top), QPointF(x, top - length), 0.85 if i % 5 == 0 else 0.6))
    return out


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """The button drawn to scale: its edge in chalk with extension lines past the corners, a ruler
    along the top with a pink cursor sliding on it, dimension lines with arrowheads down the sides
    and along the bottom, a pulse running out along them to the arrowheads."""
    ratio = _ratio(p)
    window = cover.adjusted(-9, -9, 9, 9)
    lines = _ring_lines(cover)

    def build() -> QImage:
        w, h = max(1, round(window.width() * ratio)), max(1, round(window.height() * ratio))

        def draw(q: QPainter) -> None:
            q.scale(ratio, ratio)
            q.translate(-window.left(), -window.top())
            for a, b, strength in lines:
                q.setPen(QPen(col("#ffffff", strength), 1.25 if strength >= 1 else 1.0))
                q.drawLine(a, b)

        core = mask(w, h, draw)
        image = bloom(core, CHALK, ((1.5 * ratio, 0.95), (4 * ratio, 0.6)), white=0.6)
        image.setDevicePixelRatio(ratio)
        return image

    still = _made(("ring", window.width(), window.height(), ratio), build)
    p.drawImage(window.topLeft(), still)
    left, top, right, bottom = cover.left() + 0.5, cover.top() + 0.5, cover.right() - 0.5, cover.bottom() - 0.5
    # The arrowheads on the dimension lines, against the extension lines.
    for tip, toward in (
        (QPointF(left - 4.5, top + 0.6), QPointF(0, -1)),
        (QPointF(left - 4.5, bottom - 0.6), QPointF(0, 1)),
        (QPointF(right + 4.5, top + 0.6), QPointF(0, -1)),
        (QPointF(right + 4.5, bottom - 0.6), QPointF(0, 1)),
        (QPointF(left + 0.6, bottom + 4.5), QPointF(-1, 0)),
        (QPointF(right - 0.6, bottom + 4.5), QPointF(1, 0)),
    ):
        _arrow(p, tip, toward, 5.5, "#cfefff", 0.95)
    # A pulse of light from each dimension line's middle out to its arrowheads, every 2.6 s.
    pulse = (t % 2.6) / 1.3
    if pulse < 1:
        k = ease_in_out(pulse)
        a = math.sin(math.pi * pulse)
        mid_x, mid_y = cover.center().x(), cover.center().y()
        half_w, half_h = (right - left) / 2, (bottom - top) / 2
        for x, y in (
            (mid_x - half_w * k, bottom + 4.5),
            (mid_x + half_w * k, bottom + 4.5),
            (left - 4.5, mid_y - half_h * k),
            (left - 4.5, mid_y + half_h * k),
            (right + 4.5, mid_y - half_h * k),
            (right + 4.5, mid_y + half_h * k),
        ):
            soft_dot(p, x, y, 6, CHALK, 0.7 * a)
            soft_dot(p, x, y, 1.6, "#ffffff", 0.9 * a)
    # The cursor sliding to and fro along the ruler, easing at each end.
    swing = (t / 3.4) % 2
    k = ease_in_out(swing if swing < 1 else 2 - swing)
    x = left + 10 + (right - left - 20) * k
    p.setPen(QPen(col(PINK, 0.85), 1.0))
    p.drawLine(QPointF(x, top - 7.5), QPointF(x, top + 3.5))
    soft_dot(p, x, top - 1, 9, PINK, 0.6)
    _arrow(p, QPointF(x, top - 3.2), QPointF(0, 1), 4.2, "#ffd6e6", 1.0)
    soft_dot(p, x, top, 1.8, "#ffffff", 0.95)


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """An enamel dial with ∞ on it: navy glass lit from the upper left, faint graph lines, ticks
    round a chalk rim, and the lemniscate glowing pink, a point of light running round it."""
    ratio = _ratio(p)
    side = box.width()
    window = box.adjusted(-9, -9, 9, 9)
    curve = _lemniscate(box.center(), side * 0.36, 160)

    def build() -> QImage:
        w, h = max(1, round(window.width() * ratio)), max(1, round(window.height() * ratio))
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = (box.center().x() - window.left()) * ratio, (box.center().y() - window.top()) * ratio
        radius = (side / 2 - 0.8) * ratio
        d = np.hypot(xs + 0.5 - cx, ys + 0.5 - cy) / radius
        disc = np.clip((1 - d) * radius + 0.5, 0, 1)
        # Enamel: lighter up and to the left, darkening into the rim, a soft bounce low on the right.
        lx, ly = (xs + 0.5 - cx) / radius, (ys + 0.5 - cy) / radius
        light = np.clip(0.55 - 0.45 * (lx * 0.6 + ly * 0.8), 0, 1)
        shade = np.clip(1 - d ** 3 * 0.55, 0, 1)
        color = (rgb("#0a1b33")[None, None] * (1 - light)[..., None] + rgb("#1d4a7c")[None, None] * light[..., None]) * shade[..., None]
        color += rgb("#3d7fb8")[None, None] * (np.exp(-((lx - 0.45) ** 2 + (ly - 0.55) ** 2) / 0.08) * 0.25)[..., None]

        def lines(q: QPainter) -> None:
            q.scale(ratio, ratio)
            q.translate(-window.left(), -window.top())
            step = side / 8
            q.setPen(QPen(Qt.white, 0.6))
            for i in range(-4, 5):
                q.drawLine(QPointF(box.left(), box.center().y() + i * step), QPointF(box.right(), box.center().y() + i * step))
                q.drawLine(QPointF(box.center().x() + i * step, box.top()), QPointF(box.center().x() + i * step, box.bottom()))

        def dial(q: QPainter) -> None:
            q.scale(ratio, ratio)
            q.translate(-window.left(), -window.top())
            c, r = box.center(), side / 2 - 0.8
            q.setPen(QPen(Qt.white, 1.2))
            q.setBrush(Qt.NoBrush)
            q.drawEllipse(c, r, r)
            q.setPen(QPen(col("#ffffff", 0.7), 0.8))
            q.drawEllipse(c, r * 0.84, r * 0.84)
            for i in range(24):
                angle = i * math.pi / 12
                inner = r * (0.86 if i % 6 == 0 else 0.91)
                q.setPen(QPen(col("#ffffff", 1.0 if i % 6 == 0 else 0.7), 0.9))
                q.drawLine(QPointF(c.x() + math.cos(angle) * inner, c.y() + math.sin(angle) * inner), QPointF(c.x() + math.cos(angle) * r * 0.97, c.y() + math.sin(angle) * r * 0.97))

        def infinity(q: QPainter) -> None:
            q.scale(ratio, ratio)
            q.translate(-window.left(), -window.top())
            q.setPen(QPen(Qt.white, side * 0.05, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.drawPath(polyline(curve))

        grid = mask(w, h, lines) * np.clip(1.2 - d, 0, 1)
        rim = mask(w, h, dial)
        color += rgb(CHALK)[None, None] * (grid * 0.2 + rim * 0.85)[..., None]
        sign = mask(w, h, infinity)
        halo = blur(sign, 2.2 * ratio) * 0.9 + blur(sign, 5 * ratio) * 0.5
        color = color * (1 - np.clip(halo, 0, 1) * 0.3)[..., None] + rgb(PINK)[None, None] * halo[..., None]
        # A chalk-blue glow round the dial, out into the window's margin.
        outside = np.clip(blur(disc, 4 * ratio) * 0.5 + blur(rim, 2 * ratio) * 0.45, 0, 1) * (1 - disc)
        alpha = np.clip(disc + outside, 0, 1)
        color = (color * disc[..., None] + rgb(CHALK)[None, None] * outside[..., None]) / np.maximum(alpha, 1e-4)[..., None]
        image = picture(color, alpha)
        image.setDevicePixelRatio(ratio)
        return image

    still = _made(("badge", side, ratio), build)
    p.drawImage(window.topLeft(), still)
    # The sign itself, crisp at any sharpness.
    path = polyline(curve)
    p.setBrush(Qt.NoBrush)
    for w, color, alpha in ((side * 0.06, PINK, 0.85), (side * 0.024, "#ffe3ee", 0.9)):
        p.setPen(QPen(col(color, alpha), w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
    # A point of light running round it, a fading trail behind.
    n = len(curve) - 1
    head = (t / 2.8 % 1) * n
    trail = 26
    for j in range(trail):
        a0, a1 = head - j - 1, head - j
        i0, i1 = int(math.floor(a0)) % n, int(math.floor(a1)) % n
        k = 1 - j / trail
        p.setPen(QPen(col("#ffffff", 0.9 * k * k), side * 0.05 * (0.4 + 0.6 * k), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(curve[i0], curve[i1])
    i = int(head) % n
    f = head - int(head)
    a, b = curve[i], curve[i + 1]
    dot = QPointF(a.x() + (b.x() - a.x()) * f, a.y() + (b.y() - a.y()) * f)
    soft_dot(p, dot.x(), dot.y(), side * 0.2, "#ffd6e6", 0.85)
    soft_dot(p, dot.x(), dot.y(), side * 0.05, "#ffffff", 1.0)


def _lemniscate(centre: QPointF, reach: float, count: int) -> list[QPointF]:
    """Bernoulli's lemniscate, ∞, reach from its middle to either end, as count + 1 points round it."""
    out = []
    for i in range(count + 1):
        s = 2 * math.pi * i / count
        q = 1 + math.sin(s) ** 2
        out.append(QPointF(centre.x() + reach * math.cos(s) / q, centre.y() + reach * math.sin(s) * math.cos(s) / q))
    return out


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """Blueprint paper: navy, mottled, a fine chalk grid, its left and bottom edges ticked as axes,
    a chalk border, and { 心动 } on the top edge, the border broken round it, its 心动 breathing."""
    ratio = _ratio(p)
    body = rect.adjusted(0, CARD_TOP, 0, 0)
    head = _heading(min(14.0, max(10.0, body.height() * 0.22)))

    def build() -> QImage:
        w, h = max(1, math.ceil(rect.width() * ratio)), max(1, math.ceil(rect.height() * ratio))
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        top = CARD_TOP * ratio
        down = np.clip((ys - top) / max(1.0, h - top), 0, 1)
        paper_ = rgb(LOOK["card"][0])[None, None] * (1 - down)[..., None] + rgb(LOOK["card"][1])[None, None] * down[..., None]
        # Mottled like printed paper, a little light in the upper left, darker at the edges.
        grain = noise(w, h, 9 * ratio, 3, 7) - 0.5
        lx, ly = xs / max(1, w), (ys - top) / max(1.0, h - top)
        lift = np.exp(-((lx - 0.2) ** 2 / 0.18 + (ly - 0.1) ** 2 / 0.5)) * 0.07
        edge = np.minimum(np.minimum(lx, 1 - lx) * w, np.minimum(ly * (h - top), (1 - ly) * (h - top))) / ratio
        paper_ = paper_ * (1 + grain[..., None] * 0.14) + lift[..., None] - (np.exp(-edge / 6) * 0.05)[..., None]
        sheet = QRectF(0.5, CARD_TOP + 0.5, rect.width() - 1, rect.height() - CARD_TOP - 1)

        def shape(q: QPainter) -> None:
            q.scale(ratio, ratio)
            q.setPen(Qt.NoPen)
            q.setBrush(Qt.white)
            q.drawRoundedRect(sheet.adjusted(-0.5, -0.5, 0.5, 0.5), 2.5, 2.5)

        def grid(q: QPainter) -> None:
            q.scale(ratio, ratio)
            step = 6.0
            for i in range(int(rect.width() / step) + 2):
                q.setPen(QPen(col("#ffffff", 1.0 if i % 5 == 0 else 0.45), 0.5))
                q.drawLine(QPointF(sheet.left() + i * step, sheet.top()), QPointF(sheet.left() + i * step, sheet.bottom()))
            for i in range(int(sheet.height() / step) + 2):
                q.setPen(QPen(col("#ffffff", 1.0 if i % 5 == 0 else 0.45), 0.5))
                q.drawLine(QPointF(sheet.left(), sheet.bottom() - i * step), QPointF(sheet.right(), sheet.bottom() - i * step))

        def border(q: QPainter) -> None:
            q.scale(ratio, ratio)
            q.setPen(QPen(Qt.white, 1.0))
            q.setBrush(Qt.NoBrush)
            q.drawRoundedRect(sheet, 2.5, 2.5)
            # Ticks in from the left and bottom edges, as on a plot's axes.
            q.setPen(QPen(col("#ffffff", 0.8), 0.8))
            step = 6.0
            for i in range(1, int(sheet.height() / step)):
                y = sheet.bottom() - i * step
                if y > sheet.top() + 3:
                    q.drawLine(QPointF(sheet.left(), y), QPointF(sheet.left() + (3.2 if i % 5 == 0 else 1.8), y))
            for i in range(1, int(sheet.width() / step)):
                x = sheet.left() + i * step
                q.drawLine(QPointF(x, sheet.bottom()), QPointF(x, sheet.bottom() - (3.2 if i % 5 == 0 else 1.8)))
            # The border broken where the heading sits.
            gap = head.box.width() + 8
            q.setCompositionMode(QPainter.CompositionMode_Clear)
            q.fillRect(QRectF(rect.width() / 2 - gap / 2, sheet.top() - 2, gap, 4), Qt.black)

        within = mask(w, h, shape)
        lines = mask(w, h, grid) * within
        rim = mask(w, h, border)
        paper_ = paper_ + rgb(CHALK)[None, None] * (lines * 0.13 + rim * 0.75)[..., None]
        paper_ += rgb(CHALK)[None, None] * (blur(rim, 1.6 * ratio) * 0.35)[..., None]
        image = picture(paper_, np.clip(within * 0.95 + rim * 0.05, 0, 1))
        image.setDevicePixelRatio(ratio)
        return image

    still = _made(("card", rect.width(), rect.height(), ratio), build)
    p.drawImage(rect.topLeft(), still)
    # The heading on the top edge, its 心动 breathing.
    p.save()
    p.translate(rect.left() + rect.width() / 2 - head.box.width() / 2 - head.box.left(), rect.top() + CARD_TOP - head.box.center().y())
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    breathe = 0.75 + 0.25 * math.sin(t * 2 * math.pi / 3.6)
    p.setOpacity(p.opacity() * breathe)
    p.drawImage(head.glow_box, head.glow)
    p.setOpacity(1.0)
    p.setPen(Qt.NoPen)
    p.setBrush(col(INK, 0.95))
    p.drawPath(head.ink)
    p.setBrush(col(PINK, 1.0))
    p.drawPath(head.accent)
    p.restore()


@dataclass
class _Heading:
    """The card's { 心动 }: its braces (ink) and 心动 (accent) at the origin, and 心动's pink glow."""

    ink: QPainterPath
    accent: QPainterPath
    box: QRectF
    glow: QImage
    glow_box: QRectF


def _heading(px: float) -> _Heading:
    """{ 心动 }, px high, as paths at the origin, with its pink glow worked out once."""
    key = ("heading", round(px * 4))
    if key in _MADE:
        return _MADE[key]
    ink, accent = QPainterPath(), QPainterPath()
    math_font, han = _font(px * 1.25), _font(px * 1.08, han=True)
    x = 0.0
    for text, font, out in (("{ ", math_font, ink), ("心动", han, accent), (" }", math_font, ink)):
        out.addText(QPointF(x, 0), font, text)
        x += QFontMetricsF(font).horizontalAdvance(text)
    box = ink.boundingRect().united(accent.boundingRect())
    if box.isEmpty():
        box = QRectF(0, -px, max(1.0, x), px)
    ratio = 3.0
    glow_box = box.adjusted(-px * 0.5, -px * 0.5, px * 0.5, px * 0.5)
    w, h = max(1, round(glow_box.width() * ratio)), max(1, round(glow_box.height() * ratio))

    def draw(q: QPainter) -> None:
        q.scale(ratio, ratio)
        q.translate(-glow_box.left(), -glow_box.top())
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(accent)

    shape = mask(w, h, draw)
    halo = blur(shape, px * ratio * 0.12) * 0.8 + blur(shape, px * ratio * 0.35) * 0.5
    made = _Heading(ink, accent, box, glow(halo[..., None] * rgb(PINK)), glow_box)
    _MADE[key] = made
    return made


def lead(size: float, index: int) -> QPixmap:
    """A plotted point: fine chalk crosshairs and a glowing dot on them, pink and gold in turn."""
    app = QGuiApplication.instance()
    ratio = max(2.0, app.devicePixelRatio() if app is not None else 2.0)
    image = QPixmap(round(size * ratio), round(size * ratio))
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    c = size / 2
    tint = (PINK, GOLD)[index % 2]
    p.setPen(QPen(col(CHALK, 0.75), max(0.6, size * 0.05), Qt.SolidLine, Qt.FlatCap))
    reach, hole = size * 0.44, size * 0.2
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        p.drawLine(QPointF(c + dx * hole, c + dy * hole), QPointF(c + dx * reach, c + dy * reach))
    soft_dot(p, c, c, size * 0.34, tint, 0.55)
    p.setPen(QPen(col("#ffffff", 0.85), max(0.5, size * 0.04)))
    p.setBrush(col(tint))
    p.drawEllipse(QPointF(c, c), size * 0.12, size * 0.12)
    soft_dot(p, c - size * 0.03, c - size * 0.03, size * 0.07, "#ffffff", 0.95)
    p.end()
    return image
