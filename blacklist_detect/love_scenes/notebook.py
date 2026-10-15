"""风翻笔记: the wind turns 吴邪's notebook, drawn by hand in pencil and watercolour, for a 小说家-吴邪 player.

A breeze arrives as six 手书 speed lines in chalk and mint pencil, curling at their ends, with mint
watercolour ribbons sweeping in along the top, the lane, the left margin and low either side of the
gap, and bamboo leaves tumbling on it. 吴邪's brown leather notebook (its strap and red seal) tumbles in
along the lane between the rows, flips open in the left margin and riffles as it drifts on; the wind
snaps it shut and whisks it off, its leaves fanning out of its edge. One loose-leaf page slips out and
the wind lays it across the screen, left to right: celadon paper washed mint, its teal rules, red
margin line and binder holes, its leading edge bending and sagging with a shadow ahead of it, its top
corner curling over as a roll. Pencil sketches draw themselves in its wake for half a second each and
smear away: a 吴山居 moon window with bamboo behind it and the 蛇眉铜鱼 three-fish ring, bamboo and
西湖's ripples. Then loose leaves, mint-washed paper each with a little graphite doodle, stream along
the free bands trailing wide mint watercolour and hatching, crossing a name row only straight and
fast between two names; a mint-into-teal watercolour ribbon loops round the cards on a gust and the
leaves ride it home into the notebook, which blows back in along the top, snaps shut and is carried
off. Pencil doodle stars pop where a leaf flips over. The ribbon dries to its edges and drifts out,
the wind curls are rubbed out and the last bamboo leaves drift away.

Lines boil as drawn lines do (three drawings of each, ten times a second), drawn things move on twos,
colour is hatching and watercolour, and the grain lives on the paper and in the washes. The washes are
soft and drawn at one pixel per point; the line work is drawn sharp (paint.sharp). Nothing translucent
is over a name at more than about 12%, and nothing is drawn in the gap.

Its marks: the card is a notebook page with faint teal ruled lines, a mint-washed deckle, a boiling
pencil border and a leather spine with its strap and seal down its left, a bamboo sprig lying across
its top and a bamboo leaf before each name; the ring a pencil loop round the button drawn twice, as a
word is circled in notes; the badge the three-fish ring in pencil, washed bronze and verdigris, turning
slowly.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QPolygonF,
    QTransform,
)

from blacklist_detect.love_scenes.draw import clamp, ease_in, ease_in_out, ease_out, mix, win
from blacklist_detect.love_scenes.light import blur, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from collections.abc import Callable

    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# The washes are soft: drawn at one pixel per point at most and scaled up; the pencil work is drawn
# sharp on top (paint.sharp).
MAX_RATIO = 1.0
# Her palette: the celadon-mint sheet, mint and teal pencil and wash, celadon, white paper, graphite
# (on paper only), chalk pencil (on the game), the jacket's sage and olive, the notebook's leather and
# its line, the seal's muted red, the badge's bronze and verdigris and the swirl's yellow-green.
SHEET = "#e3f1ea"
MINT = "#a8dcc9"
TEAL = "#78c0c3"
CELADON = "#bbd6d2"
PAPER = "#fbf9f3"
GRAPHITE = "#4a4f54"
SOFT = "#8a9096"
CHALK = "#f3f0e6"
SAGE = "#83867d"
OLIVE = "#606158"
LEATHER = "#8a6e55"
HIDE = "#50463c"
SEAL = "#c4554d"
BRONZE = "#a88b5c"
VERDIGRIS = "#6fa595"
SWIRL = "#97be76"
# Watercolour laid straight on the dark game: the same mint and teal, more pigment in them.
WET = "#74d6b4"
WET_LIGHT = "#b8eed9"
WET_TEAL = "#4fb2b4"
INK = "#3e4347"
LOOK = {
    "glow": (120, 192, 195),
    "rim": MINT,
    "band": (TEAL, MINT),
    "card": (PAPER, "#f1f4ee"),
    "edge": TEAL,
    "ink": INK,
    "flowers": ((PAPER, MINT, TEAL), (PAPER, CELADON, SAGE)),
    "disc": (PAPER, CELADON),
    "heart": (MINT, TEAL),
    "deep": TEAL,
    "deep_glow": (100, 180, 180),
}
MARKS_ANIMATED = True
# Room over the card for the bamboo sprig lying across its top.
CARD_TOP = 13
# The leather spine down the card's left takes room there.
CARD_PAD = (24, 9, 13, 9)
CARD_FONT = "KaiTi"

# Lines are drawn again, a little differently, BOIL times a second; drawn things move TWOS times a second.
BOIL = 10
TWOS = 12
# The page is laid across the screen over SWEEP.
SWEEP = (1.0, 2.15)
# The sheet creeps on with the wind, points a second.
CREEP = 80.0
# The ribbon's gust: its head goes round the loop over GUST; its tail follows TAIL seconds behind.
GUST = (3.2, 4.35)
TAIL = 0.34
# The notebook tumbles in along the lane over TUMBLE and opens; it snaps shut at SHUT, carried on by
# the gust.
TUMBLE = (0.25, 0.55)
# The wind snaps it shut at AWAY and whisks it off along the lane.
AWAY = 1.0
SHUT = 4.3


def make(stage: Stage):  # noqa: ANN201
    plan = _Plan(stage)
    u = plan.u
    tooth = _Tooth(u)
    near, rest = _cut(plan)
    page = _Page(plan)
    sketches = _sketches(plan, tooth)
    speed = _speed_lines(plan, random.Random(3))
    book = _Book(plan, tooth)
    leaves = _leaves(plan, book, tooth)
    trails = _Trails(plan, leaves)
    ribbon = _gust(plan)
    breezes = _breezes(plan)
    curls = _curls(plan, ribbon, random.Random(17))
    for line in (*speed, *curls):
        line.warm()
    stars = _stars(plan, leaves, tooth)
    bamboo = _bamboo(plan, tooth)
    layer = QImage(plan.pw, plan.ph, QImage.Format_ARGB32_Premultiplied)

    def washes(p: QPainter, t: float) -> None:
        """The soft parts in one layer, rubbed off the names and the gap, then laid on."""
        if not (0 < t < DURATION):
            return
        layer.fill(Qt.transparent)
        q = QPainter(layer)
        q.setRenderHint(QPainter.Antialiasing)
        q.setRenderHint(QPainter.SmoothPixmapTransform)
        # Only the part drawn on is rubbed and laid on.
        drawn = _union(page.paint(q, t), trails.paint(q, t), ribbon.paint(q, t), *(breeze.paint(q, t) for breeze in breezes))
        drawn = _pixels(drawn, plan)
        if not drawn.isEmpty():
            q.setCompositionMode(QPainter.CompositionMode_DestinationOut)
            q.drawImage(drawn, near, drawn)
            q.drawImage(drawn, rest, drawn)
        q.end()
        if not drawn.isEmpty():
            p.drawImage(drawn, layer, drawn)

    def lines(p: QPainter, t: float) -> None:
        """The pencil work, sharp."""
        if t <= 0 or t >= DURATION:
            return
        v = int(t * BOIL) % 3
        tq = math.floor(t * TWOS) / TWOS
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        for sketch in sketches:
            sketch.paint(p, t, tq, v)
        for line in speed:
            line.paint(p, tq, v, tooth)
        for curl in curls:
            curl.paint(p, tq, v, tooth)
        book.paint(p, t, tq, v)
        for leaf in leaves:
            leaf.paint(p, tq, v)
        for star in stars:
            star.paint(p, tq, v)
        for drift in bamboo:
            drift.paint(p, tq, v)
        p.restore()

    def paint(p: QPainter, t: float, sharp: bool = True) -> None:
        washes(p, t)
        if sharp:
            lines(p, t)

    paint.sharp = lines
    return paint


# Where things go ------------------------------------------------------------------------------


class _Plan:
    """The stage's bands, from where its names are: the two name rows and their keeps, the lane
    between them, the margins either side, the low band either side of the gap, the title's place.
    Positions across the screen are shares of its width (design x times sx); sizes are in u."""

    def __init__(self, stage: Stage) -> None:
        from blacklist_detect.love_scenes import DESIGN

        self.stage = stage
        self.w, self.h, self.gap = stage.width, stage.height, stage.gap
        self.u = u = stage.unit()
        self.sx, self.sy = self.w / DESIGN[0], self.h / DESIGN[1]
        self.pw, self.ph = max(1, math.ceil(self.w)), max(1, math.ceil(self.h))
        self.names = names = stage.names()
        middle = sum(n.center().y() for n in names) / len(names)
        rows = [r for r in ([n for n in names if n.center().y() < middle], [n for n in names if n.center().y() >= middle]) if r]
        if len(rows) < 2:
            rows = [names, names]
        self.rows = [sorted(row, key=lambda n: n.left()) for row in rows]
        self.grow, self.feather = 8 * u, 10 * u
        out = self.grow + self.feather
        self.keep1 = (min(n.top() for n in rows[0]) - out, max(n.bottom() for n in rows[0]) + out)
        self.keep2 = (min(n.top() for n in rows[1]) - out, max(n.bottom() for n in rows[1]) + out)
        self.left = max(20 * u, min(n.left() for n in names) - out)
        self.right = min(self.w - 20 * u, max(n.right() for n in names) + out)
        # The lane between the rows, the low band under row 2, and the margins' middles.
        self.lane = (self.keep1[1] + self.keep2[0]) / 2
        self.lane_room = self.keep2[0] - self.keep1[1]
        self.low = (self.keep2[1] + self.h) / 2
        self.left_x = self.left / 2
        self.right_x = (self.right + self.w) / 2
        # The title, as the lobby draws it.
        self.title = QRectF(self.x(656), self.y(63), self.x(1069) - self.x(656), self.y(251) - self.y(63))

    def between(self, x: float, row: int) -> float:
        """The middle of the space between two names of a row (0 or 1), the one nearest x."""
        names = self.rows[row]
        gaps = [(a.right() + b.left()) / 2 for a, b in zip(names, names[1:], strict=False)]
        return min(gaps, key=lambda g: abs(g - x)) if gaps else x

    def x(self, x: float) -> float:
        return x * self.sx

    def y(self, y: float) -> float:
        return y * self.sy

    def p(self, x: float, y: float) -> tuple[float, float]:
        return (x * self.sx, y * self.sy)

    def keep_map(self) -> np.ndarray:
        """How much each pixel is in a name's keep: 1 within 8 pt of the name, fading out over 10 more."""
        keep = np.zeros((self.ph, self.pw), dtype=np.float32)
        out = self.grow + self.feather
        for r in self.names:
            x0, x1 = max(0, int(r.left() - out)), min(self.pw, math.ceil(r.right() + out))
            y0, y1 = max(0, int(r.top() - out)), min(self.ph, math.ceil(r.bottom() + out))
            if x1 <= x0 or y1 <= y0:
                continue
            xs = np.arange(x0, x1, dtype=np.float32) + 0.5
            ys = np.arange(y0, y1, dtype=np.float32) + 0.5
            dx = np.maximum(np.maximum(r.left() - self.grow - xs, xs - r.right() - self.grow), 0)
            dy = np.maximum(np.maximum(r.top() - self.grow - ys, ys - r.bottom() - self.grow), 0)
            d = np.hypot(dx[None, :], dy[:, None])
            keep[y0:y1, x0:x1] = np.maximum(keep[y0:y1, x0:x1], smooth(self.feather, 0, d))
        return keep

    def in_keep(self, x: float, y: float, pad: float = 0.0) -> bool:
        out = self.grow + self.feather + pad
        return any(r.adjusted(-out, -out, out, out).contains(QPointF(x, y)) for r in self.names)

    def near_gap(self, x: float, y: float, pad: float) -> bool:
        return self.gap.adjusted(-pad, -pad, pad, pad).contains(QPointF(x, y))


def _union(*rects: QRectF) -> QRectF:
    """The box round all of rects that are not empty."""
    out = QRectF()
    for rect in rects:
        if not rect.isEmpty():
            out = rect if out.isEmpty() else out.united(rect)
    return out


def _pixels(rect: QRectF, plan: _Plan) -> QRectF:
    """rect grown to whole pixels, a little round, and kept on the stage."""
    if rect.isEmpty():
        return QRectF()
    out = QRectF(math.floor(rect.left()) - 2, math.floor(rect.top()) - 2, math.ceil(rect.width()) + 5, math.ceil(rect.height()) + 5)
    return out.intersected(QRectF(0, 0, plan.pw, plan.ph))


def _creep(u: float, t: float) -> QPointF:
    """Where the sheet has crept to t seconds in: on with the wind, sagging and lifting a little."""
    k = t - SWEEP[0]
    # It lifts and settles on the air as it creeps, so even its long top edge never holds still.
    return QPointF(CREEP * u * k, 14 * u - 16 * u * k + 5 * u * math.sin(k * 4.4) + 2.5 * u * math.sin(k * 9.3))


def _cut(plan: _Plan) -> tuple[QImage, QImage]:
    """What is rubbed off the washes: over the names, most of the strong ones, thinning irregularly as
    a wash does near them, never in a rectangle; then about half of everything, the faint sheet too, so
    nothing translucent keeps more than about 12% there; and in the gap all of everything, easing in
    over a ragged edge round it."""
    u = plan.u
    keep = plan.keep_map()
    def coarse(scale: float, seed: int) -> np.ndarray:
        # Soft noise, worked out at half size and doubled up: it only shapes a ragged edge.
        half = noise((plan.pw + 1) // 2, (plan.ph + 1) // 2, scale / 2, 3, seed)
        return np.repeat(np.repeat(half, 2, axis=0), 2, axis=1)[: plan.ph, : plan.pw]

    jag = coarse(9 * u, 5)
    patches = coarse(24 * u, 7)
    spread = np.maximum(keep, blur(keep, 16 * u) * 1.7)
    # Irregular round a name, in ragged patches as a wash thins, but all of it over the name itself.
    near = np.maximum(smooth(0.15, 0.95, spread + 1.1 * (patches - 0.5) + 0.35 * (jag - 0.5)), smooth(0.6, 1.0, keep)) * 0.9
    black = np.zeros((plan.ph, plan.pw, 3), dtype=np.float32)
    gap = plan.gap
    xs = np.arange(plan.pw, dtype=np.float32)[None, :] + 0.5
    ys = np.arange(plan.ph, dtype=np.float32)[:, None] + 0.5
    dx = np.maximum(np.maximum(gap.left() - xs, xs - gap.right()), 0)
    dy = np.maximum(np.maximum(gap.top() - ys, ys - gap.bottom()), 0)
    d = np.sqrt(dx * dx + dy * dy) + 8 * u * (jag - 0.5)
    bare = smooth(26 * u, 4 * u, d)
    # The sheet's thinning and the gap rubbed off in one go.
    return picture(black, near), picture(black, 1 - (1 - near * 0.66) * (1 - bare))


# Pencil ---------------------------------------------------------------------------------------


class _Tooth:
    """Pencil brushes: each color laid through the paper's tooth, a baked grain the pencil skips
    over in its pits, so the line is broken and grainy as a real one is."""

    def __init__(self, u: float) -> None:
        size = 96
        rnd = np.random.default_rng(29)
        spectrum = np.fft.fft2(rnd.random((size, size)))
        fy = np.fft.fftfreq(size)[:, None]
        fx = np.fft.fftfreq(size)[None, :]
        a, b = (fx + fy) / 1.414, (fx - fy) / 1.414
        # Fine grain, drawn out a little along the hand's slant.
        n = np.real(np.fft.ifft2(spectrum * np.exp(-((a / 0.2) ** 2 + (b / 0.36) ** 2))))
        n = (n - n.mean()) / (n.std() + 1e-6)
        self.alpha = np.clip(0.8 + 0.32 * n, 0.12, 1.0).astype(np.float32)
        self._brushes: dict[tuple[str, float], QBrush] = {}

    def brush(self, color: str, strength: float = 1.0) -> QBrush:
        key = (color, round(strength, 2))
        if key not in self._brushes:
            shape = self.alpha.shape
            image = picture(np.broadcast_to(rgb(color), (*shape, 3)).copy(), self.alpha * strength)
            self._brushes[key] = QBrush(image)
        return self._brushes[key]


def _even(points: np.ndarray, step: float, closed: bool = False) -> np.ndarray:
    """Points along a line every step apart."""
    points = np.asarray(points, dtype=np.float64)
    if closed:
        points = np.vstack([points, points[:1]])
    seg = np.hypot(*np.diff(points, axis=0).T)
    points = np.vstack([points[:1], points[1:][seg > 1e-9]])
    s = np.concatenate([[0.0], np.cumsum(seg[seg > 1e-9])])
    at = np.linspace(0, s[-1], max(3, int(s[-1] / step) + 1))
    out = np.column_stack([np.interp(at, s, points[:, 0]), np.interp(at, s, points[:, 1])])
    return out[:-1] if closed else out


def _along(points: np.ndarray) -> np.ndarray:
    """How far along the line each point is."""
    return np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(points, axis=0).T))])


def _normals(points: np.ndarray) -> np.ndarray:
    """Each point's sideways unit, right of the way the line goes on a screen."""
    d = np.gradient(points, axis=0)
    d = d / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)[:, None]
    return np.column_stack([-d[:, 1], d[:, 0]])


def _tremor(s: np.ndarray, rnd: random.Random, amp: float, wave: float) -> np.ndarray:
    """A hand's slow tremor along a line, s along it: smooth, irregular, about amp at most."""
    out = np.zeros_like(s)
    for k, weight in ((1.0, 0.6), (2.3, 0.28), (5.2, 0.12)):
        out += weight * np.sin(2 * math.pi * s / (wave / k) + rnd.uniform(0, 2 * math.pi))
    return out * amp


def _spline(points: list[tuple[float, float]] | np.ndarray, step: float) -> np.ndarray:
    """A smooth line through points (Catmull-Rom), evenly spaced step apart."""
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 3:
        return _even(pts, step)
    ext = np.vstack([pts[0], pts, pts[-1]])
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        n = max(2, int(np.hypot(*(p2 - p1)) / max(step * 0.5, 1e-6)))
        k = np.linspace(0, 1, n, endpoint=False)[:, None]
        out.append(0.5 * (2 * p1 + (-p0 + p2) * k + (2 * p0 - 5 * p1 + 4 * p2 - p3) * k * k + (-p0 + 3 * p1 - 3 * p2 + p3) * k ** 3))
    out.append(pts[-1:])
    return _even(np.vstack(out), step)


def _poly(points: np.ndarray) -> QPolygonF:
    return QPolygonF([QPointF(x, y) for x, y in points.tolist()])


def _ribbon(points: np.ndarray, widths: np.ndarray) -> QPainterPath:
    """A pencil line of varying width through points, as its outline."""
    side = _normals(points) * (widths / 2)[:, None]
    path = QPainterPath()
    path.addPolygon(_poly(np.vstack([points + side, (points - side)[::-1]])))
    path.closeSubpath()
    path.setFillRule(Qt.WindingFill)
    return path


def _band(points: np.ndarray, half: float | np.ndarray) -> QPainterPath:
    """The area within half of a line, as a clip: every few points of it, a clip need not be fine."""
    if len(points) < 2:
        return QPainterPath()
    half = np.broadcast_to(np.asarray(half, dtype=np.float64), (len(points),))
    keep = np.unique(np.append(np.arange(0, len(points), 4), len(points) - 1))
    return _ribbon(points[keep], half[keep] * 2)


class _Stroke:
    """One pencil line: three drawings of it, a point or so apart (a hand never draws the same line
    twice), each pressing harder and lighter along it and tapering where the pencil lands and lifts;
    any stretch of it can be drawn, for a line drawing on or being rubbed out."""

    def __init__(self, points, width: float, rnd: random.Random, u: float, wobble: float = 0.4, ends: tuple[float, float] = (4.0, 7.0)) -> None:  # noqa: ANN001
        pts = _even(np.asarray(points, dtype=np.float64), max(0.5, 1.1 * u))
        s = _along(pts)
        self.length = float(s[-1])
        pts = pts + _normals(pts) * _tremor(s, rnd, wobble * u, 150 * u)[:, None]
        taper = np.clip(s / (ends[0] * width), 0, 1) ** 0.6 * np.clip((self.length - s) / (ends[1] * width), 0, 1) ** 0.6
        self.widths = width * (0.82 + _tremor(s, rnd, 0.22, 70 * u)) * np.maximum(taper, 0.1)
        self.width = width
        self.variants = []
        for _ in range(3):
            shift = np.array([rnd.uniform(-0.45, 0.45), rnd.uniform(-0.45, 0.45)]) * u
            self.variants.append(pts + _normals(pts) * _tremor(s, rnd, 0.7 * u, 24 * u)[:, None] + shift)
        self.s = s
        self._paths: dict[tuple, QPainterPath | None] = {}

    def path(self, v: int, a: float = 0.0, b: float = 1.0) -> QPainterPath | None:
        a, b = clamp(math.floor(a * 40) / 40), clamp(math.ceil(b * 40) / 40)
        key = (v, a, b)
        if key not in self._paths:
            self._paths[key] = self._make(v, a, b)
        return self._paths[key]

    def _make(self, v: int, a: float, b: float) -> QPainterPath | None:
        lo = int(np.searchsorted(self.s, a * self.length))
        hi = int(np.searchsorted(self.s, b * self.length, side="right"))
        if hi - lo < 2:
            return None
        s = self.s[lo:hi]
        widths = self.widths[lo:hi].copy()
        if a > 0:
            widths *= np.clip((s - a * self.length) / (6 * self.width), 0.15, 1)
        if b < 1:
            widths *= np.clip((b * self.length - s) / (3 * self.width), 0.35, 1)
        return _ribbon(self.variants[v][lo:hi], widths)

    def fill(self, p: QPainter, v: int, brush: QBrush, a: float = 0.0, b: float = 1.0) -> None:
        path = self.path(v, a, b)
        if path is not None:
            p.fillPath(path, brush)


def _hatch(poly: np.ndarray, angle: float, spacing: float, rnd: random.Random, u: float, over: float = 1.6, skip: float = 0.08) -> list[np.ndarray]:
    """Coloured-pencil hatching across a shape: lines at angle (degrees), unevenly spaced about
    spacing apart, each a quick slightly bowed stroke that may run a little past the outline."""
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    rot = poly @ np.array([[c, -s], [s, c]])
    lo, hi = rot[:, 1].min(), rot[:, 1].max()
    out = []
    y = lo + spacing * rnd.uniform(0.3, 0.8)
    edges = list(zip(rot, np.roll(rot, -1, axis=0), strict=True))
    while y < hi:
        xs = []
        for p0, p1 in edges:
            if (p0[1] - y) * (p1[1] - y) < 0:
                k = (y - p0[1]) / (p1[1] - p0[1])
                xs.append(p0[0] + (p1[0] - p0[0]) * k)
        xs.sort()
        for x0, x1 in zip(xs[::2], xs[1::2], strict=False):
            if x1 - x0 < 1.5 * u or rnd.random() < skip:
                continue
            x0 -= rnd.uniform(-0.5, over) * u
            x1 += rnd.uniform(-0.5, over) * u
            bow = rnd.uniform(-0.6, 0.6) * u
            seg = np.array([[x0, y], [(x0 + x1) / 2, y + bow], [x1, y + rnd.uniform(-0.5, 0.5) * u]])
            out.append(seg @ np.array([[c, s], [-s, c]]))
        y += spacing * rnd.uniform(0.7, 1.35)
    return out


def _mix(a: np.ndarray, b: np.ndarray, k: np.ndarray | float) -> np.ndarray:
    """a toward b by k, per pixel (colors with a last axis of 3, k without it)."""
    k = np.asarray(k, dtype=np.float32)
    return a + (b - a) * (k[..., None] if k.ndim else k)


def _fill_mask(w: int, h: int, scale: float, *shapes: np.ndarray | QRectF) -> np.ndarray:
    """What shapes (outlines as points, or rectangles, in points) cover, per pixel at scale."""

    def draw(q: QPainter) -> None:
        q.scale(scale, scale)
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#ffffff"))
        for shape in shapes:
            if isinstance(shape, QRectF):
                q.drawRect(shape)
            else:
                q.drawPolygon(_poly(shape))

    return mask(w, h, draw)


def _brush_wash(pts: np.ndarray, widths: np.ndarray, origin: tuple[float, float], size: tuple[int, int], r: float, u: float, seed: int,
                strength: float = 1.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:  # fmt: skip
    """A watercolour brush stroke along pts (points), widths wide, per pixel at r pixels a point in a
    picture size big whose top left is origin: bristle streaks running along it, pigment pooled into a
    wet, darker edge, granulated, its edges ragged and the brush running dry here and there. Gives
    its color, its alpha and the alpha of its edge alone, which is what is left once it dries."""
    w, h = size
    local = (pts - np.asarray(origin)) * r
    half = widths * r / 2
    n = _normals(pts)
    bands = 40

    def across(q: QPainter) -> None:
        # Where across the stroke each pixel is, as a shade: one band of it at a time.
        q.setPen(Qt.NoPen)
        for k in range(bands):
            a = local + n * (half * (-1 + 2 * k / bands))[:, None]
            b = local + n * (half * (-1 + 2 * (k + 1) / bands))[:, None]
            g = 20 + round(235 * (k + 0.5) / bands)
            q.setBrush(QColor(g, g, g))
            q.drawPolygon(_poly(np.vstack([a, b[::-1]])))

    shade = mask(w, h, across)
    inside = smooth(0.03, 0.08, shade)
    across_at = blur(np.clip((shade * 255 - 20) / 235, 0, 1), 0.8)
    e = np.abs(2 * across_at - 1)
    flow = noise(w, h, 30 * u * r, 3, seed)
    gran = noise(w, h, 1.3, 2, seed + 1)
    ragged = noise(w, h, 3 * u * r, 3, seed + 2)
    rnd = np.random.default_rng(seed)
    bristles = np.interp(across_at, np.linspace(0, 1, 70), np.convolve(rnd.random(70), np.ones(5) / 5, mode="same"))
    edge = 0.93 + 0.12 * (ragged - 0.5) - 0.1 * smooth(0.62, 0.85, flow)
    body = inside * smooth(edge, edge - 0.06, e)
    pool = smooth(0.68, 0.95, e / np.maximum(edge, 0.1)) * body
    rim = smooth(0.88, 0.99, e / np.maximum(edge, 0.1)) * body
    # A few bristle streaks, mostly where the brush ran thin.
    dry = 1 - 0.55 * smooth(0.55, 0.3, bristles + 0.5 * (flow - 0.5)) * (0.4 + 0.6 * e)
    alpha = strength * body * (0.17 + 0.21 * dry * (0.6 + 0.8 * gran)) + strength * 0.3 * pool * (0.65 + 0.7 * gran) + strength * 0.2 * rim
    # Over the dark game a pale tint goes grey: the body is mint, paler in mottles where the wash ran
    # thin, the pooled edge mint at full strength, its very rim teal.
    color = _mix(np.broadcast_to(rgb(WET), (h, w, 3)), rgb(WET_LIGHT), np.clip(0.3 + 0.6 * smooth(0.45, 0.8, flow) * (1 - e), 0, 1))
    color = _mix(color, rgb(WET), np.clip(pool * 1.4, 0, 1))
    color = _mix(color, rgb(WET_TEAL), np.clip(rim * 1.2, 0, 1))
    dried = strength * 0.5 * pool * (0.55 + 0.9 * gran)
    return color, np.clip(alpha, 0, 1), dried


def _sprite(w: float, h: float, scale: float) -> QImage:
    image = QImage(max(1, math.ceil(w * scale)), max(1, math.ceil(h * scale)), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    image.setDevicePixelRatio(scale)
    return image


def _put(p: QPainter, image: QImage, x: float, y: float, angle: float = 0.0, sx: float = 1.0, sy: float = 1.0) -> None:
    """A picture centred on (x, y), turned by angle degrees and sized by sx across and sy down."""
    if abs(sx) < 1e-3 or abs(sy) < 1e-3:
        return
    w, h = image.width() / image.devicePixelRatio(), image.height() / image.devicePixelRatio()
    p.save()
    p.translate(x, y)
    if angle:
        p.rotate(angle)
    if sx != 1.0 or sy != 1.0:
        p.scale(sx, sy)
    p.drawImage(QRectF(-w / 2, -h / 2, w, h), image)
    p.restore()


def _paper(w: int, h: int, scale: float, seed: int, tint: str = PAPER) -> np.ndarray:
    """Paper per pixel: its color, mottled a little, and its grain."""
    grain = noise(w, h, 1.2 * scale, 2, seed)
    cloud = noise(w, h, 16 * scale, 3, seed + 1)
    return rgb(tint) * (0.955 + 0.05 * grain + 0.03 * (cloud - 0.5))[..., None]


def _deckle(w: float, h: float, rnd: random.Random, u: float, rough: float = 1.6) -> np.ndarray:
    """A sheet's outline, w by h round (0, 0), its corners a little off square and its edges wandering
    and frayed as a deckle edge is."""
    corners = np.array([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]])
    corners += np.array([[rnd.uniform(-2, 2), rnd.uniform(-2, 2)] for _ in range(4)]) * u
    pts = _even(corners, 1.5 * u, closed=True)
    s = _along(pts)
    wander = _tremor(s, rnd, rough * u, 34 * u) + np.array([rnd.uniform(-0.45, 0.45) for _ in range(len(s))]) * rough * u
    return pts + _normals(pts) * wander[:, None]


# The page ---------------------------------------------------------------------------------------


class _Page:
    """The notebook's loose-leaf page as the wind lays it across the screen, left to right: a sheet of
    celadon paper about PAGE points wide, washed mint in uneven granulated patches, its teal rules and
    a soft red margin line, binder holes down its trailing edge, its top and trailing deckle edges
    washed mint and teal. Its leading edge bends and sags as paper does, a soft shadow ahead of it;
    its top corner curls over as a roll, showing the paper's back, shaded in pencil, a shadow under
    its edge. It is three drawings, boiling, laid across as one picture."""

    PAGE = 520

    def __init__(self, plan: _Plan) -> None:
        self.plan = plan
        u = plan.u
        h = plan.h
        rnd = random.Random(53)
        self.page = self.PAGE * u
        self.corner = (190 * u, 300 * u)
        self.shade = 60 * u
        self.top = 18 * u
        ys = np.arange(0, h + 12 * u, 6 * u, dtype=np.float64)
        mid = h / 2
        # The leading edge: tilted, its top leading; bowed back in the middle as a sheet sags in the
        # wind; a hand's wobble.
        self.curve_y = ys
        self.curve_x = 0.1 * (mid - ys) - 34 * u * (1 - ((ys - mid) / mid) ** 2) + _tremor(ys, rnd, 3 * u, 260 * u)
        lo, hi = self.curve_x.min(), self.curve_x.max()
        self.ox = lo - self.page - 24 * u
        bw = hi + self.shade + 8 * u - self.ox
        self.start = -(hi + self.shade + 10 * u)
        self.end = plan.w - lo + self.page + 30 * u
        # The paper is worked out once; its pencil edges are drawn over it three times, boiling.
        paper = self._bake(bw, h, 0)
        self.images = [self._pencil(QImage(paper), v) for v in range(3)]

    def curl(self, ys: np.ndarray) -> np.ndarray:
        """How far back the curled corner reaches from the leading edge, down the page: most at the
        top, nothing below the corner."""
        reach, tall = self.corner
        return reach * np.clip(1 - (ys - self.top) / tall, 0, 1) ** 1.4

    def _bake(self, bw: float, h: float, v: int) -> QImage:
        u = self.plan.u
        w, hh = max(4, math.ceil(bw)), max(4, math.ceil(h))
        xs = self.ox + np.arange(w, dtype=np.float32) + 0.5
        ys = np.arange(hh, dtype=np.float32) + 0.5
        c = np.interp(ys, self.curve_y, self.curve_x).astype(np.float32)
        d = c[:, None] - xs[None, :]
        flow = noise(w, hh, 22 * u, 3, 60 + v)
        grain = noise(w, hh, 1.2, 2, 63 + v)
        fibre = noise(w, hh, 1.0, 2, 66 + v)
        rnd = random.Random(70 + v)
        # Its deckle edges: the trailing one and the top, wandering.
        trail = (self.page + _tremor(ys.astype(np.float64), rnd, 4 * u, 90 * u)).astype(np.float32)[:, None]
        top = (self.top + _tremor(xs.astype(np.float64), rnd, 3 * u, 120 * u)).astype(np.float32)[None, :]
        to_trail = trail - d
        to_top = ys[:, None] - top
        edge_d = np.minimum(to_trail, to_top)
        body = smooth(-0.6, 0.6, d) * smooth(-1.0, 1.0, edge_d + 1.6 * u * (fibre - 0.5))
        # Binder holes down the trailing edge: the game shows through them.
        holes = np.zeros_like(d)
        for k in range(6):
            hy = self.top + 60 * u + k * (hh - self.top - 120 * u) / 5
            holes = np.maximum(holes, smooth(7 * u + 0.6, 7 * u - 0.6, np.hypot(to_trail - 18 * u, ys[:, None] - hy)))
        body = body * (1 - holes)
        # The paper: celadon, washed mint in uneven patches, their rims dried darker, granulated.
        patch = smooth(0.45, 0.58, noise(w, hh, 60 * u, 3, 67 + v))
        rim = np.clip((patch - blur(patch, 3 * u)) * 3, 0, 1)
        color = rgb(SHEET) * (0.95 + 0.06 * grain + 0.04 * (flow - 0.5))[..., None]
        color = _mix(color, rgb(WET_LIGHT), patch * (0.55 + 0.3 * flow))
        color = _mix(color, rgb(WET), rim * 0.8)
        deckle = np.exp(-np.clip(edge_d, 0, None) / (12 * u)) * (0.7 + 0.5 * flow)
        color = _mix(color, rgb(WET), np.clip(deckle, 0, 1))
        color = _mix(color, rgb(WET_TEAL), np.clip(np.exp(-np.clip(edge_d, 0, None) / (2.5 * u)), 0, 1) * 0.85)
        # Teal rules and a red margin line, drawn by hand.
        lines = mask(w, hh, lambda p: self._rules(p, v, hh))
        margin = mask(w, hh, lambda p: self._margin(p, v, hh))
        color = _mix(color, rgb(TEAL), np.clip(lines * (0.55 + 0.5 * grain), 0, 1))
        color = _mix(color, rgb(SEAL), np.clip(margin * (0.45 + 0.4 * grain), 0, 1))
        alpha = body * (0.5 + 0.15 * flow + 0.1 * patch + 0.25 * deckle) + body * 0.3 * (lines + margin)
        alpha = np.clip(alpha, 0, 0.92)
        # The curled corner: the paper's back, rolling over; lit along a ridge, in shade toward the
        # fold, its free edge pooled teal; the page's rules showing through, slanting.
        reach = self.curl(ys)[:, None]
        q = d / np.maximum(reach, 1e-3)
        flap = (reach > 1) * smooth(-0.6, 0.6, d) * smooth(0.6, -0.6, d - reach + 1.4 * u * (fibre - 0.5)) * smooth(-1.0, 1.0, to_top)
        back = rgb("#eef7f2") * (0.95 + 0.06 * grain)[..., None]
        back = _mix(back, rgb("#a9c7bb"), np.exp(-np.clip(q, 0, None) / 0.16) * 0.7)
        back = _mix(back, rgb("#ffffff"), np.exp(-(((q - 0.34) / 0.12) ** 2)) * 0.55)
        back = _mix(back, rgb(WET), np.clip(np.exp(-np.clip(reach - d, 0, None) / (9 * u)) * (0.8 + 0.4 * flow), 0, 1))
        back = _mix(back, rgb(WET_TEAL), np.clip(np.exp(-np.clip(reach - d, 0, None) / (2.2 * u)), 0, 1) * 0.8)
        hatch = mask(w, hh, lambda p: self._hatching(p, v, hh))
        back = _mix(back, rgb(SOFT), np.clip(hatch * smooth(0.5, 0.0, q), 0, 1) * 0.85)
        color = _mix(color, back, flap)
        alpha = np.maximum(alpha * (1 - flap), flap * 0.96)
        # Shadows: under the curl's free edge onto the page, and ahead of the page onto the game.
        under = (reach > 1) * (d > reach) * np.exp(-np.clip(d - reach, 0, None) / (8 * u)) * 0.45 * smooth(-1.0, 1.0, to_top)
        color = _mix(color, rgb("#24413c"), np.clip(under, 0, 1) * (1 - flap))
        ahead = (d < 0) * np.exp(-np.clip(-d, 0, None) / (0.35 * self.shade)) * 0.4 * (0.7 + 0.6 * flow) * smooth(-14 * u, 10 * u, to_top)
        out_c = color * alpha[..., None] + rgb("#0b1517") * (ahead * (1 - alpha))[..., None]
        out_a = alpha + ahead * (1 - alpha)
        return picture(out_c / np.maximum(out_a, 1e-4)[..., None], out_a)

    def _pencil(self, image: QImage, v: int) -> QImage:
        """Pencil over the paper: the leading edge, the curl's fold and its free edge, a line of the roll."""
        u = self.plan.u
        p = QPainter(image)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(-self.ox, 0)
        lead = np.column_stack([self.curve_x, self.curve_y])
        below = self.curve_y > self.top
        graphite = QBrush(QColor(GRAPHITE))
        _Stroke(lead[below], 2.0 * u, random.Random(71 + v), u, wobble=0.6, ends=(20, 20)).fill(p, v, graphite)
        reach_line = self.curl(self.curve_y)
        rows = (reach_line > 2 * u) & below
        if rows.sum() > 2:
            rim_line = lead[rows] - np.column_stack([reach_line[rows], np.zeros(rows.sum())])
            _Stroke(rim_line, 1.9 * u, random.Random(75 + v), u, wobble=0.5, ends=(4, 10)).fill(p, v, graphite)
            roll = lead[rows] - np.column_stack([0.14 * reach_line[rows], np.zeros(rows.sum())])
            _Stroke(roll, 1.2 * u, random.Random(80 + v), u, wobble=0.6, ends=(4, 12)).fill(p, v, QBrush(QColor(SOFT)))
        p.end()
        return image

    def _rules(self, p: QPainter, v: int, hh: int) -> None:
        u = self.plan.u
        rnd = random.Random(99 + v)
        p.translate(-self.ox, 0)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        y = self.top + 34 * u
        while y < hh:
            c = float(np.interp(y, self.curve_y, self.curve_x))
            pts = np.array([[c - self.page + 30 * u, y + rnd.uniform(-0.6, 0.6) * u], [c - 6 * u, y + rnd.uniform(-0.6, 0.6) * u]])
            path = _Stroke(pts, 1.5 * u, rnd, u, wobble=0.4, ends=(8, 8)).path(0)
            if path is not None:
                p.drawPath(path)
            y += 30 * u

    def _margin(self, p: QPainter, v: int, hh: int) -> None:
        u = self.plan.u
        rnd = random.Random(98 + v)
        p.translate(-self.ox, 0)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        pts = np.column_stack([np.interp(self.curve_y, self.curve_y, self.curve_x) - self.page + 52 * u, self.curve_y])
        pts = pts[self.curve_y > self.top + 8 * u]
        path = _Stroke(pts, 1.6 * u, rnd, u, wobble=0.5, ends=(10, 10)).path(0)
        if path is not None:
            p.drawPath(path)

    def _hatching(self, p: QPainter, v: int, hh: int) -> None:
        u = self.plan.u
        rnd = random.Random(90 + v)
        p.translate(-self.ox, 0)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        y = self.top
        while y < self.top + self.corner[1]:
            c = float(np.interp(y, self.curve_y, self.curve_x))
            length = rnd.uniform(0.25, 0.5) * float(self.curl(np.array([y]))[0])
            if length > 3 * u:
                pts = np.array([[c - 1.5 * u, y], [c - length, y + length * 0.45 + rnd.uniform(-1, 1) * u]])
                path = _Stroke(pts, 1.1 * u, rnd, u, wobble=0.2, ends=(2, 6)).path(0)
                if path is not None:
                    p.drawPath(path)
            y += rnd.uniform(3.5, 7.0) * u

    def at(self, t: float) -> float:
        k = win(t, SWEEP[0], SWEEP[1])
        k = 0.75 * k + 0.25 * k * k * (3 - 2 * k)
        return self.start + (self.end - self.start) * k

    def edge(self, y: float, t: float) -> float:
        """Where the page's leading edge is across the screen, at height y."""
        return self.at(t) + float(np.interp(y, self.curve_y, self.curve_x))

    def paint(self, q: QPainter, t: float) -> QRectF:
        if not (SWEEP[0] <= t <= SWEEP[1] + 0.05):
            return QRectF()
        image = self.images[int(t * BOIL) % 3]
        at = QPointF(self.at(t) + self.ox, 0)
        q.drawImage(at, image)
        return QRectF(at.x(), 0, image.width(), image.height())


# Sketches on the sheet ------------------------------------------------------------------------


class _Sketch:
    """A pencil sketch the sheet carries for a moment: drawn on stroke group by stroke group as the
    hand goes (each group revealed through a growing clip), held a breath, then smeared away with the
    wind. Chalk lines and mint hatching, baked in three boiling drawings."""

    SCALE = 2.0

    def __init__(self, plan: _Plan, box: QRectF, groups: list[tuple[list[_Stroke], str]], start: float, tooth: _Tooth) -> None:
        self.plan = plan
        self.box = box.adjusted(-6 * plan.u, -6 * plan.u, 6 * plan.u, 6 * plan.u)
        self.start = start
        # Drawn on, held a breath and smeared away: about half a second in all.
        self.draw_on, self.hold, self.smear = 0.25, 0.1, 0.18
        # A light mint wash laid first, so the chalk reads over a busy avatar; then each group of
        # strokes baked alone, three times, in the order the hand takes them.
        blot = self._blot(int(start * 100))
        self.groups = [[blot, blot, blot]]
        for strokes, color in groups:
            images = []
            for v in range(3):
                image = _sprite(self.box.width(), self.box.height(), self.SCALE)
                q = QPainter(image)
                q.setRenderHint(QPainter.Antialiasing)
                q.translate(-self.box.left(), -self.box.top())
                brush = tooth.brush(color)
                for stroke in strokes:
                    stroke.fill(q, v, brush)
                q.end()
                images.append(image)
            self.groups.append(images)
        # The whole drawing, for once it is all drawn on: one picture to lay instead of each group.
        self.whole = []
        for v in range(3):
            image = _sprite(self.box.width(), self.box.height(), self.SCALE)
            q = QPainter(image)
            q.setRenderHint(QPainter.SmoothPixmapTransform)
            for images in self.groups:
                q.drawImage(QRectF(0, 0, self.box.width(), self.box.height()), images[v])
            q.end()
            self.whole.append(image)

    def _blot(self, seed: int) -> QImage:
        """A mint watercolour blot behind the sketch: ragged, granulated, its rim dried darker."""
        u = self.plan.u
        w, h = max(4, math.ceil(self.box.width())), max(4, math.ceil(self.box.height()))
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        ragged = noise(w, h, 9 * u, 3, seed)
        d = np.hypot((xs - w / 2) / (w * 0.46), (ys - h / 2) / (h * 0.44)) + 0.45 * (ragged - 0.5)
        blot = smooth(1.0, 0.9, d)
        rim = np.clip((blot - blur(blot, 1.6 * u)) * 3, 0, 1)
        gran = noise(w, h, 1.3, 2, seed + 1)
        alpha = blot * 0.2 * (0.7 + 0.6 * gran) + 0.22 * rim
        color = _mix(np.broadcast_to(rgb(WET), (h, w, 3)), rgb(WET_TEAL), rim)
        return picture(color, alpha)

    def paint(self, p: QPainter, t: float, tq: float, v: int) -> None:
        age = tq - self.start
        end = self.draw_on + self.hold + self.smear
        if age <= 0 or age >= end:
            return
        box = self.box.translated(_creep(self.plan.u, t))
        n = len(self.groups)
        gone = win(age, self.draw_on + self.hold, end)
        p.save()
        if age >= self.draw_on:
            # Smeared away with the wind: the drawing slides on and thins, two ghosts trailing it.
            image = self.whole[v]
            push = ease_in(gone) * 26 * self.plan.u
            for shift, alpha in ((push * 1.9, 0.18), (push * 1.3, 0.3), (push, 1.0)) if gone > 0 else ((0.0, 1.0),):
                p.setOpacity(alpha * (1 - gone) ** 1.3)
                p.drawImage(box.translated(shift, -shift * 0.12), image)
            p.restore()
            return
        for index, images in enumerate(self.groups):
            # Each group starts as the one before it is half drawn; it is revealed left to right on
            # a slant, as the hand sweeps.
            a = self.draw_on * index / (n + 1)
            k = win(age, a, a + self.draw_on * 2 / (n + 1))
            if k <= 0:
                continue
            image = images[v]
            if k < 1:
                p.save()
                reach = box.left() + (box.width() + box.height() * 0.4) * k
                clip = QPainterPath()
                clip.addPolygon(QPolygonF([QPointF(box.left() - 2, box.top() - 2), QPointF(reach + box.height() * 0.2, box.top() - 2),
                                           QPointF(reach - box.height() * 0.2, box.bottom() + 2), QPointF(box.left() - 2, box.bottom() + 2)]))  # fmt: skip
                p.setClipPath(clip)
                p.drawImage(box, image)
                p.restore()
            elif gone > 0:
                # Smeared away with the wind: the drawing slides on and thins, two ghosts trailing it.
                push = ease_in(gone) * 26 * self.plan.u
                for shift, alpha in ((push * 1.9, 0.18), (push * 1.3, 0.3), (push, 1.0)):
                    p.setOpacity(alpha * (1 - gone) ** 1.3)
                    p.drawImage(box.translated(shift, -shift * 0.12), image)
                p.setOpacity(1.0)
            else:
                p.drawImage(box, image)
        p.restore()


def _sketches(plan: _Plan, tooth: _Tooth) -> list[_Sketch]:
    """The four sketches in the fold's wake: the lattice window left of the title, the three-fish
    ring in the lane, bamboo right of the title, ripples in the lane on the right."""
    u = plan.u
    out = []
    for build, (x, y), start in (
        (_lattice, plan.p(510, 140), 1.42),
        # Between two row-2 avatars, where the chalk reads.
        (_fish_ring, (plan.x(612), plan.lane + 6 * plan.u), 1.5),
        (_bamboo_sprig, plan.p(1230, 140), 1.72),
        (_ripples, (plan.x(1300), plan.lane), 1.78),
    ):
        groups, box = build(QPointF(x, y), u, random.Random(int(x) + 7), on_paper=False)
        out.append(_Sketch(plan, box, groups, start, tooth))
    return out


def _straight(a: tuple[float, float], b: tuple[float, float], rnd: random.Random, u: float, over: float = 3.0) -> np.ndarray:
    """A ruled-by-hand line from a to b, running a little past its ends or stopping a little short."""
    pa, pb = np.array(a, dtype=np.float64), np.array(b, dtype=np.float64)
    d = pb - pa
    d = d / max(np.hypot(*d), 1e-9)
    pa = pa - d * rnd.uniform(-1.0, over) * u
    pb = pb + d * rnd.uniform(-1.0, over) * u
    return np.array([pa, (pa + pb) / 2 + np.array([-d[1], d[0]]) * rnd.uniform(-0.8, 0.8) * u, pb])


def _leaf_shape(base: np.ndarray, tip: np.ndarray, wide: float, bend: float) -> np.ndarray:
    """A bamboo leaf's outline from base to tip and back: long, narrow, its widest a third along."""
    d = tip - base
    length = np.hypot(*d)
    d = d / max(length, 1e-9)
    n = np.array([-d[1], d[0]])
    k = np.linspace(0, 1, 24)
    half = wide * np.sin(np.pi * np.clip(k, 0, 1) ** 0.7) * (1 - k) ** 0.35
    sway = bend * np.sin(np.pi * k) * length
    side1 = base + np.outer(k * length, d) + np.outer(half + sway, n)
    side2 = base + np.outer(k * length, d) + np.outer(-half + sway, n)
    return np.vstack([side1, side2[::-1]])


def _bamboo_leaf(base: tuple[float, float], angle: float, length: float, u: float, rnd: random.Random, line: str, tint: str,
                 width: float) -> tuple[list[_Stroke], list[_Stroke], np.ndarray]:  # fmt: skip
    """One leaf: its outline drawn in one go from the stalk round the tip and back, a midrib, and
    hatching inside; and its shape."""
    b = np.array(base, dtype=np.float64)
    a = math.radians(angle)
    tip = b + length * np.array([math.cos(a), math.sin(a)])
    shape = _leaf_shape(b, tip, length * 0.13, rnd.uniform(-0.06, 0.06))
    outline = shape.copy()
    outline[-1] += (rnd.uniform(-1, 1) * u, rnd.uniform(-1, 1) * u)
    lines = [_Stroke(outline, width, rnd, u, 0.2, ends=(2.5, 2.5))]
    mid = np.array([b + (tip - b) * k for k in (0.05, 0.5, 0.86)])
    lines.append(_Stroke(mid, width * 0.6, rnd, u, 0.15, ends=(2, 5)))
    hatching = [_Stroke(seg, 0.9 * u, rnd, u, 0.1, ends=(1.5, 2.5)) for seg in _hatch(shape, angle + 55, 2.6 * u, rnd, u, over=0.6, skip=0.15)]
    return lines, hatching, shape


def _fish(c: QPointF, r: float, a0: float, span: float, u: float, rnd: random.Random, width: float) -> tuple[list[_Stroke], np.ndarray]:
    """One bronze fish curled along a ring of radius r round c, its tail at angle a0 (radians) and
    its nose span further round, its back outward: a plump body with a round head, a forked tail, a
    fin on its back, an eye under a wavy snake's brow, a gill and a few scales. Gives its strokes and
    the outline of its body and tail together (for a wash)."""
    length = r * span

    def bend(points: list[tuple[float, float]] | np.ndarray) -> np.ndarray:
        pts = np.asarray(points, dtype=np.float64)
        ang = a0 + span * pts[:, 0] / length
        rad = r + pts[:, 1]
        return np.column_stack([c.x() + rad * np.cos(ang), c.y() + rad * np.sin(ang)])

    L = length
    xs = np.linspace(0.2, 1.0, 30)
    thick = L * (0.05 + 0.17 * np.sin(np.pi * np.clip((xs - 0.2) / 0.8, 0, 1) ** 0.75) ** 0.9)
    head = np.clip((xs - 0.8) / 0.2, 0, 1)
    thick = thick * np.sqrt(np.clip(1 - head**2, 0, 1)) + 0.002 * L
    back = [(x * L, t) for x, t in zip(xs, thick, strict=True)]
    belly = [(x * L, -t * 0.88) for x, t in zip(xs, thick, strict=True)]
    tail = [(0.2 * L, -0.05 * L), (0.02 * L, -0.19 * L), (0.09 * L, 0.0), (0.02 * L, 0.19 * L), (0.2 * L, 0.05 * L)]
    body = bend(back + belly[::-1] + tail)
    strokes = [_Stroke(bend(back + belly[::-1]), width, rnd, u, 0.15, ends=(2.5, 2.5))]
    strokes.append(_Stroke(bend(tail), width * 0.9, rnd, u, 0.1, ends=(2, 2)))
    # A fin on its back, a gill, its eye and the wavy snake's brow over it, a few scales.
    strokes.append(_Stroke(bend([(0.4 * L, 0.18 * L), (0.5 * L, 0.27 * L), (0.6 * L, 0.2 * L)]), width * 0.75, rnd, u, 0.05, ends=(1.5, 1.5)))
    strokes.append(_Stroke(bend([(0.72 * L, 0.13 * L), (0.69 * L, 0.0), (0.72 * L, -0.12 * L)]), width * 0.7, rnd, u, 0.05, ends=(1.5, 1.5)))
    eye = [(0.86 * L + 0.035 * L * math.cos(q), 0.05 * L + 0.035 * L * math.sin(q)) for q in np.linspace(0, math.tau * 1.15, 14)]
    strokes.append(_Stroke(bend(eye), width * 0.9, rnd, u, 0.03, ends=(1, 1)))
    brow = [(0.76 * L + 0.18 * L * k, 0.13 * L + 0.025 * L * math.sin(k * math.tau * 1.5)) for k in np.linspace(0, 1, 12)]
    strokes.append(_Stroke(bend(brow), width * 0.8, rnd, u, 0.03, ends=(1.5, 2)))
    for x0 in (0.42, 0.53):
        for y0 in (-0.05, 0.07):
            scale_arc = [(x0 * L + 0.04 * L * math.sin(q), y0 * L + 0.04 * L * math.cos(q)) for q in np.linspace(-1.3, 1.3, 7)]
            strokes.append(_Stroke(bend(scale_arc), width * 0.55, rnd, u, 0.03, ends=(1, 1)))
    return strokes, body


class _Patch:
    """A shape washed in colour under the pencil (a leaf, a fish's body), drawn as a stroke is: its
    brush's grain makes the wash uneven."""

    def __init__(self, points: np.ndarray) -> None:
        self.poly = _poly(np.asarray(points, dtype=np.float64))

    def fill(self, p: QPainter, _v: int, brush: QBrush, _a: float = 0.0, _b: float = 1.0) -> None:
        p.setPen(Qt.NoPen)
        p.setBrush(brush)
        p.drawPolygon(self.poly)


def _colors(on_paper: bool) -> tuple[str, str, str, float]:
    """The line, the hatching, the wash and the line's weight: graphite, teal and pale mint on paper;
    on the game chalk, mint and mint wash, bolder so they read on the dark."""
    return (GRAPHITE, TEAL, "#cdeedd", 1.15) if on_paper else (CHALK, WET_TEAL, WET, 2.4)


def _circle(c: QPointF, r: float, rnd: random.Random, turns: float = 1.06, step: int = 120) -> np.ndarray:
    """A circle drawn in one go, round a little more than once."""
    a0 = rnd.uniform(0, math.tau)
    q = np.linspace(a0, a0 + math.tau * turns, step)
    return np.column_stack([c.x() + r * np.cos(q), c.y() + r * np.sin(q)])


def _lattice(c: QPointF, u: float, rnd: random.Random, on_paper: bool, size: float = 1.0) -> tuple[list, QRectF]:
    """A 吴山居 window: a round moon window in a double frame with diamond lattice across it, bamboo
    standing behind it, its leaves washed mint and showing round the frame, a few panes hatched."""
    line, tint, wash, weight = _colors(on_paper)
    width = weight * u
    R = 72 * u * size
    inner = R - 9 * u * size
    frame = [_Stroke(_circle(c, R, rnd), width, rnd, u, 0.3, ends=(3, 3)), _Stroke(_circle(c, inner, rnd, 1.03), width * 0.85, rnd, u, 0.3, ends=(3, 3))]
    # Diamond lattice across the opening.
    lattice, hatching = [], []
    spacing = 21 * u * size
    for sign in (1, -1):
        d = np.array([1, sign]) / math.sqrt(2)
        n = np.array([-d[1], d[0]])
        k = -int(inner / spacing)
        while k * spacing < inner:
            off = k * spacing
            half = math.sqrt(max(0.0, (inner - 2 * u) ** 2 - off * off))
            if half > 6 * u:
                mid = np.array([c.x(), c.y()]) + n * off
                lattice.append(_Stroke(_straight(tuple(mid - d * half), tuple(mid + d * half), rnd, u, 0.6), width * 0.75, rnd, u, 0.2, ends=(2, 2)))
            k += 1
    for i in range(-4, 4):
        for j in range(-4, 4):
            cx, cy = (i + 0.5) * spacing / math.sqrt(2) - (j + 0.5) * spacing / math.sqrt(2), (i + 0.5) * spacing / math.sqrt(2) + (j + 0.5) * spacing / math.sqrt(2)
            if math.hypot(cx, cy) > inner - spacing * 0.8 or rnd.random() > 0.3:
                continue
            r = spacing / math.sqrt(2) * 0.85
            cell = np.array([(c.x() + cx, c.y() + cy - r), (c.x() + cx + r, c.y() + cy), (c.x() + cx, c.y() + cy + r), (c.x() + cx - r, c.y() + cy)])
            hatching += [_Stroke(seg, 0.9 * width * 0.5, rnd, u, 0.1, ends=(1.5, 2)) for seg in _hatch(cell, 40, 2.8 * u * size, rnd, u, over=0.3)]
    # Bamboo behind: two culms rising through the window, leaves round its frame.
    bamboo, patches = [], []
    for bx, lean in ((-0.55, 0.18), (0.35, 0.28)):
        x0, y0 = c.x() + bx * R, c.y() + R * 1.05
        top = (x0 + lean * R * 2.2, c.y() - R * 1.1)
        bamboo.append(_Stroke(_straight((x0, y0), top, rnd, u, 1), width * 0.9, rnd, u, 0.3))
        bamboo.append(_Stroke(_straight((x0 + 5 * u * size, y0), (top[0] + 5 * u * size, top[1]), rnd, u, 1), width * 0.8, rnd, u, 0.3))
    for base, angle, length in (((c.x() + R * 0.75, c.y() - R * 0.85), -20, 42), ((c.x() + R * 0.8, c.y() - R * 0.8), 18, 36), ((c.x() - R * 0.95, c.y() + R * 0.55), 200, 38),
                                ((c.x() - R * 0.9, c.y() + R * 0.6), 160, 32), ((c.x() + R * 0.5, c.y() - R * 1.0), -55, 34)):  # fmt: skip
        lines, hatch, shape = _bamboo_leaf(base, angle, length * u * size, u, rnd, line, tint, width * 0.85)
        bamboo += lines
        hatching += hatch
        patches.append(_Patch(shape))
    groups = [(patches, wash), (bamboo, line), (frame, line), (lattice, line), (hatching, tint)]
    side = R * 2 + 70 * u * size
    return groups, QRectF(c.x() - side / 2, c.y() - side / 2, side, side)


def _bamboo_sprig(c: QPointF, u: float, rnd: random.Random, on_paper: bool, size: float = 1.0) -> tuple[list, QRectF]:
    """Bamboo: two culms leaning with the wind, drawn as double lines broken at their nodes, and sprays
    of leaves washed mint, streaming right."""
    line, tint, wash, weight = _colors(on_paper)
    width = weight * u
    culms, nodes, leaves, hatching, patches = [], [], [], [], []
    for bx, lean, tall in ((-60, 0.32, 150), (10, 0.22, 130)):
        x, y = c.x() + bx * u * size, c.y() + 75 * u * size
        segs = 3
        for k in range(segs):
            l0 = tall * u * size * k / segs
            l1 = tall * u * size * (k + 1) / segs - 4 * u
            a, b = np.array([x + l0 * lean, y - l0]), np.array([x + l1 * lean, y - l1])
            for off in (-3.6 * u * size, 3.6 * u * size):
                culms.append(_Stroke(_straight(tuple(a + (off, 0)), tuple(b + (off, 0)), rnd, u, 0.5), width * 0.9, rnd, u, 0.3))
            n0 = b + np.array([lean * 3 * u, -3 * u])
            nodes.append(_Stroke(np.array([n0 + (-6 * u, 1 * u), n0 + (0, -1 * u), n0 + (6 * u, 0.5 * u)]), width * 0.9, rnd, u, 0.2, ends=(2, 2)))
            if k >= 1:
                for angle in (rnd.uniform(-30, -5), rnd.uniform(5, 35)):
                    base = (n0[0] + 2 * u, n0[1])
                    lines, hatch, shape = _bamboo_leaf(base, angle, rnd.uniform(40, 54) * u * size, u, rnd, line, tint, width * 0.85)
                    leaves += lines
                    hatching += hatch
                    patches.append(_Patch(shape))
    groups = [(patches, wash), (culms, line), (nodes + leaves, line), (hatching, tint)]
    return groups, QRectF(c.x() - 115 * u * size, c.y() - 100 * u * size, 245 * u * size, 200 * u * size)


def _fish_ring(c: QPointF, u: float, rnd: random.Random, on_paper: bool, size: float = 1.0) -> tuple[list, QRectF]:
    """The 蛇眉铜鱼: three fish curled nose to tail into a ring, their bodies washed, hatched under."""
    line, tint, wash, weight = _colors(on_paper)
    r = 28 * u * size
    width = weight * u * (0.9 if not on_paper else 1.0)
    bodies, details, hatching, patches = [], [], [], []
    for k in range(3):
        strokes, body = _fish(c, r, math.radians(-90 + 120 * k), math.radians(112), u, rnd, width)
        bodies.append(strokes[0])
        details += strokes[1:]
        patches.append(_Patch(body))
        inner = body[np.hypot(body[:, 0] - c.x(), body[:, 1] - c.y()) <= r + 0.5 * u]
        if len(inner) > 3:
            hatching += [_Stroke(seg, max(0.85 * u, width * 0.45), rnd, u, 0.1, ends=(1.2, 2)) for seg in _hatch(inner, 35 + 40 * k, 2.6 * u, rnd, u, over=0.4, skip=0.2)]
    groups = [(patches, wash), (bodies, line), (details, line), (hatching, tint)]
    side = r * 2 + 34 * u * size
    return groups, QRectF(c.x() - side / 2, c.y() - side / 2, side, side)


def _ripples(c: QPointF, u: float, rnd: random.Random, on_paper: bool, size: float = 1.0) -> tuple[list, QRectF]:
    """西湖's ripples: a few wavy lines across the water, broken where the hand lifted, washed mint
    between, and rings spreading round where a fish rose."""
    line, tint, wash, weight = _colors(on_paper)
    width = weight * u
    waves, rings, hatching, patches = [], [], [], []
    for dy, x0, x1 in ((-26, -150, 40), (-6, -110, 150), (14, -150, 90), (32, -60, 150)):
        xs = np.linspace(x0, x1, 60) * u * size
        ys = (dy + 2.6 * np.sin(xs / (13 * u * size) + rnd.uniform(0, 6))) * u * size
        pts = np.column_stack([c.x() + xs, c.y() + ys])
        cut = rnd.randrange(18, 42)
        for part in (pts[:cut], pts[cut + 4 :]):
            if len(part) > 4:
                waves.append(_Stroke(part, width, rnd, u, 0.2, ends=(4, 6)))
        if dy > -20:
            band = np.vstack([pts[8:44], (pts[8:44] + (0, 9 * u * size))[::-1]])
            patches.append(_Patch(band))
            hatching += [_Stroke(seg, max(0.85 * u, width * 0.45), rnd, u, 0.1, ends=(1.2, 2)) for seg in _hatch(band, 60, 3.0 * u, rnd, u, over=0.5)]
    for rx, ry in ((14, 4), (26, 8), (38, 12)):
        q = np.linspace(rnd.uniform(0.3, 0.8), rnd.uniform(5.0, 5.8), 40)
        ring = np.column_stack([c.x() + 60 * u * size + rx * u * size * np.cos(q), c.y() - 8 * u * size + ry * u * size * np.sin(q)])
        rings.append(_Stroke(ring, width * 0.9, rnd, u, 0.1, ends=(3, 3)))
    groups = [(patches, wash), (waves, line), (rings, line), (hatching, tint)]
    return groups, QRectF(c.x() - 165 * u * size, c.y() - 48 * u * size, 330 * u * size, 96 * u * size)


# Speed lines and wind curls --------------------------------------------------------------------


class _Line:
    """A 手书 wind line drawn live: a pencil stroke that draws on from its tail to its curled head
    over draw seconds from start and is rubbed out from its tail over gone seconds after; with
    smudge, a faint eraser smudge lingers where it was and fades."""

    def __init__(self, stroke: _Stroke, color: str, start: float, draw: float, gone: tuple[float, float], smudge: bool = False) -> None:
        self.stroke, self.color = stroke, color
        self.start, self.draw, self.gone = start, draw, gone
        self.smudge = smudge

    def warm(self) -> None:
        """Make each stretch of it it will show, in each drawing, before it plays (on twos there are
        few), so no frame stops to make one."""
        tq = math.floor(self.start * TWOS) / TWOS
        while tq <= self.gone[1] + 0.5:
            b = ease_out(win(tq, self.start, self.start + self.draw))
            a = ease_in_out(win(tq, *self.gone))
            for v in range(3):
                if 0 < b and a < 1:
                    self.stroke.path(v, a, b)
                if self.smudge:
                    self.stroke.path((v + 1) % 3, 0.0, min(a, 1.0))
            tq += 1 / TWOS

    def paint(self, p: QPainter, tq: float, v: int, tooth: _Tooth) -> None:
        b = ease_out(win(tq, self.start, self.start + self.draw))
        a = ease_in_out(win(tq, *self.gone))
        if b <= 0 or a >= 1:
            if self.smudge and a >= 1:
                self._smudge(p, tq, v, tooth, 1.0)
            return
        if self.smudge and a > 0:
            self._smudge(p, tq, v, tooth, a)
        self.stroke.fill(p, v, tooth.brush(self.color), a, b)

    def _smudge(self, p: QPainter, tq: float, v: int, tooth: _Tooth, a: float) -> None:
        fade = 1 - win(tq, self.gone[1] - 0.1, self.gone[1] + 0.35)
        if fade <= 0:
            return
        path = self.stroke.path((v + 1) % 3, 0.0, a)
        if path is None:
            return
        p.save()
        p.setOpacity(0.16 * fade)
        brush = tooth.brush(CHALK, 0.8)
        for dx, dy in ((2.5, 1.5), (-1.5, 3.0), (4.5, -1.0)):
            p.fillPath(path.translated(dx, dy), brush)
        p.restore()


def _curled(points: list[tuple[float, float]], curl: float, u: float, turn: int = -1) -> np.ndarray:
    """A wind line through points ending in a curl of radius curl, winding in (turn -1: up and back)."""
    line = _spline(points, 2.0 * u)
    d = line[-1] - line[-6]
    heading = math.atan2(d[1], d[0])
    centre = line[-1] + curl * np.array([math.cos(heading + turn * math.pi / 2), math.sin(heading + turn * math.pi / 2)])
    start = heading - turn * math.pi / 2
    q = np.linspace(0, 1.25 * 2 * math.pi, 60)
    radius = curl * (1 - 0.62 * q / q[-1])
    spiral = np.column_stack([centre[0] + radius * np.cos(start + turn * q), centre[1] + radius * np.sin(start + turn * q)])
    return np.vstack([line, spiral[1:]])


def _swoop(a: tuple[float, float], b: tuple[float, float], amp: float, waves: float, phase: float) -> list[tuple[float, float]]:
    """A 手书 wind line's way from a to b: swinging either side of the straight way as it goes, more as
    it gathers speed."""
    pa, pb = np.array(a), np.array(b)
    d = pb - pa
    n = np.array([-d[1], d[0]]) / max(np.hypot(*d), 1e-9)
    out = []
    for k in np.linspace(0, 1, 24):
        swing = amp * (0.35 + 0.65 * k) * math.sin(phase + k * waves * math.tau)
        out.append(tuple(pa + d * k + n * swing))
    return out


def _speed_lines(plan: _Plan, rnd: random.Random) -> list[_Line]:
    """Six 手书 speed lines whipping in from the left, swinging as they go and curling at their heads,
    most with a thinner second line beside them: two across the top band, one along the lane, one low
    each side of the gap, one down the left margin."""
    u = plan.u
    g = plan.gap
    lines = []
    plans = (
        (_swoop((-30 * u, plan.y(40)), (plan.x(1450), plan.y(30)), 9 * u, 1.6, 0.4), 19, CHALK, 0.0, True),
        (_swoop((-30 * u, plan.y(140)), (plan.title.left() - 70 * u, plan.y(112)), 15 * u, 1.2, 2.0), 17, MINT, 0.06, True),
        (_swoop((-30 * u, plan.lane + 8 * u), (plan.x(1290), plan.lane - 4 * u), 14 * u, 2.2, 1.1), 18, CHALK, 0.1, True),
        (_swoop((-30 * u, plan.low + 22 * u), (g.left() - 70 * u, plan.low - 8 * u), 10 * u, 1.1, 0.3), 15, MINT, 0.14, False),
        (_swoop((g.right() + 30 * u, plan.low + 24 * u), (plan.w - 70 * u, plan.low - 8 * u), 10 * u, 1.0, 2.5), 15, CHALK, 0.18, True),
        (_swoop((plan.left_x - 30 * u, plan.y(140)), (plan.left_x + 5 * u, plan.y(600)), 14 * u, 1.1, 0.0), 13, MINT, 0.08, False),
    )
    for points, curl, color, start, twin in plans:
        path = _curled(points, curl * u, u)
        stroke = _Stroke(path, (3.9 if color == CHALK else 3.5) * u, rnd, u, wobble=0.8, ends=(10, 3))
        lines.append(_Line(stroke, color, start, 0.25, (start + 0.22, start + 0.58)))
        if twin:
            # A thinner line beside it, starting later and stopping sooner, in the other color.
            body = _spline(points, 2 * u)
            part = body[int(len(body) * 0.2) : int(len(body) * 0.8)]
            side = part + _normals(part) * 9 * u
            other = MINT if color == CHALK else CHALK
            lines.append(_Line(_Stroke(side, 2.3 * u, rnd, u, wobble=0.6, ends=(8, 6)), other, start + 0.05, 0.2, (start + 0.24, start + 0.55)))
    return lines


def _curls(plan: _Plan, ribbon: _WindRibbon, rnd: random.Random) -> list[_Line]:
    """Pencil wind curls running along the ribbon's outer edge as the gust draws it, rubbed out after."""
    u = plan.u
    out = []
    route = ribbon.route
    for share, length, color in ((0.04, 0.1, CHALK), (0.62, 0.08, MINT), (0.8, 0.1, CHALK)):
        a, b = route.length * share, route.length * (share + length)
        pts = route.slice(a, b)
        # Outside the loop, which goes round clockwise: left of the way it goes.
        edge = pts - _normals(pts) * (ribbon.half(a) + 10 * u)
        stroke = _Stroke(_curled([tuple(point) for point in edge[::6]], 11 * u, u), 2.2 * u, rnd, u, wobble=0.6, ends=(10, 3))
        t_a = ribbon.time_at(a)
        t_b = ribbon.time_at(b)
        out.append(_Line(stroke, color, t_a, max(0.12, t_b - t_a), (4.3 + 0.08 * len(out), 4.62 + 0.08 * len(out)), smudge=True))
    return out


# The notebook ---------------------------------------------------------------------------------


class _Book:
    """吴邪's brown leather notebook: a loose pencil sketch over a watercolour wash, its strap and a
    small red seal. It tumbles in along the lane, flips open in the left margin and riffles as it
    drifts on, is whisked off ahead of the fold; blows back in along the top band at the gust,
    gathers its leaves, snaps shut and is carried off the top right."""

    SCALE = 2.0

    def __init__(self, plan: _Plan, tooth: _Tooth) -> None:
        self.plan = plan
        u = plan.u
        # Closed it is 165 by 110 points: no taller than the lane between the name rows.
        self.cw, self.ch = 165 * u, 110 * u
        self.covers = [self._cover(v, tooth) for v in range(3)]
        self.spreads = [self._spread(v, tooth) for v in range(3)]
        self.tooth = tooth
        lane = plan.lane
        w = plan.w
        # (time, x, y) on its way: in along the lane, open over the left margin, drifting on, whisked off.
        self.out_path = [(TUMBLE[0], -110 * u, lane - 10 * u), (TUMBLE[1], max(self.cw * 1.05, plan.x(200)), lane), (1.02, plan.x(290), lane + 2 * u),
                         (1.4, plan.x(820), lane - 4 * u), (1.62, plan.x(1290), lane - 6 * u), (1.95, w + 260 * u, lane - 10 * u)]  # fmt: skip
        title = plan.title
        # Back in along the top band, over the title, shut right of it and away off the top right.
        self.home_path = [(3.45, -160 * u, plan.y(170)), (3.75, plan.x(330), plan.y(130)), (4.0, title.center().x(), max(55 * u, title.top() - 14 * u)),
                          (SHUT, plan.x(1360), plan.y(125)), (4.7, w + 200 * u, -110 * u)]  # fmt: skip

    def _wash(self, m: np.ndarray, scale: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
        """Leather in watercolour: granulated, darker where the wash dried at its edges, a bloom
        where it slowed, lighter where the paper shows."""
        h, w = m.shape
        soft = blur(m, 2.0 * scale)
        rim = np.clip((m - soft) * 2.6, 0, 1)
        flow = noise(w, h, 14 * scale, 3, seed)
        gran = noise(w, h, 1.1 * scale, 2, seed + 1)
        tone = 0.94 + 0.16 * (flow - 0.5) - 0.22 * (gran - 0.5)
        color = rgb(LEATHER) * tone[..., None]
        color = _mix(color, rgb("#a2846a"), smooth(0.58, 0.8, flow) * 0.45)
        color = _mix(color, rgb(HIDE), rim * 0.6)
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        bx, by, br = w * 0.7, h * 0.32, min(w, h) * 0.17
        ragged = br * (1 + 0.25 * (noise(w, h, 3 * scale, 2, seed + 2) - 0.5))
        blot = smooth(1.5, -1.5, np.hypot(xs - bx, ys - by) - ragged)
        bloom_rim = np.clip(blur(blot, 1.0 * scale) - blot * 0.7, 0, 1) * blot
        color = _mix(color, rgb("#9a7c61"), blot * 0.4)
        color = _mix(color, rgb(HIDE), np.clip(bloom_rim * 2.2, 0, 1) * 0.5)
        return color, m * (0.95 + 0.05 * gran)

    def _cover(self, v: int, tooth: _Tooth) -> QImage:
        u, s = self.plan.u, self.SCALE
        pad = 8 * u
        W, H = self.cw + 2 * pad, self.ch + 2 * pad
        rnd = random.Random(101)
        body = _deckle(self.cw, self.ch, rnd, u, 0.5) + (W / 2, H / 2)
        m = _fill_mask(math.ceil(W * s), math.ceil(H * s), s, body)
        color, alpha = self._wash(m, s, 110)
        # The strap: an olive band down near the right edge.
        strap = _fill_mask(m.shape[1], m.shape[0], s, QRectF(pad + self.cw * 0.8, pad - 3 * u, 8 * u, self.ch + 6 * u))
        color = _mix(color, rgb(OLIVE) * (0.9 + 0.2 * noise(m.shape[1], m.shape[0], 1.2 * s, 2, 7))[..., None], strap * 0.95)
        alpha = np.maximum(alpha, strap * 0.97)
        # The seal: a small round red stamp, uneven as a stamp is.
        ys, xs = np.mgrid[0 : m.shape[0], 0 : m.shape[1]].astype(np.float32)
        sx, sy, sr = (pad + self.cw * 0.2) * s, (pad + self.ch * 0.74) * s, 8 * u * s
        rr = np.hypot(xs - sx, ys - sy)
        stamp = smooth(sr + 0.7 * s, sr - 0.7 * s, rr) * (1 - 0.8 * smooth(0.3 * s, 0, np.abs(rr - sr * 0.62))) * (0.7 + 0.3 * noise(m.shape[1], m.shape[0], 1.0 * s, 2, 9))
        color = _mix(color, rgb(SEAL), np.clip(stamp, 0, 1) * 0.9)
        image = picture(color, alpha)
        image.setDevicePixelRatio(s)
        q = QPainter(image)
        q.setRenderHint(QPainter.Antialiasing)
        rnd = random.Random(120)
        # Its outline in the leather's line, the spine's fold, the strap's edges, a tiny fish in the seal.
        hide = tooth.brush(HIDE)
        corners = [(pad, pad), (pad + self.cw, pad), (pad + self.cw, pad + self.ch), (pad, pad + self.ch)]
        for k in range(4):
            line = _Stroke(_straight(corners[k], corners[(k + 1) % 4], rnd, u, 3.5), 1.5 * u, rnd, u, 0.35)
            line.fill(q, v, hide)
        _Stroke(_straight((pad + 7 * u, pad + 2 * u), (pad + 7 * u, pad + self.ch - 2 * u), rnd, u, 0), 1.1 * u, rnd, u, 0.3).fill(q, v, hide)
        for x in (pad + self.cw * 0.8, pad + self.cw * 0.8 + 8 * u):
            _Stroke(_straight((x, pad - 3 * u), (x, pad + self.ch + 3 * u), rnd, u, 0), 1.0 * u, rnd, u, 0.2).fill(q, v, hide)
        # A red tassel hanging from the spine's foot.
        red = tooth.brush(SEAL)
        for k in range(5):
            dx = (k - 2) * 1.1 * u
            pts = np.array([(pad + 5 * u, pad + self.ch - 3 * u), (pad + 3 * u + dx * 0.5, pad + self.ch + 1 * u), (pad + 1 * u + dx * 1.4, pad + self.ch + 7 * u)])
            _Stroke(pts, 1.1 * u, rnd, u, 0.1, ends=(1, 2)).fill(q, v, red)
        # A small fish cut into the seal.
        seal = QPointF(pad + self.cw * 0.2, pad + self.ch * 0.74)
        fish = np.array([(seal.x() - 4.5 * u, seal.y() - 1.5 * u), (seal.x() - 3 * u, seal.y()), (seal.x() - 4.5 * u, seal.y() + 1.5 * u),
                         (seal.x() + 1 * u, seal.y() - 2.4 * u), (seal.x() + 4 * u, seal.y()), (seal.x() + 1 * u, seal.y() + 2.4 * u), (seal.x() - 3 * u, seal.y())])  # fmt: skip
        _Stroke(fish, 0.8 * u, rnd, u, 0.05, ends=(1, 1)).fill(q, v, tooth.brush("#f6e9e0", 0.9))
        # A chalk line sketched loosely round its top and left, for the dark game round it.
        chalk = tooth.brush(CHALK, 0.85)
        for p0, p1 in ((corners[3], corners[0]), (corners[0], corners[1])):
            off = np.array([-2.2, -2.2]) * u
            _Stroke(_straight(tuple(np.array(p0) + off), tuple(np.array(p1) + off), rnd, u, 6), 1.1 * u, rnd, u, 0.6).fill(q, v, chalk)
        q.end()
        return image

    def _spread(self, v: int, tooth: _Tooth) -> QImage:
        """Open: the leather round two white pages ruled in teal, a bamboo doodle on one and a fish on
        the other, the gutter shaded in pencil."""
        u, s = self.plan.u, self.SCALE
        pad = 8 * u
        W, H = self.cw * 2 + 2 * pad, self.ch + 2 * pad
        rnd = random.Random(131)
        body = _deckle(self.cw * 2, self.ch, rnd, u, 0.5) + (W / 2, H / 2)
        w, h = math.ceil(W * s), math.ceil(H * s)
        m = _fill_mask(w, h, s, body)
        color, alpha = self._wash(m, s, 140)
        pages = _fill_mask(w, h, s, QRectF(pad + 10 * u, pad + 8 * u, self.cw * 2 - 20 * u, self.ch - 16 * u))
        paper = _paper(w, h, s, 150, "#f1f7f2")
        # The page block's edges washed mint, and the stack of pages showing at its sides.
        rim = np.clip(1 - blur(pages, 5 * u * s) * 1.4, 0, 1) * pages
        paper = _mix(paper, rgb(WET), np.clip(rim * 1.3, 0, 1))
        xs = np.arange(w, dtype=np.float32)[None, :] / s
        gutter = np.exp(-np.abs(xs - W / 2) / (7 * u))
        paper = paper * (1 - 0.1 * gutter)[..., None]
        color = _mix(color, paper, pages)
        image = picture(color, alpha)
        image.setDevicePixelRatio(s)
        q = QPainter(image)
        q.setRenderHint(QPainter.Antialiasing)
        rules = tooth.brush(TEAL, 0.55)
        y = pad + 16 * u
        while y < pad + self.ch - 8 * u:
            for x0, x1 in ((pad + 10 * u, W / 2 - 6 * u), (W / 2 + 6 * u, pad + self.cw * 2 - 10 * u)):
                _Stroke(_straight((x0, y), (x1, y), rnd, u, 0), 0.8 * u, rnd, u, 0.2, ends=(8, 8)).fill(q, v, rules)
            y += 11 * u
        graphite = tooth.brush(GRAPHITE)
        teal = tooth.brush(TEAL)
        lines, hatch, _shape = _bamboo_leaf((pad + 28 * u, pad + 70 * u), -32, 52 * u, u, rnd, GRAPHITE, TEAL, 1.1 * u)
        for stroke in lines:
            stroke.fill(q, v, graphite)
        for stroke in hatch:
            stroke.fill(q, v, teal)
        groups, _box = _fish_ring(QPointF(W / 2 + self.cw / 2, H / 2), u * 0.75, random.Random(160), on_paper=True)
        for strokes, color in groups:
            for stroke in strokes:
                stroke.fill(q, v, tooth.brush(color))
        soft = tooth.brush(SOFT, 0.8)
        for seg in _hatch(np.array([[W / 2 - 6 * u, pad + 6 * u], [W / 2, pad + 6 * u], [W / 2, pad + self.ch - 6 * u], [W / 2 - 6 * u, pad + self.ch - 6 * u]]), 70, 2.4 * u, rnd, u, 0.3):
            _Stroke(seg, 0.8 * u, rnd, u, 0.05, ends=(1, 2)).fill(q, v, soft)
        hide = tooth.brush(HIDE)
        corners = [(pad, pad), (W - pad, pad), (W - pad, H - pad), (pad, H - pad)]
        for k in range(4):
            _Stroke(_straight(corners[k], corners[(k + 1) % 4], rnd, u, 3.5), 1.5 * u, rnd, u, 0.35).fill(q, v, hide)
        _Stroke(_straight((W / 2, pad + 2 * u), (W / 2, H - pad - 2 * u), rnd, u, 0), 1.2 * u, rnd, u, 0.3).fill(q, v, tooth.brush(GRAPHITE))
        chalk = tooth.brush(CHALK, 0.85)
        off = np.array([-2.2, -2.2]) * u
        for p0, p1 in ((corners[3], corners[0]), (corners[0], corners[1])):
            _Stroke(_straight(tuple(np.array(p0) + off), tuple(np.array(p1) + off), rnd, u, 6), 1.1 * u, rnd, u, 0.6).fill(q, v, chalk)
        q.end()
        return image

    @staticmethod
    def _follow(path: list[tuple[float, float, float]], t: float) -> tuple[float, float, float]:
        """Where along path (time, x, y) it is at t, and its heading in degrees."""
        times = [p[0] for p in path]
        if t <= times[0]:
            return path[0][1], path[0][2], 0.0
        if t >= times[-1]:
            return path[-1][1], path[-1][2], 0.0
        i = max(0, np.searchsorted(times, t) - 1)
        p0, p1 = path[i], path[i + 1]
        k = (t - p0[0]) / (p1[0] - p0[0])
        pm = path[i - 1] if i > 0 else p0
        pn = path[i + 2] if i + 2 < len(path) else p1
        # Catmull-Rom between the points, for a curving way.
        x = 0.5 * (2 * p0[1] + (-pm[1] + p1[1]) * k + (2 * pm[1] - 5 * p0[1] + 4 * p1[1] - pn[1]) * k * k + (-pm[1] + 3 * p0[1] - 3 * p1[1] + pn[1]) * k ** 3)
        y = 0.5 * (2 * p0[2] + (-pm[2] + p1[2]) * k + (2 * pm[2] - 5 * p0[2] + 4 * p1[2] - pn[2]) * k * k + (-pm[2] + 3 * p0[2] - 3 * p1[2] + pn[2]) * k ** 3)
        return x, y, math.degrees(math.atan2(p1[2] - p0[2], p1[1] - p0[1]))

    def where(self, t: float) -> tuple[float, float]:
        """Where it is at t (for the leaves flying home to it)."""
        x, y, _ = self._follow(self.home_path, t)
        return x, y

    def paint(self, p: QPainter, t: float, tq: float, v: int) -> None:
        if self.out_path[0][0] <= tq <= self.out_path[-1][0]:
            self._paint_out(p, tq, v)
        elif self.home_path[0][0] <= tq <= self.home_path[-1][0]:
            self._paint_home(p, tq, v)

    def _paint_out(self, p: QPainter, t: float, v: int) -> None:
        x, y, heading = self._follow(self.out_path, t)
        if t < TUMBLE[1]:
            # Tumbling in: flipping over and over end on, on twos.
            # Its middle is half a cover right of the spine it opens about.
            flip = math.cos((t - TUMBLE[0]) * 24)
            _put(p, self.covers[v], x + self.cw / 2, y, 8 * math.sin(t * 17), 1.0, max(0.12, abs(flip)) * (1 if flip >= 0 else -1))
            return
        opening = win(t, TUMBLE[1], TUMBLE[1] + 0.12)
        if opening < 1:
            self._open(p, x, y, opening, v)
            return
        if t < AWAY:
            self._riffle(p, x, y, t - TUMBLE[1] - 0.12, v, 2 * math.sin(t * 9) + 0.08 * heading)
            return
        # The wind snaps it shut and whisks it off, its pages fanning out of its edge.
        shut = win(t, AWAY, AWAY + 0.1)
        if shut < 1:
            self._open(p, x, y, 1 - shut, v)
            return
        self._closed(p, x + self.cw / 2, y, t, v, 3 * math.sin(t * 11))

    def _closed(self, p: QPainter, x: float, y: float, t: float, v: int, angle: float) -> None:
        """Shut and carried on the wind, three or four leaves fanning out of its fore-edge, flapping,
        their edges washed mint."""
        u = self.plan.u
        p.save()
        p.translate(x, y)
        p.rotate(angle)
        edge = self.tooth.brush(GRAPHITE)
        for k in range(4):
            flap = 0.5 + 0.5 * math.sin(t * 19 + k * 1.7)
            reach = (10 + 26 * flap) * u * (1 - 0.15 * k)
            top, bottom = -self.ch / 2 + (4 + 3 * k) * u, self.ch / 2 - (4 + 2 * k) * u
            root = self.cw / 2 - 6 * u
            leaf = QPainterPath(QPointF(root, top))
            leaf.quadTo(QPointF(root + reach * 0.7, top - 6 * u * flap), QPointF(root + reach, top + 4 * u))
            leaf.lineTo(QPointF(root + reach * 0.9, bottom - 2 * u))
            leaf.quadTo(QPointF(root + reach * 0.5, bottom + 4 * u * flap), QPointF(root, bottom))
            leaf.closeSubpath()
            p.fillPath(leaf, QBrush(mix("#eef6f0", WET, 0.25 + 0.2 * k)))
            p.strokePath(leaf, QPen(edge, 1.1 * u))
        _put(p, self.covers[v], 0, 0)
        p.restore()

    def _open(self, p: QPainter, x: float, y: float, k: float, v: int) -> None:
        """The cover swinging open about the spine (k 0 shut .. 1 open), the spread's right page under it."""
        spread = self.spreads[v]
        sw = spread.width() / spread.devicePixelRatio()
        sh = spread.height() / spread.devicePixelRatio()
        r = spread.devicePixelRatio()
        spine = x
        p.save()
        p.drawImage(QRectF(spine, y - sh / 2, sw / 2, sh), spread, QRectF(spread.width() / 2, 0, spread.width() / 2, spread.height()))
        c = math.cos(math.pi * k)
        if c > 0:
            cover = self.covers[v]
            cw = cover.width() / r
            ch = cover.height() / r
            p.translate(spine - 8 * self.plan.u * c, y)
            p.scale(c, 1)
            p.drawImage(QRectF(0, -ch / 2, cw, ch), cover)
        else:
            p.translate(spine, y)
            p.scale(-c, 1)
            p.drawImage(QRectF(-sw / 2, -sh / 2, sw / 2, sh), spread, QRectF(0, 0, spread.width() / 2, spread.height()))
        p.restore()

    def _riffle(self, p: QPainter, x: float, y: float, age: float, v: int, angle: float) -> None:
        """Open, its pages riffling over in the wind, two or three in the air at once."""
        u = self.plan.u
        p.save()
        p.translate(x, y)
        p.rotate(angle)
        _put(p, self.spreads[v], 0, 0)
        edge = self.tooth.brush(GRAPHITE)
        top, bottom = -self.ch / 2 + 6 * u, self.ch / 2 - 6 * u
        wide = self.cw - 8 * u
        for k in range(5):
            f = (age * 5.2 - k * 0.55) % 3.0
            if not 0.05 < f < 0.95:
                continue
            # Caught mid-turn more than lying flat, as a riffled page is.
            turn = 0.12 + 0.76 * f
            c = math.cos(math.pi * turn)
            brush = QBrush(mix("#f3f8f3", "#d3e6dc", 0.6 * math.sin(math.pi * turn)))
            lift = math.sin(math.pi * turn) * 9 * u
            reach = wide * c
            path = QPainterPath(QPointF(0, top))
            path.quadTo(QPointF(reach * 0.5, top - lift), QPointF(reach, top - lift * 0.4))
            path.lineTo(QPointF(reach, bottom - lift * 0.4))
            path.quadTo(QPointF(reach * 0.5, bottom - lift), QPointF(0, bottom))
            path.closeSubpath()
            p.fillPath(path, brush)
            # Its rules and its edge in pencil, drawn straight off with plain pens (it turns too fast to boil).
            rules = QPainterPath()
            for share in (0.25, 0.42, 0.59, 0.76):
                y0 = top + (bottom - top) * share
                rules.moveTo(2 * u, y0)
                rules.quadTo(QPointF(reach * 0.5, y0 - lift * (0.9 - 0.1 * share)), QPointF(reach * 0.95, y0 - lift * 0.4))
            p.strokePath(rules, QPen(self.tooth.brush(TEAL, 0.6), 0.8 * u))
            p.strokePath(path, QPen(edge, 1.3 * u))
        p.restore()

    def _paint_home(self, p: QPainter, t: float, v: int) -> None:
        x, y, heading = self._follow(self.home_path, t)
        tilt = 6 * math.sin(t * 7) + 0.2 * heading
        if t < SHUT - 0.08:
            self._riffle(p, x, y, t - 3.45, v, tilt)
            return
        if t > SHUT + 0.04:
            self._closed(p, x + self.cw / 2, y, t, v, tilt - 10 * win(t, SHUT, 4.7))
            return
        k = win(t, SHUT - 0.08, SHUT + 0.04)
        if k < 1:
            p.save()
            p.translate(x, y)
            p.rotate(tilt)
            self._open(p, 0, 0, 1 - k, v)
            p.restore()
            return
        _put(p, self.covers[v], x + self.cw / 2, y, tilt - 10 * win(t, SHUT, 4.7), 0.95, 0.95)


# The loose leaves -----------------------------------------------------------------------------


class _Route:
    """A smooth way through points, evenly spaced, with how far along each point is."""

    def __init__(self, points: list[tuple[float, float]], step: float) -> None:
        self.pts = _spline(points, step)
        self.s = _along(self.pts)
        self.length = float(self.s[-1])

    def at(self, d: float) -> tuple[float, float, float]:
        d = clamp(d, 0, self.length)
        x = float(np.interp(d, self.s, self.pts[:, 0]))
        y = float(np.interp(d, self.s, self.pts[:, 1]))
        i = min(len(self.s) - 2, int(np.searchsorted(self.s, d)))
        dx, dy = self.pts[i + 1] - self.pts[i]
        return x, y, math.atan2(dy, dx)

    def slice(self, a: float, b: float) -> np.ndarray:
        a, b = clamp(a, 0, self.length), clamp(b, 0, self.length)
        lo, hi = int(np.searchsorted(self.s, a)), int(np.searchsorted(self.s, b, side="right"))
        return self.pts[max(0, lo - 1) : max(lo + 1, hi)]


class _Leaf:
    """One loose leaf out of the notebook: white paper with a mint-washed deckle and a little
    graphite doodle, fluttering end over end on twos as it rides its route, and slipping back into
    the notebook at its end."""

    def __init__(self, plan: _Plan, route: _Route, lane: _Route, times: tuple[float, float, float], sprites: tuple[list[QImage], QImage], flutter: tuple[float, float, float], home: bool) -> None:
        self.plan = plan
        self.route, self.lane = route, lane
        self.born, self.start, self.end = times
        self.fronts, self.back = sprites
        self.spin, self.flip, self.phase = flutter
        self.home = home

    def distance(self, t: float) -> float:
        """How far along its way it is: at one steady speed, so it is as quick crossing a name row as
        anywhere."""
        return self.route.length * win(t, self.start, self.end)

    def turn(self, t: float) -> tuple[float, float]:
        """How far it has tumbled end over end (radians), and how far it has swung side to side."""
        return self.phase + self.flip * (t - self.start), 0.7 * math.sin(self.spin * t + self.phase)

    def place(self, tq: float, v: int = 0) -> tuple[QImage, QPointF, float, list[QPointF], float] | None:
        """Where it is and how it lies at tq, or None while it is not seen: its picture, its middle, its
        roll in degrees, its corners round its middle (before the roll) and its opacity."""
        if tq < self.born or tq >= self.end:
            return None
        x, y, heading = self.route.at(self.distance(tq))
        # Lifting off the sheet: it rises out of it, opening up from flat.
        rise = ease_out(win(tq, self.born, self.born + 0.15))
        # Home: it slides into the binding, small.
        home = win(tq, self.end - 0.14, self.end) if self.home else 0.0
        size = (0.75 + 0.25 * rise) * (1 - 0.65 * home)
        pitch, yaw = self.turn(tq)
        pitch *= rise
        roll = math.degrees(heading) * 0.2 + 18 * math.sin(self.spin * 0.7 * tq + self.phase)
        image = self.fronts[v] if math.cos(pitch) * math.cos(yaw) >= 0 else self.back
        w, h = image.width() / image.devicePixelRatio(), image.height() / image.devicePixelRatio()
        # Its corners turned in space and seen in perspective, as a sheet tumbling in the air is.
        depth = 4.0 * max(w, h)
        quad = []
        for cx, cy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
            y1, z1 = cy * math.cos(pitch), cy * math.sin(pitch)
            x2, z2 = cx * math.cos(yaw) + z1 * math.sin(yaw), -cx * math.sin(yaw) + z1 * math.cos(yaw)
            k = depth / (depth + z2)
            quad.append(QPointF(x2 * k * size, y1 * k * size))
        area = abs((quad[2].x() - quad[0].x()) * (quad[3].y() - quad[1].y()) - (quad[3].x() - quad[1].x()) * (quad[2].y() - quad[0].y()))
        if area < 0.02 * w * h * size * size:
            return None
        return image, QPointF(x, y), roll, quad, rise * (1 - home * 0.6)

    def corners(self, tq: float) -> list[QPointF]:
        """Its picture's corners on the screen at tq (none while it is not seen)."""
        placed = self.place(tq)
        if placed is None:
            return []
        _image, at, roll, quad, _alpha = placed
        a = math.radians(roll)
        return [QPointF(at.x() + c.x() * math.cos(a) - c.y() * math.sin(a), at.y() + c.x() * math.sin(a) + c.y() * math.cos(a)) for c in quad]

    def paint(self, p: QPainter, tq: float, v: int) -> None:
        placed = self.place(tq, v)
        if placed is None:
            return
        image, at, roll, quad, alpha = placed
        w, h = image.width() / image.devicePixelRatio(), image.height() / image.devicePixelRatio()
        p.save()
        p.translate(at)
        p.rotate(roll)
        p.setTransform(QTransform.quadToQuad(QPolygonF([QPointF(0, 0), QPointF(w, 0), QPointF(w, h), QPointF(0, h)]), QPolygonF(quad)), True)
        p.setOpacity(alpha)
        p.drawImage(QRectF(0, 0, w, h), image)
        p.restore()


def _leaf_sprites(plan: _Plan, doodle: str, size: float, seed: int, tooth: _Tooth) -> tuple[list[QImage], QImage]:
    """A leaf's two sides. The front: a loose-leaf page with its binder holes down one side, warm
    white with mint and teal washed into its deckle, faint teal rules, a mint watercolour wash
    behind a graphite doodle hatched teal, its edge gone round once in soft pencil; three boiling
    drawings. The back: a little greyer, the wash and rules showing through."""
    u, s = plan.u, 2.0
    rnd = random.Random(seed)
    tall = size * u
    wide = tall * 0.8
    pad = 7 * u
    W, H = wide + 2 * pad, tall + 2 * pad
    outline = _deckle(wide, tall, rnd, u, 0.9) + (W / 2, H / 2)
    w, h = math.ceil(W * s), math.ceil(H * s)
    holes = [np.array([(pad + 6 * u + 2.6 * u * math.cos(q), H / 2 + dy * tall + 2.6 * u * math.sin(q)) for q in np.linspace(0, math.tau, 16)])
             for dy in (-0.32, 0.0, 0.32)]  # fmt: skip
    m = _fill_mask(w, h, s, outline)
    punched = _fill_mask(w, h, s, *holes)
    fibre = noise(w, h, 1.0 * s, 2, seed)
    alpha = smooth(0.3 + 0.25 * fibre, 0.75 + 0.15 * fibre, blur(m, 0.9 * s)) * (1 - punched)
    flow = noise(w, h, 10 * u * s, 3, seed + 1)
    gran = noise(w, h, 1.2 * s, 2, seed + 2)
    color = _paper(w, h, s, seed + 3, "#eef6f0")
    # Mint and teal washed into the deckle, pooled darker at the very edge.
    edge = np.clip(1 - blur(m, 8 * u * s) * 1.3, 0, 1) * alpha
    color = _mix(color, rgb(WET), np.clip(edge * (0.9 + 0.7 * flow) * (0.8 + 0.4 * gran), 0, 1))
    color = _mix(color, rgb(TEAL), np.clip((edge - blur(edge, 1.0 * s)) * 4 + smooth(0.8, 1.0, edge) * 0.5, 0, 1) * 0.75)
    # A mint wash behind the doodle, granulated, its rim dried darker.
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    blob_r = min(wide, tall) * 0.44 * s
    ragged = noise(w, h, 6 * u * s, 3, seed + 4)
    d = np.hypot((xs - W * 0.54 * s) / 1.15, ys - H * 0.5 * s) - blob_r * (1 + 0.4 * (ragged - 0.5))
    blot = smooth(1.5, -1.5, d) * (1 - punched)
    blot_rim = np.clip((blot - blur(blot, 1.4 * s)) * 3, 0, 1)
    color = _mix(color, rgb("#bfe9d4"), blot * (0.7 + 0.3 * flow) * (0.8 + 0.4 * gran))
    color = _mix(color, rgb(MINT) * 0.85 + rgb(TEAL) * 0.15, blot_rim * 0.9)
    back_color = _mix(_paper(w, h, s, seed + 5, "#eef1ec"), color, 0.25)
    fronts = []
    for v in range(3):
        image = picture(color, alpha)
        image.setDevicePixelRatio(s)
        q = QPainter(image)
        q.setRenderHint(QPainter.Antialiasing)
        q.setCompositionMode(QPainter.CompositionMode_SourceAtop)
        r2 = random.Random(seed + 10)
        rules = tooth.brush(TEAL, 0.45)
        y = pad + 9 * u
        while y < H - pad - 3 * u:
            _Stroke(_straight((pad + 13 * u, y), (W - pad - 2 * u, y), r2, u, 0), 0.7 * u, r2, u, 0.2, ends=(6, 6)).fill(q, v, rules)
            y += 9.5 * u
        c = QPointF(W * 0.54, H / 2)
        small = size / 100
        if doodle == "window":
            groups, _box = _lattice(c, u, random.Random(seed + 20), on_paper=True, size=0.3 * small)
        elif doodle == "fish":
            groups, _box = _fish_ring(c, u, random.Random(seed + 20), on_paper=True, size=0.95 * small)
        elif doodle == "ripple":
            groups, _box = _ripples(c, u, random.Random(seed + 20), on_paper=True, size=0.25 * small)
        else:
            lines, hatch, _shape = _bamboo_leaf((W * 0.54 - tall * 0.3, H / 2 + tall * 0.2), -36, tall * 0.62, u, random.Random(seed + 20), GRAPHITE, TEAL, 1.2 * u)
            groups = [(lines, GRAPHITE), (hatch, TEAL)]
        for strokes, tint in groups:
            for stroke in strokes:
                stroke.fill(q, v, tooth.brush(tint))
        q.setCompositionMode(QPainter.CompositionMode_SourceOver)
        # Its edge gone round once in soft pencil, overshooting at the corners.
        soft = tooth.brush(SOFT, 0.85)
        corners = [(pad, pad), (W - pad, pad), (W - pad, H - pad), (pad, H - pad)]
        for k in range(4):
            _Stroke(_straight(corners[k], corners[(k + 1) % 4], r2, u, 3), 0.9 * u, random.Random(seed + 30 + 4 * v + k), u, 0.5).fill(q, v, soft)
        q.end()
        fronts.append(image)
    back = picture(back_color, alpha)
    back.setDevicePixelRatio(s)
    return fronts, back


def _leaves(plan: _Plan, book: _Book, tooth: _Tooth) -> list[_Leaf]:
    """Eight leaves, in pairs along four ways, crossing a name row only straight up or down, between
    two names and fast: across the top band left to right and down the right margin; along the lane
    right to left; from the top right in steps, down between two row-1 names, along the lane and down
    between two row-2 names to the low band; in low from the right edge and up into the lane. Then
    they ride the gust round the cards and home into the notebook."""
    u, w = plan.u, plan.w
    lane, low = plan.lane, plan.low
    gap = plan.gap
    L, R = plan.left_x, plan.right_x
    top = plan.y(150)
    k1, k2 = plan.keep1, plan.keep2
    rise1 = plan.between(plan.x(1096), 0)
    drop2 = plan.between(plan.x(419), 1)
    # Right of the button, between two row-2 names.
    up2 = max(gap.right() + 60 * u, plan.between(plan.x(1324), 1))
    up1 = plan.between(plan.x(864), 0)
    ways = {
        # Across the top band, down the right margin, low right of the gap, up into the lane, along
        # it and up between two row-1 names to the notebook in the top band.
        "top": ([(plan.x(90), top), (plan.x(380), plan.y(130)), (plan.title.center().x(), plan.y(40)), (plan.x(1300), plan.y(110)), (R, plan.y(170))],
                [(R, k1[0] - 20 * u), (R, k2[1] + 10 * u), (R - 50 * u, low), (up2 + 60 * u, low + 6 * u), (up2, k2[1] + 14 * u), (up2, k2[0] - 14 * u),
                 (up2 - 60 * u, lane), (up1 + 70 * u, lane), (up1, k1[1] + 12 * u), (up1, k1[0] - 16 * u)]),
        "lane": ([(plan.x(1420), lane), (plan.x(900), lane + 8 * u), (plan.x(500), lane - 6 * u), (L + 30 * u, lane)],
                 [(L, k1[1]), (L, plan.y(300))]),
        "diagonal": ([(plan.x(1400), plan.y(130)), (rise1 + 80 * u, plan.y(170)), (rise1, plan.y(250)), (rise1, k1[0] - 16 * u), (rise1, k1[1] + 14 * u),
                      (rise1 - 70 * u, lane), (drop2 + 70 * u, lane), (drop2, k2[0] - 14 * u), (drop2, k2[1] + 14 * u), (drop2 - 60 * u, low)],
                     [(L + 30 * u, low - 6 * u), (L, k2[0]), (L, plan.y(300))]),
        "low": ([(w + 60 * u, low + 8 * u), (up2 + 80 * u, low), (up2, k2[1] + 14 * u), (up2, k2[0] - 14 * u), (up2 - 70 * u, lane), (plan.x(600), lane + 6 * u),
                 (L + 40 * u, lane - 4 * u)],
                [(L, k1[1]), (L, plan.y(300))]),
    }  # fmt: skip
    doodles = {"top": ("window", "bamboo"), "lane": ("ripple", "fish"), "diagonal": ("bamboo", "window"), "low": ("fish", "ripple")}
    born = {"top": 2.02, "lane": 2.22, "diagonal": 2.26, "low": 2.3}
    arrive = {"top": (4.1, 4.2), "lane": (3.95, 4.05), "diagonal": (4.0, 4.12), "low": (4.15, 4.24)}
    rnd = random.Random(211)
    out = []
    seed = 300
    for name in ("top", "lane", "diagonal", "low"):
        lead, ride = ways[name]
        for k in range(2):
            end = arrive[name][k]
            bx, by = book.where(end)
            first = list(lead)
            if k:
                first[0] = (first[0][0] + (40 * u if name != "low" else 50 * u), first[0][1] + 6 * u)
            if name == "top":
                home = [(up1, plan.y(250)), (bx, by)]
            else:
                home = [(L + 10 * u, plan.y(120)), (bx - 120 * u, by + 10 * u), (bx, by)]
            route = _Route(first + ride + home, 2 * u)
            lane_route = _Route(first, 2 * u)
            size = rnd.uniform(100, 116) if name != "lane" else rnd.uniform(92, 100)
            sprites = _leaf_sprites(plan, doodles[name][k], size, seed, tooth)
            seed += 17
            b = born[name] + 0.05 * k
            flutter = (rnd.uniform(4, 7), rnd.uniform(9, 14) * (1 if k else -1), rnd.uniform(0, 6))
            out.append(_Leaf(plan, route, lane_route, (b, b + 0.06, end), sprites, flutter, True))
    return out


# Watercolour wind ribbons --------------------------------------------------------------------


class _Wash:
    """A watercolour wind ribbon along a way: a broad mint-to-teal brush stroke, baked once (at half
    the screen's pixels in the box round it: a wash is soft), with quick mint hatching over it if
    hatched; and what is left of it when it dries, its darker edge. Shown a stretch at a time: its head
    rounded as a brush tip, its tail thinning as the wash dries."""

    RATIO = 0.5

    def __init__(self, plan: _Plan, route: _Route, widths: np.ndarray, seed: int, strength: float = 1.6, hatch: bool = False) -> None:
        self.plan = plan
        self.route = route
        self.widths = widths
        u, r = plan.u, self.RATIO
        pts = route.pts
        pad = float(widths.max()) * 0.8 + 6 * u
        x0, y0 = pts[:, 0].min() - pad, pts[:, 1].min() - pad
        x1, y1 = pts[:, 0].max() + pad, pts[:, 1].max() + pad
        w, h = max(4, math.ceil((x1 - x0) * r)), max(4, math.ceil((y1 - y0) * r))
        color, alpha, dried = _brush_wash(pts, widths, (x0, y0), (w, h), r, u, seed, strength)
        if hatch:
            rnd = random.Random(seed)
            lines = mask(w, h, lambda q: self._hatching(q, x0, y0, r, rnd))
            lines = lines * (0.6 + 0.5 * noise(w, h, 0.8, 2, seed + 5))
            color = _mix(color, rgb("#e6f8ef"), np.clip(lines * 1.5, 0, 1))
            alpha = alpha * (1 - lines * 0.3) + 0.6 * lines
        self.image = picture(color, np.clip(alpha, 0, 1))
        self.dried = picture(_mix(color, rgb(WET_TEAL), 0.5), np.clip(dried, 0, 1))
        self.rect = QRectF(x0, y0, w / r, h / r)

    def _hatching(self, q: QPainter, x0: float, y0: float, r: float, rnd: random.Random) -> None:
        """Quick mint pencil hatching across the ribbon, slanting, uneven."""
        u = self.plan.u
        q.scale(r, r)
        q.translate(-x0, -y0)
        # Soft and half the pixels: a plain round pen does, each mark a little heavier or lighter.
        route = self.route
        marks = QPainterPath()
        d = rnd.uniform(0, 4) * u
        while d < route.length:
            x, y, heading = route.at(d)
            half = float(np.interp(d, route.s, self.widths)) / 2
            a = heading + math.radians(rnd.uniform(50, 72))
            off = rnd.uniform(-0.4, 0.4) * half
            length = half * rnd.uniform(0.35, 0.75)
            cx, cy = x - off * math.sin(heading), y + off * math.cos(heading)
            marks.moveTo(cx - length * math.cos(a), cy - length * math.sin(a))
            marks.quadTo(QPointF(cx + rnd.uniform(-1, 1) * u, cy + rnd.uniform(-1, 1) * u), QPointF(cx + length * math.cos(a), cy + length * math.sin(a)))
            d += rnd.uniform(4.0, 9.0) * u
        q.strokePath(marks, QPen(QColor("#ffffff"), 1.6 * u, Qt.SolidLine, Qt.RoundCap))

    def half(self, d: float) -> float:
        return float(np.interp(d, self.route.s, self.widths)) / 2

    def show(self, q: QPainter, tail: float, head: float, alpha: float = 1.0) -> QRectF:
        """The stretch from tail to head along the way (in points), its head a round brush tip, its
        tail thinning in steps the eye reads as a fade."""
        tail, head = max(0.0, tail), min(self.route.length, head)
        if head - tail < 2:
            return QRectF()
        pts = self.route.slice(tail, head)
        if len(pts) < 2:
            return QRectF()
        along = _along(pts) + tail
        half = np.interp(along, self.route.s, self.widths) / 2 + 6 * self.plan.u
        if head < self.route.length - 1:
            tip = np.clip((head - along) / np.maximum(half, 1e-3), 0, 1)
            half = half * np.sqrt(np.clip(1 - (1 - tip) ** 2, 0.05, 1))
        # Laid over itself from further and further along, so it thickens from its tail in steps.
        span = head - tail
        box = QRectF()
        r = self.RATIO
        for a, share in ((0.0, 0.36), (0.16, 0.36), (0.36, 0.55)):
            keep = along >= tail + a * span - 2
            if keep.sum() < 2:
                continue
            band = _band(pts[keep], half[keep])
            area = band.boundingRect().intersected(self.rect)
            if area.isEmpty():
                continue
            box = _union(box, area)
            source = QRectF((area.left() - self.rect.left()) * r, (area.top() - self.rect.top()) * r, area.width() * r, area.height() * r)
            q.save()
            q.setClipPath(band)
            q.setOpacity(alpha * share)
            q.drawImage(area, self.image, source)
            q.restore()
        return box

    def show_dried(self, q: QPainter, tail: float, head: float, alpha: float, drift: QPointF) -> QRectF:
        """Its dried edge over a stretch, drifting off with the wind."""
        pts = self.route.slice(max(0.0, tail), min(self.route.length, head))
        if len(pts) < 2 or alpha <= 0.01:
            return QRectF()
        band = _band(pts, float(self.widths.max()) * 0.6 + 8 * self.plan.u).translated(drift)
        q.save()
        q.setClipPath(band)
        q.setOpacity(alpha)
        q.drawImage(self.rect.translated(drift), self.dried)
        q.restore()
        return band.boundingRect()


class _WindRibbon:
    """A wind ribbon the breeze or the gust draws: its head running along its way over `run`, its
    tail `lag` seconds behind, the dried edge left behind the tail drifting off and fading."""

    def __init__(self, wash: _Wash, run: tuple[float, float], lag: float, dry: float = 0.35) -> None:
        self.wash, self.run, self.lag, self.dry = wash, run, lag, dry
        self.route = wash.route

    def head(self, t: float) -> float:
        k = win(t, *self.run)
        return self.route.length * (0.6 * k + 0.4 * k * k * (3 - 2 * k))

    def half(self, d: float) -> float:
        return self.wash.half(d)

    def time_at(self, d: float) -> float:
        ks = np.linspace(0, 1, 200)
        heads = [self.head(self.run[0] + k * (self.run[1] - self.run[0])) for k in ks]
        return self.run[0] + float(np.interp(d, heads, ks)) * (self.run[1] - self.run[0])

    def paint(self, q: QPainter, t: float) -> QRectF:
        if t <= self.run[0] or t > self.run[1] + self.lag + self.dry:
            return QRectF()
        head, tail = self.head(t), self.head(t - self.lag)
        drawn = self.wash.show(q, tail, head)
        # Behind the tail, its dried edge for a moment, drifting on with the wind.
        if tail > 0:
            dried_from = self.head(t - self.lag - self.dry)
            since = max(0.0, t - self.run[0] - self.lag)
            fade = 1 - win(t, self.run[1] + self.lag, self.run[1] + self.lag + self.dry)
            drift = QPointF(60 * self.wash.plan.u * since, -8 * self.wash.plan.u * since)
            drawn = _union(drawn, self.wash.show_dried(q, dried_from, tail, fade, drift))
        return drawn


def _width(base: float, route: _Route, rnd: random.Random, u: float) -> np.ndarray:
    """A brush's width along a way: landing thin, pressed full, lifting to a point, and swelling and
    thinning as the hand goes."""
    k = route.s / max(route.length, 1e-6)
    shape = np.clip(k / 0.12, 0, 1) ** 0.6 * np.clip((1 - k) / 0.25, 0, 1) ** 0.8
    return base * (0.82 + _tremor(route.s, rnd, 0.2, 260 * u)) * np.maximum(shape, 0.08)


def _breezes(plan: _Plan) -> list[_WindRibbon]:
    """The breeze's watercolour ribbons, wide and mint, sweeping in from the left as the speed lines
    do: across the top band above the title, along the lane under the notebook, down the left margin
    and low either side of the gap; then, as the sheet is laid, two low ones streaming off the fold's
    foot and one along the lane after the notebook."""
    u = plan.u
    g = plan.gap
    lane, low = plan.lane, plan.low
    rnd = random.Random(901)
    plans = (
        (_swoop((-60 * u, plan.y(36)), (plan.w + 60 * u, plan.y(30)), 9 * u, 1.3, 0.5), 56, (0.02, 0.75), 0.4),
        (_swoop((-60 * u, lane + 6 * u), (plan.x(1400), lane), 16 * u, 1.8, 1.2), 66, (0.18, 1.05), 0.42),
        (_swoop((plan.left_x - 4 * u, -40 * u), (plan.left_x + 6 * u, plan.h + 40 * u), 14 * u, 1.1, 0.0), 54, (0.06, 0.7), 0.35),
        (_swoop((-60 * u, low + 10 * u), (g.left() - 30 * u, low - 2 * u), 12 * u, 0.9, 2.0), 58, (0.12, 0.62), 0.3),
        (_swoop((g.right() + 30 * u, low + 6 * u), (plan.w + 60 * u, low - 4 * u), 12 * u, 0.9, 0.8), 58, (0.2, 0.68), 0.3),
        (_swoop((-60 * u, low), (g.left() - 30 * u, low + 4 * u), 12 * u, 1.0, 3.0), 52, (1.02, 1.42), 0.28),
        (_swoop((g.right() + 30 * u, low - 2 * u), (plan.w + 60 * u, low + 6 * u), 12 * u, 1.0, 1.5), 52, (1.55, 1.95), 0.28),
        (_swoop((plan.x(250), lane + 4 * u), (plan.w + 80 * u, lane), 16 * u, 1.6, 2.4), 60, (1.05, 1.75), 0.35),
    )
    out = []
    for index, (points, width, run, lag) in enumerate(plans):
        route = _Route(points, 3 * u)
        wash = _Wash(plan, route, _width(width * u, route, rnd, u), 910 + index, 1.75, hatch=index % 2 == 1)
        out.append(_WindRibbon(wash, run, lag))
    return out


class _Trails:
    """Wide mint ribbons of watercolour and hatching behind the leaves along their lanes: each lane's
    baked once along its way and shown through a window that follows the leaf, fading toward its tail."""

    def __init__(self, plan: _Plan, leaves: list[_Leaf]) -> None:
        self.plan = plan
        u = plan.u
        self.leaves = leaves
        self.washes: list[_Wash] = []
        # Leaves on the same lane share its trail.
        self.lane_of: list[int] = []
        rnd = random.Random(400)
        for leaf in leaves:
            match = None
            for index, wash in enumerate(self.washes):
                route = wash.route
                if np.hypot(*(route.pts[-1] - leaf.lane.pts[-1])) < 60 * u and np.hypot(*(route.pts[0] - leaf.lane.pts[0])) < 80 * u:
                    match = index
            if match is None:
                self.washes.append(_Wash(plan, leaf.lane, _width(44 * u, leaf.lane, rnd, u), 400 + len(self.washes), 1.7, hatch=True))
                match = len(self.washes) - 1
            self.lane_of.append(match)

    def paint(self, q: QPainter, t: float) -> QRectF:
        u = self.plan.u
        drawn = QRectF()
        tq = math.floor(t * TWOS) / TWOS
        for leaf, index in zip(self.leaves, self.lane_of, strict=True):
            if leaf.start < tq < leaf.end:
                head = leaf.distance(tq)
                length = 300 * u
                if head - length < leaf.lane.length:
                    drawn = _union(drawn, self.washes[index].show(q, head - length, min(head, leaf.lane.length)))
        return drawn


def _gust(plan: _Plan) -> _WindRibbon:
    """The gust: a broad watercolour ribbon, mint into teal, drawing itself once round the cards
    (down the right margin, low right of the gap, up over the row-2 avatars and down again, low left
    of the gap, up the left margin, along the top and off the top right), blooming where it turns, a
    few yellow-green touches; its tail follows its head and dries to its darker edge, drifting off."""
    u, r = plan.u, _Wash.RATIO
    g, low, lane = plan.gap, plan.low, plan.lane
    L, R = plan.left_x, plan.right_x
    points = [
        (R - 30 * u, -60 * u), (R, plan.y(160)), (R, plan.keep1[1]), (R - 4 * u, plan.keep2[1]), (R - 70 * u, low),
        ((g.right() + R) / 2, low + 8 * u), (g.right() + 40 * u, low - 4 * u), (g.right() - 20 * u, lane + 14 * u),
        (g.center().x(), lane - 4 * u), (g.left() + 20 * u, lane + 14 * u), (g.left() - 40 * u, low - 4 * u),
        (g.left() / 2, low + 8 * u), (L + 40 * u, low), (L, plan.keep2[0]), (L - 4 * u, plan.y(250)), (L + 60 * u, plan.y(70)),
        (plan.x(500), plan.y(36)), (plan.x(1100), plan.y(30)), (plan.w + 100 * u, -60 * u),
    ]  # fmt: skip
    route = _Route(points, 3 * u)
    rnd = random.Random(71)
    # As wide as there is room: narrower between the rows and in the low band.
    widths = []
    for _x, y in route.pts:
        room = 100 * u
        if plan.keep1[1] < y < plan.keep2[0]:
            room = min(room, plan.lane_room * 0.62)
        if y > plan.keep2[1]:
            room = min(room, (plan.h - plan.keep2[1]) * 0.66)
        widths.append(max(56 * u, room))
    widths = np.array(widths) * (0.8 + _tremor(route.s, rnd, 0.22, 420 * u))
    widths = np.convolve(np.pad(widths, 40, mode="edge"), np.ones(81) / 81, mode="valid")
    wash = _Wash(plan, route, widths, 72, 1.7)
    _bloom(wash, plan, r)
    return _WindRibbon(wash, GUST, TAIL, dry=0.6)


def _bloom(wash: _Wash, plan: _Plan, r: float) -> None:
    """Blooms where the gust turns hardest and slowed, ragged pale blots, and a few touches of the
    swirl's yellow-green, worked into its baked wash."""
    u = plan.u
    pts = wash.route.pts
    d = np.gradient(pts, axis=0)
    bend = np.abs(np.gradient(np.unwrap(np.arctan2(d[:, 1], d[:, 0]))))
    turns: list[tuple[float, float, float]] = []
    for i in np.argsort(-bend):
        if len(turns) >= 6:
            break
        x, y = pts[i]
        if all(math.hypot(x - ox, y - oy) > 200 * u for ox, oy, _r in turns):
            turns.append((x, y, wash.widths[i] * 0.3))
    image = wash.image
    w, h = image.width(), image.height()
    rows = np.frombuffer(image.constBits(), dtype=np.uint8, count=image.bytesPerLine() * h).reshape(h, image.bytesPerLine())[:, : w * 4]
    premul = rows.reshape(h, w, 4).astype(np.float32) / 255
    # light.picture makes RGBA, premultiplied.
    alpha = premul[..., 3]
    color = premul[..., :3] / np.maximum(alpha, 1e-4)[..., None]
    ragged = noise(w, h, 4 * u * r, 3, 74)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x0, y0 = wash.rect.left(), wash.rect.top()
    bloom = np.zeros((h, w), dtype=np.float32)
    for bx, by, br in turns:
        rad = br * r * (1 + 0.8 * (ragged - 0.5))
        bloom = np.maximum(bloom, smooth(1.0, -1.0, np.hypot(xs - (bx - x0) * r, ys - (by - y0) * r) - rad))
    bloom = bloom * (alpha > 0.02)
    rim = np.clip((bloom - blur(bloom, 1.5 * u * r)) * 3, 0, 1)
    color = _mix(color, rgb(WET_LIGHT), bloom * 0.6)
    color = _mix(color, rgb(WET), rim * 0.6)
    alpha = alpha * (1 - 0.1 * bloom) + 0.12 * rim
    touches = smooth(0.8, 0.9, noise(w, h, 9 * u * r, 2, 75)) * smooth(0.1, 0.2, alpha)
    color = _mix(color, rgb(SWIRL), touches * 0.75)
    wash.image = picture(color, np.clip(alpha, 0, 1))


# Stars and bamboo leaves -----------------------------------------------------------------------


class _Pop:
    """A pencil doodle star or asterisk popping where a leaf flipped over, gone within 0.4 s."""

    def __init__(self, images: list[QImage], x: float, y: float, at: float, angle: float) -> None:
        self.images, self.x, self.y, self.at, self.angle = images, x, y, at, angle

    def paint(self, p: QPainter, tq: float, v: int) -> None:
        age = tq - self.at
        if age < 0 or age > 0.4:
            return
        size = min(1.0, age / 0.08) * (1.15 - 0.15 * win(age, 0.08, 0.2))
        p.save()
        p.setOpacity(1 - win(age, 0.22, 0.4))
        _put(p, self.images[v], self.x, self.y, self.angle, size, size)
        p.restore()


def _star_doodles(u: float, tooth: _Tooth) -> list[list[QImage]]:
    """Doodles, three drawings each: a five-point star drawn in one open stroke with an overshoot, in
    chalk with a little mint; and a pencil asterisk in mint."""
    out = []
    for kind in ("star", "asterisk", "star2"):
        images = []
        for v in range(3):
            rnd = random.Random(500 + v * 7 + len(out))
            side = 40 * u
            image = _sprite(side, side, 2.0)
            q = QPainter(image)
            q.setRenderHint(QPainter.Antialiasing)
            c = side / 2
            if kind.startswith("star"):
                r = (14 if kind == "star" else 11) * u
                pts = []
                for k in range(6):
                    a = -math.pi / 2 + k * 4 * math.pi / 5
                    rr = r * rnd.uniform(0.85, 1.12)
                    pts.append((c + rr * math.cos(a), c + rr * math.sin(a)))
                pts[-1] = (pts[-1][0] + rnd.uniform(2, 3.5) * u, pts[-1][1] + rnd.uniform(-1.5, 1.5) * u)
                _Stroke(np.array(pts), 2.0 * u, rnd, u, 0.2, ends=(3, 3)).fill(q, v, tooth.brush(CHALK if kind == "star" else MINT))
            else:
                for k in range(3):
                    a = math.radians(rnd.uniform(-8, 8) + 60 * k)
                    r = 10 * u * rnd.uniform(0.8, 1.1)
                    seg = np.array([(c - r * math.cos(a), c - r * math.sin(a)), (c + r * math.cos(a), c + r * math.sin(a))])
                    _Stroke(seg, 1.9 * u, rnd, u, 0.1, ends=(2, 2)).fill(q, v, tooth.brush(MINT))
            q.end()
            images.append(image)
        out.append(images)
    return out


def _stars(plan: _Plan, leaves: list[_Leaf], tooth: _Tooth) -> list[_Pop]:
    """A doodle wherever a leaf turned over in the air, away from the names, the gap and the title."""
    u = plan.u
    doodles = _star_doodles(u, tooth)
    out = []
    rnd = random.Random(311)
    for index, leaf in enumerate(leaves):
        for n in range(-40, 40):
            at = leaf.start + (math.pi / 2 + n * math.pi - leaf.phase) / leaf.flip
            if not (leaf.start + 0.2 < at < leaf.end - 0.1):
                continue
            at = math.floor(at * TWOS) / TWOS
            x, y, _ = leaf.route.at(leaf.distance(at))
            x += rnd.uniform(-18, 18) * u
            y += rnd.uniform(-18, 18) * u
            if plan.in_keep(x, y, 8 * u) or plan.near_gap(x, y, 30 * u) or plan.title.contains(QPointF(x, y)) or not (0 < x < plan.w and 0 < y < plan.h):
                continue
            if any(abs(other.at - at) < 0.1 and math.hypot(other.x - x, other.y - y) < 80 * u for other in out):
                continue
            out.append(_Pop(doodles[(index + n) % 3], x, y, at, rnd.uniform(-20, 20)))
    return out


class _Drift:
    """A pencil bamboo leaf on the wind, tumbling end over end on twos along its way."""

    def __init__(self, images: list[QImage], route: _Route, times: tuple[float, float], spin: float, phase: float) -> None:
        self.images, self.route, self.times, self.spin, self.phase = images, route, times, spin, phase

    def paint(self, p: QPainter, tq: float, v: int) -> None:
        a, b = self.times
        if not (a <= tq < b):
            return
        k = win(tq, a, b)
        x, y, heading = self.route.at(self.route.length * k)
        flip = math.cos(self.phase + tq * self.spin)
        p.save()
        p.setOpacity(min(1.0, (tq - a) / 0.1, (b - tq) / 0.15))
        _put(p, self.images[v], x, y, math.degrees(heading) + 40 * math.sin(tq * 5 + self.phase), 1.0, 0.35 + 0.65 * abs(flip))
        p.restore()


def _bamboo(plan: _Plan, tooth: _Tooth) -> list[_Drift]:
    """Bamboo leaves on the wind all through: washed solid mint, pale mint or sage, hatched teal,
    edged in chalk; tumbling along the title band, the lane, the low band and the left margin."""
    u = plan.u
    images = []
    for k, (length, wash) in enumerate(((72, WET), (62, WET_LIGHT), (54, "#a7b993"))):
        variants = []
        for v in range(3):
            rnd = random.Random(600 + k)
            size = length * u
            image = _sprite(size + 10 * u, size * 0.5 + 10 * u, 2.0)
            q = QPainter(image)
            q.setRenderHint(QPainter.Antialiasing)
            lines, hatch, shape = _bamboo_leaf((5 * u, size * 0.25 + 5 * u), 0, size, u, rnd, CHALK, MINT, 1.8 * u)
            q.setPen(Qt.NoPen)
            q.setBrush(tooth.brush(wash, 1.25))
            q.drawPolygon(_poly(shape))
            for stroke in hatch:
                stroke.fill(q, v, tooth.brush("#3d8f8a"))
            for stroke in lines:
                stroke.fill(q, v, tooth.brush(CHALK))
            q.end()
            variants.append(image)
        images.append(variants)
    w, h, lane, low = plan.w, plan.h, plan.lane, plan.low
    L, T = plan.left_x, plan.title
    g = plan.gap
    top = plan.y(150)
    paths = (
        # In on the breeze.
        ([(-50 * u, top + 40 * u), (plan.x(300), top - 20 * u), (T.left() - 40 * u, plan.y(40)), (plan.x(1250), plan.y(80)), (w + 50 * u, plan.y(30))], (0.04, 1.6)),
        ([(-50 * u, plan.y(60)), (plan.x(450), plan.y(110)), (plan.x(900), plan.y(30)), (w + 50 * u, plan.y(120))], (0.3, 1.9)),
        ([(-50 * u, lane + 20 * u), (plan.x(400), lane - 20 * u), (plan.x(900), lane + 24 * u), (w + 50 * u, lane - 10 * u)], (0.12, 1.45)),
        ([(-50 * u, lane - 10 * u), (plan.x(600), lane + 20 * u), (w + 50 * u, lane - 20 * u)], (0.45, 1.85)),
        ([(-50 * u, low + 20 * u), (g.left() * 0.5, low - 16 * u), (g.left() - 30 * u, low + 10 * u), (g.left() - 10 * u, h + 50 * u)], (0.2, 1.3)),
        ([(L - 30 * u, -40 * u), (L + 20 * u, plan.y(300)), (L - 20 * u, plan.y(600)), (L + 10 * u, h + 50 * u)], (0.1, 1.4)),
        ([(g.right() + 10 * u, h + 40 * u), ((g.right() + w) / 2, low - 14 * u), (w + 50 * u, low + 10 * u)], (0.35, 1.3)),
        ([(-50 * u, plan.y(220)), (plan.x(350), plan.y(180)), (T.left() - 60 * u, plan.y(220)), (T.left() + 40 * u, -40 * u)], (0.5, 1.5)),
        ([(-50 * u, lane + 30 * u), (plan.x(500), lane - 10 * u), (plan.x(1100), lane + 30 * u), (w + 50 * u, lane)], (0.7, 2.0)),
        ([(T.right() + 20 * u, -40 * u), (plan.x(1300), plan.y(120)), (w + 50 * u, plan.y(200))], (0.8, 1.7)),
        ([(-50 * u, low - 10 * u), (g.left() * 0.6, low + 20 * u), (g.left() - 40 * u, low - 16 * u), (g.left() * 0.8, h + 50 * u)], (0.9, 1.9)),
        # With the leaves, in the free bands.
        ([(-50 * u, plan.y(200)), (plan.x(500), plan.y(150)), (T.right() + 60 * u, plan.y(60)), (w + 50 * u, plan.y(180))], (2.05, 3.3)),
        ([(w + 50 * u, lane - 14 * u), (plan.x(900), lane + 20 * u), (-50 * u, lane - 6 * u)], (2.2, 3.6)),
        ([(w + 50 * u, low + 10 * u), ((g.right() + w) / 2, low - 20 * u), (g.right() + 20 * u, h + 50 * u)], (2.3, 3.1)),
        ([(L + 20 * u, h + 40 * u), (L - 20 * u, plan.y(500)), (L + 10 * u, -40 * u)], (2.5, 3.6)),
        ([(-50 * u, plan.y(100)), (T.left() - 20 * u, plan.y(30)), (T.right() + 40 * u, plan.y(40)), (w + 50 * u, plan.y(110))], (2.8, 3.9)),
        ([(w + 50 * u, lane + 20 * u), (plan.x(1000), lane - 20 * u), (plan.x(400), lane + 16 * u), (-50 * u, lane)], (3.0, 4.2)),
        # Off with the gust.
        ([(plan.x(300), plan.y(90)), (plan.x(900), plan.y(20)), (w + 50 * u, -40 * u)], (4.2, 5.0)),
        ([(plan.x(200), lane + 8 * u), (plan.x(800), lane - 10 * u), (w + 50 * u, lane - 20 * u)], (4.25, 5.0)),
        ([(L, plan.y(300)), (L - 20 * u, plan.y(100)), (-50 * u, -40 * u)], (4.3, 4.95)),
        ([(g.left() * 0.4, low), (g.left() - 40 * u, low - 20 * u), (g.left() * 0.2, h + 50 * u)], (4.2, 4.9)),
        ([((g.right() + w) / 2, low + 10 * u), (w + 50 * u, low - 30 * u)], (4.35, 5.0)),
    )
    rnd = random.Random(631)
    return [_Drift(images[k % 3], _Route(points, 2 * u), times, rnd.uniform(6, 10), rnd.uniform(0, 6)) for k, (points, times) in enumerate(paths)]


# The 嘉宾 marks -------------------------------------------------------------------------------

_MADE: dict[tuple, object] = {}


def _kept(key: tuple, build: Callable[[], object]):  # noqa: ANN202
    if key not in _MADE:
        _MADE[key] = build()
    return _MADE[key]


def _sharpness(p: QPainter) -> float:
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return round(max(2.0, ratio * math.hypot(p.transform().m11(), p.transform().m12())), 2)


def _page_card(rect: QRectF, scale: float, v: int) -> QImage:
    """The card: a notebook page, warm white with faint teal rules, its deckle washed mint, a boiling
    pencil border, and a leather spine strip down its left with the strap round it and a small seal."""
    u = 1.0
    tooth = _card_tooth()
    w, h = max(4, math.ceil(rect.width() * scale)), max(4, math.ceil(rect.height() * scale))
    body = QRectF(1.5, CARD_TOP + 1.5, rect.width() - 3, rect.height() - CARD_TOP - 3)
    rnd = random.Random(700)
    outline = _deckle(body.width(), body.height(), rnd, u, 0.6) + (body.center().x(), body.center().y())
    m = _fill_mask(w, h, scale, outline)
    alpha = smooth(0.2, 0.8, blur(m, 0.6 * scale))
    color = _paper(w, h, scale, 701)
    edge = np.clip(1 - blur(m, 4 * scale) * 1.3, 0, 1) * alpha
    flow = noise(w, h, 8 * scale, 3, 702)
    color = _mix(color, rgb(MINT), np.clip(edge * (0.7 + 0.5 * flow), 0, 1))
    spine_w = 13.0
    spine = _fill_mask(w, h, scale, QRectF(body.left(), body.top(), spine_w, body.height()))
    spine = spine * m
    gran = noise(w, h, 1.1 * scale, 2, 703)
    leather = rgb(LEATHER) * (0.92 + 0.16 * (flow - 0.5) - 0.2 * (gran - 0.5))[..., None]
    leather = _mix(leather, rgb(HIDE), np.clip((spine - blur(spine, 1.2 * scale)) * 2.5, 0, 1) * 0.6)
    color = _mix(color, leather, spine)
    image = picture(color, alpha)
    image.setDevicePixelRatio(scale)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    r2 = random.Random(710)
    rules = tooth.brush(TEAL, 0.45)
    y = body.top() + 8
    while y < body.bottom() - 4:
        _Stroke(_straight((body.left() + spine_w + 3, y), (body.right() - 3, y), r2, u, 0), 0.6, r2, u, 0.15, ends=(6, 6)).fill(q, 0, rules)
        y += 9
    # The strap round the spine and its seal.
    strap_y = body.center().y() - 3
    q.fillRect(QRectF(body.left() - 0.5, strap_y, spine_w + 3, 5), QColor(OLIVE))
    q.setBrush(QColor(SEAL))
    q.setPen(Qt.NoPen)
    q.drawEllipse(QPointF(body.left() + spine_w / 2, body.bottom() - 6), 2.6, 2.6)
    rnd = random.Random(720 + v)
    graphite = tooth.brush(GRAPHITE)
    corners = [(body.left(), body.top()), (body.right(), body.top()), (body.right(), body.bottom()), (body.left(), body.bottom())]
    for k in range(4):
        _Stroke(_straight(corners[k], corners[(k + 1) % 4], rnd, u, 2.5), 0.9, rnd, u, 0.35, ends=(4, 4)).fill(q, v, graphite)
    _Stroke(_straight((body.left() + spine_w, body.top()), (body.left() + spine_w, body.bottom()), rnd, u, 0), 0.8, rnd, u, 0.3).fill(q, v, tooth.brush(HIDE))
    q.end()
    return image


def _card_tooth() -> _Tooth:
    return _kept(("tooth",), lambda: _Tooth(1.0))


def _sprig(scale: float, v: int, length: float) -> QImage:
    """A bamboo sprig lying across the card's top: a thin stem, three leaves, graphite and teal."""
    tooth = _card_tooth()
    image = _sprite(length + 8, 22, scale)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    rnd = random.Random(740)
    stem = np.array([(4, 15), (length * 0.5, 13), (length, 15.5)])
    _Stroke(stem, 1.0, rnd, 1.0, 0.2, ends=(3, 3)).fill(q, v, tooth.brush(OLIVE))
    for k, (x, angle, size) in enumerate(((length * 0.62, -18, 17), (length * 0.7, 14, 15), (length * 0.4, -30, 13))):
        lines, hatch, shape = _bamboo_leaf((x, 14 - k * 0.5), angle, size, 1.0, random.Random(750 + k), GRAPHITE, TEAL, 0.8)
        # Washed mint first, so the leaf reads over the game as well as on the paper.
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#b9e2cd"))
        q.drawPolygon(_poly(shape))
        for stroke in hatch:
            stroke.fill(q, v, tooth.brush(TEAL))
        for stroke in lines:
            stroke.fill(q, v, tooth.brush(OLIVE))
    q.end()
    return image


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """The notebook page, boiling, and the bamboo sprig across its top, stirring a little."""
    scale = _sharpness(p)
    v = int(t * BOIL) % 3
    page = _kept(("card", round(rect.width()), round(rect.height()), scale, v), lambda: _page_card(rect, scale, v))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(rect, page)
    length = min(64.0, rect.width() * 0.4)
    sprig = _kept(("sprig", scale, v, round(length)), lambda: _sprig(scale, v, length))
    tq = math.floor(t * TWOS) / TWOS
    _put(p, sprig, rect.right() - length / 2 - 14, CARD_TOP - 1, -3 + 2.5 * math.sin(tq * 2.1))


def lead(size: float, index: int) -> QPixmap:
    """A tiny bamboo leaf before each name, in graphite and teal hatching."""
    scale = 3.0
    tooth = _card_tooth()
    image = _sprite(size, size, scale)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    lines, hatch, _shape = _bamboo_leaf((size * 0.12, size * 0.72), -38 + 10 * (index % 2), size * 0.9, 0.5, random.Random(760 + index), GRAPHITE, TEAL, 0.75)
    for stroke in hatch:
        stroke.fill(q, 0, tooth.brush(TEAL))
    for stroke in lines:
        stroke.fill(q, 0, tooth.brush(GRAPHITE))
    q.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def _loops(cover: QRectF, v: int) -> tuple[QPainterPath, QPainterPath]:
    """The ring's two pencil loops, as a word is circled in notes: each going round a little more
    than once and spiralling out so its ends overlap, a little different each drawing."""
    out = []
    for k, (grow, width, turns) in enumerate(((1.5, 2.2, 1.12), (4.0, 1.4, 1.06))):
        rnd = random.Random(800 + 10 * v + k)
        cx, cy = cover.center().x(), cover.center().y()
        rx, ry = cover.width() / 2 + grow, cover.height() / 2 + grow
        start = rnd.uniform(0, math.tau)
        q = np.linspace(0, math.tau * turns, 220)
        spread = q / q[-1] * 2.4
        # A squarish oval: a superellipse, as a hand goes round a button.
        c, s = np.cos(start + q), np.sin(start + q)
        ex = np.sign(c) * np.abs(c) ** 0.45 * (rx + spread)
        ey = np.sign(s) * np.abs(s) ** 0.6 * (ry + spread)
        pts = np.column_stack([cx + ex, cy + ey])
        stroke = _Stroke(pts, width, rnd, 1.0, 0.5, ends=(6, 8))
        out.append(stroke.path(0))
    return out[0], out[1]


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A pencil loop round the button, drawn twice, mint and chalk, boiling."""
    v = int(t * BOIL) % 3
    tooth = _card_tooth()
    where = (round(cover.x(), 1), round(cover.y(), 1), round(cover.width(), 1), round(cover.height(), 1))
    mint, chalk = _kept(("ring", *where, v), lambda: _loops(cover, v))
    p.fillPath(mint, tooth.brush(MINT))
    p.fillPath(chalk, tooth.brush(CHALK, 0.9))


def _medal(side: float, scale: float, v: int) -> QImage:
    """The three-fish ring for the badge: bronze and verdigris washed into each fish (granulated,
    darker where it dried at their edges), then drawn over in pencil, three drawings."""
    tooth = _card_tooth()
    c = QPointF(side / 2, side / 2)
    u = side / 92
    groups, _box = _fish_ring(c, u, random.Random(830), on_paper=True, size=1.25)
    w = h = math.ceil(side * scale)
    bodies = []
    for k in range(3):
        _strokes, body = _fish(c, 28 * u * 1.25, math.radians(-90 + 120 * k), math.radians(112), u, random.Random(831 + k), 1.0)
        bodies.append(body)
    m = _fill_mask(w, h, scale, *bodies)
    flow = noise(w, h, 6 * scale, 3, 840)
    gran = noise(w, h, 0.8 * scale, 2, 841)
    color = _mix(np.broadcast_to(rgb(BRONZE), (h, w, 3)), rgb(VERDIGRIS), np.clip(0.2 + 0.8 * flow, 0, 1))
    color = color * (0.9 + 0.2 * gran)[..., None]
    rim = np.clip((m - blur(m, 1.2 * scale)) * 2.5, 0, 1)
    color = _mix(color, rgb("#5a4a32"), rim * 0.5)
    image = picture(color, m * 0.92)
    image.setDevicePixelRatio(scale)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    # The pencil over it: chalk under a dark bronze line, so it reads on the wash and on the game; the
    # hatching in the shade side in teal.
    for strokes, tint in groups:
        for stroke in strokes:
            if tint == GRAPHITE:
                path = stroke.path(v)
                if path is not None:
                    halo = QPainterPathStroker()
                    halo.setWidth(1.1)
                    q.fillPath(halo.createStroke(path).united(path), tooth.brush(CHALK, 0.75))
                    q.fillPath(path, tooth.brush("#3a2f22"))
            elif tint == TEAL:
                stroke.fill(q, v, tooth.brush("#2f6f6c", 0.8))
    q.end()
    return image


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """The three-fish ring, turning once every six seconds, boiling."""
    scale = _sharpness(p)
    v = int(t * BOIL) % 3
    side = box.width()
    medal = _kept(("medal", round(side, 1), scale, v), lambda: _medal(side, scale, v))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    tq = math.floor(t * TWOS) / TWOS
    _put(p, medal, box.center().x(), box.center().y(), (tq * 60) % 360)
