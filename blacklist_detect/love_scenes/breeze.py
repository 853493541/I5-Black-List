"""清风徐来 Breeze: green silk on the wind, 古风 仙侠, after the 青绿山水 of 千里江山图.

Mountains breathe in along the bottom, painted per pixel as 青绿山水: ink ridge lines, 石青 and 石绿
washes over their tops that pale into rice paper and mist at their feet, 披麻 texture strokes down their
flanks, a touch of gold leaf on the peaks, the paper's grain in all of it; mist drifts between the
ridges and rises with the wind. Then the wind shows as silk: two long jade ribbons, trimmed with a gold
thread, ride in from the left across the top, braided round each other, and a 石青 one low over the
mountains; they ripple and twist as cloth does (sheen where a fold turns to the light, deeper color
in the folds, see-through where the silk is thin), bamboo leaves and pear petals riding with them and
a white crane gliding away in the distance. The two jade ribbons loop into a loose heart at the top
right, gold motes left where they passed; 清风徐来 is brushed stroke by stroke in 楷体 down the top
left on a breath of rice-paper mist and stamped with a red seal, as a gust carries the silk away. The
mist settles and it all fades.

The 嘉宾 marks wear it: a rice-paper scroll mounted in jade silk with a small red seal, the names in
楷体 each after a bamboo leaf; a jade silk ribbon circling the button, twisting as it flutters; and for
a badge a jade 玉佩 on a silk cord, a tassel swaying under it.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QFont, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QTransform

from blacklist_detect.love_scenes.draw import clamp, ease_in, ease_in_out, ease_out, win
from blacklist_detect.love_scenes.light import blur, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from collections.abc import Callable

    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# Soft paint throughout: drawn at one pixel per point and scaled up on a sharper screen.
MAX_RATIO = 1.0
# Her greens, as the mineral paints of 青绿山水 have them: 石绿 malachite, 石青 blue-green and jade;
# ink, rice paper, gold leaf and one seal red.
MALACHITE = "#3e9e7a"
GREEN = "#59b38f"
PALE = "#8fd1b0"
AZURE = "#2a6f8f"
JADE = "#2f8f6b"
INK = "#1d2b28"
PAPER = "#f3ecd8"
GOLD = "#d9b45a"
SEAL = "#c0392b"
LOOK = {
    "glow": (89, 179, 143),
    "rim": PALE,
    "band": (JADE, PALE),
    "card": ("#f6f0de", "#ebe1c4"),
    "edge": JADE,
    "ink": INK,
    "flowers": (("#ffffff", PALE, JADE), ("#fbf6e6", GOLD, MALACHITE)),
    "disc": ("#e9f5ec", "#bfe3cf"),
    "heart": (PALE, JADE),
    "deep": JADE,
    "deep_glow": (70, 160, 120),
}
MARKS_ANIMATED = True
CARD_TOP = 4
# Room either side of the names for the scroll's rollers.
CARD_PAD = (22, 9, 22, 9)
CARD_FONT = "KaiTi"
# 楷体, and the faces that stand in for it where it is missing.
KAI = ("KaiTi", "楷体", "STKaiti", "SimSun", "serif")
TITLE = "清风徐来"
SEAL_TEXT = "嘉宾"
# The silk rides in, holds as a heart, and a gust carries it away.
RIDE = (0.5, 2.3)
AWAY = (3.4, 4.4)
# The title is brushed a character every TITLE_STEP seconds from TITLE_AT, each over TITLE_EACH,
# and stamped at STAMP.
TITLE_AT = 2.95
TITLE_STEP = 0.18
TITLE_EACH = 0.27
STAMP = 3.78
# The light comes from the top left, a little in front.
_L = np.array([-0.45, -0.65, 0.62])
LIGHT = _L / np.linalg.norm(_L)
HALF = (LIGHT + [0, 0, 1]) / np.linalg.norm(LIGHT + [0, 0, 1])
# How many shades of each silk are made, from the deepest fold to full sheen, and how long its
# picture runs before it repeats.
LEVELS = 64
TILE = 192
TAU = math.tau


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    hills, mists = _mountains(stage, u)
    ribbons = _ribbons(stage, u)
    eraser = _eraser(width, height, gap, u)
    layer = QImage(max(1, math.ceil(width)), max(1, math.ceil(height)), QImage.Format_ARGB32_Premultiplied)
    layer.fill(Qt.transparent)
    crane = _crane(stage, u)
    drifters = _drifters(stage, u, random.Random(7))
    sprites = {"leaf": [_leaf(tint, 30 * u) for tint in (MALACHITE, JADE, GREEN)], "petal": [_petal(11 * u)]}
    mote = _mote(9 * u)
    motes = _motes(ribbons[0], u, random.Random(19))
    title = _title(stage, u)

    def paint(p: QPainter, t: float) -> None:
        life = ease_out(win(t, 0.0, 0.8)) * (1 - ease_in_out(win(t, 4.4, DURATION)))
        if life <= 0:
            return
        gust = _gust(t)
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        rise = (1 - ease_out(win(t, 0.0, 0.9))) * 16 * u
        for index, pieces in enumerate(hills):
            p.setOpacity(life)
            for rect, image in pieces:
                p.drawImage(rect.translated(0, rise * (0.5 + 0.4 * index)), image)
            _mist_paint(p, t, mists[index], gust, life, u)
        _silk_paint(p, layer, ribbons[2], t, gust, life, eraser)
        p.setOpacity(life)
        _crane_paint(p, t, crane, life)
        for ribbon in (ribbons[1], ribbons[0]):
            _silk_paint(p, layer, ribbon, t, gust, life)
        _drifters_paint(p, t, drifters, sprites, gap, life, u)
        _motes_paint(p, t, motes, mote, life)
        _title_paint(p, t, title, life)
        p.restore()

    return paint


# Timing ---------------------------------------------------------------------------------------


def _gust(t: float) -> float:
    """How hard the wind blows: a breeze, then the gust that carries the silk away."""
    return 0.25 * ease_in_out(win(t, 0.4, 1.2)) + 0.75 * ease_in_out(win(t, 3.3, 3.8)) * (1 - ease_in_out(win(t, 4.3, 4.9)))


def _hold(t: float) -> float:
    """How settled the silk is in its heart: it ripples less while it holds."""
    return ease_in_out(win(t, 2.0, 2.5)) * (1 - ease_in_out(win(t, 3.3, 3.6)))


# Shared ---------------------------------------------------------------------------------------


def _away(gap: QRectF, x: np.ndarray, y: np.ndarray, u: float) -> np.ndarray:
    """How much may show at these points: none in the gap, easing to all over a soft edge round it."""
    dx = np.maximum(np.maximum(gap.left() - x, x - gap.right()), 0)
    dy = np.maximum(np.maximum(gap.top() - y, y - gap.bottom()), 0)
    return smooth(0, 95 * u, np.sqrt(dx * dx + dy * dy)) ** 0.8


def _away_at(gap: QRectF, x: float, y: float, u: float) -> float:
    dx = max(gap.left() - x, x - gap.right(), 0)
    dy = max(gap.top() - y, y - gap.bottom(), 0)
    k = clamp(math.hypot(dx, dy) / (95 * u))
    return (k * k * (3 - 2 * k)) ** 0.8


def _mix(a: np.ndarray, b: np.ndarray, k: np.ndarray | float) -> np.ndarray:
    """a toward b by k, per pixel (colors with a last axis of 3, k without it)."""
    k = np.asarray(k, dtype=np.float32)
    return a + (b - a) * (k[..., None] if k.ndim else k)


def _tile(n: np.ndarray, w: int) -> np.ndarray:
    """Noise twice w across made to repeat every w: its two halves crossfaded."""
    k = (np.arange(w, dtype=np.float32) / w)[None, :]
    return n[:, w:] * (1 - k) + n[:, :w] * k


def _streaks(h: int, w: int, across: float, along: float, seed: int) -> np.ndarray:
    """Noise drawn out along x, along times longer than it is across: fibres, brush hairs."""
    gw = math.ceil(w / along) + 2
    n = noise(gw, h, across, 2, seed)
    fx = np.arange(w, dtype=np.float32) / along
    x0 = fx.astype(int)
    sx = fx - x0
    return n[:, x0] * (1 - sx) + n[:, x0 + 1] * sx


def _sample(grid: np.ndarray, fx: np.ndarray, fy: np.ndarray) -> np.ndarray:
    """A field read between its pixels (bilinear), wrapping at its edges."""
    h, w = grid.shape
    x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
    sx, sy = fx - x0, fy - y0
    x0, y0 = x0 % w, y0 % h
    x1, y1 = (x0 + 1) % w, (y0 + 1) % h
    return (grid[y0, x0] * (1 - sx) + grid[y0, x1] * sx) * (1 - sy) + (grid[y1, x0] * (1 - sx) + grid[y1, x1] * sx) * sy


def _dither(shape: tuple[int, ...], seed: int) -> np.ndarray:
    """A little noise to add before light is made into bytes, so its slow gradients do not band."""
    rnd = np.random.default_rng(seed)
    return (rnd.random(shape, dtype=np.float32) - rnd.random(shape, dtype=np.float32)) / 255.0


def _cropped(color: np.ndarray, alpha: np.ndarray, x0: float, y0: float) -> tuple[QRectF, QImage] | None:
    """A picture of only the part of color and alpha that shows, and where it goes."""
    rows = np.nonzero(alpha.max(axis=1) > 1 / 255)[0]
    cols = np.nonzero(alpha.max(axis=0) > 1 / 255)[0]
    if not len(rows) or not len(cols):
        return None
    r0, r1, c0, c1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    a = alpha[r0:r1, c0:c1]
    return QRectF(x0 + c0, y0 + r0, c1 - c0, r1 - r0), picture(color[r0:r1, c0:c1], a + _dither(a.shape, r0 + c0) * (a > 0))


def _put(p: QPainter, image: QImage, x: float, y: float, angle: float = 0.0, sx: float = 1.0, sy: float = 1.0) -> None:
    """A picture centred on (x, y), turned by angle degrees and sized by sx across and sy down."""
    w, h = image.width() / image.devicePixelRatio(), image.height() / image.devicePixelRatio()
    p.save()
    p.translate(x, y)
    if angle:
        p.rotate(angle)
    if sx != 1.0 or sy != 1.0:
        p.scale(sx, sy)
    p.drawImage(QRectF(-w / 2, -h / 2, w, h), image)
    p.restore()


def _shaded(m: np.ndarray, soft: float) -> np.ndarray:
    """How a shape lit from the top left catches the light, -1..1: its mask blurred into a dome and
    the dome's slope toward the light."""
    dome = blur(m, soft)
    gy, gx = np.gradient(dome)
    return np.clip(-(gx * LIGHT[0] + gy * LIGHT[1]) * soft * 3.0, -1, 1)


# The mountains and the mist ---------------------------------------------------------------------

# Each range of mountains, far to near: where its feet are (in shares of the room under the names,
# up from the bottom), how much mist is in its color, how dark its ink, how much gold, how strong the
# mist at its feet, and its peaks on each side, from the screen's edge in: (where, in shares of the
# side; how much of the room there it takes; how wide for its height).
RANGES = (
    (0.4, 0.45, 0.45, 0.5, 0.85, ((0.06, 1.0, 0.6), (0.42, 0.85, 1.7))),
    (0.12, 0.12, 0.85, 1.0, 0.85, ((0.0, 0.95, 0.5), (0.3, 0.74, 1.35), (0.78, 0.5, 1.6))),
    (-0.2, 0.0, 1.0, 0.7, 0.6, ((0.2, 0.6, 2.0), (0.72, 0.46, 1.9))),
)


def _mountains(stage: Stage, u: float) -> tuple[list[list[tuple[QRectF, QImage]]], list[dict]]:
    """The ranges along the bottom, each as pictures either side of the gap, and the mist at their
    feet. They keep under the names and rise high only in the corners, past the names' ends."""
    width, height, gap = stage.width, stage.height, stage.gap
    names = stage.names()
    floor = max(n.bottom() for n in names) + 10 * u
    left, right = min(n.left() for n in names), max(n.right() for n in names)
    w = math.ceil(width)
    xs = np.arange(w, dtype=np.float32) + 0.5
    # The highest a ridge may reach at each x.
    ymin = np.full(w, floor, dtype=np.float32)
    ymin = np.minimum(ymin, floor + (max(0.0, height - 420 * u) - floor) * smooth(left + 10 * u, left - 150 * u, xs))
    ymin = np.minimum(ymin, floor + (max(0.0, height - 330 * u) - floor) * smooth(right - 10 * u, right + 110 * u, xs))
    top = max(0, int(ymin.min() - 6 * u))
    bh = max(4, math.ceil(height) - top)
    ys = top + np.arange(bh, dtype=np.float32) + 0.5
    room = max(20 * u, height - floor)
    away = _away(gap, xs[None, :], ys[:, None], u)
    wash = noise(w, bh, 70 * u, 3, 3)
    grain = noise(w, bh, 1.4, 2, 5)
    fibre = _streaks(bh, w, 1.2, 9, 6)
    hairs = noise(256, 256, 2.0, 2, 8)
    rnd = random.Random(11)
    hills, mists = [], []
    for index, (feet, haze, ink, gold, misty, plan) in enumerate(RANGES):
        base = height - feet * room
        color = np.zeros((bh, w, 3), dtype=np.float32)
        alpha = np.zeros((bh, w), dtype=np.float32)
        skyline = np.full(w, base, dtype=np.float32)
        line = noise(w, 1, 14 * u, 2, 50 + index)[0]
        for peak in _peaks(plan, xs, ymin, base, gap, u, rnd):
            x0, tall, wl, wr, bumps, _folds = peak
            c0, c1 = max(0, int(x0 - wl)), min(w, math.ceil(x0 + wr))
            if c1 - c0 < 2:
                continue
            lift = _ridge(xs[c0:c1], x0, wl, wr, bumps, u, 60 + c0)
            ridge = base - tall * lift
            skyline[c0:c1] = np.minimum(skyline[c0:c1], ridge)
            r0 = max(0, int(ridge.min() - top - 3 * u))
            r1 = min(bh, math.ceil(base - top + 4 * u))
            if r1 - r0 < 2:
                continue
            region = (slice(r0, r1), slice(c0, c1))
            pc, pa = _hill(xs[c0:c1], ys[r0:r1], ridge, base, peak, line[c0:c1], wash[region], grain[region], fibre[region], hairs,
                           (haze, ink, gold), u, rnd.randrange(1000))  # fmt: skip
            color[region] = pc * pa[..., None] + color[region] * (1 - pa[..., None])
            alpha[region] = pa + alpha[region] * (1 - pa)
        alpha = alpha * away
        straight = color / np.maximum(alpha, 1e-4)[..., None]
        split = round(gap.center().x())
        pieces = [_cropped(straight[:, a:b], alpha[:, a:b], a, top) for a, b in ((0, split), (split, w))]
        hills.append([piece for piece in pieces if piece])
        mists.append(_mist(xs, skyline, base, top, bh, gap, misty, u, 70 + index))
    return hills, mists


def _peaks(plan: tuple, xs: np.ndarray, ymin: np.ndarray, base: float, gap: QRectF, u: float, rnd: random.Random) -> list[tuple]:
    """A range's peaks either side of the gap as its plan places them, each (x, height, half width
    left and right, the smaller tops on its shoulders, the folds down its face), tallest first so the
    smaller stand in front: never higher than ymin allows anywhere along them."""
    out = []
    for edge, inner in ((0.0, gap.left() - 30 * u), (float(xs[-1]) + 0.5, gap.right() + 30 * u)):
        span = inner - edge
        for at, reach, wide in plan:
            x = edge + span * (at + rnd.uniform(-0.04, 0.04))
            i = int(clamp(x, 0, len(xs) - 1))
            tall = max(0.0, base - float(ymin[i])) * reach * rnd.uniform(0.85, 1.0)
            wl = max(46 * u, tall * wide * rnd.uniform(0.85, 1.15))
            wr = max(46 * u, tall * wide * rnd.uniform(0.85, 1.15))
            bumps = [(0.0, 1.0, 1.0)]
            for _ in range(rnd.choice((2, 3, 4))):
                bumps.append((rnd.uniform(-0.7, 0.7), rnd.uniform(0.45, 0.85), rnd.uniform(0.22, 0.5)))
            if rnd.random() < 0.5:
                bumps.append((rnd.uniform(-0.3, 0.3), rnd.uniform(0.8, 0.95), rnd.uniform(0.18, 0.32)))
            near = (xs > x - wl) & (xs < x + wr)
            if near.any():
                lift = np.maximum(_ridge(xs[near], x, wl, wr, bumps, u, 0, rough=False), 1e-3) * 1.06
                tall = min(tall, float(np.min((base - ymin[near]) / lift)))
            if tall > 10 * u:
                folds = tuple(rnd.uniform(-0.65, 0.65) for _ in range(rnd.choice((2, 3))))
                out.append((x, tall, wl, wr, bumps, folds))
    return sorted(out, key=lambda peak: -peak[1])


def _ridge(xs: np.ndarray, x0: float, wl: float, wr: float, bumps: list, u: float, seed: int, rough: bool = True) -> np.ndarray:
    """A peak's ridge as a share of its height along xs: its main top and the smaller tops on its
    shoulders, each steep with a rounded top, and a little unevenness along it."""
    out = np.zeros(xs.shape, dtype=np.float32)
    for at, tall, wide in bumps:
        cx = x0 + at * (wr if at > 0 else wl)
        q = np.where(xs < cx, (cx - xs) / (wl * wide), (xs - cx) / (wr * wide))
        q = np.clip(q, 0, 1)
        out = np.maximum(out, tall * (0.75 * np.clip(1 - q * q, 0, 1) ** 1.4 + 0.25 * (1 - q) ** 2))
    if rough:
        out = out * (1 + 0.08 * (noise(len(xs), 1, 7 * u, 3, seed)[0] - 0.5) * np.sqrt(out))
    return out


def _hill(xs, ys, ridge, base, peak, line, wash, grain, fibre, hairs, kind, u, seed):  # noqa: ANN001, ANN202
    """One peak per pixel, in its rectangle: 石青 over its tops, 石绿 down its body, paling toward its
    feet; lit on its left, in shade on its right; 披麻 strokes fanning down from its top and a few
    folds drawn in ink; its ridge line laid by a brush, thick and thin, dry here and there, 点苔 moss
    dots along it and gold leaf on its top; the paper's grain in all of it."""
    haze, ink, gold = kind
    x0, tall, wl, wr, _bumps, folds = peak
    summit = base - tall
    d = ys[:, None] - ridge[None, :]
    fall = np.clip((ys[:, None] - summit) / tall, 0, 1.2)
    spread = np.sqrt(np.clip(fall, 0.03, 1))
    side = np.where(xs < x0, wl, wr)[None, :]
    r = np.clip((xs[None, :] - x0) / (side * spread), -1.3, 1.3)
    inside = smooth(-1.1, 1.1, d)
    w0 = wash - 0.5
    top = _mix(rgb(AZURE), rgb("#2f7f86"), np.clip(0.4 + 0.9 * w0, 0, 1))
    color = _mix(top, rgb(MALACHITE), smooth(0.05, 0.42, fall + 0.1 * w0))
    color = _mix(color, _mix(rgb(PALE), rgb("#d8d0a8"), 0.45), smooth(0.5, 1.05, fall + 0.1 * w0))
    # Blue pools under the ridge where the wash dried.
    color = _mix(color, rgb("#1e5a6e"), np.exp(-np.maximum(d, 0) / (0.12 * tall + 3 * u)) * 0.45 * inside)
    shade = 1.06 - 0.2 * np.clip(r, -1, 1) - 0.05 * fall
    color = color * shade[..., None]
    # 披麻 strokes, fanning down from the top, thicker on the shaded side.
    across = r * side * spread / (2.3 * u)
    strokes = smooth(0.57, 0.74, _sample(hairs, across + seed, d / (11 * u))) * (1 - smooth(0.2, 0.85, fall)) * smooth(1.5, 5 * u, d)
    strokes = strokes * (0.55 + 0.45 * np.clip(r, 0, 1))
    color = _mix(color, rgb("#173c3c"), strokes * 0.42 * ink)
    for k, fold in enumerate(folds):
        wobble = 0.08 * (_sample(hairs, np.full_like(d, seed + 40 * k), d / (6 * u)) - 0.5)
        dist = (r - fold - wobble) * side * spread
        crease = np.exp(-((dist / (0.8 * u)) ** 2)) * (1 - smooth(0.15, 0.7, fall)) * smooth(3 * u, 12 * u, d)
        color = _mix(color, rgb(INK), np.clip(crease * 0.55 * ink, 0, 1))
    color = _mix(color, rgb("#c4d8d0"), haze)
    # The ink line: a brush's weight swelling and thinning along it, dry in places.
    weight = (0.7 + 1.8 * line[None, :]) * u * (0.55 + 0.45 * ink)
    stroke = np.exp(-(((d - weight * 0.5) / (weight * 0.75)) ** 2))
    dry = smooth(0.32, 0.55, _sample(hairs, xs[None, :] / (1.3 * u) + 31, d / (1.3 * u) + 17) + 0.35 * line[None, :])
    stroke = stroke * (0.45 + 0.55 * dry)
    ink_c = rgb(INK) * (1 - haze) + rgb("#7d9690") * haze
    color = _mix(color, ink_c, np.clip(stroke * 0.95 * ink, 0, 1))
    # 点苔: moss dots of ink along the ridge, mostly near the top.
    rnd = np.random.default_rng(seed)
    count = int(tall / (7 * u)) + 2
    dots = np.zeros(d.shape, dtype=np.float32)
    for x_dot, size in zip(x0 + rnd.normal(0, 0.32, count) * (wl + wr) / 2, rnd.uniform(0.9, 1.7, count) * u, strict=True):
        i = int(np.clip(np.searchsorted(xs, x_dot), 0, len(xs) - 1))
        y_dot = ridge[i] + size * 1.2
        dots = np.maximum(dots, smooth(size + 0.6, size - 0.6, np.hypot(xs[None, :] - x_dot, ys[:, None] - y_dot)))
    color = _mix(color, ink_c, dots * 0.9 * ink)
    # Gold leaf on the tops, just under the line.
    crest = smooth(0.82, 1.0, (base - ridge) / tall)[None, :]
    leaf = crest * np.exp(-np.maximum(d - weight * 1.3, 0) / (3 * u)) * smooth(0, 1.5, d) * gold
    shine = _mix(rgb("#a8842f"), rgb("#f8e6a6"), np.clip(grain * 1.4 - 0.2, 0, 1))
    color = _mix(color, shine, np.clip(leaf * 0.9 * (1 - dots), 0, 1))
    color = color * (0.94 + 0.08 * grain + 0.04 * (fibre - 0.5))[..., None]
    alpha = inside * (1 - smooth(0.72, 1.02, fall + 0.25 * w0)) * (1 - 0.3 * haze)
    alpha = np.maximum(alpha, np.clip(np.maximum(stroke, dots) * ink, 0, 1) * inside)
    return color, np.clip(alpha, 0, 1)


def _mist(xs, skyline, base, top, bh, gap, strength, u, seed) -> dict:  # noqa: ANN001
    """The mist at a range's feet, as a quarter-size density that drifts and rises: where it lies (a
    band hugging the lower slopes, none over the gap) and the noise that moves through it."""
    q = 6
    w4, h4 = math.ceil(len(xs) / q) + 1, math.ceil(bh / q) + 1
    x4 = (np.arange(w4, dtype=np.float32) + 0.5) * q
    y4 = top + (np.arange(h4, dtype=np.float32) + 0.5) * q
    sky = np.interp(x4, xs, skyline)
    centre = sky + 0.62 * (base - sky)
    thick = 0.5 * (base - sky) + 10 * u
    where = np.exp(-(((y4[:, None] - centre[None, :]) / thick[None, :]) ** 2)) * _away(gap, x4[None, :], y4[:, None], u)
    extra = math.ceil(260 * u / q) + 2
    rising = math.ceil(60 * u / q) + 2
    billows = noise(w4 + extra, h4 + rising, 30 * u / q, 2, seed)
    return {"where": where, "billows": billows, "extra": extra, "rising": rising, "q": q, "top": top, "strength": strength, "w4": w4, "h4": h4,
            "color": np.broadcast_to(rgb(PAPER) * 0.45 + rgb("#eef8f2") * 0.55, (h4, w4, 3))}


def _mist_paint(p: QPainter, t: float, mist: dict, gust: float, life: float, u: float) -> None:
    """The mist drifting right with the wind and rising, at a quarter size and laid on smoothed."""
    q = mist["q"]
    drift = (14 * t + 150 * gust * max(0.0, t - 3.0)) * u / q
    rise = (4 * t + 30 * ease_in_out(win(t, 3.3, 4.9))) * u / q
    sx = mist["extra"] - min(drift, mist["extra"] - 1)
    sy = min(rise, mist["rising"] - 1)
    ix, iy = int(sx), int(sy)
    density = mist["billows"][iy : iy + mist["h4"], ix : ix + mist["w4"]] * mist["where"]
    alpha = smooth(0.1, 0.72, density) * mist["strength"] * (0.85 + 0.25 * ease_in_out(win(t, 4.3, 4.8)))
    color = mist["color"]
    p.setOpacity(life)
    p.drawImage(QRectF((ix - sx) * q, mist["top"] + (iy - sy) * q, mist["w4"] * q, mist["h4"] * q), picture(color, alpha))


def _eraser(width: float, height: float, gap: QRectF, u: float) -> tuple[QRectF, QImage]:
    """What rubs out a ribbon over the gap: all of it there, less and less out to a soft edge."""
    out = gap.adjusted(-96 * u, -96 * u, 96 * u, 96 * u).intersected(QRectF(0, 0, width, height))
    w, h = max(2, math.ceil(out.width())), max(2, math.ceil(out.height()))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    keep = _away(gap, xs + out.left() + 0.5, ys + out.top() + 0.5, u)
    return QRectF(out.left(), out.top(), w, h), picture(np.ones((h, w, 3), np.float32), 1 - keep)


# The silk -------------------------------------------------------------------------------------


@dataclass
class _Silk:
    """A silk ribbon: the line its head runs along, how long and wide it is, when it rides, holds and
    is carried off, and its pictures, one for each shade."""

    path: np.ndarray
    along: np.ndarray
    normals: np.ndarray
    width: float
    length: float
    ride: tuple[float, float]
    spots: tuple[float, float, float]
    braid: float
    phase: float
    levels: list[QImage]
    half: float
    tw: int
    u: float
    lag: float = 0.0
    s: np.ndarray = field(default_factory=lambda: np.zeros(0))

    def head(self, t: float) -> float:
        """How far along its line the ribbon's head is: in from off the left, slowing into its place,
        creeping while it holds, then away with the gust."""
        start, hold, gone = self.spots
        k = win(t, *self.ride)
        d = start + (hold - start) * (1 - (1 - k) ** 1.5)
        d += 34 * self.u * max(0.0, t - self.ride[1])
        d += (gone - hold) * ease_in(win(t, *AWAY)) ** 0.9
        return d - self.lag


def _ribbons(stage: Stage, u: float) -> list[_Silk]:
    """The two jade ribbons that braid across the top and loop into the heart, and the 石青 one low
    over the mountains on the left."""
    width, height, gap = stage.width, stage.height, stage.gap
    size = 200 * u
    hx, hy = width - 300 * u, 92 * u
    tip = (hx, hy + 0.574 * size)
    phi = np.linspace(0, 1, 260)[1:-1]
    a = math.pi - TAU * phi
    hxs = hx + 16 * np.sin(a) ** 3 * size / 34
    hys = hy - (13 * np.cos(a) - 5 * np.cos(2 * a) - 2 * np.cos(3 * a) - np.cos(4 * a) - 2.5) * size / 34
    loop = np.column_stack([hxs, hys])
    into = _spline([(-0.05 * width, 215 * u), (0.1 * width, 160 * u), (0.27 * width, 80 * u), (0.45 * width, 36 * u), (0.62 * width, 34 * u),
                    (hx - 175 * u, 92 * u), (hx - 118 * u, 200 * u), (hx - 52 * u, tip[1] + 18 * u), tip], 2 * u)  # fmt: skip
    out = _spline([tip, (hx + 52 * u, tip[1] + 18 * u), (hx + 150 * u, tip[1] + 10 * u), (width - 40 * u, 120 * u), (width + 70 * u, -30 * u),
                   (width + 200 * u, -220 * u)], 2 * u)  # fmt: skip
    heart = _along(loop)[-1]
    length = heart + 230 * u
    line = np.vstack([into, loop, out])
    top = _line(line, length + 120 * u, u, 25)
    first = top["start"] + _along(into)[-1] + heart + 64 * u
    jade = _Silk(top["path"], top["along"], top["normals"], 34 * u, length, RIDE, (top["start"], first, top["end"] + length), -5.0, 0.0,
                 *_silk(MALACHITE, "#16503f", "#cdf2df", 34 * u, u, 3), u)  # fmt: skip
    pale = _Silk(top["path"], top["along"], top["normals"], 22 * u, length - 70 * u, RIDE, (top["start"], first, top["end"] + length), 15.0, 2.1,
                 *_silk(PALE, "#2f7f62", "#f2fff8", 22 * u, u, 5), u, lag=26 * u)  # fmt: skip
    low = _spline([(-0.05 * width, height - 50 * u), (0.08 * width, height - 82 * u), (0.2 * width, height - 112 * u), (gap.left() - 90 * u, height - 96 * u),
                   (gap.center().x(), height - 52 * u), (gap.right() + 90 * u, height - 98 * u), (width - 190 * u, height - 120 * u),
                   (width - 80 * u, height - 178 * u), (width - 30 * u, height - 300 * u), (width + 60 * u, height - 470 * u),
                   (width + 200 * u, height - 650 * u)], 2 * u)  # fmt: skip
    blue_length = 540 * u
    bottom = _line(low, blue_length + 120 * u, u)
    stop = bottom["start"] + float(_along(low)[np.argmin(np.abs(low[:, 0] - (gap.left() - 40 * u)))])
    blue = _Silk(bottom["path"], bottom["along"], bottom["normals"], 26 * u, blue_length, (0.5, 2.25), (bottom["start"], stop, bottom["end"] + blue_length),
                 0.0, 4.2, *_silk("#4fa3a8", "#1d4f66", "#d4f3ec", 26 * u, u, 7), u)  # fmt: skip
    for silk in (jade, pale, blue):
        silk.s = np.arange(0, silk.length, 1.5 * u)
    return [jade, pale, blue]


def _line(points: np.ndarray, reach: float, u: float, k: int = 9) -> dict:
    """A ribbon's line, carried on straight off both its ends by reach so the whole ribbon can wait
    off screen before and after, its corners rounded and its points evenly spaced."""
    head = points[0] - (points[1] - points[0]) / max(1e-9, float(np.hypot(*(points[1] - points[0])))) * reach
    tail = points[-1] + (points[-1] - points[-2]) / max(1e-9, float(np.hypot(*(points[-1] - points[-2])))) * reach
    line = _even(np.vstack([head, points, tail]), 2 * u)
    kernel = np.ones(k) / k
    smoothed = np.column_stack([np.convolve(np.pad(line[:, i], k // 2, mode="edge"), kernel, mode="valid") for i in (0, 1)])
    line = _even(smoothed, 2 * u)
    along = _along(line)
    return {"path": line, "along": along, "normals": _normals(line), "start": reach, "end": float(along[-1]) - reach}


def _spline(points: list[tuple[float, float]], step: float) -> np.ndarray:
    """A smooth line through points (Catmull-Rom), as points every step apart."""
    pts = np.array([points[0], *points, points[-1]], dtype=np.float64)
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in np.linspace(0, 1, 24, endpoint=False):
            out.append(0.5 * (2 * p1 + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s + (-p0 + 3 * p1 - 3 * p2 + p3) * s**3))
    out.append(pts[-2])
    return _even(np.array(out), step)


def _even(points: np.ndarray, step: float) -> np.ndarray:
    seg = np.hypot(*np.diff(points, axis=0).T)
    points = points[np.concatenate([[True], seg > 1e-9])]
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(points, axis=0).T))])
    at = np.linspace(0, s[-1], max(3, int(s[-1] / step) + 1))
    return np.column_stack([np.interp(at, s, points[:, 0]), np.interp(at, s, points[:, 1])])


def _along(points: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(points, axis=0).T))])


def _normals(points: np.ndarray) -> np.ndarray:
    d = np.gradient(points, axis=0)
    d = d / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)[:, None]
    return np.column_stack([-d[:, 1], d[:, 0]])


def _silk(tint: str, deep: str, light: str, width: float, u: float, seed: int) -> tuple[list[QImage], float, int]:
    """A silk's pictures per pixel, LEVELS of them from its deepest fold to full sheen, each TILE long
    (three times over, to cut slices from) and as wide as the silk and its soft edge: a fine weave and
    fibres along it, the sheen streaking along the fibres, the hem a little denser, and a gold thread
    trimming each side, catching the light as the silk turns. Thin silk is see-through, a fold or the
    sheen less so. With its half width and its picture's height."""
    half = width / 2
    margin = max(2.0, 3 * u)
    tw = math.ceil(2 * (half + margin))
    v = ((np.arange(tw, dtype=np.float32) + 0.5 - tw / 2) / half)[:, None]
    av = np.abs(v)
    weave = np.tile(_tile(noise(2 * TILE, tw, 1.1, 2, seed), TILE), 3)
    fibre = np.tile(_tile(_streaks(tw, 2 * TILE, 1.2, 18, seed + 1), TILE), 3)
    spark = np.tile(_tile(noise(2 * TILE, tw, 1.0, 1, seed + 2), TILE), 3)
    cloud = np.tile(_tile(noise(2 * TILE, tw, 9 * u, 2, seed + 3), TILE), 3)
    edge = smooth(1 + 0.9 / half, 1 - 0.9 / half, av)
    hem = smooth(0.72, 0.97, av)
    thread = np.exp(-(((av - 0.84) * half / 0.8) ** 2))
    glow = 0.16 * np.exp(-np.maximum(av - 1, 0) * half / (2.2 * u)) * (1 - edge)
    round_ = 1 + 0.07 * (1 - v * v)
    deep_c, tint_c, light_c = rgb(deep), rgb(tint), rgb(light)
    out = []
    for i in range(LEVELS):
        lum = i / (LEVELS - 1)
        fold = smooth(0.45, 0.0, lum)
        sheen = smooth(0.58, 1.0, lum)
        base = deep_c + (tint_c - deep_c) * (lum / 0.5) if lum < 0.5 else tint_c + (light_c - tint_c) * ((lum - 0.5) / 0.5)
        color = base * ((0.93 + 0.1 * weave + 0.05 * (cloud - 0.5)) * round_)[..., None]
        gloss = (sheen * (0.3 + 0.7 * fibre))[..., None]
        color = color + (light_c - color) * gloss * 0.55 + (1 - color) * gloss * 0.12
        color = color * (1 - hem * 0.1)[..., None]
        gold = _mix(rgb("#8a6a26"), rgb("#fbecb4"), np.clip(0.15 + 0.75 * lum + 0.6 * (spark - 0.5), 0, 1))
        color = _mix(color, gold, thread * 0.95)
        alpha = 0.42 + 0.3 * fold + 0.16 * sheen * (0.4 + 0.6 * fibre) + 0.2 * hem + 0.06 * (cloud - 0.5)
        alpha = np.maximum(alpha, thread * 0.95)
        alpha = np.clip(alpha, 0, 1) * edge + glow
        color = _mix(np.broadcast_to(light_c, color.shape), color, edge)
        out.append(picture(color, alpha + _dither(alpha.shape, seed + i)))
    return out, half, tw


def _silk_paint(p: QPainter, layer: QImage, silk: _Silk, t: float, gust: float, life: float, eraser: tuple[QRectF, QImage] | None = None) -> None:
    """A ribbon as it is at t: its line followed back from its head, rippling and twisting, cut into
    short slices each laid from the silk's picture of its shade. They go on a layer of their own, each
    replacing what is under it, so where slices overlap on a bend there is no seam; the layer is then
    laid on."""
    u = silk.u
    head = silk.head(t)
    s = silk.s
    d = head - s
    if d[0] < silk.along[0] or d[-1] > silk.along[-1]:
        d = np.clip(d, silk.along[0], silk.along[-1])
    bx, by = np.interp(d, silk.along, silk.path[:, 0]), np.interp(d, silk.along, silk.path[:, 1])
    nx, ny = np.interp(d, silk.along, silk.normals[:, 0]), np.interp(d, silk.along, silk.normals[:, 1])
    hold = _hold(t)
    share = s / silk.length
    # Braided round its twin by the line, rippling along itself, the free end most.
    offset = silk.braid * u * np.sin(TAU * d / (240 * u))
    amp = (3 + 13 * share) * u * (1 - 0.55 * hold) + gust * 26 * u * share
    offset = offset + amp * np.sin(TAU * (s / (170 * u) - 0.9 * t) + silk.phase)
    x, y = bx + nx * offset, by + ny * offset
    if x.max() < -60 * u or x.min() > layer.width() + 60 * u or y.max() < -60 * u or y.min() > layer.height() + 60 * u:
        return
    theta = 1.05 * np.sin(TAU * (s / (150 * u) - 1.1 * t) + silk.phase * 1.7) + 0.5 * np.sin(TAU * (s / (420 * u) + 0.35 * t) + silk.phase)
    width = silk.width * (0.42 + 0.58 * smooth(0, 60 * u, s)) * (1 - 0.55 * smooth(0.82 * silk.length, silk.length, s))
    pad = silk.width + 8 * u
    x0, y0 = max(0, int(x.min() - pad)), max(0, int(y.min() - pad))
    x1, y1 = min(layer.width(), math.ceil(x.max() + pad)), min(layer.height(), math.ceil(y.max() + pad))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    box = QRect(x0, y0, x1 - x0, y1 - y0)
    q = QPainter(layer)
    q.setCompositionMode(QPainter.CompositionMode_Source)
    q.fillRect(box, Qt.transparent)
    keep = (x > x0 - pad) & (x < x1 + pad) & (y > y0 - pad) & (y < y1 + pad)
    _lay(q, x, y, s, theta, width, silk.levels, silk.half, silk.tw, keep)
    q.resetTransform()
    if eraser is not None:
        q.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        q.drawImage(*eraser)
    q.end()
    p.save()
    p.setOpacity(life)
    p.drawImage(QRectF(box), layer, QRectF(box))
    p.restore()


def _lay(q: QPainter, x: np.ndarray, y: np.ndarray, s: np.ndarray, theta: np.ndarray, width: np.ndarray, levels: list[QImage], half: float,
         tw: int, keep: np.ndarray | None = None) -> None:
    """A ribbon laid on q from its line (x, y, s along it), its twist and width at each point: a quad
    of its picture between each two points, the quads sharing their edges so they meet without a seam
    or an overlap, each in the shade its twist turns it to. A face turned toward the light shines, one
    turned edge on is narrow and deep in color; turned past edge on, its back shows."""
    tx, ty = np.gradient(x), np.gradient(y)
    if len(tx) > 4:
        # The line's direction a little smoothed, so the edges run clean along a curve.
        tx, ty = (np.convolve(np.pad(a, 2, mode="edge"), np.ones(5) / 5, mode="valid") for a in (tx, ty))
    norm = np.maximum(np.hypot(tx, ty), 1e-6)
    tx, ty = tx / norm, ty / norm
    cos, sin = np.cos(theta), np.sin(theta)
    facing = np.sign(cos + 1e-6)
    n = np.stack([ty * sin * facing, -tx * sin * facing, cos * facing], axis=-1)
    diffuse = np.maximum(n @ LIGHT, 0)
    spec = np.maximum(n @ HALF, 0) ** 9
    lum = np.clip(0.1 + 0.62 * diffuse + 0.42 * spec - 0.3 * (1 - np.abs(cos)), 0, 1)
    # The points come close together; a quad spans up to four of them, fewer where the light changes
    # fast, so no quad is more than about a shade lighter at one end than the other.
    shade = lum * (LEVELS - 1)
    chosen = [0]
    last = shade[0]
    for i in range(1, len(s)):
        if i - chosen[-1] >= 4 or abs(shade[i] - last) > 0.9 or i == len(s) - 1:
            chosen.append(i)
            last = shade[i]
    if len(chosen) < 2:
        return
    at = np.array(chosen)
    k = (np.where(np.abs(cos) < 0.05, 0.05 * facing, cos) * width / 2 / half * tw / 2)[at]
    x, y, s, tx, ty, lum = (a[at] for a in (x, y, s, tx, ty, lum))
    keep = keep[at] if keep is not None else np.ones(len(at), dtype=bool)
    # Where it turns over between two points, a point between them twice: edge on, a thread wide,
    # once each way, so each side of the turn is a proper quad.
    flip = np.nonzero(k[:-1] * k[1:] < 0)[0]
    if len(flip):
        mid = lambda a: (a[flip] + a[flip + 1]) / 2  # noqa: E731
        thin = 0.6
        x, y, s, tx, ty, lum = (np.insert(a, np.repeat(flip + 1, 2), np.repeat(mid(a), 2)) for a in (x, y, s, tx, ty, lum))
        k = np.insert(k, np.repeat(flip + 1, 2), np.column_stack([np.sign(k[flip]) * thin, np.sign(k[flip + 1]) * thin]).ravel())
        keep = np.insert(keep, np.repeat(flip + 1, 2), True)
    level = np.rint((lum[:-1] + lum[1:]) / 2 * (LEVELS - 1)).astype(int)
    # Each point's two edges, across the line from it; each quad's corners, near edge then far.
    ax, ay = x + ty * k, y - tx * k
    bx, by = x - ty * k, y + tx * k
    x0, y0, x1, y1 = ax[:-1], ay[:-1], ax[1:], ay[1:]
    x2, y2, x3, y3 = bx[1:], by[1:], bx[:-1], by[:-1]
    span = s[1:] - s[:-1]
    start = TILE + s[:-1] % TILE
    # The square onto each quad (Heckbert's), then the picture's piece onto the square.
    dx1, dx2, dx3 = x1 - x2, x3 - x2, x0 - x1 + x2 - x3
    dy1, dy2, dy3 = y1 - y2, y3 - y2, y0 - y1 + y2 - y3
    den = dx1 * dy2 - dx2 * dy1
    den = np.where(np.abs(den) < 1e-9, 1e-9, den)
    g = (dx3 * dy2 - dx2 * dy3) / den
    h = (dx1 * dy3 - dx3 * dy1) / den
    # A quad folded over itself (a tight inner bend) is laid as the parallelogram from its near end.
    turns = [((cx1 - cx0) * (cy2 - cy1) - (cy1 - cy0) * (cx2 - cx1)) for (cx0, cy0), (cx1, cy1), (cx2, cy2) in
             (((x0, y0), (x1, y1), (x2, y2)), ((x1, y1), (x2, y2), (x3, y3)), ((x2, y2), (x3, y3), (x0, y0)), ((x3, y3), (x0, y0), (x1, y1)))]  # fmt: skip
    turns = np.array(turns)
    proper = np.all(turns > 0, axis=0) | np.all(turns < 0, axis=0)
    g, h = np.where(proper, g, 0), np.where(proper, h, 0)
    a = np.where(proper, x1 - x0 + g * x1, x1 - x0)
    b = np.where(proper, x3 - x0 + h * x3, x3 - x0)
    d = np.where(proper, y1 - y0 + g * y1, y1 - y0)
    e = np.where(proper, y3 - y0 + h * y3, y3 - y0)
    safe = np.where(span > 1e-6, span, 1.0)
    m = np.column_stack([a / safe, d / safe, g / safe, b / tw, e / tw, h / tw, x0 - a * start / safe, y0 - d * start / safe, 1 - g * start / safe])
    show = keep[:-1] | keep[1:]
    show &= span > 1e-6
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.setRenderHint(QPainter.Antialiasing, False)
    for i in np.nonzero(show)[0][::-1].tolist():
        piece = QRectF(start[i], 0, span[i], tw)
        q.setTransform(QTransform(*m[i]))
        q.drawImage(piece, levels[level[i]], piece)
    q.resetTransform()


# The crane ------------------------------------------------------------------------------------


def _crane(stage: Stage, u: float) -> dict:
    """A white crane far off, its flight's line across the top left and its pictures, a wingbeat's
    worth of them: white with black flight feathers and a red crown, shaded softly from above."""
    span = 92 * u
    frames = [_crane_frame(span, k / 12, 2.0) for k in range(12)]
    start = QPointF(-80 * u, 210 * u)
    bend = QPointF(0.22 * stage.width, 150 * u)
    end = QPointF(0.52 * stage.width, -70 * u)
    return {"frames": frames, "line": (start, bend, end), "span": span}


def _crane_frame(span: float, phase: float, scale: float) -> QImage:
    """The crane in profile flying right, its wings raised by phase (0..1 of a beat): the near wing in
    front of its body, the far one behind it and greyer; the long neck stretched forward, the legs
    trailing behind."""
    s = span
    w, h = math.ceil(s * 1.25 * scale), math.ceil(s * 0.95 * scale)
    up = 0.8 + 0.2 * math.cos(TAU * phase)

    def wing(far: bool) -> tuple[QPolygonF, QPolygonF]:
        """The wing's outline, broad and swept back, its primaries spread like fingers at the tip;
        and its black secondaries along the inner trailing edge."""
        lift = up * (0.86 if far else 1.0)
        shoulder = np.array([0.07 * s - (0.05 * s if far else 0), -0.03 * s])
        elbow = shoulder + [-0.04 * s, -0.26 * s * lift]
        tip = shoulder + [-0.3 * s, -0.46 * s * lift + 0.06 * s * (1 - lift)]
        ks = np.linspace(0, 1, 22)
        lead = np.array([(1 - k) ** 2 * shoulder + 2 * (1 - k) * k * elbow + k * k * tip for k in ks])
        tangent = np.gradient(lead, axis=0)
        tangent = tangent / np.maximum(np.hypot(tangent[:, 0], tangent[:, 1]), 1e-9)[:, None]
        across = np.column_stack([tangent[:, 1], -tangent[:, 0]])
        back = np.where(across[:, :1] < 0, across, -across)
        chord = s * (0.25 * (1 - ks) + 0.08 * ks) * np.where((ks > 0.62) & (np.arange(len(ks)) % 2 == 1), 1.3, 1.0)
        trail = lead + back * chord[:, None]
        inner = lead + back * (chord * np.where(ks < 0.62, 0.66, 0.66 + (ks - 0.62) * 4))[:, None]
        black = [*inner[ks < 0.72], *reversed(trail[ks < 0.72])]
        outline = [*lead, *reversed(trail)]
        return QPolygonF([QPointF(*point) for point in outline]), QPolygonF([QPointF(*point) for point in black])

    def frame(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(w / scale * 0.5, h / scale * 0.66)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)

    def body(q: QPainter) -> None:
        frame(q)
        q.drawEllipse(QPointF(0, 0), 0.17 * s, 0.05 * s)
        neck = QPainterPath(QPointF(0.12 * s, -0.015 * s))
        neck.cubicTo(QPointF(0.22 * s, -0.05 * s), QPointF(0.32 * s, -0.06 * s), QPointF(0.42 * s, -0.05 * s))
        q.setPen(QPen(Qt.white, 0.028 * s, Qt.SolidLine, Qt.RoundCap))
        q.drawPath(neck)
        q.setPen(Qt.NoPen)
        q.drawEllipse(QPointF(0.43 * s, -0.051 * s), 0.026 * s, 0.02 * s)

    def near(q: QPainter) -> None:
        frame(q)
        q.drawPolygon(wing(False)[0])

    def near_black(q: QPainter) -> None:
        frame(q)
        q.drawPolygon(wing(False)[1])
        q.drawEllipse(QPointF(-0.17 * s, 0.006 * s), 0.05 * s, 0.024 * s)
        neck = QPainterPath(QPointF(0.3 * s, -0.058 * s))
        neck.cubicTo(QPointF(0.34 * s, -0.06 * s), QPointF(0.38 * s, -0.056 * s), QPointF(0.41 * s, -0.05 * s))
        q.setPen(QPen(Qt.white, 0.03 * s, Qt.SolidLine, Qt.RoundCap))
        q.drawPath(neck)

    def far(q: QPainter) -> None:
        frame(q)
        q.drawPolygon(wing(True)[0])

    def far_black(q: QPainter) -> None:
        frame(q)
        q.drawPolygon(wing(True)[1])

    def legs(q: QPainter) -> None:
        frame(q)
        q.setPen(QPen(Qt.white, 0.012 * s, Qt.SolidLine, Qt.RoundCap))
        q.drawLine(QPointF(-0.1 * s, 0.03 * s), QPointF(-0.47 * s, 0.07 * s))
        q.drawLine(QPointF(-0.1 * s, 0.035 * s), QPointF(-0.45 * s, 0.085 * s))
        q.setPen(QPen(Qt.white, 0.013 * s, Qt.SolidLine, Qt.RoundCap))
        q.drawLine(QPointF(0.45 * s, -0.048 * s), QPointF(0.54 * s, -0.036 * s))

    def crown(q: QPainter) -> None:
        frame(q)
        q.drawEllipse(QPointF(0.43 * s, -0.066 * s), 0.013 * s, 0.009 * s)

    white, front, black, back, back_black, grey, red = (mask(w, h, draw) for draw in (body, near, near_black, far, far_black, legs, crown))
    white = np.maximum(white, front)
    lit = _shaded(np.maximum(white, back * 0.8), 2.0 * scale)
    ys = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    shade = np.clip(0.93 + 0.14 * lit - 0.05 * ys, 0, 1.05)
    color = np.broadcast_to(rgb("#fbfaf3"), (h, w, 3)) * shade[..., None]
    # The far wing, behind, in the body's shadow and further off.
    behind = back * (1 - white)
    color = _mix(color, rgb("#b9c9c4"), behind * 0.8)
    color = _mix(color, rgb("#232a28"), np.maximum(black, back_black * (1 - white)) * 0.95)
    color = _mix(color, rgb("#4f5a56"), grey * (1 - white))
    color = _mix(color, rgb(SEAL), red)
    alpha = np.clip(np.maximum.reduce([white, behind * 0.92, black, back_black * 0.88, grey * 0.85, red]), 0, 1) * 0.94
    image = picture(color, alpha)
    image.setDevicePixelRatio(scale)
    return image


def _crane_paint(p: QPainter, t: float, crane: dict, life: float) -> None:
    k = win(t, 0.4, 3.2)
    if k <= 0 or k >= 1:
        return
    start, bend, end = crane["line"]
    m = 1 - k
    x = m * m * start.x() + 2 * m * k * bend.x() + k * k * end.x()
    y = m * m * start.y() + 2 * m * k * bend.y() + k * k * end.y()
    dx = 2 * m * (bend.x() - start.x()) + 2 * k * (end.x() - bend.x())
    dy = 2 * m * (bend.y() - start.y()) + 2 * k * (end.y() - bend.y())
    angle = math.degrees(math.atan2(dy, dx)) * 0.6
    frames = crane["frames"]
    # Slow beats, then a long glide on raised wings, then beats again.
    beat = (t * 1.1) % 1.0 if t < 1.5 or t > 2.6 else 0.0
    frame = frames[int(beat * len(frames)) % len(frames)]
    p.save()
    p.setOpacity(life * smooth(0.0, 0.06, np.float32(k)).item() * (1 - smooth(0.92, 1.0, np.float32(k)).item()))
    _put(p, frame, x, y + 3 * crane["span"] / 92 * math.sin(t * 3.0), angle)
    p.restore()


# Bamboo leaves, pear petals and gold motes ------------------------------------------------------


def _leaf(tint: str, length: float) -> tuple[QImage, QImage]:
    """A bamboo leaf per pixel, its front and its paler back: long and pointed, a fine midrib and the
    parallel veins along it, deeper at its base, lit through at its edges."""
    scale = 2.0
    wide = length * 0.17
    w, h = math.ceil(length * scale + 4), math.ceil(wide * scale + 6)

    def shape(q: QPainter) -> None:
        q.translate(2, h / 2)
        q.scale(scale, scale)
        path = QPainterPath(QPointF(0, 0))
        path.cubicTo(QPointF(length * 0.12, -wide * 0.62), QPointF(length * 0.42, -wide * 0.58), QPointF(length, 0))
        path.cubicTo(QPointF(length * 0.42, wide * 0.5), QPointF(length * 0.12, wide * 0.55), QPointF(0, 0))
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(path)

    m = mask(w, h, shape)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    along = np.clip((xs - 2) / (length * scale), 0, 1)
    across = (ys - h / 2) / (wide * scale / 2)
    rib = np.exp(-((ys - h / 2 + 0.3) / 0.9) ** 2) * (along < 0.95)
    veins = 0.5 + 0.5 * np.cos(across * 9.0)
    lit = _shaded(m, 1.6 * scale)
    out = []
    for back in (False, True):
        base = _mix(rgb(tint), rgb("#1d5a44"), (1 - along) * 0.45)
        if back:
            base = _mix(base, rgb("#cfe9d9"), 0.4)
        color = base * (0.9 + 0.2 * lit + 0.05 * veins * m)[..., None]
        color = _mix(color, rgb("#e4f7d8"), rib * 0.55)
        color = _mix(color, rgb("#d8f2a8"), (m - blur(m, 1.2 * scale)).clip(0, 1) * 0.6)
        image = picture(color, m * 0.96)
        image.setDevicePixelRatio(scale)
        out.append(image)
    return out[0], out[1]


def _petal(size: float) -> tuple[QImage, QImage]:
    """A pear petal per pixel: white, round with a small notch, a breath of green at its base and the
    faint veins fanning from it."""
    scale = 2.5
    w = h = math.ceil(size * scale + 4)

    def shape(q: QPainter) -> None:
        q.translate(w / 2, h / 2)
        q.scale(scale, scale)
        r = size / 2
        path = QPainterPath(QPointF(0, r * 0.95))
        path.cubicTo(QPointF(-r * 1.1, r * 0.55), QPointF(-r * 1.0, -r * 0.95), QPointF(-r * 0.12, -r * 0.9))
        path.lineTo(QPointF(0, -r * 0.72))
        path.lineTo(QPointF(r * 0.12, -r * 0.9))
        path.cubicTo(QPointF(r * 1.0, -r * 0.95), QPointF(r * 1.1, r * 0.55), QPointF(0, r * 0.95))
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(path)

    m = mask(w, h, shape)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = xs - w / 2, ys - (h / 2 + size * scale * 0.45)
    reach = np.hypot(dx, dy) / (size * scale)
    veins = 0.5 + 0.5 * np.cos(np.arctan2(dx, -dy) * 14)
    lit = _shaded(m, 1.5 * scale)
    out = []
    for back in (False, True):
        color = _mix(rgb("#ffffff"), rgb("#dcebd2"), smooth(0.45, 0.0, reach) * 0.8)
        color = color * (0.93 + 0.08 * lit - 0.03 * veins * smooth(0.2, 0.8, reach))[..., None]
        if back:
            color = color * 0.92
        image = picture(color, m * 0.93)
        image.setDevicePixelRatio(scale)
        out.append(image)
    return out[0], out[1]


def _mote(size: float) -> QImage:
    """A gold mote: a warm point of light with a soft halo."""
    n = max(6, math.ceil(size * 2))
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    r = np.hypot(xs - n / 2 + 0.5, ys - n / 2 + 0.5) / (n / 2)
    light = np.exp(-(r / 0.12) ** 2)[..., None] * rgb("#fff6d8") * 1.2 + np.exp(-(r / 0.45) ** 2)[..., None] * rgb(GOLD) * 0.55
    light = np.maximum(light, 0)
    alpha = np.clip(light.max(axis=-1), 0, 1)
    return picture(np.clip(light, 0, 1) / np.maximum(alpha, 1e-4)[..., None], alpha)


def _drifters(stage: Stage, u: float, rnd: random.Random) -> list[tuple]:
    """The leaves and petals the wind carries: when each comes in from the left, how high, how fast
    and how it sways, turns and tumbles, and which picture it is."""
    names = stage.names()
    sky = min(n.top() for n in names) - 175 * u
    floor = max(n.bottom() for n in names) + 12 * u
    out = []
    plan = [("leaf", 0)] * 6 + [("petal", 0)] * 5 + [("leaf", 1)] * 3 + [("petal", 1)] * 3
    for index, (kind, low) in enumerate(plan):
        if low:
            y = rnd.uniform(floor + 8 * u, stage.height - 18 * u)
        else:
            y = rnd.uniform(18 * u, max(30 * u, sky))
        start = 0.55 + index / len(plan) * 1.9 + rnd.uniform(-0.1, 0.1)
        out.append((kind, start, y, rnd.uniform(330, 520) * u, rnd.uniform(8, 22) * u, rnd.uniform(0.6, 1.3), rnd.uniform(0, TAU),
                    rnd.uniform(-160, 160), rnd.uniform(1.5, 3.5), rnd.uniform(0.8, 1.15), rnd.randrange(3), low))  # fmt: skip
    return out


def _drifters_paint(p: QPainter, t: float, drifters: list[tuple], sprites: dict, gap: QRectF, life: float, u: float) -> None:
    push = 520 * u * ease_in(win(t, 3.3, 4.6)) ** 0.8
    for kind, start, y0, speed, sway, freq, phase, spin, tumble, size, tint, low in drifters:
        age = t - start
        if age <= 0:
            continue
        x = -30 * u + speed * age + push
        y = y0 + sway * math.sin(TAU * freq * age + phase) - (40 if low else 170) * u * ease_in(win(t, 3.4, 4.8))
        if x > gap.right() + 2000 * u:
            continue
        alpha = life * clamp(age / 0.25) * _away_at(gap, x, y, u)
        if alpha <= 0.01:
            continue
        front, back = sprites[kind][tint % len(sprites[kind])]
        turn = math.cos(TAU * age / tumble + phase)
        p.setOpacity(alpha)
        _put(p, front if turn >= 0 else back, x, y, spin * age + phase * 57, size, size * max(0.12, abs(turn)))
    p.setOpacity(life)


def _motes(silk: _Silk, u: float, rnd: random.Random) -> list[tuple]:
    """Gold motes of 仙气 left where the jade ribbon passed: where each hangs, when the ribbon's head
    went by it, how long it glows, how big."""
    times = np.linspace(RIDE[0], RIDE[1] + 0.6, 400)
    heads = np.array([silk.head(float(t)) for t in times])
    lo, hi = silk.spots[0] + 40 * u, silk.spots[1]
    out = []
    for _ in range(34):
        d = rnd.uniform(lo, hi)
        when = float(np.interp(d, heads, times))
        x = float(np.interp(d, silk.along, silk.path[:, 0])) + rnd.gauss(0, 16) * u
        y = float(np.interp(d, silk.along, silk.path[:, 1])) + rnd.gauss(0, 16) * u
        out.append((x, y, when + rnd.uniform(0.05, 0.3), rnd.uniform(1.2, 2.2), rnd.uniform(0.35, 0.9), rnd.uniform(0, TAU)))
    return out


def _motes_paint(p: QPainter, t: float, motes: list[tuple], image: QImage, life: float) -> None:
    size = image.width()
    for x, y, start, last, scale, phase in motes:
        k = (t - start) / last
        if k <= 0 or k >= 1:
            continue
        glow = math.sin(math.pi * k) * (0.6 + 0.4 * math.sin(t * 9 + phase))
        p.setOpacity(life * glow)
        side = size * scale
        p.drawImage(QRectF(x + 14 * k * scale - side / 2, y - 18 * k * scale - side / 2, side, side), image)
    p.setOpacity(life)


# The title ------------------------------------------------------------------------------------


def _kai(pixels: float) -> QFont:
    font = QFont()
    font.setFamilies(list(KAI))
    font.setPixelSize(max(6, round(pixels)))
    return font


def _parts(m: np.ndarray) -> list[np.ndarray]:
    """The separate strokes of a character's mask (its connected parts), each as a mask."""
    solid = m > 0.35
    seen = np.zeros_like(solid)
    h, w = solid.shape
    out = []
    for y0, x0 in zip(*np.nonzero(solid), strict=True):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        mine = []
        while stack:
            y, x = stack.pop()
            mine.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and solid[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(mine) < 6:
            continue
        part = np.zeros_like(m)
        ys, xs = np.array(mine).T
        part[ys, xs] = 1
        out.append(part)
    return out


def _title(stage: Stage, u: float) -> dict:
    """清风徐来 on a hanging scroll in the top left: rice paper mounted in jade silk, unrolling down
    from its rod; the title in 楷体, each character cut into its strokes in writing order, each stroke
    ink per pixel with which way the brush went along it; the red seal under it."""
    names = stage.names()
    size = 46 * u
    step = 52 * u
    cx = max(48 * u, min(min(n.left() for n in names) * 0.5, 110 * u))
    head = 20 * u + 26 * u
    top = head + 6 * u
    font = _kai(size)
    margin = round(6 * u)
    side = math.ceil(size * 1.2 + margin * 2)
    strokes = []
    for index, glyph in enumerate(TITLE):
        path = QPainterPath()
        path.addText(QPointF(0, 0), font, glyph)
        box = path.boundingRect()

        def draw(q: QPainter, path: QPainterPath = path, box: QRectF = box) -> None:
            q.translate(side / 2 - box.center().x(), side / 2 - box.center().y())
            # A brush lays more ink than the face's thin lines: each stroke a little fuller.
            q.setPen(QPen(Qt.white, size * 0.032, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.setBrush(Qt.white)
            q.drawPath(path)

        m = mask(side, side, draw)
        origin = QPointF(cx - side / 2, top + index * step + size / 2 - side / 2)
        parts = _parts(m)
        if not parts:
            continue
        owner = np.zeros(m.shape, dtype=np.int32)
        reach = np.zeros(m.shape, dtype=np.float32)
        for k, part in enumerate(parts):
            near = blur(part, 1.2)
            better = near > reach
            owner[better] = k
            reach[better] = near[better]
        keys = []
        for k, part in enumerate(parts):
            rows, cols = np.nonzero(part)
            radical = cols.mean() < side * 0.42 and cols.max() < side * 0.5
            keys.append((0 if radical else 1, rows.min() // max(1, side // 8), cols.mean(), k))
        order = [k for *_key, k in sorted(keys)]
        weights = [float(parts[k].sum()) ** 0.5 for k in order]
        when = TITLE_AT + index * TITLE_STEP
        for k, weight in zip(order, weights, strict=True):
            share = TITLE_EACH * weight / sum(weights)
            strokes.append((when, share, *_stroke(m * (owner == k), origin, u, index * 31 + k)))
            when += share
    seal = QPointF(cx, top + step * (len(TITLE) - 1) + size + 28 * u)
    scroll = QRectF(cx - 37 * u, 20 * u, 74 * u, seal.y() + 32 * u)
    return {"strokes": strokes, "scroll": _hanging(scroll, u), "seal": _seal(seal, u), "at": seal}


def _stroke(ink: np.ndarray, origin: QPointF, u: float, seed: int) -> tuple:
    """One stroke per pixel: ink pooling darker at its edges, the brush's hairs dragging dry toward
    its end, a faint bleed into the paper round it. With where it goes, how far along the brush's
    way each pixel is (0..1) and its finished picture."""
    rows, cols = np.nonzero(ink > 0.05)
    pad = max(2, round(2 * u))
    r0, r1 = max(0, rows.min() - pad), min(ink.shape[0], rows.max() + pad + 1)
    c0, c1 = max(0, cols.min() - pad), min(ink.shape[1], cols.max() + pad + 1)
    a = ink[r0:r1, c0:c1]
    h, w = a.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    weight = a / max(1e-6, float(a.sum()))
    mx, my = float((xs * weight).sum()), float((ys * weight).sum())
    cov = np.cov(np.vstack([(xs - mx).ravel(), (ys - my).ravel()]), aweights=a.ravel() + 1e-6)
    vals, vecs = np.linalg.eigh(cov)
    ax, ay = vecs[:, -1]
    if vals[-1] < vals[0] * 2.2:
        # A blob more round than long: written top down, a little left to right.
        ax, ay = 0.3, 0.95
    if ax + ay < 0:
        ax, ay = -ax, -ay
    proj = (xs - mx) * ax + (ys - my) * ay
    inside = a > 0.2
    lo, hi = float(proj[inside].min()), float(proj[inside].max())
    way = np.clip((proj - lo) / max(1e-6, hi - lo), 0, 1)
    across = (xs - mx) * -ay + (ys - my) * ax
    hairs = _sample(noise(64, 64, 1.6, 2, seed), across / 0.9 + 20, way * 3.0)
    dry = smooth(0.6, 0.98, way) * smooth(0.52, 0.72, hairs)
    pool = np.clip((a - blur(a, 1.4 * u)) * 2.2, 0, 1)
    grain = noise(w, h, 1.3, 2, seed + 3)
    color = _mix(rgb(INK), rgb("#3e5d55"), np.clip(0.12 * (1 - pool) + 0.25 * dry + 0.1 * grain, 0, 1))
    color = _mix(color, rgb("#0b1412"), pool * 0.55)
    alpha = a * (1 - 0.5 * dry) * (0.94 + 0.06 * grain)
    bleed = blur(a, 1.6 * u) * 0.25
    alpha = np.maximum(alpha, bleed)
    rect = QRectF(origin.x() + c0, origin.y() + r0, w, h)
    return rect, color, alpha, way, picture(color, alpha)


def _hanging(rect: QRectF, u: float) -> dict:
    """The hanging scroll per pixel, unrolled: rice paper (grain and fibres, a gold hairline round
    it) mounted in jade silk with a faint damask, a broader band of it at the head and the foot, a
    thin dark rod at its top; the roller at its foot, jade lit from the left with gold caps, as a
    picture of its own to carry down as it unrolls; and the soft shadow it casts."""
    w, h = max(4, round(rect.width())), max(4, round(rect.height()))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    head, foot, border = 26 * u, 22 * u, 6 * u
    paper = (xs > border) & (xs < w - border) & (ys > head) & (ys < h - foot)
    paper = blur(paper.astype(np.float32), 0.5)
    grain = noise(w, h, 1.2, 2, 101)
    fibre = _streaks(h, w, 0.9, 10, 102)
    damask = noise(w, h, 5.0 * u, 2, 103)
    weave = 0.5 + 0.5 * np.sin(xs * 1.7) * np.sin(ys * 1.7)
    silk = rgb(JADE) * (0.88 + 0.1 * smooth(0.5, 0.75, damask) + 0.02 * weave + 0.04 * grain)[..., None]
    silk = _mix(silk, rgb("#174d3c"), smooth(w * 0.35, 0, np.minimum(xs, w - xs)) * 0.25)
    sheet = rgb(PAPER) * (0.95 + 0.06 * grain + 0.05 * (fibre - 0.5))[..., None]
    sheet = _mix(sheet, rgb("#e2d6b2"), smooth(0.35, 0.0, np.minimum(ys / h, 1 - ys / h) * 3) * 0.3)
    color = _mix(silk, sheet, paper)
    hairline = np.clip(blur(paper, 0.45 * u) * 1.9, 0, 1) * (1 - paper)
    color = _mix(color, rgb(GOLD) * 1.05, np.clip(hairline * 1.5, 0, 1))
    rod = smooth(3.5 * u, 2.5 * u, ys)
    color = _mix(color, rgb("#1b2a26"), rod)
    alpha = np.ones((h, w), dtype=np.float32) * 0.97
    body = picture(color, alpha)
    # The roller, wider than the scroll, a little taller than the foot band's edge.
    rw, rh = round(w + 16 * u), max(4, round(9 * u))
    ry, rx = np.mgrid[0:rh, 0:rw].astype(np.float32)
    across = (ry + 0.5) / rh * 2 - 1
    curve = np.sqrt(np.clip(1 - across * across, 0, 1))
    caps = (rx < 7 * u) | (rx > rw - 7 * u)
    jade = _mix(rgb("#123c30"), rgb("#a6e3c6"), np.clip(0.2 + 0.7 * curve - 0.35 * across, 0, 1))
    gold = _mix(rgb("#7c5e1f"), rgb("#fbecb4"), np.clip(0.2 + 0.7 * curve - 0.35 * across, 0, 1))
    roll_c = np.where(caps[..., None], gold, jade) + (np.exp(-((across + 0.45) / 0.2) ** 2) * 0.3)[..., None]
    ends = smooth(0, 1.5, np.minimum(rx, rw - rx))
    roller = picture(roll_c, smooth(1.0, 0.75, np.abs(across)) * ends)
    # The shadow under it all.
    pad = round(14 * u)
    sh = np.zeros((h + 2 * pad, w + 2 * pad), dtype=np.float32)
    sh[pad + round(3 * u) : pad + h + round(3 * u), pad + round(2 * u) : pad + w + round(2 * u)] = 1
    shadow = picture(np.zeros(sh.shape + (3,), np.float32), blur(sh, 5 * u) * 0.45)
    return {"rect": QRectF(rect.left(), rect.top(), w, h), "body": body, "roller": roller, "shadow": shadow, "pad": pad}


def _seal(at: QPointF, u: float) -> tuple[QRectF, QImage]:
    """The red seal: 嘉宾 cut in white from a block of seal red, its ink uneven and speckled where the
    paper did not take it, its edge a little rough."""
    scale = 2.0
    sw, sh = 20 * u, 38 * u
    w, h = math.ceil((sw + 8 * u) * scale), math.ceil((sh + 8 * u) * scale)
    block = QRectF((w / scale - sw) / 2, (h / scale - sh) / 2, sw, sh)

    def stone(q: QPainter) -> None:
        q.scale(scale, scale)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawRoundedRect(block, 1.5 * u, 1.5 * u)

    def cut(q: QPainter) -> None:
        q.scale(scale, scale)
        font = _kai(sw * 0.84)
        font.setBold(True)
        for i, glyph in enumerate(SEAL_TEXT):
            path = QPainterPath()
            path.addText(QPointF(0, 0), font, glyph)
            box = path.boundingRect()
            q.save()
            q.translate(block.center().x() - box.center().x(), block.top() + sh * (0.27 + 0.46 * i) - box.center().y())
            q.setPen(Qt.NoPen)
            q.setBrush(Qt.white)
            q.drawPath(path)
            q.restore()

    body = mask(w, h, stone)
    rough = noise(w, h, 2.0 * scale, 2, 81)
    body = np.clip(body * 1.6 - 0.3 - 0.5 * (rough - 0.5) * (body < 0.98), 0, 1)
    chars = mask(w, h, cut)
    speck = smooth(0.72, 0.84, noise(w, h, 1.2 * scale, 2, 83))
    press = noise(w, h, 9 * u * scale, 2, 84)
    alpha = body * (1 - chars) * (0.82 + 0.18 * press) * (1 - 0.5 * speck)
    color = _mix(rgb(SEAL), rgb("#8f2018"), np.clip(press * 0.6, 0, 1))
    image = picture(color, alpha)
    image.setDevicePixelRatio(scale)
    return QRectF(at.x() - w / scale / 2, at.y() - h / scale / 2, w / scale, h / scale), image


def _title_paint(p: QPainter, t: float, title: dict, life: float) -> None:
    """The scroll unrolls down from its rod, each stroke is brushed along its way, and the seal is
    pressed."""
    k = ease_out(win(t, TITLE_AT - 0.32, TITLE_AT + 0.12))
    if k <= 0:
        return
    scroll = title["scroll"]
    rect = scroll["rect"]
    shown = max(1.0, rect.height() * k)
    p.setOpacity(life * min(1.0, k * 5))
    pad = scroll["pad"]
    shadow = scroll["shadow"]
    p.drawImage(QRectF(rect.left() - pad, rect.top() - pad, shadow.width(), shown + 2 * pad), shadow,
                QRectF(0, 0, shadow.width(), shown + 2 * pad))  # fmt: skip
    p.drawImage(QRectF(rect.left(), rect.top(), rect.width(), shown), scroll["body"], QRectF(0, 0, rect.width(), shown))
    roller = scroll["roller"]
    p.drawImage(QRectF(rect.center().x() - roller.width() / 2, rect.top() + shown - roller.height() * 0.6, roller.width(), roller.height()), roller)
    p.setOpacity(life)
    for when, share, box, color, alpha, way, done in title["strokes"]:
        k = win(t, when, when + share)
        if k <= 0:
            continue
        if k >= 1:
            p.drawImage(box, done)
            continue
        k = ease_in_out(k) * 1.04
        p.drawImage(box, picture(color, alpha * smooth(k + 0.05, k - 0.02, way)))
    k = win(t, STAMP, STAMP + 0.12)
    if k > 0:
        rect, image = title["seal"]
        grow = 1 + 0.35 * (1 - ease_out(k))
        p.setOpacity(life * ease_out(k))
        at = title["at"]
        p.drawImage(QRectF(at.x() - rect.width() * grow / 2, at.y() - rect.height() * grow / 2, rect.width() * grow, rect.height() * grow), image)
    p.setOpacity(life)


# The 嘉宾 marks -------------------------------------------------------------------------------

_MADE: dict[tuple, object] = {}


def _kept(key: tuple, build: Callable[[], object]):  # noqa: ANN202
    if key not in _MADE:
        _MADE[key] = build()
    return _MADE[key]


def _sharpness(p: QPainter) -> float:
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return round(max(1.0, ratio * math.hypot(p.transform().m11(), p.transform().m12())), 2)


def _scroll(rect: QRectF, scale: float) -> QImage:
    """The card per pixel: a strip of rice paper mounted in jade silk (a faint damask in it, a gold
    hairline where it meets the paper), jade rollers capped in gold at either end and a tiny red seal
    in the paper's bottom right corner."""
    w, h = max(4, math.ceil(rect.width() * scale)), max(4, math.ceil(rect.height() * scale))
    body = QRectF(0, CARD_TOP, rect.width(), rect.height() - CARD_TOP)
    roll = 9.0
    silk = body.adjusted(roll - 2, 1, -roll + 2, -1)
    paper = silk.adjusted(4, 4, -4, -4)

    def shape(area: QRectF, radius: float = 1.5) -> Callable[[QPainter], None]:
        def draw(q: QPainter) -> None:
            q.scale(scale, scale)
            q.setPen(Qt.NoPen)
            q.setBrush(Qt.white)
            q.drawRoundedRect(area, radius, radius)

        return draw

    def rollers(q: QPainter) -> None:
        q.scale(scale, scale)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        for x in (body.left() + 1, body.right() - roll + 1):
            q.drawRoundedRect(QRectF(x, body.top(), roll - 2, body.height()), 3, 3)

    def caps(q: QPainter) -> None:
        q.scale(scale, scale)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        for x in (body.left() + 1, body.right() - roll + 1):
            q.drawRoundedRect(QRectF(x - 0.5, body.top(), roll - 1, 3.5), 1.5, 1.5)
            q.drawRoundedRect(QRectF(x - 0.5, body.bottom() - 3.5, roll - 1, 3.5), 1.5, 1.5)

    mount, sheet, rod, cap = (mask(w, h, draw) for draw in (shape(silk), shape(paper, 0.8), rollers, caps))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    grain = noise(w, h, 1.2 * scale, 2, 61)
    fibre = _streaks(h, w, 0.9 * scale, 8, 62)
    damask = 0.5 + 0.5 * np.sin(xs / scale * 0.9) * np.sin(ys / scale * 0.9)
    color = rgb(JADE) * (0.9 + 0.12 * damask + 0.05 * grain)[..., None]
    color = _mix(color, rgb("#8fd1b0"), smooth(silk.top() * scale + 3 * scale, silk.top() * scale, ys) * 0.35)
    gold_line = np.clip(blur(sheet, 0.6 * scale) * 1.6, 0, 1) - sheet
    color = _mix(color, rgb(GOLD), np.clip(gold_line * 1.8, 0, 1))
    paper_c = rgb(PAPER) * (0.95 + 0.06 * grain + 0.04 * (fibre - 0.5))[..., None]
    paper_c = _mix(paper_c, rgb("#e6dab8"), smooth(0.25, 0.0, np.minimum(ys / h, 1 - ys / h)) * 0.25)
    color = _mix(color, paper_c, sheet)
    # Rollers: jade rods lit from the left, gold caps.
    ux = np.zeros_like(xs)
    for x in (body.left() + 1, body.right() - roll + 1):
        inside = (xs >= x * scale) & (xs < (x + roll - 2) * scale)
        ux = np.where(inside, (xs - x * scale) / ((roll - 2) * scale) * 2 - 1, ux)
    curve = np.sqrt(np.clip(1 - ux * ux, 0, 1))
    rod_c = _mix(rgb("#164a3a"), rgb("#9fe0c0"), np.clip(0.25 + 0.6 * curve - 0.35 * ux, 0, 1))
    rod_c = rod_c + (np.exp(-((ux + 0.35) / 0.18) ** 2) * 0.35)[..., None]
    color = _mix(color, rod_c, rod)
    cap_c = _mix(rgb("#8a6a26"), rgb("#fbecb4"), np.clip(0.3 + 0.6 * curve - 0.3 * ux, 0, 1))
    color = _mix(color, cap_c, cap)
    alpha = np.maximum.reduce([mount * 0.97, sheet, rod, cap])
    # A tiny seal in the paper's corner.
    sx0, sy0 = (paper.right() - 9) * scale, (paper.bottom() - 9) * scale
    stamp = ((xs > sx0) & (xs < sx0 + 5.5 * scale) & (ys > sy0) & (ys < sy0 + 5.5 * scale)).astype(np.float32)
    stamp = blur(stamp, 0.3 * scale) * (0.8 + 0.2 * grain)
    hollow = ((np.abs(xs - sx0 - 2.75 * scale) < 0.45 * scale) | (np.abs(ys - sy0 - 2.75 * scale) < 0.45 * scale)).astype(np.float32)
    color = _mix(color, rgb(SEAL), stamp * (1 - hollow * 0.8) * 0.9)
    image = picture(color, alpha)
    image.setDevicePixelRatio(scale)
    return image


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """A rice-paper scroll mounted in jade silk, rolled on jade rods at its ends, with a small seal."""
    scale = _sharpness(p)
    image = _kept(("card", round(rect.width(), 1), round(rect.height(), 1), scale), lambda: _scroll(rect, scale))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(rect, image)


def lead(size: float, index: int) -> QPixmap:
    """A small bamboo leaf before each name, malachite and jade in turn."""
    scale = 3.0
    sprite = _kept(("lead", round(size, 2), index % 2), lambda: _leaf((MALACHITE, JADE)[index % 2], size * 1.05)[0])
    image = QImage(math.ceil(size * scale), math.ceil(size * scale), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.scale(scale, scale)
    _put(q, sprite, size / 2, size / 2, -38)
    q.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def _ring_line(cover: QRectF, window: QRectF, radius: float, scale: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The line round the button the ring's ribbon follows, in the window's pixels, evenly spaced."""
    path = QPainterPath()
    path.addRoundedRect(cover.adjusted(1, 1, -1, -1), radius, radius)
    count = 300
    pts = np.array([[path.pointAtPercent(i / count).x(), path.pointAtPercent(i / count).y()] for i in range(count + 1)])
    pts = _even((pts - [window.left(), window.top()]) * scale, path.length() * scale / count)
    return pts, _along(pts) / scale, _normals(pts)


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A jade silk ribbon round the button, twisting as it flutters, its gold thread catching the light."""
    scale = _sharpness(p)
    u = scale
    silk_w = 8.0
    levels, half, tw = _kept(("ring-silk", scale), lambda: _silk(MALACHITE, "#16503f", "#d6f6e6", silk_w * scale, u, 21))
    window = cover.adjusted(-9, -9, 9, 9)
    w, h = math.ceil(window.width() * scale), math.ceil(window.height() * scale)
    layer = _kept(("ring-layer", w, h), lambda: QImage(w, h, QImage.Format_ARGB32_Premultiplied))
    radius = min(cover.height() * 0.3, 18.0)
    pts, s, normals = _kept(("ring-line", cover.x(), cover.y(), cover.width(), cover.height(), scale), lambda: _ring_line(cover, window, radius, scale))
    wave = 1.8 * np.sin(TAU * (s / 46 - 0.7 * t)) + 0.6 * np.sin(TAU * (s / 130 + 0.3 * t))
    pts = pts + normals * (wave * scale)[:, None]
    theta = 1.1 * np.sin(TAU * (s / 60 - 0.55 * t)) + 0.5 * np.sin(TAU * (s / 190 + 0.2 * t))
    layer.fill(Qt.transparent)
    q = QPainter(layer)
    q.setCompositionMode(QPainter.CompositionMode_Source)
    _lay(q, pts[:, 0], pts[:, 1], s * scale, theta, np.full(len(s), silk_w * scale), levels, half, tw)
    q.end()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(window, layer)


def _pendant(side: float, scale: float) -> QImage:
    """The 玉佩 per pixel: a jade 璧 disc, translucent and glowing from within where it is thickest,
    clouded, its face raised in 谷纹 grain bumps between two carved rings, lit from the top left; a
    silk cord down to it through a small knot."""
    w = h = math.ceil(side * scale)
    cx, cy = side / 2, side * 0.43
    outer, inner = side * 0.3, side * 0.095
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = xs / scale - cx, ys / scale - cy
    r = np.hypot(x, y)
    mid, band = (outer + inner) / 2, (outer - inner) / 2
    q = (r - mid) / band
    disc = smooth(1.0 + 0.6 / (band * scale), 1.0 - 0.6 / (band * scale), np.abs(q))
    height = np.sqrt(np.clip(1 - q * q, 0, 1)) * 0.6
    # 谷纹: little raised grains in rows round the disc, between the carved rings.
    ang = np.arctan2(y, x)
    rows = np.clip((r - inner - band * 0.35) / (band * 1.3), 0, 1)
    grains = (0.5 + 0.5 * np.cos(ang * 18 + (rows > 0.5) * math.pi / 18 * 9)) * (0.5 + 0.5 * np.cos(rows * TAU * 1.0))
    grains = grains**3 * smooth(0.82, 0.6, np.abs(q))
    height = height + grains * 0.18
    groove = np.exp(-((np.abs(q) - 0.74) / 0.06) ** 2)
    height = height - groove * 0.12
    gy, gx = np.gradient(height * scale * 3)
    nz = np.ones_like(gx)
    norm = np.sqrt(gx * gx + gy * gy + nz)
    nx_, ny_, nz_ = -gx / norm, -gy / norm, nz / norm
    diffuse = np.clip(nx_ * LIGHT[0] + ny_ * LIGHT[1] + nz_ * LIGHT[2], 0, 1)
    spec = np.clip(nx_ * HALF[0] + ny_ * HALF[1] + nz_ * HALF[2], 0, 1) ** 40
    cloud = noise(w, h, 4 * scale, 3, 71)
    glow = np.sqrt(np.clip(1 - q * q, 0, 1))
    color = _mix(rgb("#1d6b50"), rgb("#9fe0c2"), np.clip(0.2 + 0.55 * glow + 0.25 * (cloud - 0.5), 0, 1))
    color = _mix(color, rgb("#e8fbef"), smooth(0.6, 0.85, cloud) * 0.3)
    color = color * (0.72 + 0.4 * diffuse)[..., None] + (spec * 0.8)[..., None]
    color = _mix(color, rgb("#0f3a2c"), groove * 0.4)
    alpha = disc * (0.9 + 0.1 * glow)

    def cord(q2: QPainter) -> None:
        q2.scale(scale, scale)
        q2.setPen(QPen(Qt.white, max(0.8, side * 0.022), Qt.SolidLine, Qt.RoundCap))
        knot = QPointF(cx, side * 0.065)
        q2.drawLine(QPointF(cx, 0), knot)
        q2.drawLine(knot, QPointF(cx, cy - outer + 1))
        q2.setPen(QPen(Qt.white, max(0.8, side * 0.02)))
        q2.setBrush(Qt.NoBrush)
        q2.save()
        q2.translate(knot)
        q2.rotate(45)
        d = side * 0.045
        q2.drawRect(QRectF(-d, -d, 2 * d, 2 * d))
        q2.drawLine(QPointF(-d, 0), QPointF(d, 0))
        q2.drawLine(QPointF(0, -d), QPointF(0, d))
        q2.restore()

    string = mask(w, h, cord) * (1 - disc)
    color = _mix(color, rgb(JADE) * 0.85 + rgb(PALE) * 0.15, string)
    alpha = np.maximum(alpha, string * 0.95)
    image = picture(color, alpha)
    image.setDevicePixelRatio(scale)
    return image


def _tassel(side: float, scale: float) -> QImage:
    """The tassel under the 玉佩, hung from its top middle: a gold bead, then fine jade silk threads
    falling and fanning a little, their ends ragged."""
    tall = side * 0.28
    wide = side * 0.17
    w, h = math.ceil(wide * scale * 1.6), math.ceil(tall * scale)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = xs / scale - w / scale / 2, ys / scale
    bead_r = side * 0.035
    bead = smooth(bead_r + 0.5 / scale, bead_r - 0.5 / scale, np.hypot(x, y - bead_r * 1.2))
    fall = np.clip((y - bead_r * 2) / (tall - bead_r * 2), 0, 1)
    spread = wide * (0.28 + 0.32 * fall)
    threads = smooth(1.0, 0.85, np.abs(x) / spread) * (y > bead_r * 1.8)
    ends = noise(w, 1, 1.0 * scale, 1, 73)[0][None, :]
    threads = threads * smooth(1.0, 0.9, fall + 0.08 * ends)
    strands = 0.5 + 0.5 * np.sin(x * scale * 2.2 + 0.4 * np.sin(y * 0.5))
    color = _mix(rgb("#1f6b52"), rgb("#9fe0c2"), np.clip(0.35 + 0.4 * strands - 0.3 * np.abs(x) / np.maximum(spread, 1e-3), 0, 1))
    shine = np.clip(1 - np.hypot(x + bead_r * 0.4, y - bead_r * 0.8) / bead_r, 0, 1)
    color = _mix(color, _mix(rgb("#9a7629"), rgb("#fff1c0"), shine), bead)
    alpha = np.maximum(threads * (0.75 + 0.25 * strands), bead)
    image = picture(color, alpha)
    image.setDevicePixelRatio(scale)
    return image


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A jade 玉佩 hanging on its silk cord, swaying a little, its tassel swinging under it."""
    scale = max(2.0, _sharpness(p))
    side = box.width()
    pendant = _kept(("pendant", round(side, 1), scale), lambda: _pendant(side, scale))
    tassel = _kept(("tassel", round(side, 1), scale), lambda: _tassel(side, scale))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    sway = 5 * math.sin(t * 1.7)
    p.translate(box.left() + side / 2, box.top())
    p.rotate(sway)
    p.drawImage(QRectF(-side / 2, 0, side, side), pendant)
    p.translate(0, side * (0.43 + 0.3) - 1)
    p.rotate(9 * math.sin(t * 1.7 - 0.8))
    tw, th = tassel.width() / scale, tassel.height() / scale
    p.drawImage(QRectF(-tw / 2, 0, tw, th), tassel)
