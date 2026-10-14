"""天使 Angel: holy light from above, and a crest of wings and a golden halo round the title.

Warm white-gold light washes in at the top and down the sides. A halo of gold light comes down to
float just above the title 推演成功, and soft god rays stream down from it, slowly sweeping and
breathing, faint over the names. Two great feathered wings unfold from behind the title in a burst
of holy light, spread to either side of the top of the screen and breathe; they fade to a whisper
behind the title's lines and leave its words clear. Glowing clouds drift in the two top corners, lit
gold along their upper rims. White feathers drift down the two sides, turning as they fall, gold
motes rise from the bottom corners and sparkles come and go. At the end the halo and the wings rise
into the light and it all fades.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QRadialGradient

from blacklist_detect.love_scenes.draw import (
    Wash,
    clamp,
    col,
    ease_back,
    ease_in,
    ease_in_out,
    ease_out,
    gradient,
    mix,
    soft_dot,
    star,
    win,
)
from blacklist_detect.love_scenes.light import blur, glow, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# Soft light throughout: drawn at one pixel per point and scaled up on a sharper screen; the wings,
# with their fine feathers, and the halo are drawn on top at the screen's own sharpness.
MAX_RATIO = 1.0
PEARL = "#fffdf6"
HONEY = "#ffe7a3"
GOLD = "#f3d58a"
GOLD_DEEP = "#d9a441"
# Rays, clouds and the wings' mask are soft: worked out at this share of the size and laid on scaled up.
SOFT = 0.25
# Feather shapes: width (share of length), the leading vane's share of it, how far the shaft bends
# (share of length), how much of the base is down.
KINDS = {
    "primary": (0.2, 0.36, 0.035, 0.1),
    "secondary": (0.3, 0.44, 0.025, 0.12),
    "covert": (0.46, 0.48, 0.02, 0.16),
    "loose": (0.34, 0.42, 0.09, 0.3),
}
# The longest each kind of feather is in a wing, as a share of the wing: its picture is made at that length.
LONGEST = {"primary": 0.44, "secondary": 0.35, "covert": 0.2}


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(23)
    halo_at = QPointF(width * 0.53, height * 0.04)
    # The wings meet behind the title's middle and reach out to about 0.15 and 0.9 of the width.
    axis = width * 0.525
    span = min(width * 0.33, height * 0.64)
    roots = (QPointF(axis + width * 0.035, height * 0.2), QPointF(axis - width * 0.035, height * 0.2))
    band = QRectF(0, 0, width, height * 0.36)
    cut = _wing_mask(band, width, height, u)
    heaven = Wash(lambda q, w, h: _heaven(q, w, h, u))
    rays = (_ray_layer(width, height, halo_at, 3, u), _ray_layer(width, height, halo_at, 8, u))
    shade = _ray_mask(width, height, gap, u)
    clouds = _clouds(width, height, u)
    plan = _wing_plan()
    sprites: dict[tuple[str, int], tuple[QImage, float]] = {}
    # The open wing, drawn once for the sharpness it is shown at.
    opened: dict[float, tuple[QRectF, QImage]] = {}
    halos: dict[int, QImage] = {}
    falling = [
        (
            rnd.uniform(0.5, 3.2),
            (rnd.uniform(0.03, 0.1) if i % 2 else rnd.uniform(0.962, 0.982)) * width,
            rnd.uniform(-0.06, 0.45) * height,
            rnd.uniform(30, 52) * u,
            rnd.uniform(40, 56) * u,
            rnd.uniform(0, 6.28),
            rnd.uniform(1.2, 2.2),
        )
        for i in range(14)
    ]
    motes = [
        (
            rnd.uniform(0.3, 4.0),
            (rnd.uniform(0.0, 0.11) if i % 2 else rnd.uniform(0.93, 1.0)) * width,
            height * rnd.uniform(0.82, 1.02),
            rnd.uniform(45, 105) * u,
            rnd.uniform(1.4, 3.2) * u,
            rnd.uniform(0, 6.28),
        )
        for i in range(44)
    ]
    sparkles = _sparkle_spots(width, height, gap, u, rnd)
    # Glints the burst throws out along the wings, either way and a little up.
    burst = [
        (rnd.choice((0.0, math.pi)) + rnd.uniform(-0.45, 0.12) * (1 if i % 2 else -1), rnd.uniform(160, 460) * u, rnd.uniform(0.7, 1.2))
        for i in range(22)
    ]

    def crest(p: QPainter, t: float) -> None:
        p.save()
        p.setOpacity(p.opacity() * win(t, 0.0, 0.3))
        _crest(p, t, halo_at, roots, span, band, cut, u, plan, sprites, opened, halos, burst)
        p.restore()

    def paint(p: QPainter, t: float, sharp: bool = True) -> None:
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.2, 5.0))
        flash = _burst(t)
        p.save()
        p.setOpacity(life)
        heaven.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.9)) * (1 - leave) * (0.85 + 0.25 * flash))
        _rays(p, t, rays, shade, halo_at, width, height, (1 - leave) * ease_out(win(t, 0.3, 1.3)), flash)
        _cloud_paint(p, t, clouds, u, (1 - leave) * ease_out(win(t, 0.0, 1.0)), leave)
        _falling(p, t, falling, sprites, u, 1 - leave)
        _motes(p, t, motes, u, 1 - leave)
        _sparkles(p, t, sparkles, u, 1 - leave)
        p.restore()
        if sharp:
            crest(p, t)

    paint.sharp = crest
    return paint


def _burst(t: float) -> float:
    """The holy light that bursts as the wings open: quick to come, slow to go."""
    return ease_out(win(t, 0.95, 1.2)) * (1 - ease_in_out(win(t, 1.2, 2.1)))


def _density(p: QPainter) -> float:
    """Pixels per point where p draws: the screen's ratio and any scaling (the small preview)."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    m = p.worldTransform()
    return max(0.3, ratio * math.hypot(m.m11(), m.m12()))


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


def _title(width: float, height: float, u: float) -> tuple[QRectF, QRectF]:
    """The title's words with a little room round them, and the band of it and the lines under it."""
    words = QRectF(width * 0.43, height * 0.085, width * 0.2, height * 0.115).adjusted(-14 * u, -10 * u, 14 * u, 8 * u)
    lines = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.24)
    return words, lines


def _heaven(p: QPainter, width: float, height: float, u: float) -> None:
    """Warm white-gold light at the top and down the sides, strongest above the title where the halo
    is; a faint glow in the bottom corners. Drawn once."""
    top = height * 0.3
    p.fillRect(QRectF(0, 0, width, top), gradient(QPointF(0, 0), QPointF(0, top), ((0, "#fff0c8", 0.24), (0.35, "#ffe2a0", 0.07), (1, "#ffe2a0", 0))))
    side = 170 * u
    for start, end, rect in (
        (QPointF(0, 0), QPointF(side, 0), QRectF(0, 0, side, height)),
        (QPointF(width, 0), QPointF(width - side, 0), QRectF(width - side, 0, side, height)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, "#ffedc2", 0.24), (0.45, "#ffe2a0", 0.08), (1, "#ffe2a0", 0))))
    for cx, cy, r, alpha in ((0.53, -0.08, 520, 0.3), (0.04, -0.05, 440, 0.26), (0.96, -0.05, 440, 0.26), (0.0, 1.0, 340, 0.18), (1.0, 1.0, 340, 0.18)):
        light = QRadialGradient(QPointF(width * cx, height * cy), r * u)
        light.setColorAt(0, col("#fff2d2", alpha))
        light.setColorAt(0.45, col("#ffe2a0", alpha * 0.4))
        light.setColorAt(1, col("#ffe2a0", 0))
        p.fillRect(QRectF(0, 0, width, height), light)


def _ray_layer(width: float, height: float, source: QPointF, seed: int, u: float) -> tuple[QRectF, QImage]:
    """God rays streaming down and out from the halo, worked out per pixel at SOFT size: streaks by
    angle, each its own length, coming on just beyond the halo and fading as they go. Brightest out
    to the sides, under the wings; softer straight down. A margin round the stage lets them turn."""
    margin = width * 0.12
    box = QRectF(-margin, -margin, width + 2 * margin, height + margin)
    w, h = max(1, round(box.width() * SOFT)), max(1, round(box.height() * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = box.left() + xs / SOFT, box.top() + ys / SOFT
    dx, dy = x - source.x(), y - source.y()
    angle = np.arctan2(dx, dy)
    rnd = np.random.default_rng(seed)
    beams = 0.62 * _wave(angle, 0.045, rnd) + 0.38 * _wave(angle, 0.016, rnd)
    streak = smooth(0.42, 0.86, beams)
    r = np.hypot(dx, dy)
    reach = height * (0.45 + 0.6 * _wave(angle, 0.08, rnd))
    fall = smooth(30 * u, 140 * u, r) * (1 - smooth(0.0, reach, r)) ** 1.2
    spread = np.abs(angle)
    side = (0.35 + 0.65 * smooth(0.25, 0.9, spread)) * (1 - smooth(1.45, 1.75, spread))
    strength = side * fall * (0.1 + 0.9 * streak)
    tint = rgb("#ffda90") + (rgb("#fff6e2") - rgb("#ffda90")) * (streak * 0.6)[..., None]
    return box, glow(tint * (strength * 0.9)[..., None])


def _ray_mask(width: float, height: float, gap: QRectF, u: float) -> QImage:
    """Where the rays may show, at SOFT size: faint over the names and the title, none over the gap."""
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = xs / SOFT, ys / SOFT
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    words, lines = _title(width, height, u)
    keep = (1 - 0.74 * _box(x, y, names, 60 * u)) * (1 - 0.45 * _box(x, y, lines, 40 * u)) * (1 - 0.6 * _box(x, y, words, 30 * u))
    keep = keep * (1 - _box(x, y, gap.adjusted(-20 * u, -20 * u, 20 * u, 20 * u), 50 * u))
    return picture(np.ones((h, w, 3), dtype=np.float32), keep)


def _rays(p: QPainter, t: float, layers: tuple, shade: QImage, source: QPointF, width: float, height: float, a: float, flash: float) -> None:
    """The ray layers turning slowly about the halo, each breathing, cut to where they may show on a
    small picture and laid on scaled up."""
    if a <= 0.01:
        return
    small = QImage(shade.width(), shade.height(), QImage.Format_ARGB32_Premultiplied)
    small.fill(Qt.transparent)
    q = QPainter(small)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.setCompositionMode(QPainter.CompositionMode_Plus)
    q.scale(SOFT, SOFT)
    for index, (box, image) in enumerate(layers):
        turn = (2.2 if index == 0 else -2.6) * math.sin(t * (0.45 + 0.17 * index) + index * 1.7)
        breathe = 0.62 + 0.38 * math.sin(t * (1.05 - 0.3 * index) + index * 2.3)
        q.save()
        q.translate(source)
        q.rotate(turn)
        q.translate(-source)
        q.setOpacity(clamp(a * (breathe * 0.75 + 0.9 * flash)))
        q.drawImage(box, image)
        q.restore()
    q.resetTransform()
    q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    q.setOpacity(1.0)
    q.drawImage(0, 0, shade)
    q.end()
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, width, height), small)
    p.restore()


def _cloud(w: int, h: int, right: bool, seed: int, dim: float) -> QImage:
    """A bank of cloud heaped in a top corner, per pixel: round billows along it, their edges frayed
    with noise, glowing warm white where the light from above falls, rimmed gold where it catches
    their tops, a soft honey shade beneath, thinning away toward the middle of the screen."""
    rnd = np.random.default_rng(seed)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    if right:
        xs = w - xs
    # A few large billows fill the corner; smaller ones heap along the bank's lower edge, low at the
    # screen's edge and rising toward the top further in.
    puffs = [(rnd.uniform(-0.05, 0.2) * w, rnd.uniform(-0.25, 0.05) * h, rnd.uniform(0.5, 0.62) * h) for _ in range(3)]
    # Uneven: billows of all sizes, some heaped higher, some hanging lower, never a row of equals.
    for k in sorted(rnd.uniform(0, 1, 12)):
        x = (k * 0.92 + rnd.normal(0, 0.03)) * w
        y = (0.55 * (1 - k) ** 1.3 + 0.06 + rnd.normal(0, 0.06)) * h
        puffs.append((x, y, (0.24 * (1 - k) + 0.08) * h * rnd.uniform(0.7, 1.4)))
    field = np.full((h, w), -float(h), dtype=np.float32)
    for cx, cy, r in puffs:
        d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / r
        field = np.maximum(field, r * np.where(d < 1, np.sqrt(np.clip(1 - d * d, 0, 1)), 1 - d))
    fray = noise(w, h, h * 0.26, 5, seed + 50)
    field = field + (fray - 0.5) * h * 0.26
    # Thin at the edge, wisps fading into the air; denser further in.
    cover = smooth(-h * 0.03, h * 0.16, field)
    gy, gx = np.gradient(blur(np.maximum(field, 0), max(1.0, h * 0.015)))
    norm = np.sqrt(gx * gx + gy * gy + 1)
    nx, ny, nz = -gx / norm, -gy / norm, 1 / norm
    lx, ly, lz = 0.3 if right else -0.3, -0.82, 0.5
    lit = np.clip((nx * lx + ny * ly + nz * lz) / math.sqrt(lx * lx + ly * ly + lz * lz), 0, 1)
    lit = np.clip(lit * (0.8 + 0.4 * noise(w, h, h * 0.06, 3, seed + 90)), 0, 1)
    # Lit through with warm light: the shaded side a soft honey, never grey.
    color = rgb("#f6dcae") + (rgb("#fffaf0") - rgb("#f6dcae")) * (lit ** 0.6)[..., None]
    rim = blur((1 - smooth(-h * 0.02, h * 0.12, field)) * smooth(-h * 0.06, h * 0.02, field) * np.clip(-ny * 1.6 + 0.1, 0, 1), max(1.0, h * 0.012))
    color = color + (rgb(GOLD) * 1.12 - color) * np.clip(rim * 2.2, 0, 0.95)[..., None]
    inward = 1 - smooth(0.62, 1.0, xs / w)
    # Dense enough that the dark lobby does not grey it, and glowing warm into the air round it.
    alpha = np.clip(cover * (0.62 + 0.33 * lit) + rim * 0.4, 0, 1)
    light = color * alpha[..., None] + rgb(HONEY) * (blur(cover, h * 0.06) * (1 - alpha) * 0.35)[..., None]
    return glow(light * (inward * dim)[..., None])


def _clouds(width: float, height: float, u: float) -> list[tuple[QRectF, QImage, float]]:
    """The two corners' clouds, a dimmer bank behind and a brighter one before it, at half size:
    (where, picture, how far it drifts over the scene)."""
    out = []
    # They drift outward, and reach past the edge so their cut end never shows.
    margin = 12 * u
    for right, w, h, seed, dim, drift in (
        (False, 0.36, 0.28, 11, 0.75, -10),
        (False, 0.26, 0.22, 12, 1.0, -20),
        (True, 0.34, 0.27, 13, 0.75, 9),
        (True, 0.24, 0.2, 14, 1.0, 16),
    ):
        rect = QRectF(width * (1 - w) if right else -margin, 0, width * w + margin, height * h)
        out.append((rect, _cloud(max(8, round(rect.width() * 0.5)), max(8, round(rect.height() * 0.5)), right, seed, dim), drift * u))
    return out


def _cloud_paint(p: QPainter, t: float, clouds: list[tuple], u: float, a: float, leave: float) -> None:
    """The clouds drifting slowly outward, the nearer ones faster, and rising away at the end."""
    if a <= 0.01:
        return
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for index, (rect, image, drift) in enumerate(clouds):
        dx = drift * (t / DURATION + 0.15 * math.sin(t * 0.7 + index))
        dy = -30 * u * leave * (1 + index % 2)
        p.setOpacity(a)
        p.drawImage(rect.translated(dx, dy), image)
    p.restore()


def _feather(px: int, kind: str) -> tuple[QImage, float]:
    """A feather px pixels long, quill on the left pointing right, per pixel: a vane on each side of
    the shaft (the leading one narrower), fine barbs sweeping toward the tip, the odd split where the
    barbs part, a translucent frayed edge lit gold from behind, warm cream at the base going to pearl
    white at the tip, and down at the base. Also where the quill is, as a share of its height."""
    broad, lead, bend, down = KINDS[kind]
    high = int(px * (broad + bend) * 1.15) + 4
    ys, xs = np.mgrid[0:high, 0:px].astype(np.float32) + 0.5
    s = xs / px
    root = high / 2 - bend * px / 2
    dv = ys - (root + bend * px * s * s)
    profile = smooth(0.0, 0.3, s) ** 0.55 * np.sqrt(np.clip(1 - np.clip((s - 0.36) / 0.64, 0, 1) ** 2.4, 0, 1))
    half = 0.5 * broad * px * profile * np.where(dv < 0, 2 * lead, 2 * (1 - lead))
    r = np.abs(dv) / np.maximum(half, 1e-3)
    rnd = np.random.default_rng(px * 7 + len(kind))
    # Barbs leave the shaft slanting toward the tip.
    along = xs - np.abs(dv) * 1.15
    spacing = max(2.0, px / 60)
    barbs = 0.5 + 0.5 * np.cos(along / spacing * 2 * math.pi)
    parts = _wave(along + np.where(dv < 0, 0, px * 3), px / 9, rnd)
    split = smooth(0.8, 0.9, parts) * smooth(0.3, 0.6, r) * smooth(0.15, 0.3, s)
    jag = 0.06 * barbs + 0.08 * _wave(along * 1.7, px / 30, rnd)
    inside = 1 - smooth(0.84 - jag, 1.0 - jag, r)
    downy = smooth(0.02, down, s)
    alpha = inside * (1 - 0.9 * split) * (0.6 + 0.32 * (1 - r * r)) * (0.9 + 0.1 * barbs) * (0.5 + 0.5 * downy)
    shaft_w = px * 0.016 * (1 - 0.75 * s) + 0.35
    shaft = (1 - smooth(shaft_w * 0.45, shaft_w, np.abs(dv))) * (1 - smooth(0.9, 0.99, s))
    base = rgb("#efd6a0") + (rgb(PEARL) - rgb("#efd6a0")) * smooth(0.0, 0.7, s)[..., None]
    # Lit from above: the upper vane brighter, each vane curving away from the light toward its edge.
    light = np.where(dv < 0, 1.0, 0.9) * (0.8 + 0.2 * np.cos(np.clip(r, 0, 1) * 1.4)) * (0.94 + 0.06 * barbs)
    color = base * light[..., None]
    edge = smooth(0.55, 0.95, r)
    color = color + (rgb(HONEY) * 1.05 - color) * (edge * 0.45)[..., None]
    color = color + (rgb("#fff3d0") - color) * (shaft * 0.85)[..., None]
    alpha = np.maximum(alpha, shaft * 0.92)
    # A soft warm shadow just below its edge, so a feather shows where it lies over the next.
    shadow = np.roll(blur(inside * smooth(0.0, 0.2, s), px * 0.014), max(1, round(px * 0.008)), axis=0) * 0.17
    under = shadow * (1 - alpha)
    total = alpha + under
    color = (color * alpha[..., None] + rgb("#6e4c1c") * under[..., None]) / np.maximum(total, 1e-4)[..., None]
    return picture(color, total), root / high


def _sprite(sprites: dict, kind: str, length: float, density: float) -> tuple[QImage, float]:
    """The feather of a kind, length long at its longest, for the screen's sharpness: drawn once."""
    px = max(16, math.ceil(length * density / 8) * 8)
    key = (kind, px)
    if key not in sprites:
        sprites[key] = _feather(px, kind)
    return sprites[key]


def _lay(p: QPainter, sprite: tuple[QImage, float], x: float, y: float, angle: float, length: float, across: float = 1.0) -> None:
    """A feather laid with its quill at (x, y), pointing angle degrees clockwise from the right,
    length long; across squeezes its width (below 0, flips it), as when it turns about its shaft."""
    image, root = sprite
    scale = length / image.width()
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.scale(scale, scale * across)
    p.drawImage(QPointF(0, -root * image.height()), image)
    p.restore()


def _wing_plan() -> list[tuple[float, float, float, str]]:
    """The right wing's feathers, drawn in this order: (where along the arm 0..1, angle open, length
    as a share of the wing, kind). The arm reaches out and a little up; flight feathers hang from it,
    the secondaries down and out near the root, the primaries fanning out from the wrist and lifting
    at the tip; rows of coverts, shorter and shorter, lie over their bases."""

    def angle(a: float) -> float:
        return 64 - 70 * a

    def flight(a: float) -> float:
        return 0.16 + 0.3 * a ** 1.1 - 0.03 * clamp((a - 0.9) / 0.1)

    # No two feathers quite alike: each a little turned and a little longer or shorter.
    rnd = random.Random(5)
    plan = []
    for i in range(31):
        a = 1 - i / 30
        plan.append((a, angle(a) + rnd.uniform(-2.0, 2.0), flight(a) * rnd.uniform(0.95, 1.04), "primary" if a > 0.62 else "secondary"))
    for count, start, end, share, lift, kind in ((22, 0.0, 0.97, 0.55, 4, "secondary"), (18, 0.0, 0.92, 0.34, 7, "covert"), (14, 0.0, 0.85, 0.18, 10, "covert")):
        for i in range(count):
            a = clamp(end - i / (count - 1) * (end - start) + rnd.uniform(-0.008, 0.008))
            plan.append((a, angle(a) + lift + rnd.uniform(-3.5, 3.5), (flight(a) * share + 0.04) * rnd.uniform(0.92, 1.06), kind))
    return plan


def _wing(p: QPainter, span: float, plan: list[tuple], sprites: dict, density: float, k: float) -> None:
    """The right wing with its root at the origin, span long, open by k: each feather on the arm,
    the arm and the feathers' angles and lengths going from tucked in behind the title to spread."""
    fold = ((0.0, 0.0), (0.03, 0.04), (0.08, 0.06))
    spread = ((0.0, 0.0), (0.26, -0.17), (0.62, -0.17))
    (x0, y0), (cx, cy), (x1, y1) = ((fx + (sx - fx) * k, fy + (sy - fy) * k) for (fx, fy), (sx, sy) in zip(fold, spread, strict=True))
    for at, angle, length, kind in plan:
        m = 1 - at
        x = m * m * x0 + 2 * m * at * cx + at * at * x1
        y = m * m * y0 + 2 * m * at * cy + at * at * y1
        size = span * length * (0.45 + 0.55 * k)
        _lay(p, _sprite(sprites, kind, span * LONGEST[kind], density), x * span, y * span, 100 + (angle - 100) * k, size)


def _open_wing(span: float, plan: list[tuple], sprites: dict, density: float) -> tuple[QRectF, QImage]:
    """The right wing spread, drawn once at the screen's sharpness: where it lies round its root, and
    the picture. Once open it only breathes, which turns it whole."""
    box = QRectF(-0.08 * span, -0.42 * span, 1.18 * span, 0.76 * span)
    image = QImage(max(1, math.ceil(box.width() * density)), max(1, math.ceil(box.height() * density)), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.scale(density, density)
    q.translate(-box.left(), -box.top())
    _wing(q, span, plan, sprites, density, 1.0)
    q.end()
    return box, image


def _wing_mask(band: QRectF, width: float, height: float, u: float) -> QImage:
    """Where the wings may show over band, at SOFT size: a whisper behind the title's lines and none
    over its words."""
    w, h = max(1, round(band.width() * SOFT)), max(1, round(band.height() * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = band.left() + xs / SOFT, band.top() + ys / SOFT
    words, lines = _title(width, height, u)
    keep = (1 - 0.78 * _box(x, y, lines, 50 * u)) * (1 - _box(x, y, words, 24 * u))
    return picture(np.ones((h, w, 3), dtype=np.float32), keep)


def _halo_picture(px: int) -> QImage:
    """A halo of gold light px pixels across, seen a little from below, per pixel: a ring with a
    white-hot line along it, its near side brighter, blooming out into the air round it."""
    rx, ry = px / 2, px / 2 * 0.27
    w, h = int(px * 1.5) + 4, int(px * 0.85) + 4
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = (xs - w / 2) / rx, (ys - h / 2) / ry
    # Distance from the ellipse, roughly in pixels: the step from 1 over how fast it grows there.
    e = np.sqrt(x * x + y * y)
    gx, gy = x / rx, y / ry
    reach = np.maximum(e, 1e-3) / np.maximum(np.hypot(gx, gy), 1e-6)
    d = np.abs(e - 1) * reach / np.maximum(e, 1e-3)
    tube = px * 0.028
    band = 1 - smooth(tube * 0.5, tube * 1.1, d)
    core = 1 - smooth(tube * 0.1, tube * 0.5, d)
    near = 0.7 + 0.3 * smooth(-0.6, 0.6, y / np.maximum(e, 1e-3))
    light = (rgb(GOLD_DEEP) * 0.9 * band[..., None] + rgb("#fff8e6") * (core * 1.15)[..., None]) * near[..., None]
    light = light + rgb(GOLD) * (blur(band, px * 0.025) * 0.85 + blur(band, px * 0.07) * 0.5)[..., None]
    return glow(light)


def _crest(p: QPainter, t: float, halo_at: QPointF, roots: tuple, span: float, band: QRectF, cut: QImage, u: float, plan: list, sprites: dict, opened: dict, halos: dict, burst: list) -> None:
    """The crest round the title: the halo comes down above it, the wings unfold from behind it with
    a burst of light and breathe; at the end they rise into the light and fade."""
    leave = ease_in_out(win(t, 4.15, 4.95))
    rise = ease_in(win(t, 3.95, 4.95))
    flash = _burst(t)
    density = _density(p)
    # The pictures, made on the first frame while nothing shows yet.
    rx = 106 * u
    px = max(16, math.ceil(rx * 2 * density / 8) * 8)
    if px not in halos:
        halos[px] = _halo_picture(px)
    for kind, longest in LONGEST.items():
        _sprite(sprites, kind, span * longest, density)
    a = 1 - leave
    if a <= 0.01:
        return
    lift = -50 * u * rise
    p.save()
    p.setOpacity(p.opacity() * a)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    k = ease_back(win(t, 0.6, 1.6), 1.2)
    if k > 0:
        _wings(p, t, roots, span, band, cut, lift, plan, sprites, opened, density, k)
    _halo(p, t, QPointF(halo_at.x(), halo_at.y() + lift), rx, halos[px], px, flash, u)
    p.restore()
    hc = QPointF(halo_at.x(), halo_at.y() + lift)
    # Glints thrown out by the burst along the wings, slowing as they go.
    for angle, far, life in burst:
        age = t - 1.0
        if 0 < age < life:
            k_ = ease_out(age / life)
            x = hc.x() + math.cos(angle) * far * k_
            y = hc.y() + 20 * u + math.sin(angle) * far * k_ * 0.5
            fade = 1 - age / life
            soft_dot(p, x, y, 10 * u, GOLD, 0.6 * fade)
            star(p, x, y, 8 * u * (0.6 + 0.4 * fade), "#ffffff", fade)
    # Going, the halo leaves glints of its light rising from its ring.
    if rise > 0:
        for i in range(12):
            turn = i / 12 * 2 * math.pi + 0.3
            k_ = clamp(rise * 1.4 - 0.035 * i)
            if 0 < k_ < 1:
                x = hc.x() + rx * math.cos(turn)
                y = hc.y() + rx * 0.27 * math.sin(turn) - 70 * u * k_ * (0.7 + 0.05 * i)
                soft_dot(p, x, y, 12 * u, GOLD, 0.6 * (1 - k_))
                star(p, x, y, 8 * u * math.sin(math.pi * k_), "#ffffff", 1 - k_ * 0.6)


def _wings(p: QPainter, t: float, roots: tuple, span: float, band: QRectF, cut: QImage, lift: float, plan: list, sprites: dict, opened: dict, density: float, k: float) -> None:
    """Both wings drawn on a picture of the band they live in, at the screen's sharpness, cut away
    over the title, and laid on: a warm light behind them once they are open. Unfolding, each
    feather moves; open, each wing is laid whole, breathing as it turns a little about its root."""
    layer = QImage(max(1, math.ceil(band.width() * density)), max(1, math.ceil(band.height() * density)), QImage.Format_ARGB32_Premultiplied)
    layer.fill(Qt.transparent)
    q = QPainter(layer)
    q.setRenderHint(QPainter.Antialiasing)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.scale(density, density)
    q.translate(-band.left(), -band.top() + lift)
    spread = ease_out(win(t, 0.8, 1.6))
    for mirror, root in zip((1, -1), roots, strict=True):
        soft_dot(q, root.x() + mirror * span * 0.5, root.y() - span * 0.15, span * 0.5, "#ffe2a0", 0.22 * spread)
    q.setOpacity(clamp(win(t, 0.55, 0.85)))
    beat = -3.2 * math.sin(2 * math.pi * (t - 1.6) / 2.1) * win(t, 1.6, 2.2)
    if t >= 1.6 and density not in opened:
        opened.clear()
        opened[density] = _open_wing(span, plan, sprites, density)
    for mirror, root in zip((1, -1), roots, strict=True):
        q.save()
        q.translate(root)
        q.scale(mirror, 1)
        q.rotate(beat)
        if t >= 1.6:
            box, image = opened[density]
            q.drawImage(box, image)
        else:
            _wing(q, span, plan, sprites, density, k)
        q.restore()
    q.resetTransform()
    q.setOpacity(1.0)
    q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    q.drawImage(QRectF(0, 0, layer.width(), layer.height()), cut)
    q.end()
    p.drawImage(band, layer)


def _halo(p: QPainter, t: float, hc: QPointF, rx: float, image: QImage, px: int, flash: float, u: float) -> None:
    """The halo comes down to float above the title, tilted a little, a glint running round it; the
    burst blooms out of it."""
    down = ease_out(win(t, 0.3, 1.0))
    if down <= 0:
        return
    hc = QPointF(hc.x(), hc.y() - 40 * u * (1 - down) + 2.5 * u * math.sin(t * 1.9 + 0.8))
    # Its radiance, wide and low.
    p.save()
    p.translate(hc)
    p.scale(1, 0.3)
    soft_dot(p, 0, 0, rx * 1.9, HONEY, 0.4 * down)
    p.restore()
    if flash > 0.02:
        # A soft bloom, wide and low, kept above the words.
        p.save()
        p.translate(hc)
        p.scale(1, 0.42)
        soft_dot(p, 0, 0, rx * 2.6, "#ffffff", 0.55 * flash)
        soft_dot(p, 0, 0, rx * 4.2, HONEY, 0.35 * flash)
        p.restore()
    scale = rx * 2 / px
    w, h = image.width() * scale, image.height() * scale
    p.save()
    p.translate(hc)
    p.rotate(-6)
    p.save()
    p.setOpacity(p.opacity() * down * (0.92 + 0.08 * math.sin(t * 3.1)))
    p.drawImage(QRectF(-w / 2, -h / 2, w, h), image)
    p.restore()
    turn = t * 2.2
    gx, gy = rx * math.cos(turn), rx * 0.27 * math.sin(turn)
    near = 0.5 + 0.5 * math.sin(turn)
    shine = down * (0.45 + 0.55 * near)
    soft_dot(p, gx, gy, 16 * u, "#fff6dc", 0.7 * shine)
    star(p, gx, gy, (9 + 8 * near) * u, "#ffffff", shine, 0.08)
    p.restore()


def _falling(p: QPainter, t: float, falling: list[tuple], sprites: dict, u: float, a: float) -> None:
    """White feathers drifting down the sides, swaying, and turning about their shafts as they go."""
    # Made on the first frame, while none falls yet.
    sprite = _sprite(sprites, "loose", 56 * u, _density(p))
    if a <= 0.01:
        return
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    base = p.opacity()
    for index, (born, x, y, fall, length, phase, rate) in enumerate(falling):
        age = t - born
        if age <= 0:
            continue
        fade = min(1.0, age / 0.5) * a
        # Lying nearly flat, it rocks from side to side as it falls, dipping at each end of a swing.
        swing = math.sin(age * 1.7 + phase)
        cx = x + 18 * u * swing
        cy = y + fall * age - 6 * u * abs(swing)
        heading = 180 if index % 4 < 2 else 0
        angle = heading + 28 * math.cos(age * 1.7 + phase) * (1 if heading else -1) + 12
        turn = math.cos(age * rate + phase)
        across = math.copysign(0.35 + 0.65 * abs(turn), turn)
        p.setOpacity(base * fade * (0.75 + 0.25 * abs(turn)))
        # Laid by its quill, half its length back from where it is.
        back = math.radians(angle)
        _lay(p, sprite, cx - math.cos(back) * length / 2, cy - math.sin(back) * length / 2, angle, length, across)
    p.restore()


def _motes(p: QPainter, t: float, motes: list[tuple], u: float, a: float) -> None:
    """Gold motes rising from the bottom corners, swaying and twinkling, gone before the names."""
    for born, x, y, rise, r, phase in motes:
        age = t - born
        if age <= 0 or age > 2.6:
            continue
        fade = min(1.0, age / 0.4) * min(1.0, (2.6 - age) / 0.9) * a
        px, py = x + 10 * u * math.sin(age * 1.8 + phase), y - rise * age
        twinkle = 0.6 + 0.4 * math.sin(age * 6 + phase)
        soft_dot(p, px, py, r * 4, GOLD, 0.45 * fade)
        soft_dot(p, px, py, r * 1.3, "#fffbea", 0.95 * fade * twinkle)


def _sparkle_spots(width: float, height: float, gap: QRectF, u: float, rnd: random.Random) -> list[tuple]:
    """Where sparkles come and go: the top band either side of the title, and down the sides."""
    names = QRectF(width * 0.12, height * 0.27, width * 0.83, height * 0.6)
    title = QRectF(width * 0.36, height * 0.0, width * 0.34, height * 0.34)
    out = []
    while len(out) < 26:
        x, y = rnd.uniform(0.01, 0.99) * width, rnd.uniform(0.02, 0.9) * height
        point = QPointF(x, y)
        if names.contains(point) or title.contains(point) or gap.adjusted(-40 * u, -40 * u, 40 * u, 0).contains(point):
            continue
        out.append((x, y, rnd.uniform(0.4, 3.8), rnd.uniform(0.7, 1.3), rnd.uniform(5, 11) * u))
    return out


def _sparkles(p: QPainter, t: float, spots: list[tuple], u: float, a: float) -> None:
    for x, y, when, span, r in spots:
        k = win(t, when, when + span)
        if not 0 < k < 1:
            continue
        shine = math.sin(math.pi * k) * a
        soft_dot(p, x, y, r * 2.2, HONEY, 0.4 * shine)
        star(p, x, y, r * (0.6 + 0.6 * shine), "#ffffff", shine, 0.1)
        if r > 9 * u:
            star(p, x, y, r * 0.5 * shine, mix(GOLD, "#ffffff", 0.5), shine, 0.25)
