"""数学 trial 3, Fractal: a blueprint night where the Mandelbrot set is found, not drawn.

The edges darken to blueprint navy with faint graph paper in them, fading toward the middle. In the
top right the complex plane's axes draw themselves, and the escape lines of z → z² + c close in on the
Mandelbrot set level by level, each flashing in chalk as it lands and staying faintly; then
the set itself lights, worked out per pixel: its edge burning white-blue by its distance estimate, its
inside deep navy, a blue glow round it, and the escape lines flowing on into it. A point c then moves
through it, its orbit 0, c, c² + c, … drawn in gold: a triangle in the period-3 bulb, a four-sided loop
in the period-4 one, a five-point star in the period-5 one, spiralling in between. In the top left a square wave
builds itself term by term out of turning circles, its Fourier sum tracing it out on axes and its
Gibbs overshoot showing; in the bottom right a Koch snowflake grows a level at a time. Equations write
themselves in chalk round the sides; at the end they crumble into chalk dust and everything fades.

Its marks are of the same blueprint. The ring is a ruler of coordinate ticks round 准备案件还原, two gold
readings running round it. The badge is a glass disc with the Mandelbrot set lit in it, a dial of ticks
on its rim, escape lines flowing into the set and a glint going round. The card is a dark blueprint plate, a fine grid in it,
the filigree of a Julia set showing faintly at its edges, a light running round its edge and a title tab
on top, 心动 ∈ ℳ; a plotted point comes before each name.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
    QTransform,
)

from blacklist_detect.love_scenes.draw import (
    Wash,
    catmull,
    clamp,
    col,
    ease_in,
    ease_in_out,
    ease_out,
    gradient,
    partial,
    polyline,
    soft_dot,
    win,
)
from blacklist_detect.love_scenes.light import bloom, blur, glow, mask, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
CHALK = "#7fd8ff"
INK = "#eaf6ff"
PINK = "#ff9fc4"
NAVY = "#0f2440"
DEEP = "#06142a"
NIGHT = "#030b18"
BLUE = "#2d6fa8"
GOLD = "#f3cf7a"
PALE_GOLD = "#fff6dc"
LOOK = {
    "glow": (127, 216, 255),
    "rim": "#7fd8ff",
    "band": ("#7fd8ff", "#f3cf7a"),
    "card": ("#0d2140", "#06142a"),
    "edge": "#5fb8e6",
    "ink": "#eaf6ff",
    "flowers": (("#f2fbff", "#9fe1ff", "#3fa9e0"), ("#fffaf0", "#f3cf7a", "#c99a3c")),
    "disc": ("#13304f", "#0a1a30"),
    "heart": ("#9fe1ff", "#3fa9e0"),
    "deep": "#3fa9e0",
    "deep_glow": (95, 190, 255),
}
MARKS_ANIMATED = True
# Room above the card for its title tab.
CARD_TOP = 16
# The equations' glow is soft: worked out at this share of the stage's size and laid on scaled up.
SOFT = 0.5
# The escape lines flow into the set through this many steps, each drawn once.
PHASES = 8
# The escape lines that land one at a time, by their smooth escape count, outermost first.
LEVELS = (3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 8.0, 9.0)
# Between one escape line and the next, in escape count.
SPACE = 0.5
LAND, LAND_STEP = 0.45, 0.1
# When the set lights, and when its escape lines start to flow.
IGNITE = LAND + LAND_STEP * len(LEVELS) + 0.05
FLOW = IGNITE + 0.35
# The point c: where it stops (the centres of the period-3, -4 and -5 bulbs, where its orbit is a
# triangle, a four-sided loop and a five-point star) and the way between, inside the set.
ORBIT_AT = IGNITE + 0.35
STOPS = (complex(-0.1226, 0.7449), complex(0.2823, 0.5301), complex(-0.5043, 0.5628))
VIA = (complex(0.05, 0.47), complex(-0.12, 0.42))
# The mark's room round the ring's cover and the badge's box (ui_overlay._GLOW).
ROOM = 9.0


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(31)
    paper = Wash(lambda q, w, h: _paper(q, w, h, u))
    # The complex plane in the top right: its origin, and points to one unit.
    origin, unit = QPointF(width - 112 * u, 128 * u), 100 * u
    hero = _Mandelbrot(origin, unit, QRectF(width - 470 * u, 0, 470 * u, 312 * u), u)
    fourier = _Fourier(QPointF(92 * u, 140 * u), 44 * u, QPointF(196 * u, 140 * u), 380 * u, 190 * u, u)
    koch = _Koch(QPointF(width - 100 * u, height - 84 * u), 64 * u)
    formulas = [
        _formula([("t", _it("f") + "(" + _it("x") + ") = "), ("frac", "4", _it("π")), ("t", " "), ("big", "∑"), ("under", _it("n") + " odd"), ("t", " "), ("frac", "sin " + _it("nx"), _it("n"))], 24 * u, QPointF(206 * u, 50 * u), 0.5, 1.3, GOLD, rnd),
        _formula([("t", _it("z")), ("sub", _it("n") + "+1"), ("t", " = " + _it("z")), ("sub", _it("n")), ("sup", "2"), ("t", " + "), ("t", _it("c"), True)], 28 * u, QPointF(origin.x() - 222 * u, 54 * u), 0.95, 1.65, GOLD, rnd, ends=True),
        _formula([("t", "|" + _it("z")), ("sub", _it("n")), ("t", "| ≤ 2")], 28 * u, QPointF(26 * u, height * 0.44), 1.35, 1.9, CHALK, rnd),
        _formula([("t", "dim"), ("sub", _it("H")), ("t", " ∂ℳ = 2")], 27 * u, QPointF(24 * u, height * 0.62), 2.0, 2.6, CHALK, rnd),
        _formula([("t", _it("D") + " = "), ("frac", "log 4", "log 3")], 27 * u, QPointF(koch.centre.x() - 92 * u, height * 0.935), 1.85, 2.45, CHALK, rnd, ends=True),
        _formula([("han", "心动", True), ("sub", _it("n") + "+1"), ("t", " = "), ("han", "心动", True), ("sub", _it("n")), ("sup", "2"), ("t", " + " + _it("c"))], 29 * u, QPointF(30 * u, height * 0.925), 2.7, 3.5, PINK, rnd),
    ]
    # Each crumbles to chalk dust in turn at the end, the last written last.
    for index, formula in enumerate(formulas):
        formula.leaves = 4.12 + 0.07 * index

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.3, 5.0))
        p.save()
        p.setOpacity(life)
        paper.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.8)) * (1 - leave))
        hero.paint(p, t, 1 - leave)
        fourier.paint(p, t, 1 - leave)
        koch.paint(p, t, u, 1 - leave)
        for formula in formulas:
            formula.paint(p, t, u)
        p.restore()

    return paint


def _paper(p: QPainter, width: float, height: float, u: float) -> None:
    """Blueprint navy at the edges, deepest at the top, and graph paper in it that fades out
    before the names: fine squares, every fifth line stronger."""
    top = height * 0.34
    p.fillRect(QRectF(0, 0, width, top), gradient(QPointF(0, 0), QPointF(0, top), ((0, DEEP, 0.86), (0.5, NAVY, 0.44), (1, NAVY, 0))))
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
    # Deeper night behind the set, so its light reads, and a little chalk-blue light behind the wave.
    for x, y, r, color, alpha in ((0.89, 0.15, 330, NIGHT, 0.55), (0.13, 0.16, 250, BLUE, 0.26), (0.94, 0.9, 170, BLUE, 0.22)):
        soft_dot(p, width * x, height * y, r * u, color, alpha)


# The Mandelbrot set ---------------------------------------------------------------------------------


def _escape(c: np.ndarray, iterations: int, chunk: int = 0):  # noqa: ANN202
    """Each point's smooth escape count under z → z² + c from 0 (nan for one that never leaves) and
    its distance estimate to the set in the plane's units, both float32. If chunk, it yields after
    each of the first, heavy iterations and then every chunk of them, so no frame waits on all of it;
    the result is the generator's return value (_run gets it at once)."""
    shape = c.shape
    c = c.ravel()
    mu = np.full(c.shape, np.nan, dtype=np.float32)
    distance = np.zeros(c.shape, dtype=np.float32)
    x, y = c.real, c.imag
    # The main cardioid and the period-2 bulb never escape: left out from the start.
    q = (x - 0.25) ** 2 + y * y
    inside = (q * (q + x - 0.25) <= 0.25 * y * y) | ((x + 1) ** 2 + y * y <= 0.0625)
    index = np.flatnonzero(~inside)
    z = np.zeros(index.shape, dtype=np.complex128)
    dz = np.zeros(index.shape, dtype=np.complex128)
    cc = c[index]
    if chunk:
        yield
    for n in range(iterations):
        dz = 2 * z * dz + 1
        z = z * z + cc
        size = z.real * z.real + z.imag * z.imag
        out = size > 65536.0
        if out.any():
            r = np.sqrt(size[out])
            mu[index[out]] = n + 2 - np.log2(np.log(r))
            distance[index[out]] = r * np.log(r) / np.abs(dz[out])
            keep = ~out
            z, dz, cc, index = z[keep], dz[keep], cc[keep], index[keep]
        if chunk and (n < 8 or n % chunk == chunk - 1):
            yield
    return mu.reshape(shape), distance.reshape(shape)


def _run(work):  # noqa: ANN001, ANN202
    """A generator's return value, run to its end."""
    try:
        while True:
            next(work)
    except StopIteration as done:
        return done.value


def _apart(mu: np.ndarray) -> np.ndarray:
    """Pixels between escape counts one apart, at each pixel (inside the set, as good as none)."""
    outside = np.isfinite(mu)
    filled = np.where(outside, mu, np.nanmax(mu) + 1 if outside.any() else 0).astype(np.float32)
    gy, gx = np.gradient(filled)
    return (1 / (np.hypot(gx, gy) + 1e-6)).astype(np.float32)


def _lines(mu: np.ndarray, apart: np.ndarray, phase: float, levels: tuple[float, float], density: float, space: float = 1.0, crowd: float = 2.5) -> np.ndarray:
    """Escape lines where mu is a whole number of spaces past phase (a share of one space), from
    levels[0] in to levels[1], the same fine width wherever they run, fading where they crowd
    together near the set (closer than crowd pixels, and fully past three times that): 0..1 for each
    pixel given (mu and apart, from _apart, alike in shape)."""
    q = mu * (1 / space) - phase
    off = np.abs(q - np.rint(q)) * (space * apart)
    line = np.exp(-((off * (1 / (0.8 * density))) ** 2)) + 0.22 / (1 + (off * (1 / (2.6 * density))) ** 2)
    # Where the next line is fewer than a few pixels away they would only blur together.
    room = smooth(crowd * density, crowd * 2.8 * density, space * apart)
    edge = space * 0.6
    band = smooth(levels[0] - edge, levels[0] + edge * 0.3, mu) * (1 - smooth(levels[1] - edge * 0.3, levels[1] + edge, mu))
    return np.nan_to_num(line * room * band)


def _tinted(value: np.ndarray, color: np.ndarray) -> QImage:
    """Light of one color, value (h, w) strong, as a picture that adds it over what is under (as
    light.glow makes it), straight in the painter's own format."""
    h, w = value.shape
    pixels = np.empty((h, w, 4), dtype=np.uint8)
    for channel, k in ((0, 2), (1, 1), (2, 0)):
        pixels[..., channel] = np.clip(value * color[k], 0, 1) * 255 + 0.5
    pixels[..., 3] = np.clip(value * color.max(), 0, 1) * 255 + 0.5
    return QImage(pixels.data, w, h, w * 4, QImage.Format_ARGB32_Premultiplied).copy()


def _composite(light: np.ndarray, dark: np.ndarray, dark_alpha: np.ndarray) -> QImage:
    """Light (as light.glow takes it) laid over a dark fill (straight color, alpha), as one picture."""
    light = np.maximum(light, 0)
    over = np.clip(light.max(axis=-1, keepdims=True) - 1, 0, None)
    light = light + over * 0.6
    top = np.clip(light.max(axis=-1), 0, 1)
    shown = np.clip(light, 0, 1)
    under = dark_alpha * (1 - top)
    alpha = top + under
    color = (shown + dark * under[..., None]) / np.maximum(alpha, 1e-4)[..., None]
    return _ready(picture(color, alpha))


def _bounds(alpha: np.ndarray, spare: int = 1) -> tuple[slice, slice]:
    """The rows and columns where alpha shows, spare pixels round them, so a picture need be no bigger."""
    rows, columns = np.flatnonzero(alpha.max(axis=1) > 0.004), np.flatnonzero(alpha.max(axis=0) > 0.004)
    if not len(rows):
        return slice(0, 1), slice(0, 1)
    h, w = alpha.shape
    return slice(max(0, rows[0] - spare), min(h, rows[-1] + 1 + spare)), slice(max(0, columns[0] - spare), min(w, columns[-1] + 1 + spare))


class _Mandelbrot:
    """The set in the top right of the complex plane, origin its 0 and unit points to 1.

    Its light is worked out per pixel on the first frames, a few milliseconds of it a frame (the
    escape counts, then each escape line, the set lit, each step of the flowing lines), each piece
    before it is wanted, and all at once if the scene is shown part way through."""

    def __init__(self, origin: QPointF, unit: float, box: QRectF, u: float) -> None:
        self.origin, self.unit, self.box, self.u = origin, unit, box, u
        self.density = 0.0
        self.pieces: dict = {}
        self.made = 0
        self.work = None
        # When each piece is wanted: the counts, the lines as they land, the set, the flow.
        self.wanted = [LAND - 0.05, *(LAND + LAND_STEP * i for i in range(len(LEVELS))), IGNITE, *(FLOW for _ in range(PHASES))]
        # The orbit's c along its way, stop to stop, inside the set.
        way = [STOPS[0], VIA[0], STOPS[1], VIA[1], STOPS[2]]
        self.way = catmull([QPointF(z.real, z.imag) for z in way], per=24)

    def paint(self, p: QPainter, t: float, fade: float) -> None:
        if fade <= 0:
            return
        self._build(p, t)
        _axes(p, t, self.origin, self.unit, self.u, fade)
        pieces = self.pieces
        ignite = ease_out(win(t, IGNITE, IGNITE + 0.55))
        flow = ease_in_out(win(t, FLOW, FLOW + 0.5))
        p.save()
        # The escape lines landing, each flashing and then staying faintly, till the flow takes over.
        for i, (image, rect) in enumerate(pieces.get("rings", ())):
            at = LAND + LAND_STEP * i
            k = win(t, at, at + 0.1)
            if k <= 0 or flow >= 1:
                break
            flash = 1 - 0.7 * ease_out(win(t, at + 0.1, at + 0.55))
            p.setOpacity(fade * k * flash * (1 - flow))
            p.drawImage(rect, image)
        if ignite > 0 and "core" in pieces:
            p.setOpacity(fade * ignite)
            p.drawImage(*pieces["body"][::-1])
            # The edge flares as it lights, then breathes.
            flare = math.sin(math.pi * win(t, IGNITE, IGNITE + 0.7))
            p.setOpacity(fade * ignite * (0.85 + 0.15 * math.sin(t * 2.6)))
            p.drawImage(*pieces["core"][::-1])
            if flare > 0:
                p.setOpacity(fade * flare * 0.9)
                p.drawImage(*pieces["core"][::-1])
        flows = pieces.get("flow", ())
        if flow > 0 and len(flows) == PHASES:
            steps = (t - FLOW) * 0.55 % 1 * PHASES
            i, f = int(steps), steps - int(steps)
            image, rect = flows[i % PHASES]
            p.setOpacity(fade * flow * 0.3 * (1 - f))
            p.drawImage(rect, image)
            image, rect = flows[(i + 1) % PHASES]
            p.setOpacity(fade * flow * 0.3 * f)
            p.drawImage(rect, image)
        p.restore()
        self._orbit(p, t, fade)

    def _build(self, p: QPainter, t: float) -> None:
        """Some more of the pictures: a few milliseconds' worth, or all that is wanted by now."""
        density = min(2.0, _density(p))
        if abs(density - self.density) > 0.01:
            self.density = density
            self.pieces = {}
            self.made = 0
            self.work = self._pieces(density)
        needed = sum(1 for at in self.wanted if at <= t + 0.05)
        start = time.perf_counter()
        while self.work is not None and (self.made < needed or time.perf_counter() - start < 0.004):
            try:
                next(self.work)
            except StopIteration:
                self.work = None

    def _pieces(self, density: float):  # noqa: ANN202
        """Makes the pictures a piece at a time, yielding between pieces."""
        box = self.box
        left, top = math.floor(box.left() * density), math.floor(box.top() * density)
        w, h = max(8, round(box.width() * density)), max(8, round(box.height() * density))
        per = self.unit * density
        xs = (left + np.arange(w) + 0.5 - self.origin.x() * density) / per
        ys = (self.origin.y() * density - top - np.arange(h) - 0.5) / per
        mu, distance = yield from _escape(xs[None, :] + 1j * ys[:, None], 160, chunk=16)
        outside = np.isfinite(mu)
        # Faded out away from the set, toward the box's left and bottom (the top and right are the screen's).
        px, py = np.meshgrid(np.arange(w, dtype=np.float32) + left + 0.5, np.arange(h, dtype=np.float32) + top + 0.5)
        cx, cy = (self.origin.x() - 80 * self.u) * density, self.origin.y() * density
        reach = np.hypot((px - cx) / (250 * self.u * density), (py - cy) / (176 * self.u * density))
        vignette = 1 - smooth(0.55, 1.0, reach)
        apart = _apart(mu)
        self.made += 1
        yield

        def placed(value: np.ndarray, make, spare: int = 1) -> tuple[QImage, QRectF]:  # noqa: ANN001
            """A picture of only where value shows (and spare pixels round it), and where it goes, in points."""
            rows, columns = _bounds(value, spare)
            rect = QRectF((left + columns.start) / density, (top + rows.start) / density, (columns.stop - columns.start) / density, (rows.stop - rows.start) / density)
            return make(rows, columns), rect

        tint = rgb("#d8f2ff") * 0.75 + rgb(CHALK) * 0.35
        self.pieces["rings"] = []
        for level in LEVELS:
            near = np.abs(np.nan_to_num(mu, nan=99) - level) < SPACE
            value = np.zeros(mu.shape, dtype=np.float32)
            value[near] = _lines(mu[near], apart[near], 0.0, (level, level), density, SPACE, crowd=0.8) * vignette[near]
            self.pieces["rings"].append(placed(value, lambda rows, columns, value=value: _tinted(value[rows, columns], tint)))
            self.made += 1
            yield
        # The set lit: its edge by the distance estimate, a glow round it, its inside deep navy.
        away = np.where(outside, distance * per, 0)
        inside = (~outside).astype(np.float32)
        rim = np.clip(inside * (1 - blur(inside, 1.1 * density)) * 2.4, 0, 1)
        depth = blur(inside, 9 * density)
        yield
        near = np.where(outside, np.exp(-away / (6 * density)), 0)
        far = np.where(outside, np.exp(-away / (34 * density)), 0)
        light = (rgb("#3f9fff") * (0.42 * near + 0.18 * rim)[..., None] + rgb("#1d5fc0") * (0.6 * far)[..., None]) * vignette[..., None]
        dark = rgb(NIGHT) * (1 - depth)[..., None] + rgb("#0b2547") * depth[..., None]
        shade = inside * 0.9 * vignette
        self.pieces["body"] = placed(np.maximum(light.max(axis=-1), shade), lambda rows, columns: _composite(light[rows, columns], dark[rows, columns], shade[rows, columns]))
        yield
        edge = np.where(outside, 1 / (1 + (away / (0.75 * density)) ** 2), rim) * vignette * 0.85
        self.pieces["core"] = placed(edge, lambda rows, columns: _ready(bloom(edge[rows, columns], "#4fb8ff", ((1.6 * density, 0.8), (5 * density, 0.45)), white=0.35)), round(14 * density))
        self.made += 1
        yield
        # The flowing lines are wanted only where they show.
        shows = (vignette > 0.003) & outside & (mu > LEVELS[0] - SPACE) & (mu < LEVELS[-1] + 3 + SPACE)
        rows, columns = _bounds(shows.astype(np.float32))
        rect = QRectF((left + columns.start) / density, (top + rows.start) / density, (columns.stop - columns.start) / density, (rows.stop - rows.start) / density)
        part = shows[rows, columns]
        mu, apart, vignette = mu[rows, columns][part], apart[rows, columns][part], vignette[rows, columns][part]
        self.pieces["flow"] = []
        for phase in range(PHASES):
            value = np.zeros(part.shape, dtype=np.float32)
            value[part] = _lines(mu, apart, phase / PHASES, (LEVELS[0], LEVELS[-1] + 3), density, SPACE) * vignette
            self.pieces["flow"].append((_tinted(value, tint), rect))
            self.made += 1
            yield

    def _orbit(self, p: QPainter, t: float, fade: float) -> None:
        """The point c and its orbit 0, c, c² + c, … in gold, c resting in a bulb and moving on."""
        a = ease_out(win(t, ORBIT_AT, ORBIT_AT + 0.4)) * fade
        if a <= 0:
            return
        # Rest, move, rest, move, rest: the way is two legs, each about half of it.
        legs = ((ORBIT_AT + 0.6, ORBIT_AT + 1.15), (ORBIT_AT + 1.6, ORBIT_AT + 2.15))
        along = sum(0.5 * ease_in_out(win(t, start, end)) for start, end in legs)
        spot = partial(self.way, along)
        c = complex(spot[-1].x(), spot[-1].y()) if spot else STOPS[0]
        z, points = 0j, [self._at(0j)]
        for _ in range(48):
            z = z * z + c
            if abs(z) > 2.5:
                break
            points.append(self._at(z))
        path = polyline(points)
        u = self.u
        p.setBrush(Qt.NoBrush)
        for w, color, alpha in ((7, GOLD, 0.15), (2.6, GOLD, 0.42), (1.1, PALE_GOLD, 0.75)):
            p.setPen(QPen(col(color, alpha * a), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
        for i, point in enumerate(points[1:7]):
            soft_dot(p, point.x(), point.y(), 7 * u, GOLD, 0.55 * a * (1 - i / 9))
        here = self._at(c)
        soft_dot(p, here.x(), here.y(), 20 * u, GOLD, 0.75 * a)
        soft_dot(p, here.x(), here.y(), 4.2 * u, "#ffffff", a)
        start = self._at(0j)
        soft_dot(p, start.x(), start.y(), 3 * u, INK, 0.8 * a)

    def _at(self, z: complex) -> QPointF:
        return QPointF(self.origin.x() + z.real * self.unit, self.origin.y() - z.imag * self.unit)


def _ready(image: QImage) -> QImage:
    """A picture in the painter's own format, so laying it on each frame converts nothing."""
    return image.convertToFormat(QImage.Format_ARGB32_Premultiplied)


def _axes(p: QPainter, t: float, origin: QPointF, unit: float, u: float, fade: float) -> None:
    """The complex plane's axes drawing out from 0, ticked every half unit, with Re and Im at their ends."""
    a = ease_out(win(t, 0.25, 0.75)) * fade
    if a <= 0:
        return
    grow = ease_out(win(t, 0.25, 0.85))
    left, right, up, down = 2.45 * unit, 1.0 * unit, 1.22 * unit, 1.5 * unit
    p.setPen(QPen(col(CHALK, 0.42 * a), 1 * u))
    p.drawLine(QPointF(origin.x() - left * grow, origin.y()), QPointF(origin.x() + right * grow, origin.y()))
    p.drawLine(QPointF(origin.x(), origin.y() - up * grow), QPointF(origin.x(), origin.y() + down * grow))
    for i in range(-4, 3):
        x = i * unit / 2
        if i and -left * grow < x < right * grow:
            tick = (5 if i % 2 == 0 else 3) * u
            p.drawLine(QPointF(origin.x() + x, origin.y() - tick), QPointF(origin.x() + x, origin.y() + tick))
    for i in (-2, -1, 1, 2):
        y = i * unit / 2
        if -up * grow < -y < down * grow:
            tick = (5 if i % 2 == 0 else 3) * u
            p.drawLine(QPointF(origin.x() - tick, origin.y() - y), QPointF(origin.x() + tick, origin.y() - y))
    label = ease_out(win(t, 0.65, 1.0)) * fade
    if label > 0:
        p.setFont(_font(15 * u))
        p.setPen(col(INK, 0.55 * label))
        p.drawText(QPointF(origin.x() + right - 6 * u, origin.y() + 18 * u), "Re")
        p.drawText(QPointF(origin.x() + 7 * u, origin.y() - up + 14 * u), "Im")
        p.drawText(QPointF(origin.x() - unit * 2 - 7 * u, origin.y() + 19 * u), "−2")


# The Fourier square wave ------------------------------------------------------------------------------


class _Fourier:
    """A square wave summed term by term: circles of radius 4/(πn) for odd n turning n times as fast,
    their tip's height traced out to the right on axes as the wave, the next term's circle growing in
    every so often, the ideal wave dashed under it."""

    TERMS = 8

    def __init__(self, centre: QPointF, amp: float, start: QPointF, length: float, wave: float, u: float) -> None:
        """centre: the first circle's; amp: the wave's height for 1; start: where its axis starts;
        length: how long it is; wave: the wavelength."""
        self.centre, self.amp, self.u = centre, amp, u
        self.x0, self.y0, self.length, self.wave = start.x(), start.y(), length, wave
        self.xs = np.linspace(0, self.length, 170)
        self.font = _font(17 * u)

    def paint(self, p: QPainter, t: float, fade: float) -> None:
        a = ease_out(win(t, 0.3, 0.75)) * fade
        if a <= 0:
            return
        u, amp = self.u, self.amp
        self._axes(p, t, a)
        turn = 2 * math.pi * 0.3 * t + 0.6
        sizes = [ease_out(win(t, 0.55 + 0.26 * k, 0.85 + 0.26 * k)) for k in range(self.TERMS)]
        # The circles, each on the rim of the one before.
        centres = [self.centre]
        for k, size in enumerate(sizes):
            n = 2 * k + 1
            r = 4 / (math.pi * n) * amp * size
            last = centres[-1]
            centres.append(QPointF(last.x() + r * math.cos(n * turn), last.y() - r * math.sin(n * turn)))
        p.setBrush(Qt.NoBrush)
        for k, (size, centre) in enumerate(zip(sizes, centres, strict=False)):
            r = 4 / (math.pi * (2 * k + 1)) * amp * size
            if r < 1.2 * u:
                continue
            p.setPen(QPen(col(CHALK, (0.5 if k == 0 else 0.4) * a), 1 * u))
            p.drawEllipse(centre, r, r)
        arms = polyline(centres)
        for w, color, alpha in ((3.5, CHALK, 0.18), (1.2, INK, 0.85)):
            p.setPen(QPen(col(color, alpha * a), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(arms)
        tip = centres[-1]
        # Across to where the wave starts.
        p.setPen(QPen(col(INK, 0.4 * a), 1 * u, Qt.DashLine))
        p.drawLine(tip, QPointF(self.x0, tip.y()))
        # The wave: the same sum, further back in its turn the further right.
        back = turn - 2 * math.pi * self.xs / self.wave
        weights = np.array([4 / (math.pi * (2 * k + 1)) * sizes[k] for k in range(self.TERMS)])
        ns = np.arange(1, 2 * self.TERMS, 2)[:, None]
        heights = self.y0 - amp * (weights[:, None] * np.sin(ns * back[None, :])).sum(axis=0)
        wave = QPolygonF([QPointF(self.x0 + x, y) for x, y in zip(self.xs, heights, strict=True)])
        p.setPen(QPen(col(CHALK, 0.3 * a), 1 * u, Qt.DashLine))
        p.drawPolyline(self._ideal(turn))
        for w, color, alpha in ((7, GOLD, 0.13), (2.8, GOLD, 0.5), (1.15, PALE_GOLD, 0.95)):
            p.setPen(QPen(col(color, alpha * a), w * u, Qt.SolidLine, Qt.RoundCap, Qt.BevelJoin))
            p.drawPolyline(wave)
        soft_dot(p, tip.x(), tip.y(), 16 * u, GOLD, 0.75 * a)
        soft_dot(p, tip.x(), tip.y(), 3.4 * u, "#ffffff", a)
        soft_dot(p, self.x0, tip.y(), 9 * u, GOLD, 0.6 * a)
        # How many terms so far.
        count = sum(1 for size in sizes if size > 0.5)
        if count:
            p.setFont(self.font)
            p.setPen(col(INK, 0.6 * a))
            p.drawText(QPointF(self.centre.x() - 34 * u, self.y0 + amp * 1.55 + 8 * u), f"{_it('n')} ≤ {2 * count - 1}")

    def _ideal(self, turn: float) -> QPolygonF:
        """The square wave the sum is making, corner to corner: 1 where the turn's sine is positive."""
        lam, amp = self.wave, self.amp
        # It flips where turn − 2πx/λ is a whole number of half turns.
        first = math.floor(turn / math.pi)
        flips = [(turn - k * math.pi) * lam / (2 * math.pi) for k in range(first, first - 2 * math.ceil(self.length / lam) - 2, -1)]
        flips = [x for x in flips if 0 < x < self.length]
        level = 1 if math.sin(turn) >= 0 else -1
        corners = [QPointF(self.x0, self.y0 - amp * level)]
        for x in flips:
            corners.append(QPointF(self.x0 + x, self.y0 - amp * level))
            level = -level
            corners.append(QPointF(self.x0 + x, self.y0 - amp * level))
        corners.append(QPointF(self.x0 + self.length, self.y0 - amp * level))
        return QPolygonF(corners)

    def _axes(self, p: QPainter, t: float, a: float) -> None:
        u, amp = self.u, self.amp
        grow = ease_out(win(t, 0.3, 0.85))
        end = self.x0 + (self.length + 14 * u) * grow
        p.setPen(QPen(col(CHALK, 0.42 * a), 1 * u))
        p.drawLine(QPointF(self.x0 - 6 * u, self.y0), QPointF(end, self.y0))
        p.drawLine(QPointF(self.x0, self.y0 - amp * 1.4 * grow), QPointF(self.x0, self.y0 + amp * 1.4 * grow))
        for sign in (-1, 1):
            p.drawLine(QPointF(self.x0 - 4 * u, self.y0 - sign * amp), QPointF(self.x0 + 4 * u, self.y0 - sign * amp))
        for i in range(1, 9):
            x = self.x0 + i * self.wave / 4
            if x < end - 8 * u:
                tick = (4 if i % 2 == 0 else 2.5) * u
                p.drawLine(QPointF(x, self.y0 - tick), QPointF(x, self.y0 + tick))
        p.setBrush(col(CHALK, 0.5 * a))
        p.setPen(Qt.NoPen)
        arrow = QPainterPath(QPointF(end, self.y0))
        arrow.lineTo(end - 7 * u, self.y0 - 3.2 * u)
        arrow.lineTo(end - 7 * u, self.y0 + 3.2 * u)
        arrow.closeSubpath()
        p.drawPath(arrow)
        p.setFont(self.font)
        p.setPen(col(INK, 0.5 * a))
        p.drawText(QPointF(self.x0 - 18 * u, self.y0 - amp + 6 * u), "1")
        p.drawText(QPointF(end + 4 * u, self.y0 + 6 * u), _it("x"))


# The Koch snowflake -----------------------------------------------------------------------------------


class _Koch:
    """A Koch snowflake about centre, its points radius from it: a triangle drawing itself, then each
    side growing a bump on its middle third, a level at a time, turning slowly."""

    # Three levels: a fourth's sides would be a pixel or two long.
    DEPTH = 3

    def __init__(self, centre: QPointF, radius: float) -> None:
        self.centre, self.radius = centre, radius
        corners = [(math.cos(-math.pi / 2 + i * 2 * math.pi / 3), math.sin(-math.pi / 2 + i * 2 * math.pi / 3)) for i in range(3)]
        self.levels = [np.array(corners)]
        for _ in range(self.DEPTH):
            self.levels.append(_koch_step(self.levels[-1], 1.0))

    def paint(self, p: QPainter, t: float, u: float, fade: float) -> None:
        draw = ease_in_out(win(t, 0.8, 1.3))
        if draw <= 0 or fade <= 0:
            return
        reached = clamp((t - 1.3) / 0.45, 0, self.DEPTH)
        level = int(reached)
        points = self.levels[level]
        if level < self.DEPTH:
            points = _koch_step(points, ease_in_out(reached - level))
        turn = math.radians(5 * t)
        cos, sin = math.cos(turn), math.sin(turn)
        r, cx, cy = self.radius, self.centre.x(), self.centre.y()
        shape = [QPointF(cx + r * (x * cos - y * sin), cy + r * (x * sin + y * cos)) for x, y in points]
        shape.append(shape[0])
        if draw < 1:
            shape = partial(shape, draw)
        path = polyline(shape)
        if draw >= 1:
            path.closeSubpath()
            p.setPen(Qt.NoPen)
            fill = QRadialGradient(self.centre, r)
            fill.setColorAt(0, col(CHALK, 0.14 * fade))
            fill.setColorAt(1, col(CHALK, 0.03 * fade))
            p.setBrush(fill)
            p.drawPath(path)
        p.setBrush(Qt.NoBrush)
        for w, color, alpha in ((5, CHALK, 0.14), (2.2, CHALK, 0.4), (1.0, INK, 0.9)):
            p.setPen(QPen(col(color, alpha * fade), w * u, Qt.SolidLine, Qt.RoundCap, Qt.BevelJoin))
            p.drawPath(path)


def _koch_step(points: np.ndarray, grow: float) -> np.ndarray:
    """A closed polyline's next Koch level: each side's middle third raised outward into a bump,
    grow of its full height."""
    a, b = points, np.roll(points, -1, axis=0)
    d = b - a
    first, second = a + d / 3, a + 2 * d / 3
    # Outward of a side going clockwise on the screen (y down) is to its left.
    normal = np.stack([d[:, 1], -d[:, 0]], axis=1)
    apex = (a + b) / 2 + normal * (math.sqrt(3) / 6) * grow
    return np.stack([a, first, apex, second], axis=1).reshape(-1, 2)


# The equations -------------------------------------------------------------------------------------


def _it(text: str) -> str:
    """Letters as Cambria Math sets variables: in math italic, from Unicode's own alphabet."""
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append("ℎ" if ch == "h" else chr(0x1D44E + ord(ch) - ord("a")))
        elif "A" <= ch <= "Z":
            out.append(chr(0x1D434 + ord(ch) - ord("A")))
        elif ch == "π":
            out.append("\U0001d70b")
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
    centered beneath the one before, sup and sub, frac a fraction (kind, top, bottom), han Chinese in
    a brush hand."""
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
            # A sup straight after a sub sits over it, as zₙ² does.
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
    lit = glow(halo[..., None] * rgb(tint))
    # The chalk dust it crumbles into: specks from its own letters.
    ys, xs = np.nonzero(shape > 0.5)
    motes = []
    for i in rnd.sample(range(len(xs)), min(len(xs), 34)):
        x0 = glow_box.left() + (xs[i] + 0.5) / SOFT
        y0 = glow_box.top() + (ys[i] + 0.5) / SOFT
        motes.append((x0, y0, rnd.uniform(18, 46) * px / 26, rnd.uniform(-12, 12) * px / 26, rnd.uniform(0.7, 1.9) * px / 26, rnd.uniform(0, 0.45)))
    return _Formula(ink, accent, box, lit, glow_box, motes, start, end, tint)


def _density(p: QPainter) -> float:
    """Pixels per point where p draws: the screen's ratio and any scaling (the small preview)."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    m = p.worldTransform()
    return max(0.3, ratio * math.hypot(m.m11(), m.m12()))


# The marks ---------------------------------------------------------------------------------------------

# Each mark's pictures, worked out once for each size and sharpness it is drawn at.
_MADE: dict[tuple, object] = {}


def _keep(made: tuple) -> tuple:
    """What a mark made, to be kept: the oldest go once there are many (a card for every set of names)."""
    if len(_MADE) >= 24:
        _MADE.pop(next(iter(_MADE)))
    return made


def _sharp(p: QPainter) -> float:
    """How many pixels to a point a mark's pictures are made at: two at least, so they stay crisp."""
    return max(2.0, _density(p))


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A ruler of coordinate ticks round the button, longer every fifth, crosshairs off its corners,
    and two gold readings running round it, brightening the ticks they pass."""
    ratio = _sharp(p)
    window = cover.adjusted(-ROOM, -ROOM, ROOM, ROOM)
    key = ("ring", round(cover.width(), 1), round(cover.height(), 1), ratio)
    if key not in _MADE:
        _MADE[key] = _keep(_ruler(window, cover, ratio))
    image, ticks, path = _MADE[key]
    p.drawImage(window, image)
    count = len(ticks)
    for k in range(2):
        at = (t / 4.2 + k / 2) % 1
        point = path.pointAtPercent(path.percentAtLength(path.length() * at))
        here = at * count
        for offset in range(-4, 5):
            i = (int(here) + offset) % count
            near = 1 - min(abs(i - here), count - abs(i - here)) / 4.5
            if near <= 0:
                continue
            base, tip = ticks[i]
            p.setPen(QPen(col(PALE_GOLD, 0.95 * near), 1.4, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(base, tip)
        soft_dot(p, point.x(), point.y(), 13, GOLD, 0.85)
        soft_dot(p, point.x(), point.y(), 2.4, "#ffffff", 1.0)


def _ruler(window: QRectF, cover: QRectF, ratio: float) -> tuple[QImage, list, QPainterPath]:
    """The ring's still part lit once: the ruler line just outside the cover, its ticks and the
    corner crosshairs in chalk, bloomed; with the ticks (base, tip) and the line, for the readings."""
    line = cover.adjusted(-2, -2, 2, 2)
    radius = max(4.0, cover.height() * 0.14) + 2
    path = QPainterPath()
    path.addRoundedRect(line, radius, radius)
    length = path.length()
    count = max(20, round(length / 7.5 / 5) * 5)
    ticks = []
    for i in range(count):
        percent = path.percentAtLength(length * i / count)
        point = path.pointAtPercent(percent)
        angle = math.radians(path.angleAtPercent(percent))
        normal = QPointF(math.sin(angle), math.cos(angle))
        # Outward, away from the cover.
        if line.contains(point + normal):
            normal = -normal
        reach = 6.0 if i % 5 == 0 else 3.2
        ticks.append((point, point + normal * reach))
    w, h = round(window.width() * ratio), round(window.height() * ratio)

    def draw(q: QPainter) -> None:
        q.scale(ratio, ratio)
        q.translate(-window.left(), -window.top())
        q.setBrush(Qt.NoBrush)
        q.setPen(QPen(Qt.white, 1.1))
        q.drawPath(path)
        for i, (base, tip) in enumerate(ticks):
            q.setPen(QPen(Qt.white, 1.0 if i % 5 == 0 else 0.75, Qt.SolidLine, Qt.FlatCap))
            q.drawLine(base, tip)
        q.setPen(QPen(Qt.white, 0.9))
        for x, y, sx, sy in ((line.left(), line.top(), -1, -1), (line.right(), line.top(), 1, -1), (line.left(), line.bottom(), -1, 1), (line.right(), line.bottom(), 1, 1)):
            mx, my = x + sx * 4.5, y + sy * 4.5
            q.drawLine(QPointF(mx - 2.6, my), QPointF(mx + 2.6, my))
            q.drawLine(QPointF(mx, my - 2.6), QPointF(mx, my + 2.6))

    core = mask(w, h, draw)
    lit = np.clip(core, 0, 1) * 0.9
    image = bloom(lit, CHALK, ((1.0 * ratio, 0.8), (3.5 * ratio, 0.45)), white=0.45)
    return _ready(image), ticks, path


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A glass disc with the Mandelbrot set lit in it, a dial of ticks on its rim and escape lines
    flowing into the set, a glint going round the rim."""
    ratio = _sharp(p)
    window = box.adjusted(-ROOM, -ROOM, ROOM, ROOM)
    key = ("badge", round(box.width(), 1), ratio)
    if key not in _MADE:
        _MADE[key] = _keep(_seal(window, box, ratio))
    base, flows = _MADE[key]
    p.drawImage(window, base)
    steps = t * 0.5 % 1 * PHASES
    i, f = int(steps), steps - int(steps)
    p.save()
    p.setOpacity(0.55 * (1 - f))
    p.drawImage(window, flows[i % PHASES])
    p.setOpacity(0.55 * f)
    p.drawImage(window, flows[(i + 1) % PHASES])
    p.restore()
    r = box.width() / 2 - 1.5
    angle = -t * 1.3
    c = box.center()
    soft_dot(p, c.x() + r * math.cos(angle), c.y() + r * math.sin(angle), 6, CHALK, 0.6)
    soft_dot(p, c.x() + r * math.cos(angle), c.y() + r * math.sin(angle), 1.6, "#ffffff", 0.8)


def _seal(window: QRectF, box: QRectF, ratio: float) -> tuple[QImage, list[QImage]]:
    """The badge's pictures: the disc with its set, rim and glow; and each step of its flowing lines."""
    w, h = round(window.width() * ratio), round(window.height() * ratio)
    side = box.width()
    centre = box.center()
    radius = side / 2 - 1
    px, py = np.meshgrid((np.arange(w) + 0.5) / ratio + window.left(), (np.arange(h) + 0.5) / ratio + window.top())
    off = np.hypot(px - centre.x(), py - centre.y())
    disc = np.clip(radius - off + 0.5, 0, 1).astype(np.float32)
    # The set across most of the disc, its middle at −0.72 so it sits centred.
    unit = side * 0.78 / 2.6
    c = (px - centre.x()) / unit - 0.72 + 1j * (centre.y() - py) / unit
    mu, distance = _run(_escape(c, 90))
    outside = np.isfinite(mu)
    per = unit * ratio
    away = np.where(outside, distance * per, 0.0)
    inside = (~outside).astype(np.float32) * disc
    rim_in = np.clip(inside * (1 - blur(inside, 0.9 * ratio)) * 2.2, 0, 1)
    edge = np.where(outside, 1 / (1 + (away / (0.7 * ratio)) ** 2), rim_in) * disc
    # Glass: lit from the upper left, darker to its rim.
    shade = np.clip(1 - off / radius, 0, 1)
    sheen = np.exp(-(((px - centre.x() + radius * 0.35) ** 2 + (py - centre.y() + radius * 0.45) ** 2) / (radius * 0.55) ** 2))
    glass = rgb("#0a1f3c")[None, None] * (0.6 + 0.4 * shade)[..., None] + rgb("#3d7fc0")[None, None] * (0.22 * sheen)[..., None]
    deep = rgb(NIGHT)[None, None] * np.ones_like(shade)[..., None]
    fill = np.where(inside[..., None] > 0.5, deep, glass)
    # The rim: a fine chalk circle, a dial of ticks just inside it, and a glow outside.

    def dial(q: QPainter) -> None:
        q.scale(ratio, ratio)
        q.translate(-window.left(), -window.top())
        q.setBrush(Qt.NoBrush)
        q.setPen(QPen(Qt.white, 1.2))
        q.drawEllipse(centre, radius - 0.5, radius - 0.5)
        for i in range(36):
            a = i * math.pi / 18
            reach = 4.0 if i % 9 == 0 else 2.2
            q.setPen(QPen(Qt.white, 0.9 if i % 9 == 0 else 0.6))
            q.drawLine(QPointF(centre.x() + (radius - 1.5) * math.cos(a), centre.y() + (radius - 1.5) * math.sin(a)),
                       QPointF(centre.x() + (radius - 1.5 - reach) * math.cos(a), centre.y() + (radius - 1.5 - reach) * math.sin(a)))

    rim = mask(w, h, dial)
    near = np.where(outside, np.exp(-away / (4 * ratio)), 0.0) * disc
    halo = blur(disc, 3.2 * ratio) * (1 - disc)
    light = (
        rgb(CHALK) * (0.45 * near + 0.5 * halo + 0.55 * rim)[..., None]
        + rgb("#cfeeff") * (0.75 * edge + 0.4 * rim)[..., None]
        + rgb("#4fb8ff") * blur(edge, 1.4 * ratio)[..., None] * 0.55
    )
    base = _composite(light.astype(np.float32), fill, disc * 0.94)
    spacing = _apart(mu)
    flows = []
    for phase in range(PHASES):
        line = _lines(mu, spacing, phase / PHASES, (1, 9), ratio * 0.6) * disc
        flows.append(_tinted(line, rgb(CHALK)))
    return base, flows


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """A dark blueprint plate: a fine grid, a Julia set's filigree faint at its edges, a chalk edge
    with corner ticks, a title tab on top and a light running round its edge."""
    ratio = _sharp(p)
    key = ("card", round(rect.width(), 1), round(rect.height(), 1), ratio)
    if key not in _MADE:
        _MADE[key] = _keep(_plate(rect, ratio))
    image, path = _MADE[key]
    p.drawImage(rect, image)
    at = t / 5.0 % 1
    point = path.pointAtPercent(path.percentAtLength(path.length() * at))
    soft_dot(p, point.x(), point.y(), 10, CHALK, 0.55)
    soft_dot(p, point.x(), point.y(), 1.8, "#ffffff", 0.85)


def _plate(rect: QRectF, ratio: float) -> tuple[QImage, QPainterPath]:
    """The card's picture, made once for its size: the plate, its texture, edge and tab; with its
    edge as a path, for the light running round it."""
    w, h = max(1, round(rect.width() * ratio)), max(1, round(rect.height() * ratio))
    body = rect.adjusted(0.5, CARD_TOP + 0.5, -0.5, -0.5)
    px, py = np.meshgrid((np.arange(w) + 0.5) / ratio + rect.left(), (np.arange(h) + 0.5) / ratio + rect.top())
    # How far in from the body's edge, in points.
    inward = np.minimum(np.minimum(px - body.left(), body.right() - px), np.minimum(py - body.top(), body.bottom() - py))
    within = np.clip(inward + 0.5, 0, 1).astype(np.float32)
    down = np.clip((py - body.top()) / max(1.0, body.height()), 0, 1)
    plate = rgb(LOOK["card"][0])[None, None] * (1 - down)[..., None] + rgb(LOOK["card"][1])[None, None] * down[..., None]
    # The filigree: a Julia set's escape lines, faint, there only near the edges.
    scale = 2.9 / max(1.0, body.width())
    c = (px - body.center().x()) * scale + 1j * (body.center().y() - py) * scale
    mu, distance = _julia(c, complex(-0.7269, 0.1889), 70)
    outside = np.isfinite(mu)
    lines = _lines(mu, _apart(mu), 0.0, (2, 14), ratio * 0.55)
    set_edge = np.where(outside, 1 / (1 + (distance / scale / 0.8) ** 2), 0.4)
    border = np.exp(-np.clip(inward, 0, None) / 9.0)
    texture = (lines * 0.5 + set_edge * 0.35) * border * within
    # Graph paper: a fine grid, every fourth line stronger.
    step = 6.0
    gxl = np.abs(((px - body.left()) / step + 0.5) % 1 - 0.5) * step
    gyl = np.abs(((py - body.top()) / step + 0.5) % 1 - 0.5) * step
    major = (np.abs(((px - body.left()) / (step * 4) + 0.5) % 1 - 0.5) * step * 4 < 0.6) | (np.abs(((py - body.top()) / (step * 4) + 0.5) % 1 - 0.5) * step * 4 < 0.6)
    grid = np.maximum(np.exp(-((gxl * ratio / 0.7) ** 2)), np.exp(-((gyl * ratio / 0.7) ** 2))) * np.where(major, 0.13, 0.06) * within
    path = QPainterPath()
    path.addRoundedRect(body, 3, 3)
    tab = QRectF(body.left() + 7, rect.top() + 1, min(70.0, body.width() * 0.6), CARD_TOP + 2)

    def lines_drawn(q: QPainter) -> None:
        q.scale(ratio, ratio)
        q.translate(-rect.left(), -rect.top())
        q.setBrush(Qt.NoBrush)
        q.setPen(QPen(Qt.white, 1.0))
        q.drawPath(path)
        tab_path = QPainterPath(QPointF(tab.left(), body.top()))
        tab_path.lineTo(tab.left() + 3, tab.top())
        tab_path.lineTo(tab.right() - 3, tab.top())
        tab_path.lineTo(tab.right(), body.top())
        q.drawPath(tab_path)
        # Corner ticks, as a drawing's sheet has.
        q.setPen(QPen(Qt.white, 1.4))
        for x, y, sx, sy in ((body.left(), body.top(), 1, 1), (body.right(), body.top(), -1, 1), (body.left(), body.bottom(), 1, -1), (body.right(), body.bottom(), -1, -1)):
            q.drawLine(QPointF(x + sx * 2, y + sy * 2), QPointF(x + sx * 8, y + sy * 2))
            q.drawLine(QPointF(x + sx * 2, y + sy * 2), QPointF(x + sx * 2, y + sy * 8))

    edge = mask(w, h, lines_drawn)

    def tab_fill(q: QPainter) -> None:
        q.scale(ratio, ratio)
        q.translate(-rect.left(), -rect.top())
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        shape = QPainterPath(QPointF(tab.left(), body.top() + 1))
        shape.lineTo(tab.left() + 3, tab.top())
        shape.lineTo(tab.right() - 3, tab.top())
        shape.lineTo(tab.right(), body.top() + 1)
        shape.closeSubpath()
        q.drawPath(shape)

    tabbed = mask(w, h, tab_fill)
    fill_alpha = np.clip(within * 0.94 + tabbed * 0.94, 0, 0.94)
    light = rgb(CHALK) * (texture * 0.8 + grid)[..., None] + rgb("#cfefff") * (edge * 0.85)[..., None] + rgb(CHALK) * blur(edge, 1.5 * ratio)[..., None] * 0.6
    image = _composite(light.astype(np.float32), plate, fill_alpha)
    # The tab's title: the liked ones are in the set.
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.setRenderHint(QPainter.TextAntialiasing)
    q.scale(ratio, ratio)
    q.translate(-rect.left(), -rect.top())
    label = QFont()
    label.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei"])
    label.setPixelSize(11)
    label.setWeight(QFont.DemiBold)
    q.setFont(label)
    q.setPen(col(INK, 0.95))
    words = QFontMetricsF(label).horizontalAdvance("心动")
    q.drawText(QPointF(tab.left() + 7, tab.bottom() - 5), "心动")
    q.setFont(_font(13))
    q.setPen(col(CHALK, 0.95))
    q.drawText(QPointF(tab.left() + 10 + words, tab.bottom() - 5), "∈ ℳ")
    q.end()
    return image, path


def _julia(z: np.ndarray, c: complex, iterations: int) -> tuple[np.ndarray, np.ndarray]:
    """The Julia set of z → z² + c: each point's smooth escape count (nan inside) and its distance
    estimate to the set."""
    shape = z.shape
    z = z.ravel().astype(np.complex128)
    mu = np.full(z.shape, np.nan)
    distance = np.zeros(z.shape)
    index = np.arange(z.size)
    dz = np.ones(z.shape, dtype=np.complex128)
    for n in range(iterations):
        dz = 2 * z * dz
        z = z * z + c
        size = z.real * z.real + z.imag * z.imag
        out = size > 65536.0
        if out.any():
            r = np.sqrt(size[out])
            mu[index[out]] = n + 2 - np.log2(np.log(r))
            distance[index[out]] = r * np.log(r) / np.abs(dz[out])
            keep = ~out
            z, dz, index = z[keep], dz[keep], index[keep]
    return mu.reshape(shape), distance.reshape(shape)


def lead(size: float, index: int) -> QPixmap:
    """A plotted point: a lit dot, a fine ring round it and four ticks, as on a graph."""
    ratio = 3.0
    image = QPixmap(round(size * ratio), round(size * ratio))
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.transparent)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    c = size / 2
    tint = GOLD if index % 2 else CHALK
    soft_dot(q, c, c, size * 0.42, tint, 0.55)
    q.setBrush(Qt.NoBrush)
    q.setPen(QPen(col(tint, 0.9), max(0.8, size * 0.055)))
    q.drawEllipse(QPointF(c, c), size * 0.24, size * 0.24)
    for k in range(4):
        a = k * math.pi / 2
        q.drawLine(QPointF(c + math.cos(a) * size * 0.33, c + math.sin(a) * size * 0.33), QPointF(c + math.cos(a) * size * 0.46, c + math.sin(a) * size * 0.46))
    q.setPen(Qt.NoPen)
    q.setBrush(col("#ffffff"))
    q.drawEllipse(QPointF(c, c), size * 0.1, size * 0.1)
    q.end()
    return image
