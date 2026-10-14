"""天使: a crest of gold-leaf wings and a gold halo round the title, in golden light.

Warm gold light washes in at the top and down the sides. A halo of molten gold comes down to float
just above the title 推演成功, and golden rays stream down from it, slowly sweeping and breathing,
faint over the names. Two great wings of gold leaf unfold from behind the title in a burst of light:
every feather is polished metal shaded per pixel, deep amber in its hollows and pale gold where it
catches the light, and a sheen runs out along each wing as it opens, and again later. They spread
to either side of the top of the screen and breathe, and fade to a whisper behind the title's lines
and leave its words clear. Gold dust sifts down from them and glints on their feathers; glowing
golden clouds drift in the two top corners, gold feathers drift down the two sides, gold motes rise
from the bottom corners. At the end the halo and the wings rise into the light and it all fades.

The marks are gilded too, and keep moving: the ring is a band of polished gold round 准备案件还原,
soft rays of light shimmering beyond it and a glint running round it; the badge a gold halo disc,
its field finely engraved, a raised star in its middle and rays turning round it; the card ivory
paper in a gilt frame with filigree scrolls in its corners and a small pair of gilded wings on its
top edge, a sheen passing over the gold now and then; a tiny gold feather before each name.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient, QTransform

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
from blacklist_detect.love_scenes.light import blur, glow, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# Soft light throughout: drawn at one pixel per point and scaled up on a sharper screen; the wings,
# with their fine feathers, and the halo are drawn on top at the screen's own sharpness.
MAX_RATIO = 1.0
IVORY = "#fffaf0"
HONEY = "#ffd98a"
GOLD = "#f2c14e"
GOLD_PALE = "#fff0bf"
AMBER = "#e9a23b"
LOOK = {
    "glow": (255, 200, 90),
    "rim": "#f5cf6a",
    "band": ("#ffe9a8", "#e6b04a"),
    "card": (IVORY, "#f7e8c6"),
    "edge": "#d4a440",
    "ink": "#64410c",
    "flowers": (("#fff8e0", "#f6d68a", "#d9a441"), ("#fffaf0", "#ffe9b0", "#c9962a")),
    "disc": ("#fff7dc", "#e9bf5c"),
    "heart": ("#ffe39a", "#c98a1f"),
    "deep": "#c98a1f",
    "deep_glow": (245, 190, 80),
}
MARKS_ANIMATED = True
# Room above the card for its little gilded wings, and the names' margins inside its gilt frame.
CARD_TOP = 18
CARD_PAD = (14, 10, 14, 9)
# The marks' windows reach this far past the cover and the badge (the glow room the app gives them).
ROOM = 9
# Polished gold from its darkest hollow to the light it catches: brown, amber, gold, pale gold, white.
RAMP = (
    (0.0, "#2a1703"),
    (0.25, "#6e420b"),
    (0.5, "#b97d1c"),
    (0.68, "#e3ab3c"),
    (0.82, "#f6cf68"),
    (0.93, "#ffeaa6"),
    (1.0, "#fffbee"),
)
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
# Pictures made once and kept: feathers, and the marks for each size and sharpness they are shown at.
_SPRITES: dict[tuple[str, int], tuple[QImage, float]] = {}
_MARKS: dict[tuple, tuple] = {}


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(29)
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
    sprites = _SPRITES
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
        for i in range(12)
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
        for i in range(36)
    ]
    dust = _dust(roots, span, u, rnd)
    glints = _glint_spots(rnd)
    sparkles = _sparkle_spots(width, height, gap, u, rnd)
    # Glints the burst throws out along the wings, either way and a little up.
    burst = [
        (rnd.choice((0.0, math.pi)) + rnd.uniform(-0.45, 0.12) * (1 if i % 2 else -1), rnd.uniform(160, 460) * u, rnd.uniform(0.7, 1.2))
        for i in range(22)
    ]

    def crest(p: QPainter, t: float) -> None:
        p.save()
        p.setOpacity(p.opacity() * win(t, 0.0, 0.3))
        _crest(p, t, halo_at, roots, span, band, cut, u, plan, sprites, opened, halos, burst, glints)
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
        _dust_paint(p, t, dust, height, u, 1 - leave)
        p.restore()
        if sharp:
            crest(p, t)

    paint.sharp = crest
    return paint


def _burst(t: float) -> float:
    """The light that bursts as the wings open: quick to come, slow to go."""
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


def _ramp(b: np.ndarray) -> np.ndarray:
    """Brightness 0..1 as polished gold shows it (RAMP), straight color (h, w, 3)."""
    at = [k for k, _color in RAMP]
    shades = [rgb(color) for _k, color in RAMP]
    b = np.clip(b, 0, 1)
    return np.stack([np.interp(b, at, [shade[c] for shade in shades]) for c in range(3)], axis=-1).astype(np.float32)


def _shine(height: np.ndarray, light: tuple[float, float, float] = (-0.4, -0.75, 0.55), gloss: float = 20.0) -> np.ndarray:
    """How bright polished metal looks where it has this height (in pixels), lit from light (x right,
    y down, z out of the screen): a warm sky reflected everywhere, more where it faces the light, and
    a sharp highlight where it mirrors it. About 0.6 where flat."""
    gy, gx = np.gradient(height)
    norm = np.sqrt(gx * gx + gy * gy + 1)
    size = math.sqrt(sum(c * c for c in light))
    lx, ly, lz = (c / size for c in light)
    half = math.sqrt(lx * lx + ly * ly + (lz + 1) ** 2)
    hx, hy, hz = lx / half, ly / half, (lz + 1) / half
    lit = np.clip((-gx * lx - gy * ly + lz) / norm, 0, 1)
    spec = np.clip((-gx * hx - gy * hy + hz) / norm, 0, 1) ** gloss
    return 0.3 + 0.45 * lit + 0.6 * spec


def _title(width: float, height: float, u: float) -> tuple[QRectF, QRectF]:
    """The title's words with a little room round them, and the band of it and the lines under it."""
    words = QRectF(width * 0.43, height * 0.085, width * 0.2, height * 0.115).adjusted(-14 * u, -10 * u, 14 * u, 8 * u)
    lines = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.24)
    return words, lines


def _heaven(p: QPainter, width: float, height: float, u: float) -> None:
    """Warm gold light at the top and down the sides, strongest above the title where the halo is;
    a faint glow in the bottom corners. Drawn once."""
    top = height * 0.3
    p.fillRect(QRectF(0, 0, width, top), gradient(QPointF(0, 0), QPointF(0, top), ((0, "#ffe6a6", 0.26), (0.35, "#ffcf6e", 0.08), (1, "#ffcf6e", 0))))
    side = 170 * u
    for start, end, rect in (
        (QPointF(0, 0), QPointF(side, 0), QRectF(0, 0, side, height)),
        (QPointF(width, 0), QPointF(width - side, 0), QRectF(width - side, 0, side, height)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, "#ffe0a0", 0.24), (0.45, "#ffc95e", 0.08), (1, "#ffc95e", 0))))
    for cx, cy, r, alpha in ((0.53, -0.08, 540, 0.34), (0.04, -0.05, 440, 0.26), (0.96, -0.05, 440, 0.26), (0.0, 1.0, 340, 0.18), (1.0, 1.0, 340, 0.18)):
        light = QRadialGradient(QPointF(width * cx, height * cy), r * u)
        light.setColorAt(0, col("#ffe9b8", alpha))
        light.setColorAt(0.45, col("#ffc95e", alpha * 0.42))
        light.setColorAt(1, col("#ffc95e", 0))
        p.fillRect(QRectF(0, 0, width, height), light)


def _ray_layer(width: float, height: float, source: QPointF, seed: int, u: float) -> tuple[QRectF, QImage]:
    """Golden rays streaming down and out from the halo, worked out per pixel at SOFT size: streaks
    by angle, each its own length, coming on just beyond the halo and fading as they go. Brightest
    out to the sides, under the wings; softer straight down. A margin round the stage lets them turn."""
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
    tint = rgb("#ffb43c") + (rgb("#ffeab0") - rgb("#ffb43c")) * (streak * 0.7)[..., None]
    return box, glow(tint * (strength * 1.15)[..., None])


def _ray_mask(width: float, height: float, gap: QRectF, u: float) -> QImage:
    """Where the rays may show, at SOFT size: faint over the names and the title, none over the gap."""
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = xs / SOFT, ys / SOFT
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    words, lines = _title(width, height, u)
    keep = (1 - 0.76 * _box(x, y, names, 60 * u)) * (1 - 0.45 * _box(x, y, lines, 40 * u)) * (1 - 0.6 * _box(x, y, words, 30 * u))
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
        q.setOpacity(clamp(a * (breathe * 0.8 + 0.9 * flash)))
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
    """A bank of golden cloud heaped in a top corner, per pixel: round billows along it, their edges
    frayed with noise, glowing pale gold where the light from above falls, rimmed bright gold where
    it catches their tops, a warm amber shade beneath, thinning away toward the middle of the screen."""
    rnd = np.random.default_rng(seed)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    if right:
        xs = w - xs
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
    cover = smooth(-h * 0.03, h * 0.16, field)
    gy, gx = np.gradient(blur(np.maximum(field, 0), max(1.0, h * 0.015)))
    norm = np.sqrt(gx * gx + gy * gy + 1)
    nx, ny, nz = -gx / norm, -gy / norm, 1 / norm
    lx, ly, lz = 0.3 if right else -0.3, -0.82, 0.5
    lit = np.clip((nx * lx + ny * ly + nz * lz) / math.sqrt(lx * lx + ly * ly + lz * lz), 0, 1)
    lit = np.clip(lit * (0.8 + 0.4 * noise(w, h, h * 0.06, 3, seed + 90)), 0, 1)
    # Lit through with gold: the shaded side a warm amber, never grey.
    color = rgb("#e9b660") + (rgb("#fff3d2") - rgb("#e9b660")) * (lit ** 0.7)[..., None]
    rim = blur((1 - smooth(-h * 0.02, h * 0.12, field)) * smooth(-h * 0.06, h * 0.02, field) * np.clip(-ny * 1.6 + 0.1, 0, 1), max(1.0, h * 0.012))
    color = color + (rgb("#ffc53d") * 1.15 - color) * np.clip(rim * 2.4, 0, 0.95)[..., None]
    inward = 1 - smooth(0.62, 1.0, xs / w)
    alpha = np.clip(cover * (0.6 + 0.33 * lit) + rim * 0.45, 0, 1)
    light = color * alpha[..., None] + rgb(HONEY) * (blur(cover, h * 0.06) * (1 - alpha) * 0.4)[..., None]
    return glow(light * (inward * dim)[..., None])


def _clouds(width: float, height: float, u: float) -> list[tuple[QRectF, QImage, float]]:
    """The two corners' clouds, a dimmer bank behind and a brighter one before it, at half size:
    (where, picture, how far it drifts over the scene)."""
    out = []
    # They drift outward, and reach past the edge so their cut end never shows.
    margin = 12 * u
    for right, w, h, seed, dim, drift in (
        (False, 0.34, 0.26, 11, 0.7, -10),
        (False, 0.24, 0.2, 12, 0.95, -20),
        (True, 0.32, 0.25, 13, 0.7, 9),
        (True, 0.22, 0.19, 14, 0.95, 16),
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
    """A feather of gold leaf px pixels long, quill on the left pointing right, per pixel: a vane on
    each side of the shaft (the leading one narrower), each a gentle dome grooved by fine barbs that
    sweep toward the tip, the odd split where the barbs part, the shaft a raised ridge; shaded as
    polished gold lit from above, each flake of leaf catching the light a little differently, deeper
    at the base and paler toward the tip. Also where the quill is, as a share of its height."""
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
    alpha = inside * (1 - 0.6 * split) * (0.86 + 0.12 * (1 - r * r)) * (0.55 + 0.45 * downy)
    shaft_w = px * 0.016 * (1 - 0.75 * s) + 0.35
    shaft = (1 - smooth(shaft_w * 0.45, shaft_w, np.abs(dv))) * (1 - smooth(0.9, 0.99, s))
    # A shallow tent: each vane slopes gently away from the shaft, the upper toward the light.
    tent = (1 - np.clip(r, 0, 1)) * half * 0.2
    height = tent * inside + barbs * spacing * 0.13 + shaft * shaft_w * 1.2
    flakes = noise(px, high, px / 6, 2, px + 3) - 0.5
    # Polished, it mirrors a bright streak of sky along the upper vane and a fainter one along the
    # lower; each barb's crest catches a fine line of light.
    across = np.where(dv < 0, -1.0, 1.0) * np.clip(r, 0, 1)
    streak = 0.2 * np.exp(-(((across + 0.45) / 0.22) ** 2)) + 0.08 * np.exp(-(((across - 0.5) / 0.2) ** 2))
    bright = _shine(blur(height, 0.5), (-0.3, -0.8, 0.55), 28) + streak + (barbs ** 3 - 0.3) * 0.15 + flakes * 0.16 + 0.24 * (s - 0.62)
    color = _ramp(bright + shaft * 0.1)
    # A soft dark shadow just below its edge, so a feather shows where it lies over the next.
    shadow = np.roll(blur(inside * smooth(0.0, 0.2, s), px * 0.014), max(1, round(px * 0.008)), axis=0) * 0.38 * (1 - inside)
    alpha = np.maximum(alpha, shaft * 0.95)
    under = shadow * (1 - alpha)
    total = alpha + under
    color = (color * alpha[..., None] + rgb("#2e1904") * under[..., None]) / np.maximum(total, 1e-4)[..., None]
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


def _arm(at: float) -> tuple[float, float]:
    """Where along the open right wing's arm a feather sits, as shares of the wing from its root."""
    (x0, y0), (cx, cy), (x1, y1) = (0.0, 0.0), (0.26, -0.17), (0.62, -0.17)
    m = 1 - at
    return m * m * x0 + 2 * m * at * cx + at * at * x1, m * m * y0 + 2 * m * at * cy + at * at * y1


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
    # Deeper amber toward the trailing tips, away from the light falling on the arm.
    q.setCompositionMode(QPainter.CompositionMode_SourceAtop)
    q.fillRect(box, gradient(QPointF(0, -0.2 * span), QPointF(0.1 * span, 0.3 * span), ((0, "#5a3306", 0), (1, "#5a3306", 0.4))))
    q.end()
    return box, image


def _wing_mask(band: QRectF, width: float, height: float, u: float) -> QImage:
    """Where the wings may show over band, at SOFT size: a whisper behind the title's lines and none
    over its words."""
    w, h = max(1, round(band.width() * SOFT)), max(1, round(band.height() * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = band.left() + xs / SOFT, band.top() + ys / SOFT
    words, lines = _title(width, height, u)
    keep = (1 - 0.8 * _box(x, y, lines, 50 * u)) * (1 - _box(x, y, words, 24 * u))
    return picture(np.ones((h, w, 3), dtype=np.float32), keep)


def _halo_picture(px: int) -> QImage:
    """A halo of molten gold px pixels across, seen a little from below, per pixel: a round band
    shaded across like a tube, a white-hot line where it catches the light, its near side brighter, a
    fine second ring inside it, all blooming out in amber light round it."""
    rx, ry = px / 2, px / 2 * 0.27
    w, h = int(px * 1.5) + 4, int(px * 0.85) + 4
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    x, y = (xs - w / 2) / rx, (ys - h / 2) / ry
    # Distance from the ellipse, roughly in pixels: the step from 1 over how fast it grows there.
    e = np.sqrt(x * x + y * y)
    gx, gy = x / rx, y / ry
    reach = np.maximum(e, 1e-3) / np.maximum(np.hypot(gx, gy), 1e-6)
    signed = (e - 1) * reach / np.maximum(e, 1e-3)
    d = np.abs(signed)
    tube = px * 0.034
    band = 1 - smooth(tube * 0.75, tube * 1.05, d)
    across = np.clip(signed / tube, -1, 1)
    near = 0.72 + 0.28 * smooth(-0.6, 0.6, y / np.maximum(e, 1e-3))
    # Round across, lit from above: the highlight a little toward its outer edge on the far side.
    bright = 0.35 + 0.4 * np.sqrt(np.clip(1 - across * across, 0, 1)) + 0.55 * np.exp(-(((across + 0.25) / 0.3) ** 2))
    metal = _ramp(bright * near)
    inner = 1 - smooth(px * 0.004, px * 0.009, np.abs(signed + tube * 2.6))
    light = metal * (band * 0.95)[..., None] + rgb(GOLD_PALE) * (inner * 0.75 * near)[..., None]
    light = light + rgb(AMBER) * (blur(band, px * 0.025) * 0.7 + blur(band, px * 0.075) * 0.5 + blur(band, px * 0.16) * 0.3)[..., None]
    return glow(light)


def _crest(p: QPainter, t: float, halo_at: QPointF, roots: tuple, span: float, band: QRectF, cut: QImage, u: float, plan: list, sprites: dict, opened: dict, halos: dict, burst: list, glints: list) -> None:
    """The crest round the title: the halo comes down above it, the wings unfold from behind it with
    a burst of light and breathe, glints coming and going on their gold; at the end they rise into
    the light and fade."""
    leave = ease_in_out(win(t, 4.15, 4.95))
    rise = ease_in(win(t, 3.95, 4.95))
    flash = _burst(t)
    density = _density(p)
    # The pictures, made on the first frame while nothing shows yet.
    rx = 112 * u
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
        _wing_glints(p, t, glints, roots, span, lift, u)
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
            soft_dot(p, x, y, 11 * u, AMBER, 0.6 * fade)
            star(p, x, y, 8 * u * (0.6 + 0.4 * fade), "#fff6dc", fade)
    # Going, the halo leaves glints of its light rising from its ring.
    if rise > 0:
        for i in range(12):
            turn = i / 12 * 2 * math.pi + 0.3
            k_ = clamp(rise * 1.4 - 0.035 * i)
            if 0 < k_ < 1:
                x = hc.x() + rx * math.cos(turn)
                y = hc.y() + rx * 0.27 * math.sin(turn) - 70 * u * k_ * (0.7 + 0.05 * i)
                soft_dot(p, x, y, 12 * u, GOLD, 0.6 * (1 - k_))
                star(p, x, y, 8 * u * math.sin(math.pi * k_), "#fffaf0", 1 - k_ * 0.6)


def _sheen(t: float) -> float | None:
    """How far out along the wings the sheen has run, 0 at the roots to past the tips, or None: once
    as they finish opening, once more later."""
    for start, end in ((1.45, 2.45), (3.0, 3.9)):
        if start <= t <= end:
            return ease_in_out(win(t, start, end))
    return None


def _wings(p: QPainter, t: float, roots: tuple, span: float, band: QRectF, cut: QImage, lift: float, plan: list, sprites: dict, opened: dict, density: float, k: float) -> None:
    """Both wings drawn on a picture of the band they live in, at the screen's sharpness, a sheen
    run along their gold, cut away over the title, and laid on: a warm light behind them once they
    are open. Unfolding, each feather moves; open, each wing is laid whole, breathing as it turns a
    little about its root."""
    layer = QImage(max(1, math.ceil(band.width() * density)), max(1, math.ceil(band.height() * density)), QImage.Format_ARGB32_Premultiplied)
    layer.fill(Qt.transparent)
    q = QPainter(layer)
    q.setRenderHint(QPainter.Antialiasing)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.scale(density, density)
    q.translate(-band.left(), -band.top() + lift)
    spread = ease_out(win(t, 0.8, 1.6))
    for mirror, root in zip((1, -1), roots, strict=True):
        soft_dot(q, root.x() + mirror * span * 0.5, root.y() - span * 0.15, span * 0.5, "#ffc95e", 0.24 * spread)
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
    sweep = _sheen(t)
    if sweep is not None:
        # A slanted band of pale light laid over the gold only, running out from each root to the tip.
        q.setOpacity(1.0)
        q.setCompositionMode(QPainter.CompositionMode_SourceAtop)
        reach = span * 0.16
        for mirror, root in zip((1, -1), roots, strict=True):
            x = root.x() + mirror * span * (sweep * 1.35 - 0.2)
            shine = QLinearGradient(QPointF(x - mirror * reach, root.y() + reach * 0.5), QPointF(x + mirror * reach, root.y() - reach * 0.5))
            strength = math.sin(math.pi * sweep) * 0.9
            shine.setColorAt(0, col("#fff6d8", 0))
            shine.setColorAt(0.4, col("#ffe9a6", strength * 0.5))
            shine.setColorAt(0.5, col("#fffcf0", strength))
            shine.setColorAt(0.6, col("#ffe9a6", strength * 0.5))
            shine.setColorAt(1, col("#fff6d8", 0))
            q.fillRect(QRectF(x - reach * 2, band.top() - lift, reach * 4, band.height()), shine)
    q.resetTransform()
    q.setOpacity(1.0)
    q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    q.drawImage(QRectF(0, 0, layer.width(), layer.height()), cut)
    q.end()
    p.drawImage(band, layer)


def _glint_spots(rnd: random.Random) -> list[tuple]:
    """Where the gold catches the light on the open wings now and then: on a feather of either wing,
    toward the outer half and the tips, as (side, x, y from the root in shares of the wing, when, how long)."""
    out = []
    for i in range(16):
        at = rnd.uniform(0.25, 1.0)
        x, y = _arm(at)
        reach = rnd.uniform(0.05, 0.3)
        angle = math.radians(64 - 70 * at)
        out.append(((1, -1)[i % 2], x + math.cos(angle) * reach, y + math.sin(angle) * reach, rnd.uniform(1.7, 3.9), rnd.uniform(0.5, 0.9)))
    return out


def _wing_glints(p: QPainter, t: float, glints: list, roots: tuple, span: float, lift: float, u: float) -> None:
    """The glints on the wings: a little star flaring and going, with a warm halo."""
    for side, x, y, when, life in glints:
        k = win(t, when, when + life)
        if not 0 < k < 1:
            continue
        root = roots[0] if side > 0 else roots[1]
        shine = math.sin(math.pi * k)
        gx, gy = root.x() + side * x * span, root.y() + y * span + lift
        soft_dot(p, gx, gy, 14 * u, HONEY, 0.5 * shine)
        star(p, gx, gy, (6 + 10 * shine) * u, "#fffaf0", shine, 0.08)


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
    soft_dot(p, 0, 0, rx * 2.0, "#ffc24f", 0.42 * down)
    p.restore()
    if flash > 0.02:
        # A soft bloom, wide and low, kept above the words.
        p.save()
        p.translate(hc)
        p.scale(1, 0.42)
        soft_dot(p, 0, 0, rx * 2.6, "#fff6dc", 0.55 * flash)
        soft_dot(p, 0, 0, rx * 4.2, "#ffc24f", 0.4 * flash)
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
    for offset, size in ((0.0, 1.0), (math.pi * 0.9, 0.6)):
        turn = t * 2.2 + offset
        gx, gy = rx * math.cos(turn), rx * 0.27 * math.sin(turn)
        near = 0.5 + 0.5 * math.sin(turn)
        shine = down * (0.4 + 0.6 * near) * size
        soft_dot(p, gx, gy, 18 * u * size, "#ffe9b0", 0.7 * shine)
        star(p, gx, gy, (9 + 9 * near) * u * size, "#fffdf6", shine, 0.08)
    p.restore()


def _falling(p: QPainter, t: float, falling: list[tuple], sprites: dict, u: float, a: float) -> None:
    """Gold feathers drifting down the sides, swaying, and turning about their shafts as they go,
    flashing as they face the light."""
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
        p.setOpacity(base * fade * (0.8 + 0.2 * abs(turn)))
        back = math.radians(angle)
        _lay(p, sprite, cx - math.cos(back) * length / 2, cy - math.sin(back) * length / 2, angle, length, across)
        if abs(turn) > 0.92:
            # Flat to the light, its gold flashes.
            flare = (abs(turn) - 0.92) / 0.08
            p.setOpacity(base * fade)
            soft_dot(p, cx, cy, 16 * u, HONEY, 0.45 * flare)
            star(p, cx, cy, 9 * u * flare, "#fffaf0", flare, 0.1)
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
        soft_dot(p, px, py, r * 4, AMBER, 0.42 * fade)
        soft_dot(p, px, py, r * 1.3, "#fff4d0", 0.95 * fade * twinkle)


def _dust(roots: tuple, span: float, u: float, rnd: random.Random) -> list[tuple]:
    """Gold dust shed by the open wings: specks born under either wing, as (when, x, y, drift, fall,
    size, phase, how long)."""
    out = []
    for i in range(84):
        side = (1, -1)[i % 2]
        root = roots[0] if side > 0 else roots[1]
        at = rnd.uniform(0.3, 1.0)
        x, y = _arm(at)
        hang = rnd.uniform(0.02, 0.24)
        out.append(
            (
                rnd.uniform(1.15, 4.1),
                root.x() + side * (x + 0.25 * hang) * span,
                root.y() + (y + hang) * span,
                side * rnd.uniform(4, 18) * u,
                rnd.uniform(16, 40) * u,
                rnd.uniform(1.1, 2.6) * u,
                rnd.uniform(0, 6.28),
                rnd.uniform(1.4, 2.4),
            )
        )
    return out


def _dust_paint(p: QPainter, t: float, dust: list[tuple], height: float, u: float, a: float) -> None:
    """The dust sifting down and outward, each speck glinting as it turns, gone before the names."""
    if a <= 0.01:
        return
    floor = height * 0.3
    for born, x, y, drift, fall, r, phase, life in dust:
        age = t - born
        if age <= 0 or age > life:
            continue
        px = x + drift * age + 5 * u * math.sin(age * 2.3 + phase)
        py = y + fall * age
        fade = min(1.0, age / 0.3) * min(1.0, (life - age) / 0.6) * clamp((floor - py) / (40 * u)) * a
        if fade <= 0.01:
            continue
        flick = abs(math.sin(age * 4.2 + phase)) ** 3
        soft_dot(p, px, py, r * 4.5, GOLD, 0.42 * fade)
        soft_dot(p, px, py, r * (1.0 + 0.6 * flick), "#fff6dc", fade * (0.5 + 0.5 * flick))
        if flick > 0.6:
            star(p, px, py, r * 4 * flick, "#fffaf0", fade * flick, 0.1)


def _sparkle_spots(width: float, height: float, gap: QRectF, u: float, rnd: random.Random) -> list[tuple]:
    """Where sparkles come and go: the top band either side of the title, and down the sides."""
    names = QRectF(width * 0.12, height * 0.27, width * 0.83, height * 0.6)
    title = QRectF(width * 0.36, height * 0.0, width * 0.34, height * 0.34)
    out = []
    while len(out) < 22:
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
        star(p, x, y, r * (0.6 + 0.6 * shine), "#fffaf0", shine, 0.1)
        if r > 9 * u:
            star(p, x, y, r * 0.5 * shine, mix(GOLD, "#ffffff", 0.4), shine, 0.25)


# The marks.


def _kept(key: tuple, build: Callable[[], tuple]) -> tuple:
    """The pictures for a mark at one size and sharpness, made once; a few sizes are kept."""
    if key not in _MARKS:
        if len(_MARKS) > 24:
            _MARKS.clear()
        _MARKS[key] = build()
    return _MARKS[key]


def _grid(w: float, h: float, density: float) -> tuple[int, int, np.ndarray, np.ndarray]:
    """A picture's size in pixels for w by h points, and each pixel's middle in points."""
    pw, ph = max(1, math.ceil(w * density)), max(1, math.ceil(h * density))
    ys, xs = np.mgrid[0:ph, 0:pw].astype(np.float32) + 0.5
    return pw, ph, xs / density, ys / density


def _rounded(xs: np.ndarray, ys: np.ndarray, rect: QRectF, radius: float) -> np.ndarray:
    """How far each point is outside a rounded rectangle, in points (inside, below 0)."""
    cx, cy = rect.center().x(), rect.center().y()
    qx = np.abs(xs - cx) - (rect.width() / 2 - radius)
    qy = np.abs(ys - cy) - (rect.height() / 2 - radius)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - radius


def _rays_around(angle: np.ndarray, counts: tuple[int, ...], seed: int) -> np.ndarray:
    """Rays all round, 0..1 by angle: a few waves of whole counts each, so they meet where they start."""
    rnd = np.random.default_rng(seed)
    out = np.full(angle.shape, 0.5, dtype=np.float32)
    for n, weight in zip(counts, (0.28, 0.14, 0.08), strict=False):
        out += weight * np.cos(n * angle + rnd.uniform(0, 6.28))
    return smooth(0.42, 0.88, out)


def _ring_pictures(w: float, h: float, density: float) -> tuple[QImage, QImage, QImage, QImage]:
    """The ring for a cover w by h, at density, per pixel, the window being the cover and ROOM round
    it: the band of polished gold along the cover's edge with a fine line of pale gold inside it; its
    amber glow; and two sets of soft rays beyond it, to shimmer from one to the other."""
    width, height = w + 2 * ROOM, h + 2 * ROOM
    _pw, _ph, xs, ys = _grid(width, height, density)
    cover = QRectF(ROOM, ROOM, w, h)
    radius = max(4.0, h * 0.14)
    edge = _rounded(xs, ys, cover, radius)
    middle, half = -2.6, 2.4
    k = np.abs(edge - middle) / half
    band = np.clip((half - np.abs(edge - middle)) * density + 0.5, 0, 1)
    height_px = np.sqrt(np.clip(1 - k * k, 0, 1)) * half * 0.9 * density
    bright = _shine(height_px, (-0.35, -0.8, 0.5))
    line = np.clip((0.45 - np.abs(edge + 6.6)) * density + 0.5, 0, 1)
    color = _ramp(bright)
    color = color * (1 - line[..., None] * (1 - band[..., None])) + rgb(GOLD_PALE) * (line * (1 - band))[..., None]
    metal = picture(color, np.maximum(band, line * 0.85))
    lit = glow(rgb(AMBER) * (blur(band, 2.6 * density) * 0.75 * (edge > -1))[..., None])
    outside = (1 - smooth(0.0, ROOM, edge)) ** 1.4 * smooth(-0.5, 1.5, edge)
    angle = np.arctan2((ys - height / 2) / (h / 2), (xs - width / 2) / (w / 2))
    rays = []
    for seed in (2, 7):
        streak = _rays_around(angle, (27, 43, 71), seed)
        tint = rgb("#ffc24f") + (rgb("#fff0c4") - rgb("#ffc24f")) * streak[..., None] * 0.6
        rays.append(glow(tint * (outside * (0.08 + 0.92 * streak) * 1.5)[..., None]))
    return metal, lit, rays[0], rays[1]


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A band of polished gold round the button, soft golden rays shimmering beyond it, two glints
    running round it."""
    density = _density(p)
    metal, lit, rays_a, rays_b = _kept(("ring", round(cover.width(), 1), round(cover.height(), 1), round(density, 2)), lambda: _ring_pictures(cover.width(), cover.height(), density))
    window = cover.adjusted(-ROOM, -ROOM, ROOM, ROOM)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    shimmer = 0.5 + 0.5 * math.sin(t * 1.4)
    breathe = 0.72 + 0.28 * math.sin(t * 2.2)
    p.setOpacity(breathe * (1 - shimmer))
    p.drawImage(window, rays_a)
    p.setOpacity(breathe * shimmer)
    p.drawImage(window, rays_b)
    p.setOpacity(0.8 + 0.2 * math.sin(t * 2.2))
    p.drawImage(window, lit)
    p.setOpacity(1.0)
    p.drawImage(window, metal)
    path = QPainterPath()
    radius = max(4.0, cover.height() * 0.14)
    path.addRoundedRect(cover.adjusted(2.6, 2.6, -2.6, -2.6), radius - 2.6, radius - 2.6)
    for offset, size in ((0.0, 1.0), (0.5, 0.7)):
        at = path.pointAtPercent((t / 3.6 + offset) % 1.0)
        soft_dot(p, at.x(), at.y(), 8 * size, "#ffe9b0", 0.75)
        star(p, at.x(), at.y(), 7 * size, "#fffdf6", 0.95, 0.1)


def _star_radius(angle: np.ndarray, outer: float, inner: float) -> np.ndarray:
    """A four-point star's edge by angle, its sides straight: outer at its points (right, down, left,
    up), inner in the notches between."""
    a = np.abs((angle + math.pi / 4) % (math.pi / 2) - math.pi / 4)
    # The side from the point (outer, 0) to the notch, inner out at 45 degrees, where the ray at a meets it.
    notch = inner / math.sqrt(2)
    nx, ny = notch, outer - notch
    return nx * outer / (nx * np.cos(a) + ny * np.sin(a))


def _badge_pictures(side: float, density: float) -> tuple[QImage, QImage, QImage]:
    """The badge for a box side wide, at density, per pixel, the window being the box and ROOM round
    it: a disc of polished gold with a raised bezel and a groove inside it, its sunken field spun
    like a coin's so the light lies across it in a bow, and a star raised in its middle, four long
    points and four short, in paler gold; its glow; and the rays round it."""
    width = side + 2 * ROOM
    _pw, _ph, xs, ys = _grid(width, width, density)
    dx, dy = xs - width / 2, ys - width / 2
    r = np.hypot(dx, dy)
    angle = np.arctan2(dy, dx)
    big = side * 0.44
    disc = np.clip((big - r) * density + 0.5, 0, 1)
    bezel = np.sqrt(np.clip(1 - ((r - big * 0.9) / (big * 0.12)) ** 2, 0, 1)) * big * 0.09
    reach_long = _star_radius(angle, big * 0.74, big * 0.2)
    reach_short = _star_radius(angle + math.pi / 4, big * 0.46, big * 0.14)
    # Each point a ridge with a facet either side, highest at the middle.
    raised = np.maximum(np.clip(1 - r / reach_long, 0, 1) * big * 0.3, np.clip(1 - r / reach_short, 0, 1) * big * 0.2)
    star_in = np.clip((np.maximum(reach_long - r, reach_short - r)) * density + 0.5, 0, 1)
    height_px = blur(np.maximum(bezel, raised) * density, 0.35 * density)
    bright = _shine(height_px, (-0.45, -0.75, 0.5), 16)
    # The field, spun: the light lies across it in a bow, brightest along the line toward the light.
    spun = 0.16 * np.cos(2 * (angle + 2.1))
    field = (r < big * 0.8) * (1 - star_in)
    groove = 1 - smooth(0.0, big * 0.035, np.abs(r - big * 0.79))
    bright = bright + field * (spun - 0.16) + 0.24 * star_in - 0.3 * groove
    metal = picture(_ramp(bright), disc)
    outside = (1 - smooth(big, width / 2, r)) * smooth(big * 0.9, big * 1.05, r)
    lit = glow(rgb(AMBER) * ((1 - smooth(big * 0.8, width / 2, r)) * 0.7 * smooth(big * 0.6, big, r))[..., None])
    streak = _rays_around(angle, (16, 28, 44), 5)
    rays = glow((rgb("#ffcf63") + (rgb("#fff3cc") - rgb("#ffcf63")) * streak[..., None] * 0.6) * (outside * (0.1 + 0.9 * streak))[..., None])
    return metal, lit, rays


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A gold halo disc with a raised star, rays of light turning slowly round it, a glint coming
    to the star's top point now and then."""
    density = _density(p)
    metal, lit, rays = _kept(("badge", round(box.width(), 1), round(density, 2)), lambda: _badge_pictures(box.width(), density))
    window = box.adjusted(-ROOM, -ROOM, ROOM, ROOM)
    centre = box.center()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.save()
    p.translate(centre)
    p.rotate(t * 9)
    p.setOpacity(0.75 + 0.25 * math.sin(t * 2.0))
    p.drawImage(window.translated(-centre.x(), -centre.y()), rays)
    p.restore()
    p.drawImage(window, lit)
    p.drawImage(window, metal)
    k = (t % 2.8) / 0.9
    if k < 1:
        shine = math.sin(math.pi * k)
        x, y = centre.x(), centre.y() - box.width() * 0.44 * 0.62
        soft_dot(p, x, y, box.width() * 0.2, "#fff0c4", 0.6 * shine)
        star(p, x, y, box.width() * (0.08 + 0.14 * shine), "#fffdf6", shine, 0.08)


def _filigree(q: QPainter, frame: QRectF, size: float) -> None:
    """Scrolls in each corner of frame: from the corner one runs along the top or bottom edge and one
    down or up the side, each coiling, with a small bead where they meet."""
    q.save()
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        q.save()
        q.translate(frame.center())
        q.scale(sx, sy)
        corner = QPointF(-frame.width() / 2, -frame.height() / 2)
        q.translate(corner)
        q.setPen(QPen(Qt.white, size * 0.11, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        q.setBrush(Qt.NoBrush)
        for swap in (False, True):
            q.save()
            if swap:
                # Mirrored about the corner's diagonal, so the side's scroll coils the same way.
                q.setTransform(QTransform(0, 1, 1, 0, 0, 0), True)
            path = QPainterPath(QPointF(size * 0.25, size * 0.25))
            path.cubicTo(size * 0.6, size * 0.05, size * 1.0, size * 0.05, size * 1.35, size * 0.32)
            path.cubicTo(size * 1.6, size * 0.55, size * 1.45, size * 0.85, size * 1.2, size * 0.72)
            path.cubicTo(size * 1.05, size * 0.62, size * 1.15, size * 0.45, size * 1.28, size * 0.52)
            q.drawPath(path)
            q.restore()
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawEllipse(QPointF(size * 0.22, size * 0.22), size * 0.17, size * 0.17)
        q.restore()
    q.restore()


def _little_wings(q: QPainter, x: float, y: float, size: float) -> None:
    """A pair of little wings spread either side of (x, y), each three feathers fanning up and out,
    a tiny halo over a bead between them; each feather edged so it shows from the next."""
    for mirror in (1, -1):
        for length, angle, thick in ((size * 1.25, -14, size * 0.3), (size * 1.0, -36, size * 0.28), (size * 0.72, -58, size * 0.26)):
            q.save()
            q.translate(x + mirror * size * 0.22, y)
            q.scale(mirror, 1)
            q.rotate(angle)
            feather = QPainterPath(QPointF(0, 0))
            feather.cubicTo(length * 0.25, -thick * 1.1, length * 0.75, -thick * 0.9, length, -thick * 0.2)
            feather.cubicTo(length * 0.75, thick * 0.55, length * 0.3, thick * 0.6, 0, 0)
            q.setPen(QPen(Qt.black, size * 0.07))
            q.setBrush(Qt.white)
            q.drawPath(feather)
            q.restore()
    q.setPen(QPen(Qt.black, size * 0.06))
    q.setBrush(Qt.white)
    q.drawEllipse(QPointF(x, y), size * 0.2, size * 0.2)
    q.setPen(QPen(Qt.white, size * 0.08))
    q.setBrush(Qt.NoBrush)
    q.drawEllipse(QPointF(x, y - size * 0.5), size * 0.3, size * 0.1)


def _card_pictures(w: float, h: float, density: float) -> tuple[QImage, QImage]:
    """The card for a window w by h, at density, per pixel: ivory paper with fine fibres, warmer
    toward its edges, in a gilt frame (a band, a hairline inside it, filigree scrolls in the corners)
    with the little wings on its top edge, the gold polished and casting a faint shadow on the paper.
    The ornaments are smaller on a smaller card (fewer names, or names made small on a small game),
    so they keep clear of the names. Also the gold alone, for the sheen to run over."""
    pw, ph, xs, ys = _grid(w, h, density)
    body = QRectF(0.5, CARD_TOP + 0.5, w - 1, h - CARD_TOP - 1)
    k = clamp(body.height() / 66, 0.6, 1.0)
    edge = _rounded(xs, ys, body, 7.0)
    paper = np.clip(-edge * density + 0.5, 0, 1)
    down = np.clip((ys - body.top()) / max(1.0, body.height()), 0, 1)
    color = rgb(LOOK["card"][0]) + (rgb(LOOK["card"][1]) - rgb(LOOK["card"][0])) * down[..., None]
    fibres = noise(pw, ph, 3 * density, 3, 31) - 0.5
    color = color * (1 + 0.035 * fibres)[..., None]
    warm = 1 - smooth(0.0, 12.0, -edge)
    color = color + (rgb("#ecd29a") - color) * (warm * 0.3)[..., None]

    def draw(q: QPainter) -> None:
        q.scale(density, density)
        q.setBrush(Qt.NoBrush)
        q.setPen(QPen(Qt.white, 2.0))
        q.drawRoundedRect(body.adjusted(1.8, 1.8, -1.8, -1.8), 5.4, 5.4)
        q.setPen(QPen(Qt.white, 0.7))
        frame = body.adjusted(4.9, 4.9, -4.9, -4.9)
        q.drawRoundedRect(frame, 3, 3)
        _filigree(q, frame.adjusted(-1, -1, 1, 1), 8.0 * k * k)
        _little_wings(q, w / 2, CARD_TOP - 3.0 * k, 16.0 * k)

    gold = mask(pw, ph, draw)
    raised = blur(gold, 0.7 * density) * 1.4 * density
    metal = _ramp(_shine(raised, (-0.4, -0.8, 0.5), 14))
    shadow = np.roll(blur(gold, 1.1 * density), max(1, round(density)), axis=0) * 0.45 * paper
    color = color * (1 - shadow[..., None]) + rgb("#5a3a0c") * shadow[..., None]
    color = color * (1 - gold[..., None]) + metal * gold[..., None]
    alpha = np.maximum(paper, gold)
    return picture(color, alpha), picture(np.ones((ph, pw, 3), dtype=np.float32), gold)


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """Ivory in a gilt frame with filigree corners and little gilded wings on top; now and then a
    sheen passes over the gold."""
    density = _density(p)
    paper, gold = _kept(("card", round(rect.width(), 1), round(rect.height(), 1), round(density, 2)), lambda: _card_pictures(rect.width(), rect.height(), density))
    p.drawImage(rect, paper)
    k = (t % 4.5) / 1.4
    if k >= 1:
        return
    sheen = QImage(gold.size(), QImage.Format_ARGB32_Premultiplied)
    sheen.fill(Qt.transparent)
    q = QPainter(sheen)
    q.scale(density, density)
    x = -30 + (rect.width() + 60) * ease_in_out(k)
    band = QLinearGradient(QPointF(x - 18, 0), QPointF(x + 18, 24))
    strength = math.sin(math.pi * k) * 0.85
    band.setColorAt(0, col("#fff8e2", 0))
    band.setColorAt(0.5, col("#fff8e2", strength))
    band.setColorAt(1, col("#fff8e2", 0))
    q.fillRect(QRectF(0, 0, rect.width(), rect.height()), band)
    q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    q.resetTransform()
    q.drawImage(0, 0, gold)
    q.end()
    p.drawImage(rect, sheen)


def lead(size: float, index: int) -> QPixmap:
    """A tiny gold feather, leaning up and to the right, every other one a little more."""
    ratio = 3.0
    image = QPixmap(max(1, round(size * ratio)), max(1, round(size * ratio)))
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.transparent)
    length = size * 1.12
    sprite = _sprite(_SPRITES, "loose", length, ratio)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    angle = -52 if index % 2 == 0 else -60
    back = math.radians(angle)
    p.translate(size / 2, size / 2)
    _lay(p, sprite, -math.cos(back) * length / 2, -math.sin(back) * length / 2, angle, length)
    p.end()
    return image
