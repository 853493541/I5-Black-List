"""数学 Equation: a blueprint night where the heart is worked out, not drawn.

The edges darken to blueprint navy with faint graph paper in them, fading toward the middle. In
the top right (every other scene's heart is in the top left) a chain of rotating circles, the
heart curve's own Fourier series (x = 16 sin³t, y = 13 cos t − 5 cos 2t − 2 cos 3t − cos 4t has
only eight terms), traces the heart in a glowing pink line while z(t) = Σ cₖ e^{ikt} writes itself
above it. The circles fade, the heart fills with light from the middle out, and inside it the
level lines of (x²+y²−1)³ − x²y³ glow and flow outward, past its edge in chalk blue; it beats once
and a level line ripples away. Equations write themselves in chalk down the left side and in the
corners, a cardioid r = 1 − sin θ plots itself in gold on a polar grid in the top left, and a
golden spiral grows through its Fibonacci squares in the bottom right. Math symbols drift up the
sides. At the end the equations crumble into chalk dust and everything fades.
"""

from __future__ import annotations

import cmath
import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QRadialGradient, QTransform

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
from blacklist_detect.love_scenes.light import blur, glow, mask, rgb, smooth

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
# The heart's level lines flow outward through this many steps, each drawn once.
PHASES = 8
SYMBOLS = "πΣ∞√θ∫φ∂Δ"


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(23)
    # The heart in the top right, unlike the other scenes; the polar plot takes the top left.
    heart_at = QPointF(width * 0.88, height * 0.172)
    size = 172 * u
    terms = _terms()
    paper = Wash(lambda q, w, h: _paper(q, w, h, u))
    formulas = [
        # z(t) = Σ cₖ e^{ikt}, the sum the circles add up, over the heart in the corner.
        _formula([("t", _it("z") + "(" + _it("t") + ") = "), ("big", "∑"), ("under", _it("k")), ("t", " " + _it("c")), ("sub", _it("k")), ("t", " " + _it("e")), ("sup", _it("ikt"))], 28 * u, QPointF(width - 24 * u, 50 * u), 0.35, 1.2, CHALK, rnd, ends=True),
        # The heart's own equation to its left as it fills, low by its narrowing point, short of the title.
        _formula([("t", "(" + _it("x") + "² + " + _it("y") + "² − 1)³ = " + _it("x") + "²" + _it("y") + "³")], 26 * u, QPointF(heart_at.x() - 62 * u, height * 0.255), 2.5, 3.3, PINK, rnd, ends=True),
        _formula([("t", _it("e")), ("sup", _it("iπ")), ("t", " + 1 = 0")], 30 * u, QPointF(24 * u, height * 0.44), 0.9, 1.55, CHALK, rnd),
        _formula([("t", "∫"), ("sup", "∞"), ("sub", "−∞"), ("t", " " + _it("e")), ("sup", "−" + _it("x") + "²"), ("t", " d" + _it("x") + " = "), ("root", _it("π"))], 26 * u, QPointF(22 * u, height * 0.62), 1.75, 2.5, CHALK, rnd),
        _formula([("t", _it("r") + " = 1 − sin " + _it("θ"))], 27 * u, QPointF(width * 0.19, height * 0.085), 1.0, 1.6, GOLD, rnd),
        _formula([("t", _it("φ") + " = "), ("frac", "1 + √5", "2")], 28 * u, QPointF(width * 0.718, height * 0.91), 2.05, 2.7, GOLD, rnd),
        _formula([("t", "lim"), ("under", _it("t") + "→∞"), ("t", " "), ("han", "心动", True), ("t", "(" + _it("t") + ") = "), ("t", "∞", True)], 31 * u, QPointF(30 * u, height * 0.915), 2.85, 3.6, PINK, rnd),
    ]
    # Each crumbles to chalk dust in turn at the end, the last written last.
    for index, formula in enumerate(formulas):
        formula.leaves = 4.12 + 0.07 * index
    polar = (QPointF(width * 0.1, height * 0.12), 46 * u)
    golden = QRectF(width - 14 * u - 136 * u * PHI, height - 10 * u - 136 * u, 136 * u * PHI, 136 * u)
    spiral = _spiral(golden)
    glyphs = _glyphs(u)
    # Where the drifting symbols keep out of the way: the equations, the heart, the polar plot, the spiral.
    boxes = [formula.box.adjusted(-14 * u, -14 * u, 14 * u, 14 * u) for formula in formulas]
    boxes += [
        QRectF(heart_at.x() - 125 * u, 0, 250 * u, heart_at.y() + 115 * u),
        QRectF(polar[0].x() - 104 * u, 0, 208 * u, polar[0].y() + 104 * u),
        golden.adjusted(-10 * u, -10 * u, 0, 0),
    ]
    drift = []
    for i in range(22):
        left = i % 3 == 0
        x = (rnd.uniform(0.012, 0.1) if left else rnd.uniform(0.952, 0.988)) * width
        drift.append((rnd.choice(SYMBOLS), x, rnd.uniform(0.25, 1.05) * height, rnd.uniform(18, 34) * u, rnd.uniform(0.6, 1.1), rnd.uniform(0, 6.28), rnd.uniform(0.0, 1.2)))
    # The traced heart, one lap of the series, in heart units with y down.
    curve = [_chain(terms, 2 * math.pi * i / 240)[-1] for i in range(241)]
    # The heart's light, worked out per pixel a piece at a time on the first frames.
    fill: dict = {}

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.3, 5.0))
        p.save()
        p.setOpacity(life)
        paper.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.8)) * (1 - leave))
        _drift(p, t, drift, glyphs, boxes, u, (1 - leave) * ease_out(win(t, 0.2, 1.0)))
        _spiral_paint(p, t, spiral, u, 1 - leave)
        _polar(p, t, *polar, u, 1 - leave)
        _heart(p, t, heart_at, size, terms, curve, fill, u)
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
    """An equation in chalk: its letters (ink, and accent in its color), the glow round them drawn
    once, the chalk dust it crumbles into, and when it is written."""

    ink: QPainterPath
    accent: QPainterPath
    box: QRectF
    glow: QImage
    glow_box: QRectF
    motes: list[tuple]
    start: float
    end: float
    tint: str
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
                p.setBrush(col(self.tint, 0.98))
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


def _formula(items: list[tuple], px: float, at: QPointF, start: float, end: float, tint: str, rnd: random.Random, ends: bool = False) -> _Formula:
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
    box = ink.boundingRect().united(accent.boundingRect())
    if box.isEmpty():
        box = QRectF(at.x(), at.y() - px, max(1.0, x), px * 1.3)
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
    picture = glow(halo[..., None] * rgb(tint))
    # The chalk dust it crumbles into: specks from its own letters.
    ys, xs = np.nonzero(shape > 0.5)
    motes = []
    for i in rnd.sample(range(len(xs)), min(len(xs), 34)):
        x0 = glow_box.left() + (xs[i] + 0.5) / SOFT
        y0 = glow_box.top() + (ys[i] + 0.5) / SOFT
        motes.append((x0, y0, rnd.uniform(18, 46) * px / 26, rnd.uniform(-12, 12) * px / 26, rnd.uniform(0.7, 1.9) * px / 26, rnd.uniform(0, 0.45)))
    return _Formula(ink, accent, box, picture, glow_box, motes, start, end, tint)


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
    for x, y, r in ((0.88, 0.2, 300), (0.1, 0.14, 240)):
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


def _heart(p: QPainter, t: float, centre: QPointF, size: float, terms: list, curve: list[complex], fill: dict, u: float) -> None:
    """The epicycles trace the heart; their circles fade, it fills with its level lines from the
    middle out, beats once, and fades at the end."""
    k = size / 34
    # The series' own origin (heart_points draws the curve 2.5 units lower), and F's middle.
    origin = QPointF(centre.x(), centre.y() + 2.5 * k)
    middle = QPointF(centre.x(), centre.y() + 6.6 * k)
    fade = 1 - ease_in_out(win(t, 4.25, 4.85))
    if fade <= 0:
        return
    density = _density(p)
    px = max(16, round(k * density * 8))
    if fill.get("px") != px:
        fill.clear()
        fill["px"] = px
    # The fill: from the middle out, on past the edge to the chalk level lines round it.
    grow = ease_out(win(t, 2.45, 3.25))
    _build(fill, size, density, grow > 0)
    lap = ease_in_out(win(t, 0.6, 2.45))
    beat = 1 + 0.07 * math.sin(math.pi * win(t, 3.3, 3.62))
    outline = heart_path(centre.x(), centre.y(), size)
    _axes(p, t, origin, k, u, fade)
    p.save()
    p.translate(middle)
    p.scale(beat, beat)
    p.translate(-middle.x(), -middle.y())
    reach = 0.05 + 1.4 * grow
    pieces = fill.get("done")
    if grow > 0 and pieces:
        body, lines, box = pieces
        box = box.translated(centre.x(), centre.y())
        front = _scaled(outline, middle, reach)
        p.save()
        p.setOpacity(p.opacity() * fade)
        if grow < 1:
            p.setClipPath(front)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(box, body)
        flow = (t * 0.55) % 1 * PHASES
        i, f = int(flow), flow - int(flow)
        base = p.opacity()
        p.setOpacity(base * (1 - f))
        p.drawImage(box, lines[i % PHASES])
        p.setOpacity(base * f)
        p.drawImage(box, lines[(i + 1) % PHASES])
        p.restore()
        edge = (1 - clamp((reach - 1) / 0.4)) * fade
        if grow < 1 and edge > 0:
            p.setBrush(Qt.NoBrush)
            for w, color, alpha in ((7, PINK, 0.25), (2, "#ffffff", 0.75)):
                p.setPen(QPen(col(color, alpha * edge), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawPath(front)
    # The trace: one lap of the series, the heart's line left behind the tip.
    if lap > 0:
        done = lap * (len(curve) - 1)
        trail = [_point(origin, k, z) for z in curve[: int(done) + 1]]
        if lap < 1:
            trail.append(_point(origin, k, _chain(terms, lap * 2 * math.pi)[-1]))
        if len(trail) > 1:
            path = polyline(trail)
            p.setBrush(Qt.NoBrush)
            for w, color, alpha in ((16, ROSE, 0.1), (8, PINK, 0.2), (3.2, "#ffc4da", 0.65), (1.3, "#ffffff", 0.95)):
                p.setPen(QPen(col(color, alpha * fade), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawPath(path)
    p.restore()
    # A level line rippling away as it beats.
    ripple = win(t, 3.32, 4.1)
    if 0 < ripple < 1:
        ring = _scaled(outline, middle, 1 + 0.38 * ease_out(ripple))
        p.setBrush(Qt.NoBrush)
        for w, color, alpha in ((6, CHALK, 0.18), (1.4, INK, 0.7)):
            p.setPen(QPen(col(color, alpha * (1 - ripple) * fade), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(ring)
    _epicycles(p, t, origin, k, terms, lap * 2 * math.pi, u)


def _axes(p: QPainter, t: float, origin: QPointF, k: float, u: float, fade: float) -> None:
    """Faint x and y axes through the series' origin, ticked every four units, there while the
    circles turn."""
    a = ease_out(win(t, 0.3, 0.8)) * (1 - ease_in_out(win(t, 2.5, 3.1))) * fade
    if a <= 0:
        return
    reach_x, up, down = 22 * k, 16 * k, 19 * k
    p.setPen(QPen(col(CHALK, 0.4 * a), 1 * u))
    p.drawLine(QPointF(origin.x() - reach_x, origin.y()), QPointF(origin.x() + reach_x, origin.y()))
    p.drawLine(QPointF(origin.x(), origin.y() - up), QPointF(origin.x(), origin.y() + down))
    for i in range(-5, 6):
        if i == 0:
            continue
        x = origin.x() + i * 4 * k
        if abs(i * 4 * k) < reach_x:
            p.drawLine(QPointF(x, origin.y() - 3 * u), QPointF(x, origin.y() + 3 * u))
        y = origin.y() + i * 4 * k
        if -up < i * 4 * k < down:
            p.drawLine(QPointF(origin.x() - 3 * u, y), QPointF(origin.x() + 3 * u, y))
    # Arrowheads at the positive ends.
    p.setBrush(col(CHALK, 0.5 * a))
    p.setPen(Qt.NoPen)
    for tip, back in (
        (QPointF(origin.x() + reach_x, origin.y()), QPointF(-7 * u, 0)),
        (QPointF(origin.x(), origin.y() - up), QPointF(0, 7 * u)),
    ):
        side = QPointF(back.y() * 0.45, back.x() * 0.45)
        arrow = QPainterPath(tip)
        arrow.lineTo(tip + back + side)
        arrow.lineTo(tip + back - side)
        arrow.closeSubpath()
        p.drawPath(arrow)


def _point(origin: QPointF, k: float, z: complex) -> QPointF:
    return QPointF(origin.x() + z.real * k, origin.y() + z.imag * k)


def _epicycles(p: QPainter, t: float, origin: QPointF, k: float, terms: list, s: float, u: float) -> None:
    """The chain of circles, each turning on the rim of the one before: thin chalk circles, white
    arms, a glowing pink tip."""
    a = ease_out(win(t, 0.3, 0.75)) * (1 - ease_in_out(win(t, 2.45, 2.95)))
    if a <= 0:
        return
    grow = ease_out(win(t, 0.3, 0.75))
    chain = [_point(origin, k * grow, z) for z in _chain(terms, s)]
    p.setBrush(Qt.NoBrush)
    for (_turns, c), centre in zip(terms, chain, strict=False):
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
    tip = chain[-1]
    soft_dot(p, tip.x(), tip.y(), 22 * u, PINK, 0.8 * a)
    soft_dot(p, tip.x(), tip.y(), 5 * u, "#ffffff", a)


def _scaled(path: QPainterPath, about: QPointF, scale: float) -> QPainterPath:
    return QTransform().translate(about.x(), about.y()).scale(scale, scale).translate(-about.x(), -about.y()).map(path)


def _density(p: QPainter) -> float:
    """Pixels per point where p draws: the screen's ratio and any scaling (the small preview)."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    m = p.worldTransform()
    return max(0.3, ratio * math.hypot(m.m11(), m.m12()))


def _build(fill: dict, size: float, density: float, now: bool) -> None:
    """One piece more of the heart's light, if it is not all made yet: first the level function
    and the body, then each step of the flowing lines. A piece a frame, while the circles turn, so
    no frame waits on all of it; all of it at once if it is wanted now (the scene shown part way)."""
    while "done" not in fill:
        if "field" not in fill:
            fill["field"] = _field(size, density)
            fill["lines"] = []
        else:
            field = fill["field"]
            fill["lines"].append(_lines(field, len(fill["lines"]) / PHASES))
            if len(fill["lines"]) == PHASES:
                fill["done"] = (field["body"], fill["lines"], field["box"])
                del fill["field"]
        if not now:
            return


def _field(size: float, density: float) -> dict:
    """The heart equation's level function over the heart and a little round it, per pixel.

    F(x, y) = (x²+y²−1)³ − x²y³ is negative inside its heart. Its heart is rounder than the traced
    one, so each pixel is first moved along the ray from the middle by how much farther the one
    heart's edge is than the other's there: F's zero line then runs along the traced edge and its
    other level lines nest inside and round it. v = ∛F runs −1 in the middle, 0 on the edge."""
    k = size / 34
    # Heart units, y up, as heart_points uses them; the box reaches five units past the heart.
    left, right, top, bottom = -21.0, 21.0, 17.0, -22.0
    w, h = max(8, round((right - left) * k * density)), max(8, round((top - bottom) * k * density))
    per = w / (right - left)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    hx = left + xs / per
    hy = top - ys / per
    # The traced heart's middle that F's middle (0, 0) goes to: their heights lined up.
    mid = -4.1
    s = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    cx = 16 * np.sin(s) ** 3
    cy = 13 * np.cos(s) - 5 * np.cos(2 * s) - 2 * np.cos(3 * s) - np.cos(4 * s) - mid
    order = np.argsort(np.arctan2(cy, cx))
    traced_angle, traced_r = np.arctan2(cy, cx)[order], np.hypot(cx, cy)[order]
    # How far F's own edge is along each ray: where F turns positive, between the samples either side.
    angles = np.linspace(-np.pi, np.pi, 361)
    reach = np.linspace(0, 1.6, 321)[:, None]
    ra, rb = reach * np.cos(angles), reach * np.sin(angles)
    on_ray = (ra * ra + rb * rb - 1) ** 3 - ra * ra * rb ** 3
    out = np.argmax(on_ray >= 0, axis=0)
    columns = np.arange(len(angles))
    before, after = on_ray[out - 1, columns], on_ray[out, columns]
    own_r = reach[out - 1, 0] + (reach[1, 0] - reach[0, 0]) * before / (before - after)
    dx, dy = hx, hy - mid
    theta = np.arctan2(dy, dx)
    ratio = np.interp(theta, angles, own_r) / np.interp(theta, traced_angle, traced_r, period=2 * np.pi)
    a = dx * ratio
    b = dy * ratio
    f = (a * a + b * b - 1) ** 3 - a * a * b ** 3
    v = np.cbrt(f).astype(np.float32)
    gy, gx = np.gradient(v)
    slope = np.hypot(gx, gy) + 1e-6
    # The traced heart's own shape, for what is inside it.
    box = QRectF(-21 * k, -(top - 2.5) * k, (right - left) * k, (top - bottom) * k)

    def draw(q: QPainter) -> None:
        q.scale(density, density)
        q.translate(-box.left(), -box.top())
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(heart_path(0, 0, size))

    within = mask(w, h, draw)
    # F dips again in each upper lobe, so its level lines there would close into small rings of
    # their own, which read as eyes. Below the saddle between a lobe and the middle, the lobe is
    # left as one smooth glow instead: its lines fade out and its light holds level.
    depth = np.clip(-v, 0, 1)
    lobe = np.where((hx > 3) & (hy > 2) & (v < 0), v, np.inf)
    basin = np.zeros_like(v)
    if np.isfinite(lobe.min()):
        row, column = np.unravel_index(np.argmin(lobe), v.shape)
        lobe_x, lobe_y = hx[row, column], hy[row, column]
        along = np.linspace(0, 1, 200)
        columns = np.clip(((along * lobe_x - left) * per).astype(int), 0, w - 1)
        rows = np.clip(((top - mid - along * (lobe_y - mid)) * per).astype(int), 0, h - 1)
        saddle = v[rows, columns].max()
        side = smooth(-1.5, 1.5, np.hypot(hx, hy - mid) - np.hypot(np.abs(hx) - lobe_x, hy - lobe_y))
        # The lines just above the saddle go too, or their arcs round the lobes read as brows.
        basin = side * smooth(-0.14, 0.06, saddle - v)
        depth = depth - side * np.clip(depth + saddle, 0, None)
    light = (
        rgb(ROSE)[None, None] * (0.42 * (1 - depth) ** 1.5)[..., None]
        + rgb(PINK)[None, None] * (0.62 * depth)[..., None]
        + rgb("#fff2f7")[None, None] * (0.75 * depth ** 5)[..., None]
    ) * within[..., None]
    halo = blur(within, 3 * density * k / 5) * (1 - within) * 0.25
    light += rgb(ROSE)[None, None] * halo[..., None]
    return {
        "v": v,
        "slope": slope,
        "within": within,
        "depth": depth,
        "basin": basin,
        "density": density,
        "body": glow(light.astype(np.float32)),
        "box": box,
    }


def _lines(field: dict, phase: float) -> QImage:
    """F's level lines, the same fine width wherever they run (however steep F is there), moved
    out by phase of the gap between them: pink-white inside the heart, chalk blue and fading round it."""
    v, slope, within, depth, density = field["v"], field["slope"], field["within"], field["depth"], field["density"]
    levels = 6
    q = v * levels - phase
    off = np.abs(q - np.round(q)) / (levels * slope)
    line = np.exp(-((off / (0.75 * density)) ** 2))
    inner = line * within * (1 - field["basin"]) * (0.45 + 0.55 * depth)
    outer = line * (1 - within) * np.exp(-np.clip(v, 0, None) * 3.2) * smooth(0.0, 0.05, v)
    light = rgb("#ffe0ec")[None, None] * inner[..., None] + rgb(CHALK)[None, None] * (outer * 0.7)[..., None]
    spread = 2.2 * density
    halo = rgb(PINK)[None, None] * blur(inner, spread)[..., None] + rgb(CHALK)[None, None] * (blur(outer, spread) * 0.7)[..., None]
    return glow((light + halo * 1.2).astype(np.float32))


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
