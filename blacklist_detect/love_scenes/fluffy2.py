"""紫白庆典 Lavender Celebration (fluffy2): a party in lavender and white, drawn as a sketchbook draws it.

The top of the screen lifts into a lavender and white haze with soft bokeh in it. In the top right a
little crown of lavender silver drops in and settles, tilted, worked out per pixel: a bevelled
silver body with a lavender enamel band, a violet stone between a pink and a blue one, pearls on its
points; light sweeps across it and sparkles fly off it as it lands. Hand-drawn line fireworks rise on
wobbly trails and burst round the edges in pink, blue and purple strokes that fly out, thin and
droop, with dots at their tips and a soft bloom under them. Curling ribbon streamers unroll from the
top edge and sway, catching the light as they turn; confetti flutters down the sides and the top,
turning over as it falls; outlined stars pop in and twinkle. At the end it all fades.

Its marks wear the party too: a lavender satin ribbon wrapped round 准备案件还原, tied in a bow on
top, a shine running round it; the badge a little crown that bobs and glints; the card white paper
with a scalloped lace hem and a stitched lavender line, a satin bow on top and sparkles on it; a
small puffy star before each name, lavender, pink and blue in turn.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient

from blacklist_detect.love_scenes.draw import (
    Wash,
    clamp,
    col,
    ease_back,
    ease_in,
    ease_in_out,
    ease_out,
    mix,
    soft_dot,
    spring,
    star,
    win,
)
from blacklist_detect.love_scenes.light import blur, glow, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
LAVENDER = "#b9a3e8"
LILAC = "#ddd0fa"
VIOLET = "#7a5fd0"
PLUM = "#4b3489"
PINK = "#ff8cc8"
BLUE = "#7cc8ff"
PURPLE = "#ab8cff"
LOOK = {
    "glow": (190, 168, 238),
    "rim": LAVENDER,
    "band": (LAVENDER, "#f5f0ff"),
    "card": ("#ffffff", "#f3eefd"),
    "edge": LAVENDER,
    "ink": "#523a92",
    "flowers": (("#ffffff", "#e6dcfb", LAVENDER), ("#fbf8ff", "#d9cdf6", "#8f74d8")),
    "disc": ("#fbf8ff", "#e2d6fa"),
    "heart": ("#c9b5f2", VIOLET),
    "deep": VIOLET,
    "deep_glow": (170, 140, 240),
}
MARKS_ANIMATED = True
# Room above the card for its bow; the names sit a little lower under it.
CARD_TOP = 19
CARD_PAD = (12, 10, 14, 11)
# Light comes from the upper left, toward the viewer.
_LIGHT = np.array([-0.45, -0.72, 0.53], dtype=np.float32) / np.float32(math.hypot(0.45, 0.72, 0.53))
_HALF = (_LIGHT + np.array([0, 0, 1], dtype=np.float32)) / np.float32(np.linalg.norm(_LIGHT + np.array([0, 0, 1])))
# Lavender silver, from its shade to where it catches the light.
SILVER = ((0.0, "#5a45a0"), (0.3, "#a593e2"), (0.5, "#e6defd"), (0.6, "#ffffff"), (0.72, "#cbbdf4"), (1.0, "#f8f5ff"))
ENAMEL = ((0.0, "#4f3699"), (0.35, "#8a6ed8"), (0.6, "#b49ff0"), (0.82, "#e0d6ff"), (1.0, "#ffffff"))
SATIN = ((0.0, "#5e45ad"), (0.3, "#9178dc"), (0.6, "#bfaaf1"), (0.85, "#e6dcff"), (1.0, "#ffffff"))
PEARL = ((0.0, "#9a86d4"), (0.5, "#e5ddf9"), (1.0, "#ffffff"))
CONFETTI = ("#c9b6ff", "#ffb2da", "#a8dcff", "#ffffff", "#ffe59a", "#b9f0d9", "#c9b6ff", "#ffffff", "#ffb2da", "#a8dcff")
# (when it goes up, where it bursts as shares of the stage, radius, its two colors, how many strokes)
BURSTS = (
    (0.12, 0.165, 0.15, 122, PINK, PURPLE, 26),
    (0.55, 0.292, 0.07, 82, BLUE, PINK, 20),
    (0.95, 0.052, 0.43, 80, PURPLE, BLUE, 20),
    (1.4, 0.76, 0.085, 94, PINK, BLUE, 22),
    (1.9, 0.975, 0.52, 68, BLUE, PURPLE, 18),
    (2.25, 0.07, 0.96, 96, BLUE, PINK, 22),
    (2.6, 0.94, 0.97, 92, PURPLE, PINK, 22),
    (2.95, 0.2, 0.1, 106, PURPLE, BLUE, 24),
    (3.3, 0.752, 0.2, 68, PINK, PURPLE, 18),
)
# A rocket climbs this long before it bursts; a burst lasts this long.
RISE = 0.42
BURST = 1.6
# (where it hangs as a share of the width, how long as a share of the height, front and back, when it unrolls)
STREAMERS = (
    (0.03, 0.5, ("#ddd0ff", "#7e64c8"), 0.15),
    (0.088, 0.27, ("#ffffff", "#a996df"), 0.32),
    (0.258, 0.2, ("#ffc6e4", "#c27aad"), 0.5),
    (0.712, 0.18, ("#ddd0ff", "#7e64c8"), 0.42),
    (0.982, 0.52, ("#ffffff", "#a996df"), 0.25),
)
# Pictures made once for each size, the marks' and the crown's; the oldest go when there are many.
_PICTURES: dict[tuple, QImage] = {}


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(62)
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    title = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.18)
    keep = gap.adjusted(-24 * u, -24 * u, 24 * u, 24 * u)
    haze = Wash(lambda q, w, h: _haze(q, w, h, u, title, names))
    crown_w = 190 * u
    crown_at = QPointF(width - 196 * u, 112 * u)
    crown = _crown_picture(max(8, round(crown_w * 2)))
    crown_halo = _halo(crown, 0.25, 9.0, "#cdb8ff", 1.5)
    bursts = [_burst(i, when, QPointF(width * x, height * y), r * u, a, b, n, u) for i, (when, x, y, r, a, b, n) in enumerate(BURSTS)]
    streamers = [
        (width * x, height * length, _ribbon_shades(*colors), when, rnd.uniform(0, 6.28), rnd.uniform(0.8, 1.2)) for x, length, colors, when in STREAMERS
    ]
    confetti = _confetti(rnd, width, height, u, title)
    stars = _stars(rnd, width, height, u, names, title, keep)
    glints = []
    while len(glints) < 28:
        x, y = rnd.uniform(0, width), rnd.uniform(0, height)
        point = QPointF(x, y)
        if names.contains(point) or title.contains(point) or keep.contains(point):
            continue
        glints.append((x, y, rnd.uniform(2.5, 6.0) * u, rnd.uniform(0.3, 3.6), rnd.uniform(2.0, 4.5), rnd.choice(("#ffffff", LILAC, "#ffe3f3"))))

    def paint(p: QPainter, t: float) -> None:
        life = ease_out(win(t, 0.0, 0.3))
        leave = ease_in(win(t, DURATION - 0.75, DURATION))
        if life * (1 - leave) <= 0:
            return
        p.save()
        p.setOpacity(life * (1 - leave))
        haze.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.8)))
        for at in streamers:
            _streamer(p, t, at, u)
        for burst in bursts:
            _firework(p, t, burst, u)
        _crown(p, t, crown, crown_halo, crown_at, crown_w, u)
        _twinkles(p, t, glints)
        _outlined_stars(p, t, stars, u)
        _flutter(p, t, confetti, u, names, title, keep, height)
        p.restore()

    return paint


# The haze, drawn once.


def _haze(p: QPainter, width: float, height: float, u: float, title: QRectF, names: QRectF) -> None:
    """Lavender and white light pooled in the top corners and along the top, softer down the sides
    and in the bottom corners, with bokeh in it: the title and the names stay clear."""
    p.setPen(Qt.NoPen)
    for x, y, r, color, alpha in (
        (0.0, 0.0, 600, "#efe8ff", 0.62),
        (1.0, 0.0, 560, "#efe8ff", 0.58),
        (0.25, -0.05, 440, "#d9c9ff", 0.3),
        (0.8, -0.05, 400, "#d9c9ff", 0.28),
        (0.0, 0.6, 340, "#c4b0f0", 0.26),
        (1.0, 0.6, 340, "#c4b0f0", 0.26),
        (0.0, 1.0, 380, "#d6c6ff", 0.38),
        (1.0, 1.0, 380, "#d6c6ff", 0.38),
    ):
        pool = QRadialGradient(QPointF(width * x, height * y), r * u)
        pool.setColorAt(0, col(color, alpha))
        pool.setColorAt(0.45, col(color, alpha * 0.4))
        pool.setColorAt(1, col(color, 0))
        p.setBrush(pool)
        p.drawEllipse(pool.center(), r * u, r * u)
    rnd = random.Random(9)
    placed = 0
    while placed < 34:
        x, y = rnd.uniform(0, width), rnd.uniform(0, height)
        point = QPointF(x, y)
        if names.adjusted(-20 * u, -20 * u, 20 * u, 0).contains(point) or title.contains(point):
            continue
        if height * 0.28 < y < height * 0.86 and width * 0.08 < x < width * 0.92:
            continue
        placed += 1
        r = rnd.uniform(7, 30) * u
        a = rnd.uniform(0.06, 0.13)
        # A bokeh disc: even inside, a little brighter at its rim.
        disc = QRadialGradient(QPointF(x, y), r)
        tint = rnd.choice(("#f3eeff", "#d9c9ff", "#ffd2ec", "#cfe6ff"))
        disc.setColorAt(0, col(tint, a * 0.6))
        disc.setColorAt(0.8, col(tint, a))
        disc.setColorAt(0.93, col(tint, a * 1.3))
        disc.setColorAt(1, col(tint, 0))
        p.setBrush(disc)
        p.drawEllipse(QPointF(x, y), r, r)


# Pictures worked out per pixel.


def _kept(key: tuple, image: QImage) -> QImage:
    if len(_PICTURES) >= 48:
        del _PICTURES[next(iter(_PICTURES))]
    _PICTURES[key] = image
    return image


def _ramp(k: np.ndarray, stops: tuple) -> np.ndarray:
    """Colors (h, w, 3) along a list of (at, color) for k in 0..1."""
    at = [a for a, _c in stops]
    shades = np.array([rgb(c) for _a, c in stops])
    return np.stack([np.interp(k, at, shades[:, i]) for i in range(3)], axis=-1).astype(np.float32)


def _relief(height: np.ndarray, strength: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Unit normals of a height field, steeper with strength."""
    gy, gx = np.gradient(height)
    nx, ny = -gx * strength, -gy * strength
    inv = 1 / np.sqrt(nx * nx + ny * ny + 1)
    return nx * inv, ny * inv, inv


def _lit(nx: np.ndarray, ny: np.ndarray, nz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """How much light falls on each pixel, and how squarely it reflects to the eye (for highlights)."""
    diffuse = np.clip(nx * _LIGHT[0] + ny * _LIGHT[1] + nz * _LIGHT[2], 0, 1)
    facing = np.clip(nx * _HALF[0] + ny * _HALF[1] + nz * _HALF[2], 0, 1)
    return diffuse, facing


def _rim(body: np.ndarray, px: float) -> np.ndarray:
    """The inside edge of a shape, about 2 px pixels wide: where an ink line goes."""
    return np.clip(body - smooth(0.62, 0.97, blur(body, px)), 0, 1)


def _over(color: np.ndarray, alpha: np.ndarray, top: np.ndarray, top_alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """One straight-color layer over another."""
    out = top_alpha + alpha * (1 - top_alpha)
    mixed = (top * top_alpha[..., None] + color * (alpha * (1 - top_alpha))[..., None]) / np.maximum(out, 1e-4)[..., None]
    return mixed, out


def _grid(width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
    return np.mgrid[0:height, 0:width].astype(np.float32)[::-1] + 0.5


def _disc(xs: np.ndarray, ys: np.ndarray, x: float, y: float, r: float) -> np.ndarray:
    return np.clip(r - np.hypot(xs - x, ys - y) + 0.5, 0, 1)


def _filled(*paths: QPainterPath):  # noqa: ANN202
    def draw(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#ffffff"))
        for path in paths:
            q.drawPath(path)

    return draw


def _ball(xs: np.ndarray, ys: np.ndarray, x: float, y: float, r: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """A sphere of radius r at (x, y): its coverage, and its normals."""
    dx, dy = (xs - x) / r, (ys - y) / r
    d2 = dx * dx + dy * dy
    nz = np.sqrt(np.clip(1 - d2, 0, 1))
    return _disc(xs, ys, x, y, r), dx, dy, nz


def _gem(xs: np.ndarray, ys: np.ndarray, x: float, y: float, r: float, color: str) -> tuple[np.ndarray, np.ndarray]:
    """A cabochon stone: deep at its rim, glowing inside opposite the light, a sharp highlight."""
    inside, dx, dy, nz = _ball(xs, ys, x, y, r)
    d2 = np.clip(dx * dx + dy * dy, 0, 1)
    nx, ny = dx * 0.8, dy * 0.8
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    _diffuse, facing = _lit(nx / norm, ny / norm, nz / norm)
    base = rgb(color)
    shade = base * 0.25 + base * 0.75 * ((1 - d2) ** 0.7)[..., None]
    caustic = np.exp(-((dx - 0.3) ** 2 + (dy - 0.38) ** 2) / 0.09)[..., None]
    shade = shade + (base * 0.5 + 0.5) * caustic * 0.6 + (facing ** 70 * 1.2)[..., None]
    shade *= (1 - 0.45 * smooth(0.78, 1.0, np.sqrt(d2)))[..., None]
    return shade, inside


def _pearl(xs: np.ndarray, ys: np.ndarray, x: float, y: float, r: float) -> tuple[np.ndarray, np.ndarray]:
    """A pearl: lilac in its shade, a sharp highlight and a blush of pink bounced up from below."""
    inside, dx, dy, nz = _ball(xs, ys, x, y, r)
    diffuse, facing = _lit(dx, dy, nz)
    shade = _ramp(0.25 + 0.75 * diffuse, PEARL) + (facing ** 40 * 0.9)[..., None]
    bounce = np.exp(-((dx - 0.45) ** 2 + (dy - 0.55) ** 2) / 0.12)[..., None]
    shade = shade + rgb("#ffc8e6") * bounce * 0.25
    return shade, inside


def _crown_paths(w: float) -> tuple[QPainterPath, QPainterPath]:
    """The crown's five points and its band, w wide."""

    def at(x: float, y: float) -> QPointF:
        return QPointF(x * w, (y + 0.03) * w)

    points = QPainterPath(at(0.155, 0.64))
    for x, y in ((0.07, 0.26), (0.265, 0.47), (0.3, 0.155), (0.405, 0.43), (0.5, 0.075), (0.595, 0.43), (0.7, 0.155), (0.735, 0.47), (0.93, 0.26), (0.845, 0.64)):
        points.lineTo(at(x, y))
    points.closeSubpath()
    band = QPainterPath(at(0.13, 0.57))
    band.quadTo(at(0.5, 0.66), at(0.87, 0.57))
    band.lineTo(at(0.885, 0.775))
    band.quadTo(at(0.5, 0.87), at(0.115, 0.775))
    band.closeSubpath()
    return points, band


def _box(x: float, y: float, r: float, w: int, h: int) -> tuple[slice, slice]:
    """The rows and columns round a circle, inside a picture w by h."""
    return slice(max(0, int(y - r) - 2), min(h, int(y + r) + 3)), slice(max(0, int(x - r) - 2), min(w, int(x + r) + 3))


def _crown_picture(w: int) -> QImage:
    """The little crown, w pixels wide and 0.9 w high: lavender silver points with a ridge down each,
    a lavender enamel band with a row of seed pearls, a violet stone between a pink and a blue one,
    pearls on its points and an ink line round it all, lit per pixel from the upper left. Made once
    for each size."""
    key = ("crown", w)
    if key in _PICTURES:
        return _PICTURES[key]
    h = round(w * 0.9)
    points, band = _crown_paths(w)
    oy = 0.03 * w
    pointed = mask(w, h, _filled(points))
    banded = mask(w, h, _filled(band))
    body = np.maximum(pointed, banded)

    def ridges(q: QPainter) -> None:
        q.setPen(QPen(QColor("#ffffff"), w * 0.014, Qt.SolidLine, Qt.RoundCap))
        for (x0, y0), (x1, y1) in (((0.2, 0.6), (0.075, 0.27)), ((0.31, 0.6), (0.3, 0.17)), ((0.5, 0.6), (0.5, 0.09)), ((0.69, 0.6), (0.7, 0.17)), ((0.8, 0.6), (0.925, 0.27))):
            q.drawLine(QPointF(x0 * w, y0 * w + oy), QPointF(x1 * w, y1 * w + oy))

    xs, ys = _grid(w, h)
    s = w * 0.016
    gems = ((0.5, 0.715, 0.07, "#8a5cff"), (0.295, 0.692, 0.042, "#ff7fbf"), (0.705, 0.692, 0.042, "#62b8ff"), (0.5, 0.37, 0.034, "#b58cff"))
    tips = ((0.07, 0.23, 0.042), (0.3, 0.125, 0.04), (0.5, 0.04, 0.047), (0.7, 0.125, 0.04), (0.93, 0.23, 0.042))
    seeds = [(x, 0.8 - 0.21 * (1 - ((x - 0.5) / 0.4) ** 2) * 0.22, 0.013) for x in np.linspace(0.17, 0.83, 13) if abs(x - 0.5) > 0.09]
    height = 1.3 * blur(pointed, s * 1.8) * pointed + 0.5 * blur(mask(w, h, ridges), s * 0.9) * pointed
    height = np.maximum(height, 0.9 * blur(banded, s * 0.8) + 0.25)
    height *= smooth(0.0, 0.5, blur(body, s * 0.5))
    for x, y, r, _c in gems:
        cut = _box(x * w, y * w + oy, r * w * 1.34 + 3 * s, w, h)
        height[cut] += 0.45 * blur(_disc(xs[cut], ys[cut], x * w, y * w + oy, r * w * 1.34), s * 0.35)
    for x, y, r in seeds:
        cut = _box(x * w, y * w + oy, r * w, w, h)
        height[cut] += 0.6 * _ball(xs[cut], ys[cut], x * w, y * w + oy, r * w)[3]
    nx, ny, nz = _relief(height, 3.0 * s)
    diffuse, facing = _lit(nx, ny, nz)
    e = np.clip(0.52 - 0.5 * ny + 0.2 * nx + (0.5 - ys / h) * 0.35, 0, 1)
    light = (0.7 + 0.3 * diffuse)[..., None]
    silver = _ramp(e, SILVER) * light + (facing ** 40 * 0.9)[..., None]
    enamel = _ramp(e, ENAMEL) * light + (facing ** 60 * 0.8)[..., None]
    share = np.clip(blur(banded, 0.8), 0, 1)[..., None]
    color = silver * (1 - share) + enamel * share
    alpha = body.copy()
    ink = np.maximum(_rim(body, w * 0.004), 0.55 * _rim(banded, w * 0.003))
    for x, y, r in seeds:
        cut = _box(x * w, y * w + oy, r * w, w, h)
        shade, inside = _pearl(xs[cut], ys[cut], x * w, y * w + oy, r * w)
        color[cut], alpha[cut] = _over(color[cut], alpha[cut], shade, inside)
    for x, y, r, tint in gems:
        cut = _box(x * w, y * w + oy, r * w, w, h)
        shade, inside = _gem(xs[cut], ys[cut], x * w, y * w + oy, r * w, tint)
        color[cut], alpha[cut] = _over(color[cut], alpha[cut], shade, inside)
        ink[cut] = np.maximum(ink[cut], 0.7 * _rim(inside, w * 0.003))
    for x, y, r in tips:
        cut = _box(x * w, y * w + oy, r * w, w, h)
        shade, inside = _pearl(xs[cut], ys[cut], x * w, y * w + oy, r * w)
        color[cut], alpha[cut] = _over(color[cut], alpha[cut], shade, inside)
        ink[cut] = np.maximum(ink[cut], _rim(inside, w * 0.0035))
    color = color * (1 - 0.85 * ink[..., None]) + rgb(PLUM) * (0.85 * ink[..., None])
    return _kept(key, picture(color, alpha))


def _bow_paths(w: float) -> tuple[QPainterPath, QPainterPath, QPainterPath, QPainterPath]:
    """A bow w wide: its two tails, two loops, the knot, and the folds in the loops."""

    def at(x: float, y: float) -> QPointF:
        return QPointF(x * w, (y + 0.04) * w)

    tails = QPainterPath()
    for side in (1, -1):

        def m(x: float, y: float, side: int = side) -> QPointF:
            return at(0.5 + (x - 0.5) * side, y)

        tails.moveTo(m(0.46, 0.3))
        tails.cubicTo(m(0.41, 0.39), m(0.34, 0.46), m(0.25, 0.55))
        tails.lineTo(m(0.315, 0.535))
        tails.lineTo(m(0.345, 0.6))
        tails.cubicTo(m(0.41, 0.51), m(0.47, 0.42), m(0.52, 0.34))
        tails.closeSubpath()
    loops = QPainterPath()
    folds = QPainterPath()
    for side in (1, -1):

        def m(x: float, y: float, side: int = side) -> QPointF:
            return at(0.5 + (x - 0.5) * side, y)

        loops.moveTo(m(0.47, 0.24))
        loops.cubicTo(m(0.4, 0.03), m(0.1, -0.03), m(0.045, 0.15))
        loops.cubicTo(m(0.0, 0.3), m(0.1, 0.42), m(0.24, 0.39))
        loops.cubicTo(m(0.34, 0.37), m(0.42, 0.34), m(0.47, 0.32))
        loops.closeSubpath()
        folds.moveTo(m(0.45, 0.26))
        folds.quadTo(m(0.28, 0.14), m(0.12, 0.13))
        folds.moveTo(m(0.45, 0.31))
        folds.quadTo(m(0.3, 0.33), m(0.14, 0.31))
    knot = QPainterPath()
    knot.addRoundedRect(QRectF(at(0.425, 0.19), at(0.575, 0.355)), 0.05 * w, 0.05 * w)
    return tails, loops, knot, folds


def _bow_picture(w: int) -> QImage:
    """A lavender satin bow w pixels wide and 0.7 w high: puffed loops gathered into the knot with
    folds running out from it, a sheen across them, the tails behind, an ink line round each part and
    a soft shadow under it all. Made once for each size."""
    key = ("bow", w)
    if key in _PICTURES:
        return _PICTURES[key]
    h = round(w * 0.7)
    tails, loops, knot, folds = _bow_paths(w)
    xs, ys = _grid(w, h)
    kx, ky = 0.5 * w, 0.31 * w
    near = smooth(0.0, 0.22 * w, np.hypot(xs - kx, (ys - ky) * 1.4))

    def drawn(q: QPainter) -> None:
        q.setPen(QPen(QColor("#ffffff"), w * 0.022, Qt.SolidLine, Qt.RoundCap))
        q.drawPath(folds)

    # The folds are deepest where the knot gathers them and smooth out toward the loops' ends.
    crease = blur(mask(w, h, drawn), w * 0.014) * np.exp(-np.hypot(xs - kx, ys - ky) / (0.2 * w))
    color = np.zeros((h, w, 3), dtype=np.float32)
    alpha = np.zeros((h, w), dtype=np.float32)
    layers = []
    for part, puff, dim in ((tails, 0.03, 0.82), (loops, 0.05, 1.0), (knot, 0.035, 1.0)):
        cover = mask(w, h, _filled(part))
        height = blur(cover, puff * w)
        if part is loops:
            height = height * (0.5 + 0.5 * near) - 0.35 * crease * cover
        nx, ny, nz = _relief(height, 2.6 * puff * w)
        diffuse, facing = _lit(nx, ny, nz)
        shade = _ramp(np.clip(0.12 + 0.88 * diffuse, 0, 1), SATIN) * dim
        shade = shade + (facing ** 10 * 0.3 + facing ** 60 * 0.45)[..., None]
        if part is loops:
            shade *= (1 - 0.25 * (1 - near) * cover - 0.25 * crease)[..., None]
        ink = _rim(cover, w * 0.006) * 0.85
        shade = shade * (1 - ink[..., None]) + rgb(PLUM) * ink[..., None]
        layers.append((shade, cover))
    total = np.max([cover for _shade, cover in layers], axis=0)
    shadow = np.roll(blur(total, w * 0.025), round(w * 0.025), axis=0) * 0.32
    color[:] = rgb(PLUM)
    alpha[:] = shadow
    for shade, cover in layers:
        color, alpha = _over(color, alpha, shade, cover)
    return _kept(key, picture(color, alpha))


def _halo(image: QImage, scale: float, sigma: float, tint: str, strength: float) -> QImage:
    """A soft glow round what image shows, at scale of its size: laid on scaled up, under it."""
    w, h = max(1, round(image.width() * scale)), max(1, round(image.height() * scale))
    small = image.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGBA8888_Premultiplied)
    pad = round(sigma * 3)
    a = np.frombuffer(small.constBits(), dtype=np.uint8, count=small.bytesPerLine() * h).reshape(h, small.bytesPerLine())[:, 3 : w * 4 : 4]
    shape = np.pad(a.astype(np.float32) / 255, pad)
    light = blur(shape, sigma)[..., None] * rgb(tint) * strength
    return glow(light)


# The scene.


def _burst(index: int, when: float, centre: QPointF, radius: float, main: str, second: str, count: int, u: float) -> tuple:
    """A firework's strokes, worked out once: for each color, when its strokes start and an array of
    them (angle, reach as a share of the radius, bend, width, wobble); where dots go past their tips,
    its rocket's launch point and its bloom."""
    rnd = random.Random(300 + index)
    rays = []
    for i in range(count):
        ray = (2 * math.pi * (i + rnd.uniform(-0.3, 0.3)) / count, rnd.uniform(0.62, 1.0), rnd.uniform(-0.22, 0.22), rnd.uniform(2.0, 3.4) * u, rnd.uniform(0, 6.28))
        rays.append(ray)
        # Now and then a stroke is gone over twice, as a quick sketch does.
        if rnd.random() < 0.3:
            rays.append((ray[0] + rnd.choice((-1, 1)) * 0.05, ray[1] * 0.86, ray[2] * 0.6, ray[3] * 0.6, ray[4] + 2))
    inner = [
        (2 * math.pi * (i + 0.5) / (count // 2) + rnd.uniform(-0.12, 0.12), rnd.uniform(0.32, 0.46), rnd.uniform(-0.15, 0.15), 1.9 * u, rnd.uniform(0, 6.28))
        for i in range(count // 2)
    ]
    groups = (
        (main, 0.0, np.array([ray for i, ray in enumerate(rays) if i % 3], dtype=np.float64)),
        (second, 0.0, np.array([ray for i, ray in enumerate(rays) if not i % 3], dtype=np.float64)),
        (second, 0.12, np.array(inner, dtype=np.float64)),
    )
    launch = QPointF(centre.x() + rnd.uniform(-30, 30) * u, centre.y() + rnd.uniform(110, 150) * u)
    tips = np.array(rays[::2], dtype=np.float64)
    return when, centre, radius, groups, tips, launch, _burst_bloom(centre, radius, groups, u), rnd.uniform(0, 6.28), main


def _arms(centre: QPointF, radius: float, rays: np.ndarray, near: np.ndarray, outer: np.ndarray, droop: float, steps: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """Points along strokes from near to outer out from the centre (rays by steps): curving a little
    with a hand's wobble, drooping as they fall."""
    angle, bend, phase = rays[:, 0:1], rays[:, 2:3], rays[:, 4:5]
    rho = near[:, None] + (outer - near)[:, None] * np.linspace(0, 1, steps)
    k = rho / radius
    side = bend * rho * k + radius * 0.015 * np.sin(k * 9 + phase)
    ca, sa = np.cos(angle), np.sin(angle)
    return centre.x() + ca * rho - sa * side, centre.y() + sa * rho + ca * side + droop * k * k


def _pen(xs: np.ndarray, ys: np.ndarray, widths: np.ndarray) -> QPainterPath:
    """Pen strokes along rows of points, each its width at its fullest, as one shape to fill: thin at
    both ends, fullest a little past the middle, as a pen presses."""
    dx, dy = np.gradient(xs, axis=1), np.gradient(ys, axis=1)
    length = np.hypot(dx, dy) + 1e-6
    pressure = np.sin(np.pi * np.clip(np.linspace(0, 1, xs.shape[1]) * 0.85 + 0.08, 0, 1)) ** 0.6
    half = widths[:, None] * 0.5 * pressure
    nx, ny = -dy / length * half, dx / length * half
    outline_x = np.concatenate([xs + nx, (xs - nx)[:, ::-1]], axis=1).tolist()
    outline_y = np.concatenate([ys + ny, (ys - ny)[:, ::-1]], axis=1).tolist()
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    for row_x, row_y in zip(outline_x, outline_y, strict=True):
        path.addPolygon(QPolygonF([QPointF(x, y) for x, y in zip(row_x, row_y, strict=True)]))
    return path


def _tapered(points: list[QPointF], width: float) -> QPainterPath:
    """One pen stroke along points."""
    xs = np.array([[point.x() for point in points]])
    ys = np.array([[point.y() for point in points]])
    return _pen(xs, ys, np.array([width]))


def _burst_bloom(centre: QPointF, radius: float, groups: tuple, u: float) -> tuple[QImage, QRectF]:
    """The soft light under a burst at its fullest, worked out per pixel at half size."""
    scale = 0.5
    size = radius * 2.6
    area = QRectF(centre.x() - size / 2, centre.y() - size / 2, size, size)
    side = max(4, round(size * scale))
    light = np.zeros((side, side, 3), dtype=np.float32)
    for tint, _start, rays in groups:
        if not len(rays):
            continue
        xs, ys = _arms(centre, radius, rays, radius * rays[:, 1] * 0.3, radius * rays[:, 1], radius * 0.06)

        def draw(q: QPainter, xs: np.ndarray = xs, ys: np.ndarray = ys) -> None:
            q.scale(scale, scale)
            q.translate(-area.left(), -area.top())
            q.setPen(QPen(QColor("#ffffff"), 3.0 * u, Qt.SolidLine, Qt.RoundCap))
            for row_x, row_y in zip(xs.tolist(), ys.tolist(), strict=True):
                q.drawPolyline(QPolygonF([QPointF(x, y) for x, y in zip(row_x, row_y, strict=True)]))

        lines = mask(side, side, draw)
        light += (blur(lines, 5 * u * scale) * 0.9 + blur(lines, 14 * u * scale) * 0.8)[..., None] * rgb(tint)
    return glow(light), area


def _firework(p: QPainter, t: float, burst: tuple, u: float) -> None:
    """A rocket climbs, then the burst: strokes fly out, thin from the inside and droop as they fall,
    over a bloom that opens with them, with dots and little crosses twinkling past their tips."""
    when, centre, radius, groups, tips, launch, (bloom, area), phase, main = burst
    age = t - when
    if age < 0 or age > RISE + BURST:
        return
    if age < RISE:
        _rocket(p, age / RISE, launch, centre, u, phase, main)
        return
    tau = age - RISE
    fade = 1 - ease_in(win(tau, 0.85, BURST))
    grow = ease_out(clamp(tau / 0.6))
    shine = ease_out(win(tau, 0.0, 0.1)) * (1 - ease_in_out(win(tau, 0.25, 1.35)))
    if shine > 0.01:
        k = 0.45 + 0.55 * grow
        p.save()
        p.setOpacity(p.opacity() * shine)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        c = area.center()
        p.drawImage(QRectF(c.x() - area.width() * k / 2, c.y() - area.height() * k / 2, area.width() * k, area.height() * k), bloom)
        p.restore()
    flash = 1 - clamp(tau / 0.22)
    if flash > 0:
        soft_dot(p, centre.x(), centre.y(), radius * 0.45, "#ffffff", 0.85 * flash)
    # An ember stays a moment where it burst.
    ember = 1 - ease_out(clamp(tau / 0.9))
    if ember > 0:
        soft_dot(p, centre.x(), centre.y(), radius * 0.16, mix(main, "#ffffff", 0.6), 0.6 * ember)
    droop = radius * 0.16 * tau * tau
    thin = 1 - 0.45 * clamp(tau / BURST)
    p.setPen(Qt.NoPen)
    for tint, start, rays in groups:
        k = clamp((tau - start) / 0.6)
        if k <= 0 or not len(rays):
            continue
        reach = radius * rays[:, 1]
        outer = reach * (0.12 + 0.88 * ease_out(k))
        near = reach * (0.06 + 0.84 * ease_in_out(clamp((tau - start - 0.12) / 1.15)))
        if np.all(outer - near < 1.5 * u):
            continue
        xs, ys = _arms(centre, radius, rays, near, outer, droop)
        p.setBrush(col(tint, 0.95 * fade))
        p.drawPath(_pen(xs, ys, rays[:, 3] * thin))
        p.setBrush(mix(tint, "#ffffff", 0.7, 0.9 * fade))
        p.drawPath(_pen(xs, ys, rays[:, 3] * thin * 0.38))
    dots = ease_out(win(tau, 0.3, 0.55)) * fade
    if dots > 0.01:
        reach = radius * tips[:, 1]
        xs, ys = _arms(centre, radius, tips, reach * 1.1, reach * 1.1, droop * 1.2, 2)
        for i, (x, y) in enumerate(zip(xs[:, 0].tolist(), ys[:, 0].tolist(), strict=True)):
            twinkle = 0.55 + 0.45 * math.sin(tau * 9 + i * 1.7 + phase)
            if i % 3 == 0:
                star(p, x, y, 5.5 * u * twinkle, mix(main, "#ffffff", 0.5), dots, 0.16)
            else:
                p.setBrush(mix(main, "#ffffff", 0.35, dots * twinkle))
                p.drawEllipse(QPointF(x, y), 2.0 * u, 2.0 * u)


def _rocket(p: QPainter, k: float, launch: QPointF, centre: QPointF, u: float, phase: float, tint: str) -> None:
    """A rocket climbing on a wobbly hand-drawn trail, slowing as it nears the top."""
    head = ease_out(k)
    tail = max(0.0, head - 0.45)
    points = []
    for i in range(10):
        s = tail + (head - tail) * i / 9
        wobble = 4 * u * math.sin(s * 15 + phase) * (1 - s)
        points.append(QPointF(launch.x() + (centre.x() - launch.x()) * s + wobble, launch.y() + (centre.y() - launch.y()) * s))
    p.setPen(Qt.NoPen)
    p.setBrush(col(tint, 0.85))
    p.drawPath(_tapered(points, 3.2 * u))
    p.setBrush(col("#ffffff", 0.9))
    p.drawPath(_tapered(points, 1.3 * u))
    end = points[-1]
    soft_dot(p, end.x(), end.y(), 12 * u, tint, 0.7)
    star(p, end.x(), end.y(), 6 * u, "#ffffff", 1.0, 0.18)


def _crown(p: QPainter, t: float, image: QImage, halo: QImage, at: QPointF, w: float, u: float) -> None:
    """The crown drops in, tilted, bounces and settles, then floats; a glow breathes under it, light
    sweeps across it now and then and sparkles fly off it as it lands."""
    drop = win(t, 0.18, 0.78)
    if drop <= 0:
        return
    landed = t - 0.78
    y = at.y() - 150 * u * (1 - ease_back(drop, 1.4)) + (2.5 * u * math.sin((t - 0.78) * 1.7) if landed > 0 else 0)
    tilt = 13 + (9 * spring(landed, 1.3, 3.0) if landed > 0 else -10 * (1 - drop))
    h = w * image.height() / image.width()
    p.save()
    p.translate(at.x(), y)
    p.rotate(tilt)
    p.setOpacity(p.opacity() * ease_out(drop * 1.6))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    breathe = 0.75 + 0.25 * math.sin(t * 2.2)
    p.save()
    p.setOpacity(p.opacity() * breathe)
    hw = w * halo.width() / (image.width() * 0.25)
    hh = h * halo.height() / (image.height() * 0.25)
    p.drawImage(QRectF(-hw / 2, -hh / 2, hw, hh), halo)
    p.restore()
    sweep = max((win(t, at_, at_ + 0.6) for at_ in (1.05, 2.45, 3.8) if at_ <= t < at_ + 0.6), default=0.0)
    p.drawImage(QRectF(-w / 2, -h / 2, w, h), _sheen(image, sweep) if 0 < sweep < 1 else image)
    # Its pearls catch the light one after another.
    for i, (x, yy) in enumerate(((0.07, 0.26), (0.3, 0.155), (0.5, 0.07), (0.7, 0.155), (0.93, 0.26))):
        k = math.sin(math.pi * win((t - 1.0 - 0.27 * i) % 2.2, 0.0, 0.5))
        if k > 0.02 and landed > 0:
            gx, gy = (x - 0.5) * w - 0.012 * w, (yy - 0.45) * h / 0.9 - 0.02 * w
            soft_dot(p, gx, gy, 16 * u * k, "#ffffff", 0.55 * k)
            star(p, gx, gy, 13 * u * k, "#ffffff", k, 0.1)
    p.restore()
    # Landing, it throws a ring of little stars.
    if 0 < landed < 0.9:
        k = ease_out(landed / 0.9)
        for i in range(9):
            angle = -math.pi * (0.05 + 0.9 * i / 8) + math.pi * 0.08
            d = (40 + 80 * k) * u
            x, yy = at.x() + math.cos(angle) * d * 1.2, at.y() + math.sin(angle) * d * 0.8 + 20 * u * k * k
            star(p, x, yy, (7 - 3 * k) * u, ("#ffffff", LILAC, "#ffd2ec")[i % 3], 1 - k, 0.14)


def _sheen(image: QImage, k: float) -> QImage:
    """image with a slanting band of light across it, k from its left to its right, only where it is."""
    out = QImage(image)
    q = QPainter(out)
    q.setCompositionMode(QPainter.CompositionMode_SourceAtop)
    w, h = out.width(), out.height()
    x = -0.3 * w + 1.6 * w * k
    band = QLinearGradient(QPointF(x - 0.18 * w, 0), QPointF(x + 0.18 * w, h * 0.5))
    band.setColorAt(0, col("#ffffff", 0))
    band.setColorAt(0.5, col("#ffffff", 0.75 * math.sin(math.pi * k)))
    band.setColorAt(1, col("#ffffff", 0))
    q.fillRect(out.rect(), band)
    q.end()
    return out


def _ribbon_shades(front: str, back: str) -> tuple[list[QColor], list[QColor]]:
    """A curling ribbon's colors by how squarely a turn faces the eye: its back's, edge on to facing
    away, and its front's, edge on to facing the eye, where it catches the light."""
    backs = [mix(back, PLUM, 0.35 * (1 + f)) for f in np.linspace(-1, 0, 6)]
    fronts = []
    for f in np.linspace(0, 1, 12):
        shade = mix(back, front, 0.35 + 0.65 * f)
        fronts.append(mix(shade, "#ffffff", math.exp(-(((f - 0.93) / 0.07) ** 2)) * 0.8) if f > 0.75 else shade)
    return backs, fronts


def _streamer(p: QPainter, t: float, at: tuple, u: float) -> None:
    """A curling ribbon unrolling from the top edge, its curls tighter toward its end, swaying and
    turning: its turns show their bright front and darker back, and catch the light where they face it."""
    x0, length, (backs, fronts), when, phase, rate = at
    k = win(t, when, when + 0.9)
    if k <= 0:
        return
    shown = length * ease_out(k) * (1 + 0.05 * spring(t - when - 0.9, 1.4, 3.0) * (k >= 1))
    steps = max(8, round(shown / (4.5 * u)))
    sway = math.sin(t * 1.3 * rate + phase) * 16 * u + math.sin(t * 2.9 + phase * 2) * 4 * u
    pitch, curl, half = 30 * u, 10 * u, 3.25 * u
    s = np.linspace(0, shown, steps + 1)
    spin = 2 * math.pi * s / pitch * (1 + 0.4 * s / length) - t * 2.4 * rate + phase
    xs = x0 + curl * np.minimum(1.0, 0.25 + s / (0.35 * length)) * np.sin(spin) + sway * (s / length) ** 1.6
    ys = -6 * u + s
    facing = np.cos(spin)
    facing = (facing[1:] + facing[:-1]) / 2
    # Each piece reaches a little into the next, so they meet without a seam.
    dx, dy = np.diff(xs), np.diff(ys)
    reach = 0.5 / (np.hypot(dx, dy) + 1e-6)
    ax, ay = (xs[:-1] - dx * reach).tolist(), (ys[:-1] - dy * reach).tolist()
    bx, by = (xs[1:] + dx * reach).tolist(), (ys[1:] + dy * reach).tolist()
    shades = np.where(facing > 0, 6 + np.clip(np.round(facing * 11), 0, 11), np.clip(np.round((facing + 1) * 5), 0, 5)).astype(int).tolist()
    pieces: dict[int, QPainterPath] = {}
    for i, shade in enumerate(shades):
        if shade not in pieces:
            pieces[shade] = QPainterPath()
            pieces[shade].setFillRule(Qt.WindingFill)
        # All wound the same way, so pieces that overlap add up instead of cancelling.
        (lx, ly), (rx, ry) = ((ax[i], ay[i]), (bx[i], by[i])) if bx[i] >= ax[i] else ((bx[i], by[i]), (ax[i], ay[i]))
        pieces[shade].addPolygon(QPolygonF([QPointF(lx, ly - half), QPointF(rx, ry - half), QPointF(rx, ry + half), QPointF(lx, ly + half)]))
    p.setPen(Qt.NoPen)
    for shade in sorted(pieces):
        p.setBrush(backs[shade] if shade < 6 else fronts[shade - 6])
        p.drawPath(pieces[shade])


def _confetti(rnd: random.Random, width: float, height: float, u: float, title: QRectF) -> list[tuple]:
    """Pieces of confetti: when each starts falling, where, how fast, how it sways, spins and turns
    over, its shape and color."""
    pieces = []
    while len(pieces) < 96:
        side = rnd.random() < 0.45
        x = rnd.choice((rnd.uniform(0, width * 0.11), rnd.uniform(width * 0.95, width))) if side else rnd.uniform(0, width)
        if not side and title.left() - 20 * u < x < title.right() + 20 * u:
            continue
        born = rnd.uniform(-1.6, 3.6) if side else rnd.uniform(-0.6, 3.4)
        pieces.append(
            (
                born,
                x,
                rnd.uniform(-20, 30) * u,
                rnd.uniform(55, 115) * u,
                rnd.uniform(6, 20) * u,
                rnd.uniform(1.2, 2.8),
                rnd.uniform(0, 6.28),
                rnd.uniform(-3, 3),
                rnd.uniform(3, 8),
                rnd.choice(("strip", "strip", "square", "dot", "curl", "star")),
                rnd.uniform(0.8, 1.3) * u,
                rnd.choice(CONFETTI),
                side,
            )
        )
    return pieces


def _flutter(p: QPainter, t: float, pieces: list[tuple], u: float, names: QRectF, title: QRectF, keep: QRectF, bottom: float) -> None:
    """Confetti falling and turning over: the pieces over the top fade out before they reach the names,
    those down the sides fall on past them, faintly."""
    p.setPen(Qt.NoPen)
    for born, x0, y0, fall, sway, rate, phase, spin, flip, shape, size, color, side in pieces:
        age = t - born
        if age < 0:
            continue
        x, y = x0 + sway * math.sin(age * rate + phase), y0 + fall * age
        point = QPointF(x, y)
        if y > bottom + 20 * u or keep.contains(point):
            continue
        a = min(1.0, age / 0.3)
        if not side:
            a *= clamp((names.top() - 10 * u - y) / (40 * u))
        elif names.contains(point):
            a *= 0.2
        if title.contains(point):
            a *= 0.15
        if a <= 0.02:
            continue
        turn = math.cos(age * flip + phase)
        angle = age * spin + phase
        ca, sa = math.cos(angle), math.sin(angle)
        tint = col(color, a) if turn > 0 else mix(color, VIOLET, 0.3, a)
        if shape == "dot":
            p.setBrush(tint)
            p.drawEllipse(point, 2.6 * size, 2.6 * size * max(0.25, abs(turn)))
        elif shape == "star":
            p.setBrush(tint)
            p.drawPath(_star_path(x, y, 4.6 * size * (0.55 + 0.45 * abs(turn)), angle, inner=0.5))
        elif shape == "curl":
            bends = [((i - 2.5) * 2.4 * size, 2.4 * size * math.sin(i * 1.6) * turn) for i in range(6)]
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(tint, 1.7 * size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPolyline(QPolygonF([QPointF(x + lx * ca - ly * sa, y + lx * sa + ly * ca) for lx, ly in bends]))
            p.setPen(Qt.NoPen)
        else:
            hw, hh = (5.0, 2.4) if shape == "strip" else (3.2, 3.2)
            hw, hh = hw * size, hh * size * max(0.12, abs(turn))
            corners = ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))
            p.setBrush(tint)
            p.drawPolygon(QPolygonF([QPointF(x + dx * ca - dy * sa, y + dx * sa + dy * ca) for dx, dy in corners]))


def _stars(rnd: random.Random, width: float, height: float, u: float, names: QRectF, title: QRectF, keep: QRectF) -> list[tuple]:
    """Outlined stars round the edges: where, how big, when each pops in, its turn, its line and fill."""
    spots = (
        (0.045, 0.07), (0.33, 0.215), (0.235, 0.255), (0.115, 0.05), (0.69, 0.045), (0.795, 0.255), (0.985, 0.31),
        (0.035, 0.63), (0.095, 0.79), (0.2, 0.94), (0.775, 0.935), (0.965, 0.78), (0.045, 0.27), (0.6, 0.03),
    )
    out = []
    for i, (x, y) in enumerate(spots):
        point = QPointF(width * x, height * y)
        if names.contains(point) or title.contains(point) or keep.contains(point):
            continue
        out.append(
            (
                point,
                rnd.uniform(9, 15) * u,
                0.25 + 0.21 * i + rnd.uniform(0, 0.15),
                rnd.uniform(-0.3, 0.3),
                (BLUE, LAVENDER, PINK, "#9fb4ff")[i % 4],
                i % 3 != 1,
                rnd.uniform(0, 6.28),
                random.Random(500 + i),
            )
        )
    return out


def _star_path(x: float, y: float, r: float, turn: float, wobble: random.Random | None = None, inner: float = 0.48) -> QPainterPath:
    """A five-point star, a little uneven if wobble is given, as a hand draws it."""
    # The same wobble each time it is drawn.
    state = wobble.getstate() if wobble is not None else None
    corners = []
    for i in range(10):
        rr = r * (1 if i % 2 == 0 else inner) * (1 + (wobble.uniform(-0.06, 0.06) if wobble is not None else 0))
        a = turn - math.pi / 2 + i * math.pi / 5
        corners.append(QPointF(x + rr * math.cos(a), y + rr * math.sin(a)))
    if wobble is not None:
        wobble.setstate(state)
    path = QPainterPath()
    path.addPolygon(QPolygonF(corners))
    path.closeSubpath()
    return path


def _outlined_stars(p: QPainter, t: float, stars: list[tuple], u: float) -> None:
    """Each star pops in spinning, overshoots and settles, then breathes and rocks a little."""
    for point, r, born, turn, line, filled, phase, wobble in stars:
        k = win(t, born, born + 0.45)
        if k <= 0:
            continue
        size = r * ease_back(k, 2.2) * (1 + 0.09 * math.sin(t * 3.1 + phase))
        spin = turn + 0.15 * math.sin(t * 1.4 + phase) + (1 - ease_out(k)) * 1.2
        path = _star_path(point.x(), point.y(), size, spin, wobble)
        soft_dot(p, point.x(), point.y(), size * 2.2, line, 0.22 * min(1.0, k * 2))
        p.setPen(QPen(col(line, 0.95), 2.0 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(col("#ffffff", 0.92) if filled else Qt.NoBrush)
        p.drawPath(path)
    p.setPen(Qt.NoPen)


def _twinkles(p: QPainter, t: float, glints: list[tuple]) -> None:
    """Little four-point glints round the edges, each twinkling at its own pace."""
    for x, y, r, born, rate, color in glints:
        k = win(t, born, born + 0.3)
        if k <= 0:
            continue
        twinkle = max(0.0, math.sin((t - born) * rate))
        if twinkle <= 0.02:
            continue
        soft_dot(p, x, y, r * 2.4, color, 0.4 * twinkle * k)
        star(p, x, y, r * (0.6 + 0.6 * twinkle), "#ffffff", twinkle * k, 0.12)


# The marks.


def _ratio(p: QPainter) -> float:
    device = p.device()
    return max(2.0, device.devicePixelRatioF() if device is not None else 1.0)


def _ribbon_ring(cover: QRectF, ratio: float) -> QImage:
    """The ring's picture: a lavender satin ribbon wrapped round the button's edge, stitched down its
    middle, a soft glow round it and a bow tied on top. Made once for each size."""
    key = ("ring", round(cover.width(), 1), round(cover.height(), 1), ratio)
    if key in _PICTURES:
        return _PICTURES[key]
    room = 9.0
    w, h = math.ceil((cover.width() + 2 * room) * ratio), math.ceil((cover.height() + 2 * room) * ratio)
    edge = QRectF(room, room, cover.width(), cover.height()).adjusted(2.5, 2.5, -2.5, -2.5)
    radius = edge.height() * 0.17
    path = QPainterPath()
    path.addRoundedRect(edge, radius, radius)

    def stroke(width: float, dashes: list[float] | None = None):  # noqa: ANN202
        def draw(q: QPainter) -> None:
            q.scale(ratio, ratio)
            pen = QPen(QColor("#ffffff"), width, Qt.SolidLine, Qt.FlatCap, Qt.RoundJoin)
            if dashes:
                pen.setDashPattern(dashes)
                pen.setCapStyle(Qt.RoundCap)
            q.setPen(pen)
            q.setBrush(Qt.NoBrush)
            q.drawPath(path)

        return draw

    band = mask(w, h, stroke(6.5))
    stitch = mask(w, h, stroke(0.9, [2.6, 2.4]))
    nx, ny, nz = _relief(blur(band, 1.6 * ratio), 4.0 * ratio)
    diffuse, facing = _lit(nx, ny, nz)
    # Satin catches the light here and there along its length as it wraps.
    xs, ys = _grid(w, h)
    around = np.arctan2(ys / ratio - room - cover.height() / 2, (xs / ratio - room - cover.width() / 2) * cover.height() / cover.width())
    lit = np.clip(0.18 + 0.82 * diffuse * (0.86 + 0.14 * np.sin(3 * around + 0.6)), 0, 1)
    shade = _ramp(lit, SATIN) + (facing ** 12 * 0.3 + facing ** 70 * 0.4)[..., None]
    shade = shade * (1 - 0.5 * stitch[..., None]) + 0.5 * stitch[..., None]
    ink = _rim(band, 0.45 * ratio) * 0.7
    shade = shade * (1 - ink[..., None]) + rgb(PLUM) * ink[..., None]
    halo = blur(band, 3.5 * ratio) * 0.35
    color, alpha = _over(np.broadcast_to(rgb("#d9c8ff"), shade.shape).copy(), halo, shade, band)
    image = picture(color, alpha)
    bow_w = min(42.0, cover.width() * 0.3)
    bow = _bow_picture(round(bow_w * ratio))
    q = QPainter(image)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.scale(ratio, ratio)
    q.drawImage(QRectF(room + cover.width() / 2 - bow_w / 2, 0.5, bow_w, bow_w * 0.7), bow)
    q.end()
    return _kept(key, image)


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A lavender satin ribbon round the button with a bow on top; a shine runs round it."""
    image = _ribbon_ring(cover, _ratio(p))
    window = cover.adjusted(-9, -9, 9, 9)
    p.drawImage(window, image)
    edge = cover.adjusted(2.5, 2.5, -2.5, -2.5)
    radius = edge.height() * 0.17
    path = QPainterPath()
    path.addRoundedRect(edge, radius, radius)
    for k, strength in (((t * 0.16) % 1.0, 1.0), ((t * 0.16 + 0.5) % 1.0, 0.6)):
        at = path.pointAtPercent(k)
        soft_dot(p, at.x(), at.y(), 9, "#ffffff", 0.55 * strength)
        star(p, at.x(), at.y(), 5.5 * strength, "#ffffff", 0.95 * strength, 0.14)
    # A glint on the bow's knot now and then.
    k = math.sin(math.pi * win(t % 2.6, 0.0, 0.55))
    if k > 0.02:
        x, y = cover.center().x() - 3, cover.top() - 9 + 0.5 + min(42.0, cover.width() * 0.3) * 0.22
        star(p, x, y, 8 * k, "#ffffff", k, 0.12)


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A little crown that bobs and sways, a glow under it and light glinting off its stone."""
    ratio = _ratio(p)
    w = box.width() * 0.92
    image = _crown_picture(round(w * ratio))
    key = ("badge halo", image.width())
    # A glow 7 points soft, worked out at a quarter size.
    halo = _PICTURES.get(key)
    if halo is None:
        halo = _kept(key, _halo(image, 0.25, 1.75 * ratio, "#cdb8ff", 1.4))
    h = w * 0.9
    c = box.center()
    p.save()
    p.translate(c.x(), c.y() + 1.2 * math.sin(t * 2.3))
    p.rotate(5 * math.sin(t * 1.15))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    hw, hh = w * halo.width() / (image.width() * 0.25), h * halo.height() / (image.height() * 0.25)
    p.save()
    p.setOpacity(0.75 + 0.25 * math.sin(t * 2.0))
    p.drawImage(QRectF(-hw / 2, -hh / 2, hw, hh), halo)
    p.restore()
    sweep = win(t % 3.2, 1.2, 1.9)
    p.drawImage(QRectF(-w / 2, -h / 2, w, h), _sheen(image, sweep) if 0 < sweep < 1 else image)
    k = math.sin(math.pi * win(t % 3.2, 0.2, 0.75))
    if k > 0.02:
        star(p, -0.035 * w, 0.27 * w - h / 2 + 0.3 * h, 9 * k, "#ffffff", k, 0.1)
    p.restore()


def _card_picture(width: float, height: float, ratio: float) -> QImage:
    """The card's picture: white paper with a fine grain and a lavender blush at its foot, a scalloped
    lace hem with a row of lavender dots stitched above it, a stitched lavender line inside its edge
    and a satin bow on top. Made once for each size."""
    key = ("card", round(width, 1), round(height, 1), ratio)
    if key in _PICTURES:
        return _PICTURES[key]
    w, h = math.ceil(width * ratio), math.ceil(height * ratio)
    body = QRectF(0.75, CARD_TOP + 0.5, width - 1.5, height - CARD_TOP - 1.0)
    bump = 2.8
    count = max(3, round(body.width() / (bump * 2.2)))
    step = body.width() / count
    paper = QPainterPath()
    paper.addRoundedRect(body.adjusted(0, 0, 0, -bump), 9, 9)
    lower = QPainterPath()
    lower.addRect(body.adjusted(0, body.height() * 0.5, 0, -bump))
    paper = paper.united(lower)
    # The scallops add to the paper where they overlap it and each other.
    paper.setFillRule(Qt.WindingFill)
    dots = QPainterPath()
    for i in range(count):
        x = body.left() + step * (i + 0.5)
        paper.addEllipse(QPointF(x, body.bottom() - bump), step * 0.56, bump)
        dots.addEllipse(QPointF(x, body.bottom() - bump - 2.6), 0.85, 0.85)
    paper = paper.simplified()
    stitch_at = body.adjusted(3.5, 3.5, -3.5, -bump - 5.5)

    def scaled(draw):  # noqa: ANN001, ANN202
        def inner(q: QPainter) -> None:
            q.scale(ratio, ratio)
            draw(q)

        return inner

    def stitch_line(q: QPainter) -> None:
        pen = QPen(QColor("#ffffff"), 0.9, Qt.SolidLine, Qt.RoundCap)
        pen.setDashPattern([2.6, 2.2])
        q.setPen(pen)
        q.setBrush(Qt.NoBrush)
        q.drawRoundedRect(stitch_at, 6, 6)

    cover = mask(w, h, scaled(_filled(paper)))
    dotted = mask(w, h, scaled(_filled(dots)))
    stitch = mask(w, h, scaled(stitch_line))
    _xs, ys = _grid(w, h)
    grain = noise(w, h, 3.0 * ratio, 2, 41) - 0.5
    down = np.clip((ys / ratio - CARD_TOP) / max(1.0, height - CARD_TOP), 0, 1)
    shade = _ramp(down, ((0.0, "#ffffff"), (0.55, "#fcfaff"), (1.0, "#f1ebfd")))
    shade = shade * (1 + grain[..., None] * 0.03)
    edge = 1 - smooth(0.55, 1.0, blur(cover, 2.5 * ratio))
    shade = shade * (1 - 0.08 * edge)[..., None] + rgb("#cdb9f5") * (0.08 * edge)[..., None]
    for marks, tint, strength in ((stitch, LAVENDER, 0.8), (dotted, LAVENDER, 0.9), (_rim(cover, 0.5 * ratio), "#a58ce0", 0.75)):
        shade = shade * (1 - strength * marks[..., None]) + rgb(tint) * (strength * marks[..., None])
    image = picture(shade, cover)
    bow_w = min(44.0, width * 0.36)
    bow = _bow_picture(round(bow_w * ratio))
    q = QPainter(image)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.scale(ratio, ratio)
    q.drawImage(QRectF(width / 2 - bow_w / 2, CARD_TOP + 5 - bow_w * 0.7 * 0.62, bow_w, bow_w * 0.7), bow)
    q.end()
    return _kept(key, image)


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """White lace-hemmed paper with a lavender bow on top; sparkles twinkle on the bow and corners."""
    p.drawImage(rect, _card_picture(rect.width(), rect.height(), _ratio(p)))
    bow_w = min(44.0, rect.width() * 0.36)
    spots = (
        (rect.center().x() - 2, rect.top() + CARD_TOP + 5 - bow_w * 0.7 * 0.62 + bow_w * 0.25, 6.5),
        (rect.right() - 7, rect.top() + CARD_TOP + 6, 5.0),
        (rect.left() + 7, rect.bottom() - 9, 4.5),
    )
    for i, (x, y, r) in enumerate(spots):
        k = math.sin(math.pi * win((t - 0.8 * i) % 2.4, 0.0, 0.6))
        if k > 0.02:
            soft_dot(p, x, y, r * 1.4, "#e6dcff", 0.6 * k)
            star(p, x, y, r * k, "#ffffff", k, 0.13)


# Before each name: a puffy star, lavender, pink and blue in turn.
_STAR_TINTS = (
    ((0.0, "#6b50c0"), (0.45, "#a58cf0"), (0.8, "#d9ccff"), (1.0, "#ffffff")),
    ((0.0, "#c0508f"), (0.45, "#f590c8"), (0.8, "#ffd0ea"), (1.0, "#ffffff")),
    ((0.0, "#3f78c0"), (0.45, "#7cbcf5"), (0.8, "#cfe9ff"), (1.0, "#ffffff")),
)


def lead(size: float, index: int) -> QPixmap:
    """A small puffy star, lit per pixel, tipped a little this way or that."""
    ratio = 3.0
    side = max(4, round(size * ratio))
    which = index % 3
    xs, ys = _grid(side, side)
    path = _star_path(side / 2, side * 0.53, side * 0.4, (-0.12, 0.1, -0.04)[which], inner=0.55)
    cover = mask(side, side, _filled(path))
    nx, ny, nz = _relief(blur(cover, side * 0.07), side * 0.2)
    diffuse, facing = _lit(nx, ny, nz)
    shade = _ramp(np.clip(0.15 + 0.85 * diffuse, 0, 1), _STAR_TINTS[which]) + (facing ** 30 * 0.6)[..., None]
    ink = _rim(cover, side * 0.018) * 0.75
    shade = shade * (1 - ink[..., None]) + rgb(PLUM) * ink[..., None]
    image = picture(shade, cover)
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap
