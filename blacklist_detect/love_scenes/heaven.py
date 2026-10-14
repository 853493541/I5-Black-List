"""天国之门: golden clouds part on a sun at the top of the screen, its rays turning.

Two banks of golden cloud meet over the top of the title 推演成功 and slowly part, sliding under the
great clouds heaped in the two top corners; as the gate opens a sun burns through at the top edge
with a burst of light, and a radiant sunburst fans out from behind the title: soft regular rays and
long crepuscular shafts, turning slowly opposite ways, faint over the title's words and the names.
Pillars of light descend from the corner clouds down both sides, land in a glow at the bottom and
fill with sparkles spiralling up them; gold dust drifts in the rays. At the end the gate draws
partly closed, the pillars narrow and it all fades.

Its marks are gold too, all worked per pixel: the ring is a gilt rim round 准备案件还原 with soft
sun rays standing out from its edge, creeping round it and shimmering, glints running along the rim;
the badge is a gold sun (a domed boss in a field engraved with fine rays, a raised rim, long and
short rays) on a slowly turning radiance, a sheen crossing it; the card is an illuminated panel of
gold leaf, faintly crinkled and laid in squares, in a raised gilt frame with a row of punched dots,
a little gold sun rising on its top edge and a sheen crossing it now and then. A small gold sun
stands before each name.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QImage, QLinearGradient, QPainter, QPixmap, QRadialGradient, QTransform

from blacklist_detect.love_scenes.draw import (
    Wash,
    clamp,
    col,
    ease_in,
    ease_in_out,
    ease_out,
    gradient,
    soft_dot,
    star,
    win,
)
from blacklist_detect.love_scenes.light import blur, glow, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# Soft light throughout: drawn at one pixel per point and scaled up on a sharper screen.
MAX_RATIO = 1.0
HONEY = "#ffe2a0"
GOLD = "#f5c860"
SUNLIGHT = "#fff6dc"
LOOK = {
    "glow": (255, 208, 110),
    "rim": "#f2c255",
    "band": ("#fff0c0", "#eebb4c"),
    "card": ("#f4d27c", "#d9a540"),
    "edge": "#a8741e",
    "ink": "#3d2104",
    "flowers": (("#fffbe8", "#f8dc8a", "#d99a2b"), ("#fff6d8", "#f2cf72", "#c98a1e")),
    "disc": ("#fff6d8", "#f2c95c"),
    "heart": ("#ffe08a", "#d99a2b"),
    "deep": "#c98a1e",
    "deep_glow": (250, 200, 90),
}
MARKS_ANIMATED = True
# Room over the card for the sun rising on its top edge, and margins inside its gilt frame.
CARD_TOP = 15
CARD_PAD = (15, 9, 15, 9)
# Rays and the sun are soft: worked out at this share of the size and laid on scaled up.
SOFT = 0.25
# Clouds and pillars, a little finer.
HALF = 0.5
# Gold as metal shows it, from the shade away from the light to a white-hot highlight.
METAL = (
    (0.0, "#3b2105"),
    (0.3, "#8c5a12"),
    (0.52, "#d4a03c"),
    (0.7, "#f0c860"),
    (0.85, "#fde7a0"),
    (1.0, "#fffbea"),
)
# Where the light comes from on the marks: the upper left, a little in front.
LIGHT = np.array([-0.55, -0.7, 0.75], dtype=np.float32) / np.float32(math.sqrt(0.55**2 + 0.7**2 + 0.75**2))
_HALFWAY = LIGHT + np.array([0, 0, 1], dtype=np.float32)
SHINE = _HALFWAY / np.float32(np.linalg.norm(_HALFWAY))
# The marks' pictures, made once for each size and sharpness they are shown at.
_MADE: dict[tuple, object] = {}


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(29)
    sun = QPointF(width * 0.53, height * 0.004)
    heaven = Wash(lambda q, w, h: _heaven(q, w, h, sun, u))
    layers = (_sunburst(width, height, sun, u), _shafts(width, height, sun, u))
    glare = _sun_glare(sun, u)
    shade = _ray_mask(width, height, gap, u)
    doors, heaps = _clouds(width, height, u)
    pillars = _pillars(width, height, u, rnd)
    dust = _dust(width, height, sun, u, rnd)

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.2, 5.0))
        flash = _flash(t)
        opening = ease_in_out(win(t, 0.35, 1.9)) * (1 - 0.4 * ease_in_out(win(t, 4.0, 5.0)))
        p.save()
        p.setOpacity(life)
        heaven.paint(p, width, height, gap, ease_out(win(t, 0.0, 1.0)) * (1 - leave) * (0.85 + 0.3 * flash))
        _radiance(p, t, layers, glare, shade, sun, width, height, leave, flash)
        _doors(p, t, doors, width, opening, 1 - leave)
        for pillar in pillars:
            _pillar(p, t, pillar, u, leave)
        _heaps(p, t, heaps, u, 1 - leave)
        _burst(p, sun, u, flash)
        for pillar in pillars:
            _sparkles(p, t, pillar, u, 1 - leave)
        _motes(p, t, dust, u, (1 - leave) * ease_out(win(t, 0.8, 1.8)))
        p.restore()

    return paint


def _flash(t: float) -> float:
    """The light that bursts through as the gate opens: quick to come, slow to go."""
    return ease_out(win(t, 0.8, 1.1)) * (1 - ease_in_out(win(t, 1.1, 2.2)))


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


def _heaven(p: QPainter, width: float, height: float, sun: QPointF, u: float) -> None:
    """Warm gold light at the top, strongest round the sun, down the sides where the pillars fall and
    pooled in the bottom corners. Drawn once."""
    top = height * 0.32
    p.fillRect(QRectF(0, 0, width, top), gradient(QPointF(0, 0), QPointF(0, top), ((0, "#ffe6a8", 0.22), (0.4, "#ffd27a", 0.06), (1, "#ffd27a", 0))))
    side = 190 * u
    for start, end, rect in (
        (QPointF(0, 0), QPointF(side, 0), QRectF(0, 0, side, height)),
        (QPointF(width, 0), QPointF(width - side, 0), QRectF(width - side, 0, side, height)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, "#ffdf98", 0.2), (0.5, "#ffd27a", 0.06), (1, "#ffd27a", 0))))
    for cx, cy, r, alpha in ((sun.x() / width, sun.y() / height, 600, 0.4), (0.06, 1.0, 330, 0.2), (0.966, 1.0, 330, 0.2)):
        light = QRadialGradient(QPointF(width * cx, height * cy), r * u)
        light.setColorAt(0, col("#fff0c4", alpha))
        light.setColorAt(0.4, col("#ffd98a", alpha * 0.35))
        light.setColorAt(1, col("#ffd98a", 0))
        p.fillRect(QRectF(0, 0, width, height), light)


def _ray_box(width: float, height: float) -> QRectF:
    """Room round the stage for the rays to turn in."""
    margin = width * 0.12
    return QRectF(-margin, -margin, width + 2 * margin, height + margin)


def _polar(box: QRectF, sun: QPointF) -> tuple[np.ndarray, np.ndarray]:
    """Each pixel of box at SOFT size: how far from the sun and at what angle (0 straight down)."""
    w, h = max(1, round(box.width() * SOFT)), max(1, round(box.height() * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    dx, dy = box.left() + xs / SOFT - sun.x(), box.top() + ys / SOFT - sun.y()
    return np.hypot(dx, dy), np.arctan2(dx, dy)


def _sunburst(width: float, height: float, sun: QPointF, u: float) -> tuple[QRectF, QImage]:
    """The sunburst: regular soft wedges of gold light all round the sun, long ones and short ones in
    turn, white near the sun and gold further out, per pixel at SOFT size."""
    box = _ray_box(width, height)
    r, angle = _polar(box, sun)
    count = 32
    wedge = smooth(0.25, 0.95, 0.5 + 0.5 * np.cos(angle * count))
    long = (np.round(angle * count / (2 * math.pi)).astype(int) % 2) == 0
    reach = height * np.where(long, 1.05, 0.62)
    fall = smooth(30 * u, 160 * u, r) * (1 - smooth(0.0, reach, r)) ** 1.4
    strength = fall * wedge * 0.55
    tint = rgb("#ffcf70") + (rgb(SUNLIGHT) - rgb("#ffcf70")) * (1 - smooth(60 * u, 420 * u, r))[..., None]
    return box, glow(tint * strength[..., None])


def _shafts(width: float, height: float, sun: QPointF, u: float) -> tuple[QRectF, QImage]:
    """Crepuscular shafts: long uneven beams streaming from the sun, each its own width and length,
    fading as they go, per pixel at SOFT size."""
    box = _ray_box(width, height)
    r, angle = _polar(box, sun)
    rnd = np.random.default_rng(17)
    beams = 0.6 * _wave(angle, 0.05, rnd) + 0.4 * _wave(angle, 0.017, rnd)
    streak = smooth(0.45, 0.85, beams)
    reach = height * (0.55 + 0.7 * _wave(angle, 0.09, rnd))
    fall = smooth(40 * u, 180 * u, r) * (1 - smooth(0.0, reach, r)) ** 1.2
    # Out to the sides as much as down: a fan, not a spotlight.
    side = 0.55 + 0.45 * smooth(0.2, 0.9, np.abs(angle))
    strength = fall * side * (0.08 + 0.92 * streak) * 0.8
    tint = rgb("#ffd88a") + (rgb(SUNLIGHT) - rgb("#ffd88a")) * (streak * 0.5)[..., None]
    return box, glow(tint * strength[..., None])


def _sun_glare(sun: QPointF, u: float) -> tuple[QRectF, QImage]:
    """The sun at the top edge, per pixel at SOFT size: a white-hot disc, a gold corona spiked with
    fine streaks, and a wide bloom."""
    reach = 420 * u
    box = QRectF(sun.x() - reach, sun.y() - reach, 2 * reach, 2 * reach)
    r, angle = _polar(box, sun)
    rnd = np.random.default_rng(5)
    disc = 32 * u
    core = 1 - smooth(disc * 0.8, disc * 1.15, r)
    spikes = 0.45 + 0.55 * smooth(0.3, 0.9, 0.6 * _wave(angle, 0.04, rnd) + 0.4 * _wave(angle, 0.013, rnd))
    corona = np.exp(-np.maximum(r - disc, 0) / (46 * u)) * (0.55 + 0.45 * spikes)
    bloom = (np.exp(-r / (150 * u)) * 0.5 + np.exp(-r / (330 * u)) * 0.22) * (1 - smooth(reach * 0.6, reach, r))
    light = rgb("#fffaf0") * (core * 1.6)[..., None] + rgb("#ffd36e") * (corona * 0.95 + bloom)[..., None]
    return box, glow(light)


def _ray_mask(width: float, height: float, gap: QRectF, u: float) -> QImage:
    """Where the light from the sun may show, at SOFT size: faint over the names, softer over the
    title's lines, fainter still over its words, none over the gap."""
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = xs / SOFT, ys / SOFT
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    words = QRectF(width * 0.43, height * 0.085, width * 0.2, height * 0.115).adjusted(-14 * u, -10 * u, 14 * u, 8 * u)
    lines = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.24)
    keep = (1 - 0.72 * _box(x, y, names, 60 * u)) * (1 - 0.25 * _box(x, y, lines, 90 * u)) * (1 - 0.5 * _box(x, y, words, 60 * u))
    keep = keep * (1 - _box(x, y, gap.adjusted(-20 * u, -20 * u, 20 * u, 20 * u), 50 * u))
    return picture(np.ones((h, w, 3), dtype=np.float32), keep)


def _radiance(p: QPainter, t: float, layers: tuple, glare: tuple, shade: QImage, sun: QPointF, width: float, height: float, leave: float, flash: float) -> None:
    """The sunburst and the shafts fanning out from the sun as the gate opens and turning slowly
    opposite ways, and the sun itself, added up on a small picture, cut to where they may show and
    laid on scaled up."""
    fan = ease_out(win(t, 0.7, 2.1))
    burn = ease_out(win(t, 0.45, 1.4))
    if fan <= 0.01 and burn <= 0.01:
        return
    small = QImage(shade.width(), shade.height(), QImage.Format_ARGB32_Premultiplied)
    small.fill(Qt.transparent)
    q = QPainter(small)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.setCompositionMode(QPainter.CompositionMode_Plus)
    q.scale(SOFT, SOFT)
    grow = 0.35 + 0.65 * fan
    for index, (box, image) in enumerate(layers):
        turn = (3.2 if index == 0 else -1.9) * t + (0 if index == 0 else 1.5 * math.sin(t * 0.8))
        breathe = 0.82 + 0.18 * math.sin(t * (1.3 - 0.4 * index) + index * 2.1)
        q.save()
        q.translate(sun)
        q.rotate(turn)
        q.scale(grow, grow)
        q.translate(-sun)
        q.setOpacity(clamp(fan * (1 - leave) * (breathe + 0.8 * flash)))
        q.drawImage(box, image)
        q.restore()
    box, image = glare
    q.setOpacity(clamp(burn * (1 - leave * 0.9) * (0.88 + 0.12 * math.sin(t * 2.3) + 0.5 * flash)))
    q.drawImage(box, image)
    q.resetTransform()
    q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    q.setOpacity(1.0)
    q.drawImage(0, 0, shade)
    q.end()
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, width, height), small)
    p.restore()


def _cloud(w: int, h: int, puffs: list[tuple[float, float, float]], seed: int, outer: float, g: float) -> QImage:
    """A bank of golden cloud per pixel, its inner end toward the sun on the right: round billows,
    their edges frayed with noise, warm white where the sunlight falls on them, honey and amber in
    their shade, their edges toward the sun burning bright, with a soft gold glow round them; its
    inner end, and its outer end over outer of its width, fading away. g is the size of its billows, in pixels."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    # Billows warped out of round and melted into one another, never a row of balls.
    wx = xs + (noise(w, h, g * 0.5, 3, seed + 7) - 0.5) * g * 0.45
    wy = ys + (noise(w, h, g * 0.5, 3, seed + 8) - 0.5) * g * 0.3
    melt = g * 0.07
    total = np.zeros((h, w), dtype=np.float32)
    for cx, cy, r in puffs:
        d = np.sqrt((wx - cx) ** 2 + (wy - cy) ** 2) / r
        total += np.exp((r * np.where(d < 1, np.sqrt(np.clip(1 - d * d, 0, 1)), 1 - d) - g) / melt)
    field = g + melt * np.log(total + 1e-30)
    field = field + (noise(w, h, g * 0.16, 2, seed) - 0.5) * g * 0.1 + (noise(w, h, g * 0.4, 2, seed + 3) - 0.5) * g * 0.16
    cover = smooth(-g * 0.05, g * 0.12, field)
    thick = smooth(0.0, g * 0.45, field)
    gy, gx = np.gradient(blur(np.maximum(field, 0), max(1.0, g * 0.025)))
    norm = np.sqrt(gx * gx + gy * gy + 1)
    nx, ny, nz = -gx / norm, -gy / norm, 1 / norm
    # Lit from the sun: above, toward the inner end, and from behind; wrapped, as light through vapour.
    lx, ly, lz = 0.5, -0.7, 0.5
    facing = (nx * lx + ny * ly + nz * lz) / math.sqrt(lx * lx + ly * ly + lz * lz)
    lit = np.clip(facing * 0.5 + 0.5, 0, 1) ** 1.8
    lit = np.clip(lit * (0.88 + 0.24 * noise(w, h, g * 0.08, 3, seed + 40)), 0, 1)
    color = rgb("#cf9246") + (rgb("#efbc68") - rgb("#cf9246")) * smooth(0.05, 0.45, lit)[..., None]
    color = color + (rgb("#fde0a2") - color) * smooth(0.35, 0.75, lit)[..., None]
    color = color + (rgb("#fff8e8") - color) * smooth(0.7, 1.0, lit)[..., None]
    # The silver lining, in gold: the thin edge toward the sun.
    edge = (1 - smooth(-g * 0.02, g * 0.12, field)) * smooth(-g * 0.07, g * 0.02, field)
    toward = np.clip(nx * 0.8 - ny * 0.6, 0, 1)
    rim = blur(edge * toward, max(1.0, g * 0.012))
    color = color + (rgb("#fffaf0") * 1.1 - color) * np.clip(rim * 3.2, 0, 0.95)[..., None]
    alpha = np.clip(cover * (0.62 + 0.33 * thick) + rim * 0.4, 0, 1)
    halo = blur(cover, g * 0.08) * 0.4
    total = alpha + halo * (1 - alpha)
    color = (color * alpha[..., None] + rgb(HONEY) * (halo * (1 - alpha))[..., None]) / np.maximum(total, 1e-4)[..., None]
    fade = (1 - smooth(0.9, 1.0, ys / h)) * (1 - smooth(0.92, 1.0, xs / w))
    if outer > 0:
        fade = fade * smooth(0.0, outer, xs / w)
    return picture(color, total * fade)


def _clouds(width: float, height: float, u: float) -> tuple[list[tuple], list[tuple]]:
    """The gate's two doors, low banks along the top that meet over the title and part, and the great
    clouds heaped in the two top corners, at HALF size: (side, where, picture)."""
    rnd = np.random.default_rng(3)
    doors, heaps = [], []
    for side, seed in ((-1, 21), (1, 22)):
        w, h = max(8, round(width * 0.33 * HALF)), max(8, round(height * 0.105 * HALF))
        puffs = [(k * w * 0.82 + rnd.normal(0, 0.015) * w, rnd.uniform(-0.35, 0.0) * h, rnd.uniform(0.45, 0.8) * h) for k in np.linspace(0, 1, 14)]
        puffs += [(k * w * 0.8 + rnd.normal(0, 0.02) * w, rnd.uniform(0.3, 0.52) * h, rnd.uniform(0.16, 0.32) * h) for k in np.linspace(0.03, 0.97, 11)]
        puffs += [(w * 0.8, h * 0.15, h * 0.5), (w * 0.85, h * 0.42, h * 0.26)]
        image = _cloud(w, h, puffs, seed, 0.12, height * 0.3 * HALF)
        doors.append((side, QSizeF(width * 0.33, height * 0.105), image if side < 0 else _flip(image)))
    for side, seed in ((-1, 31), (1, 32)):
        w, h = max(8, round(width * 0.34 * HALF)), max(8, round(height * 0.3 * HALF))
        puffs = [(rnd.uniform(-0.05, 0.15) * w, rnd.uniform(-0.3, -0.05) * h, rnd.uniform(0.55, 0.7) * h) for _ in range(2)]
        puffs += [(rnd.uniform(0.3, 0.55) * w, -0.32 * h, 0.5 * h), (rnd.uniform(0.6, 0.8) * w, -0.4 * h, 0.42 * h)]
        for k in sorted(rnd.uniform(0, 1, 22)):
            x = (k * 0.95 + rnd.normal(0, 0.025)) * w
            y = (0.62 * (1 - k) ** 1.3 + 0.04 + rnd.normal(0, 0.05)) * h
            puffs.append((x, y, (0.2 * (1 - k) + 0.07) * h * rnd.uniform(0.6, 1.4)))
        image = _cloud(w, h, puffs, seed, 0.0, height * 0.3 * HALF)
        margin = 14 * u
        rect = QRectF(-margin if side < 0 else width * 0.66, 0, width * 0.34 + margin, height * 0.3)
        heaps.append((side, rect, image if side < 0 else _flip(image)))
    return doors, heaps


def _flip(image: QImage) -> QImage:
    """The picture as in a mirror, left for right."""
    return image.transformed(QTransform().scale(-1, 1))


def _doors(p: QPainter, t: float, doors: list[tuple], width: float, opening: float, a: float) -> None:
    """The gate: the two low banks meet just past the sun and slide apart under the corner clouds,
    each bobbing a little."""
    if a <= 0.01:
        return
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setOpacity(p.opacity() * a)
    for index, (side, size, image) in enumerate(doors):
        inner = width * (0.58 if side < 0 else 0.48) + side * width * 0.2 * opening
        left = inner - size.width() if side < 0 else inner
        bob = size.height() * 0.03 * math.sin(t * 1.1 + index * 2)
        p.drawImage(QRectF(left, bob - size.height() * 0.04, size.width(), size.height()), image)
    p.restore()


def _heaps(p: QPainter, t: float, heaps: list[tuple], u: float, a: float) -> None:
    """The corner clouds, drifting slowly outward."""
    if a <= 0.01:
        return
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setOpacity(p.opacity() * a)
    for side, rect, image in heaps:
        drift = side * 14 * u * (t / DURATION) + 3 * u * math.sin(t * 0.9 + side)
        p.drawImage(rect.translated(drift, 0), image)
    p.restore()


def _burst(p: QPainter, sun: QPointF, u: float, flash: float) -> None:
    """The light bursting through the opening gate, wide and low, kept above the title's words."""
    if flash <= 0.02:
        return
    p.save()
    p.translate(sun)
    p.scale(1, 0.38)
    soft_dot(p, 0, 0, 260 * u, "#ffffff", 0.5 * flash)
    soft_dot(p, 0, 0, 520 * u, HONEY, 0.4 * flash)
    p.restore()


def _beam(w: int, h: int, seed: int) -> QImage:
    """A pillar of light per pixel, w across and h tall: a white-hot core in a gold body and a wide
    haze, streaked along its length like light through dust, coming on from the top and fading out
    at its foot."""
    rnd = np.random.default_rng(seed)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    down = ys / h
    # Light spreads as it falls: narrow under the cloud, broader at its foot.
    across = (xs - w / 2) / w / (0.72 + 0.28 * down)
    # Streaks that fan out with it, fading in and out along its length, as light through dust.
    streaks = (1 - down) * _wave(across * w, w * 0.06, rnd) + down * _wave(across * w, w * 0.045, rnd)
    streaks = 0.62 + 0.38 * smooth(0.2, 0.85, streaks)
    swell = 0.78 + 0.22 * _wave(ys[:, :1] + across * w * 0.8, h * 0.16, rnd)
    core = np.exp(-((across / 0.12) ** 2))
    body = np.exp(-((across / 0.24) ** 2)) * streaks * swell
    haze = np.exp(-((across / 0.45) ** 2))
    along = smooth(0.0, 0.08, down) * (1 - smooth(0.78, 1.0, down)) * (1 - 0.4 * down)
    light = rgb(SUNLIGHT) * (core * 0.38 * swell)[..., None] + rgb("#ffd27a") * (body * 0.85 + haze * 0.2)[..., None]
    return glow(light * along[..., None])


def _pillars(width: float, height: float, u: float, rnd: random.Random) -> list[dict]:
    """The pillars of light down the two sides, and the sparkles that rise in them."""
    out = []
    top, foot = height * 0.07, height * 0.975
    for at, wide, strength, start, seed in ((0.058, 200, 1.0, 1.15, 3), (0.966, 170, 0.95, 1.35, 5)):
        w = wide * u
        image = _beam(max(4, round(w * HALF)), max(8, round((foot - top) * HALF)), seed)
        rising = [
            (start + 0.4 + rnd.uniform(0, 3.0), rnd.uniform(0, 6.28), rnd.uniform(0.1, 0.36) * w, rnd.uniform(70, 150) * u, rnd.uniform(2.6, 6.0) * u, rnd.uniform(1.6, 2.8))
            for _ in range(24)
        ]
        twinkles = [(rnd.uniform(0.2, 0.92), rnd.uniform(-0.35, 0.35), start + 0.5 + rnd.uniform(0, 2.9), rnd.uniform(0.5, 0.9), rnd.uniform(6, 11) * u) for _ in range(8)]
        out.append({"x": width * at, "w": w, "top": top, "foot": foot, "image": image, "turned": _flip(image), "strength": strength, "start": start, "rising": rising, "twinkles": twinkles})
    return out


def _pillar(p: QPainter, t: float, pillar: dict, u: float, leave: float) -> None:
    """A pillar descending from the clouds: its bright front comes down, it lands in a glow and
    shimmers, its streaks shifting as a turned copy of it comes and goes; leaving, it narrows and
    fades."""
    start = pillar["start"]
    down = ease_in_out(win(t, start, start + 0.6))
    if down <= 0 or leave >= 1:
        return
    x, w, top, foot, strength = pillar["x"], pillar["w"], pillar["top"], pillar["foot"], pillar["strength"]
    a = strength * (1 - leave)
    breathe = 0.86 + 0.14 * math.sin(t * 1.7 + x)
    narrow = w * (1 - 0.55 * leave)
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    base = p.opacity() * a * breathe
    shimmer = 0.5 + 0.5 * math.sin(t * 1.3 + x * 0.01)
    where = QRectF(x - narrow / 2, top, narrow, (foot - top) * down)
    p.setOpacity(base * (1 - 0.45 * shimmer))
    p.drawImage(where, pillar["image"])
    p.setOpacity(base * 0.45 * shimmer)
    p.drawImage(where, pillar["turned"])
    p.restore()
    if down < 1:
        # Its front, drawn out along its fall.
        p.save()
        p.translate(x, top + (foot - top) * down)
        p.scale(1, 2.2)
        soft_dot(p, 0, 0, w * 0.32, GOLD, 0.5 * a)
        soft_dot(p, 0, 0, w * 0.1, "#ffffff", 0.85 * a)
        p.restore()
    land = win(t, start + 0.55, start + 1.5)
    if land > 0:
        pool = (0.35 + 0.65 * (1 - ease_out(land))) * a
        p.save()
        p.translate(x, foot - 4 * u)
        p.scale(1, 0.3)
        soft_dot(p, 0, 0, w * (0.8 + 0.6 * ease_out(land)), GOLD, 0.5 * pool)
        soft_dot(p, 0, 0, w * 0.35, SUNLIGHT, 0.6 * pool)
        p.restore()


def _sparkles(p: QPainter, t: float, pillar: dict, u: float, a: float) -> None:
    """Sparkles spiralling up a pillar, brighter on the near side of their turn, and stars that
    flash in it here and there."""
    if a <= 0.01 or t < pillar["start"] + 0.4:
        return
    x, top, foot, strength = pillar["x"], pillar["top"], pillar["foot"], pillar["strength"]
    for born, phase, reach, rise, r, spin in pillar["rising"]:
        age = t - born
        if age <= 0:
            continue
        y = foot - 20 * u - rise * age
        if y < top + (foot - top) * 0.15:
            continue
        turn = spin * age + phase
        near = 0.5 + 0.5 * math.cos(turn)
        fade = min(1.0, age / 0.4) * _fades(y, top + (foot - top) * 0.45, top + (foot - top) * 0.15) * a * (0.5 + 0.5 * strength)
        px = x + reach * math.sin(turn)
        size = r * (0.6 + 0.5 * near)
        soft_dot(p, px, y, size * 2.6, GOLD, 0.4 * fade * (0.4 + 0.6 * near))
        soft_dot(p, px, y, size * 0.8, "#fffbea", 0.9 * fade * (0.3 + 0.7 * near))
        if near > 0.6:
            star(p, px, y, size * 1.6 * (near - 0.4), "#ffffff", fade * (near - 0.5) * 2, 0.1)
    for along, side, when, span, r in pillar["twinkles"]:
        k = win(t, when, when + span)
        if 0 < k < 1:
            shine = math.sin(math.pi * k) * a
            px, py = x + side * pillar["w"], top + (foot - top) * along
            soft_dot(p, px, py, r * 2.2, HONEY, 0.45 * shine)
            star(p, px, py, r * (0.5 + 0.7 * shine), "#ffffff", shine, 0.09)


def _fades(x: float, start: float, end: float) -> float:
    """1 down to start, 0 from end on, smoothly between (start may be above end or below)."""
    k = clamp((x - end) / (start - end))
    return k * k * (3 - 2 * k)


def _dust(width: float, height: float, sun: QPointF, u: float, rnd: random.Random) -> list[tuple]:
    """Gold dust in the rays either side of the title, off its words and the names."""
    words = QRectF(width * 0.4, height * 0.06, width * 0.26, height * 0.2)
    out = []
    while len(out) < 34:
        x, y = rnd.uniform(0.14, 0.9) * width, rnd.uniform(0.03, 0.27) * height
        if words.contains(QPointF(x, y)):
            continue
        heading = math.atan2(y - sun.y(), x - sun.x())
        out.append((x, y, heading, rnd.uniform(0.6, 3.6), rnd.uniform(1.6, 2.6), rnd.uniform(1.0, 2.2) * u, rnd.uniform(0, 6.28)))
    return out


def _motes(p: QPainter, t: float, dust: list[tuple], u: float, a: float) -> None:
    """The dust drifting slowly out from the sun, twinkling."""
    if a <= 0.01:
        return
    for x, y, heading, born, span, r, phase in dust:
        k = win(t, born, born + span)
        if not 0 < k < 1:
            continue
        shine = math.sin(math.pi * k) * a * (0.65 + 0.35 * math.sin(t * 5 + phase))
        far = 26 * u * k
        px, py = x + math.cos(heading) * far, y + math.sin(heading) * far
        soft_dot(p, px, py, r * 3.5, GOLD, 0.35 * shine)
        soft_dot(p, px, py, r, "#fffbea", 0.9 * shine)


# The marks.


def _density(p: QPainter) -> float:
    """Pixels per point where p draws: the screen's ratio and any scaling."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    m = p.worldTransform()
    return max(1.0, min(4.0, ratio * math.hypot(m.m11(), m.m12())))


def _made(key: tuple, build):  # noqa: ANN001, ANN202
    """What build makes for key, made once."""
    if key not in _MADE:
        if len(_MADE) > 64:
            _MADE.clear()
        _MADE[key] = build()
    return _MADE[key]


def _metal(shade: np.ndarray) -> np.ndarray:
    """Gold for a shade 0..1, as metal shows it."""
    at = np.array([stop for stop, _color in METAL], dtype=np.float32)
    colors = np.array([rgb(color) for _stop, color in METAL], dtype=np.float32)
    shade = np.clip(shade, 0, 1)
    return np.stack([np.interp(shade, at, colors[:, c]) for c in range(3)], axis=-1).astype(np.float32)


def _lit(nx: np.ndarray, ny: np.ndarray, flat: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """How brightly gold whose surface leans by (nx, ny) shines, 0..1, and its highlight alone."""
    nz = np.full(nx.shape, flat, dtype=np.float32)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / norm, ny / norm, nz / norm
    diffuse = np.clip(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0, 1)
    gleam = np.clip(nx * SHINE[0] + ny * SHINE[1] + nz * SHINE[2], 0, 1) ** 28
    return np.clip(0.12 + 0.66 * diffuse + 0.5 * gleam, 0, 1), gleam


def _over(under: tuple[np.ndarray, np.ndarray], top: tuple[np.ndarray, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Straight color and alpha of top laid over under."""
    (c1, a1), (c2, a2) = under, top
    alpha = a2 + a1 * (1 - a2)
    color = (c2 * a2[..., None] + c1 * (a1 * (1 - a2))[..., None]) / np.maximum(alpha, 1e-4)[..., None]
    return color, alpha


def _light(light: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Light (may run over 1) as straight color and alpha, the way glow lays it on."""
    light = np.maximum(light, 0)
    light = light + np.clip(light.max(axis=-1, keepdims=True) - 1, 0, None) * 0.6
    alpha = np.clip(light.max(axis=-1), 0, 1)
    return np.clip(light, 0, 1) / np.maximum(alpha, 1e-4)[..., None], alpha


def _rounded(xs: np.ndarray, ys: np.ndarray, rect: tuple[float, float, float, float], r: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """How far each point is outside a rounded rectangle's edge (below 0 inside), and the way out
    from the edge there."""
    x0, y0, x1, y1 = rect
    ix0, iy0, ix1, iy1 = x0 + r, y0 + r, x1 - r, y1 - r
    vx, vy = xs - np.clip(xs, ix0, ix1), ys - np.clip(ys, iy0, iy1)
    out = np.hypot(vx, vy)
    sides = np.stack([xs - ix0, ix1 - xs, ys - iy0, iy1 - ys])
    nearest = sides.argmin(axis=0)
    d = np.where(out > 0, out, -sides.min(axis=0)) - r
    safe = np.maximum(out, 1e-6)
    nx = np.where(out > 0, vx / safe, np.array([-1.0, 1.0, 0.0, 0.0], dtype=np.float32)[nearest])
    ny = np.where(out > 0, vy / safe, np.array([0.0, 0.0, -1.0, 1.0], dtype=np.float32)[nearest])
    return d, nx.astype(np.float32), ny.astype(np.float32)


def _along(xs: np.ndarray, ys: np.ndarray, rect: tuple[float, float, float, float], r: float) -> tuple[np.ndarray, float]:
    """How far round a rounded rectangle's edge each point outside it lies, clockwise from the top
    left, and the length of the edge."""
    x0, y0, x1, y1 = rect
    ix0, iy0, ix1, iy1 = x0 + r, y0 + r, x1 - r, y1 - r
    lw, lh, q = ix1 - ix0, iy1 - iy0, math.pi * r / 2
    left, right, above, below = xs < ix0, xs > ix1, ys < iy0, ys > iy1
    s = np.select(
        [right & above, right & below, left & below, left & above, above, right, below, left],
        [
            lw + r * np.arctan2(xs - ix1, iy0 - ys),
            lw + q + lh + r * np.arctan2(ys - iy1, xs - ix1),
            2 * lw + 2 * q + lh + r * np.arctan2(ix0 - xs, ys - iy1),
            2 * lw + 3 * q + 2 * lh + r * np.arctan2(iy0 - ys, ix0 - xs),
            xs - ix0,
            lw + q + (ys - iy0),
            lw + 2 * q + lh + (ix1 - xs),
            2 * lw + 3 * q + lh + (iy1 - ys),
        ],
        0.0,
    )
    return s.astype(np.float32), 2 * (lw + lh) + 4 * q


def _edge_point(rect: QRectF, r: float, s: float) -> QPointF:
    """The point s along a rounded rectangle's edge, clockwise from the top left (s wraps)."""
    x0, y0, x1, y1 = rect.left() + r, rect.top() + r, rect.right() - r, rect.bottom() - r
    lw, lh, q = x1 - x0, y1 - y0, math.pi * r / 2
    s %= 2 * (lw + lh) + 4 * q
    for length, place in (
        (lw, lambda k: QPointF(x0 + k, rect.top())),
        (q, lambda k: QPointF(x1 + r * math.sin(k / r), y0 - r * math.cos(k / r))),
        (lh, lambda k: QPointF(rect.right(), y0 + k)),
        (q, lambda k: QPointF(x1 + r * math.cos(k / r), y1 + r * math.sin(k / r))),
        (lw, lambda k: QPointF(x1 - k, rect.bottom())),
        (q, lambda k: QPointF(x0 - r * math.sin(k / r), y1 + r * math.cos(k / r))),
        (lh, lambda k: QPointF(rect.left(), y1 - k)),
        (q, lambda k: QPointF(x0 - r * math.cos(k / r), y0 - r * math.sin(k / r))),
    ):
        if s <= length:
            return place(s)
        s -= length
    return QPointF(rect.left() + r, rect.top())


def _grid(w: float, h: float, density: float) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Each pixel's middle, in points, for a picture w by h points at density."""
    pw, ph = max(1, math.ceil(w * density)), max(1, math.ceil(h * density))
    ys, xs = np.mgrid[0:ph, 0:pw].astype(np.float32) + 0.5
    return xs / density, ys / density, pw, ph


def _image(color: np.ndarray, alpha: np.ndarray, density: float) -> QImage:
    image = picture(color, alpha)
    image.setDevicePixelRatio(density)
    return image


# The ring: a gilt rim round the button with sun rays standing out from it.

# Rays round the ring: about this far apart, the long ones this long, the short ones this long, in points.
RAY_STEP = 11.0
RAY_LONG = 8.8
RAY_SHORT = 5.2
# Pictures of the rays crept on by one step (a long and a short ray) and how long that takes.
RAY_PHASES = 12
RAY_CREEP = 2.6


def _ring_shape(cover: QRectF) -> tuple[tuple[float, float, float, float], float]:
    radius = max(4, round(cover.height() * 0.14))
    return (cover.left(), cover.top(), cover.right(), cover.bottom()), float(radius)


def _ring_base(w: float, h: float, cover: QRectF, density: float) -> QImage:
    """The ring's rim and glow per pixel: a warm glow out into the air and a little in over the
    button's edge, and a rounded gilt rim on the edge, lit from the upper left."""
    xs, ys, _pw, _ph = _grid(w, h, density)
    rect, radius = _ring_shape(cover)
    d, nx, ny = _rounded(xs, ys, rect, radius)
    px = 1 / density
    outside = rgb(HONEY) * (np.exp(-np.maximum(d, 0) / 3.2) * smooth(-0.5, 0.5, d) * 0.5)[..., None]
    inside = rgb(HONEY) * (np.exp(np.minimum(d, 0) / 2.6) * (1 - smooth(-0.5, 0.5, d)) * 0.32)[..., None]
    base = _light(outside + inside)
    middle, half = -1.0, 1.35
    k = np.clip((d - middle) / half, -1, 1)
    bead = np.sqrt(np.clip(1 - k * k, 0, 1))
    lean = k / np.maximum(bead, 0.3) * 0.9
    shade, _gleam = _lit(nx * lean, ny * lean)
    cover_rim = np.clip((half - np.abs(d - middle)) / px + 0.5, 0, 1)
    color, alpha = _over(base, (_metal(shade), cover_rim))
    return _image(color, alpha, density)


def _ring_rays(w: float, h: float, cover: QRectF, density: float, phase: int) -> QImage:
    """The rays standing out from the rim, crept phase steps round it: soft tapered light, long and
    short in turn, white at the root and gold toward the tip, with their bloom."""
    xs, ys, _pw, _ph = _grid(w, h, density)
    rect, radius = _ring_shape(cover)
    d, _nx, _ny = _rounded(xs, ys, rect, radius)
    s, perimeter = _along(xs, ys, rect, radius)
    count = max(2, round(perimeter / RAY_STEP / 2) * 2)
    step = perimeter / count
    j = s / step - phase / RAY_PHASES * 2
    k = np.round(j)
    off = np.abs(j - k) * step
    long = (k.astype(int) % 2) == 0
    length = np.where(long, RAY_LONG, RAY_SHORT)
    reach = np.clip(d - 0.5, 0, None) / length
    half = np.where(long, 1.9, 1.4) * np.clip(1 - reach, 0, 1) ** 0.7
    # Light, not metal: each ray soft across, fading toward its tip, the long ones brighter, and
    # brighter here and there round the button, so the rays shimmer as they creep through.
    ray = np.exp(-((off / np.maximum(half, 1e-3)) ** 2) * 1.6) * (reach < 1) * smooth(0.0, 1.2, d)
    swell = 0.5 + 0.5 * (0.5 + 0.5 * np.cos(s / perimeter * 2 * math.pi * 3 + 1.0))
    hot = ray * np.clip(1 - reach, 0, 1) * np.where(long, 1.0, 0.62) * swell
    light = rgb(SUNLIGHT) * (hot * 0.95)[..., None] + rgb(GOLD) * (hot * 0.45 + blur(hot, 1.6 * density) * 0.8 + blur(hot, 3.5 * density) * 0.45)[..., None]
    color, alpha = _light(light)
    return _image(color, alpha, density)


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A gilt rim round the button with sun rays standing out from it, creeping slowly round and
    breathing, and two glints running along the rim."""
    w, h = cover.width() + 2 * cover.left(), cover.height() + 2 * cover.top()
    density = _density(p)
    size = (round(w, 2), round(h, 2), round(cover.left(), 2), round(cover.top(), 2), density)
    base = _made(("ring", *size), lambda: _ring_base(w, h, cover, density))
    at = (t / RAY_CREEP) % 1 * RAY_PHASES
    first = int(at) % RAY_PHASES
    then = (first + 1) % RAY_PHASES
    mix = at - int(at)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    whole = QRectF(0, 0, w, h)
    p.drawImage(whole, base)
    breathe = 0.82 + 0.18 * math.sin(t * 2.1)
    for phase, share in ((first, 1 - mix), (then, mix)):
        rays = _made(("rays", *size, phase), lambda phase=phase: _ring_rays(w, h, cover, density, phase))
        p.setOpacity(breathe * share)
        p.drawImage(whole, rays)
    p.setOpacity(1.0)
    _rect, radius = _ring_shape(cover)
    edge = cover.adjusted(1.0, 1.0, -1.0, -1.0)
    perimeter = 2 * (edge.width() + edge.height())
    for index in range(2):
        point = _edge_point(edge, radius - 1.0, t * perimeter * 0.16 + index * perimeter / 2)
        soft_dot(p, point.x(), point.y(), 7.0, SUNLIGHT, 0.75)
        star(p, point.x(), point.y(), 6.5 + 1.5 * math.sin(t * 5 + index * 3), "#ffffff", 0.95, 0.12)


# The badge, the lead and the card's ornament: a gold sun in splendour.


def _sun(px: int, count: int, disc: float, tips: tuple[float, float], widths: tuple[float, float], fine: bool, keyline: float = 0.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A gold sun px pixels square, per pixel, lit from the upper left: a domed boss in a field
    engraved with fine rays (fine) inside a raised rim, and count rays round it, long and short in
    turn, each with a ridge along it; a soft shadow under it all, and a dark keyline round it that
    wide (to stand out on gold). Sizes are shares of half its width. Gives its straight color,
    alpha, and where it shines brightest."""
    radius = px / 2
    ys, xs = np.mgrid[0:px, 0:px].astype(np.float32) + 0.5
    dx, dy = (xs - radius) / radius, (ys - radius) / radius
    r = np.hypot(dx, dy)
    angle = np.arctan2(dy, dx)
    pixel = 1 / radius
    step = 2 * math.pi / count
    k = np.round(angle / step)
    off = r * np.sin(angle - k * step)
    short = (k.astype(int) % 2) == 1
    tip = np.where(short, tips[1], tips[0])
    half = np.where(short, widths[1], widths[0]) * np.clip((tip - r) / (tip - disc * 0.7), 0, 1)
    # Thinner than a pixel at the tip, a ray fades rather than running on as a hairline.
    rays = np.clip((half - np.abs(off)) / pixel + 0.5, 0, 1) * np.clip(half / pixel, 0, 1)
    across = np.clip(off / np.maximum(half, 1e-4), -1, 1)
    ux, uy = np.cos(angle), np.sin(angle)
    lean = across * 1.1
    ray_shade, ray_gleam = _lit(-uy * lean + ux * 0.3, ux * lean + uy * 0.3)
    rr = r / disc
    boss, rim = 0.5, 0.84
    slope = np.where(rr < boss, rr / boss * 0.85, np.where(rr < rim, -0.04, (rr - (rim + 1) / 2) / ((1 - rim) / 2) * 0.9))
    sx, sy = ux * slope, uy * slope
    if fine:
        # Fine rays engraved in the field between the boss and the rim, leaning the surface across.
        ridge = np.sin(angle * count * 3) * 0.22 * smooth(boss, boss + 0.06, rr) * (1 - smooth(rim - 0.06, rim, rr))
        sx, sy = sx - uy * ridge, sy + ux * ridge
    disc_shade, disc_gleam = _lit(sx, sy)
    # A fine dark line where the boss and the rim rise from the field.
    groove = (1 - smooth(0.0, 0.04, np.abs(rr - boss))) + (1 - smooth(0.0, 0.035, np.abs(rr - rim)))
    disc_shade = disc_shade * (1 - 0.35 * np.clip(groove, 0, 1))
    disc_cover = np.clip((disc - r) / pixel + 0.5, 0, 1)
    color, alpha = _over((_metal(ray_shade), rays), (_metal(disc_shade), disc_cover))
    gleam = np.maximum(rays * ray_gleam, disc_cover * disc_gleam) + alpha * np.clip(np.maximum(ray_shade, disc_shade) - 0.6, 0, 1)
    sigma = max(1.0, px * 0.03)
    shadow = np.roll(np.roll(blur(alpha, sigma), max(1, round(px * 0.02)), axis=1), max(1, round(px * 0.03)), axis=0) * 0.55
    if keyline > 0:
        shadow = np.maximum(shadow, np.clip(blur(alpha, max(0.6, keyline * radius)) * 2.6, 0, 1) * 0.92)
    color, alpha = _over((np.broadcast_to(rgb("#2a1604"), color.shape), shadow), (color, alpha))
    return color, alpha, np.clip(gleam, 0, 1)


def _radiance_disc(px: int) -> QImage:
    """The light round the badge: soft gold rays all round, fading out from the middle."""
    radius = px / 2
    ys, xs = np.mgrid[0:px, 0:px].astype(np.float32) + 0.5
    dx, dy = xs - radius, ys - radius
    r = np.hypot(dx, dy) / radius
    angle = np.arctan2(dy, dx)
    rays = 0.45 + 0.55 * smooth(0.2, 1.0, 0.5 + 0.5 * np.cos(angle * 24))
    fall = np.exp(-r * 2.6) * (1 - smooth(0.85, 1.0, r))
    return glow(rgb(HONEY) * (fall * rays * 1.25)[..., None])


def _badge_parts(side: float, room: float, density: float) -> tuple[QImage, QImage, QImage]:
    """The badge's pictures: its turning radiance, the sun, and where the sun shines."""
    whole = side + 2 * room
    px = max(8, math.ceil(whole * density))
    color, alpha, gleam = _sun(px, 16, 0.36 * side / (whole / 2), (0.96, 0.76), (0.085, 0.065), True)
    sun = _image(color, alpha, px / whole)
    shine = _image(np.ones(color.shape, dtype=np.float32) * rgb("#fff4d0"), gleam * 0.9, px / whole)
    halo = _radiance_disc(px)
    halo.setDevicePixelRatio(px / whole)
    return halo, sun, shine


def _sheen(p: QPainter, shine: QImage, target: QRectF, k: float, alpha: float) -> None:
    """A slanting band of light crossing a gold picture, k from 0 (before its left) to 1 (past its
    right), lighting it where it shines."""
    if alpha <= 0.01 or not 0 < k < 1:
        return
    layer = QImage(shine)
    q = QPainter(layer)
    q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    w, h = layer.width() / layer.devicePixelRatio(), layer.height() / layer.devicePixelRatio()
    x = (-0.3 + 1.6 * k) * w
    band = max(w, h) * 0.22
    g = QLinearGradient(QPointF(x - band, -band * 0.5), QPointF(x + band, band * 0.5))
    g.setColorAt(0, col("#ffffff", 0))
    g.setColorAt(0.5, col("#ffffff", alpha))
    g.setColorAt(1, col("#ffffff", 0))
    q.fillRect(QRectF(0, 0, w, h), g)
    q.end()
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.drawImage(target, layer)
    p.restore()


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A gold sun in splendour on a slowly turning radiance that breathes, a sheen crossing it now
    and then and a glint on its boss."""
    room = box.left()
    whole = QRectF(0, 0, box.width() + 2 * room, box.height() + 2 * room)
    density = _density(p)
    halo, sun, shine = _made(("badge", round(box.width(), 2), round(room, 2), density), lambda: _badge_parts(box.width(), room, density))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    center = whole.center()
    p.save()
    p.translate(center)
    p.rotate(t * 9)
    p.setOpacity(0.8 + 0.2 * math.sin(t * 1.9))
    p.drawImage(QRectF(-whole.width() / 2, -whole.height() / 2, whole.width(), whole.height()), halo)
    p.restore()
    p.drawImage(whole, sun)
    _sheen(p, shine, whole, (t % 3.4) / 1.3, 0.95)
    glint = math.sin(math.pi * clamp((t % 2.7) / 0.9))
    if glint > 0.02:
        x, y = center.x() - box.width() * 0.07, center.y() - box.width() * 0.08
        soft_dot(p, x, y, box.width() * 0.16, SUNLIGHT, 0.6 * glint)
        star(p, x, y, box.width() * 0.14 * glint, "#ffffff", glint, 0.1)


def lead(size: float, index: int) -> QPixmap:
    """A small gold sun before each name, the odd ones turned half a ray."""
    ratio = 3.0
    px = max(8, round(size * ratio))
    color, alpha, _gleam = _made(("lead", px), lambda: _sun(px, 12, 0.42, (0.96, 0.72), (0.15, 0.11), False, 0.045))
    image = picture(color, alpha)
    if index % 2:
        turned = QImage(image.size(), QImage.Format_ARGB32_Premultiplied)
        turned.fill(Qt.transparent)
        q = QPainter(turned)
        q.setRenderHint(QPainter.SmoothPixmapTransform)
        q.translate(px / 2, px / 2)
        q.rotate(15)
        q.translate(-px / 2, -px / 2)
        q.drawImage(0, 0, image)
        q.end()
        image = turned
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


# The card: an illuminated panel of gold leaf.

FRAME = 4.2
CORNER = 4.0


def _leaf(w: float, h: float, top: float, density: float) -> tuple[QImage, QImage]:
    """The card per pixel: gold leaf, faintly crinkled and laid in squares whose edges overlap, warm
    and lighter toward the upper left, in a raised rounded gilt frame with a fine dark line inside it
    and a row of punched dots; and where the leaf shines, for its sheen."""
    xs, ys, pw, ph = _grid(w, h, density)
    rect = (0.0, top, w, h)
    d, nx, ny = _rounded(xs, ys, rect, CORNER)
    inward = -d
    # The frame: a rounded molding FRAME wide; the field a little lower inside it.
    k = np.clip(inward / FRAME, 0, 1)
    molding = np.where(inward < FRAME, np.cos(k * math.pi) * 1.2, 0.0)
    lean_x, lean_y = nx * molding, ny * molding
    # The leaf's crinkle and the squares it was laid in, each edge a fine raised step.
    crinkle = noise(pw, ph, 9 * density, 3, 7)
    cy_, cx_ = np.gradient(crinkle)
    field = inward >= FRAME
    lean_x = lean_x + np.where(field, -cx_ * density * 3.2, 0)
    lean_y = lean_y + np.where(field, -cy_ * density * 3.2, 0)
    burnish = noise(pw, ph, 26 * density, 2, 9) - 0.5
    cell = 21.0
    seam_x = smooth(0.0, 0.7, np.abs(((xs + 3.0 + 1.2 * np.sin(ys * 0.21)) % cell) - 0.6))
    seam_y = smooth(0.0, 0.7, np.abs(((ys - top + 7.0 + 1.2 * np.sin(xs * 0.17)) % cell) - 0.6))
    seam = (1 - np.minimum(seam_x, seam_y)) * field
    # The punched dots: little hollows in a row just inside the frame.
    dots = _punches(w, h, top, density)
    hy, hx = np.gradient(blur(dots, 0.5 * density))
    lean_x = lean_x + hx * density * 2.2
    lean_y = lean_y + hy * density * 2.2
    shade, gleam = _lit(lean_x, lean_y, 1.6)
    # Warm and light toward the upper left, deeper toward the lower right, in the field.
    across = (xs / w + (ys - top) / max(1.0, h - top)) / 2
    shade = np.where(field, shade * 0.8 + 0.25 - 0.1 * across + burnish * 0.12, shade) + seam * 0.06
    line = (1 - smooth(0.0, 0.45, np.abs(inward - FRAME - 0.7))) * 0.75
    color = _metal(shade)
    color = color + (rgb("#4a2a06") - color) * line[..., None]
    alpha = np.clip(0.5 - d * density, 0, 1)
    shine = alpha * np.clip(gleam * 1.5 + np.clip(shade - 0.62, 0, 1) * 1.6, 0, 1)
    return _image(color, alpha, density), _image(np.ones(color.shape, dtype=np.float32) * rgb("#fff1c8"), shine * 0.85, density)


def _punches(w: float, h: float, top: float, density: float) -> np.ndarray:
    """A row of punched dots a little inside the frame, 0..1 per pixel."""
    inset = FRAME + 3.1
    row = QRectF(inset, top + inset, w - 2 * inset, h - top - 2 * inset)
    gap = 4.6

    def draw(q: QPainter) -> None:
        q.scale(density, density)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        for start, end in ((row.topLeft(), row.topRight()), (row.topRight(), row.bottomRight()), (row.bottomRight(), row.bottomLeft()), (row.bottomLeft(), row.topLeft())):
            length = math.dist((start.x(), start.y()), (end.x(), end.y()))
            count = max(1, round(length / gap))
            for i in range(count):
                k = i / count
                q.drawEllipse(QPointF(start.x() + (end.x() - start.x()) * k, start.y() + (end.y() - start.y()) * k), 0.75, 0.75)

    return mask(max(1, math.ceil(w * density)), max(1, math.ceil(h * density)), draw)


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """The gold-leaf panel in its gilt frame, a sheen crossing it now and then, and a little sun
    rising over its top edge, its light turning."""
    w, h = rect.width(), rect.height()
    density = _density(p)
    panel, shine = _made(("card", round(w, 2), round(h, 2), density), lambda: _leaf(w, h, CARD_TOP, density))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(rect, panel)
    _sheen(p, shine, rect, (t % 4.2) / 1.6, 0.8)
    # The sun rising on the frame's top edge, its light turning behind it; below the frame only its
    # disc shows, clear of the names.
    side = 30.0
    px = max(8, math.ceil(side * density))
    sun = _made(("crest", px), lambda: _image(*_sun(px, 12, 0.44, (0.95, 0.72), (0.13, 0.1), False, 0.04)[:2], px / side))
    halo = _made(("crest-halo", px), lambda: _radiance_disc(px))
    middle = QPointF(rect.center().x(), rect.top() + CARD_TOP + 0.5)
    p.save()
    p.setClipRect(QRectF(rect.left(), rect.top(), w, CARD_TOP + FRAME + 1.5))
    p.save()
    p.translate(middle)
    p.rotate(t * 12)
    p.setOpacity(0.75 + 0.25 * math.sin(t * 1.7))
    reach = CARD_TOP - 0.5
    p.drawImage(QRectF(-reach, -reach, 2 * reach, 2 * reach), halo)
    p.restore()
    p.drawImage(QRectF(middle.x() - side / 2, middle.y() - side / 2, side, side), sun)
    p.restore()

