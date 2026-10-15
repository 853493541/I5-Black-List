"""竹风: the lobby in a frame of jade and bamboo with a breeze blowing round it, for a player who plays
吴邪 (小说家, the 盗墓笔记 costume).

The whole lobby turns a soft jade green, deeper toward the edges, and luminous mint mist drifts along
them from left to right. A carved jade frame with a fine pale-gold line inside it runs round the
screen, lattice window corners (窗棂, as at 吴山居) in its four corners and a jade knob at each end by
the button. Bamboo rises along the left and right edges as it starts and bends with each gust; sprigs
of bamboo leaves hang along the top and rustle, and tufts of them grow from the bottom either side of
the button. The wind goes round the frame, up the left, across the top and down the right, as
curling streaks of mint light carrying leaves, and a few cross between the rows. In the top left the
蛇眉铜鱼, three bronze fish nose to tail in a ring with a snake's brow over each eye, turns in a swirl
of yellow-green wind with sparkles; in the top right the wind and its leaves gather into a heart that
breathes. At the end it all fades.

Its marks: the card is pale jade framed in bamboo, a sprig over its corner and a bamboo leaf before
each name; the ring is a jade band round the button with small leaves blown round it; the badge is
the three-fish ring, turning.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
    QTransform,
)

from blacklist_detect.love_scenes.draw import (
    catmull,
    clamp,
    col,
    ease_in,
    ease_in_out,
    ease_out,
    lengths,
    mix,
    point_at,
    soft_dot,
    star,
    win,
)
from blacklist_detect.love_scenes.light import blur, glow, mask, noise, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# Soft light and slow shapes: drawn at one pixel per point and scaled up on a sharper screen; the
# fish ring and the heart are drawn crisp on top (paint.sharp).
MAX_RATIO = 1.0
# Jade from its glow to its depth, mint light and mist, the wind's yellow-green, pale gold, the ink.
JADE_LIGHT = "#a6f0cc"
JADE = "#3fb488"
JADE_DEEP = "#0d5a43"
JADE_DARK = "#06382b"
MINT = "#aef5d6"
MIST = "#e6fff4"
LIME = "#d9f27c"
GOLD = "#f2e2a8"
INK = "#0e4a37"
# The lobby's tint: mint-jade in the middle, deep jade at the edges.
TINT = ("#3fb98d", "#0b5640")
GOLD_RAMP = ((0.0, "#4a3410"), (0.35, "#a0803a"), (0.6, "#d8bd78"), (0.82, "#f3e4b2"), (1.0, "#fffbee"))
PATINA = ("#3f8f74", "#8fd6bb")
BRONZE_RAMP = ((0.0, "#120a04"), (0.25, "#36220f"), (0.48, "#654522"), (0.66, "#957037"), (0.82, "#c6a05c"), (0.94, "#ead293"), (1.0, "#fff3d0"))
# Bamboo leaves, base to tip: jade, mint, spring yellow-green and deep.
LEAVES = (
    ("#2c6c3a", "#3f9f5e", "#93d27a"),
    ("#246a4c", "#41aa7e", "#a9e6b0"),
    ("#4a7c27", "#80b545", "#d6ec8a"),
    ("#1d553a", "#2c8659", "#71c592"),
)
# The stalks: shade, lit side, sheen.
STALKS = (("#24502a", "#58b468", "#eaffd6"), ("#2c5626", "#7bb54e", "#f2ffd0"), ("#1d4a35", "#47a879", "#e2fff0"))
# Light from the upper left.
LIGHT = np.array([-0.5, -0.62, 0.6], dtype=np.float32) / np.linalg.norm([-0.5, -0.62, 0.6])
# The gusts: when each is strongest, and how strong.
GUSTS = ((1.3, 1.0), (2.4, 0.85), (3.5, 1.0))
LOOK = {
    "glow": (96, 214, 160),
    "rim": "#62d6a6",
    "band": ("#43b685", "#c9f2dc"),
    "card": ("#e8f8ee", "#cdeedb"),
    "edge": "#4aac80",
    "ink": INK,
    "flowers": (("#effcf4", "#a6f0cc", "#3fb488"), ("#fbffe8", "#d9f27c", "#80b545")),
    "disc": ("#eefaf3", "#bfe9d2"),
    "heart": ("#a6f0cc", "#2f9c74"),
    "deep": "#2f9c74",
    "deep_glow": (80, 200, 150),
}
MARKS_ANIMATED = True
# Room over the card for the sprig over its corner.
CARD_TOP = 12
# The bamboo round the card takes room on its edges.
CARD_PAD = (15, 10, 15, 10)


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(31)
    settled = _settled(width, height, gap, u)
    mist = _Mist(width, height, gap, u)
    leaves = _Leaves(u)
    stalks = _stalks(width, height, u, leaves)
    garland = _garland(width, u, rnd, leaves)
    tufts = _tufts(width, height, gap, u, rnd, leaves)
    loop = _path(_loop_points(width, height, u))
    lane = _lane(stage, u)
    flyers = [
        (rnd.random() * loop[1][-1], rnd.uniform(-1, 1), rnd.uniform(0.8, 1.15), rnd.randrange(len(LEAVES)), rnd.uniform(0, 6.3), rnd.uniform(0.9, 1.4), 0.75 + rnd.uniform(0, 0.55))
        for _ in range(36)
    ]
    crossers = [(1.45, 0.95), (2.55, 1.1), (3.3, 0.85)]
    motes = [(rnd.random() * loop[1][-1], rnd.uniform(-1, 1), rnd.uniform(0.5, 1.6), rnd.uniform(1.6, 3.4) * u, rnd.uniform(0, 6.3)) for _ in range(22)]
    streaks = _streaks(width, height, gap, u, lane)
    shine = _shine_route(width, height, gap, u)
    heroes = _Heroes(QPointF(190 * u, 150 * u), QPointF(width - 190 * u, 150 * u), u, leaves)
    travel = _travel()

    def paint(p: QPainter, t: float, sharp: bool = True) -> None:
        life = ease_out(win(t, 0.0, 0.8))
        leave = ease_in(win(t, 4.2, 5.0))
        a = life * (1 - leave)
        if a <= 0:
            return
        gust = _gust(t)
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setOpacity(a * (0.95 + 0.05 * math.sin(t * 2.4)))
        p.drawImage(QRectF(0, 0, width, height), settled)
        p.setOpacity(1.0)
        mist.paint(p, t, a * (0.85 + 0.15 * math.sin(t * 1.7 + 1)))
        p.setOpacity(a)
        for stalk in stalks:
            stalk.paint(p, t, gust)
        for at, angle, sprig, phase in tufts:
            grow = ease_out(win(t, 0.35 + phase * 0.05, 0.9 + phase * 0.05))
            if grow > 0:
                rustle = 5 * math.sin(t * 2.3 + phase * 1.7) + 9 * _gust(t - 0.1 - phase * 0.02)
                sprig.paint(p, at, angle + rustle, grow)
        for at, angle, sprig, phase in garland:
            drop = ease_out(win(t, 0.25 + 0.03 * phase, 0.85 + 0.03 * phase))
            if drop > 0:
                rustle = 4 * math.sin(t * 2.6 + phase * 0.9) - 10 * _gust(t - 0.04 * phase) + 2 * math.sin(t * 7.1 + phase)
                sprig.paint(p, at, angle + rustle, drop)
        blow = ease_out(win(t, 0.75, 1.3))
        for streak in streaks:
            streak.paint(p, t, a)
        _shine(p, t, shine, u, a * blow)
        _motes(p, t, motes, loop, travel, stage, a * blow)
        _flyers(p, t, flyers, loop, travel, leaves, stage, blow * (1 - leave))
        _crossers(p, t, crossers, lane, leaves, u, 1 - leave)
        p.restore()
        if sharp:
            heroes.paint(p, t, gust)

    paint.sharp = lambda p, t: heroes.paint(p, t, _gust(t))
    return paint


def _gust(t: float) -> float:
    """How hard the wind blows t seconds in: a breeze from when it starts, and three gusts."""
    breeze = 0.3 * ease_out(win(t, 0.6, 1.2))
    return breeze + sum(strength * math.exp(-(((t - at) / 0.34) ** 2)) for at, strength in GUSTS)


def _travel() -> np.ndarray:
    """How far the wind has carried a leaf by each hundredth of a second, in points at full size: a
    steady breeze, faster in the gusts and at the end, as it blows away."""
    times = np.arange(0, 5.6, 0.01)
    speed = np.array([230 * (0.65 + 0.85 * _gust(t)) + 260 * ease_in(win(t, 4.1, 5.0)) for t in times])
    return np.concatenate([[0.0], np.cumsum(speed[:-1] * 0.01)])


def _carried(travel: np.ndarray, t: float) -> float:
    return float(np.interp(t * 100, np.arange(len(travel)), travel))


# Pictures worked out per pixel.


def _lit(height: np.ndarray, relief: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A height field lit from the upper left: how lit each pixel is, how much it mirrors the light,
    and how much it mirrors the bright sky above."""
    gy, gx = np.gradient(height)
    nx, ny = -gx * relief, -gy * relief
    norm = np.sqrt(nx * nx + ny * ny + 1)
    nx, ny, nz = nx / norm, ny / norm, 1 / norm
    diffuse = np.clip(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0, 1)
    rx, ry, rz = 2 * nz * nx, 2 * nz * ny, 2 * nz * nz - 1
    spec = np.clip(rx * LIGHT[0] + ry * LIGHT[1] + rz * LIGHT[2], 0, 1)
    sky = smooth(-0.6, 0.7, -(ry * 0.85 + rx * 0.4))
    return diffuse, spec, sky


def _jade(height: np.ndarray, relief: float, thick: np.ndarray, cloud: np.ndarray | float, deep: str = JADE_DEEP, light: str = JADE_LIGHT) -> np.ndarray:
    """Carved jade over a height field: light comes through where it is thick and cloudy, it is deep
    green where thin, lit from the upper left with a soft wet shine and the sky in its slopes."""
    diffuse, spec, sky = _lit(height, relief)
    body = rgb(deep) + (rgb(light) - rgb(deep)) * np.clip(0.12 + 0.55 * thick + 0.3 * cloud, 0, 1)[..., None]
    return body * (0.48 + 0.62 * diffuse)[..., None] + rgb("#c8ffe8") * (0.16 * sky)[..., None] + (spec ** 26 * 0.8)[..., None]


def _ramp(stops: tuple, tone: np.ndarray) -> np.ndarray:
    at = [k for k, _ in stops]
    colors = np.array([rgb(color) for _, color in stops])
    out = np.empty((*tone.shape, 3), dtype=np.float32)
    for k in range(3):
        out[..., k] = np.interp(tone, at, colors[:, k])
    return out


def _gold(height: np.ndarray, relief: float) -> np.ndarray:
    diffuse, spec, sky = _lit(height, relief)
    tone = np.clip(0.18 + 0.42 * diffuse + 0.3 * sky + 0.3 * spec ** 10, 0, 1)
    return _ramp(GOLD_RAMP, tone) + (spec ** 24 * 0.35)[..., None]


def _over(pre: np.ndarray, alpha: np.ndarray, top_color: np.ndarray, top_alpha: np.ndarray, y: int = 0, x: int = 0) -> None:
    """Lays a picture (straight color and alpha) over a premultiplied one, its top left at x, y;
    whatever falls outside is left out."""
    h, w = top_alpha.shape
    y0, x0 = max(0, y), max(0, x)
    y1, x1 = min(alpha.shape[0], y + h), min(alpha.shape[1], x + w)
    if y1 <= y0 or x1 <= x0:
        return
    ta = top_alpha[y0 - y : y1 - y, x0 - x : x1 - x]
    tc = top_color[y0 - y : y1 - y, x0 - x : x1 - x] if top_color.ndim == 3 else top_color
    keep = 1 - ta
    pre[y0:y1, x0:x1] *= keep[..., None]
    pre[y0:y1, x0:x1] += tc * ta[..., None]
    alpha[y0:y1, x0:x1] *= keep
    alpha[y0:y1, x0:x1] += ta


def _picture(pre: np.ndarray, alpha: np.ndarray, ratio: float = 1.0) -> QImage:
    alpha = np.clip(alpha, 0, 1)
    pre = np.minimum(np.clip(pre, 0, 1), alpha[..., None])
    pixels = np.ascontiguousarray((np.dstack([pre, alpha]) * 255 + 0.5).astype(np.uint8))
    h, w = alpha.shape
    image = QImage(pixels.data, w, h, w * 4, QImage.Format_RGBA8888_Premultiplied).copy()
    image.setDevicePixelRatio(ratio)
    return image


def _straight(color: np.ndarray, alpha: np.ndarray, ratio: float = 1.0) -> QImage:
    return _picture(np.clip(color, 0, 1) * np.clip(alpha, 0, 1)[..., None], alpha, ratio)


def _rounded(xs: np.ndarray, ys: np.ndarray, rect: QRectF, radius: float) -> np.ndarray:
    """How far each point is outside a rounded rectangle (less than 0 inside)."""
    qx = np.abs(xs - rect.center().x()) - (rect.width() / 2 - radius)
    qy = np.abs(ys - rect.center().y()) - (rect.height() / 2 - radius)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - radius


# The frame, the lobby's tint and the lattice corners: laid once, then on every frame.

# The frame's bar: its outer edge in from the screen's, its width and the roundness of its corners.
EDGE, BAR, ROUND = 11.0, 15.0, 30.0
# The lattice corners' reach.
CORNER = 128.0


def _settled(width: float, height: float, gap: QRectF, u: float) -> QImage:
    """The jade tint over the whole lobby, the mint light inside the frame, the frame and its gold
    line, its knobs by the button, the festoon of bamboo twig under its top and the lattice corners,
    one picture at a pixel to the point."""
    w, h = max(1, round(width)), max(1, round(height))
    xs = (np.arange(w, dtype=np.float32) + 0.5)[None, :]
    ys = (np.arange(h, dtype=np.float32) + 0.5)[:, None]
    side = np.minimum(xs, w - xs)
    near = 1 - smooth(0, 340 * u, side) * smooth(0, 290 * u, ys) * smooth(0, 220 * u, h - ys)
    hole = smooth(0, 44 * u, _rounded(xs, ys, gap, 14 * u))
    alpha = (0.2 + 0.52 * near ** 1.6) * hole
    color = rgb(TINT[0]) + (rgb(TINT[1]) - rgb(TINT[0])) * (near ** 0.9)[..., None]
    pre = color * alpha[..., None]
    cloud = noise(max(2, w // 4 + 2), max(2, h // 4 + 2), 18 * u, 3, 7)
    # The frame and the light inside it are only near the edges: worked out in four strips there.
    reach = min(math.ceil(150 * u), h // 2, w // 2)
    for y0, y1, x0, x1 in ((0, reach, 0, w), (h - reach, h, 0, w), (reach, h - reach, 0, reach), (reach, h - reach, w - reach, w)):
        if y1 > y0 and x1 > x0:
            _frame(pre[y0:y1, x0:x1], alpha[y0:y1, x0:x1], xs[:, x0:x1], ys[y0:y1], hole[y0:y1, x0:x1], cloud, width, height, gap, u)
    middle = EDGE * u + BAR * u / 2
    ends = (gap.left() - 14 * u, gap.right() + 14 * u)
    for x in ends:
        _over(*_knob(QPointF(x, height - middle), 10.5 * u, u, pre, alpha))
    _festoon(pre, alpha, width, u)
    _corners(pre, alpha, width, height, u)
    return _picture(pre, alpha)


def _frame(pre: np.ndarray, alpha: np.ndarray, xs: np.ndarray, ys: np.ndarray, hole: np.ndarray, cloud: np.ndarray, width: float, height: float, gap: QRectF, u: float) -> None:
    """Mint light gathered inside the frame, deep jade outside it to the screen's edge, the bar (a
    rounded jade molding with a groove along its inner side) and its fine gold line, in a part of
    the picture: xs and ys are its points' places."""
    # The frame's middle line, and how far each point is from it (less than 0 inside).
    middle = EDGE * u + BAR * u / 2
    inner = QRectF(middle, middle, width - 2 * middle, height - 2 * middle)
    d = _rounded(xs, ys, inner, (ROUND - BAR / 2) * u)
    half = BAR * u / 2
    inside = np.maximum(-d - half, 0)
    _over(pre, alpha, rgb(MINT), np.exp(-inside / (24 * u)) * (inside > 0) * hole * 0.42)
    # The frame stops either side of the button, a knob at each end.
    ends = (gap.left() - 14 * u, gap.right() + 14 * u)
    bottom = ys > height / 2
    cut = bottom & (xs > ends[0]) & (xs < ends[1])
    feather = np.where(bottom, 1 - smooth(ends[0] - 2 * u, ends[0] + 10 * u, xs) * (1 - smooth(ends[1] - 10 * u, ends[1] + 2 * u, xs)), 1.0)
    rows = np.minimum((ys[:, 0] // 4).astype(int), cloud.shape[0] - 1)
    cols = np.minimum((xs[0] // 4).astype(int), cloud.shape[1] - 1)
    cloud = cloud[rows][:, cols]
    out = np.clip(d - half + 0.5, 0, 1) * feather
    _over(pre, alpha, rgb(JADE_DARK) + (rgb(JADE_DEEP) - rgb(JADE_DARK)) * cloud[..., None], out * 0.86)
    v = np.clip(d / half, -1, 1)
    bar = np.clip(half - np.abs(d) + 0.5, 0, 1) * ~cut
    shape = np.sqrt(np.clip(1 - v * v, 0, 1)) - 0.22 * np.exp(-(((v + 0.42) / 0.11) ** 2))
    jade = _jade(shape * half * (np.abs(d) < half + 2), 1.0, np.clip(shape, 0, 1) * 0.8, cloud, JADE_DEEP, "#6fd6a6")
    _over(pre, alpha, jade, bar)
    line = d + half + 3.6 * u
    gold = np.clip(0.75 * u - np.abs(line) + 0.5, 0, 1) * ~cut
    _over(pre, alpha, rgb(GOLD) * (0.9 + 0.2 * cloud)[..., None], gold * 0.95)


def _knob(center: QPointF, r: float, u: float, pre: np.ndarray, alpha: np.ndarray) -> tuple:
    """A jade bead at an end of the frame, with a gold ring round it."""
    x0, y0 = math.floor(center.x() - r - 2), math.floor(center.y() - r - 2)
    size = math.ceil(2 * r + 4)
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32) + 0.5
    dist = np.hypot(xs + x0 - center.x(), ys + y0 - center.y())
    ball = np.sqrt(np.clip(1 - (dist / r) ** 2, 0, 1))
    color = _jade(ball * r, 1.0, ball, 0.5)
    cover = np.clip(r - dist + 0.5, 0, 1)
    ring = np.clip(0.7 * u - np.abs(dist - (r - 1.6 * u)) + 0.5, 0, 1)
    color = color * (1 - ring[..., None]) + _gold(ball * r, 1.0) * ring[..., None]
    return pre, alpha, color, cover, y0, x0


def _festoon(pre: np.ndarray, alpha: np.ndarray, width: float, u: float) -> None:
    """A bamboo twig hung in swags under the frame's top, from one sprig to the next."""
    top = math.ceil(70 * u)
    w = pre.shape[1]
    points = _festoon_points(width, u)
    path = QPainterPath(points[0])
    for a, b in zip(points, points[1:], strict=False):
        path.quadTo(QPointF((a.x() + b.x()) / 2, a.y() + 18 * u), b)

    def draw(q: QPainter) -> None:
        q.setPen(QPen(QColor("#ffffff"), 3.2 * u, Qt.SolidLine, Qt.RoundCap))
        q.drawPath(path)

    cover = mask(w, top, draw)
    lift = blur(cover, 1.2 * u) * cover
    color = _jade(lift * 2.4 * u, 1.0, lift, 0.4, "#2a5a26", "#9bd67a")
    _over(pre, alpha, color, cover * 0.95)


def _festoon_points(width: float, u: float) -> list[QPointF]:
    count = 17
    left, right = 280 * u, width - 280 * u
    return [QPointF(left + (right - left) * k / (count - 1), 33 * u) for k in range(count)]


def _lattice(u: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The top left lattice corner, its corner at 0, 0: the jade (a band round its arc, a plate in
    the corner and the nested steps of 步步锦 between them), the gold (a fine line inside the arc, a
    knot on the plate and a few studs) and the window paper behind, glowing."""
    reach = CORNER * u
    size = math.ceil(reach + 2)

    def lattice(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#ffffff"))
        disc = QPainterPath()
        disc.addEllipse(QPointF(0, 0), reach, reach)
        within = QPainterPath()
        within.addEllipse(QPointF(0, 0), reach - 7 * u, reach - 7 * u)
        q.drawPath(disc.subtracted(within))
        q.drawRoundedRect(QRectF(-8 * u, -8 * u, 44 * u, 44 * u), 5 * u, 5 * u)
        q.setClipPath(within)
        bar = 2.2 * u
        steps = [36 * u + 14 * u * k for k in range(6)]
        for d in steps:
            q.drawRect(QRectF(d - bar, d - bar, 2 * bar, reach))
            q.drawRect(QRectF(d - bar, d - bar, reach, 2 * bar))
        for k, (a, b) in enumerate(zip(steps, steps[1:], strict=False)):
            for along in ((12 if k % 2 == 0 else 28) * u, (44 if k % 2 == 0 else 60) * u):
                at = b + along
                q.drawRect(QRectF(a, at - bar, b - a, 2 * bar))
                q.drawRect(QRectF(at - bar, a, 2 * bar, b - a))
        # A rail along each screen edge from the plate to the arc.
        q.drawRect(QRectF(16 * u - bar, 30 * u, 2 * bar, reach))
        q.drawRect(QRectF(30 * u, 16 * u - bar, reach, 2 * bar))

    def gilt(q: QPainter) -> None:
        q.setBrush(Qt.NoBrush)
        q.setPen(QPen(QColor("#ffffff"), 1.3 * u))
        q.drawEllipse(QPointF(0, 0), reach - 9.5 * u, reach - 9.5 * u)
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#ffffff"))
        knot = QPolygonF([QPointF(18 * u, 9 * u), QPointF(27 * u, 18 * u), QPointF(18 * u, 27 * u), QPointF(9 * u, 18 * u)])
        q.drawPolygon(knot)
        for x, y in ((57 * u, 57 * u), (85 * u, 85 * u), (36 * u, 92 * u), (92 * u, 36 * u)):
            q.drawEllipse(QPointF(x, y), 2.2 * u, 2.2 * u)

    def paper(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#ffffff"))
        q.drawEllipse(QPointF(0, 0), reach, reach)

    jade = mask(size, size, lattice)
    gold = mask(size, size, gilt)

    def hollow(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#ffffff"))
        q.drawPolygon(QPolygonF([QPointF(18 * u, 12.5 * u), QPointF(23.5 * u, 18 * u), QPointF(18 * u, 23.5 * u), QPointF(12.5 * u, 18 * u)]))

    gold *= 1 - mask(size, size, hollow)
    return jade, gold, mask(size, size, paper)


def _corners(pre: np.ndarray, alpha: np.ndarray, width: float, height: float, u: float) -> None:
    jade, gold, paper = _lattice(u)
    size = jade.shape[0]
    h, w = alpha.shape
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32) + 0.5
    glow_at = np.clip(np.hypot(xs, ys) / (CORNER * u), 0, 1)
    for flip_x, flip_y in ((False, False), (True, False), (False, True), (True, True)):

        def turned(a: np.ndarray, flip_x: bool = flip_x, flip_y: bool = flip_y) -> np.ndarray:
            return a[::-1 if flip_y else 1, ::-1 if flip_x else 1]

        j, g, pp = turned(jade), turned(gold), turned(paper)
        x0 = w - size if flip_x else 0
        y0 = h - size if flip_y else 0
        light = turned(glow_at)
        _over(pre, alpha, rgb(MINT) + (rgb(LIME) - rgb(MINT)) * light[..., None], pp * (0.06 + 0.14 * light ** 2), y0, x0)
        lift = blur(j, 1.1 * u) * j
        _over(pre, alpha, _jade(lift * 3 * u, 1.0, lift * 0.8, 0.45, JADE_DEEP, "#6fd6a6"), j, y0, x0)
        rise = blur(g, 0.7 * u) * g
        _over(pre, alpha, _gold(rise * 2 * u, 1.0), g, y0, x0)


# Mist.


class _Mist:
    """Mint mist drifting left to right along the edges: two bands of soft noise a quarter size, slid
    along and kept to the edges (not the gap) by a picture of where mist may be, then laid on."""

    SHRINK = 4

    def __init__(self, width: float, height: float, gap: QRectF, u: float) -> None:
        s = self.SHRINK
        self.size = QRectF(0, 0, width, height)
        self.w, self.h = max(2, math.ceil(width / s)), max(2, math.ceil(height / s))
        self.layers = [(_mist_band(self.w, self.h, u / s, seed), speed * u / s, strength) for seed, speed, strength in ((5, 46, 1.0), (9, 92, 0.75))]
        xs = ((np.arange(self.w, dtype=np.float32) + 0.5) * s)[None, :]
        ys = ((np.arange(self.h, dtype=np.float32) + 0.5) * s)[:, None]
        side = np.minimum(xs, width - xs)
        near = 1 - smooth(0, 300 * u, side) * smooth(0, 250 * u, ys) * smooth(0, 190 * u, height - ys)
        where = (0.05 + 0.95 * near ** 1.2) * smooth(0, 46 * u, _rounded(xs, ys, gap, 14 * u)) * 0.5
        self.where = _straight(np.ones((self.h, self.w, 3), dtype=np.float32), where)
        self.buffer = QImage(self.w, self.h, QImage.Format_ARGB32_Premultiplied)

    def paint(self, p: QPainter, t: float, alpha: float) -> None:
        if alpha <= 0.01:
            return
        self.buffer.fill(Qt.transparent)
        q = QPainter(self.buffer)
        q.setRenderHint(QPainter.SmoothPixmapTransform)
        for image, speed, strength in self.layers:
            shift = (t * speed) % self.w
            q.setOpacity(strength)
            q.drawImage(QRectF(shift - self.w, 0, self.w, self.h), image)
            q.drawImage(QRectF(shift, 0, self.w, self.h), image)
        q.setOpacity(1.0)
        q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        q.drawImage(0, 0, self.where)
        q.end()
        p.save()
        p.setOpacity(p.opacity() * alpha)
        p.drawImage(self.size, self.buffer)
        p.restore()


def _mist_band(w: int, h: int, unit: float, seed: int) -> QImage:
    """Long soft wisps of mist, w by h pixels, that tile left to right."""
    raw = noise(max(3, (2 * w) // 3 + 3), h, 17 * unit * 4, 3, seed)
    at = np.linspace(0, raw.shape[1] - 1.001, 2 * w)
    x0 = at.astype(int)
    f = (at - x0)[None, :]
    wide = raw[:, x0] * (1 - f) + raw[:, x0 + 1] * f
    k = (np.arange(w, dtype=np.float32) / w)[None, :]
    tiled = wide[:, w:] * (1 - k) + wide[:, :w] * k
    tiled = (tiled - tiled.mean()) / max(1e-4, tiled.std()) * 0.5 + 0.5
    band = smooth(0.42, 0.85, tiled)
    color = rgb(MINT) + (rgb(MIST) - rgb(MINT)) * band[..., None]
    return _straight(color, band)


# Leaves and sprigs.


def _leaf_shape(s: np.ndarray) -> np.ndarray:
    """A bamboo leaf's half width along it (0 at its stalk, 1 at its tip), at most 1: widest a third
    of the way, tapering long to a sharp tip."""
    return np.maximum(np.clip(np.sin(np.pi * np.clip(s, 0, 1) ** 0.62), 0, 1) ** 0.85, 0.12 * (s < 0.08))


def _leaf(length: float, width: float, tone: tuple[str, str, str], scale: float, back: bool = False, bend: float = 0.4) -> tuple[QImage, QRectF]:
    """A bamboo leaf from its stalk at 0, 0 to its tip at length, 0, per pixel: folded along its
    midrib, its upper half lit and its lower in shade, fine veins along it, base to tip in tone's
    three greens; its back is paler and duller. Also where it is, around 0, 0."""
    pad = 1.5
    rect = QRectF(-pad, -width / 2 - pad - abs(bend) * width * 0.4, length + 2 * pad, width + 2 * pad + abs(bend) * width * 0.4)
    w, h = max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale))
    x = ((np.arange(w, dtype=np.float32) + 0.5) / scale + rect.left())[None, :]
    y = ((np.arange(h, dtype=np.float32) + 0.5) / scale + rect.top())[:, None]
    s = np.clip(x / length, 0, 1)
    half = width / 2 * _leaf_shape(s)
    mid = bend * width * 0.4 * s * s
    across = y - mid
    v = across / np.maximum(half, 1e-3)
    cover = np.clip((half - np.abs(across)) * scale + 0.5, 0, 1) * (x > -0.3) * (x < length)
    k = s[..., None]
    base, middle, tip = (rgb(c) for c in tone)
    color = np.where(k < 0.45, base + (middle - base) * (k / 0.45), middle + (tip - middle) * ((k - 0.45) / 0.55))
    shade = 0.84 - 0.2 * np.tanh(v * 3)
    veins = 1 - 0.06 * (0.5 + 0.5 * np.cos(v * np.pi * 9))
    rib = np.exp(-((v / 0.07) ** 2)) * (s < 0.97)
    color = color * (shade * veins)[..., None] + rgb("#efffc8") * (0.32 * rib)[..., None]
    edge = smooth(0.8, 1.0, np.abs(v))
    color = color * (1 - 0.18 * edge)[..., None] + rgb(MINT) * (0.22 * edge * (v < 0))[..., None]
    if back:
        color = color * 0.6 + rgb("#bfe0c8") * 0.4
    else:
        sheen = np.exp(-(((v + 0.38) / 0.16) ** 2)) * (0.4 + 0.6 * s)
        color = color + rgb("#f4fff0") * (0.28 * sheen)[..., None]
    return _straight(color, cover, scale), rect


class _Leaves:
    """The leaf pictures, front and back, of each tone and size class, at two pixels to the point."""

    SCALE = 2.0

    def __init__(self, u: float) -> None:
        self.u = u
        self.front = [_leaf(42 * u, 8.5 * u, tone, self.SCALE, bend=0.5) for tone in LEAVES]
        self.back = [_leaf(42 * u, 8.5 * u, tone, self.SCALE, back=True, bend=0.5) for tone in LEAVES]
        self.length = 42 * u
        # A soft round mint light, laid under a leaf the wind carries.
        side = 48
        ys, xs = np.mgrid[0:side, 0:side].astype(np.float32) + 0.5
        fall = np.exp(-(((xs - side / 2) ** 2 + (ys - side / 2) ** 2) / (side * 0.2) ** 2))
        self.light = glow(fall[..., None] * rgb(MINT) * 0.7)

    def draw(self, p: QPainter, at: QPointF, angle: float, tone: int, size: float, turn: float = 1.0) -> None:
        """A leaf with its middle at at, pointing at angle degrees, size times its own length,
        turned on its midrib by turn (1 face on, 0 edge on, below 0 its back)."""
        image, rect = (self.front if turn >= 0 else self.back)[tone % len(LEAVES)]
        p.save()
        p.translate(at)
        p.rotate(angle)
        p.scale(size, size * max(0.25, abs(turn)))
        p.drawImage(rect.translated(-self.length / 2, 0), image)
        p.restore()


class _Sprig:
    """A twig of bamboo leaves fanned from its tip, worked out once as one picture: its twig points
    along 0 degrees from its pivot."""

    def __init__(self, leaves: _Leaves, twig: float, fan: list[tuple[float, float, float, int]], scale: float = 2.0) -> None:
        u = leaves.u
        parts = []
        box = QRectF(-3 * u, -3 * u, twig + 6 * u, 6 * u)
        for along, angle, size, tone in fan:
            transform = QTransform().translate(twig * along, 0).rotate(angle).scale(size, size)
            image, rect = leaves.front[tone % len(LEAVES)]
            parts.append((transform, image, rect))
            box = box.united(transform.mapRect(rect))
        self.rect = box.adjusted(-1, -1, 1, 1)
        image = QImage(max(1, math.ceil(self.rect.width() * scale)), max(1, math.ceil(self.rect.height() * scale)), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        q = QPainter(image)
        q.setRenderHint(QPainter.Antialiasing)
        q.setRenderHint(QPainter.SmoothPixmapTransform)
        q.scale(scale, scale)
        q.translate(-self.rect.left(), -self.rect.top())
        twig_path = QPainterPath(QPointF(0, 0))
        twig_path.quadTo(QPointF(twig * 0.5, -twig * 0.06), QPointF(twig, 0))
        q.setPen(QPen(col("#27512a"), 2.2 * u, Qt.SolidLine, Qt.RoundCap))
        q.drawPath(twig_path)
        q.setPen(QPen(col("#8fca6c", 0.9), 0.8 * u, Qt.SolidLine, Qt.RoundCap))
        q.drawPath(twig_path.translated(0, -0.5 * u))
        for transform, leaf, rect in parts:
            q.save()
            q.setTransform(transform, True)
            q.drawImage(rect, leaf)
            q.restore()
        q.end()
        image.setDevicePixelRatio(scale)
        self.image = image

    def paint(self, p: QPainter, at: QPointF, angle: float, size: float = 1.0) -> None:
        if size <= 0.01:
            return
        p.save()
        p.translate(at)
        p.rotate(angle)
        p.scale(size, size)
        p.drawImage(self.rect, self.image)
        p.restore()


def _fan(rnd: random.Random, count: int, spread: float, droop: float, size: float) -> list[tuple[float, float, float, int]]:
    out = []
    for k in range(count):
        side = k / max(1, count - 1) - 0.5
        out.append((rnd.uniform(0.55, 1.0), side * spread + droop + rnd.uniform(-6, 6), size * rnd.uniform(0.78, 1.1), rnd.randrange(len(LEAVES))))
    return out


def _garland(width: float, u: float, rnd: random.Random, leaves: _Leaves) -> list[tuple[QPointF, float, _Sprig, int]]:
    """Sprigs hung along the top from the festoon's points, pointing down and leaning with the wind;
    smaller over the title."""
    out = []
    for index, at in enumerate(_festoon_points(width, u)):
        middle = abs(at.x() - width / 2) / (width / 2)
        size = 0.75 + 0.55 * clamp((middle - 0.2) / 0.4)
        sprig = _Sprig(leaves, 12 * u, _fan(rnd, 5 + index % 2, 80, 0, size))
        out.append((at, 90 + (14 if index % 2 else -14) + rnd.uniform(-8, 8), sprig, index))
    return out


def _tufts(width: float, height: float, gap: QRectF, u: float, rnd: random.Random, leaves: _Leaves) -> list[tuple[QPointF, float, _Sprig, int]]:
    """Tufts of leaves standing up from the bottom of the frame, either side of the button."""
    out = []
    left = [x * u for x in (150, 270, 385)]
    right = [width - x * u for x in (150, 270, 385)]
    for index, x in enumerate(left + right):
        if gap.left() - 60 * u < x < gap.right() + 60 * u:
            continue
        sprig = _Sprig(leaves, 4 * u, _fan(rnd, 7, 130, 0, rnd.uniform(1.0, 1.3)))
        out.append((QPointF(x, height - 18 * u), -90 + rnd.uniform(-10, 10), sprig, index))
    return out


# Bamboo.


def _internode(width: float, length: float, scale: float, tone: tuple[str, str, str], seed: int) -> tuple[QImage, QRectF]:
    """A length of bamboo stalk from its node at the bottom (the joint it turns about, at 0, 0) up to
    the next, per pixel: a lit cylinder, bright green on its lit side and olive in its shade, a sheen
    down it, fine fibres, the pale bloom bamboo has under each node, mint light caught on its far
    edge, and the node itself, a raised ring a little wider than the stalk."""
    r = width / 2
    ring = r * 1.13
    node = max(2.5, width * 0.24)
    pad = 1.0
    rect = QRectF(-ring - pad, -length - 2.0, 2 * (ring + pad), length + 2.0 + node / 2 + pad)
    w, h = max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale))
    x = ((np.arange(w, dtype=np.float32) + 0.5) / scale + rect.left())[None, :]
    y = ((np.arange(h, dtype=np.float32) + 0.5) / scale + rect.top())[:, None]
    shade, lit, sheen = (rgb(c) for c in tone)
    across = np.clip(x / r, -1, 1)
    nz = np.sqrt(1 - across * across)
    light = np.clip(across * -0.62 + nz * 0.78, 0, 1)
    fibre = noise(w, max(2, h // 14 + 2), 1.6 * scale, 2, seed)
    fibre = fibre[np.minimum(np.arange(h) // 14, fibre.shape[0] - 1)]
    body = shade + (lit - shade) * light[..., None]
    body = body * (1 + 0.14 * (fibre - 0.5))[..., None]
    body = body * (0.72 + 0.28 * nz)[..., None]
    body = body + (sheen - body) * (0.5 * np.exp(-(((across + 0.42) / 0.15) ** 2)))[..., None]
    body = body + (rgb(MINT) - body) * (0.35 * smooth(0.6, 1.0, across))[..., None]
    bloom = (1 - smooth(0, 0.18 * length, y + length)) * (0.5 + 0.5 * light)
    body = body + (rgb("#dcf2e0") - body) * (0.38 * bloom)[..., None]
    body_cover = np.clip((r - np.abs(x)) * scale + 0.5, 0, 1) * (y > -length - 2.0) * (y < node * 0.3)
    k = np.clip(y / (node / 2), -1, 1)
    reach = ring * np.sqrt(np.clip(1 - k * k, 0, 1))
    node_cover = np.clip((reach - np.abs(x)) * scale + 0.5, 0, 1) * (np.abs(y) < node / 2)
    na = np.clip(x / ring, -1, 1)
    nlight = np.clip(na * -0.62 + np.sqrt(1 - na * na) * 0.78, 0, 1)
    knot = shade + (lit - shade) * (nlight * (1 - 0.35 * k))[..., None]
    knot = knot * (1 - 0.5 * np.exp(-(((y - node * 0.18) / (node * 0.14)) ** 2)))[..., None]
    knot = knot + rgb("#f2ffd8") * (0.25 * np.exp(-(((y + node * 0.22) / (node * 0.12)) ** 2)) * nlight)[..., None]
    color = body * (1 - node_cover[..., None]) + knot * node_cover[..., None]
    return _straight(color, np.maximum(body_cover, node_cover), scale), rect


class _Stalk:
    """A bamboo stalk rising from below the bottom edge: its internodes one on another, each turned
    a little more than the one under it, so it bends with the wind; sprigs of leaves at its upper
    nodes."""

    def __init__(self, base: QPointF, lean: float, sway: float, internodes: list[tuple[float, float]], tone: int, delay: float, seed: int, sprigs: dict[int, tuple[float, _Sprig]]) -> None:
        self.base, self.lean, self.sway, self.delay, self.seed = base, lean, sway, delay, seed
        self.pieces = [(*_internode(w, length, 1.6, STALKS[tone], seed + i), length) for i, (w, length) in enumerate(internodes)]
        self.total = sum(length for _w, length in internodes)
        self.sprigs = sprigs

    def paint(self, p: QPainter, t: float, gust: float) -> None:
        rise = ease_out(win(t, self.delay, self.delay + 0.8))
        if rise <= 0:
            return
        bend = self.sway * (_gust(t - 0.12) + 0.14 * math.sin(t * 1.9 + self.seed))
        x, y = self.base.x(), self.base.y() + self.total * (1 - rise)
        n = len(self.pieces)
        joints = []
        for i, (image, rect, length) in enumerate(self.pieces):
            angle = self.lean + bend * ((i + 0.5) / n) ** 1.6
            p.save()
            p.translate(x, y)
            p.rotate(angle)
            p.drawImage(rect, image)
            p.restore()
            joints.append((QPointF(x, y), angle))
            rad = math.radians(angle)
            x += length * math.sin(rad)
            y -= length * math.cos(rad)
            if y < -80:
                break
        for i, (turn, sprig) in self.sprigs.items():
            if i < len(joints):
                at, angle = joints[i]
                flutter = 6 * math.sin(t * 3.1 + i * 1.3 + self.seed) + 8 * gust
                sprig.paint(p, at, angle - 90 + turn + flutter, ease_out(win(t, self.delay + 0.5, self.delay + 1.0)))


def _stalks(width: float, height: float, u: float, leaves: _Leaves) -> list[_Stalk]:
    """Three stalks up each side: a tall one off the top, a middle one with leaves at its top, a short
    one; those on the right stay close to the edge, where the names come near."""
    rnd = random.Random(12)

    def internodes(total: float, w: float) -> list[tuple[float, float]]:
        out, gone, k = [], 0.0, 0
        while gone < total:
            length = (70 + 46 * min(1.0, k / 3)) * u * rnd.uniform(0.92, 1.08)
            out.append((w * u * (1 - 0.18 * gone / max(total, 1)), length))
            gone += length
            k += 1
        return out

    def sprigs(count: int, nodes: int, side: int) -> dict[int, tuple[float, _Sprig]]:
        out = {}
        for k in range(count):
            node = nodes - 1 - k
            turn = (60 if (k + (side < 0)) % 2 == 0 else -60) + rnd.uniform(-12, 12)
            out[node] = (turn, _Sprig(leaves, 22 * u, _fan(rnd, 5, 70, 12 if turn > 0 else -12, 0.85)))
        return out

    out = []
    bottom = height + 10 * u
    for side, x, lean, sway, total, w, tone, delay in (
        (1, 36, 1.2, 2.4, 1000, 21, 0, 0.0),
        (1, 82, 1.8, 3.0, 560, 15, 1, 0.12),
        (1, 12, -0.8, 2.6, 430, 12, 2, 0.22),
        (-1, 26, 0.6, 2.0, 1000, 20, 0, 0.06),
        (-1, 60, 0.4, 2.8, 660, 14, 1, 0.16),
        (-1, 8, 1.0, 2.4, 400, 11, 2, 0.26),
    ):
        nodes = internodes(total * u, w)
        at = QPointF(x * u if side > 0 else width - x * u, bottom)
        lean = lean if side > 0 else -lean * 0.3
        out.append(_Stalk(at, lean, sway, nodes, tone, delay, len(out) * 17, sprigs(3 if total < 900 else 2, len(nodes), side)))
    return out


# The wind's paths.


def _path(points: list[QPointF], per: int = 10) -> tuple[list[QPointF], list[float]]:
    smooth_points = catmull(points, per)
    return smooth_points, lengths(smooth_points)


def _loop_points(width: float, height: float, u: float) -> list[QPointF]:
    """Up the left, round the fish ring, across the top over the title, round the heart and down the
    right, close to its edge where the names come near."""
    left = [(122, height / u + 40), (128, height / u - 130), (116, height / u - 280), (130, 470), (118, 330), (84, 250), (56, 160), (74, 76), (140, 40)]
    top = [(270, 84), (430, 104), (600, 70), (800, 60), (1000, 66), (None, 104, 440), (None, 80, 290)]
    right = [(None, 40, 130), (None, 100, 60), (None, 230, 40), (None, 400, 36), (None, 560, 38), (None, 700, 34), (None, height / u - 60, 50), (None, height / u + 40, 30)]
    out = []
    for point in left + top + right:
        if point[0] is None:
            out.append(QPointF(width - point[2] * u, point[1] * u))
        else:
            out.append(QPointF(point[0] * u, point[1] * u))
    return out


def _room(at: QPointF, width: float, u: float) -> float:
    """How far a leaf may stray from the wind's path here: little down the right, by the names."""
    if at.y() < 90 * u:
        return 16 * u
    if at.x() > width / 2:
        return 7 * u if at.y() > 300 * u else 14 * u
    return 22 * u


def _lane(stage: Stage, u: float) -> tuple[list[QPointF], list[float]]:
    """Across the screen just under the first row's names."""
    names = stage.names()
    row = max(box.bottom() for box in names[:6]) if len(names) >= 6 else stage.height * 0.55
    y = row + 38 * u
    width = stage.width
    points = [QPointF(-80 * u, y + 6 * u), QPointF(width * 0.3, y - 10 * u), QPointF(width * 0.62, y + 8 * u), QPointF(width + 80 * u, y - 4 * u)]
    return _path(points, 14)


def _curl(points: list[QPointF], radius: float, turn: int) -> list[QPointF]:
    """points, then a curl at their end, winding in: clockwise (turn 1) or not (-1)."""
    a, b = points[-2], points[-1]
    heading = math.atan2(b.y() - a.y(), b.x() - a.x())
    out = list(points)
    x, y = b.x(), b.y()
    steps, turns = 22, 0.85
    for k in range(1, steps + 1):
        heading += turn * 2 * math.pi * turns / steps
        r = radius * (1 - 0.7 * k / steps)
        x += r * 2 * math.pi * turns / steps * math.cos(heading)
        y += r * 2 * math.pi * turns / steps * math.sin(heading)
        out.append(QPointF(x, y))
    return out


class _Streak:
    """A streak of wind: a soft line of mint light running along a path, its head drawing on, its
    tail following, ending in a curl."""

    def __init__(self, points: list[QPointF], start: float, speed: float, length: float, thick: float, strength: float) -> None:
        self.points = points
        self.run = lengths(points)
        self.start, self.speed, self.length, self.thick, self.strength = start, speed, length, thick, strength

    def paint(self, p: QPainter, t: float, a: float) -> None:
        gone = (t - self.start) * self.speed
        total = self.run[-1]
        head = min(gone, total)
        tail = gone - self.length
        if gone <= 0 or tail >= total or a <= 0.01:
            return
        tail = max(0.0, tail)
        if head - tail < 2:
            return
        count = max(4, int((head - tail) / (6 * self.thick / 3 + 4)))
        count = min(count, 40)
        spine = []
        for k in range(count + 1):
            at, angle = point_at(self.points, self.run, tail + (head - tail) * k / count)
            spine.append((at, angle))
        fade = clamp((total - tail) / (self.length * 0.6)) * a * self.strength
        _ribbon(p, spine, self.thick * 4.5, col(MINT, 0), col(MINT, 0.34 * fade))
        _ribbon(p, spine, self.thick, col(MIST, 0), col("#ffffff", 0.8 * fade))


def _ribbon(p: QPainter, spine: list[tuple[QPointF, float]], thick: float, start: QColor, end: QColor) -> None:
    """A band along spine (points and their headings), thickest two thirds along, colored from
    start to end."""
    if len(spine) < 2:
        return
    count = len(spine) - 1
    left, right = [], []
    for k, (at, angle) in enumerate(spine):
        s = k / count
        w = thick * 0.5 * math.sin(math.pi * min(1.0, s / 0.68 * 0.5 if s < 0.68 else 0.5 + (s - 0.68) / 0.32 * 0.5)) + 0.15
        nx, ny = -math.sin(angle) * w, math.cos(angle) * w
        left.append(QPointF(at.x() + nx, at.y() + ny))
        right.append(QPointF(at.x() - nx, at.y() - ny))
    shade = QLinearGradient(spine[0][0], spine[-1][0])
    shade.setColorAt(0, start)
    shade.setColorAt(1, end)
    p.setPen(Qt.NoPen)
    p.setBrush(shade)
    p.drawPolygon(QPolygonF(left + right[::-1]))


def _streaks(width: float, height: float, gap: QRectF, u: float, lane: tuple[list[QPointF], list[float]]) -> list[_Streak]:
    def at(x: float, y: float) -> QPointF:
        return QPointF(x * u if x >= 0 else width + x * u, y * u if y >= 0 else height + y * u)

    def line(points: list[tuple[float, float]], radius: float, turn: int) -> list[QPointF]:
        return _curl(catmull([at(x, y) for x, y in points], 8), radius * u, turn)

    paths = (
        (line([(140, 62), (420, 40), (760, 60)], 24, 1), 0.85, 2.6),
        (line([(50, -80), (88, 520), (74, 330), (56, 215)], 22, 1), 1.0, 2.2),
        (line([(-120, 44), (-44, 200), (-36, 420), (-40, 620), (-48, -100)], 18, 1), 1.2, 2.0),
        (line([(600, 26), (900, 46), (1200, 28), (-330, 46)], 26, 1), 1.45, 2.4),
        (line([(36, -40), (200, -60), (400, -46)], 18, -1), 1.6, 1.6),
        (line([(-36, -40), (-200, -60), (-400, -46)], 18, 1), 1.9, 1.6),
        (line([(40, 300), (36, 130), (110, 36), (270, 28)], 22, 1), 2.1, 2.2),
        (line([(-330, 36), (-200, 22), (-80, 70), (-50, 210)], 20, 1), 2.35, 2.2),
        (line([(200, 20), (700, 38), (1100, 22), (-180, 40)], 22, 1), 2.8, 2.0),
        (line([(46, -60), (92, 560), (70, 380), (48, 250)], 20, 1), 3.05, 2.0),
        (line([(-60, 60), (-38, 300), (-40, 560), (-46, -110)], 16, 1), 3.3, 1.8),
        (line([(300, 50), (650, 30), (1000, 50), (-500, 30)], 24, 1), 3.55, 2.2),
    )
    out = []
    # Each blows twice, the second time a little in from the first.
    for points, start, thick in paths:
        if any(gap.adjusted(-20 * u, -20 * u, 20 * u, 0).contains(point) for point in points):
            continue
        out.append(_Streak(points, start, 760 * u, 320 * u, thick * 1.4 * u, 1.0))
        if start + 1.25 < 4.2:
            inward = [QPointF(point.x() + (10 * u if point.x() < width / 2 else -10 * u), point.y() + 12 * u) for point in points]
            out.append(_Streak(inward, start + 1.25, 820 * u, 280 * u, thick * 1.1 * u, 0.8))
    crossing = list(lane[0])
    out.append(_Streak(crossing, 2.05, 1500 * u, 380 * u, 1.6 * u, 0.55))
    return out


def _shine_route(width: float, height: float, gap: QRectF, u: float) -> tuple[list[QPointF], list[float]]:
    """The frame's gold line, from the knob left of the button round to the one right of it."""
    inset = EDGE * u + BAR * u + 3.6 * u
    path = QPainterPath()
    path.addRoundedRect(QRectF(inset, inset, width - 2 * inset, height - 2 * inset), (ROUND - BAR - 3.6) * u, (ROUND - BAR - 3.6) * u)
    points = [QPointF(point) for point in path.toSubpathPolygons()[0]]
    dense = []
    for a, b in zip(points, points[1:], strict=False):
        steps = max(1, int(math.dist((a.x(), a.y()), (b.x(), b.y())) / (20 * u)))
        dense += [QPointF(a.x() + (b.x() - a.x()) * k / steps, a.y() + (b.y() - a.y()) * k / steps) for k in range(steps)]
    bottom = height - inset - 2
    # Start right of the button, go round, end left of it.
    start = min(range(len(dense)), key=lambda i: math.hypot(dense[i].x() - gap.right() - 20 * u, dense[i].y() - bottom))
    dense = dense[start:] + dense[:start]
    end = min(range(len(dense)), key=lambda i: math.hypot(dense[i].x() - gap.left() + 20 * u, dense[i].y() - bottom))
    dense = dense[: end + 1]
    return dense, lengths(dense)


def _shine(p: QPainter, t: float, route: tuple[list[QPointF], list[float]], u: float, a: float) -> None:
    """Two glints of light running along the gold line."""
    points, run = route
    if a <= 0.01 or len(points) < 2:
        return
    for offset in (0.0, 0.5):
        k = (t * 0.11 + offset) % 1.0
        at, _ = point_at(points, run, k * run[-1])
        twinkle = 0.65 + 0.35 * math.sin(t * 4 + offset * 7)
        soft_dot(p, at.x(), at.y(), 16 * u, "#fff6c8", 0.5 * a * twinkle)
        star(p, at.x(), at.y(), 9 * u * twinkle, "#fffdf0", 0.95 * a, 0.12)


def _along(loop: tuple[list[QPointF], list[float]], s: float, stray: float, stage: Stage) -> tuple[QPointF, float]:
    points, run = loop
    at, angle = point_at(points, run, s)
    room = _room(at, stage.width, stage.unit()) * stray
    return QPointF(at.x() - math.sin(angle) * room, at.y() + math.cos(angle) * room), angle


def _flyers(p: QPainter, t: float, flyers: list[tuple], loop: tuple, travel: np.ndarray, leaves: _Leaves, stage: Stage, a: float) -> None:
    """Leaves carried round the frame: tumbling, fluttering, faster in the gusts."""
    if a <= 0.01:
        return
    u = stage.unit()
    total = loop[1][-1]
    carried = _carried(travel, t) * u
    for s0, stray, speed, tone, phase, size, born in flyers:
        k = win(t, born, born + 0.35)
        if k <= 0:
            continue
        s = (s0 + (carried - _carried(travel, born) * u) * speed) % total
        ends = clamp(s / (60 * u)) * clamp((total - s) / (80 * u))
        at, angle = _along(loop, s, stray * math.sin(t * 0.9 + phase), stage)
        flutter = 40 * math.sin(t * 5.2 * speed + phase) + 20 * math.sin(t * 2.3 + phase * 2)
        turn = math.cos(t * 6.4 * speed + phase)
        p.setOpacity(a * ease_out(k) * ends)
        # Lit by the wind that carries it: a soft mint light under it, so it reads apart from the bamboo.
        r = 34 * u * size
        p.drawImage(QRectF(at.x() - r, at.y() - r, 2 * r, 2 * r), leaves.light)
        leaves.draw(p, at, math.degrees(angle) + flutter, (1, 2)[tone % 2], size * (0.6 + 0.4 * ease_out(k)), turn)
    p.setOpacity(a)


def _crossers(p: QPainter, t: float, crossers: list[tuple[float, float]], lane: tuple, leaves: _Leaves, u: float, a: float) -> None:
    """A few leaves blown fast across the screen, under the first row's names."""
    points, run = lane
    for index, (start, size) in enumerate(crossers):
        gone = (t - start) * 1150 * u
        if gone <= 0 or gone >= run[-1]:
            continue
        at, angle = point_at(points, run, gone)
        p.setOpacity(a * 0.9)
        turn = math.cos(t * 9 + index)
        leaves.draw(p, at, math.degrees(angle) + 30 * math.sin(t * 7 + index), index, 0.75 * size, turn)
    p.setOpacity(a)


def _motes(p: QPainter, t: float, motes: list[tuple], loop: tuple, travel: np.ndarray, stage: Stage, a: float) -> None:
    """Specks of mint light drifting round with the leaves."""
    if a <= 0.01:
        return
    u = stage.unit()
    total = loop[1][-1]
    carried = _carried(travel, t) * u
    for s0, stray, speed, r, phase in motes:
        s = (s0 + carried * speed * 1.2) % total
        at, _ = _along(loop, s, stray, stage)
        twinkle = 0.5 + 0.5 * math.sin(t * 3.3 + phase)
        soft_dot(p, at.x(), at.y(), r * 3, MINT, 0.4 * a * twinkle)
        if twinkle > 0.8:
            star(p, at.x(), at.y(), r * 2.2 * twinkle, "#ffffff", a * (twinkle - 0.8) * 4, 0.14)


# The two in the top corners: the fish ring and the heart of wind.


class _Heroes:
    def __init__(self, fish: QPointF, heart: QPointF, u: float, leaves: _Leaves) -> None:
        self.fish, self.heart, self.u, self.leaves = fish, heart, u, leaves
        self.size = 165 * u
        self.rings: dict[int, QImage] = {}
        self.glows: dict[int, QImage] = {}

    def paint(self, p: QPainter, t: float, gust: float) -> None:
        # Both worked out on the first frame, while there is nothing yet to see, so none waits for them.
        ring, heart = self._pictures(p)
        a = 1 - ease_in(win(t, 4.2, 5.0))
        if a <= 0:
            return
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        self._fish(p, t, a, ring)
        self._heart(p, t, a, gust, heart)
        p.restore()

    def _pictures(self, p: QPainter) -> tuple[QImage, QImage]:
        scale = _sharpness(p)
        px = max(16, math.ceil(self.size * scale / 8) * 8)
        if px not in self.rings:
            self.rings[px] = _fish_ring(px)
        key = max(16, math.ceil(150 * self.u * scale / 16) * 16)
        if key not in self.glows:
            self.glows[key] = _heart_glow(key)
        return self.rings[px], self.glows[key]

    def _fish(self, p: QPainter, t: float, a: float, image: QImage) -> None:
        u = self.u
        come = ease_out(win(t, 0.3, 1.0))
        if come <= 0:
            return
        c = QPointF(self.fish.x(), self.fish.y() + 3 * u * math.sin(t * 1.6))
        a *= come
        spin = 16 * t + 70 * ease_in_out(win(t, 0.8, 3.8))
        whirl = t * 1.2 + 3.0 * ease_in_out(win(t, 0.8, 3.0))
        halo = QRadialGradient(c, 120 * u)
        halo.setColorAt(0, col("#d9f27c", 0.34 * a))
        halo.setColorAt(0.45, col("#3fb488", 0.2 * a))
        halo.setColorAt(1, col("#3fb488", 0))
        p.setPen(Qt.NoPen)
        p.setBrush(halo)
        p.drawEllipse(c, 120 * u, 120 * u)
        runs = _swirl(c, whirl, u)
        _wheel(p, runs, u, a * ease_out(win(t, 0.6, 1.3)), front=False)
        size = self.size * (0.7 + 0.3 * come)
        p.save()
        p.setOpacity(a)
        p.translate(c)
        p.rotate(spin)
        p.drawImage(QRectF(-size / 2, -size / 2, size, size), image)
        p.restore()
        _wheel(p, runs, u, a * ease_out(win(t, 0.6, 1.3)), front=True)
        for k in range(6):
            angle = whirl * (1.1 + 0.1 * k) + k * 1.05
            r = (78 + 16 * math.sin(k * 2.1)) * u
            x, y = c.x() + math.cos(angle) * r, c.y() + math.sin(angle) * r * 0.55
            twinkle = max(0.0, math.sin(t * 3.4 + k * 1.9))
            soft_dot(p, x, y, 10 * u, LIME, 0.45 * a * twinkle)
            star(p, x, y, (4 + 8 * twinkle) * u, "#fffbe6", a * (0.3 + 0.7 * twinkle), 0.12)

    def _heart(self, p: QPainter, t: float, a: float, gust: float, light: QImage) -> None:
        u = self.u
        form = ease_out(win(t, 0.9, 1.9))
        if form <= 0:
            return
        breathe = 1 + 0.045 * math.sin(2 * math.pi * (t - 1.9) / 1.5) * win(t, 1.6, 2.2)
        c = self.heart
        size = 150 * u * breathe
        glow_size = size * 1.6
        p.save()
        p.setOpacity(a * form * (0.75 + 0.25 * math.sin(t * 2.4)))
        p.drawImage(QRectF(c.x() - glow_size / 2, c.y() - glow_size / 2 + 4 * u, glow_size, glow_size), light)
        p.restore()
        for scale, phase, speed, thick, tone in ((1.0, 0.0, 0.32, 3.2, MIST), (0.86, 0.33, 0.27, 2.4, LIME), (1.1, 0.62, 0.36, 2.0, MINT), (0.72, 0.15, 0.3, 1.8, MIST)):
            reach = 0.62 * form
            head = phase + speed * t
            count = 22
            spine = []
            for k in range(count + 1):
                turn = head - reach + reach * k / count
                at = _heart_at(c, size * scale, turn)
                ahead = _heart_at(c, size * scale, turn + 0.004)
                spine.append((at, math.atan2(ahead.y() - at.y(), ahead.x() - at.x())))
            _ribbon(p, spine, thick * 3.4 * u, col(tone, 0), col(tone, 0.2 * a))
            _ribbon(p, spine, thick * u, col(tone, 0), col("#ffffff" if tone == MIST else tone, 0.9 * a))
        for k in range(12):
            turn = k / 12 + t * 0.09
            on = _heart_at(c, size * 1.04, turn)
            ahead = _heart_at(c, size * 1.04, turn + 0.01)
            angle = math.degrees(math.atan2(ahead.y() - on.y(), ahead.x() - on.x()))
            come = ease_in_out(win(t, 0.9 + 0.07 * k, 1.7 + 0.07 * k))
            if come <= 0:
                continue
            start = QPointF(c.x() - (260 + 30 * k) * u, c.y() - (90 - 14 * k) * u)
            at = QPointF(start.x() + (on.x() - start.x()) * come, start.y() + (on.y() - start.y()) * come)
            p.save()
            p.setOpacity(a * min(1.0, come * 2))
            self.leaves.draw(p, at, angle + 25 * math.sin(t * 4 + k) + 12 * gust, k, 0.78, math.cos(t * 3 + k * 0.8))
            p.restore()
        for k in range(4):
            twinkle = max(0.0, math.sin(t * 2.8 + k * 1.7))
            at = _heart_at(c, size * 0.6, k / 4 + 0.12)
            star(p, at.x(), at.y(), (3 + 8 * twinkle) * u, "#ffffff", a * form * twinkle, 0.12)


def _heart_at(c: QPointF, size: float, turn: float) -> QPointF:
    """The point a turn round a heart size wide (0 at its top cleft, clockwise)."""
    a = turn * 2 * math.pi
    x = 16 * math.sin(a) ** 3
    y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
    return QPointF(c.x() + x * size / 34, c.y() - (y - 2.5) * size / 34)


def _heart_glow(px: int) -> QImage:
    """Soft jade light in the shape of a heart, px pixels for a heart px wide (the picture 1.6 times
    it)."""
    side = math.ceil(px * 1.6)

    def draw(q: QPainter) -> None:
        points = [_heart_at(QPointF(side / 2, side / 2), px, k / 90) for k in range(90)]
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#ffffff"))
        q.drawPolygon(QPolygonF(points))

    shape = mask(side, side, draw)
    light = blur(shape, px * 0.08) * 0.55 + blur(shape, px * 0.2) * 0.45
    return glow(light[..., None] * rgb("#5fdca6") * 0.9 + (light ** 3)[..., None] * rgb("#d9f27c") * 0.5)


def _swirl(c: QPointF, whirl: float, u: float) -> list[tuple[bool, list, float, float, float, str]]:
    """Ribbons of yellow-green and jade wind wheeling round the fish ring on tilted rings, in runs:
    (before the ring or behind it, the run's points and headings, how far along the ribbon it starts
    and ends, its thickness, its color)."""
    out = []
    count, sweep = 26, 3.4
    for tilt, ra, rb, speed, phase, thick, tone in (
        (-24, 108, 42, 1.0, 0.0, 4.6, LIME),
        (32, 100, 36, 1.25, 2.1, 3.6, MINT),
        (82, 94, 32, 0.9, 4.0, 3.0, "#8fe8a0"),
    ):
        start = phase + whirl * speed
        cos_t, sin_t = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
        phis = [start + sweep * k / count for k in range(count + 1)]
        pts = []
        for phi in phis:
            ex, ey = ra * u * math.cos(phi), rb * u * math.sin(phi)
            pts.append(QPointF(c.x() + ex * cos_t - ey * sin_t, c.y() + ex * sin_t + ey * cos_t))
        spine = [(pts[k], math.atan2(pts[min(k + 1, count)].y() - pts[max(k - 1, 0)].y(), pts[min(k + 1, count)].x() - pts[max(k - 1, 0)].x())) for k in range(count + 1)]
        # Before the ring where the orbit comes toward the eye.
        k0 = 0
        for k in range(1, count + 2):
            if k == count + 1 or (math.sin(phis[k]) > 0) != (math.sin(phis[k0]) > 0):
                if k - 1 - k0 >= 2:
                    out.append((math.sin(phis[k0]) > 0, spine[k0:k], k0 / count, (k - 1) / count, thick, tone))
                k0 = k
    return out


def _wheel(p: QPainter, runs: list[tuple], u: float, a: float, front: bool) -> None:
    """The swirl's runs behind the ring, or before it."""
    if a <= 0.01:
        return
    for near, part, s0, s1, thick, tone in runs:
        if near == front:
            _ribbon(p, part, thick * 3.4 * u, col(tone, 0.3 * a * s0), col(tone, 0.32 * a * s1))
            _ribbon(p, part, thick * u, col(tone, 0.9 * a * s0), mix(tone, "#ffffff", 0.35, 0.95 * a * s1))


def _sharpness(p: QPainter) -> float:
    """Pixels per point where p draws: its screen's and its own scaling."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return max(0.5, round(ratio * math.hypot(p.transform().m11(), p.transform().m12()), 2))


def _fish_w(ub: np.ndarray, hw: float) -> np.ndarray:
    """A fish's half width along its body, 0 at its tail's root to 1 at its nose."""
    nose = hw * np.sqrt(np.clip(1 - ((ub - 0.62) / 0.38) ** 2, 0, 1))
    body = hw * (0.3 + 0.7 * np.sin(np.pi / 2 * np.clip(ub / 0.62, 0, 1)) ** 1.1)
    return np.where(ub > 0.62, nose, body) * (ub >= 0)


def _fish_ring(px: int) -> QImage:
    """The 蛇眉铜鱼: three bronze fish curled nose to tail into a ring, px pixels across, per pixel.
    Each has a rounded body in fine scales, a forked tail, a fin along its back, a gill and a bead of
    an eye, and over the eye a brow like a little snake, its head at the front and its body trailing
    back in waves; the bronze is lit from the upper left and green with verdigris in its hollows."""
    c = px / 2
    yy, xx = np.mgrid[0:px, 0:px].astype(np.float32) + 0.5
    dx, dy = xx - c, yy - c
    r = np.hypot(dx, dy)
    th = np.arctan2(dy, dx)
    radius, hw = px * 0.28, px * 0.125
    span = 2 * np.pi / 3 * 0.99
    height = np.zeros((px, px), dtype=np.float32)
    cover = np.zeros((px, px), dtype=np.float32)
    eyes = np.zeros((px, px), dtype=np.float32)
    brows = np.zeros((px, px), dtype=np.float32)
    off = r - radius
    for k in range(3):
        start = k * 2 * np.pi / 3 + 0.3
        s = np.mod(th - start, 2 * np.pi) / span
        on = s <= 1
        ub = (s - 0.2) / 0.8
        w = _fish_w(ub, hw)
        v = off / np.maximum(w, 1e-3)
        body = np.clip(w - np.abs(off) + 0.5, 0, 1) * on * (ub >= 0)
        lift = np.sqrt(np.clip(1 - v * v, 0, 1)) * w * 0.9
        # Scales: rows of little roofs along the body, each row half a scale on from the next.
        row = np.floor((v + 1) * 2.5)
        tile = np.mod(ub * 17 + 0.5 * row, 1.0)
        lift -= 0.1 * w * smooth(0.0, 1.0, tile) * (ub > 0.06) * (ub < 0.74) * (1 - np.abs(v) ** 4)
        lift -= 0.16 * w * np.exp(-(((ub - 0.77) / 0.016) ** 2)) * (np.abs(v) < 0.95)
        # The tail, forked, with rays.
        fs = np.clip((0.22 - s) / 0.22, 0, 1)
        fin_w = hw * (0.32 + 0.95 * fs ** 0.8)
        notch = fin_w * 0.55 * smooth(0.5, 1.0, fs)
        tail = (s <= 0.22) * on * np.clip(fin_w - np.abs(off) + 0.5, 0, 1) * np.clip(np.abs(off) - notch + 0.5, 0, 1)
        tail_lift = 0.24 * hw * np.sqrt(np.clip(1 - np.abs(off) / fin_w, 0, 1)) * (0.72 + 0.28 * np.cos(off / fin_w * 9 * np.pi))
        # A fin along its back, on the ring's outside.
        dk = np.clip((ub - 0.26) / 0.34, 0, 1)
        dorsal_h = hw * 0.55 * np.sin(np.pi * dk) * (ub > 0.26) * (ub < 0.6)
        dorsal = on * (off > 0) * np.clip(w + dorsal_h - off + 0.5, 0, 1) * (dorsal_h > 0.5)
        dorsal_lift = 0.2 * hw * np.clip(1 - (off - w) / np.maximum(dorsal_h, 1e-3), 0, 1) * (0.7 + 0.3 * np.cos(ub * 90))
        # Its eye, near its nose on the outside.
        eye_s = 0.2 + 0.8 * 0.88
        eye_angle = start + eye_s * span
        eye_r = radius + 0.3 * float(_fish_w(np.float32(0.88), hw))
        ex, ey = c + eye_r * math.cos(eye_angle), c + eye_r * math.sin(eye_angle)
        de = np.hypot(xx - ex, yy - ey)
        er = hw * 0.2
        eye = np.sqrt(np.clip(1 - (de / er) ** 2, 0, 1))
        lift = lift + eye * er * 0.9
        eyes = np.maximum(eyes, np.clip(er * 0.75 - de + 0.5, 0, 1) * on)
        # The snake brow over it.
        brow = np.zeros((px, px), dtype=np.float32)
        for q in np.linspace(0, 1, 34):
            ubq = 0.99 - 0.36 * q
            vq = 0.62 + 0.16 * math.sin(q * 3 * math.pi) * q - 0.08 * (1 - q) ** 4
            wq = hw * (0.13 * (1 - 0.6 * q) + 0.09 * max(0.0, 1 - q / 0.14))
            ang = start + (0.2 + 0.8 * ubq) * span
            rad = radius + vq * float(_fish_w(np.float32(ubq), hw))
            bx, by = c + rad * math.cos(ang), c + rad * math.sin(ang)
            d = np.hypot(xx - bx, yy - by)
            brow = np.maximum(brow, np.sqrt(np.clip(1 - (d / wq) ** 2, 0, 1)) * wq * 2.2)
            brows = np.maximum(brows, np.clip(wq - d + 0.5, 0, 1))
        lift = np.maximum(lift, (lift + brow * 0.8) * (brow > 0))
        parts = np.stack([body, tail, dorsal, np.clip(brow * 3, 0, 1) * on])
        fish = parts.max(axis=0)
        fish_lift = np.maximum.reduce([lift * body, tail_lift * tail * (body < 0.5), dorsal_lift * dorsal * (body < 0.5), brow * 1.2])
        height = np.maximum(height, fish_lift)
        cover = np.maximum(cover, fish)
    height = blur(height, max(0.6, px / 240))
    diffuse, spec, sky = _lit(height, 1.2)
    tone = np.clip(0.1 + 0.42 * diffuse + 0.3 * sky + 0.35 * spec ** 8, 0, 1)
    color = _ramp(BRONZE_RAMP, tone) + (spec ** 22 * 0.4)[..., None]
    hollow = np.clip((blur(height, px / 60) - height) / (hw * 0.06), 0, 1)
    rust = noise(px, px, px / 9, 3, 4)
    patina = np.clip(hollow * 1.1 + smooth(0.42, 0.72, rust) * 0.75, 0, 1) * (0.55 + 0.45 * (1 - diffuse))
    green = rgb(PATINA[0]) + (rgb(PATINA[1]) - rgb(PATINA[0])) * (rust * diffuse)[..., None]
    color = color + (green - color) * (patina * 0.85)[..., None]
    # The brows are rubbed bright, as raised bronze is, in a dark groove.
    groove = np.clip(blur(brows, max(0.7, px / 200)) * 1.8 - brows, 0, 1)
    color = color * (1 - 0.6 * groove)[..., None]
    shine = _ramp(BRONZE_RAMP, np.clip(0.45 + 0.5 * diffuse + 0.3 * spec ** 6, 0, 1))
    color = color + (shine - color) * (brows * 0.9)[..., None]
    color = color * (1 - 0.65 * eyes)[..., None] + (spec ** 30 * eyes * 0.9)[..., None]
    shadow = np.roll(np.roll(blur(cover, px / 70), round(px / 70), axis=0), round(px / 110), axis=1) * 0.45
    total = cover + shadow * (1 - cover)
    pre = color * cover[..., None] + rgb("#03241a") * (shadow * (1 - cover))[..., None]
    return _picture(pre, total)


# The marks: a jade card framed in bamboo, a jade ring with leaves blown round it, the fish ring.

_MARKS: dict[tuple, object] = {}


def _mark(key: tuple, make_it):  # noqa: ANN001, ANN202
    if key not in _MARKS:
        if len(_MARKS) > 32:
            _MARKS.clear()
        _MARKS[key] = make_it()
    return _MARKS[key]


def _mark_leaves() -> _Leaves:
    return _mark(("leaves",), lambda: _Leaves(0.45))


def _cane(length: float, thick: float, scale: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """A thin bamboo cane lying along x, per pixel: its color and cover, length by thick points."""
    w, h = max(1, math.ceil(length * scale)), max(1, math.ceil(thick * scale))
    x = ((np.arange(w, dtype=np.float32) + 0.5) / scale)[None, :]
    y = ((np.arange(h, dtype=np.float32) + 0.5) / scale - thick / 2)[:, None]
    across = np.clip(y / (thick / 2), -1, 1)
    nz = np.sqrt(1 - across * across)
    light = np.clip(across * -0.7 + nz * 0.72, 0, 1)
    shade, lit, sheen = (rgb(c) for c in STALKS[seed % len(STALKS)])
    color = shade + (lit - shade) * light[..., None]
    color = color + (sheen - color) * (0.5 * np.exp(-(((across + 0.45) / 0.2) ** 2)))[..., None]
    step = 24.0
    nodes = np.exp(-(((np.mod(x + seed * 7, step) - step / 2) / 0.6) ** 2))
    color = color * (1 - 0.45 * nodes)[..., None]
    cover = np.clip((thick / 2 - np.abs(y)) * scale + 0.5, 0, 1) * np.ones_like(x)
    return color, cover


def _card_art(rect: QRectF, scale: float) -> QImage:
    """The card: pale jade, clouded and softly beveled, framed by four bamboo canes that cross at its
    corners, lashed there in gold."""
    w, h = max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale))
    body = QRectF(4, CARD_TOP + 4, rect.width() - 8, rect.height() - CARD_TOP - 8)
    xs = ((np.arange(w, dtype=np.float32) + 0.5) / scale)[None, :]
    ys = ((np.arange(h, dtype=np.float32) + 0.5) / scale)[:, None]
    d = _rounded(xs, ys, body, 6)
    cover = np.clip(-d * scale + 0.5, 0, 1)
    bevel = np.clip(-d / 5, 0, 1)
    cloud = noise(w, h, 14 * scale, 3, 3)
    tone = (ys - body.top()) / max(body.height(), 1)
    base = rgb(LOOK["card"][0]) + (rgb(LOOK["card"][1]) - rgb(LOOK["card"][0])) * np.clip(tone, 0, 1)[..., None]
    diffuse, spec, sky = _lit(np.sqrt(bevel) * 4 * scale, 1.0)
    color = base * (0.86 + 0.16 * diffuse + 0.05 * (cloud - 0.5))[..., None] + (spec ** 20 * 0.4)[..., None]
    pre = color * cover[..., None]
    alpha = cover * 0.97
    thick = 3.6
    for seed, (x0, y0, length, vertical) in enumerate((
        (body.left() + thick / 2, body.top() - 3, body.height() + 6, True),
        (body.right() - thick / 2, body.top() - 3, body.height() + 6, True),
        (body.left() - 3, body.top() + thick / 2, body.width() + 6, False),
        (body.left() - 3, body.bottom() - thick / 2, body.width() + 6, False),
    )):
        cane, cane_cover = _cane(length, thick, scale, seed)
        if vertical:
            cane, cane_cover = np.transpose(cane, (1, 0, 2))[:, ::-1], cane_cover.T[:, ::-1]
            _over(pre, alpha, cane, cane_cover, round(y0 * scale), round((x0 - thick / 2) * scale))
        else:
            _over(pre, alpha, cane, cane_cover, round((y0 - thick / 2) * scale), round(x0 * scale))
    knots = np.zeros((h, w), dtype=np.float32)
    for x, y in ((body.left() + thick / 2, body.top() + thick / 2), (body.right() - thick / 2, body.top() + thick / 2), (body.left() + thick / 2, body.bottom() - thick / 2), (body.right() - thick / 2, body.bottom() - thick / 2)):
        knots = np.maximum(knots, np.clip((2.6 - np.hypot(xs - x, ys - y)) * scale + 0.5, 0, 1))
    _over(pre, alpha, _gold(blur(knots, scale) * 2 * scale, 1.0), knots)
    return _picture(pre, alpha, scale)


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """The jade card in its bamboo frame, a sprig of leaves over its top left corner, rustling."""
    scale = max(2.0, _sharpness(p))
    image = _mark(("card", round(rect.width()), round(rect.height()), scale), lambda: _card_art(rect, scale))
    p.drawImage(rect, image)
    sprig = _mark(("card-sprig",), lambda: _Sprig(_mark_leaves(), 3.0, [(0.9, -40, 0.85, 0), (1.0, -8, 1.0, 2), (0.8, 24, 0.8, 1)], 4.0))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    sprig.paint(p, QPointF(rect.left() + 9, rect.top() + CARD_TOP + 6), -100 + 8 * math.sin(t * 1.9) + 4 * math.sin(t * 4.3), 1.35)


def lead(size: float, index: int) -> QPixmap:
    """A bamboo leaf before each name, jade and spring green in turn."""
    ratio = 3.0
    pixmap = QPixmap(max(1, round(size * ratio)), max(1, round(size * ratio)))
    pixmap.fill(Qt.transparent)
    pixmap.setDevicePixelRatio(ratio)
    image, rect = _leaf(size * 0.95, size * 0.28, LEAVES[(0, 2)[index % 2]], ratio * 1.5, bend=0.6)
    q = QPainter(pixmap)
    q.setRenderHint(QPainter.Antialiasing)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.translate(size * 0.1, size * 0.78)
    q.rotate(-38)
    q.drawImage(rect, image)
    q.end()
    return pixmap


def _ring_art(window: QRectF, cover: QRectF, scale: float) -> tuple[QImage, QImage, list[QPointF], list[float]]:
    """The jade band round the button, a fine gold line inside it, its mint glow, and the points
    round it for the leaves."""
    w, h = max(1, math.ceil(window.width() * scale)), max(1, math.ceil(window.height() * scale))
    radius = cover.height() * 0.3
    band = cover.adjusted(-1.5, -1.5, 1.5, 1.5)
    xs = ((np.arange(w, dtype=np.float32) + 0.5) / scale + window.left())[None, :]
    ys = ((np.arange(h, dtype=np.float32) + 0.5) / scale + window.top())[:, None]
    d = _rounded(xs, ys, band, radius)
    half = 2.4
    v = np.clip(d / half, -1, 1)
    cover_px = np.clip((half - np.abs(d)) * scale + 0.5, 0, 1)
    shape = np.sqrt(np.clip(1 - v * v, 0, 1))
    jade = _jade(shape * half * scale, 1.0, shape, 0.5)
    pre = jade * cover_px[..., None]
    alpha = cover_px.copy()
    line = d + half + 1.6
    gold = np.clip((0.5 - np.abs(line)) * scale + 0.5, 0, 1)
    _over(pre, alpha, rgb(GOLD), gold * 0.95)
    light = np.exp(-np.maximum(np.abs(d) - half, 0) / 3.5) * (1 - cover_px)
    halo = glow(light[..., None] * rgb("#5fe0a8") * 0.85)
    route = QPainterPath()
    route.addRoundedRect(band, radius, radius)
    points = [QPointF(point) for point in route.toSubpathPolygons()[0]]
    image = _picture(pre, alpha, scale)
    halo.setDevicePixelRatio(1.0)
    return image, halo, points, lengths(points)


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A jade band round the button breathing mint light, small leaves blown round it and a wisp of
    wind running after them."""
    scale = max(1.0, _sharpness(p))
    window = cover.adjusted(-9, -9, 9, 9)
    key = ("ring", round(cover.width(), 1), round(cover.height(), 1), scale)
    image, halo, points, run = _mark(key, lambda: _ring_art(window, cover, scale))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setOpacity(0.7 + 0.3 * math.sin(t * 2.0))
    p.drawImage(window, halo)
    p.setOpacity(1.0)
    p.drawImage(window, image)
    leaves = _mark_leaves()
    total = run[-1]
    head = (t * 95) % total
    spine = [point_at(points, run, (head - 70 + 70 * k / 14) % total) for k in range(15)]
    if all(math.dist((a.x(), a.y()), (b.x(), b.y())) < 20 for (a, _), (b, _) in zip(spine, spine[1:], strict=False)):
        _ribbon(p, spine, 2.2, col(MIST, 0), col("#ffffff", 0.9))
    for k in range(4):
        at, angle = point_at(points, run, (t * 95 + k * total / 4 + 20) % total)
        # Just outside the band, on the dark of the game, in the light greens.
        out = 4.5 + 1.5 * math.sin(t * 3 + k)
        at = QPointF(at.x() + math.sin(angle) * out, at.y() - math.cos(angle) * out)
        leaves.draw(p, at, math.degrees(angle) + 30 * math.sin(t * 5 + k), (1, 2)[k % 2], 1.15, math.cos(t * 4 + k))


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """The three-fish ring, turning slowly in jade light, a wisp of wind and a sparkle by it."""
    scale = _sharpness(p)
    side = box.width() * 0.92
    px = max(16, math.ceil(side * scale / 4) * 4)
    image = _mark(("badge", px), lambda: _fish_ring(px))
    c = box.center()
    halo = QRadialGradient(c, box.width() * 0.62)
    halo.setColorAt(0, col(LIME, 0.45))
    halo.setColorAt(0.5, col(JADE, 0.28))
    halo.setColorAt(1, col(JADE, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(halo)
    p.drawEllipse(c, box.width() * 0.62, box.width() * 0.62)
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.translate(c)
    p.rotate(t * 24)
    p.drawImage(QRectF(-side / 2, -side / 2, side, side), image)
    p.restore()
    twinkle = 0.5 + 0.5 * math.sin(t * 3.1)
    star(p, box.right() - box.width() * 0.12, box.top() + box.width() * 0.14, box.width() * 0.1 * (0.5 + 0.5 * twinkle), "#fffbe6", 0.6 + 0.4 * twinkle, 0.13)
