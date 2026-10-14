"""天使: a gilded cathedral frame that draws itself round the lobby, and a
round window of golden light.

Candlelight warms the screen's edges and pools in the two bottom corners, flickering. From the top
corners gold tracery draws itself, a hot pen of light running ahead of each line: a gilt molding (a
rule, a row of beads and a fine rule) along the top and down both sides, with a quatrefoil boss on
each corner and a pendant trefoil at each end, and under it over the title a frieze of little
pointed arches whose two halves meet in a quatrefoil above its middle with a burst of light. In the
top left a great cusped arch sweeps from the top edge down to the side, holding a round window of
quatrefoil tracery, trefoils and filigree scrolls that curl as they grow. In the top right a round
window draws its gold tracery from the middle out, an angel with its wings spread and a halo over
its head, then its glass lights up from the middle: the angel in pale glowing glass on rays of
honey and amber, wavering like candlelight; it throws slow shafts of light down toward the lobby,
dust turning in them. The gold is
shaded per pixel, raised and lit from the upper left; once it is all drawn, glints run along it.
Gold-leaf feathers fall down the sides, flashing as they turn, and motes rise from the candlelight.
At the end it all fades.

Its marks are of the same gold: the ring is a gilded frame on 准备案件还原, with quatrefoils at its
corners, a little pointed crest and filigree, glints running round it; the badge is a gold rosette of
twelve foils and eight petals round a honey glass boss; the card is a window of pale golden glass
leaded in diamonds, under an ogee arch with a star on its tip, in a gold frame, with a gold
four-point star before each name.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient, QTransform

from blacklist_detect.love_scenes.draw import (
    Wash,
    catmull,
    clamp,
    col,
    ease_in,
    ease_in_out,
    ease_out,
    gradient,
    lengths,
    point_at,
    polyline,
    quad,
    star,
    win,
)
from blacklist_detect.love_scenes.light import blur, glow, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
LOOK = {
    "glow": (255, 208, 120),
    "rim": "#e9bd5c",
    "band": ("#fff1c4", "#d9a441"),
    "card": ("#fff0c4", "#f4cf7c"),
    "edge": "#c8952e",
    "ink": "#3a2206",
    "flowers": (("#fffbea", "#f5d47e", "#c8922e"), ("#fff3d0", "#ffd98a", "#b07a22")),
    "disc": ("#fff3d0", "#e9bd5c"),
    "heart": ("#ffe08a", "#c8922e"),
    "deep": "#b8862b",
    "deep_glow": (240, 190, 90),
}
MARKS_ANIMATED = True
# The card's pointed arch and the star on its tip stand in this room above the names.
CARD_TOP = 30
CARD_PAD = (15, 5, 15, 10)

HONEY = "#ffd98a"
EMBER = "#ffb24a"
# Gold from its shade to its shine: tone 0..1 picks a color along it.
RAMP = ((0.0, "#2e1a04"), (0.2, "#6b4410"), (0.42, "#a8721e"), (0.6, "#d6a240"), (0.76, "#f2cf76"), (0.9, "#fff0b8"), (1.0, "#fffbec"))
# How fast the tracery spreads from where it starts, and how fast each line draws, in design points a second.
SPREAD = 560.0
DRAW = 620.0
# The round window's shafts of light are soft: worked out at this share of the size and laid on scaled up.
SOFT = 0.25


@dataclass
class _Line:
    """A line of the tracery: its points, how thick it is (in units), when it starts drawing and how long
    that takes."""

    points: list[QPointF]
    width: float
    start: float
    span: float
    # A row of beads this far apart (in units), each width across, instead of a solid line.
    beads: float = 0.0
    path: QPainterPath = field(init=False)
    run: list[float] = field(init=False)

    def __post_init__(self) -> None:
        self.path = polyline(self.points)
        self.run = lengths(self.points)


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(31)
    lines, rose, regions = _cathedral(width, height, u)
    ends = max(line.start + line.span for line in lines)
    # The top rules meet over the title's middle, at the keystone.
    meet, keystone = 0.12 + (width / 2 - 10 * u) / (DRAW * u), QPointF(width / 2, 40 * u)
    warmth = Wash(lambda q, w, h: _warmth(q, w, h, u))
    # The longest lines carry the glints once everything is drawn.
    tracks = sorted(lines, key=lambda line: -line.run[-1])[:10]
    glints = [(2.0 + 0.27 * i + rnd.uniform(0, 0.15), tracks[i % len(tracks)], rnd.uniform(0.9, 1.4), rnd.random() < 0.5) for i in range(9)]
    falling = [
        (
            rnd.uniform(0.6, 3.0),
            (rnd.uniform(0.025, 0.1) if i % 2 else rnd.uniform(0.958, 0.985)) * width,
            rnd.uniform(0.18, 0.55) * height,
            rnd.uniform(34, 52) * u,
            rnd.uniform(50, 66) * u,
            rnd.uniform(0, 6.28),
            rnd.uniform(1.1, 1.9),
        )
        for i in range(10)
    ]
    rising = [
        (rnd.uniform(0.2, 4.0), (rnd.uniform(0.0, 0.13) if i % 2 else rnd.uniform(0.9, 1.0)) * width, height * rnd.uniform(0.86, 1.02),
         rnd.uniform(40, 90) * u, rnd.uniform(1.3, 2.8) * u, rnd.uniform(0, 6.28))
        for i in range(36)
    ]  # fmt: skip
    center, radius = rose
    dust = [
        (rnd.uniform(1.6, 3.4), rnd.uniform(0.35, 1.0), rnd.uniform(1.95, 2.9), rnd.uniform(0.35, 0.95), rnd.uniform(1.0, 2.2) * u, rnd.uniform(0, 6.28))
        for _ in range(20)
    ]
    spark = _spark()
    # The pictures, made for each sharpness they are shown at, each a little before it is wanted: one
    # a frame, so no frame waits long, and at once whatever is wanted already.
    baked: dict[float, tuple[_Gilding, dict, list]] = {}

    def bake(scale: float) -> tuple[_Gilding, dict]:
        if scale not in baked:
            baked.clear()
            gilding = _Gilding(lines, regions, scale, u)
            jobs = [(need, f"area{k}", lambda k=k: gilding.build(k)) for k, need in enumerate(gilding.need)]
            jobs += [
                (0.5, "feather", lambda: _feather(max(16, math.ceil(66 * u * scale / 8) * 8))),
                (1.05, "glass", lambda: _rose_glass(center, radius, scale, u)),
                (1.5, "shafts", lambda: _shafts(width, height, gap, rose, u)),
            ]
            baked[scale] = (gilding, {}, sorted(jobs, key=lambda job: job[0]))
        return baked[scale][:2]

    def prepare(scale: float, t: float) -> None:
        _gilding, art, jobs = baked[scale]
        ran = False
        while jobs and (jobs[0][0] <= t + 0.05 or not ran):
            _need, name, job = jobs.pop(0)
            art[name] = job()
            ran = True

    def paint(p: QPainter, t: float) -> None:
        scale = _sharpness(p)
        gilding, art = bake(scale)
        prepare(scale, t)
        gilding.advance(t)
        shafts, glass, feather = art.get("shafts"), art.get("glass"), art.get("feather")
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.3, 5.0))
        flicker = _flicker(t, 0)
        p.save()
        p.setOpacity(life)
        warmth.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.9)) * (1 - leave) * (0.86 + 0.14 * flicker))
        _candles(p, t, width, height, u, (1 - leave) * ease_out(win(t, 0.0, 1.2)))
        lit = ease_out(win(t, 1.15, 2.05))
        if shafts is not None:
            _shaft_paint(p, t, shafts, width, height, (1 - leave) * ease_out(win(t, 1.6, 2.7)))
        _dust(p, t, dust, center, radius, spark, u, (1 - leave) * lit)
        if glass is not None:
            _rose(p, t, glass, center, radius, lit, 1 - ease_in(win(t, 4.1, 4.85)), u, spark)
        _tracery(p, t, gilding, ends, 1 - leave, flicker)
        _pens(p, t, lines, spark, u, 1 - leave)
        _flare(p, t, keystone, meet, spark, u)
        _glints(p, t, glints, spark, u, 1 - leave)
        if feather is not None:
            _feathers(p, t, falling, feather, 1 - leave)
        _motes(p, t, rising, spark, u, 1 - leave)
        p.restore()

    return paint


# The tracery: where its lines are and when each draws.


def _cathedral(width: float, height: float, u: float) -> tuple[list[_Line], tuple[QPointF, float], list[QRectF]]:
    """The lines of the gilded frame, the round window (its middle and radius) and the areas the gold is
    worked out over, one picture each: the top left corner (in two), the frieze, the top right corner
    and the two sides."""
    lines: list[_Line] = []
    mid = width / 2
    low = height * 0.76
    left, right = QPointF(0, 0), QPointF(width, 0)

    def at(x: float, y: float, side: int = 1) -> QPointF:
        return QPointF(x * u if side > 0 else width - x * u, y * u)

    def add(points: list[QPointF], thick: float, origin: QPointF, t0: float, closed: bool = False, after: float = 0.0, beads: float = 0.0) -> None:
        """A line growing out from where it is nearest origin, both ways if that is in its middle."""
        if closed:
            points = points[:-1]
            i = min(range(len(points)), key=lambda k: _dist(points[k], origin))
            points = points[i:] + points[:i] + [points[i]]
            half = len(points) // 2
            parts = [points[: half + 1], points[half:][::-1]]
        else:
            i = min(range(len(points)), key=lambda k: _dist(points[k], origin))
            parts = [part for part in (points[i::-1], points[i:]) if len(part) > 1]
        for part in parts:
            run = lengths(part)[-1]
            start = t0 + after + _dist(part[0], origin) / (SPREAD * u)
            lines.append(_Line(part, thick, start, max(0.12, run / (DRAW * u)), beads))

    # The molding: a rule, a row of beads and a fine rule, along the top from each corner to the
    # middle and down each side; a quatrefoil boss on each corner.
    for side, origin in ((1, left), (-1, right)):
        for inset, thick, beads in ((10, 3.6, 0.0), (16.5, 3.2, 6.6), (22, 1.2, 0.0)):
            corner = at(inset, inset, side)
            add([QPointF(corner.x(), low), corner, QPointF(mid, corner.y())], thick, origin, 0.12, beads=beads)
        boss = at(16, 16, side)
        add(_foil(boss.x(), boss.y(), 12 * u, 4, math.pi / 4), 2.4, origin, 0.12, closed=True)
        add(_circle(boss.x(), boss.y(), 3.4 * u, 12), 2.0, origin, 0.12, closed=True, after=0.1)
        # Each side ends in a pendant trefoil and a drop.
        x = 16 * u if side > 0 else width - 16 * u
        foil = _foil(x, low + 14 * u, 10 * u, 3, math.pi / 2)
        add(foil, 1.8, QPointF(x, low), 0.12 + (low - 10 * u) / (SPREAD * u), closed=True)
        add([QPointF(x, low + 24 * u), QPointF(x, low + 38 * u)], 2.4, QPointF(x, low), 0.12 + (low + 10 * u) / (SPREAD * u))
    center, radius = QPointF(width - 150 * u, 132 * u), 92 * u
    # The arch's ends, on the fine rules.
    a, c, b = at(470, 22), at(120, 120), at(22, 430)
    base = 58 * u
    frieze_end = (a.x(), center.x() - math.sqrt(max(0.0, (radius + 6 * u) ** 2 - (center.y() - base) ** 2)))
    _frieze(add, width, u, base, frieze_end, left, right)
    _spandrel(add, a, c, b, u, left)
    _rose_lines(add, center, radius, u)
    regions = [
        QRectF(0, 0, 530 * u, 210 * u),
        QRectF(0, 210 * u, 240 * u, 260 * u),
        QRectF(530 * u, 0, max(1.0, width - 830 * u), 66 * u),
        QRectF(width - 300 * u, 0, 300 * u, 270 * u),
        QRectF(0, 470 * u, 50 * u, max(1.0, low + 50 * u - 470 * u)),
        QRectF(width - 50 * u, 270 * u, 50 * u, max(1.0, low + 50 * u - 270 * u)),
    ]
    return lines, (center, radius), regions


def _frieze(add, width: float, u: float, base: float, ends: tuple[float, float], left: QPointF, right: QPointF) -> None:  # noqa: ANN001
    """Under the top molding, a row of little pointed arches standing on a rule at base, from the
    corners to a quatrefoil over the middle of the title."""
    mid = width / 2
    spring, apex, span = base - 8 * u, base - 30 * u, 30 * u
    # The arches' halves are arcs about a point on the spring line, through the apex.
    r = ((span / 2) ** 2 + (spring - apex) ** 2) / span
    for side, origin, end in ((1, left, ends[0]), (-1, right, ends[1])):
        add([QPointF(end, base), QPointF(mid - side * 16 * u, base)], 1.8, origin, 0.12)
        k = 0
        while True:
            x0 = mid - side * (22 * u + k * span)
            x1 = x0 - side * span
            if (x1 < end + 4 * u) if side > 0 else (x1 > end - 4 * u):
                break
            lo, hi = min(x0, x1), max(x0, x1)
            half_l = _arc(lo + r, spring, r, math.pi, math.pi + math.acos((r - span / 2) / r), 8)
            half_r = _arc(hi - r, spring, r, -math.acos((r - span / 2) / r), 0.0, 8)
            arch = [QPointF(lo, base), *half_l, *half_r, QPointF(hi, base)]
            add(arch, 1.5, origin, 0.12, after=0.08)
            add(_circle((lo + hi) / 2, base - 19 * u, 2.4 * u, 10), 1.1, origin, 0.12, closed=True, after=0.18)
            add(_circle(lo if side > 0 else hi, base - 24 * u, 2.6 * u, 10), 1.1, origin, 0.12, closed=True, after=0.14)
            k += 1
    # The keystone: a quatrefoil in a ring over the middle, lit when the two halves meet.
    when = 0.12 + (mid - 10 * u) / (SPREAD * u) - 0.25
    y = base - 18 * u
    add(_circle(mid, y, 15 * u, 40), 2.2, QPointF(mid, y - 15 * u), when, closed=True)
    add(_foil(mid, y, 12 * u, 4, math.pi / 4), 1.6, QPointF(mid, y - 12 * u), when + 0.1, closed=True)
    add(_circle(mid, y, 3 * u, 12), 1.4, QPointF(mid, y - 3 * u), when + 0.2, closed=True)


def _spandrel(add, a: QPointF, c: QPointF, b: QPointF, u: float, origin: QPointF) -> None:  # noqa: ANN001
    """The top left corner: a great arch from the top rule to the side rule, a molding beside it and
    cusps under it, and the corner it leaves filled with a round window, foils in rings and scrolls."""
    t0 = 0.12
    arch = [quad(a, c, b, i / 60) for i in range(61)]
    add(arch, 3.0, origin, t0)
    add(_offset(arch, 7 * u), 1.4, origin, t0 + 0.05)
    # Cusps hang from it into the lobby: arcs between points on it, meeting in points.
    count = 11
    for i in range(count):
        s0, s1 = (i + 0.5) / (count + 1), (i + 1.5) / (count + 1)
        p0, p1 = quad(a, c, b, s0), quad(a, c, b, s1)
        n0, n1 = _normal(a, c, b, s0), _normal(a, c, b, s1)
        sm = (s0 + s1) / 2
        m, nm = quad(a, c, b, sm), _normal(a, c, b, sm)
        tip0 = QPointF(p0.x() + n0.x() * 11 * u, p0.y() + n0.y() * 11 * u)
        tip1 = QPointF(p1.x() + n1.x() * 11 * u, p1.y() + n1.y() * 11 * u)
        dip = QPointF(m.x() + nm.x() * 2 * u, m.y() + nm.y() * 2 * u)
        cusp = [quad(tip0, QPointF(2 * dip.x() - (tip0.x() + tip1.x()) / 2, 2 * dip.y() - (tip0.y() + tip1.y()) / 2), tip1, k / 12) for k in range(13)]
        add(cusp, 1.4, origin, t0, after=0.12)
        if i:
            add(_circle(tip0.x() + n0.x() * 2.5 * u, tip0.y() + n0.y() * 2.5 * u, 2.2 * u, 10), 1.1, origin, t0, closed=True, after=0.2)
    # The round window: two rings, a quatrefoil and a boss.
    ox, oy, r = 98 * u, 98 * u, 62 * u
    add(_circle(ox, oy, r, 72), 3.0, origin, t0, closed=True)
    add(_circle(ox, oy, r - 6 * u, 72), 1.3, origin, t0, closed=True, after=0.06)
    add(_foil(ox, oy, r - 11 * u, 4, 0.0), 2.2, origin, t0, closed=True, after=0.2)
    add(_foil(ox, oy, r - 30 * u, 4, math.pi / 4), 1.2, origin, t0, closed=True, after=0.35)
    add(_circle(ox, oy, 9 * u, 20), 2.0, origin, t0, closed=True, after=0.45)
    for k in range(8):
        turn = k * math.pi / 4
        add([QPointF(ox + 9 * u * math.cos(turn), oy + 9 * u * math.sin(turn)), QPointF(ox + 19 * u * math.cos(turn), oy + 19 * u * math.sin(turn))], 1.1, origin, t0, after=0.5)
    # Trefoils in rings by the arch's two ends, and a little quatrefoil between the window and the arch.
    for x, y, rr, turn in ((250, 48, 22, -math.pi / 2), (48, 250, 22, math.pi), (180, 130, 13, math.pi / 4)):
        add(_circle(x * u, y * u, rr * u, 40), 2.2, origin, t0, closed=True)
        add(_foil(x * u, y * u, (rr - 5) * u, 3, turn), 1.4, origin, t0, closed=True, after=0.15)
    # Filigree scrolls off the round window and the trefoils, curling as they grow.
    scrolls = (
        (QPointF(ox + r * math.cos(-0.15), oy + r * math.sin(-0.15)), -0.05, 58, 5.0),
        (QPointF(ox + r * math.cos(1.72), oy + r * math.sin(1.72)), 1.62, 58, -5.0),
        (QPointF(228 * u, 48 * u), math.pi + 0.1, 36, -4.6),
        (QPointF(48 * u, 228 * u), -math.pi / 2 - 0.1, 36, 4.6),
    )
    for start, heading, length, turn in scrolls:
        curl = _scroll(start, heading, length * u, turn)
        add(curl, 1.5, origin, t0, after=0.15)
        end = curl[-1]
        add(_circle(end.x(), end.y(), 2.2 * u, 10), 1.6, origin, t0, closed=True, after=0.15 + length * u / (DRAW * u))


def _rose_lines(add, center: QPointF, radius: float, u: float) -> None:  # noqa: ANN001
    """The round window's tracery, drawing from its middle out: an angel with its wings spread and a
    halo over its head, and the ring round it all."""
    t0 = 0.5
    for outline, thick in _angel_outlines():
        add([QPointF(center.x() + x * radius, center.y() + y * radius) for x, y in outline], thick, center, t0, closed=True)
    add(_circle(center.x(), center.y(), radius, 96), 3.0, center, t0, closed=True)


def _angel_outlines() -> list[tuple[list[tuple[float, float]], float]]:
    """The angel in the round window, in shares of its radius from its middle (y down), each a closed
    outline with the width its gold is drawn: the two wings, the robe, the head and the halo."""

    def bend(a: tuple, c: tuple, b: tuple, steps: int) -> list[tuple[float, float]]:
        return [
            ((1 - k) ** 2 * a[0] + 2 * (1 - k) * k * c[0] + k * k * b[0], (1 - k) ** 2 * a[1] + 2 * (1 - k) * k * c[1] + k * k * b[1])
            for k in (i / steps for i in range(steps + 1))
        ]

    def ring(cx: float, cy: float, rx: float, ry: float) -> list[tuple[float, float]]:
        return [(cx + rx * math.sin(i * math.pi / 16), cy - ry * math.cos(i * math.pi / 16)) for i in range(33)]

    def wing(side: int) -> list[tuple[float, float]]:
        # Up and out from the shoulder to the tip, then back down the trailing edge, a bulge for
        # each of four long feathers, and in along the robe to the shoulder.
        root, tip, end = (0.12, -0.1), (0.76, -0.4), (0.22, 0.22)
        points = bend(root, (0.34, -0.54), tip, 14)
        for i in range(4):
            a = (tip[0] + (end[0] - tip[0]) * i / 4, tip[1] + (end[1] - tip[1]) * i / 4)
            b = (tip[0] + (end[0] - tip[0]) * (i + 1) / 4, tip[1] + (end[1] - tip[1]) * (i + 1) / 4)
            points += bend(a, ((a[0] + b[0]) / 2 + 0.05, (a[1] + b[1]) / 2 + 0.045), b, 6)[1:]
        points += bend(end, (0.12, 0.06), root, 6)[1:]
        return [(side * x, y) for x, y in points]

    robe = bend((-0.055, -0.225), (-0.13, -0.21), (-0.15, -0.13), 6)
    for a, c, b, steps in (
        ((-0.15, -0.13), (-0.2, 0.22), (-0.3, 0.6), 10),
        ((-0.3, 0.6), (0.0, 0.7), (0.3, 0.6), 12),
        ((0.3, 0.6), (0.2, 0.22), (0.15, -0.13), 10),
        ((0.15, -0.13), (0.13, -0.21), (0.055, -0.225), 6),
        ((0.055, -0.225), (0.0, -0.21), (-0.055, -0.225), 4),
    ):
        robe += bend(a, c, b, steps)[1:]
    return [(wing(1), 1.5), (wing(-1), 1.5), (robe, 1.7), (ring(0, -0.33, 0.1, 0.1), 1.6), (ring(0, -0.5, 0.15, 0.045), 2.2)]


def _dist(a: QPointF, b: QPointF) -> float:
    return math.hypot(a.x() - b.x(), a.y() - b.y())


def _arc(cx: float, cy: float, r: float, a0: float, a1: float, count: int) -> list[QPointF]:
    return [QPointF(cx + r * math.cos(a0 + (a1 - a0) * i / count), cy + r * math.sin(a0 + (a1 - a0) * i / count)) for i in range(count + 1)]


def _circle(cx: float, cy: float, r: float, count: int) -> list[QPointF]:
    return _arc(cx, cy, r, -math.pi / 2, 1.5 * math.pi, count)


def _foil(cx: float, cy: float, r: float, lobes: int, turn: float) -> list[QPointF]:
    """A foil (trefoil, quatrefoil...): lobes round arcs inside r, meeting in cusps; one lobe at turn."""
    d = r * 0.5
    b = r - d
    out = []
    for i in range(lobes * 24 + 1):
        a = turn + 2 * math.pi * i / (lobes * 24)
        best = 0.0
        for k in range(lobes):
            off = a - (turn + 2 * math.pi * k / lobes)
            s = d * math.sin(off)
            if abs(s) <= b:
                best = max(best, d * math.cos(off) + math.sqrt(b * b - s * s))
        out.append(QPointF(cx + best * math.cos(a), cy + best * math.sin(a)))
    return out


def _normal(a: QPointF, c: QPointF, b: QPointF, s: float) -> QPointF:
    """The curve's normal at s, toward the side away from the corner it bows into."""
    dx = 2 * (1 - s) * (c.x() - a.x()) + 2 * s * (b.x() - c.x())
    dy = 2 * (1 - s) * (c.y() - a.y()) + 2 * s * (b.y() - c.y())
    n = math.hypot(dx, dy) or 1.0
    return QPointF(dy / n, -dx / n)


def _offset(points: list[QPointF], d: float) -> list[QPointF]:
    """The polyline moved d along its left normal."""
    out = []
    for i, point in enumerate(points):
        a, b = points[max(0, i - 1)], points[min(len(points) - 1, i + 1)]
        dx, dy = b.x() - a.x(), b.y() - a.y()
        n = math.hypot(dx, dy) or 1.0
        out.append(QPointF(point.x() - dy / n * d, point.y() + dx / n * d))
    return out


def _scroll(start: QPointF, heading: float, length: float, turn: float) -> list[QPointF]:
    """A filigree scroll: it leaves start along heading and curls tighter and tighter, turning by turn
    radians in all, most of it at the end."""
    out = [start]
    x, y = start.x(), start.y()
    count = 48
    for i in range(1, count + 1):
        s = i / count
        a = heading + turn * s ** 2.6
        step = length / count * (1.0 - 0.45 * s)
        x += step * math.cos(a)
        y += step * math.sin(a)
        out.append(QPointF(x, y))
    return out


def _between(points: list[QPointF], run: list[float], a: float, b: float) -> list[QPointF]:
    """The polyline's points between distances a and b along it."""
    if b <= a or b <= 0:
        return []
    first, _ = point_at(points, run, a)
    out = [first]
    for point, at in zip(points, run, strict=True):
        if a < at < b:
            out.append(point)
        elif at >= b:
            break
    last, _ = point_at(points, run, b)
    out.append(last)
    return out


# Per pixel: gold, glass and light.


def _ramp(tone: np.ndarray) -> np.ndarray:
    stops = [at for at, _ in RAMP]
    colors = np.array([rgb(color) for _, color in RAMP])
    out = np.empty((*tone.shape, 3), dtype=np.float32)
    for k in range(3):
        out[..., k] = np.interp(tone, stops, colors[:, k])
    return out


def _metal(height: np.ndarray, relief: float) -> np.ndarray:
    """Gold over a height field, lit from the upper left: its slopes catch the light or fall into
    shade, and it mirrors a bright sky above and a dark floor below, as polished metal does."""
    gy, gx = np.gradient(height)
    nx, ny = -gx * relief, -gy * relief
    norm = np.sqrt(nx * nx + ny * ny + 1)
    nx, ny, nz = nx / norm, ny / norm, 1 / norm
    lx, ly, lz = -0.45, -0.62, 0.64
    diffuse = np.clip(nx * lx + ny * ly + nz * lz, 0, 1)
    rx, ry, rz = 2 * nz * nx, 2 * nz * ny, 2 * nz * nz - 1
    sky = smooth(-0.55, 0.65, -(ry * 0.85 + rx * 0.4))
    spec = np.clip(rx * lx + ry * ly + rz * lz, 0, 1) ** 26
    tone = np.clip(0.12 + 0.4 * sky + 0.42 * diffuse + 0.3 * spec, 0, 1)
    return _ramp(tone) + (spec * 0.3)[..., None]


def _shift(a: np.ndarray, dy: int, dx: int) -> np.ndarray:
    out = np.zeros_like(a)
    h, w = a.shape
    out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = a[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
    return out


def _gild(cover: np.ndarray, px: float, shadow: float = 0.55) -> QImage:
    """Lines (cover, 0..1 a pixel) as raised gold wire, with a soft shadow under them; px is pixels to
    the unit."""
    height = blur(cover, max(0.6, 0.8 * px))
    color = _metal(height, 2.6 * px)
    under = _shift(blur(cover, max(0.6, 1.1 * px)), max(1, round(1.2 * px)), round(0.5 * px)) * shadow * (1 - cover)
    total = cover + under
    color = (color * cover[..., None] + rgb("#1e1004") * under[..., None]) / np.maximum(total, 1e-4)[..., None]
    return picture(color, total)


class _Gilding:
    """The gold tracery as it draws itself. For each area: the finished gold and its warm light, and
    the same two pictures filled in only where the lines have been drawn so far. Each frame adds what
    was drawn since the last, laying the finished picture on along it; going back in time starts them
    afresh. An area's pictures are made when build is called, by its need: a little before its first
    line starts."""

    def __init__(self, lines: list[_Line], regions: list[QRectF], scale: float, u: float) -> None:
        self.lines, self.regions, self.scale, self.u = lines, regions, scale, u
        self.near, self.need = [], []
        for rect in regions:
            room = rect.adjusted(-30 * u, -30 * u, 30 * u, 30 * u)
            near = [i for i, line in enumerate(lines) if line.path.boundingRect().adjusted(-1, -1, 1, 1).intersects(room)]
            self.near.append(near)
            # When the first line gets to it.
            first = 9.0
            for i in near:
                line = lines[i]
                # Along the line every so often: a rule is one long straight piece.
                steps = [k * 10 * u for k in range(int(line.run[-1] / (10 * u)) + 1)] if len(line.points) <= 3 else line.run
                at = next((d for d in steps if room.contains(point_at(line.points, line.run, d)[0])), line.run[-1])
                first = min(first, line.start + line.span * at / max(line.run[-1], 1e-6))
            self.need.append(first - 0.15)
        self.areas: list[tuple | None] = [None] * len(regions)
        self.drawn = [0.0] * len(lines)
        self.t = -1.0

    def build(self, k: int) -> None:
        rect, near = self.regions[k], self.near[k]
        gold, bloom = _gilt(rect, [self.lines[i] for i in near], self.scale, self.u)
        self.areas[k] = (rect, near, gold, bloom, _blank(gold), _blank(bloom))
        # What was drawn before it was made.
        self._lay(self.areas[k], [0.0] * len(self.lines), self.drawn)

    def advance(self, t: float) -> None:
        if t < self.t:
            for area in self.areas:
                if area is not None:
                    area[4].fill(Qt.transparent)
                    area[5].fill(Qt.transparent)
            self.drawn = [0.0] * len(self.lines)
        self.t = t
        reach = [clamp((t - line.start) / line.span) * line.run[-1] for line in self.lines]
        for area in self.areas:
            if area is not None:
                self._lay(area, self.drawn, reach)
        self.drawn = [max(a, b) for a, b in zip(self.drawn, reach, strict=True)]

    def _lay(self, area: tuple, since: list[float], reach: list[float]) -> None:
        """Copy the finished pictures into the area's along each line from since to reach."""
        rect, near, gold, bloom, gold_so_far, bloom_so_far = area
        u = self.u
        path = QPainterPath()
        for i in near:
            if reach[i] > since[i]:
                line = self.lines[i]
                path.addPath(polyline(_between(line.points, line.run, max(0.0, since[i] - 2 * u), reach[i])))
        if path.isEmpty():
            return
        for image, so_far, at, wide in ((gold, gold_so_far, self.scale, 7), (bloom, bloom_so_far, self.scale * 0.5, 40)):
            brush = QBrush(image)
            brush.setTransform(QTransform(1 / at, 0, 0, 1 / at, rect.left(), rect.top()))
            q = QPainter(so_far)
            q.setRenderHint(QPainter.Antialiasing)
            # The finished picture copied in, so going over a part twice changes nothing.
            q.setCompositionMode(QPainter.CompositionMode_Source)
            q.scale(at, at)
            q.translate(-rect.left(), -rect.top())
            q.strokePath(path, QPen(brush, wide * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.end()


def _blank(image: QImage) -> QImage:
    out = QImage(image.size(), QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    return out


def _gilt(rect: QRectF, lines: list[_Line], scale: float, u: float) -> tuple[QImage, QImage]:
    """The gold lines over rect, at scale pixels to the point: the gold, and its warm light at half the
    size."""

    def draw(q: QPainter, at: float) -> None:
        q.scale(at, at)
        q.translate(-rect.left(), -rect.top())
        for line in lines:
            if line.beads:
                q.setPen(Qt.NoPen)
                q.setBrush(QColor("#ffffff"))
                for k in range(int(line.run[-1] / (line.beads * u)) + 1):
                    point, _ = point_at(line.points, line.run, k * line.beads * u)
                    q.drawEllipse(point, line.width * u / 2, line.width * u / 2)
                continue
            q.setBrush(Qt.NoBrush)
            q.setPen(QPen(QColor("#ffffff"), line.width * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.drawPath(line.path)

    w, h = max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale))
    gold = _gild(mask(w, h, lambda q: draw(q, scale)), u * scale)
    half = scale * 0.5
    small = mask(max(1, math.ceil(rect.width() * half)), max(1, math.ceil(rect.height() * half)), lambda q: draw(q, half))
    px = u * half
    light = (blur(small, 2.5 * px) * 0.9 + blur(small, 8 * px) * 0.55 + blur(small, 20 * px) * 0.3)[..., None] * rgb(HONEY)
    return gold, glow(light * 0.85)


def _rose_glass(center: QPointF, radius: float, scale: float, u: float) -> tuple[QRectF, QImage, QRectF, QImage]:
    """The round window's glass, per pixel: an angel in pale gold glass, its wings streaked in feathers,
    on rays of honey and amber, mottled and streaked as old glass is, dark lead where panes meet, brightest in the middle where the light comes through and glowing over the lead;
    and the light it throws round itself."""
    rect = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)
    n = max(8, math.ceil(2 * radius * scale))
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32) + 0.5
    x, y = (xs / n * 2 - 1), (ys / n * 2 - 1)
    rho = np.hypot(x, y)
    rnd = np.random.default_rng(7)

    def shape(points: list[tuple[float, float]]) -> np.ndarray:
        def draw(q: QPainter) -> None:
            q.translate(n / 2, n / 2)
            q.scale(n / 2, n / 2)
            q.setPen(Qt.NoPen)
            q.setBrush(Qt.white)
            q.drawPolygon(QPolygonF([QPointF(px, py) for px, py in points]))

        return mask(n, n, draw)

    outlines = _angel_outlines()
    figure = np.maximum(shape(outlines[2][0]), shape(outlines[3][0]))
    wings = np.maximum(shape(outlines[0][0]), shape(outlines[1][0])) * (1 - figure)
    honey, amber, pale = (rgb(c) for c in ("#ffcf55", "#ec8f22", "#ffe7a0"))
    # Behind the angel, rays of honey and amber glass from its heart, deeper toward the rim, and the
    # light it gives round it.
    fx, fy = x, y + 0.15
    rays = smooth(0.2, 0.8, 0.5 + 0.5 * np.cos(np.arctan2(fy, fx) * 12))
    tint = (amber + (honey - amber) * rays[..., None]) * (1.2 - 0.55 * smooth(0.45, 0.95, rho))[..., None]
    tint = tint + (pale - tint) * (np.exp(-(fx * fx + fy * fy) / 0.12) * 0.6)[..., None]
    # The wings pale gold, streaked in feathers fanning from the shoulders; the robe and head paler,
    # the robe falling in soft folds; the halo glowing.
    fan = 0.5 + 0.5 * np.cos(np.arctan2(y + 0.1, np.abs(x) - 0.12) * 18)
    plume = rgb("#ffcf5e") + (rgb("#fff4d6") - rgb("#ffcf5e")) * (fan * (1 - 0.35 * smooth(0.3, 0.8, np.abs(x))))[..., None]
    tint = tint * (1 - wings[..., None]) + plume * wings[..., None]
    folds = 0.9 + 0.1 * np.cos(x * 40) * smooth(-0.1, 0.4, y)
    robe = rgb("#fffbef") + (rgb("#ffe2a0") - rgb("#fffbef")) * (smooth(-0.3, 0.7, y) * 0.8 + 0.3 * smooth(0.06, 0.3, np.abs(x)))[..., None]
    tint = tint * (1 - figure[..., None]) + (robe * folds[..., None]) * figure[..., None]
    around = np.hypot(x / 0.15, (y + 0.5) / 0.045)
    tint = tint + rgb("#fff1b0") * (np.exp(-((around - 1) ** 2) / 0.3) * 0.5)[..., None]
    # Mottled and streaked as old glass is.
    mottle = noise(n, n, n * 0.06, 3, 11)
    streak = noise(n, n, n * 0.02, 2, 12)
    bright = (0.82 + 0.28 * mottle + 0.08 * streak) * (1.15 - 0.3 * rho) * rnd.uniform(0.97, 1.03)
    # Dark lead where one pane meets the next, under the gold.
    pane = np.where(figure > 0.5, 2, np.where(wings > 0.5, 1, 0))
    seam = np.zeros((n, n), dtype=np.float32)
    seam[1:, :] += pane[1:, :] != pane[:-1, :]
    seam[:, 1:] += pane[:, 1:] != pane[:, :-1]
    lead = np.clip(blur(np.clip(seam, 0, 1), max(0.6, n / 260)) * 2.2, 0, 1)
    color = tint * bright[..., None] * (1 - 0.7 * lead[..., None])
    # Lit from behind, the brightest glass glows over the lead round it.
    hot = np.clip(color - 0.55, 0, None)
    color = color + np.dstack([blur(hot[..., k], max(1.0, n / 90)) for k in range(3)]) * 0.9
    edge = 1 - smooth(0.985, 1.0, rho)
    alpha = edge * (0.9 + 0.08 * mottle)
    glass = picture(color, alpha)
    # Its light, spilled round it: worked out at a quarter of the size, three radii across.
    m = max(8, math.ceil(6 * radius * scale * 0.25))
    ys, xs = np.mgrid[0:m, 0:m].astype(np.float32) + 0.5
    d = np.hypot(xs / m * 2 - 1, ys / m * 2 - 1) * 3
    spill = np.exp(-((np.maximum(d - 0.85, 0)) / 0.4) ** 2) * 0.6 + np.exp(-((np.maximum(d - 0.9, 0)) / 0.8) ** 2) * 0.25
    spill = spill * smooth(0.5, 1.0, d) * 0.75
    halo = glow(rgb(HONEY)[None, None, :] * spill[..., None])
    return rect, glass, QRectF(center.x() - 3 * radius, center.y() - 3 * radius, 6 * radius, 6 * radius), halo


def _wave(x: np.ndarray, cell: float, rnd: np.random.Generator) -> np.ndarray:
    """Smooth value noise along one axis, 0..1, a new value every cell."""
    low = math.floor(float(x.min()) / cell) - 1
    knots = rnd.random(int(math.ceil(float(x.max()) / cell)) - low + 3)
    f = x / cell - low
    i = np.floor(f).astype(int)
    k = f - i
    k = k * k * (3 - 2 * k)
    return knots[i] * (1 - k) + knots[i + 1] * k


def _box(xs: np.ndarray, ys: np.ndarray, rect: QRectF, feather: float) -> np.ndarray:
    """1 inside rect, 0 feather beyond it, smoothly between."""
    out = np.maximum(np.maximum(rect.left() - xs, xs - rect.right()), np.maximum(rect.top() - ys, ys - rect.bottom()))
    return 1 - smooth(-feather * 0.5, feather, out)


def _shafts(width: float, height: float, gap: QRectF, rose: tuple[QPointF, float], u: float) -> tuple[QImage, list[QImage]]:
    """Shafts of light from the round window slanting down toward the lobby, at SOFT size: two sets of
    streaks by angle, to breathe in turn, and where they may show: faint over the names, none over
    the title's words or the button."""
    center, radius = rose
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = xs / SOFT, ys / SOFT
    dx, dy = x - center.x(), y - center.y()
    angle = np.arctan2(dy, dx)
    r = np.hypot(dx, dy)
    # Down and to the left, most of it.
    fan = smooth(1.45, 1.75, angle) * (1 - smooth(2.55, 2.95, angle))
    fall = smooth(radius * 0.8, radius * 1.4, r) * (1 - smooth(0, height * 0.95, r)) ** 1.3
    layers = []
    for seed in (3, 9):
        rnd = np.random.default_rng(seed)
        beams = 0.6 * _wave(angle, 0.05, rnd) + 0.4 * _wave(angle, 0.017, rnd)
        streak = smooth(0.45, 0.85, beams)
        strength = fan * fall * (0.08 + 0.92 * streak)
        tint = rgb("#ffd486") + (rgb("#fff3d6") - rgb("#ffd486")) * (streak * 0.5)[..., None]
        layers.append(glow(tint * (strength * 0.85)[..., None]))
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    words = QRectF(width * 0.42, height * 0.07, width * 0.23, height * 0.14)
    lines = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.24)
    keep = (1 - 0.8 * _box(x, y, names, 50 * u)) * (1 - 0.5 * _box(x, y, lines, 30 * u)) * (1 - _box(x, y, words, 24 * u))
    keep = keep * (1 - _box(x, y, gap.adjusted(-20 * u, -20 * u, 20 * u, 20 * u), 50 * u))
    return picture(np.ones((h, w, 3), dtype=np.float32), keep), layers


def _feather(px: int) -> tuple[QImage, float]:
    """A gold-leaf feather px pixels long, quill on the left pointing right, per pixel: two vanes of
    fine barbs sweeping toward the tip, the odd split where they part, beaten gold that shines in a
    band along each vane and darkens toward its frayed edge, a bright shaft. Also where the quill is,
    as a share of its height."""
    broad, lead, bend = 0.3, 0.42, 0.06
    high = int(px * (broad + bend) * 1.15) + 4
    ys, xs = np.mgrid[0:high, 0:px].astype(np.float32) + 0.5
    s = xs / px
    root = high / 2 - bend * px / 2
    dv = ys - (root + bend * px * s * s)
    profile = smooth(0.0, 0.3, s) ** 0.55 * np.sqrt(np.clip(1 - np.clip((s - 0.36) / 0.64, 0, 1) ** 2.4, 0, 1))
    half = 0.5 * broad * px * profile * np.where(dv < 0, 2 * lead, 2 * (1 - lead))
    r = np.abs(dv) / np.maximum(half, 1e-3)
    rnd = np.random.default_rng(px)
    along = xs - np.abs(dv) * 1.15
    spacing = max(2.0, px / 55)
    barbs = 0.5 + 0.5 * np.cos(along / spacing * 2 * math.pi)
    parts = _wave(along + np.where(dv < 0, 0, px * 3), px / 9, rnd)
    split = smooth(0.8, 0.9, parts) * smooth(0.3, 0.6, r) * smooth(0.15, 0.3, s)
    jag = 0.06 * barbs + 0.08 * _wave(along * 1.7, px / 30, rnd)
    inside = 1 - smooth(0.84 - jag, 1.0 - jag, r)
    alpha = inside * (1 - 0.9 * split) * (0.82 + 0.18 * (1 - r * r)) * (0.5 + 0.5 * smooth(0.02, 0.25, s))
    # Beaten gold: a band of shine along each vane, the upper one brighter, darker to the edge.
    sheen = np.exp(-(((r - 0.38) / 0.2) ** 2)) * np.where(dv < 0, 1.0, 0.65)
    tone = 0.38 + 0.38 * sheen + 0.1 * barbs - 0.22 * smooth(0.6, 1.0, r) + 0.08 * _wave(along, px / 14, rnd)
    color = _ramp(np.clip(tone, 0, 1))
    shaft_w = px * 0.016 * (1 - 0.75 * s) + 0.35
    shaft = (1 - smooth(shaft_w * 0.45, shaft_w, np.abs(dv))) * (1 - smooth(0.9, 0.99, s))
    color = color + (rgb("#fff4cc") - color) * (shaft * 0.8)[..., None]
    alpha = np.maximum(alpha, shaft * 0.95)
    return picture(color, alpha), root / high


def _spark() -> QImage:
    """A mote of light: a white-hot core in a honey glow."""
    n = 64
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32) + 0.5
    d = np.hypot(xs - n / 2, ys - n / 2) / (n / 2)
    light = rgb(HONEY) * (np.exp(-((d / 0.42) ** 2)) * 0.8)[..., None] + rgb("#fffaf0") * (np.exp(-((d / 0.12) ** 2)) * 1.3)[..., None]
    return glow(light * (1 - smooth(0.85, 1.0, d))[..., None])


# Drawing each frame.


def _sharpness(p: QPainter) -> float:
    """Pixels per point where p draws: its screen's and its own scaling."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return round(ratio * math.hypot(p.transform().m11(), p.transform().m12()), 2)


def _flicker(t: float, seed: int) -> float:
    """A candle's light: 0..1, wavering, now and then guttering."""
    k = seed * 1.7
    return clamp(0.62 + 0.16 * math.sin(t * 7.1 + k) + 0.1 * math.sin(t * 12.7 + 2 * k) + 0.07 * math.sin(t * 23.3 + k) + 0.05 * math.sin(t * 3.1 + 3 * k))


def _lay(p: QPainter, image: QImage, x: float, y: float, r: float, alpha: float) -> None:
    if alpha <= 0.01 or r <= 0.2:
        return
    p.setOpacity(clamp(alpha))
    p.drawImage(QRectF(x - r, y - r, 2 * r, 2 * r), image)


def _warmth(p: QPainter, width: float, height: float, u: float) -> None:
    """Warm light at the top and down the sides, as in a candlelit nave; drawn once."""
    top = height * 0.32
    p.fillRect(QRectF(0, 0, width, top), gradient(QPointF(0, 0), QPointF(0, top), ((0, "#ffdf9e", 0.22), (0.4, "#ffcf7a", 0.07), (1, "#ffcf7a", 0))))
    side = 190 * u
    for start, end, rect in (
        (QPointF(0, 0), QPointF(side, 0), QRectF(0, 0, side, height)),
        (QPointF(width, 0), QPointF(width - side, 0), QRectF(width - side, 0, side, height)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, "#ffd88f", 0.2), (0.5, "#ffc870", 0.06), (1, "#ffc870", 0))))
    for cx, cy, r, alpha in ((0.12, 0.1, 480, 0.24), (0.91, 0.15, 420, 0.22)):
        light = QRadialGradient(QPointF(width * cx, height * cy), r * u)
        light.setColorAt(0, col("#ffe2a6", alpha))
        light.setColorAt(0.5, col("#ffcf7a", alpha * 0.35))
        light.setColorAt(1, col("#ffcf7a", 0))
        p.fillRect(QRectF(0, 0, width, height), light)


def _candles(p: QPainter, t: float, width: float, height: float, u: float, a: float) -> None:
    """Candlelight pooled in the two bottom corners, each flickering on its own."""
    if a <= 0.01:
        return
    p.save()
    p.setPen(Qt.NoPen)
    for seed, x in ((1, 0.0), (2, width)):
        k = _flicker(t, seed)
        r = (400 + 30 * k) * u
        pool = QRadialGradient(QPointF(x, height), r)
        pool.setColorAt(0, col("#ffc76a", 0.42 * a * (0.7 + 0.3 * k)))
        pool.setColorAt(0.35, col(EMBER, 0.16 * a * (0.6 + 0.4 * k)))
        pool.setColorAt(1, col(EMBER, 0))
        p.setBrush(pool)
        p.drawEllipse(QPointF(x, height), r, r)
    p.restore()


def _shaft_paint(p: QPainter, t: float, shafts: tuple[QImage, list[QImage]], width: float, height: float, a: float) -> None:
    """The round window's shafts, each set breathing in turn, cut to where they may show on a small
    picture and laid on scaled up."""
    if a <= 0.01:
        return
    keep, layers = shafts
    small = QImage(keep.width(), keep.height(), QImage.Format_ARGB32_Premultiplied)
    small.fill(Qt.transparent)
    q = QPainter(small)
    q.setCompositionMode(QPainter.CompositionMode_Plus)
    for index, layer in enumerate(layers):
        q.setOpacity(clamp(a * (0.55 + 0.45 * math.sin(t * (0.9 + 0.35 * index) + index * 2.4))))
        q.drawImage(0, 0, layer)
    q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    q.setOpacity(1.0)
    q.drawImage(0, 0, keep)
    q.end()
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, width, height), small)
    p.restore()


def _dust(p: QPainter, t: float, dust: list[tuple], center: QPointF, radius: float, spark: QImage, u: float, a: float) -> None:
    """Dust turning slowly in the shafts below the round window, catching the light as it turns."""
    if a <= 0.01:
        return
    base = p.opacity()
    p.save()
    for along, across, turn, depth, r, phase in dust:
        # Placed along the shafts by angle and distance, drifting down and round.
        angle = turn + 0.04 * math.sin(t * 0.5 + phase)
        far = radius * 1.3 + (depth * 380 * u + 18 * u * t) % (380 * u)
        x = center.x() + far * math.cos(angle) + 8 * u * math.sin(t * 0.8 + phase)
        y = center.y() + far * math.sin(angle) * across + 10 * u * t * 0.3
        shine = 0.5 + 0.5 * math.sin(t * along * 2.1 + phase)
        _lay(p, spark, x, y, r * (3 + 2 * shine), base * a * (0.25 + 0.55 * shine))
    p.restore()


def _rose(p: QPainter, t: float, art: tuple, center: QPointF, radius: float, lit: float, a: float, u: float, spark: QImage) -> None:
    """The round window's glass lights from the middle out, flaring as it fills, and its light spills
    round it; the glass is laid on under its tracery."""
    rect, glass, halo_rect, halo = art
    if lit <= 0 or a <= 0.01:
        return
    base = p.opacity()
    flare = ease_out(win(t, 1.8, 2.05)) * (1 - ease_in_out(win(t, 2.05, 2.9)))
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setOpacity(base * a * lit * (0.8 + 0.12 * _flicker(t, 4) + 0.5 * flare))
    p.drawImage(halo_rect, halo)
    p.setOpacity(base * a)
    if lit >= 1:
        p.drawImage(rect, glass)
        # The light behind the glass wavers like candlelight.
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        p.setOpacity(base * a * 0.22 * _flicker(t, 5))
        p.drawImage(rect, glass)
    else:
        brush = QBrush(glass)
        brush.setTransform(QTransform(rect.width() / glass.width(), 0, 0, rect.height() / glass.height(), rect.left(), rect.top()))
        p.setPen(Qt.NoPen)
        p.setBrush(brush)
        reach = radius * lit
        p.drawEllipse(center, reach, reach)
    if flare > 0.01:
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        _lay(p, spark, center.x(), center.y(), radius * 1.1, base * a * flare * 0.7)
    p.restore()


def _flare(p: QPainter, t: float, at: QPointF, when: float, spark: QImage, u: float) -> None:
    """A burst of light at the keystone as the two halves of the frieze meet there."""
    k = ease_out(win(t, when - 0.05, when + 0.1)) * (1 - ease_in_out(win(t, when + 0.1, when + 0.9)))
    if k <= 0.01:
        return
    base = p.opacity()
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    _lay(p, spark, at.x(), at.y(), 70 * u, base * k * 0.8)
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.setOpacity(base)
    star(p, at.x(), at.y(), 30 * u * k, "#fffbea", k, 0.07)
    star(p, at.x(), at.y(), 14 * u * k, "#fffbea", k * 0.8, 0.2)
    p.restore()


def _tracery(p: QPainter, t: float, gilding: _Gilding, ends: float, a: float, flicker: float) -> None:
    """The gold as far as it has been drawn, its light under it; all of it once it is done."""
    if a <= 0.01:
        return
    base = p.opacity()
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    done = t >= ends
    for area in gilding.areas:
        if area is None:
            continue
        rect, _near, gold, bloom, gold_so_far, bloom_so_far = area
        p.setOpacity(base * a * (0.8 + 0.2 * flicker))
        p.drawImage(rect, bloom if done else bloom_so_far)
        p.setOpacity(base * a)
        p.drawImage(rect, gold if done else gold_so_far)
    p.restore()


def _pens(p: QPainter, t: float, lines: list[_Line], spark: QImage, u: float, a: float) -> None:
    """The hot pen of light at the head of each line still drawing, a comet of light behind it."""
    base = p.opacity()
    heads = []
    for line in lines:
        drawn = (t - line.start) / line.span
        if 0 < drawn < 1:
            heads.append((line, drawn * line.run[-1]))
    if not heads or a <= 0.01:
        return
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    for line, at in heads:
        big = 0.6 + 0.2 * line.width
        for back, size, alpha in ((44, 9, 0.18), (26, 11, 0.3), (12, 13, 0.45), (0, 15, 0.85)):
            if at - back * u > 0 or not back:
                point, _ = point_at(line.points, line.run, at - back * u)
                _lay(p, spark, point.x(), point.y(), size * big * u, base * a * alpha)
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.setOpacity(base)
    for line, at in heads:
        if line.width >= 2.2:
            point, _ = point_at(line.points, line.run, at)
            star(p, point.x(), point.y(), 9 * u, "#ffffff", 0.9 * a, 0.1)
    p.restore()


def _glints(p: QPainter, t: float, glints: list[tuple], spark: QImage, u: float, a: float) -> None:
    """Once it is all drawn, light catches the gold and runs along its longest lines."""
    base = p.opacity()
    p.save()
    for when, line, span, back in glints:
        k = win(t, when, when + span)
        if not 0 < k < 1:
            continue
        at = ease_in_out(k) * line.run[-1]
        head, _ = point_at(line.points, line.run, line.run[-1] - at if back else at)
        shine = math.sin(math.pi * k) * a
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        _lay(p, spark, head.x(), head.y(), 16 * u, base * shine * 0.8)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setOpacity(base)
        star(p, head.x(), head.y(), (6 + 7 * shine) * u, "#fffbea", shine, 0.09)
    p.restore()


def _feathers(p: QPainter, t: float, falling: list[tuple], sprite: tuple[QImage, float], a: float) -> None:
    """Gold-leaf feathers drifting down the sides, rocking as they fall and turning about their
    shafts, flashing when they turn their face to the light."""
    if a <= 0.01:
        return
    image, root = sprite
    base = p.opacity()
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for index, (born, x, y, fall, length, phase, rate) in enumerate(falling):
        age = t - born
        if age <= 0:
            continue
        fade = min(1.0, age / 0.6) * a
        swing = math.sin(age * 1.6 + phase)
        cx = x + 16 * (length / 40) * swing
        cy = y + fall * age - 5 * (length / 40) * abs(swing)
        heading = 180 if index % 4 < 2 else 0
        angle = heading + 26 * math.cos(age * 1.6 + phase) * (1 if heading else -1) + 12
        turn = math.cos(age * rate + phase)
        across = math.copysign(0.3 + 0.7 * abs(turn), turn)
        back = math.radians(angle)
        scale = length / image.width()
        p.save()
        p.translate(cx - math.cos(back) * length / 2, cy - math.sin(back) * length / 2)
        p.rotate(angle)
        p.scale(scale, scale * across)
        p.setOpacity(base * fade * (0.7 + 0.3 * abs(turn)))
        p.drawImage(QPointF(0, -root * image.height()), image)
        flash = clamp((abs(turn) - 0.86) / 0.14)
        if flash > 0.01:
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            p.setOpacity(base * fade * flash * 0.55)
            p.drawImage(QPointF(0, -root * image.height()), image)
        p.restore()
    p.restore()


def _motes(p: QPainter, t: float, motes: list[tuple], spark: QImage, u: float, a: float) -> None:
    """Gold motes rising from the candlelight in the bottom corners, swaying and twinkling."""
    if a <= 0.01:
        return
    base = p.opacity()
    p.save()
    for born, x, y, rise, r, phase in motes:
        age = t - born
        if age <= 0 or age > 2.8:
            continue
        fade = min(1.0, age / 0.4) * min(1.0, (2.8 - age) / 1.0) * a
        twinkle = 0.55 + 0.45 * math.sin(age * 6.5 + phase)
        _lay(p, spark, x + 10 * u * math.sin(age * 1.7 + phase), y - rise * age, r * 3.2, base * fade * twinkle)
    p.restore()


# The marks: a gilded frame on the button, a gold rosette, a lancet window of golden glass.

_MADE: dict[tuple, object] = {}


def _made(key: tuple, build):  # noqa: ANN001, ANN202
    """A mark's pictures, made once for its size and sharpness."""
    if key not in _MADE:
        if len(_MADE) > 24:
            _MADE.clear()
        _MADE[key] = build()
    return _MADE[key]


def _ring_lines(cover: QRectF) -> tuple[QPainterPath, QPainterPath]:
    """The frame on the button: a gilded molding just inside its edge and a fine line within it, a
    quatrefoil at each corner, a pointed crest over its middle and a pendant under it, and filigree
    scrolls either side of the crest. Also the molding alone, for the glints to run round."""
    radius = cover.height() * 0.14
    molding = QPainterPath()
    molding.addRoundedRect(cover.adjusted(1.8, 1.8, -1.8, -1.8), radius, radius)
    frame = QPainterPath(molding)
    inner = QPainterPath()
    inner.addRoundedRect(cover.adjusted(5.5, 5.5, -5.5, -5.5), max(1.0, radius - 4), max(1.0, radius - 4))
    frame.addPath(inner)
    unit = cover.height() / 80
    for x, y in ((cover.left(), cover.top()), (cover.right(), cover.top()), (cover.left(), cover.bottom()), (cover.right(), cover.bottom())):
        cx = x + (4.5 if x == cover.left() else -4.5) * unit
        cy = y + (4.5 if y == cover.top() else -4.5) * unit
        frame.addPath(polyline(_foil(cx, cy, 7.5 * unit, 4, math.pi / 4)))
        frame.addPath(polyline(_circle(cx, cy, 1.6 * unit, 8)))
    cx = cover.center().x()
    top, bottom = cover.top() + 1.8, cover.bottom() - 1.8
    for y, sign in ((top, -1), (bottom, 1)):
        rise = 7.5 * unit
        crest = [QPointF(cx - 17 * unit, y), QPointF(cx - 7 * unit, y + sign * rise * 0.55), QPointF(cx, y + sign * rise)]
        crest += [QPointF(cx + 7 * unit, y + sign * rise * 0.55), QPointF(cx + 17 * unit, y)]
        frame.addPath(polyline(catmull(crest, 8)))
        frame.addPath(polyline(_circle(cx, y + sign * rise * 0.25, 1.7 * unit, 8)))
    for side in (-1, 1):
        for k, length in ((0, 30), (1, 20)):
            start = QPointF(cx + side * (21 + 13 * k) * unit, top + 0.5)
            heading = 0.0 if side > 0 else math.pi
            curl = _scroll(start, heading + side * 0.25, length * unit, side * (4.8 + 0.4 * k))
            frame.addPath(polyline(curl))
            start = QPointF(cx + side * (21 + 13 * k) * unit, bottom - 0.5)
            curl = _scroll(start, heading - side * 0.25, length * unit, -side * (4.8 + 0.4 * k))
            frame.addPath(polyline(curl))
    return frame, molding


def _ring_art(window: QRectF, cover: QRectF, scale: float) -> tuple[QImage, QImage, list[QPointF], list[float]]:
    """The frame on the button in gold, its warm glow, and the molding's points for the glints."""
    frame, molding = _ring_lines(cover)
    unit = cover.height() / 80
    w, h = max(1, math.ceil(window.width() * scale)), max(1, math.ceil(window.height() * scale))

    def draw(q: QPainter, thick: float, lines: QPainterPath) -> None:
        q.scale(scale, scale)
        q.translate(-window.left(), -window.top())
        q.setPen(QPen(QColor("#ffffff"), thick, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        q.drawPath(lines)

    cover_px = mask(w, h, lambda q: draw(q, 1.5 * unit, frame))
    cover_px = np.maximum(cover_px, mask(w, h, lambda q: draw(q, 3.2 * unit, molding)))
    gold = _gild(cover_px, unit * scale, 0.5)
    px = unit * scale
    light = blur(cover_px, 2.0 * px) * 0.7 + blur(cover_px, 5 * px) * 0.6
    halo = glow(rgb(HONEY)[None, None, :] * light[..., None])
    points = [QPointF(point) for point in molding.toSubpathPolygons()[0]]
    return gold, halo, points, lengths(points)


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A gilded frame on the button, breathing warm light, two glints running round it."""
    scale = _sharpness(p)
    window = cover.adjusted(-9, -9, 9, 9)
    key = ("ring", round(cover.width(), 1), round(cover.height(), 1), scale)
    gold, halo, points, run = _made(key, lambda: _ring_art(window, cover, scale))
    spark = _made(("spark",), _spark)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setOpacity(0.75 + 0.25 * math.sin(t * 2.0))
    p.drawImage(window, halo)
    p.setOpacity(1.0)
    p.drawImage(window, gold)
    unit = cover.height() / 80
    for offset in (0.0, 0.5):
        k = (t * 0.16 + offset) % 1.0
        head, _ = point_at(points, run, k * run[-1])
        shine = 0.6 + 0.4 * math.sin(t * 3.0 + offset * 9)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        _lay(p, spark, head.x(), head.y(), 11 * unit, 0.75 * shine)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setOpacity(1.0)
        star(p, head.x(), head.y(), (5 + 3 * shine) * unit, "#fffbea", shine, 0.1)


def _rosette(side: int) -> tuple[QImage, QImage]:
    """A gold rosette side pixels across, per pixel: a rim of twelve foils, eight carved petals with a
    vein each, and a cabochon of honey glass in the middle; and its warm halo, twice as wide."""
    ys, xs = np.mgrid[0:side, 0:side].astype(np.float32) + 0.5
    x, y = (xs / side * 2 - 1), (ys / side * 2 - 1)
    rho = np.hypot(x, y)
    theta = np.arctan2(y, x)
    px = side / 2
    rim_r = 0.9 + 0.1 * np.abs(np.cos(6 * theta)) ** 0.5
    cover = 1 - smooth(rim_r - 1.2 / px, rim_r, rho)
    # Heights: the plate, a raised ring of foils at its edge, the petals, the boss.
    plate = 0.25 * cover
    ring_h = 0.35 * np.exp(-(((rho - (rim_r - 0.08)) / 0.06) ** 2)) * cover
    phi = (theta + math.pi / 8) % (math.pi / 4) - math.pi / 8
    reach = np.clip((rho - 0.26) / 0.48, 0, 1)
    breadth = np.sin(math.pi * reach ** 0.8) * (math.pi / 8) * 0.95
    petal = np.clip(1 - (np.abs(phi) / np.maximum(breadth, 1e-3)) ** 2, 0, 1) * (rho > 0.26) * (rho < 0.74)
    vein = np.exp(-((phi * rho / 0.018) ** 2)) * petal
    petals = 0.32 * np.sqrt(petal) + 0.06 * vein
    boss = rho < 0.27
    height = blur(plate + ring_h + petals, max(0.6, side / 90))
    color = _metal(height, side * 0.35)
    # The boss: honey glass, domed, lit from the upper left with a bright window in it.
    dome = np.sqrt(np.clip(1 - (rho / 0.27) ** 2, 0, 1))
    glass = rgb("#f0a63a") * (0.55 + 0.45 * dome)[..., None] + rgb("#fff1c2") * (np.exp(-(((x + 0.09) ** 2 + (y + 0.1) ** 2) / 0.006)) * 1.2)[..., None]
    glass = glass + rgb("#ffd56e") * (np.exp(-(((x - 0.06) ** 2 + (y - 0.08) ** 2) / 0.02)) * 0.5)[..., None]
    bezel = np.exp(-(((rho - 0.27) / 0.025) ** 2))
    color = np.where(boss[..., None], glass, color)
    color = color * (1 - 0.55 * bezel)[..., None] + _ramp(np.full(rho.shape, 0.8)) * (bezel * 0.55)[..., None]
    gold = picture(color, cover)
    big = side * 2
    ys, xs = np.mgrid[0:big, 0:big].astype(np.float32) + 0.5
    d = np.hypot(xs / big * 2 - 1, ys / big * 2 - 1) * 2
    halo = glow(rgb(HONEY)[None, None, :] * (np.exp(-((np.maximum(d - 0.7, 0) / 0.3) ** 2)) * 0.75 * smooth(0.4, 0.9, d))[..., None])
    return gold, halo


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A gold rosette in a warm halo, a glint walking round its foils and its glass boss glowing."""
    scale = _sharpness(p)
    side = max(16, math.ceil(box.width() * scale))
    gold, halo = _made(("rosette", side), lambda: _rosette(side))
    spark = _made(("spark",), _spark)
    c = box.center()
    r = box.width() / 2
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setOpacity(0.7 + 0.3 * math.sin(t * 2.0 + 1.0))
    p.drawImage(QRectF(c.x() - 2 * r, c.y() - 2 * r, 4 * r, 4 * r), halo)
    p.setOpacity(1.0)
    p.drawImage(box, gold)
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    _lay(p, spark, c.x(), c.y(), r * 0.45, 0.25 + 0.2 * math.sin(t * 2.6))
    turn = t * 1.1 - 2.2
    gx, gy = c.x() + r * 0.86 * math.cos(turn), c.y() + r * 0.86 * math.sin(turn)
    shine = 0.55 + 0.45 * math.sin(t * 2.3)
    _lay(p, spark, gx, gy, r * 0.42, 0.7 * shine)
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.setOpacity(1.0)
    star(p, gx, gy, r * (0.22 + 0.12 * shine), "#fffbea", shine, 0.1)


def _lancet(rect: QRectF) -> QPainterPath:
    """The card's outline: straight sides and a flat foot under an ogee arch, its shoulders swelling
    out and its two sides sweeping up to a sharp point."""
    left, right = rect.left() + 1.5, rect.right() - 1.5
    mid = (left + right) / 2
    apex = rect.top() + 9.0
    spring = rect.top() + CARD_TOP + 2
    half, rise = (right - left) / 2, spring - apex
    path = QPainterPath(QPointF(left, rect.bottom() - 1.5))
    path.lineTo(left, spring)
    path.cubicTo(QPointF(left, spring - rise * 0.55), QPointF(mid - half * 0.1, apex + rise * 0.62), QPointF(mid, apex))
    path.cubicTo(QPointF(mid + half * 0.1, apex + rise * 0.62), QPointF(right, spring - rise * 0.55), QPointF(right, spring))
    path.lineTo(right, rect.bottom() - 1.5)
    path.closeSubpath()
    return path


def _card_art(rect: QRectF, scale: float) -> tuple[QImage, QImage]:
    """The card per pixel: golden glass, mottled and lit from behind, brightest at the top, in a gold
    frame with a fine line inside it; a quatrefoil in the arch's head, a star on its tip and a sill at
    its foot. And the gold alone, for the glint that crosses it."""
    w, h = max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale))
    outline = _lancet(rect)
    inner = QPainterPath(outline)
    trim = QPainterPath()
    shrink = QTransform()
    c = outline.boundingRect().center()
    inset = 4.0
    bound = outline.boundingRect()
    shrink.translate(c.x(), c.y() + 1.0)
    shrink.scale((bound.width() - 2 * inset) / bound.width(), (bound.height() - 2 * inset) / bound.height())
    shrink.translate(-c.x(), -c.y())
    inner = shrink.map(outline)
    head = rect.top() + CARD_TOP - 5.5
    mid = rect.center().x()
    trim.addPath(polyline(_circle(mid, head, 6.6, 32)))
    trim.addPath(polyline(_foil(mid, head, 5.4, 4, math.pi / 4)))
    sill = rect.bottom() - 4.5
    trim.moveTo(rect.left() + 4, sill)
    trim.lineTo(rect.right() - 4, sill)

    def draw(q: QPainter, paint) -> None:  # noqa: ANN001
        q.scale(scale, scale)
        q.translate(-rect.left(), -rect.top())
        paint(q)

    def strokes(q: QPainter) -> None:
        q.setBrush(Qt.NoBrush)
        for path, thick in ((outline, 2.6), (inner, 1.0), (trim, 1.1)):
            q.setPen(QPen(QColor("#ffffff"), thick, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.drawPath(path)

    def fill(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#ffffff"))
        q.drawPath(outline)

    lines = mask(w, h, lambda q: draw(q, strokes))
    # The star on the arch's tip, raised gold.
    tip = _star_height(w, h, (mid - rect.left()) * scale, 6.5 * scale, 6.5 * scale)
    lines = np.maximum(lines, np.clip(tip * 4, 0, 1))
    pane = mask(w, h, lambda q: draw(q, fill))
    ys, xs = (np.mgrid[0:h, 0:w].astype(np.float32) + 0.5) / scale
    mottle = noise(w, h, max(4.0, 18 * scale), 3, 21)
    down = ys / rect.height()
    tint = rgb("#fff4d2") + (rgb(LOOK["card"][1]) - rgb("#fff4d2")) * smooth(0.0, 1.0, down)[..., None]
    # Quarries: the glass under the arch leaded in tall diamonds, faintly.
    cell = 12.0
    a, b = (xs + ys * 0.62) / cell, (xs - ys * 0.62) / cell
    lattice = np.maximum(np.exp(-((np.abs(a - np.round(a)) * cell / 0.5) ** 2)), np.exp(-((np.abs(b - np.round(b)) * cell / 0.5) ** 2)))
    lattice = lattice * smooth(CARD_TOP + 1, CARD_TOP + 4, ys)
    glass = tint * (0.93 + 0.12 * mottle - 0.16 * lattice)[..., None]
    height = blur(lines, max(0.6, 0.7 * scale)) + tip * 0.6
    gold = _metal(height, 2.4 * scale)
    under = _shift(blur(lines, max(0.6, scale)), max(1, round(scale)), 0) * 0.35 * (1 - lines)
    color = glass * (1 - lines)[..., None] + gold * lines[..., None]
    color = color * (1 - under)[..., None] + rgb("#6b4410") * under[..., None]
    alpha = np.clip(np.maximum(pane * 0.97, lines), 0, 1)
    return picture(color, alpha), picture(_metal(height, 2.4 * scale), lines)


def _star_height(w: int, h: int, cx: float, cy: float, r: float) -> np.ndarray:
    """A four-point star r pixels long, as a height (0 outside, 1 at its middle): cut, with ridges
    along its arms."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = np.abs(xs - cx) / r, np.abs(ys - cy) / r
    s = np.sqrt(x) + np.sqrt(y)
    return np.clip(1 - s, 0, 1)


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """The lancet window: its glass with the light behind it drifting slowly, and now and then a glint
    crossing its gold."""
    scale = _sharpness(p)
    key = ("card", round(rect.width(), 1), round(rect.height(), 1), scale)
    art, gold = _made(key, lambda: _card_art(rect, scale))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(rect, art)
    # The light behind the glass, drifting across it.
    drift = rect.left() + rect.width() * (0.5 + 0.4 * math.sin(t * 0.5))
    light = QRadialGradient(QPointF(drift, rect.top() + rect.height() * 0.35), rect.width() * 0.6)
    light.setColorAt(0, col("#fffbe8", 0.32))
    light.setColorAt(1, col("#fffbe8", 0))
    p.save()
    p.setClipPath(_lancet(rect))
    p.setPen(Qt.NoPen)
    p.setBrush(light)
    p.drawRect(rect)
    p.restore()
    # A glint crossing the gold every few seconds.
    k = (t % 3.6) / 1.2
    if k < 1:
        band = QImage(gold.size(), QImage.Format_ARGB32_Premultiplied)
        band.fill(Qt.transparent)
        q = QPainter(band)
        q.drawImage(0, 0, gold)
        q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        x = (-0.3 + 1.6 * ease_in_out(k)) * band.width()
        q.fillRect(band.rect(), gradient(QPointF(x - band.width() * 0.25, 0), QPointF(x + band.width() * 0.25, band.height()), ((0, "#ffffff", 0), (0.5, "#ffffff", 1), (1, "#ffffff", 0))))
        q.end()
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        p.setOpacity(0.7)
        p.drawImage(rect, band)


def lead(size: float, index: int) -> QPixmap:
    """A gold four-point star, cut and raised, with a fine dark edge so it stands out on the glass."""
    ratio = 3.0
    n = max(8, round(size * ratio))
    height = _star_height(n, n, n / 2, n / 2, n * 0.42)
    cover = np.clip(height * 9, 0, 1)
    color = _metal(height * 1.0, n * 0.9)
    edge = np.clip(blur(cover, max(0.6, n / 40)) * 1.6, 0, 1) * (1 - cover)
    total = cover + edge * 0.7
    color = (color * cover[..., None] + rgb("#4a2c06") * (edge * 0.7)[..., None]) / np.maximum(total, 1e-4)[..., None]
    image = QPixmap.fromImage(picture(color, total))
    image.setDevicePixelRatio(ratio)
    return image
