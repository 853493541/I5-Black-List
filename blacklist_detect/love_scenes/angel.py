"""天使 Angel: holy light from above, and a winged heart under a golden halo.

Warm white-gold light washes in at the top and down the sides, and soft god rays stream down from
above the top left, slowly sweeping and breathing. Luminous clouds drift in the two top corners, lit
gold along their upper rims. In the top left a pearl heart glows, white at its middle and gold at
its rim, under a halo of gold light with a glint running round it; two feathered wings unfold from
behind it in a burst of holy light, then breathe. White feathers drift down the two sides, turning
as they fall, gold motes rise from the bottom corners and sparkles come and go. At the end the
heart and its halo rise into the light and it all fades.
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
    heart_path,
    heart_points,
    mix,
    soft_dot,
    star,
    win,
)
from blacklist_detect.love_scenes.light import blur, glow, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# Soft light throughout: drawn at one pixel per point and scaled up on a sharper screen; the winged
# heart, with its fine feathers, is drawn on top at the screen's own sharpness.
MAX_RATIO = 1.0
PEARL = "#fffdf6"
CREAM = "#fbefd2"
HONEY = "#ffe7a3"
GOLD = "#f3d58a"
GOLD_DEEP = "#d9a441"
# Rays and clouds are soft: worked out at this share of the stage's size and laid on scaled up.
SOFT = 0.25
# Feather shapes: width (share of length), the leading vane's share of it, how far the shaft bends
# (share of length), how much of the base is down.
KINDS = {
    "primary": (0.2, 0.36, 0.035, 0.1),
    "secondary": (0.3, 0.44, 0.025, 0.12),
    "covert": (0.46, 0.48, 0.02, 0.16),
    "loose": (0.34, 0.42, 0.09, 0.3),
}
# A wing's length, as a share of the heart's size, and the longest each kind of feather is in it, as
# a share of the wing: its picture is made at that length.
WING = 1.45
LONGEST = {"primary": 0.6, "secondary": 0.52, "covert": 0.26}


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(23)
    size = 112 * u
    # heart_points' heart reaches 0.28 of its size above its centre and 0.57 below: lift it so the
    # middle of what shows sits at the hero's place.
    heart_at = QPointF(width * 0.118, height * 0.19 - size * 0.12)
    heaven = Wash(lambda q, w, h: _heaven(q, w, h, u))
    source = QPointF(width * 0.17, -height * 0.5)
    rays = (_ray_layer(width, height, source, 3), _ray_layer(width, height, source, 8))
    shade = _ray_mask(width, height, gap, u)
    clouds = _clouds(width, height, u)
    wing = _wing_plan()
    sprites: dict[tuple[str, int], tuple[QImage, float]] = {}
    hearts: dict[int, tuple[QImage, QImage]] = {}
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
    burst = [(rnd.uniform(-math.pi * 1.1, math.pi * 0.08), rnd.uniform(140, 300) * u, rnd.uniform(0.7, 1.2)) for _ in range(18)]

    def hero(p: QPainter, t: float) -> None:
        p.save()
        p.setOpacity(p.opacity() * win(t, 0.0, 0.3))
        _hero(p, t, heart_at, size, u, wing, sprites, hearts, halos, burst)
        p.restore()

    def paint(p: QPainter, t: float, sharp: bool = True) -> None:
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.2, 5.0))
        flash = _burst(t)
        p.save()
        p.setOpacity(life)
        heaven.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.9)) * (1 - leave) * (0.85 + 0.25 * flash))
        _rays(p, t, rays, shade, source, width, height, (1 - leave) * ease_out(win(t, 0.1, 1.2)), flash)
        _cloud_paint(p, t, clouds, u, (1 - leave) * ease_out(win(t, 0.0, 1.0)), leave)
        _falling(p, t, falling, sprites, u, 1 - leave)
        _motes(p, t, motes, u, 1 - leave)
        _sparkles(p, t, sparkles, u, 1 - leave)
        p.restore()
        if sharp:
            hero(p, t)

    paint.sharp = hero
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


def _heaven(p: QPainter, width: float, height: float, u: float) -> None:
    """Warm white-gold light at the top and down the sides, strongest in the top left where the rays
    come from; a faint glow in the bottom corners. Drawn once."""
    top = height * 0.3
    p.fillRect(QRectF(0, 0, width, top), gradient(QPointF(0, 0), QPointF(0, top), ((0, "#fff0c8", 0.3), (0.35, "#ffe2a0", 0.1), (1, "#ffe2a0", 0))))
    side = 170 * u
    for start, end, rect in (
        (QPointF(0, 0), QPointF(side, 0), QRectF(0, 0, side, height)),
        (QPointF(width, 0), QPointF(width - side, 0), QRectF(width - side, 0, side, height)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, "#ffedc2", 0.24), (0.45, "#ffe2a0", 0.08), (1, "#ffe2a0", 0))))
    for cx, cy, r, alpha in ((0.1, -0.05, 600, 0.36), (0.92, -0.05, 440, 0.22), (0.0, 1.0, 340, 0.18), (1.0, 1.0, 340, 0.18)):
        light = QRadialGradient(QPointF(width * cx, height * cy), r * u)
        light.setColorAt(0, col("#fff2d2", alpha))
        light.setColorAt(0.45, col("#ffe2a0", alpha * 0.4))
        light.setColorAt(1, col("#ffe2a0", 0))
        p.fillRect(QRectF(0, 0, width, height), light)


def _ray_layer(width: float, height: float, source: QPointF, seed: int) -> tuple[QRectF, QImage]:
    """God rays from a point above the top left, worked out per pixel at SOFT size: streaks by angle,
    each its own length, brightest at the top. A margin round the stage lets them turn a little."""
    margin = width * 0.12
    box = QRectF(-margin, -margin, width + 2 * margin, height + margin)
    w, h = max(1, round(box.width() * SOFT)), max(1, round(box.height() * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = box.left() + xs / SOFT, box.top() + ys / SOFT
    angle = np.arctan2(x - source.x(), y - source.y())
    rnd = np.random.default_rng(seed)
    beams = 0.62 * _wave(angle, 0.05, rnd) + 0.38 * _wave(angle, 0.017, rnd)
    streak = smooth(0.42, 0.86, beams)
    reach = height * (0.35 + 0.55 * _wave(angle, 0.08, rnd))
    fall = (1 - smooth(-height * 0.1, reach, y)) ** 1.3
    # Most light falls on the left, toward the heart; less across to the right.
    side = smooth(-0.75, -0.25, angle) * (1 - 0.55 * smooth(0.1, 1.0, angle))
    strength = side * fall * (0.1 + 0.9 * streak)
    tint = rgb("#ffda90") + (rgb("#fff6e2") - rgb("#ffda90")) * (streak * 0.6)[..., None]
    return box, glow(tint * (strength * 0.62)[..., None])


def _ray_mask(width: float, height: float, gap: QRectF, u: float) -> QImage:
    """Where the rays may show, at SOFT size: faint over the names and the title, none over the gap."""
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = xs / SOFT, ys / SOFT
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    title = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.18)
    keep = (1 - 0.74 * _box(x, y, names, 60 * u)) * (1 - 0.5 * _box(x, y, title, 50 * u)) * (1 - _box(x, y, gap.adjusted(-20 * u, -20 * u, 20 * u, 20 * u), 50 * u))
    return picture(np.ones((h, w, 3), dtype=np.float32), keep)


def _rays(p: QPainter, t: float, layers: tuple, shade: QImage, source: QPointF, width: float, height: float, a: float, flash: float) -> None:
    """The ray layers turning slowly about their source, each breathing, cut to where they may show
    on a small picture and laid on scaled up."""
    if a <= 0.01:
        return
    small = QImage(shade.width(), shade.height(), QImage.Format_ARGB32_Premultiplied)
    small.fill(Qt.transparent)
    q = QPainter(small)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.setCompositionMode(QPainter.CompositionMode_Plus)
    q.scale(SOFT, SOFT)
    for index, (box, image) in enumerate(layers):
        turn = (1.6 if index == 0 else -1.9) * math.sin(t * (0.45 + 0.17 * index) + index * 1.7)
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
    with noise, lit warm white from above, rimmed gold where the light catches their tops, a soft
    warm grey beneath, thinning away toward the middle of the screen."""
    rnd = np.random.default_rng(seed)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    if right:
        xs = w - xs
    # A few large billows fill the corner; smaller ones heap along the bank's lower edge, low at the
    # screen's edge and rising toward the top further in.
    puffs = [(rnd.uniform(-0.05, 0.2) * w, rnd.uniform(-0.25, 0.05) * h, rnd.uniform(0.5, 0.62) * h) for _ in range(3)]
    for i in range(15):
        k = i / 14
        x = (k * 0.92 + rnd.normal(0, 0.015)) * w
        y = (0.6 * (1 - k) ** 1.3 + 0.06 + rnd.normal(0, 0.03)) * h
        puffs.append((x, y, (0.22 * (1 - k) + 0.07) * h * rnd.uniform(0.8, 1.25)))
    field = np.full((h, w), -float(h), dtype=np.float32)
    for cx, cy, r in puffs:
        d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / r
        field = np.maximum(field, r * np.where(d < 1, np.sqrt(np.clip(1 - d * d, 0, 1)), 1 - d))
    fray = noise(w, h, h * 0.18, 4, seed + 50)
    field = field + (fray - 0.5) * h * 0.2
    # Thin at the edge, wisps fading into the air; denser further in.
    cover = smooth(-h * 0.03, h * 0.16, field)
    gy, gx = np.gradient(blur(np.maximum(field, 0), max(1.0, h * 0.015)))
    norm = np.sqrt(gx * gx + gy * gy + 1)
    nx, ny, nz = -gx / norm, -gy / norm, 1 / norm
    lx, ly, lz = 0.3 if right else -0.3, -0.82, 0.5
    lit = np.clip((nx * lx + ny * ly + nz * lz) / math.sqrt(lx * lx + ly * ly + lz * lz), 0, 1)
    lit = np.clip(lit * (0.8 + 0.4 * noise(w, h, h * 0.06, 3, seed + 90)), 0, 1)
    color = rgb("#dcc6a8") + (rgb(PEARL) - rgb("#dcc6a8")) * (lit ** 0.6)[..., None]
    # Gold where the light from above catches the billows' tops, soft as light through their edges.
    rim = blur((1 - smooth(-h * 0.02, h * 0.12, field)) * smooth(-h * 0.06, h * 0.02, field) * np.clip(-ny * 1.6 + 0.1, 0, 1), max(1.0, h * 0.012))
    color = color + (rgb(HONEY) - color) * (lit * 0.18)[..., None]
    color = color + (rgb(GOLD) * 1.12 - color) * np.clip(rim * 2.2, 0, 0.95)[..., None]
    inward = 1 - smooth(0.62, 1.0, xs / w)
    alpha = np.clip(cover * (0.45 + 0.4 * lit) + rim * 0.5, 0, 1) * inward * dim
    return picture(color, alpha)


def _clouds(width: float, height: float, u: float) -> list[tuple[QRectF, QImage, float]]:
    """The two corners' clouds, a dimmer bank behind and a brighter one before it, at half size:
    (where, picture, how far it drifts over the scene)."""
    out = []
    # They drift outward, and reach past the edge so their cut end never shows.
    margin = 12 * u
    for right, w, h, seed, dim, drift in (
        (False, 0.42, 0.3, 11, 0.7, -10),
        (False, 0.3, 0.24, 12, 1.0, -20),
        (True, 0.36, 0.27, 13, 0.7, 9),
        (True, 0.25, 0.2, 14, 1.0, 16),
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
    as a share of the wing, kind). Flight feathers hang from the arm, the secondaries down and out
    from near the heart, the primaries fanning out and up from the wrist; rows of coverts, shorter
    and shorter, lie over their bases."""

    def angle(a: float) -> float:
        return 80 - 112 * a

    def flight(a: float) -> float:
        return 0.32 + 0.3 * a ** 1.1 - 0.07 * clamp((a - 0.9) / 0.1)

    # No two feathers quite alike: each a little turned and a little longer or shorter.
    rnd = random.Random(5)
    plan = []
    for i in range(21):
        a = 1 - i / 20
        plan.append((a, angle(a) + rnd.uniform(-2.5, 2.5), flight(a) * rnd.uniform(0.95, 1.04), "primary" if a > 0.6 else "secondary"))
    for count, start, end, share, lift, kind in ((15, 0.0, 0.96, 0.56, 5, "secondary"), (13, 0.0, 0.9, 0.34, 8, "covert"), (10, 0.0, 0.8, 0.18, 12, "covert")):
        for i in range(count):
            a = clamp(end - i / (count - 1) * (end - start) + rnd.uniform(-0.012, 0.012))
            plan.append((a, angle(a) + lift + rnd.uniform(-4, 4), (flight(a) * share + 0.04) * rnd.uniform(0.92, 1.06), kind))
    return plan


def _arm(k: float, beat: float) -> tuple[QPointF, QPointF, QPointF]:
    """The right wing's arm as a curve from its root, in wing lengths: tucked down behind the heart
    when k is 0, raised and spread when 1, turned by beat degrees."""
    fold = ((0.0, 0.0), (0.05, 0.15), (0.12, 0.3))
    spread = ((0.0, 0.0), (0.06, -0.42), (0.45, -0.44))
    turn = math.radians(beat)
    out = []
    for (fx, fy), (sx, sy) in zip(fold, spread, strict=True):
        x, y = fx + (sx - fx) * k, fy + (sy - fy) * k
        out.append(QPointF(x * math.cos(turn) - y * math.sin(turn), x * math.sin(turn) + y * math.cos(turn)))
    return out[0], out[1], out[2]


def _wing(p: QPainter, t: float, root: QPointF, span: float, plan: list[tuple], sprites: dict, density: float, k: float) -> None:
    """The right wing at root, span long, open by k: each feather on the arm, its angle and length
    going from tucked to spread, then the whole wing breathing, its tips a moment behind."""
    breath = t - 1.6
    beat = -5 * math.sin(2 * math.pi * breath / 1.9) * win(t, 1.4, 2.0)
    a0, c, a1 = _arm(k, beat)
    for at, angle, length, kind in plan:
        m = 1 - at
        x = m * m * a0.x() + 2 * m * at * c.x() + at * at * a1.x()
        y = m * m * a0.y() + 2 * m * at * c.y() + at * at * a1.y()
        lag = 3 * at * math.sin(2 * math.pi * breath / 1.9 - 0.9) * win(t, 1.4, 2.0)
        turn = 100 + (angle - 100) * k + beat + lag
        size = span * length * (0.45 + 0.55 * k)
        _lay(p, _sprite(sprites, kind, span * LONGEST[kind], density), root.x() + x * span, root.y() + y * span, turn, size)


def _pearl_heart(px: int) -> tuple[QImage, QImage, float]:
    """A heart of pearl px pixels wide, per pixel, and the glow round it, in one square picture each.

    Its surface rises in a rounded bevel from the outline. Face on it is pearl, warm white light
    gathered in its middle and a faint sheen of rose and lilac as it turns; toward the edge it goes
    to honey and at the rim to polished gold, which reflects the light above and the dark below; a
    soft window of light sits on each lobe. The glow's picture is larger; both have the heart's centre
    (as heart_path takes it) at the middle across and px * 0.145 above the middle down."""
    side = int(px * 1.04) + 4
    cx, cy = side / 2, side / 2 - px * 0.145
    ring = heart_points(cx, cy, px, 72)
    mask_ = _fill(side, heart_path(cx, cy, px))
    inside = (mask_ > 0.5).astype(np.float32)
    # How far in from the outline, measured on every other pixel and spread back out.
    ax = np.array([point.x() for point in ring], dtype=np.float32)
    ay = np.array([point.y() for point in ring], dtype=np.float32)
    half_y, half_x = np.mgrid[0:side:2, 0:side:2].astype(np.float32) + 0.5
    dist = np.full(half_x.shape, np.inf, dtype=np.float32)
    for x0, y0, x1, y1 in zip(ax, ay, np.roll(ax, -1), np.roll(ay, -1), strict=True):
        dx, dy = x1 - x0, y1 - y0
        k = np.clip(((half_x - x0) * dx + (half_y - y0) * dy) / (dx * dx + dy * dy + 1e-6), 0, 1)
        dist = np.minimum(dist, np.hypot(half_x - x0 - k * dx, half_y - y0 - k * dy))
    dist = np.kron(dist, np.ones((2, 2), dtype=np.float32))[:side, :side]
    yy, xx = np.mgrid[0:side, 0:side].astype(np.float32)
    bevel = px * 0.24
    k = np.clip(dist / bevel, 0, 1)
    height = blur(np.sqrt(1 - (1 - k) ** 2) * inside, px * 0.02) * inside
    gy, gx = np.gradient(height * bevel)
    norm = np.sqrt(gx * gx + gy * gy + 1)
    nx, ny, nz = -gx / norm, -gy / norm, 1 / norm
    lx, ly, lz = -0.45, -0.68, 0.58
    length = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / length, ly / length, lz / length
    diffuse = np.clip(nx * lx + ny * ly + nz * lz, 0, 1)
    rx, ry, rz = 2 * nz * nx, 2 * nz * ny, 2 * nz * nz - 1
    x = (xx - cx) / px
    y = (yy - cy) / px - 0.14
    inner = np.exp(-((x / 0.3) ** 2 + ((y - 0.02) / 0.26) ** 2))
    body = rgb(CREAM) + (rgb(PEARL) - rgb(CREAM)) * inner[..., None]
    slope = 1 - nz
    body = body + (rgb(HONEY) - body) * (smooth(0.05, 0.5, slope) * 0.75)[..., None]
    turn = np.arctan2(ny, nx)
    sheen = np.stack([0.5 + 0.5 * np.cos(turn * 2 + shift) for shift in (0.6, 2.4, 4.4)], axis=-1)
    body = body * (0.8 + 0.28 * diffuse)[..., None] + (sheen - 0.5) * (0.07 * smooth(0.05, 0.35, slope))[..., None]
    up = np.clip(-ry, -1, 1)[..., None]
    sky, gold, deep = rgb("#fff6dc"), rgb(GOLD_DEEP), rgb("#8a5a14")
    env = np.where(up > 0, gold + (sky - gold) * smooth(0.0, 0.7, up), gold + (deep - gold) * smooth(0.0, 0.7, -up))
    metal = smooth(0.42, 0.8, slope)[..., None]
    color = body * (1 - metal) + env * metal
    facing = (rx * lx + ry * ly + rz * lz) / (lx * lx + ly * ly + lz * lz) ** 0.5
    away_from_cleft = smooth(0.1, 0.22, np.hypot(x, y + 0.12))
    color = color + (smooth(0.86, 0.97, facing) * 0.5 * away_from_cleft)[..., None] + (inner ** 3 * 0.12)[..., None]
    wide = int(px * 1.9) + 4
    around = _fill(wide, heart_path(wide / 2, wide / 2 - px * 0.145, px))
    light = rgb(HONEY) * (blur(around, px * 0.06) * 0.7 + blur(around, px * 0.18) * 0.55)[..., None]
    return picture(color, mask_), glow(light)


def _heart_rect(image: QImage, px: int, c: QPointF, shown: float) -> QRectF:
    """Where a heart picture made px wide goes to show a heart shown wide with its centre at c."""
    f = shown / px
    side = image.width() * f
    return QRectF(c.x() - side / 2, c.y() - (image.width() / 2 - px * 0.145) * f, side, side)


def _fill(side: int, path) -> np.ndarray:  # noqa: ANN001
    """A path filled white on black, side pixels square, as 0..1."""
    image = QImage(side, side, QImage.Format_Grayscale8)
    image.fill(0)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.setPen(Qt.NoPen)
    q.setBrush(Qt.white)
    q.drawPath(path)
    q.end()
    stride = image.bytesPerLine()
    return np.frombuffer(image.constBits(), dtype=np.uint8, count=stride * side).reshape(side, stride)[:, :side].astype(np.float32) / 255.0


def _halo_picture(px: int) -> QImage:
    """A halo of gold light px pixels across, seen a little from below, per pixel: a ring with a
    white-hot line along it, its near side brighter, blooming out into the air round it."""
    rx, ry = px / 2, px / 2 * 0.27
    w, h = int(px * 1.7) + 4, int(px * 1.15) + 4
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = (xs - w / 2) / rx, (ys - h / 2) / ry
    # Distance from the ellipse, roughly in pixels: the step from 1 over how fast it grows there.
    e = np.sqrt(x * x + y * y)
    gx, gy = x / rx, y / ry
    reach = np.maximum(e, 1e-3) / np.maximum(np.hypot(gx, gy), 1e-6)
    d = np.abs(e - 1) * reach / np.maximum(e, 1e-3)
    tube = px * 0.035
    band = 1 - smooth(tube * 0.5, tube * 1.1, d)
    core = 1 - smooth(tube * 0.1, tube * 0.5, d)
    near = 0.72 + 0.28 * smooth(-0.6, 0.6, y / np.maximum(e, 1e-3))
    light = (rgb(GOLD_DEEP) * 0.9 * band[..., None] + rgb("#fff8e6") * (core * 1.1)[..., None]) * near[..., None]
    light = light + rgb(GOLD) * (blur(band, px * 0.03) * 0.8 + blur(band, px * 0.09) * 0.5)[..., None]
    return glow(light)


def _hero(p: QPainter, t: float, centre: QPointF, size: float, u: float, plan: list, sprites: dict, hearts: dict, halos: dict, burst: list) -> None:
    """The winged heart under its halo: the heart glows in, the halo comes down over it, the wings
    unfold with a burst of light and breathe; at the end it rises into the light and fades."""
    leave = ease_in_out(win(t, 4.15, 4.95))
    rise = ease_in(win(t, 3.95, 4.95))
    form = ease_out(win(t, 0.15, 0.8))
    flash = _burst(t)
    density = _density(p)
    # The heart, drawn for the largest it gets and only ever shown smaller; made on the first frame,
    # while nothing shows yet.
    px = max(16, math.ceil(size * 1.06 * density / 8) * 8)
    if px not in hearts:
        hearts[px] = _pearl_heart(px)
    hx = max(16, math.ceil(size * 0.92 * density / 8) * 8)
    if hx not in halos:
        halos[hx] = _halo_picture(hx)
    span = size * WING
    for kind, longest in LONGEST.items():
        _sprite(sprites, kind, span * longest, density)
    a = form * (1 - leave)
    if a <= 0.01:
        return
    lift = 3 * u * math.sin(t * 1.6) - 70 * u * rise
    c = QPointF(centre.x(), centre.y() + lift)
    beat = 1 + 0.045 * max(0.0, math.sin(math.pi * win(t, 2.3, 2.5))) + 0.03 * max(0.0, math.sin(math.pi * win(t, 2.56, 2.74)))
    scale = (0.86 + 0.14 * form) * beat
    p.save()
    p.setOpacity(p.opacity() * a)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    # Light behind it all, on the wings too once they are open, and the burst as they open.
    soft_dot(p, c.x(), c.y() + size * 0.1, size * 1.5, "#fff1c8", 0.35 + 0.4 * flash)
    spread = ease_out(win(t, 0.8, 1.6))
    for mirror in (1, -1):
        soft_dot(p, c.x() + mirror * size * 0.75, c.y() - size * 0.3, size * 0.9, "#ffe2a0", 0.35 * spread)
    soft_dot(p, c.x(), c.y() + size * 0.1, size * (1.6 + 1.4 * flash), "#ffffff", 0.5 * flash)
    body, aura = hearts[px]
    shown = size * 1.06 * scale
    p.drawImage(_heart_rect(aura, px, c, shown), aura)
    k = ease_back(win(t, 0.6, 1.6), 1.2)
    if k > 0:
        opened = clamp(win(t, 0.6, 0.85))
        for mirror in (1, -1):
            p.save()
            p.setOpacity(p.opacity() * opened)
            p.translate(c.x(), 0)
            p.scale(mirror, 1)
            p.translate(-c.x(), 0)
            _wing(p, t, QPointF(c.x() + size * 0.2, c.y() - size * 0.02), span, plan, sprites, density, k)
            p.restore()
    p.drawImage(_heart_rect(body, px, c, shown), body)
    _halo(p, t, c, size, halos[hx], hx, flash, u)
    # Glints thrown out by the burst, slowing as they go.
    for angle, far, life in burst:
        age = t - 1.0
        if 0 < age < life:
            k_ = ease_out(age / life)
            x = c.x() + math.cos(angle) * far * k_
            y = c.y() + math.sin(angle) * far * k_ * 0.8
            fade = 1 - age / life
            soft_dot(p, x, y, 9 * u, GOLD, 0.6 * fade)
            star(p, x, y, 7 * u * (0.6 + 0.4 * fade), "#ffffff", fade)
    if flash > 0.02:
        # A flare across the heart, as bright light shows through a lens.
        mid = QPointF(c.x(), c.y() + size * 0.1)
        reach = size * (1.0 + 1.2 * flash)
        p.setBrush(gradient(QPointF(mid.x() - reach, 0), QPointF(mid.x() + reach, 0), ((0, HONEY, 0), (0.5, "#ffffff", 0.55 * flash), (1, HONEY, 0))))
        p.drawEllipse(mid, reach, size * 0.07)
        soft_dot(p, mid.x(), mid.y(), size * 0.8, "#ffffff", 0.75 * flash)
        star(p, mid.x(), mid.y(), size * 0.42 * flash, "#ffffff", 0.9 * flash, 0.16)
    p.restore()
    # Going, it leaves glints of its light rising from its edge.
    if rise > 0:
        for i, point in enumerate(heart_points(c.x(), c.y(), size * 1.06 * scale, 10, 0.05)):
            k = clamp(rise * 1.4 - 0.04 * i)
            if 0 < k < 1:
                y = point.y() - 90 * u * k * (0.7 + 0.06 * i)
                soft_dot(p, point.x(), y, 12 * u, GOLD, 0.6 * (1 - k))
                star(p, point.x(), y, 8 * u * math.sin(math.pi * k), "#ffffff", 1 - k * 0.6)


def _halo(p: QPainter, t: float, c: QPointF, size: float, image: QImage, px: int, flash: float, u: float) -> None:
    """The halo comes down over the heart and floats there, a glint running round it."""
    down = ease_out(win(t, 0.35, 1.1))
    if down <= 0:
        return
    rx = size * 0.46
    hc = QPointF(c.x(), c.y() - size * 0.5 - 34 * u * (1 - down) + 2.5 * u * math.sin(t * 1.9 + 0.8))
    scale = rx * 2 / px
    w, h = image.width() * scale, image.height() * scale
    p.save()
    p.setOpacity(p.opacity() * down * (0.92 + 0.08 * math.sin(t * 3.1)))
    p.drawImage(QRectF(hc.x() - w / 2, hc.y() - h / 2, w, h), image)
    p.restore()
    if flash > 0.02:
        soft_dot(p, hc.x(), hc.y(), rx * 1.6, HONEY, 0.4 * flash)
    ry = rx * 0.27
    turn = t * 2.4
    gx, gy = hc.x() + rx * math.cos(turn), hc.y() + ry * math.sin(turn)
    near = 0.5 + 0.5 * math.sin(turn)
    glint_a = down * (0.45 + 0.55 * near)
    soft_dot(p, gx, gy, 14 * u, "#fff6dc", 0.7 * glint_a)
    star(p, gx, gy, (8 + 7 * near) * u, "#ffffff", glint_a, 0.08)


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
    title = QRectF(width * 0.36, height * 0.04, width * 0.34, height * 0.24)
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
