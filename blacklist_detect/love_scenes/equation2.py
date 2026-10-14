"""数学 trial 2, Geometry: Euclid's figures construct themselves on a blueprint night, with no heart.

The edges darken to blueprint navy with faint graph paper in them, fading toward the middle. In the top
left a drafting compass drawn in chalk opens, swings a circle, then walks round it as dividers do,
flipping over at each step and cutting five marks; a straightedge joins them into a pentagon and, in
one gold stroke, a pentagram, which fills with a quiet gold light while the pentagon inside it and the
smaller star inside that appear, the golden ratio over and over; φ = (1 + √5)/2 and AC : AB = φ write
themselves beside it. In the top right, Euclid's first proposition: two circles, each through the
other's centre, the vesica piscis between them lighting up and the equilateral triangle on AB drawn in
gold. Down the left a 3-4-5 right triangle unfolds its squares, of 9, 16 and 25 cells, over
a² + b² = c²; in the bottom corners a rose r = sin 4θ and a Lissajous figure plot themselves. The
symbols of geometry drift up the sides. At the end the equations crumble into chalk dust and
everything fades.

Its marks are drafting instruments: round 准备案件还原 a protractor (ruled ticks along its edges, a
degree scale at each corner where a gold needle sweeps, and a light running round), beside it φ on a
navy glass dial with a gold rim, and a blueprint card with a compass construction on its top edge and
a protractor arc in its corner, a small compass before each name. They move (MARKS_ANIMATED).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient, QTransform

from blacklist_detect.love_scenes.draw import (
    Wash,
    clamp,
    col,
    ease_in,
    ease_in_out,
    ease_out,
    gradient,
    lengths,
    point_at,
    polyline,
    soft_dot,
    win,
)
from blacklist_detect.love_scenes.light import blur, glow, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.5
CHALK = "#7fd8ff"
INK = "#eaf6ff"
NAVY = "#0f2440"
DEEP = "#06142a"
GOLD = "#f3cf7a"
GOLD_LIGHT = "#fff6dc"
GOLD_DEEP = "#b8893a"
PHI = (1 + 5 ** 0.5) / 2
LOOK = {
    "glow": (127, 216, 255),
    "rim": CHALK,
    "band": (CHALK, GOLD),
    "card": ("#112a4b", "#081a33"),
    "edge": "#5fb8e6",
    "ink": INK,
    "flowers": (("#f2fbff", "#9fe1ff", "#3fa9e0"), ("#fff8e6", GOLD, GOLD_DEEP)),
    "disc": ("#13304f", "#0a1a30"),
    "heart": ("#fff0c8", "#e0b050"),
    "deep": GOLD,
    "deep_glow": (243, 207, 122),
}
MARKS_ANIMATED = True
# Room on the card's top edge for its compass arc.
CARD_TOP = 16
# The equations' glow is soft: worked out at this share of the stage's size and laid on scaled up.
SOFT = 0.5
SYMBOLS = "△∠⊥∥≅∽πφ⊙"
# Lines as the scene draws them, (width, color, alpha) from the glow in to the core.
CHALK_LINE = ((5.0, CHALK, 0.12), (1.2, CHALK, 0.72))
INK_LINE = ((6.0, CHALK, 0.14), (2.4, CHALK, 0.4), (1.0, INK, 0.92))
GOLD_LINE = ((8.0, GOLD, 0.14), (3.0, GOLD, 0.5), (1.2, GOLD_LIGHT, 0.95))
# When everything goes: the equations crumble from here, the figures fade over the next while.
LEAVE = 4.45


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(31)
    paper = Wash(lambda q, w, h: _paper(q, w, h, u))
    hero = _Pentagram(QPointF(width * 0.105, height * 0.17), 98 * u, u)
    euclid = _Vesica(QPointF(width - 188 * u, height * 0.165), 78 * u, u)
    pythagoras = _Pythagoras(QPointF(69 * u, height * 0.34 + 119 * u), 17 * u, u)
    rose = _Rose(QPointF(82 * u, height - 82 * u), 56 * u, u)
    lissajous = _Lissajous(QPointF(width - 96 * u, height - 80 * u), 70 * u, 52 * u, u)
    formulas = [
        _formula([("t", _it("φ") + " = "), ("frac", "1 + √5", "2")], 28 * u, QPointF(width * 0.2, height * 0.115), 3.0, 3.6, GOLD, rnd),
        _formula([("t", _it("AC") + " ∶ " + _it("AB") + " = "), ("t", _it("φ"), True)], 25 * u, QPointF(width * 0.2, height * 0.215), 3.35, 3.95, GOLD, rnd),
        _formula([("t", _it("AB") + " = " + _it("BC") + " = " + _it("CA"))], 24 * u, QPointF(euclid.left - 16 * u, height * 0.2), 2.55, 3.2, GOLD, rnd, ends=True),
        _formula([("t", _it("a") + "² + " + _it("b") + "² = "), ("t", _it("c") + "²", True)], 30 * u, QPointF(18 * u, pythagoras.bottom + 50 * u), 2.85, 3.5, GOLD, rnd),
        _formula([("t", _it("r") + " = sin 4" + _it("θ"))], 26 * u, QPointF(width * 0.1, height * 0.895), 2.2, 2.8, GOLD, rnd),
        _formula([("t", _it("V") + " − " + _it("E") + " + " + _it("F") + " = 2")], 24 * u, QPointF(width * 0.1, height * 0.965), 3.2, 3.8, CHALK, rnd),
        _formula([("t", _it("x") + " = cos 3" + _it("t"))], 25 * u, QPointF(width - 182 * u, height * 0.885), 2.5, 3.0, CHALK, rnd, ends=True),
        _formula([("t", _it("y") + " = sin 2" + _it("t"))], 25 * u, QPointF(width - 182 * u, height * 0.955), 2.75, 3.25, CHALK, rnd, ends=True),
    ]
    # Each crumbles to chalk dust in turn at the end.
    for index, formula in enumerate(formulas):
        formula.leaves = LEAVE + 0.05 * index
    glyphs = _glyphs(u)
    # Where the drifting symbols keep out of the way: the equations and the figures.
    boxes = [formula.box.adjusted(-14 * u, -14 * u, 14 * u, 14 * u) for formula in formulas]
    boxes += [
        hero.box.adjusted(-20 * u, -20 * u, 20 * u, 20 * u),
        euclid.box.adjusted(-20 * u, -20 * u, 20 * u, 20 * u),
        pythagoras.box.adjusted(-20 * u, -20 * u, 20 * u, 20 * u),
        rose.box.adjusted(-10 * u, -10 * u, 10 * u, 10 * u),
        lissajous.box.adjusted(-10 * u, -10 * u, 10 * u, 10 * u),
    ]
    drift = []
    for i in range(18):
        left = i % 3 == 0
        x = (rnd.uniform(0.015, 0.1) if left else rnd.uniform(0.952, 0.988)) * width
        drift.append((rnd.choice(SYMBOLS), x, rnd.uniform(0.3, 1.05) * height, rnd.uniform(16, 30) * u, rnd.uniform(0.6, 1.0), rnd.uniform(0, 6.28), rnd.uniform(0.2, 1.4)))

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.3) * (1 - ease_in(win(t, DURATION - 0.3, DURATION)))
        fade = 1 - ease_in_out(win(t, LEAVE + 0.15, DURATION - 0.15))
        p.save()
        p.setOpacity(life)
        paper.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.8)) * (1 - ease_in(win(t, LEAVE, DURATION))))
        _drift(p, t, drift, glyphs, boxes, u, fade * ease_out(win(t, 0.2, 1.0)))
        rose.paint(p, t, fade)
        lissajous.paint(p, t, fade)
        pythagoras.paint(p, t, fade)
        euclid.paint(p, t, fade)
        hero.paint(p, t, fade)
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
        elif "A" <= ch <= "Z":
            out.append(chr(0x1D434 + ord(ch) - ord("A")))
        elif ch in "θπφ":
            out.append({"θ": "\U0001d703", "π": "\U0001d70b", "φ": "\U0001d711"}[ch])
        else:
            out.append(ch)
    return "".join(out)


def _font(px: float) -> QFont:
    font = QFont()
    font.setFamilies(["Cambria Math", "Cambria"])
    font.setPixelSize(max(1, round(px)))
    return font


def _on(centre: QPointF, r: float, angle: float) -> QPointF:
    """The point r from centre at angle, in radians clockwise from the right as the screen has it."""
    return QPointF(centre.x() + r * math.cos(angle), centre.y() + r * math.sin(angle))


def _lerp(a: QPointF, b: QPointF, k: float) -> QPointF:
    return QPointF(a.x() + (b.x() - a.x()) * k, a.y() + (b.y() - a.y()) * k)


def _stroke(p: QPainter, path: QPainterPath, layers: tuple, u: float, a: float) -> None:
    """A line drawn layer on layer, its glow first and its core last."""
    if a <= 0.005:
        return
    p.setBrush(Qt.NoBrush)
    for w, color, alpha in layers:
        p.setPen(QPen(col(color, alpha * a), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)


def _arc(centre: QPointF, r: float, start: float, sweep: float, steps: int = 96) -> list[QPointF]:
    count = max(2, round(steps * abs(sweep) / (2 * math.pi)) + 2)
    return [_on(centre, r, start + sweep * i / (count - 1)) for i in range(count)]


def _label(text: str, px: float, at: QPointF) -> QPainterPath:
    """A point's letter in math italic, centred on at."""
    path = QPainterPath()
    path.addText(QPointF(0, 0), _font(px), _it(text))
    box = path.boundingRect()
    return path.translated(at.x() - box.center().x(), at.y() - box.center().y()) if not box.isEmpty() else path


def _letters(p: QPainter, labels: list[QPainterPath], shown: list[float], a: float) -> None:
    p.setPen(Qt.NoPen)
    for path, k in zip(labels, shown, strict=True):
        if k > 0:
            p.setBrush(col(INK, 0.8 * k * a))
            p.drawPath(path)


def _point(p: QPainter, at: QPointF, u: float, a: float, pop: float = 1.0) -> None:
    """A construction point: a fine dot with a soft light, swelling a moment as it is found."""
    if a <= 0:
        return
    swell = 1 + 1.4 * math.sin(math.pi * clamp(pop)) if pop < 1 else 1
    soft_dot(p, at.x(), at.y(), 9 * u * swell, CHALK, 0.55 * a)
    p.setPen(Qt.NoPen)
    p.setBrush(col(INK, a))
    p.drawEllipse(at, 2.3 * u, 2.3 * u)


def _nib(p: QPainter, at: QPointF, u: float, color: str, a: float) -> None:
    """The light where a line is being drawn."""
    soft_dot(p, at.x(), at.y(), 16 * u, color, 0.6 * a)
    soft_dot(p, at.x(), at.y(), 4 * u, "#ffffff", 0.95 * a)


def _density(p: QPainter) -> float:
    """Pixels per point where p draws: the screen's ratio and any scaling (the small preview)."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    m = p.worldTransform()
    return max(0.3, ratio * math.hypot(m.m11(), m.m12()))


class _Still:
    """What a figure leaves once it is all drawn: painted once into a picture at the screen's
    sharpness and laid on every frame after, instead of stroking its lines again."""

    def __init__(self, box: QRectF) -> None:
        self.box = box
        self.image: QImage | None = None
        self.key = 0.0

    def paint(self, p: QPainter, alpha: float, draw) -> None:  # noqa: ANN001
        if alpha <= 0.005:
            return
        density = round(_density(p), 1)
        if self.image is None or density != self.key:
            w, h = max(1, round(self.box.width() * density)), max(1, round(self.box.height() * density))
            self.image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
            self.image.fill(Qt.transparent)
            q = QPainter(self.image)
            q.setRenderHint(QPainter.Antialiasing)
            q.scale(w / self.box.width(), h / self.box.height())
            q.translate(-self.box.left(), -self.box.top())
            draw(q)
            q.end()
            self.key = density
        p.save()
        p.setOpacity(p.opacity() * alpha)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(self.box, self.image)
        p.restore()


# The pentagram.


@dataclass
class _Pentagram:
    """The hero: a compass swings a circle about centre, walks five marks round it, and a pentagon
    and a pentagram are ruled through them; the star fills with gold light, its own pentagon and the
    smaller star inside appear, and a light runs along its stroke."""

    centre: QPointF
    r: float
    u: float
    light: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        c, r, u = self.centre, self.r, self.u
        self.box = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        # A at the top, then B to E clockwise.
        self.tips = [_on(c, r, -math.pi / 2 + i * 2 * math.pi / 5) for i in range(5)]
        inner = r * math.cos(2 * math.pi / 5) / math.cos(math.pi / 5)
        self.inner = [_on(c, inner, -math.pi / 2 + math.pi / 5 + i * 2 * math.pi / 5) for i in range(5)]
        # The small star inside the inner pentagon, and the pentagon inside that.
        self.small = [self.inner[(2 * i) % 5] for i in range(6)]
        self.core = [_on(c, inner * inner / r, -math.pi / 2 + i * 2 * math.pi / 5) for i in range(5)]
        self.side = 2 * r * math.sin(math.pi / 5)
        # The star in one stroke, A C E B D A.
        self.star = [self.tips[(2 * i) % 5] for i in range(6)]
        dense = []
        for a, b in zip(self.star, self.star[1:], strict=False):
            dense += [_lerp(a, b, j / 40) for j in range(40)]
        self.dense = [*dense, self.star[-1]]
        self.along = lengths(self.dense)
        self.outline = [point for pair in zip(self.tips, self.inner, strict=True) for point in pair]
        self.labels = [_label(letter, 17 * u, _on(c, r + 15 * u, -math.pi / 2 + i * 2 * math.pi / 5)) for i, letter in enumerate("ABCDE")]
        self.still = _Still(self.box.adjusted(-36 * u, -36 * u, 36 * u, 36 * u))

    # When each step is done: the compass opens, swings the circle, moves to A, then walks four steps.
    OPEN = (0.25, 0.55)
    CIRCLE = (0.55, 1.4)
    MOVE = (1.42, 1.62)
    STEP = 0.19
    LIFT = (2.4, 2.75)
    # From here on only the light running along the star moves.
    SETTLED = 4.1

    def _walked(self, t: float) -> int:
        """How many of the marks B to E, then A again, the compass has cut by t."""
        if t < self.MOVE[1]:
            return 0
        return 1 + min(4, int((t - self.MOVE[1]) / self.STEP))

    def paint(self, p: QPainter, t: float, fade: float) -> None:
        c, r = self.centre, self.r
        if fade <= 0:
            return
        soft_dot(p, c.x(), c.y(), 2.4 * r, "#2d6fa8", 0.3 * fade * ease_out(win(t, 0.2, 1.0)))
        if t >= 2.0:
            # The star's light is made now, while little else is drawn, ready for when it fills.
            self._light(p)
        if t >= self.SETTLED:
            self.still.paint(p, fade, lambda q: self._drawn(q, self.SETTLED, 1.0))
        else:
            self._drawn(p, t, fade)
            self._compass(p, t, fade)
        self._glint(p, t, fade)

    def _drawn(self, p: QPainter, t: float, fade: float) -> None:
        """All that is drawn by t but the compass and the running light."""
        u, c, r = self.u, self.centre, self.r
        sweep = ease_in_out(win(t, *self.CIRCLE))
        if sweep > 0:
            _stroke(p, polyline(_arc(c, r, -math.pi / 2, 2 * math.pi * sweep, 160)), CHALK_LINE, u, fade)
            if sweep < 1:
                # The chalk just laid, still bright behind the pencil.
                fresh = min(0.6, 2 * math.pi * sweep)
                _stroke(p, polyline(_arc(c, r, -math.pi / 2 + 2 * math.pi * sweep - fresh, fresh, 40)), ((3.5, CHALK, 0.25), (1.2, INK, 0.8)), u, fade)
        if t >= self.OPEN[0]:
            _point(p, c, u, fade * ease_out(win(t, *self.OPEN)), win(t, 0.25, 0.5))
        # The cuts the dividers leave: a short arc across each mark.
        for i in range(1, self._walked(t) + 1):
            pivot, mark = self.tips[i - 1], self.tips[i % 5]
            heading = math.atan2(mark.y() - pivot.y(), mark.x() - pivot.x())
            _stroke(p, polyline(_arc(pivot, self.side, heading - 0.13, 0.26, 12)), CHALK_LINE, u, fade * 0.9)
        shown = [ease_out(win(t, self.CIRCLE[1] - 0.1, self.CIRCLE[1] + 0.2))]
        shown += [ease_out(win(t, self.MOVE[1] + i * self.STEP - 0.05, self.MOVE[1] + i * self.STEP + 0.25)) for i in range(4)]
        for tip, k in zip(self.tips, shown, strict=True):
            if k > 0:
                _point(p, tip, u, fade * k, k)
        _letters(p, self.labels, shown, fade)
        self._ruled(p, t, fade)

    def _ruled(self, p: QPainter, t: float, fade: float) -> None:
        """The pentagon's sides, the star in one gold stroke, its light, and what is inside it."""
        u = self.u
        sides = ease_in_out(win(t, 2.3, 2.75))
        if sides > 0:
            path = QPainterPath()
            for a, b in zip(self.tips, self.tips[1:] + self.tips[:1], strict=True):
                path.moveTo(a)
                path.lineTo(_lerp(a, b, sides))
            _stroke(p, path, CHALK_LINE, u, fade * 0.8)
        fill = ease_out(win(t, 3.15, 3.8))
        if fill > 0:
            self._fill(p, fill, fade)
        stroke = ease_in_out(win(t, 2.55, 3.35))
        if stroke <= 0:
            return
        done = stroke * self.along[-1]
        end, _heading = point_at(self.dense, self.along, done)
        trail = [point for point, at in zip(self.dense, self.along, strict=True) if at < done] + [end]
        _stroke(p, polyline(trail), GOLD_LINE, u, fade)
        if stroke < 1:
            _nib(p, end, u, GOLD, fade)
        # Inside: its own pentagon in chalk, the small star in gold, the pentagon in that.
        inside = ease_out(win(t, 3.35, 3.8))
        if inside > 0:
            _stroke(p, polyline([*self.inner, self.inner[0]]), ((3.0, CHALK, 0.15), (0.9, INK, 0.6)), u, fade * inside)
            small = ease_in_out(win(t, 3.45, 3.9))
            if small > 0:
                along = lengths(self.small)
                done = small * along[-1]
                end, _heading = point_at(self.small, along, done)
                trail = [point for point, at in zip(self.small, along, strict=True) if at < done] + [end]
                _stroke(p, polyline(trail), ((4.0, GOLD, 0.16), (0.9, GOLD_LIGHT, 0.8)), u, fade)
            core = ease_out(win(t, 3.75, 4.05))
            if core > 0:
                _stroke(p, polyline([*self.core, self.core[0]]), ((0.8, INK, 0.55),), u, fade * core)

    def _glint(self, p: QPainter, t: float, fade: float) -> None:
        """Once the star is drawn, a light runs along it again and again, the way it was drawn."""
        run = t - 3.45
        if run <= 0:
            return
        length = self.along[-1]
        head = (run * 0.62 % 1) * length * 1.3
        tail = head - length * 0.12
        if tail >= length:
            return
        part = [point for point, at in zip(self.dense, self.along, strict=True) if tail < at < min(head, length)]
        if len(part) > 1:
            _stroke(p, polyline(part), ((6.0, GOLD_LIGHT, 0.22), (1.8, "#ffffff", 0.7)), self.u, fade * ease_out(win(t, 3.45, 3.7)))
        if head < length:
            spot, _heading = point_at(self.dense, self.along, head)
            soft_dot(p, spot.x(), spot.y(), 10 * self.u, GOLD_LIGHT, 0.7 * fade)

    def _light(self, p: QPainter) -> tuple[QImage, QRectF]:
        """The star's light per pixel, made for where p draws."""
        density = round(_density(p), 1)
        if self.light.get("key") != density:
            # Soft light needs fewer pixels than the screen has; the gold lines drawn over it are sharp.
            self.light = {"key": density, "image": _star_light(self.outline, self.centre, self.r, density * 0.7, self.u)}
        return self.light["image"]

    def _fill(self, p: QPainter, grow: float, fade: float) -> None:
        """The star's light, from its middle out."""
        image, box = self._light(p)
        p.save()
        if grow < 1:
            front = QPainterPath()
            front.addEllipse(self.centre, self.r * 1.3 * grow, self.r * 1.3 * grow)
            p.setClipPath(front)
        p.setOpacity(p.opacity() * fade)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(box, image)
        p.restore()

    def _compass(self, p: QPainter, t: float, fade: float) -> None:
        """The compass where it is at t: on the centre, opening and swinging the circle; moved onto
        A and opened to the side; then walking from mark to mark, flipping over each time."""
        if t < self.OPEN[0] or t > self.LIFT[1]:
            return
        c, r = self.centre, self.r
        top = -math.pi / 2
        bend = 1.0
        if t < self.CIRCLE[0]:
            needle, tip = c, _on(c, r * ease_out(win(t, *self.OPEN)), top)
        elif t < self.MOVE[0]:
            needle, tip = c, _on(c, r, top + 2 * math.pi * ease_in_out(win(t, *self.CIRCLE)))
        elif t < self.MOVE[1]:
            k = ease_in_out(win(t, *self.MOVE))
            needle, tip = _lerp(c, self.tips[0], k), _lerp(self.tips[0], self.tips[1], k)
        else:
            step = min(3, int((t - self.MOVE[1]) / self.STEP))
            k = ease_in_out(win(t - self.MOVE[1] - step * self.STEP, 0, self.STEP))
            pivot = self.tips[step + 1]
            before, after = self.tips[step], self.tips[(step + 2) % 5]
            a0 = math.atan2(before.y() - pivot.y(), before.x() - pivot.x())
            a1 = math.atan2(after.y() - pivot.y(), after.x() - pivot.x())
            turn = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
            needle, tip = pivot, _on(pivot, self.side, a0 + turn * k)
            # Dividers walk by turning over: seen from above, the hinge folds through the line of the legs.
            bend = -math.cos(math.pi * k)
        lift = ease_in(win(t, *self.LIFT))
        a = fade * ease_out(win(t, self.OPEN[0], self.OPEN[0] + 0.2)) * (1 - lift)
        drawing = 0.0
        if self.CIRCLE[0] < t < self.CIRCLE[1]:
            drawing = 1.0
        elif self.MOVE[1] < t < self.MOVE[1] + 4 * self.STEP:
            # Each step cuts as it lands.
            drawing = win((t - self.MOVE[1]) % self.STEP, self.STEP * 0.55, self.STEP * 0.85)
        p.save()
        if lift > 0:
            p.translate(0, -18 * self.u * lift)
        _compass(p, needle, tip, r * 0.74, bend, self.u, a, drawing)
        p.restore()


def _compass(p: QPainter, needle: QPointF, tip: QPointF, reach: float, bend: float, u: float, a: float, drawing: float) -> None:
    """A drafting compass in chalk line, its needle on needle and its pencil on tip, each leg reach
    long from the hinge; bend says which side of the legs the hinge is, and how far (0 lies flat)."""
    if a <= 0.01:
        return
    dx, dy = tip.x() - needle.x(), tip.y() - needle.y()
    d = math.hypot(dx, dy) or 1e-6
    rise = math.sqrt(max(reach * reach - d * d / 4, 0.0))
    nx, ny = dy / d, -dx / d
    mid = QPointF(needle.x() + dx / 2, needle.y() + dy / 2)
    hinge = QPointF(mid.x() + nx * rise * bend, mid.y() + ny * rise * bend)
    body, lines, bevel = QPainterPath(), QPainterPath(), QPainterPath()
    lead = QPainterPath()
    for foot, pencil in ((needle, False), (tip, True)):
        lx, ly = foot.x() - hinge.x(), foot.y() - hinge.y()
        length = math.hypot(lx, ly) or 1e-6
        ex, ey = lx / length, ly / length
        sx, sy = -ey, ex
        shoe = _lerp(hinge, foot, 0.8)
        leg = QPainterPath(QPointF(hinge.x() + sx * 4.4 * u, hinge.y() + sy * 4.4 * u))
        leg.lineTo(QPointF(shoe.x() + sx * 2.3 * u, shoe.y() + sy * 2.3 * u))
        leg.lineTo(QPointF(shoe.x() - sx * 2.3 * u, shoe.y() - sy * 2.3 * u))
        leg.lineTo(QPointF(hinge.x() - sx * 4.4 * u, hinge.y() - sy * 4.4 * u))
        leg.closeSubpath()
        body.addPath(leg)
        # The bevel down the leg, where it catches the light.
        bevel.moveTo(_lerp(hinge, foot, 0.12))
        bevel.lineTo(_lerp(hinge, foot, 0.76))
        # A collar where the point or the lead is held.
        collar = _lerp(hinge, foot, 0.85)
        lines.moveTo(QPointF(shoe.x() + sx * 3.0 * u, shoe.y() + sy * 3.0 * u))
        lines.lineTo(QPointF(collar.x() + sx * 3.0 * u, collar.y() + sy * 3.0 * u))
        lines.lineTo(QPointF(collar.x() - sx * 3.0 * u, collar.y() - sy * 3.0 * u))
        lines.lineTo(QPointF(shoe.x() - sx * 3.0 * u, shoe.y() - sy * 3.0 * u))
        lines.closeSubpath()
        if pencil:
            lead = QPainterPath(QPointF(collar.x() + sx * 2.0 * u, collar.y() + sy * 2.0 * u))
            lead.lineTo(foot)
            lead.lineTo(QPointF(collar.x() - sx * 2.0 * u, collar.y() - sy * 2.0 * u))
            lead.closeSubpath()
        else:
            lines.moveTo(collar)
            lines.lineTo(foot)
    # The handle above the hinge, foreshortened as the compass turns over.
    hx, hy = nx * bend, ny * bend
    grip = QPainterPath()
    if abs(bend) > 0.05:
        top = QPointF(hinge.x() + hx * 22 * u, hinge.y() + hy * 22 * u)
        grip.moveTo(QPointF(hinge.x() + ny * 3.0 * u, hinge.y() - nx * 3.0 * u))
        grip.lineTo(QPointF(top.x() + ny * 3.0 * u, top.y() - nx * 3.0 * u))
        grip.lineTo(QPointF(top.x() - ny * 3.0 * u, top.y() + nx * 3.0 * u))
        grip.lineTo(QPointF(hinge.x() - ny * 3.0 * u, hinge.y() + nx * 3.0 * u))
        grip.closeSubpath()
        for i in range(1, 5):
            knurl = QPointF(hinge.x() + hx * (8 + 3 * i) * u, hinge.y() + hy * (8 + 3 * i) * u)
            lines.moveTo(QPointF(knurl.x() + ny * 3.0 * u, knurl.y() - nx * 3.0 * u))
            lines.lineTo(QPointF(knurl.x() - ny * 3.0 * u, knurl.y() + nx * 3.0 * u))
    joint = QPainterPath()
    joint.addEllipse(hinge, 7.5 * u, 7.5 * u)
    p.setPen(Qt.NoPen)
    p.setBrush(col(NAVY, 0.8 * a))
    for part in (body, grip, joint):
        p.drawPath(part)
    outline = QPainterPath()
    for part in (body, grip, joint, lines):
        outline.addPath(part)
    _stroke(p, outline, ((6.0, CHALK, 0.14), (1.2, INK, 0.9)), u, a)
    _stroke(p, bevel, ((0.9, CHALK, 0.5),), u, a)
    p.setPen(QPen(col(CHALK, 0.6 * a), 0.9 * u))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(hinge, 4.2 * u, 4.2 * u)
    p.setPen(Qt.NoPen)
    p.setBrush(col(INK, 0.95 * a))
    p.drawEllipse(hinge, 1.8 * u, 1.8 * u)
    p.setBrush(col(GOLD, 0.95 * a))
    p.drawPath(lead)
    soft_dot(p, tip.x(), tip.y(), (8 + 10 * drawing) * u, GOLD, (0.35 + 0.5 * drawing) * a)
    soft_dot(p, needle.x(), needle.y(), 7 * u, CHALK, 0.5 * a)


def _star_light(outline: list[QPointF], centre: QPointF, r: float, density: float, u: float) -> tuple[QImage, QRectF]:
    """The pentagram's light per pixel: gold, faceted a little as if raised along its arms and lit
    from the upper left, brightest in its middle, a finer line along its edge and a halo round it."""
    reach = r * 1.22
    box = QRectF(centre.x() - reach, centre.y() - reach, 2 * reach, 2 * reach)
    n = max(8, round(2 * reach * density))
    per = n / (2 * reach)

    def draw(q: QPainter) -> None:
        q.scale(per, per)
        q.translate(-box.left(), -box.top())
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPolygon(outline)

    inside = mask(n, n, draw)
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32) + 0.5
    px, py = xs / per - reach, ys / per - reach
    angle = np.arctan2(py, px)
    distance = np.hypot(px, py) / r
    # Ten facets, each between an arm's ridge and the notch beside it; each tilts out across its edge.
    facet = np.floor(((angle + np.pi / 2) % (2 * np.pi)) / (np.pi / 5)).astype(int) % 10
    normals = []
    for j in range(10):
        a, b = outline[j], outline[(j + 1) % 10]
        ex, ey = b.x() - a.x(), b.y() - a.y()
        nx, ny = ey, -ex
        mx, my = (a.x() + b.x()) / 2 - centre.x(), (a.y() + b.y()) / 2 - centre.y()
        if nx * mx + ny * my < 0:
            nx, ny = -nx, -ny
        normals.append(math.atan2(ny, nx))
    lit = np.cos(np.array(normals, dtype=np.float32)[facet] + 3 * np.pi / 4)
    shade = 0.86 + 0.14 * lit
    centre_light = np.clip(1 - distance, 0, 1)
    body = inside * (0.2 + 0.42 * centre_light ** 1.4) * shade
    edge = np.clip(inside - blur(inside, 1.4 * density), 0, 1) * 1.6
    halo = blur(inside, 7 * density * u) * (1 - inside) * 0.38
    light = rgb(GOLD)[None, None] * (body + halo)[..., None] + rgb(GOLD_LIGHT)[None, None] * (edge * 0.8 + inside * centre_light ** 4 * 0.5)[..., None]
    return glow(light.astype(np.float32)), box


# Euclid I.1.


@dataclass
class _Vesica:
    """Euclid's first proposition about centre: A and B, the circle about each through the other,
    the vesica piscis they share lighting up, and the equilateral triangle ABC on AB in gold."""

    centre: QPointF
    d: float
    u: float
    light: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        c, d, u = self.centre, self.d, self.u
        self.a = QPointF(c.x() - d / 2, c.y())
        self.b = QPointF(c.x() + d / 2, c.y())
        self.c = QPointF(c.x(), c.y() - d * math.sqrt(3) / 2)
        self.d_point = QPointF(c.x(), c.y() + d * math.sqrt(3) / 2)
        self.left = c.x() - 1.5 * d
        self.box = QRectF(c.x() - 1.5 * d, c.y() - d, 3 * d, 2 * d)
        # The vesica's edge, down B's circle on the left and up A's on the right, from C.
        self.edge = _arc(self.b, d, -2 * math.pi / 3, -2 * math.pi / 3, 40) + _arc(self.a, d, math.pi / 3, -2 * math.pi / 3, 40)
        self.along = lengths(self.edge)
        self.labels = [
            _label("A", 17 * u, QPointF(self.a.x() - 10 * u, self.a.y() + 14 * u)),
            _label("B", 17 * u, QPointF(self.b.x() + 10 * u, self.b.y() + 14 * u)),
            _label("C", 17 * u, QPointF(self.c.x(), self.c.y() - 14 * u)),
            _label("D", 17 * u, QPointF(self.d_point.x(), self.d_point.y() + 15 * u)),
        ]
        self.still = _Still(self.box.adjusted(-24 * u, -24 * u, 24 * u, 24 * u))

    TRACE = (0.95, 2.0)
    # From here on only the light running round the vesica moves.
    SETTLED = 3.0

    def paint(self, p: QPainter, t: float, fade: float) -> None:
        u = self.u
        if fade <= 0 or t < 0.5:
            return
        soft_dot(p, self.centre.x(), self.centre.y(), 2.2 * self.d, "#2d6fa8", 0.28 * fade * ease_out(win(t, 0.5, 1.3)))
        if t >= 1.0:
            # The lens's light is made early, while the circles are still being drawn.
            self._light(p)
        if t >= self.SETTLED:
            self.still.paint(p, fade, lambda q: self._drawn(q, self.SETTLED, 1.0))
        else:
            self._drawn(p, t, fade)
        # Then a light keeps running round the vesica's edge.
        run = ease_out(win(t, 3.0, 3.4))
        if run > 0:
            along = self.along[-1] * ((t - 3.0) / 2.4 % 1.0)
            spot, _heading = point_at(self.edge, self.along, along)
            soft_dot(p, spot.x(), spot.y(), 12 * u, CHALK, 0.75 * run * fade)
            soft_dot(p, spot.x(), spot.y(), 3 * u, "#ffffff", 0.9 * run * fade)

    def _drawn(self, p: QPainter, t: float, fade: float) -> None:
        """All that is drawn by t but the running light."""
        u = self.u
        lens = ease_out(win(t, 2.25, 2.9))
        if lens > 0:
            self._lens(p, lens, fade)
        segment = ease_in_out(win(t, 0.6, 0.95))
        if segment > 0:
            _stroke(p, polyline([self.a, _lerp(self.a, self.b, segment)]), INK_LINE, u, fade)
        # The two circles, each from the other's centre upward, meeting at C and again at D.
        trace = ease_in_out(win(t, *self.TRACE))
        if trace > 0:
            turn = 2 * math.pi * trace
            for about, start, way in ((self.a, 0.0, -1), (self.b, math.pi, 1)):
                arc = _arc(about, self.d, start, way * turn, 120)
                _stroke(p, polyline(arc), CHALK_LINE, u, fade)
                if trace < 1:
                    _nib(p, arc[-1], u, CHALK, fade)
        # C is found a sixth of the way round, D five sixths.
        found_c = (self.TRACE[0] + (self.TRACE[1] - self.TRACE[0]) * 0.2, 0.3)
        found_d = (self.TRACE[0] + (self.TRACE[1] - self.TRACE[0]) * 0.8, 0.3)
        sides = ease_in_out(win(t, 2.05, 2.5))
        if sides > 0:
            path = QPainterPath(self.c)
            path.lineTo(_lerp(self.c, self.a, sides))
            path.moveTo(self.c)
            path.lineTo(_lerp(self.c, self.b, sides))
            path.moveTo(self.a)
            path.lineTo(self.b)
            _stroke(p, path, GOLD_LINE, u, fade * (0.4 + 0.6 * sides))
        # Its sides marked equal and its angles too, as a geometer would.
        marked = ease_out(win(t, 2.6, 2.95))
        if marked > 0:
            path = QPainterPath()
            corners = (self.a, self.b, self.c)
            for i, corner in enumerate(corners):
                after, before = corners[(i + 1) % 3], corners[(i + 2) % 3]
                middle = _lerp(corner, after, 0.5)
                heading = math.atan2(after.y() - corner.y(), after.x() - corner.x())
                path.moveTo(_on(middle, 4.5 * u, heading + math.pi / 2))
                path.lineTo(_on(middle, 4.5 * u, heading - math.pi / 2))
                start = math.atan2(after.y() - corner.y(), after.x() - corner.x())
                end = math.atan2(before.y() - corner.y(), before.x() - corner.x())
                turn = (end - start + math.pi) % (2 * math.pi) - math.pi
                path.addPath(polyline(_arc(corner, 13 * u * marked, start, turn, 24)))
            _stroke(p, path, ((3.0, GOLD, 0.18), (0.9, GOLD_LIGHT, 0.85)), u, fade * marked)
        axis = ease_in_out(win(t, 2.4, 2.85))
        if axis > 0:
            p.setPen(QPen(col(CHALK, 0.55 * fade), 1.0 * u, Qt.DashLine))
            p.drawLine(self.c, _lerp(self.c, self.d_point, axis))
        shown =[ease_out(win(t, 0.55, 0.8)), ease_out(win(t, 0.75, 1.0))]
        shown += [ease_out(win(t, at, at + span)) for at, span in (found_c, found_d)]
        for point, k in zip((self.a, self.b, self.c, self.d_point), shown, strict=True):
            if k > 0:
                _point(p, point, u, fade * k, k)
        _letters(p, self.labels, shown, fade)

    def _light(self, p: QPainter) -> tuple[QImage, QRectF]:
        """The lens's light per pixel, made for where p draws."""
        density = round(_density(p), 1)
        if self.light.get("key") != density:
            self.light = {"key": density, "image": _lens_light(self.a, self.b, self.d, density, self.u)}
        return self.light["image"]

    def _lens(self, p: QPainter, grow: float, fade: float) -> None:
        image, box = self._light(p)
        p.save()
        p.setOpacity(p.opacity() * fade * grow)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(box, image)
        p.restore()


def _lens_light(a: QPointF, b: QPointF, d: float, density: float, u: float) -> tuple[QImage, QRectF]:
    """The vesica piscis lit per pixel: chalk light deepest along its long axis, a bright fine rim
    and a soft halo round it."""
    half = d * math.sqrt(3) / 2
    middle = QPointF((a.x() + b.x()) / 2, a.y())
    pad = 18 * u
    box = QRectF(middle.x() - d / 2 - pad, middle.y() - half - pad, d + 2 * pad, 2 * half + 2 * pad)
    w, h = max(8, round(box.width() * density)), max(8, round(box.height() * density))

    def draw(q: QPainter) -> None:
        q.scale(w / box.width(), h / box.height())
        q.translate(-box.left(), -box.top())
        one, two = QPainterPath(), QPainterPath()
        one.addEllipse(a, d, d)
        two.addEllipse(b, d, d)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(one.intersected(two))

    inside = mask(w, h, draw)
    xs = (np.arange(w, dtype=np.float32) + 0.5) / density + box.left() - middle.x()
    across = np.clip(1 - np.abs(xs) / (d / 2), 0, 1)[None, :]
    body = inside * (0.1 + 0.3 * across ** 1.6)
    rim = np.clip(inside - blur(inside, 1.3 * density), 0, 1) * 1.4
    halo = blur(inside, 6 * density * u) * (1 - inside) * 0.3
    light = rgb(CHALK)[None, None] * (body + halo)[..., None] + rgb(INK)[None, None] * (rim * 0.55)[..., None]
    return glow(light.astype(np.float32)), box


# Pythagoras.


@dataclass
class _Pythagoras:
    """A 3-4-5 right triangle, its right angle at corner, k the side of a cell: drawn in one stroke,
    then a square unfolds from each side, ruled into 9, 16 and 25 cells, the one on c in gold."""

    corner: QPointF
    k: float
    u: float

    def __post_init__(self) -> None:
        o, k, u = self.corner, self.k, self.u
        a, b = 3 * k, 4 * k
        self.up = QPointF(o.x(), o.y() - a)
        self.right = QPointF(o.x() + b, o.y())
        self.bottom = o.y() + b
        self.box = QRectF(o.x() - a, o.y() - a - b, 2 * a + b, 2 * b + a)
        # (from, to, the way out, cells, tint, letter, when it unfolds)
        self.squares = [
            (o, self.up, QPointF(-1, 0), 3, CHALK, "a", 1.95),
            (o, self.right, QPointF(0, 1), 4, CHALK, "b", 2.1),
            (self.up, self.right, QPointF(a / (5 * k), -b / (5 * k)), 5, GOLD, "c", 2.3),
        ]
        self.labels = []
        for start, end, out, cells, _tint, letter, _when in self.squares:
            side = cells * k
            middle = QPointF((start.x() + end.x()) / 2 + out.x() * side / 2, (start.y() + end.y()) / 2 + out.y() * side / 2)
            path = QPainterPath()
            path.addText(QPointF(0, 0), _font(22 * u), _it(letter) + "²")
            box = path.boundingRect()
            if not box.isEmpty():
                path.translate(middle.x() - box.center().x(), middle.y() - box.center().y())
            self.labels.append(path)
        self.still = _Still(self.box.adjusted(-12 * u, -12 * u, 12 * u, 12 * u))

    # The cells are counted, a² then b² beside c², one at a time: 9 and 16 come to the 25.
    COUNT = (3.05, 4.0)
    # By then the last cell's light has died down, and nothing in it moves.
    SETTLED = 4.4

    def paint(self, p: QPainter, t: float, fade: float) -> None:
        if fade <= 0 or t < 1.2:
            return
        if t >= self.SETTLED:
            self.still.paint(p, fade, lambda q: self._drawn(q, self.SETTLED, 1.0))
        else:
            self._drawn(p, t, fade)

    def _count(self, p: QPainter, t: float, start: QPointF, step: QPointF, out: QPointF, cells: int, tint: str, fade: float) -> None:
        """Each cell lights as the count reaches it and stays a little lit."""
        count = (t - self.COUNT[0]) / (self.COUNT[1] - self.COUNT[0]) * 25
        if count <= 0:
            return
        first = 0 if cells != 4 else 9
        k = self.k
        p.setPen(Qt.NoPen)
        for i in range(cells * cells):
            at = count - first - i - 0.5
            if at < -1.5:
                break
            light = 0.3 * math.exp(-(at / 0.9) ** 2) + (0.06 if at > 0 else 0)
            row, column = divmod(i, cells)
            corner = QPointF(start.x() + step.x() * column + out.x() * k * row, start.y() + step.y() * column + out.y() * k * row)
            cell = QPainterPath(corner)
            cell.lineTo(corner + step)
            cell.lineTo(corner + step + out * k)
            cell.lineTo(corner + out * k)
            cell.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(col(tint, light * 0.6 * fade))
            p.drawPath(cell)
            middle = corner + (step + out * k) * 0.5
            soft_dot(p, middle.x(), middle.y(), k * 0.9, tint, light * 1.8 * fade)

    def _drawn(self, p: QPainter, t: float, fade: float) -> None:
        """The triangle and its squares as they are at t."""
        u, k = self.u, self.k
        for (start, end, out, cells, tint, _letter, when), label in zip(self.squares, self.labels, strict=True):
            grow = ease_out(win(t, when, when + 0.5))
            if grow <= 0:
                continue
            side = cells * k
            h = side * grow
            ox, oy = out.x() * h, out.y() * h
            square = QPainterPath(start)
            square.lineTo(end)
            square.lineTo(QPointF(end.x() + ox, end.y() + oy))
            square.lineTo(QPointF(start.x() + ox, start.y() + oy))
            square.closeSubpath()
            p.setPen(Qt.NoPen)
            base = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
            p.setBrush(gradient(base, QPointF(base.x() + out.x() * side, base.y() + out.y() * side), ((0, tint, 0.14), (1, tint, 0.03)), fade))
            p.drawPath(square)
            ex, ey = (end.x() - start.x()) / cells, (end.y() - start.y()) / cells
            if grow >= 1:
                self._count(p, t, start, QPointF(ex, ey), out, cells, tint, fade)
            # The cells: lines across as the square reaches them, and along it as far as it reaches.
            cell_lines = QPainterPath()
            for i in range(1, cells):
                if i * k < h:
                    cell_lines.moveTo(QPointF(start.x() + out.x() * i * k, start.y() + out.y() * i * k))
                    cell_lines.lineTo(QPointF(end.x() + out.x() * i * k, end.y() + out.y() * i * k))
                foot = QPointF(start.x() + ex * i, start.y() + ey * i)
                cell_lines.moveTo(foot)
                cell_lines.lineTo(QPointF(foot.x() + ox, foot.y() + oy))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(col(tint, 0.32 * fade), 0.8 * u))
            p.drawPath(cell_lines)
            _stroke(p, square, CHALK_LINE if tint == CHALK else ((5.0, GOLD, 0.14), (1.2, GOLD, 0.8)), u, fade)
            named = ease_out(win(t, when + 0.35, when + 0.7))
            if named > 0:
                p.setPen(Qt.NoPen)
                p.setBrush(col(GOLD_LIGHT if tint == GOLD else INK, 0.85 * named * fade))
                p.drawPath(label)
        draw = ease_in_out(win(t, 1.3, 1.9))
        if draw > 0:
            corner = [self.corner, self.up, self.right, self.corner]
            along = lengths(corner)
            end, _heading = point_at(corner, along, draw * along[-1])
            trail = [point for point, at in zip(corner, along, strict=True) if at < draw * along[-1]] + [end]
            _stroke(p, polyline(trail), INK_LINE, u, fade)
            if draw < 1:
                _nib(p, end, u, CHALK, fade)
        mark = ease_out(win(t, 1.8, 2.05))
        if mark > 0:
            s = 9 * u
            o = self.corner
            _stroke(p, polyline([QPointF(o.x(), o.y() - s), QPointF(o.x() + s, o.y() - s), QPointF(o.x() + s, o.y())]), ((1.0, INK, 0.8),), u, fade * mark)


# The rose and the Lissajous figure.


@dataclass
class _Rose:
    """A polar grid, and the rose r = sin 4θ plotting itself on it in gold: a point runs round with
    its radius out to it, the eight petals left behind; then it keeps going."""

    centre: QPointF
    r: float
    u: float

    PLOT = (1.5, 3.3)

    def __post_init__(self) -> None:
        reach = self.r * 1.12 + 12 * self.u
        self.box = QRectF(self.centre.x() - reach, self.centre.y() - reach, 2 * reach, 2 * reach)
        self.still = _Still(self.box)

    def _at(self, theta: float) -> QPointF:
        rho = math.sin(4 * theta) * self.r
        return QPointF(self.centre.x() + rho * math.cos(theta), self.centre.y() - rho * math.sin(theta))

    def paint(self, p: QPainter, t: float, fade: float) -> None:
        a = ease_out(win(t, 1.2, 1.7)) * fade
        if a <= 0:
            return
        if t >= self.PLOT[1]:
            self.still.paint(p, a, lambda q: self._drawn(q, self.PLOT[1], 1.0))
        else:
            self._drawn(p, t, a)
        plot = ease_in_out(win(t, *self.PLOT))
        if plot <= 0:
            return
        point = self._at(2 * math.pi * plot + max(0.0, t - self.PLOT[1]) * 0.9)
        p.setPen(QPen(col(GOLD_LIGHT, 0.55 * a), 1.0 * self.u, Qt.DashLine))
        p.drawLine(self.centre, point)
        soft_dot(p, point.x(), point.y(), 14 * self.u, GOLD, 0.8 * a)
        soft_dot(p, point.x(), point.y(), 3.4 * self.u, "#ffffff", a)

    def _drawn(self, p: QPainter, t: float, a: float) -> None:
        """The grid and as much of the rose as is plotted by t."""
        centre, r, u = self.centre, self.r, self.u
        p.setBrush(Qt.NoBrush)
        for i in (1, 2):
            p.setPen(QPen(col(CHALK, (0.28 if i == 2 else 0.15) * a), 0.9 * u))
            p.drawEllipse(centre, r * i / 2, r * i / 2)
        for i in range(8):
            p.setPen(QPen(col(CHALK, (0.26 if i % 2 == 0 else 0.12) * a), 0.9 * u))
            p.drawLine(centre, _on(centre, r * 1.12, i * math.pi / 4))
        plot = ease_in_out(win(t, *self.PLOT))
        if plot > 0:
            count = max(2, round(320 * plot))
            _stroke(p, polyline([self._at(2 * math.pi * plot * i / (count - 1)) for i in range(count)]), GOLD_LINE, u, a)


@dataclass
class _Lissajous:
    """Axes, and x = cos 3t, y = sin 2t tracing itself in chalk; then a point keeps running round it
    with a bright tail."""

    centre: QPointF
    wide: float
    high: float
    u: float

    PLOT = (1.75, 3.5)

    def __post_init__(self) -> None:
        pad = 12 * self.u
        self.box = QRectF(self.centre.x() - self.wide * 1.15 - pad, self.centre.y() - self.high * 1.15 - pad, (self.wide * 1.15 + pad) * 2, (self.high * 1.15 + pad) * 2)
        self.still = _Still(self.box)

    def _at(self, s: float) -> QPointF:
        return QPointF(self.centre.x() + self.wide * math.cos(3 * s), self.centre.y() - self.high * math.sin(2 * s))

    def paint(self, p: QPainter, t: float, fade: float) -> None:
        a = ease_out(win(t, 1.4, 1.9)) * fade
        if a <= 0:
            return
        if t >= self.PLOT[1]:
            self.still.paint(p, a, lambda q: self._drawn(q, self.PLOT[1], 1.0))
        else:
            self._drawn(p, t, a)
        plot = ease_in_out(win(t, *self.PLOT))
        if plot <= 0:
            return
        s = 2 * math.pi * plot + max(0.0, t - self.PLOT[1]) * 1.3
        if plot >= 1:
            tail = polyline([self._at(s - 0.7 * i / 23) for i in range(24)])
            _stroke(p, tail, ((7.0, CHALK, 0.25), (2.2, "#ffffff", 0.75)), self.u, a * ease_out(win(t, 3.5, 3.8)))
        point = self._at(s)
        soft_dot(p, point.x(), point.y(), 14 * self.u, CHALK, 0.8 * a)
        soft_dot(p, point.x(), point.y(), 3.4 * self.u, "#ffffff", a)

    def _drawn(self, p: QPainter, t: float, a: float) -> None:
        """The axes and as much of the figure as is traced by t."""
        centre, wide, high, u = self.centre, self.wide, self.high, self.u
        axes = QPainterPath()
        axes.moveTo(centre.x() - wide * 1.15, centre.y())
        axes.lineTo(centre.x() + wide * 1.15, centre.y())
        axes.moveTo(centre.x(), centre.y() + high * 1.15)
        axes.lineTo(centre.x(), centre.y() - high * 1.15)
        for side in (-1, 1):
            axes.moveTo(centre.x() + side * wide, centre.y() - 3 * u)
            axes.lineTo(centre.x() + side * wide, centre.y() + 3 * u)
            axes.moveTo(centre.x() - 3 * u, centre.y() + side * high)
            axes.lineTo(centre.x() + 3 * u, centre.y() + side * high)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(col(CHALK, 0.38 * a), 0.9 * u))
        p.drawPath(axes)
        plot = ease_in_out(win(t, *self.PLOT))
        if plot > 0:
            count = max(2, round(260 * plot))
            _stroke(p, polyline([self._at(2 * math.pi * plot * i / (count - 1)) for i in range(count)]), INK_LINE, u, a)


# The equations in chalk.


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
    leaves: float = LEAVE

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
    ends). Each item is (kind, text, accent?): t text, or frac a fraction (kind, top, bottom)."""
    ink, accent = QPainterPath(), QPainterPath()
    big = _font(px)
    x = 0.0
    for item in items:
        kind = item[0]
        out = accent if item[-1] is True else ink
        if kind == "t":
            out.addText(QPointF(x, 0.0), big, item[1])
            x += QFontMetricsF(big).horizontalAdvance(item[1])
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
    lit = glow(halo[..., None] * rgb(tint))
    # The chalk dust it crumbles into: specks from its own letters.
    ys, xs = np.nonzero(shape > 0.5)
    motes = []
    for i in rnd.sample(range(len(xs)), min(len(xs), 34)):
        x0 = glow_box.left() + (xs[i] + 0.5) / SOFT
        y0 = glow_box.top() + (ys[i] + 0.5) / SOFT
        motes.append((x0, y0, rnd.uniform(18, 46) * px / 26, rnd.uniform(-12, 12) * px / 26, rnd.uniform(0.7, 1.9) * px / 26, rnd.uniform(0, 0.45)))
    return _Formula(ink, accent, box, lit, glow_box, motes, start, end, tint)


# The paper and the drifting symbols.


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
    """Symbols drifting up the sides and twinkling, dimmed where a figure or an equation is."""
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
        alpha = 0.45 * a * on * twinkle * clear
        if alpha <= 0.01:
            continue
        p.setOpacity(alpha)
        r = side * scale
        p.drawImage(QRectF(x - r / 2, y - r / 2, r, r), glyphs[glyph])
    p.restore()


# The marks.


_CACHE: dict = {}


def _ruled(v: np.ndarray, every: float, per: float) -> np.ndarray:
    """Fine lines every so many points along v, about a pixel wide at per pixels a point."""
    q = v / every
    return np.exp(-((np.abs(q - np.round(q)) * every * per / 0.7) ** 2))


def _ratio(p: QPainter) -> float:
    device = p.device()
    return max(2.0, device.devicePixelRatioF() if device is not None else 1.0)


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A protractor round the button: a chalk line with ruled ticks along its edges, a gold degree
    scale at each corner where a needle sweeps to and fro, and a light running round."""
    radius = min(14.0, cover.height() * 0.2)
    edge = cover.adjusted(0.5, 0.5, -0.5, -0.5)
    key = ("ring", round(edge.width(), 1), round(edge.height(), 1))
    if key not in _CACHE:
        _CACHE[key] = _ring_parts(edge, radius)
    outline, band, rim, ticks, scales, corners = _CACHE[key]
    # The protractor's clear body round the button, faintly tinted, its outer edge a fine line.
    p.setPen(Qt.NoPen)
    p.setBrush(col(NAVY, 0.5))
    p.drawPath(band)
    p.setBrush(col(CHALK, 0.07))
    p.drawPath(band)
    _stroke(p, rim, ((0.8, CHALK, 0.45),), 1.0, 1.0)
    _stroke(p, outline, ((6.0, CHALK, 0.12), (3.0, CHALK, 0.28), (1.4, CHALK, 0.95), (0.6, INK, 0.9)), 1.0, 1.0)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(col(CHALK, 0.75), 0.9))
    p.drawPath(ticks)
    _stroke(p, scales, ((3.0, GOLD, 0.2), (0.9, GOLD, 0.95)), 1.0, 1.0)
    # The needles, each corner a little behind the last.
    needles = QPainterPath()
    tips = []
    for index, (centre, start) in enumerate(corners):
        swing = 0.5 - 0.5 * math.cos(t * 1.7 + index * math.pi / 2)
        angle = start + math.pi / 2 * (0.08 + 0.84 * swing)
        needles.moveTo(_on(centre, radius + 1.5, angle))
        tips.append(_on(centre, radius + 8.0, angle))
        needles.lineTo(tips[-1])
    _stroke(p, needles, ((3.2, GOLD, 0.3), (1.1, GOLD_LIGHT, 1.0)), 1.0, 1.0)
    for tip in tips:
        soft_dot(p, tip.x(), tip.y(), 4.5, GOLD, 0.8)
    run = outline.pointAtPercent((t / 3.2) % 1.0)
    soft_dot(p, run.x(), run.y(), 11, CHALK, 0.85)
    soft_dot(p, run.x(), run.y(), 3, "#ffffff", 1.0)


def _ring_parts(edge: QRectF, radius: float) -> tuple:
    """The ring's still parts: its outline, the ticks along its straight edges (every fifth longer,
    every tenth longer still), the degree scales round its corners, and each corner's centre and
    the angle its quarter starts at."""
    outline = QPainterPath()
    outline.addRoundedRect(edge, radius, radius)
    rim = QPainterPath()
    rim.addRoundedRect(edge.adjusted(-6.5, -6.5, 6.5, 6.5), radius + 6.5, radius + 6.5)
    band = rim.subtracted(outline)
    ticks = QPainterPath()
    step = 4.0

    def rule(start: QPointF, end: QPointF, out: QPointF) -> None:
        length = math.dist((start.x(), start.y()), (end.x(), end.y()))
        count = int(length / step)
        offset = (length - count * step) / 2
        for i in range(count + 1):
            k = (offset + i * step) / length
            at = _lerp(start, end, k)
            long = 5.5 if i % 10 == 0 else 3.8 if i % 5 == 0 else 2.2
            ticks.moveTo(QPointF(at.x() + out.x() * 1.2, at.y() + out.y() * 1.2))
            ticks.lineTo(QPointF(at.x() + out.x() * long, at.y() + out.y() * long))

    left, right, top, bottom = edge.left(), edge.right(), edge.top(), edge.bottom()
    rule(QPointF(left + radius + 2, top), QPointF(right - radius - 2, top), QPointF(0, -1))
    rule(QPointF(left + radius + 2, bottom), QPointF(right - radius - 2, bottom), QPointF(0, 1))
    rule(QPointF(left, top + radius + 2), QPointF(left, bottom - radius - 2), QPointF(-1, 0))
    rule(QPointF(right, top + radius + 2), QPointF(right, bottom - radius - 2), QPointF(1, 0))
    corners = [
        (QPointF(left + radius, top + radius), math.pi),
        (QPointF(right - radius, top + radius), -math.pi / 2),
        (QPointF(right - radius, bottom - radius), 0.0),
        (QPointF(left + radius, bottom - radius), math.pi / 2),
    ]
    scales = QPainterPath()
    for centre, start in corners:
        scales.addPath(polyline(_arc(centre, radius + 5.5, start, math.pi / 2, 24)))
        for i in range(10):
            angle = start + math.pi / 2 * i / 9
            long = 8.0 if i % 3 == 0 else 5.5
            scales.moveTo(_on(centre, radius + 2.0, angle))
            scales.lineTo(_on(centre, radius + long, angle))
    return outline, band, rim, ticks, scales, corners


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """φ in gold on a navy glass dial with a gold rim and its degree ticks, a glint going round
    the rim and φ's light breathing."""
    ratio = _ratio(p)
    side = box.width()
    key = ("badge", round(side, 1), ratio)
    if key not in _CACHE:
        _CACHE[key] = _dial(side, ratio)
    image, letter = _CACHE[key]
    pad = 9.0
    target = box.adjusted(-pad, -pad, pad, pad)
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(target, image)
    p.restore()
    c = box.center()
    breath = 0.5 + 0.5 * math.sin(t * 2.0)
    soft_dot(p, c.x(), c.y(), side * 0.34, GOLD, 0.16 + 0.14 * breath)
    p.save()
    p.translate(c)
    p.setPen(Qt.NoPen)
    p.setBrush(gradient(QPointF(0, -side * 0.25), QPointF(0, side * 0.25), ((0, GOLD_LIGHT), (0.55, GOLD), (1, GOLD_DEEP))))
    p.drawPath(letter)
    p.restore()
    angle = t * 1.4 - math.pi / 2
    glint = _on(c, side * 0.445, angle)
    soft_dot(p, glint.x(), glint.y(), side * 0.16, GOLD_LIGHT, 0.85)
    soft_dot(p, glint.x(), glint.y(), side * 0.04, "#ffffff", 1.0)


def _dial(side: float, ratio: float) -> tuple[QImage, QPainterPath]:
    """The badge's dial per pixel, with 9 points of room round it for its glow: navy glass lit from
    the upper left over faint graph lines, a gold rim shaded as turned metal, ticks every 6°; and φ
    as a path about the middle (a circle and a stroke if no font has the letter)."""
    pad = 9.0
    full = side + 2 * pad
    n = max(8, round(full * ratio))
    per = n / full
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32) + 0.5
    x, y = xs / per - full / 2, ys / per - full / 2
    dist = np.hypot(x, y)
    angle = np.arctan2(y, x)
    outer = side * 0.48
    inner = side * 0.41
    disc = smooth(outer + 0.6, outer - 0.6, dist)
    rim = disc * smooth(inner - 0.6, inner + 0.6, dist)
    glass = disc - rim
    # The glass: deep navy, lighter toward the upper left, a soft sheen there, faint squares in it.
    k = np.clip((x + y) / (2 * inner) * 0.5 + 0.5, 0, 1)
    color = rgb("#16365c")[None, None] * (1 - k)[..., None] + rgb(DEEP)[None, None] * k[..., None]
    lines = np.maximum(_ruled(x, side * 0.12, per), _ruled(y, side * 0.12, per))
    color = color + rgb(CHALK)[None, None] * (lines * 0.08)[..., None]
    sheen = np.exp(-(((x + inner * 0.35) / (inner * 0.6)) ** 2 + ((y + inner * 0.5) / (inner * 0.32)) ** 2))
    color = color + (sheen * 0.16)[..., None]
    # The rim: turned gold, bright where it faces the upper left and the lower right, rings across it.
    facing = np.cos(2 * (angle + np.pi / 4))
    across = np.clip((dist - inner) / (outer - inner), 0, 1)
    metal = 0.62 + 0.3 * facing + 0.12 * np.sin(across * np.pi * 3)
    gold = rgb(GOLD_DEEP)[None, None] * (1 - metal)[..., None] + rgb(GOLD_LIGHT)[None, None] * metal[..., None]
    color = color * (glass / np.maximum(disc, 1e-4))[..., None] + gold * (rim / np.maximum(disc, 1e-4))[..., None]
    halo = blur(disc, 3.0 * per) * (1 - disc) * 0.55
    glow_color = rgb(CHALK)
    alpha = np.clip(disc + halo, 0, 1)
    color = color * (disc / np.maximum(alpha, 1e-4))[..., None] + glow_color[None, None] * (halo / np.maximum(alpha, 1e-4))[..., None]
    image = picture(color.astype(np.float32), alpha.astype(np.float32))
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(per, per)
    q.translate(full / 2, full / 2)
    for i in range(60):
        long = side * (0.07 if i % 5 == 0 else 0.035)
        a = i * math.pi / 30
        q.setPen(QPen(col(GOLD_LIGHT if i % 5 == 0 else CHALK, 0.85 if i % 5 == 0 else 0.5), 0.7 if i % 5 == 0 else 0.5))
        q.drawLine(_on(QPointF(0, 0), inner - 0.8, a), _on(QPointF(0, 0), inner - 0.8 - long, a))
    q.end()
    letter = QPainterPath()
    letter.addText(QPointF(0, 0), _font(side * 0.52), _it("φ"))
    box = letter.boundingRect()
    if box.isEmpty():
        letter = QPainterPath()
        letter.addEllipse(QPointF(0, 0), side * 0.15, side * 0.12)
        letter.addEllipse(QPointF(0, 0), side * 0.1, side * 0.075)
        letter.addRect(QRectF(-side * 0.02, -side * 0.24, side * 0.04, side * 0.48))
        letter.setFillRule(Qt.WindingFill)
    else:
        letter.translate(-box.center().x(), -box.center().y())
    # Its glow, worked out once and laid into the dial.
    shape = mask(n, n, lambda q: (q.scale(per, per), q.translate(full / 2, full / 2), q.setPen(Qt.NoPen), q.setBrush(Qt.white), q.drawPath(letter)))
    shine = glow((blur(shape, 1.6 * per) * 0.9 + blur(shape, 4 * per) * 0.5)[..., None] * rgb(GOLD))
    q = QPainter(image)
    q.drawImage(0, 0, shine)
    q.end()
    return image, letter


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """A blueprint card: navy paper with a grain and fine squares, ruled twice round its edge, a
    protractor arc in its bottom right; on its top edge a compass construction, two arcs crossing
    over its middle where a gold point pulses, and a light that runs along the arc."""
    ratio = _ratio(p)
    key = ("card", round(rect.width()), round(rect.height()), ratio)
    if key not in _CACHE:
        _CACHE[key] = _card_paper(rect.width(), rect.height(), ratio)
    image, cross, arc = _CACHE[key]
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(rect.topLeft(), rect.size()), image)
    p.restore()
    pulse = 0.5 + 0.5 * math.sin(t * 2.6)
    at = QPointF(rect.left() + cross.x(), rect.top() + cross.y())
    soft_dot(p, at.x(), at.y(), 7 + 3 * pulse, GOLD, 0.5 + 0.3 * pulse)
    soft_dot(p, at.x(), at.y(), 1.8, "#ffffff", 1.0)
    # A light running along the arc, out from one corner to the other, as the compass drew it.
    along = (t / 2.6) % 1.0
    run, _heading = point_at(arc, lengths(arc), lengths(arc)[-1] * along)
    soft_dot(p, rect.left() + run.x(), rect.top() + run.y(), 7, GOLD_LIGHT, 0.75 * math.sin(math.pi * along))


def _card_paper(width: float, height: float, ratio: float) -> tuple[QImage, QPointF, list[QPointF]]:
    """The card's still picture per pixel, with where its construction crosses and its protractor arc."""
    w, h = max(8, round(width * ratio)), max(8, round(height * ratio))
    body = QRectF(0.5, CARD_TOP + 0.5, width - 1, height - CARD_TOP - 1)
    shape = mask(w, h, lambda q: (q.scale(ratio, ratio), q.setPen(Qt.NoPen), q.setBrush(Qt.white), q.drawRoundedRect(body, 4, 4)))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = xs / ratio, ys / ratio
    down = np.clip((y - body.top()) / max(1.0, body.height()), 0, 1)
    color = rgb(LOOK["card"][0])[None, None] * (1 - down)[..., None] + rgb(LOOK["card"][1])[None, None] * down[..., None]
    grain = noise(w, h, 2.5 * ratio, 2, 7) - 0.5
    color = color * (1 + grain * 0.18)[..., None]
    # Fine squares every 6 points, every fourth line stronger, as on drafting film.
    fine = np.maximum(_ruled(x - body.left(), 6.0, ratio), _ruled(y - body.top(), 6.0, ratio))
    strong = np.maximum(_ruled(x - body.left(), 24.0, ratio), _ruled(y - body.top(), 24.0, ratio))
    color = color + rgb(CHALK)[None, None] * (fine * 0.06 + strong * 0.08)[..., None]
    # A soft light high on the left, as if the card caught the room's light.
    sheen = np.exp(-(((x - width * 0.25) / (width * 0.6)) ** 2 + ((y - body.top()) / (body.height() * 0.5)) ** 2))
    color = color + rgb("#2d6fa8")[None, None] * (sheen * 0.18)[..., None]
    image = picture(color.astype(np.float32), shape * 0.95)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(ratio, ratio)
    q.setBrush(Qt.NoBrush)
    # A protractor quarter in the bottom right corner, faint behind the names' ends.
    corner = QPointF(body.right() - 3, body.bottom() - 3)
    reach = min(body.height() * 0.78, body.width() * 0.5)
    arc = _arc(corner, reach, math.pi, math.pi / 2, 30)
    q.setPen(QPen(col(CHALK, 0.3), 0.8))
    q.drawPolyline(arc)
    q.drawPolyline(_arc(corner, reach * 0.62, math.pi, math.pi / 2, 20))
    for i in range(10):
        angle = math.pi + math.pi / 2 * i / 9
        q.setPen(QPen(col(CHALK, 0.3 if i % 3 == 0 else 0.2), 0.7))
        q.drawLine(_on(corner, reach - (4.5 if i % 3 == 0 else 2.5), angle), _on(corner, reach, angle))
    # Ruled twice round the edge, with drafting ticks at the inner rule's corners.
    q.setPen(QPen(col(LOOK["edge"], 0.95), 1.0))
    q.drawRoundedRect(body, 4, 4)
    inner = body.adjusted(3, 3, -3, -3)
    q.setPen(QPen(col(CHALK, 0.28), 0.7))
    q.drawRect(inner)
    q.setPen(QPen(col(CHALK, 0.7), 0.8))
    for cx, cy, sx, sy in ((inner.left(), inner.top(), 1, 1), (inner.right(), inner.top(), -1, 1), (inner.right(), inner.bottom(), -1, -1), (inner.left(), inner.bottom(), 1, -1)):
        q.drawLine(QPointF(cx, cy), QPointF(cx + 5 * sx, cy))
        q.drawLine(QPointF(cx, cy), QPointF(cx, cy + 5 * sy))
    # On the top edge a compass arc from corner to corner, ruled as a protractor's scale, with
    # small arcs crossing at its crown where the line square to the edge rises.
    middle, top = width / 2, body.top()
    half = body.width() / 2 - 5
    rise = CARD_TOP - 5.0
    reach = (half * half + rise * rise) / (2 * rise)
    centre = QPointF(middle, top - rise + reach)
    spread = math.asin(half / reach)
    crown = _arc(centre, reach, -math.pi / 2 - spread, 2 * spread, 60)
    for w, color, alpha in ((3.0, GOLD, 0.22), (1.0, GOLD, 0.95)):
        q.setPen(QPen(col(color, alpha), w, Qt.SolidLine, Qt.RoundCap))
        q.drawPolyline(crown)
    count = max(4, int(half * 2 / 4.5))
    for i in range(count + 1):
        angle = -math.pi / 2 - spread + 2 * spread * i / count
        long = 3.6 if i % 5 == 0 else 2.0
        q.setPen(QPen(col(GOLD_LIGHT if i % 5 == 0 else GOLD, 0.85 if i % 5 == 0 else 0.6), 0.7))
        q.drawLine(_on(centre, reach + 0.6, angle), _on(centre, reach + long, angle))
    cross = QPointF(middle, top - rise)
    for sign in (-1, 1):
        foot = QPointF(middle + sign * 9, top)
        opening = math.dist((foot.x(), foot.y()), (cross.x(), cross.y()))
        heading = math.atan2(cross.y() - foot.y(), cross.x() - foot.x())
        q.setPen(QPen(col(INK, 0.75), 0.8))
        q.drawPolyline(_arc(foot, opening, heading - 0.3, 0.6, 12))
        q.drawLine(QPointF(foot.x(), top - 2), QPointF(foot.x(), top + 2))
    q.setPen(QPen(col(GOLD_LIGHT, 0.7), 0.8, Qt.DashLine))
    q.drawLine(cross, QPointF(middle, top + 4))
    for end in (crown[0], crown[-1]):
        q.setPen(Qt.NoPen)
        q.setBrush(col(INK, 0.95))
        q.drawEllipse(end, 1.5, 1.5)
    q.end()
    return image, cross, crown


def lead(size: float, index: int) -> QPixmap:
    """A small compass in chalk line, its point down and an arc cut by its pencil, the arc gold
    and chalk by turns."""
    ratio = 3.0
    image = QPixmap(round(size * ratio), round(size * ratio))
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    s = size
    hinge = QPointF(s * 0.46, s * 0.22)
    needle = QPointF(s * 0.2, s * 0.84)
    pencil = QPointF(s * 0.72, s * 0.84)
    # The arc its pencil has just cut, gold and chalk by turns.
    tint = GOLD if index % 2 == 0 else CHALK
    reach = pencil.x() - needle.x()
    cut = polyline(_arc(needle, reach, -0.5, 0.78, 16))
    p.setBrush(Qt.NoBrush)
    for w, color, alpha in ((s * 0.18, tint, 0.2), (s * 0.075, tint, 1.0)):
        p.setPen(QPen(col(color, alpha), w, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(cut)
    legs = QPainterPath(needle)
    legs.lineTo(hinge)
    legs.lineTo(QPointF(s * 0.68, s * 0.72))
    legs.moveTo(hinge)
    legs.lineTo(QPointF(s * 0.46, s * 0.04))
    for w, color, alpha in ((s * 0.24, CHALK, 0.2), (s * 0.1, INK, 1.0)):
        p.setPen(QPen(col(color, alpha), w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(legs)
    # The pencil's lead, and the hinge's screw.
    point = QPainterPath(QPointF(s * 0.63, s * 0.7))
    point.lineTo(pencil)
    point.lineTo(QPointF(s * 0.73, s * 0.66))
    point.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(col(GOLD))
    p.drawPath(point)
    p.setPen(QPen(col(INK), s * 0.065))
    p.setBrush(col(NAVY))
    p.drawEllipse(hinge, s * 0.11, s * 0.11)
    p.end()
    return image
