"""清风徐来 Breeze: a fresh spring wind, green and airy, after 苏轼's 赤壁赋.

A soft celadon light breathes in along the screen's edges, grained like mist; sunlight comes through
leaves in the two top corners, its flecks drifting; slender willow branches hang from the top left
and sway, and tall grass and reeds stand along the bottom in sage and jade. Then the gust: the wind
itself shows, as hand-drawn films draw it, in a few thin glowing ribbons, mint to white, sweeping
left to right through the top and the bottom and curling into spirals at their ends. Willow, maple
and ginkgo leaves ride it, tumbling over (their undersides paler, their veins lit, the sun through
them), dandelion seeds lift from the grass, and the grass and the willow bend with it and spring
back. A glass wind chime with a jade paper strip comes down from the top edge and swings, glinting.
In the top right the leaves swirl into a gentle vortex and gather for a moment into a heart of
leaves, softly lit, its edges fluttering, until a second gust scatters them away to the right. The
title 清风徐来 writes itself stroke by stroke in 楷体 in the top left, deep jade on a glow of mist, a
wisp of wind under it; then the wind settles, the last leaves drift down and it all fades.

Its sound (ui_music) is build/theme_tunes.py's breeze_take: a bamboo flute and a plucked zither in a
pentatonic mode, the chime ringing as it swings, the wind swelling with each gust.

The 嘉宾 marks wear it: frosted celadon glass with a faint leaf-vein watermark and a willow sprig on
its corner, the names in 楷体 each after a small green leaf; thin streamlines of wind circling the
button with a leaf riding them; and for a badge a little glass wind chime with its jade strip,
swaying and glinting now and then.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from blacklist_detect.love_scenes.draw import clamp, col, ease_in, ease_in_out, ease_out, heart_path, heart_points, soft_dot, star, win
from blacklist_detect.love_scenes.light import blur, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# Soft light throughout: drawn at one pixel per point and scaled up on a sharper screen.
MAX_RATIO = 1.0
# Her greens: jade, fresh leaf, mint, sage and celadon, a touch of warm sunlight, and the deep jade of
# the ink and the shade.
JADE = "#3fae7a"
LEAF = "#8fd16a"
MINT = "#c9f2d9"
SAGE = "#a7c4a0"
CELADON = "#e6f5ec"
SUN = "#fff4c8"
INK = "#17573f"
SHADE = "#21543c"
LOOK = {
    "glow": (96, 200, 146),
    "rim": MINT,
    "band": (JADE, MINT),
    "card": ("#f1faf4", "#d5eedf"),
    "edge": "#86c9a3",
    "ink": INK,
    "flowers": (("#f4fff0", LEAF, JADE), ("#f0fff6", MINT, "#5fbf8f")),
    "disc": ("#f0faf3", "#cdeedb"),
    "heart": (LEAF, JADE),
    "deep": "#2f8f62",
    "deep_glow": (80, 190, 130),
}
MARKS_ANIMATED = True
# Room over the card for the willow sprig hanging over its top left corner.
CARD_TOP = 12
CARD_FONT = "KaiTi"
# 楷体, and the faces that stand in for it where it is missing.
KAI = ("KaiTi", "楷体", "STKaiti", "SimSun", "serif")
TITLE = "清风徐来"
# The gust (it rises, holds and lets go) and the second gust that scatters the heart.
GUST = (0.6, 1.1, 1.9, 2.5)
SECOND = (3.25, 3.55, 3.8, 4.4)
# The heart of leaves: gathered by HEART[0], scattered from HEART[1].
HEART = (3.0, 3.4)
# The title writes itself from here, a character every TITLE_STEP seconds, each over TITLE_EACH.
TITLE_AT = 3.0
TITLE_STEP = 0.24
TITLE_EACH = 0.36
# Pictures of leaves and the like are made at this many pixels to the point, for turning smoothly.
FINE = 2.0
# The light comes from the top left.
LIGHT = (-0.55, -0.7)


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(53)
    haze = _haze(width, height, gap, u)
    rays = [_rays(width, u, seed) for seed in (61, 67)]
    branches = _branches(width, u, rnd)
    willow = [_leaf_sprites("willow", tint, 24 * u, FINE)[0] for tint in (LEAF, "#62b86e", "#a6d98a")]
    grass = _grass(width, height, gap, u, rnd)
    bend_grass = (_spring(1.5, 0.35), _spring(1.9, 0.3))
    bend_willow = _spring(0.9, 0.22)
    ribbons = _ribbons(width, height, gap, u)
    flows = {name: _flow(ribbon["flow"]) for name, ribbon in ribbons.items()}
    # The heart's leaves ride the top ribbon only as far as where the heart gathers.
    flows["heart"] = _flow(ribbons["top1"]["path"])
    kinds = [(kind, tint) for kind in ("willow", "maple", "ginkgo") for tint in (LEAF, JADE, "#b5e08a")]
    sprites = {key: _leaf_sprites(key[0], key[1], (46 if key[0] == "willow" else 34) * u, FINE) for key in kinds}
    heart_at = QPointF(width - 232 * u, 140 * u)
    heart_size = 178 * u
    riders, gathered = _leaves(width, u, flows, kinds, heart_at, heart_size, random.Random(59))
    heart_glow = _heart_glow(heart_at, heart_size, u)
    seed_image = _seed(26 * u, FINE)
    seeds = _seeds(width, height, gap, u, random.Random(71))
    chime_at = QPointF(min(width - 420 * u, width * 0.715), 0.0)
    chime = _chime(u, FINE)
    title = _title(QPointF(max(250 * u, width * 0.25), 104 * u), 50 * u, u)
    wisp = _title_wisp(title["rect"], u, gap)
    flecks = _flecks(width, title["rect"], u, rnd)

    def paint(p: QPainter, t: float) -> None:
        life = ease_out(win(t, 0.0, 0.8)) * (1 - ease_in(win(t, 4.2, DURATION)))
        if life <= 0:
            return
        gust = _gust(t)
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        # The mist breathes; a gust brightens it a little.
        p.setOpacity(life * (0.86 + 0.1 * math.sin(t * 2.4) + 0.12 * gust))
        for rect, image in haze:
            p.drawImage(rect, image)
        _sunlight(p, t, life, rays, flecks, u)
        p.setOpacity(life)
        _willow(p, t, branches, willow, bend_willow, u)
        for ribbon in ribbons.values():
            _ribbon_paint(p, t, ribbon, life)
        _grass_paint(p, t, grass, bend_grass, height, life, back=True)
        _seeds_paint(p, t, seeds, seed_image, heart_at, life, u)
        _grass_paint(p, t, grass, bend_grass, height, life, back=False)
        _chime_paint(p, t, chime, chime_at, life, u)
        _heart_light(p, t, heart_glow, life)
        _leaves_paint(p, t, riders, gathered, sprites, flows, heart_at, gap, life, u)
        _title_paint(p, t, title, wisp, life, u)
        p.restore()

    return paint


# Timing ---------------------------------------------------------------------------------------


def _gust(t: float) -> float:
    """How hard the wind blows: 0 still, 1 the gust at its height; the second gust a little softer."""
    first = ease_in_out(win(t, GUST[0], GUST[1])) * (1 - ease_in_out(win(t, GUST[2], GUST[3])))
    second = ease_in_out(win(t, SECOND[0], SECOND[1])) * (1 - ease_in_out(win(t, SECOND[2], SECOND[3]))) * 0.8
    return max(first, second)


def _spring(freq: float, damp: float) -> np.ndarray:
    """How far something springy is bent by the wind, at 240 steps a second over the scene: pushed
    toward the gust's strength, overshooting a little as it lets go and swinging back."""
    step = 1 / 240
    k, c = (2 * math.pi * freq) ** 2, 2 * damp * 2 * math.pi * freq
    x = v = 0.0
    out = []
    for i in range(int(DURATION / step) + 2):
        t = i * step
        v += (k * (_gust(t) - x) - c * v) * step
        x += v * step
        out.append(x)
    return np.array(out)


def _at(track: np.ndarray, t: float) -> float:
    return float(np.interp(t * 240, np.arange(len(track)), track))


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


def _dither(shape: tuple[int, ...], seed: int) -> np.ndarray:
    """A little noise to add before light is made into bytes, so its slow gradients do not band."""
    rnd = np.random.default_rng(seed)
    return (rnd.random(shape, dtype=np.float32) - rnd.random(shape, dtype=np.float32)) / 255.0


def _rgba(image: QImage) -> np.ndarray:
    """A picture's pixels as (h, w, 4) premultiplied RGBA floats 0..1."""
    image = image.convertToFormat(QImage.Format_RGBA8888_Premultiplied)
    rows = np.frombuffer(image.constBits(), dtype=np.uint8, count=image.bytesPerLine() * image.height())
    return rows.reshape(image.height(), image.bytesPerLine())[:, : image.width() * 4].reshape(image.height(), image.width(), 4).astype(np.float32) / 255.0


def _lit(light: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Light (h, w, 3, may run over 1) as straight color and alpha: as opaque as its brightest channel,
    so dim light stays see-through and a hot core goes white (light.glow, before it is a picture)."""
    light = np.maximum(light, 0)
    over = np.clip(light.max(axis=-1, keepdims=True) - 1, 0, None)
    light = light + over * 0.6
    alpha = np.clip(light.max(axis=-1), 0, 1)
    return np.clip(light, 0, 1) / np.maximum(alpha, 1e-4)[..., None], alpha


def _sprite(image: QImage, scale: float) -> QImage:
    image.setDevicePixelRatio(scale)
    return image


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
    return np.clip(-(gx * LIGHT[0] + gy * LIGHT[1]) * soft * 2.2, -1, 1)


# The mist and the sunlight --------------------------------------------------------------------


def _haze(width: float, height: float, gap: QRectF, u: float) -> list[tuple[QRectF, QImage]]:
    """The celadon mist along the edges, per pixel and grained, pooling in the top corners where the
    sun comes in: in four strips round the middle, which it leaves clear."""
    w, h = max(8, round(width)), max(8, round(height))
    top, bottom, side = min(h // 2, round(345 * u)), min(h // 3, round(160 * u)), min(w // 3, round(160 * u))
    billows = noise(w, h, 150 * u, 3, 5)
    grains = noise(w, h, 1.6, 2, 6)
    out = []
    for x0, y0, x1, y1 in ((0, 0, w, top), (0, h - bottom, w, h), (0, top, side, h - bottom), (w - side, top, w, h - bottom)):
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32) + 0.5
        edge = np.minimum(np.minimum(xs, w - xs), np.minimum(ys, h - ys)) / u
        rim = smooth(150, 0, edge) ** 1.9
        pool = smooth(340, 0, np.minimum(np.hypot(xs, ys), np.hypot(w - xs, ys)) / u) ** 1.6
        billow = billows[y0:y1, x0:x1]
        grain = grains[y0:y1, x0:x1]
        density = (rim * 0.3 + pool * 0.13) * (0.45 + 0.85 * billow) * (0.88 + 0.24 * grain)
        alpha = density * _away(gap, xs, ys, u) + _dither(xs.shape, x0 * 7 + y0)
        tint = smooth(0.3, 0.8, billow)[..., None]
        color = rgb("#9ddcb6") * (1 - tint) + rgb(MINT) * tint
        warm = (pool * smooth(0.4, 0.9, billow) * 0.5)[..., None]
        color = color * (1 - warm) + rgb(SUN) * warm
        out.append((QRectF(x0, y0, x1 - x0, y1 - y0), picture(color, alpha)))
    return out


def _rays(width: float, u: float, seed: int) -> tuple[QRectF, QImage]:
    """Sunlight slanting in through the leaves from the top left: soft shafts fanning down to the
    right, warm near the corner and mint further out, streaked as light through leaves is, fading
    before they reach the names."""
    rw, rh = min(round(width * 0.62), round(980 * u)), round(300 * u)
    ys, xs = np.mgrid[0:rh, 0:rw].astype(np.float32) + 0.5
    sx, sy = -160 * u, -120 * u
    angle = np.arctan2(ys - sy, xs - sx)
    reach = np.hypot(xs - sx, ys - sy) / u
    rnd = np.random.default_rng(seed)
    shafts = np.zeros_like(angle)
    for k, weight in ((23, 0.5), (41, 0.3), (67, 0.2)):
        shafts += weight * np.sin(angle * k + rnd.uniform(0, math.tau))
    shafts = smooth(0.15, 0.85, shafts * 0.5 + 0.5) ** 1.5
    streaks = noise(rw, rh, 60 * u, 2, seed + 1)
    fall = smooth(1100, 200, reach) * smooth(rh / u, rh / u * 0.45, ys / u) * smooth(0.05, 0.35, angle)
    light = shafts * fall * (0.55 + 0.6 * streaks)
    warm = smooth(700, 250, reach)[..., None]
    color = rgb("#d6f5c4") * (1 - warm) + rgb(SUN) * warm
    alpha = np.clip(light * 0.2, 0, 1) + _dither(light.shape, seed)
    return QRectF(0, 0, rw, rh), picture(color, alpha)


def _bokeh(radius: float, tint: str, seed: int) -> QImage:
    """A fleck of sunlight out of focus: a soft disc, a little brighter at its rim, grained."""
    side = max(4, math.ceil(radius * 2.4))
    ys, xs = np.mgrid[0:side, 0:side].astype(np.float32) + 0.5
    r = np.hypot(xs - side / 2, ys - side / 2) / radius
    disc = smooth(1.0, 0.85, r)
    rim = np.exp(-(((r - 0.9) / 0.08) ** 2)) * 0.35
    grain = noise(side, side, max(2.0, radius * 0.3), 2, seed)
    light = (disc * (0.55 + 0.2 * grain) + rim)[..., None] * rgb(tint)
    color, alpha = _lit(light)
    return picture(color, alpha * 0.9 + _dither(alpha.shape, seed) * (alpha > 0))


def _flecks(width: float, title: QRectF, u: float, rnd: random.Random) -> list[tuple]:
    """Where the flecks of sunlight float in the two top corners: (x, y, picture, when it twinkles)."""
    out = []
    while len(out) < 22:
        right = len(out) % 2 == 1
        x = width - rnd.uniform(40, 560) * u if right else rnd.uniform(20, 620) * u
        y = rnd.uniform(14, 225) * u
        if title.adjusted(-20 * u, -10 * u, 20 * u, 10 * u).contains(QPointF(x, y)):
            continue
        r = rnd.uniform(5, 15) * u
        out.append((x, y, _bokeh(r, rnd.choice((SUN, SUN, "#e3f8c8", MINT)), len(out)), rnd.uniform(0, math.tau)))
    return out


def _sunlight(p: QPainter, t: float, life: float, rays: list, flecks: list, u: float) -> None:
    """The shafts shimmer as the leaves above them move, their two patterns coming and going; flecks
    of sunlight drift with the wind and twinkle."""
    gust = _gust(t)
    mix = 0.5 + 0.5 * math.sin(t * 1.3 + gust * 2.5)
    for index, (rect, image) in enumerate(rays):
        p.setOpacity(life * (mix if index else 1 - mix) * (0.75 + 0.25 * ease_out(win(t, 0.2, 1.0))))
        p.drawImage(rect.translated(14 * u * gust, 0), image)
    for x, y, image, phase in flecks:
        twinkle = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 1.9 + phase))
        p.setOpacity(life * twinkle * 0.8)
        w = image.width()
        p.drawImage(QPointF(x + 22 * u * t + 50 * u * gust - w / 2, y + 7 * u * math.sin(t * 1.1 + phase) - w / 2), image)
    p.setOpacity(life)


# The willow -----------------------------------------------------------------------------------


def _branches(width: float, u: float, rnd: random.Random) -> list[tuple]:
    """The willow's branches hanging from the top left: (where they hang from, their length, how far
    out they arch at first, when they sway, their leaves (where along, which side, which green, how
    big))."""
    out = []
    for x, length, arch in ((-18, 330, 0.75), (14, 410, 0.6), (48, 300, 0.85), (84, 370, 0.65), (122, 260, 0.9), (162, 200, 0.95), (204, 150, 1.0), (246, 105, 1.05)):
        leaves = []
        count = int(length / 14)
        for j in range(2, count):
            for side in (-1, 1):
                if rnd.random() < 0.82:
                    leaves.append((j / count + rnd.uniform(-0.01, 0.01), side, rnd.randrange(3), rnd.uniform(0.75, 1.05)))
        out.append((x * u, length * u, arch, rnd.uniform(0, math.tau), leaves))
    return out


def _branch_line(x: float, length: float, arch: float, phase: float, t: float, bent: float, u: float, n: int = 18) -> np.ndarray:
    """A branch's points, top to tip: arching out from where it hangs, then hanging, swaying, and
    bent toward the right by the wind, the tip most and a moment later."""
    pts = [(x, -6 * u)]
    angle_sum = 0.0
    for j in range(n):
        s = (j + 0.5) / n
        rest = arch * math.exp(-s / 0.22)
        sway = (s**1.3) * (0.09 * math.sin(t * 1.6 + phase - s * 1.4) + 0.75 * bent * (1 + 0.15 * math.sin(t * 7 + phase + s * 3)))
        angle_sum = rest + sway
        step = length / n
        px, py = pts[-1]
        pts.append((px + math.sin(angle_sum) * step, py + math.cos(angle_sum) * step))
    return np.array(pts)


def _willow(p: QPainter, t: float, branches: list, sprites: list[QImage], bend: np.ndarray, u: float) -> None:
    grow = ease_out(win(t, 0.0, 0.9))
    if grow <= 0:
        return
    bent = _at(bend, t)
    base = p.opacity()
    for x, length, arch, phase, leaves in branches:
        line = _branch_line(x, length * (0.55 + 0.45 * grow), arch, phase, t, bent, u)
        p.setOpacity(base * grow)
        p.setPen(QPen(col("#5f8a52", 0.85), 1.3 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(QPolygonF([QPointF(a, b) for a, b in line.tolist()]))
        n = len(line) - 1
        for s, side, tint, size in leaves:
            k = s * n
            i = min(n - 1, int(k))
            f = k - i
            ax, ay = line[i] * (1 - f) + line[i + 1] * f
            dx, dy = line[i + 1] - line[i]
            # The leaf hangs down the branch, out to its side, and flutters.
            heading = math.degrees(math.atan2(dy, dx)) - side * (30 - 10 * bent) + 9 * math.sin(t * 6.5 + s * 20 + side)
            sprite = sprites[tint]
            p.save()
            p.translate(ax, ay)
            p.rotate(heading)
            p.scale(size, size)
            p.drawImage(QRectF(0, -sprite.height() / sprite.devicePixelRatio() / 2, sprite.width() / sprite.devicePixelRatio(), sprite.height() / sprite.devicePixelRatio()), sprite)
            p.restore()
    p.setOpacity(base)


# Leaves ----------------------------------------------------------------------------------------


def _leaf_shape(kind: str, size: float) -> tuple[QPainterPath, QPainterPath]:
    """A leaf size long lying along +x, its stalk's end at x 0, and its veins."""
    shape = QPainterPath()
    veins = QPainterPath()
    if kind == "willow":
        top, bottom = [], []
        for i in range(41):
            s = i / 40
            half = size * 0.11 * math.sin(math.pi * s) ** 0.75 * (1.05 - 0.35 * s)
            top.append(QPointF(s * size, -half))
            bottom.append(QPointF(s * size, half * 0.92))
        shape.moveTo(top[0])
        for point in top[1:]:
            shape.lineTo(point)
        for point in reversed(bottom):
            shape.lineTo(point)
        shape.closeSubpath()
        veins.moveTo(0, 0)
        veins.lineTo(size * 0.97, 0)
        return shape, veins
    if kind == "maple":
        # Five pointed lobes round a middle, a little serrated, on a stalk.
        r = size * 0.42
        cx = size * 0.18 + r
        lobes = ((0.0, 1.0), (1.05, 0.86), (-1.05, 0.86), (2.05, 0.55), (-2.05, 0.55))
        points = []
        for i in range(240):
            a = -math.pi + i / 240 * math.tau
            reach = 0.36 + sum(length * 0.7 * math.exp(-(((a - at + math.pi) % math.tau - math.pi) / 0.2) ** 2) for at, length in lobes)
            reach *= 1 + 0.05 * math.sin(a * 22)
            points.append(QPointF(cx + math.cos(a) * r * reach, math.sin(a) * r * reach))
        shape.moveTo(points[0])
        for point in points[1:]:
            shape.lineTo(point)
        shape.closeSubpath()
        stalk = QPainterPath()
        stalk.addRoundedRect(QRectF(0, -size * 0.018, cx - r * 0.2, size * 0.036), size * 0.018, size * 0.018)
        shape = shape.united(stalk)
        veins.moveTo(0, 0)
        veins.lineTo(cx, 0)
        for at, length in lobes:
            veins.moveTo(cx, 0)
            veins.lineTo(cx + math.cos(at) * r * (0.36 + length * 0.62), math.sin(at) * r * (0.36 + length * 0.62))
        return shape, veins
    # Ginkgo: a fan with a notch in the middle of its rim, on a long stalk.
    base = QPointF(size * 0.34, 0)
    reach = size * 0.62
    points = [base]
    for i in range(61):
        a = -1.05 + 2.1 * i / 60
        r = reach * (1 - 0.2 * math.exp(-(a / 0.09) ** 2)) * (1 + 0.025 * math.sin(a * 30))
        points.append(QPointF(base.x() + math.cos(a) * r, math.sin(a) * r))
    shape.moveTo(points[0])
    for point in points[1:]:
        shape.lineTo(point)
    shape.closeSubpath()
    stalk = QPainterPath()
    stalk.addRoundedRect(QRectF(0, -size * 0.017, base.x() + size * 0.05, size * 0.034), size * 0.017, size * 0.017)
    shape = shape.united(stalk)
    veins.moveTo(0, 0)
    veins.lineTo(base)
    for i in range(13):
        a = -0.95 + 1.9 * i / 12
        veins.moveTo(base)
        veins.lineTo(base.x() + math.cos(a) * reach * 0.94, math.sin(a) * reach * 0.94)
    return shape, veins


def _leaf_sprites(kind: str, tint: str, size: float, scale: float) -> tuple[QImage, QImage, QImage]:
    """A leaf lit per pixel at scale pixels to the point, centred in its picture: its face (lit from
    the top left, darker at its stalk, its veins pale where the sun shows through), its underside
    (paler, its veins standing out) and the sunlight through it, to lay over either."""
    shape, veins = _leaf_shape(kind, size)
    box = shape.boundingRect()
    margin = size * 0.12
    w, h = max(4, math.ceil((box.width() + margin * 2) * scale)), max(4, math.ceil((box.height() + margin * 2) * scale))

    def place(q: QPainter) -> None:
        q.translate(w / 2, h / 2)
        q.scale(scale, scale)
        q.translate(-box.center())

    def body(q: QPainter) -> None:
        place(q)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(shape)

    def lines(q: QPainter) -> None:
        place(q)
        q.setPen(QPen(Qt.white, max(0.5, size * 0.022), Qt.SolidLine, Qt.RoundCap))
        q.drawPath(veins)

    m = mask(w, h, body)
    v = mask(w, h, lines) * m
    lit = _shaded(m, size * 0.14 * scale)
    _ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    along = np.clip((xs / scale - margin) / max(1.0, box.width()), 0, 1)
    grain = noise(w, h, max(2.0, size * 0.08 * scale), 2, len(kind) * 7 + len(tint))
    base = rgb(tint)
    color = base * (0.62 + 0.38 * smooth(0.0, 0.7, along))[..., None]
    color = color * (1 + 0.28 * lit)[..., None] * (0.94 + 0.12 * grain)[..., None]
    sunny = (blur(m, size * 0.22 * scale) * 0.22)[..., None]
    color = color * (1 - sunny) + rgb(SUN) * sunny
    face = color * (1 - 0.45 * v[..., None]) + rgb("#e8f8b8") * (0.45 * v[..., None])
    edge = np.clip(m - blur(m, 0.9 * scale), 0, 1)[..., None] * 0.5
    face = face * (1 - edge) + rgb(SHADE) * edge
    under = color * 0.55 + rgb("#e3f2cf") * 0.45
    under = under * (1 + 0.15 * lit)[..., None]
    under = under * (1 - 0.55 * v[..., None]) + rgb("#f6fbe6") * (0.55 * v[..., None])
    alpha = m * 0.97
    through = blur(m, size * 0.2 * scale) * m
    light = (through * 0.55 + v * 0.35)[..., None] * rgb("#f0ffc0") + blur(m, size * 0.25 * scale)[..., None] * rgb(LEAF) * 0.25
    glow_color, glow_alpha = _lit(light)
    return (
        _sprite(picture(face, alpha), scale),
        _sprite(picture(under, alpha), scale),
        _sprite(picture(glow_color, glow_alpha * 0.9), scale),
    )


def _leaf(p: QPainter, sprites: tuple[QImage, QImage, QImage], x: float, y: float, angle: float, flip: float, alpha: float, size: float = 1.0) -> None:
    """A leaf tumbling: turned by angle, its face or underside shown as it flips over (flip in radians),
    the sun glowing through it as it turns toward the light."""
    if alpha <= 0.01:
        return
    across = math.cos(flip)
    face, under, through = sprites
    p.save()
    p.setOpacity(p.opacity() * alpha)
    _put(p, face if across >= 0 else under, x, y, angle, size, size * max(0.3, abs(across)))
    sun = 0.25 + 0.75 * max(0.0, math.sin(flip + 0.7))
    p.setOpacity(p.opacity() * sun * 0.8)
    _put(p, through, x, y, angle, size, size * max(0.3, abs(across)))
    p.restore()


def _leaves(width: float, u: float, flows: dict, kinds: list, heart_at: QPointF, heart_size: float, rnd: random.Random) -> tuple[list, list]:
    """The leaves the wind carries: riders, blown along a ribbon's flow and away, and the ones
    gathered into the heart, blown in along the top ribbon (leaving at, speed, offset, kind, spin,
    and for those in the heart their place on it)."""
    riders = []
    for name, count, start in (("top2", 7, 0.7), ("low", 5, 0.85), ("high", 5, 1.0), ("top3", 6, 3.3), ("low2", 3, 3.4)):
        for i in range(count):
            riders.append((
                name, start + i * rnd.uniform(0.07, 0.13), rnd.uniform(620, 860) * u, rnd.uniform(-34, 22) * u, rnd.randrange(len(kinds)),
                rnd.uniform(1.6, 3.4) * rnd.choice((-1, 1)), rnd.uniform(0, math.tau), rnd.uniform(0.75, 1.05),
            ))  # fmt: skip
    # Round the heart's edge, and a smaller ring inside it to fill it out.
    places = []
    for count, share, size in ((28, 1.0, 1.0), (13, 0.6, 0.8)):
        ring = heart_points(heart_at.x(), heart_at.y() + (1 - share) * heart_size * 0.06, heart_size * share, count, 0.5 / count)
        for i, place in enumerate(ring):
            after = ring[(i + 1) % count]
            places.append((place, math.degrees(math.atan2(after.y() - place.y(), after.x() - place.x())), size))
    gathered = []
    for i, (place, tangent, size) in enumerate(places):
        gathered.append((
            0.62 + 0.03 * i + rnd.uniform(0, 0.05), rnd.uniform(560, 700) * u, rnd.uniform(-40, 18) * u, rnd.randrange(len(kinds)),
            rnd.uniform(1.2, 2.6) * rnd.choice((-1, 1)), rnd.uniform(0, math.tau), size * rnd.uniform(0.8, 0.95),
            place, tangent + rnd.uniform(-25, 25), rnd.uniform(0, math.tau), i,
        ))  # fmt: skip
    return riders, gathered


def _leaves_paint(p: QPainter, t: float, riders: list, gathered: list, sprites: dict, flows: dict, heart_at: QPointF, gap: QRectF, life: float, u: float) -> None:
    keys = list(sprites)
    for name, start, speed, offset, kind, spin, phase, size in riders:
        age = t - start
        if age <= 0:
            continue
        points, along, normals = flows[name]
        d = age * speed * (0.85 + 0.3 * _gust(t))
        if d >= along[-1]:
            continue
        x, y, nx, ny = _on(points, along, normals, d)
        x += nx * (offset + 9 * u * math.sin(age * 5 + phase))
        y += ny * (offset + 9 * u * math.sin(age * 5 + phase)) + 6 * u * math.sin(age * 3.1 + phase)
        fade = min(ease_out(win(age, 0, 0.2)), _away_at(gap, x, y, u))
        _leaf(p, sprites[keys[kind]], x, y, math.degrees(phase) + age * spin * 40, phase + age * spin, fade * life, size)
    points, along, normals = flows["heart"]
    for start, speed, offset, kind, spin, phase, size, place, tangent, swirl, index in gathered:
        age = t - start
        if age <= 0:
            continue
        x, y, angle, flip, alpha = _gathered(t, age, start, speed, offset, spin, phase, place, tangent, swirl, index, points, along, normals, heart_at, u)
        _leaf(p, sprites[keys[kind]], x, y, angle, flip, alpha * life, size)


def _gathered(
    t: float, age: float, start: float, speed: float, offset: float, spin: float, phase: float, place: QPointF, tangent: float,
    swirl: float, index: int, points: np.ndarray, along: np.ndarray, normals: np.ndarray, heart_at: QPointF, u: float,
) -> tuple[float, float, float, float, float]:
    """Where a leaf of the heart is: blown in along the top ribbon, caught in the vortex as it nears
    the heart's place and circling in, settled on the heart and fluttering, then scattered to the
    right by the second gust, a few drifting down instead."""
    d = min(age * speed, along[-1])
    x, y, nx, ny = _on(points, along, normals, d)
    x += nx * offset
    y += ny * offset + 8 * u * math.sin(age * 3 + phase)
    angle = math.degrees(phase) + age * spin * 40
    flip = phase + age * spin
    # Caught: the vortex round the heart's place, circling in.
    caught = smooth(along[-1] - 380 * u, along[-1] - 40 * u, np.float32(d)).item()
    if caught > 0:
        turn = swirl + (t - 1.6) * 2.8
        r = (95 + 55 * math.sin(swirl * 3)) * u * (1 - 0.35 * ease_in_out(win(t, 2.2, 2.9)))
        vx, vy = heart_at.x() + math.cos(turn) * r * 1.15, heart_at.y() + math.sin(turn) * r * 0.75
        x, y = x + (vx - x) * caught, y + (vy - y) * caught
        angle = angle * (1 - caught) + (math.degrees(turn) + 90) * caught
    # Settled on the heart, its edges fluttering.
    settle = ease_in_out(win(t, 2.55 + index * 0.006, HEART[0]))
    if settle > 0:
        flutter = math.sin(t * 11 + index * 1.7)
        hx, hy = place.x() + 1.5 * u * flutter, place.y() + 1.5 * u * math.cos(t * 9 + index)
        x, y = x + (hx - x) * settle, y + (hy - y) * settle
        angle = angle * (1 - settle) + (tangent + 12 * flutter) * settle
        flip = flip * (1 - settle) + (0.35 * flutter) * settle
    # Scattered: the second gust's front reaches it from the left.
    away = t - (HEART[1] + 0.12 * (place.x() - heart_at.x() + 90 * u) / (180 * u))
    alpha = ease_out(win(age, 0, 0.25))
    if away > 0:
        if index % 6 == 0:
            # A few drift down instead, swaying, into the right edge.
            x += 90 * u * away + 22 * u * math.sin(away * 3.2 + phase)
            y += 70 * u * away
            angle += 25 * math.sin(away * 3.2 + phase)
            flip += away * 2.5
        else:
            x += 300 * u * away + 520 * u * away * away
            y += (-60 + 40 * math.sin(index * 2.1)) * u * away - 40 * u * away * away * math.cos(index)
            angle += away * spin * 70
            flip += away * spin * 1.6
    return x, y, angle, flip, alpha


def _on(points: np.ndarray, along: np.ndarray, normals: np.ndarray, d: float) -> tuple[float, float, float, float]:
    """The point d along a line, and its sideways unit there."""
    i = int(np.clip(np.searchsorted(along, d) - 1, 0, len(along) - 2))
    seg = along[i + 1] - along[i]
    f = (d - along[i]) / seg if seg > 0 else 0.0
    x, y = points[i] * (1 - f) + points[i + 1] * f
    return float(x), float(y), float(normals[i][0]), float(normals[i][1])


# The heart's light -----------------------------------------------------------------------------


def _heart_glow(at: QPointF, size: float, u: float) -> tuple[QRectF, QImage]:
    """A soft light where the leaves gather into the heart: warm at its middle, mint at its edge."""
    margin = 60 * u
    rect = QRectF(at.x() - size / 2 - margin, at.y() - size / 2 - margin, size + 2 * margin, size + 2 * margin)
    w, h = max(4, round(rect.width())), max(4, round(rect.height()))
    shape = heart_path(w / 2, h / 2 + size * 0.02, size * 0.92)

    def draw(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(shape)

    m = mask(w, h, draw)
    inner = blur(m, 16 * u)
    outer = blur(m, 34 * u)
    light = inner[..., None] * rgb(SUN) * 0.42 + outer[..., None] * rgb(MINT) * 0.4
    color, alpha = _lit(light)
    return rect, picture(color, alpha + _dither(alpha.shape, 3))


def _heart_light(p: QPainter, t: float, glow: tuple[QRectF, QImage], life: float) -> None:
    a = ease_in_out(win(t, 2.6, HEART[0])) * (1 - ease_in(win(t, HEART[1], HEART[1] + 0.5)))
    if a <= 0:
        return
    p.save()
    p.setOpacity(life * a * (0.85 + 0.15 * math.sin(t * 7)))
    p.drawImage(*glow)
    p.restore()


# The grass and the reeds -----------------------------------------------------------------------


def _grass(width: float, height: float, gap: QRectF, u: float, rnd: random.Random) -> list[tuple]:
    """Tall grass along the bottom either side of the button, and reeds with feathery heads in the
    corners, per pixel: (its picture's place, picture, back or front, how it sways), back and front
    on each side."""
    out = []
    for side, (x0, x1) in enumerate(((-12 * u, gap.left() - 26 * u), (gap.right() + 26 * u, width + 12 * u))):
        if x1 - x0 < 30 * u:
            continue
        for back in (True, False):
            tall = (200 if back else 120) * u
            rect = QRectF(x0 - 30 * u, height - tall - 40 * u, x1 - x0 + 60 * u, tall + 40 * u)
            out.append((rect, _grass_layer(rect, height, gap, u, rnd, side, back, x0, x1), back, rnd.uniform(0, math.tau)))
    return out


def _blade(x: float, base: float, tall: float, lean: float, wide: float) -> QPainterPath:
    """A blade of grass, tapering from its foot to a point, curving over by lean at its tip."""
    left, right = [], []
    for i in range(17):
        s = i / 16
        cx = x + lean * s * s
        cy = base - tall * s
        half = wide * (1 - s) ** 0.9
        left.append(QPointF(cx - half, cy))
        right.append(QPointF(cx + half, cy))
    path = QPainterPath(left[0])
    for point in left[1:]:
        path.lineTo(point)
    for point in reversed(right):
        path.lineTo(point)
    path.closeSubpath()
    return path


def _grass_layer(rect: QRectF, height: float, gap: QRectF, u: float, rnd: random.Random, side: int, back: bool, x0: float, x1: float) -> QImage:
    w, h = max(4, round(rect.width())), max(4, round(rect.height()))
    blades = []
    reeds = []
    x = x0
    while x < x1:
        # Tallest toward the screen's corner, low by the button.
        outer = (x1 - x) / (x1 - x0) if side == 0 else (x - x0) / (x1 - x0)
        tall = rnd.uniform(0.55, 1.0) * (36 + 70 * outer**0.8) * u * (1.25 if back else 0.85)
        blades.append(_blade(x - rect.left(), h + 2, tall, rnd.uniform(-10, 24) * u, rnd.uniform(1.6, 3.0) * u))
        x += rnd.uniform(3.0, 7.0) * u * (1.4 if back else 1.0)
    if back:
        corner = x0 + 20 * u if side == 0 else x1 - 20 * u
        for k in range(4):
            rx = corner + (1 if side == 0 else -1) * (k * 34 + rnd.uniform(-8, 8)) * u
            reeds.append((rx - rect.left(), rnd.uniform(150, 195) * u * (1 - 0.12 * k), rnd.uniform(6, 22) * u))

    def draw_blades(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        for blade in blades:
            q.drawPath(blade)
        for rx, tall, lean in reeds:
            q.drawPath(_blade(rx, h + 2, tall, lean, 1.2 * u))

    def draw_heads(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        for rx, tall, lean in reeds:
            tip = QPointF(rx + lean, h + 2 - tall)
            q.save()
            q.translate(tip)
            q.rotate(math.degrees(math.atan2(lean, tall)) + 8)
            q.drawEllipse(QRectF(-6 * u, -6 * u, 12 * u, 44 * u))
            q.restore()

    m = mask(w, h, draw_blades)
    heads = mask(w, h, draw_heads)
    heads = np.clip(blur(heads, 2.2 * u) * (0.55 + 0.7 * noise(w, h, 2.4 * u, 2, 81 + side)), 0, 1)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    up = np.clip((h - ys) / (rect.height() - 40 * u), 0, 1)[..., None]
    low, high = (rgb(SHADE), rgb(SAGE)) if back else (rgb("#2d7a52"), rgb(LEAF))
    color = low * (1 - smooth(0.0, 0.9, up)) + high * smooth(0.0, 0.9, up)
    mid = (np.exp(-((up - 0.45) / 0.25) ** 2) * (0.25 if back else 0.4))
    color = color * (1 - mid) + rgb(JADE) * mid
    streaks = np.repeat(noise(w, max(2, h // 12 + 2), 2.2 * u, 2, 90 + side + back), 12, axis=0)[:h]
    color = color * (0.85 + 0.3 * streaks)[..., None]
    # Lit from behind: a pale rim along each blade's edges, brighter toward the tips.
    rim = np.clip((m - blur(m, 0.9 * u)) * 2.4, 0, 1)[..., None] * up
    color = color * (1 - rim * 0.7) + rgb(MINT) * (rim * 0.7)
    if back:
        color = color * 0.8 + rgb("#16382a") * 0.2
    plume = heads[..., None]
    color = color * (1 - plume) + (rgb("#efe9cf") * 0.7 + rgb(SUN) * 0.3) * plume
    alpha = np.maximum(m * (0.9 if back else 0.97), heads * 0.85)
    keep = _away(gap, xs + rect.left(), ys + rect.top(), u)
    return picture(color, alpha * keep)


def _grass_paint(p: QPainter, t: float, grass: list, bends: tuple[np.ndarray, np.ndarray], height: float, life: float, back: bool) -> None:
    """The grass grows up from the bottom at the start and sways, bent over by each gust from its foot
    and springing back."""
    rise = ease_out(win(t, 0.0, 0.9))
    if rise <= 0:
        return
    for rect, image, is_back, phase in grass:
        if is_back != back:
            continue
        bent = _at(bends[0 if back else 1], t)
        lean = 0.05 * math.sin(t * 2.1 + phase) + 0.42 * bent
        p.save()
        p.setOpacity(life)
        p.translate(0, height)
        p.shear(-lean, 0)
        p.scale(1, rise * (1 - 0.18 * lean * lean))
        p.translate(0, -height)
        p.drawImage(rect, image)
        p.restore()


# Dandelion seeds ------------------------------------------------------------------------------


def _seed(size: float, scale: float) -> QImage:
    """A dandelion seed: a fine spray of white filaments on a hair-thin stalk down to the seed,
    glowing softly as the light catches it."""
    w = h = max(4, math.ceil(size * 1.5 * scale))

    def draw(q: QPainter) -> None:
        q.translate(w / 2, h / 2)
        q.scale(scale, scale)
        hub = QPointF(0, -size * 0.1)
        q.setPen(QPen(Qt.white, max(0.3, size * 0.014), Qt.SolidLine, Qt.RoundCap))
        q.setBrush(Qt.NoBrush)
        for i in range(29):
            a = math.radians(-82 + 164 * i / 28) - math.pi / 2
            reach = size * (0.36 + 0.06 * math.sin(i * 2.7))
            end = QPointF(hub.x() + math.cos(a) * reach, hub.y() + math.sin(a) * reach * 0.8)
            bow = QPointF(hub.x() + math.cos(a) * reach * 0.5, hub.y() + math.sin(a) * reach * 0.5 - size * 0.04)
            line = QPainterPath(hub)
            line.quadTo(bow, end)
            q.drawPath(line)
        q.setPen(QPen(Qt.white, max(0.35, size * 0.02), Qt.SolidLine, Qt.RoundCap))
        q.drawLine(hub, QPointF(0, size * 0.4))
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawEllipse(QPointF(0, size * 0.45), size * 0.03, size * 0.07)

    core = mask(w, h, draw)
    light = core[..., None] * rgb("#fffdf0") * 0.95 + blur(core, size * 0.05 * scale)[..., None] * rgb(MINT) * 0.9
    light += blur(core, size * 0.16 * scale)[..., None] * rgb(SUN) * 0.5
    color, alpha = _lit(light)
    return _sprite(picture(color, alpha), scale)


def _seeds(width: float, height: float, gap: QRectF, u: float, rnd: random.Random) -> list[tuple]:
    """Dandelion seeds lifted from the grass in the bottom corners as the gust comes: (from, when,
    rising speed, drift, sway, size, caught into the vortex)."""
    out = []
    for i in range(14):
        right = i % 2 == 1
        x = width - rnd.uniform(30, 150) * u if right else rnd.uniform(20, 120) * u
        out.append((QPointF(x, height - rnd.uniform(60, 120) * u), 0.7 + i * 0.08 + rnd.uniform(0, 0.08), rnd.uniform(60, 100) * u,
                    rnd.uniform(8, 26) * u, rnd.uniform(0, math.tau), rnd.uniform(0.7, 1.1), right and i % 4 == 1))  # fmt: skip
    return out


def _seeds_paint(p: QPainter, t: float, seeds: list, image: QImage, heart_at: QPointF, life: float, u: float) -> None:
    for at, when, rise, drift, sway, size, caught in seeds:
        age = t - when
        if age <= 0:
            continue
        x = at.x() + drift * age + 14 * u * math.sin(age * 2.2 + sway) + 12 * u * _gust(t) * age
        y = at.y() - rise * age - 30 * u * age * age
        alpha = ease_out(win(age, 0, 0.3)) * (1 - ease_in(win(age, 2.0, 3.0)))
        if caught:
            # Up the right edge and into the vortex, circling with the leaves, then scattered with them.
            k = ease_in_out(win(t, 2.0, 2.8))
            turn = sway + t * 2.8
            vx, vy = heart_at.x() + math.cos(turn) * 70 * u, heart_at.y() + math.sin(turn) * 50 * u
            x, y = x + (vx - x) * k, y + (vy - y) * k
            away = max(0.0, t - HEART[1])
            x += 380 * u * away + 400 * u * away * away
            alpha = ease_out(win(age, 0, 0.3)) * (1 - ease_in(win(t, 3.6, 4.2)))
        if alpha > 0.01:
            p.save()
            p.setOpacity(p.opacity() * alpha * life)
            _put(p, image, x, y, 14 * math.sin(age * 2.2 + sway), size, size)
            p.restore()


# The wind ribbons -----------------------------------------------------------------------------


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
    keep = np.concatenate([[True], seg > 1e-9])
    points = points[keep]
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(points, axis=0).T))])
    at = np.linspace(0, s[-1], max(3, int(s[-1] / step) + 1))
    return np.column_stack([np.interp(at, s, points[:, 0]), np.interp(at, s, points[:, 1])])


def _curl(points: np.ndarray, radius: float, turns: float, step: float) -> np.ndarray:
    """The line carried on into a spiral curling up and over at its end, tightening to its middle."""
    end, before = points[-1], points[-4]
    d = (end - before) / max(1e-9, float(np.hypot(*(end - before))))
    up = np.array([d[1], -d[0]])
    centre = end + up * radius
    start = math.atan2(end[1] - centre[1], end[0] - centre[0])
    total = turns * math.tau
    count = max(8, int(total * radius / step))
    phi = np.linspace(0, total, count)[1:]
    r = radius * (1 - phi / (total * 1.12))
    spiral = np.column_stack([centre[0] + r * np.cos(start - phi), centre[1] + r * np.sin(start - phi)])
    return np.vstack([points, spiral])


def _along(points: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(points, axis=0).T))])


def _normals(points: np.ndarray) -> np.ndarray:
    d = np.gradient(points, axis=0)
    d = d / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)[:, None]
    return np.column_stack([-d[:, 1], d[:, 0]])


def _ribbons(width: float, height: float, gap: QRectF, u: float) -> dict[str, dict]:
    """The wind made visible: each ribbon's line (its flow, for the leaves riding it, carries on past
    its curl), when it sweeps through, and its picture in pieces along it."""
    w, h, step = width, height, 3 * u
    left, right = gap.left(), gap.right()
    plans = {
        # The gust across the top: under where the title comes, over the game's title, curling where
        # the heart will gather.
        "top1": ([(-0.06 * w, 236 * u), (0.1 * w, 212 * u), (0.22 * w, 178 * u), (0.33 * w, 118 * u), (0.44 * w, 52 * u), (0.56 * w, 38 * u),
                  (0.68 * w, 64 * u), (w - 340 * u, 118 * u), (w - 260 * u, 150 * u)], 48 * u, 1.35, (0.55, 1.75), 4.0 * u, (w + 120 * u, 120 * u)),
        "top2": ([(-0.06 * w, 70 * u), (0.08 * w, 112 * u), (0.18 * w, 128 * u), (0.3 * w, 70 * u), (0.42 * w, 26 * u), (0.53 * w, 20 * u),
                  (0.6 * w, 32 * u)], 22 * u, 1.25, (0.8, 1.9), 2.6 * u, (w + 120 * u, 30 * u)),
        "low": ([(-0.05 * w, h - 34 * u), (0.3 * left, h - 64 * u), (0.62 * left, h - 98 * u), (left - 170 * u, h - 104 * u)], 30 * u, 1.25,
                (0.7, 1.75), 3.2 * u, (left + 200 * u, h - 120 * u)),
        "high": ([(right + 30 * u, h - 52 * u), (right + 0.35 * (w - right), h - 86 * u), (w - 210 * u, h - 104 * u), (w - 130 * u, h - 134 * u)],
                 30 * u, 1.25, (0.95, 2.05), 3.2 * u, (w + 120 * u, h - 230 * u)),
        # The second gust, through the heart, and low on the left.
        "top3": ([(0.5 * w, 18 * u), (0.66 * w, 48 * u), (w - 380 * u, 104 * u), (w - 240 * u, 150 * u), (w - 110 * u, 128 * u)], 26 * u, 1.2,
                 (3.2, 4.05), 3.4 * u, (w + 120 * u, 110 * u)),
        "low2": ([(-0.05 * w, h - 70 * u), (0.35 * left, h - 112 * u), (left - 230 * u, h - 122 * u)], 22 * u, 1.15, (3.3, 4.15), 2.6 * u,
                 (left + 120 * u, h - 160 * u)),
    }  # fmt: skip
    out = {}
    for name, (ctrl, radius, turns, when, thick, leave) in plans.items():
        line = _spline(ctrl, step)
        curled = _curl(line, radius, turns, step)
        out[name] = {"when": when, "pieces": _ribbon_pieces(curled, thick, gap, u, 22 * u), "length": float(_along(curled)[-1]), "head": 110 * u,
                     "flow": _spline([*ctrl, leave], step), "path": line}  # fmt: skip
    return out


def _title_wisp(rect: QRectF, u: float, gap: QRectF) -> dict:
    """The wisp of wind under the title, curling up at its right end."""
    y = rect.bottom() + 8 * u
    line = _spline([(rect.left() - 30 * u, y + 8 * u), (rect.center().x(), y - 2 * u), (rect.right() + 10 * u, y + 2 * u)], 2 * u)
    curled = _curl(line, 12 * u, 1.1, 2 * u)
    return {"when": (3.55, 4.25), "pieces": _ribbon_pieces(curled, 2.0 * u, gap, u, 12 * u), "length": float(_along(curled)[-1]), "head": 40 * u}


def _flow(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return points, _along(points), _normals(points)


def _ribbon_pieces(points: np.ndarray, thick: float, gap: QRectF, u: float, piece: float) -> list[tuple[float, QRectF, QImage]]:
    """A ribbon of wind lit per pixel, cut along its length into pieces that together are the whole of
    it: (how far along its middle is, where, picture). Thin and tapering, with a fainter thread
    beside it for a while; a white core and a mint glow round it."""
    along = _along(points)
    total = along[-1]
    s = along / total
    margin = 56 * u
    x0, y0 = points.min(axis=0) - margin
    x1, y1 = points.max(axis=0) + margin
    w, h = max(4, math.ceil(x1 - x0)), max(4, math.ceil(y1 - y0))
    local = points - [x0, y0]
    widths = thick * (0.2 + 0.8 * smooth(0.0, 0.1, s)) * (1 - 0.75 * smooth(0.7, 1.0, s)) + 0.5
    normals = _normals(points)
    beside = (smooth(0.12, 0.25, s) * smooth(0.62, 0.45, s))
    twin = local + normals * (thick * 2.6 + 6 * u * np.sin(s * 9))[:, None]

    def core_lines(q: QPainter) -> None:
        q.setBrush(Qt.NoBrush)
        for line, width_of in ((local, widths), (twin, widths * 0.45 * beside)):
            for i in range(len(line) - 1):
                if width_of[i] < 0.15:
                    continue
                q.setPen(QPen(Qt.white, float(width_of[i]), Qt.SolidLine, Qt.RoundCap))
                q.drawLine(QPointF(*line[i]), QPointF(*line[i + 1]))

    count = max(2, min(250, int(total / piece)))

    def pieces_of(q: QPainter) -> None:
        q.setRenderHint(QPainter.Antialiasing, False)
        cuts = np.linspace(0, len(local) - 1, count + 1).astype(int)
        for k in range(count):
            q.setPen(QPen(QColor(k + 1, k + 1, k + 1), margin * 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            part = local[cuts[k] : cuts[k + 1] + 1]
            q.drawPolyline(QPolygonF([QPointF(a, b) for a, b in part.tolist()]))

    core = mask(w, h, core_lines)
    which = np.rint(mask(w, h, pieces_of) * 255).astype(np.int32)
    halo = blur(core, 2 * u) * 0.9 + blur(core, 6 * u) * 0.7 + blur(core, 15 * u) * 0.5 + blur(core, 32 * u) * 0.3
    light = halo[..., None] * rgb(MINT) + (core**1.3)[..., None] * rgb("#ffffff") * 0.8
    color, alpha = _lit(light)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    alpha = alpha * 0.85 * _away(gap, xs + x0, ys + y0, u)
    out = []
    for k in range(count):
        mine = which == k + 1
        if not mine.any():
            continue
        rows, cols = np.nonzero(mine)
        r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        a = np.where(mine[r0:r1, c0:c1], alpha[r0:r1, c0:c1], 0)
        if a.max() < 1 / 255:
            continue
        a = a + _dither(a.shape, k) * (a > 0)
        out.append(((k + 0.5) / count * total, QRectF(x0 + c0, y0 + r0, c1 - c0, r1 - r0), picture(color[r0:r1, c0:c1], a)))
    return out


def _ribbon_paint(p: QPainter, t: float, ribbon: dict, life: float) -> None:
    """A ribbon sweeping through: its bright head runs along the line and into the curl, its thin tail
    following and catching up, so it goes into the curl and is gone."""
    start, end = ribbon["when"]
    k = win(t, start, end)
    if k <= 0 or k >= 1:
        return
    total = ribbon["length"]
    head = total * ease_out(min(1.0, k * 1.3)) + 1
    tail = total * ease_in_out(clamp((k - 0.22) / 0.78))
    fade = total * 0.28
    base = p.opacity()
    for at, rect, image in ribbon["pieces"]:
        if at > head or at < tail:
            continue
        o = smooth(tail, tail + fade, np.float32(at)).item() * (1 - smooth(head - ribbon["head"], head, np.float32(at)).item())
        if o > 0.01:
            p.setOpacity(base * o * life)
            p.drawImage(rect, image)
    p.setOpacity(base)


# The wind chime -------------------------------------------------------------------------------


def _bell_shape(bw: float, bh: float) -> QPainterPath:
    """A wind chime's glass bell, its top at 0, open at the bottom."""
    path = QPainterPath(QPointF(-bw / 2, bh))
    path.cubicTo(QPointF(-bw / 2, bh * 0.38), QPointF(-bw * 0.32, 0), QPointF(0, 0))
    path.cubicTo(QPointF(bw * 0.32, 0), QPointF(bw / 2, bh * 0.38), QPointF(bw / 2, bh))
    path.quadTo(QPointF(0, bh * 1.12), QPointF(-bw / 2, bh))
    path.closeSubpath()
    return path


def _chime(u: float, scale: float) -> dict:
    """The wind chime per pixel: its clear glass bell, thick at its rim, painted inside with wisps of
    wind and a leaf, its highlights; and its jade paper strip on a thread, with a glass bead for a
    clapper, 风 brushed on it in celadon."""
    bw, bh = 60 * u, 52 * u
    bell = _bell(bw, bh, scale)
    sw, sh, thread = 30 * u, 92 * u, 26 * u
    strip = _strip(sw, sh, thread, u, scale)
    return {"bell": bell, "strip": strip, "bw": bw, "bh": bh, "string": 62 * u, "sh": sh + thread}


def _bell(bw: float, bh: float, scale: float) -> QImage:
    margin = bw * 0.12
    w, h = max(4, math.ceil((bw + margin * 2) * scale)), max(4, math.ceil((bh * 1.12 + margin * 2) * scale))
    shape = _bell_shape(bw, bh)

    def place(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(margin + bw / 2, margin)

    def body(q: QPainter) -> None:
        place(q)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(shape)

    def lip(q: QPainter) -> None:
        place(q)
        q.setPen(QPen(Qt.white, bw * 0.05))
        q.setBrush(Qt.NoBrush)
        q.drawArc(QRectF(-bw / 2, bh * 0.88, bw, bh * 0.24), 0, -180 * 16)
        q.setPen(QPen(Qt.white, bw * 0.03))
        q.drawArc(QRectF(-bw / 2, bh * 0.88, bw, bh * 0.24), 0, 180 * 16)

    def painted(q: QPainter) -> None:
        place(q)
        q.setPen(QPen(Qt.white, bw * 0.04, Qt.SolidLine, Qt.RoundCap))
        q.setBrush(Qt.NoBrush)
        for k, y in enumerate((0.48, 0.66)):
            wisp = QPainterPath(QPointF(-bw * 0.36, bh * y))
            wisp.cubicTo(QPointF(-bw * 0.1, bh * (y - 0.12)), QPointF(bw * 0.05, bh * (y + 0.1)), QPointF(bw * (0.22 + 0.08 * k), bh * (y - 0.05)))
            q.drawPath(wisp)
        leaf = QPainterPath()
        leaf.moveTo(bw * 0.12, bh * 0.36)
        leaf.quadTo(bw * 0.28, bh * 0.2, bw * 0.34, bh * 0.36)
        leaf.quadTo(bw * 0.22, bh * 0.46, bw * 0.12, bh * 0.36)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(leaf)

    m = mask(w, h, body)
    rim = mask(w, h, lip)
    paint_mask = mask(w, h, painted) * m
    inner = blur(m, bw * 0.08 * scale)
    thick = np.clip((1 - inner) * 2.4, 0, 1) * m
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xs / scale - margin - bw / 2) / (bw / 2)
    ny = (ys / scale - margin) / bh
    streak = np.exp(-(((nx + 0.48) / 0.11) ** 2) - ((ny - 0.52) / 0.3) ** 2) + 0.5 * np.exp(-(((nx - 0.55) / 0.07) ** 2) - ((ny - 0.6) / 0.22) ** 2)
    glass = rgb(CELADON) * 0.55 + rgb(MINT) * 0.45
    color = glass * (1 - thick[..., None] * 0.4) + rgb("#9fdcbc") * (thick[..., None] * 0.4)
    color = color + streak[..., None] * 0.5
    tint = paint_mask[..., None]
    color = color * (1 - tint) + (rgb(JADE) * (1 - smooth(0.3, 0.6, ny))[..., None] + rgb(LEAF) * smooth(0.3, 0.6, ny)[..., None]) * tint
    alpha = m * (0.2 + 0.55 * thick) + streak * m * 0.6 + paint_mask * 0.75
    alpha = np.maximum(alpha, rim * 0.9)
    color = color * (1 - rim[..., None]) + rgb("#ffffff") * rim[..., None]
    return _sprite(picture(color, np.clip(alpha, 0, 1)), scale)


def _strip(sw: float, sh: float, thread: float, u: float, scale: float) -> QImage:
    """The thread hanging from the bell with its glass bead, and the jade paper strip on it: fibrous,
    a little darker toward its foot, paler at its edges, 风 brushed on it. Its top is the picture's
    top middle."""
    margin = 3 * u
    w, h = max(4, math.ceil((sw + margin * 2) * scale)), max(4, math.ceil((sh + thread + margin) * scale))
    paper = QRectF(margin, thread, sw, sh)

    def strip(q: QPainter) -> None:
        q.scale(scale, scale)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawRect(paper)

    def threads(q: QPainter) -> None:
        q.scale(scale, scale)
        q.setPen(QPen(Qt.white, 0.9 * u))
        q.drawLine(QPointF(margin + sw / 2, 0), QPointF(margin + sw / 2, thread))
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawEllipse(QPointF(margin + sw / 2, thread * 0.35), 4.2 * u, 4.2 * u)

    def word(q: QPainter) -> None:
        q.scale(scale, scale)
        font = QFont()
        font.setFamilies(list(KAI))
        font.setPixelSize(max(6, round(sw * 0.8)))
        path = QPainterPath()
        path.addText(QPointF(0, 0), font, "风")
        box = path.boundingRect()
        q.translate(paper.center().x() - box.center().x(), paper.top() + sh * 0.36 - box.center().y())
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(path)

    m = mask(w, h, strip)
    line = mask(w, h, threads)
    ink = mask(w, h, word) * m
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    v = np.clip((ys / scale - thread) / sh, 0, 1)[..., None]
    fibres = np.repeat(noise(w, max(2, h // 6 + 2), 1.2 * scale, 2, 17), 6, axis=0)[:h]
    color = rgb("#4cbd86") * (1 - v) + rgb("#2a8a5e") * v
    color = color * (0.9 + 0.2 * fibres)[..., None]
    edge = np.clip((m - blur(m, 1.2 * scale)) * 2, 0, 1)[..., None]
    color = color * (1 - edge * 0.5) + rgb(MINT) * (edge * 0.5)
    color = color * (1 - ink[..., None] * 0.92) + rgb(CELADON) * (ink[..., None] * 0.92)
    bead = line[..., None]
    color = color * (1 - bead) + rgb("#eafff2") * bead
    alpha = np.maximum(m * 0.95, line * 0.85)
    return _sprite(picture(color, alpha), scale)


def _chime_paint(p: QPainter, t: float, chime: dict, at: QPointF, life: float, u: float) -> None:
    """The chime comes down from the top edge on its string, swings with the gust (its strip lagging
    and fluttering), glints as the sun catches it, and goes back up."""
    come = ease_out(win(t, 1.2, 1.6)) * (1 - ease_in(win(t, 2.95, 3.35)))
    if come <= 0:
        return
    drop = (1 - come) * (chime["string"] + chime["bh"] + chime["sh"] + 20 * u)
    age = t - 1.2
    swing = math.radians(14 * math.sin(age * 4.4) * math.exp(-age * 0.4) * (0.4 + _gust(t)) + 4 * _gust(t))
    flap = math.radians(22 * math.sin(age * 4.4 - 1.0) * (0.3 + _gust(t)) + 10 * _gust(t))
    flutter = 0.82 + 0.18 * math.cos(age * 13)
    p.save()
    p.setOpacity(p.opacity() * life * come)
    p.translate(at.x(), at.y() - drop)
    p.rotate(-math.degrees(swing))
    string = chime["string"]
    p.setPen(QPen(col(MINT, 0.8), 1.0 * u))
    p.drawLine(QPointF(0, -10 * u), QPointF(0, string))
    bell, strip = chime["bell"], chime["strip"]
    bh = chime["bh"]
    sw, sh = strip.width() / strip.devicePixelRatio(), strip.height() / strip.devicePixelRatio()
    p.save()
    p.translate(0, string + bh * 0.95)
    p.rotate(-math.degrees(flap - swing))
    p.scale(flutter, 1)
    p.drawImage(QRectF(-sw / 2, -bh * 0.55, sw, sh), strip)
    p.restore()
    bw, bhh = bell.width() / bell.devicePixelRatio(), bell.height() / bell.devicePixelRatio()
    p.drawImage(QRectF(-bw / 2, string - (bhh - bh * 1.12) / 2, bw, bhh), bell)
    # The sun catches the glass at the ends of its swing.
    glint = max(0.0, math.cos(age * 4.4)) ** 12 * (0.3 + _gust(t))
    if glint > 0.03:
        gx, gy = -chime["bw"] * 0.24, string + bh * 0.42
        soft_dot(p, gx, gy, 16 * u, "#ffffff", 0.5 * glint)
        star(p, gx, gy, 13 * u * glint, "#ffffff", min(1.0, glint * 1.4), 0.1)
    p.restore()


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


def _title(centre: QPointF, size: float, u: float) -> dict:
    """清风徐来 in 楷体, each character cut into its strokes, in writing order (a radical on the left
    first, then top to bottom), each stroke a picture: deep jade ink, a little uneven as a brush lays
    it, on a glow of mist. With when each stroke is written and which way."""
    font = _kai(size)
    spacing = size * 1.12
    margin = round(14 * u)
    strokes = []
    left = centre.x() - spacing * (len(TITLE) - 1) / 2
    for index, glyph in enumerate(TITLE):
        path = QPainterPath()
        path.addText(QPointF(0, 0), font, glyph)
        box = path.boundingRect()
        w, h = max(4, math.ceil(size * 1.1 + margin * 2)), max(4, math.ceil(size * 1.1 + margin * 2))

        def draw(q: QPainter, path: QPainterPath = path, box: QRectF = box, w: int = w, h: int = h) -> None:
            q.translate(w / 2 - box.center().x(), h / 2 - box.center().y())
            q.setPen(Qt.NoPen)
            q.setBrush(Qt.white)
            q.drawPath(path)

        m = mask(w, h, draw)
        origin = QPointF(left + index * spacing - w / 2, centre.y() - h / 2)
        parts = _parts(m)
        # Each part gets the ink round its edge that the threshold left out.
        owner = np.zeros(m.shape, dtype=np.int32)
        reach = np.zeros(m.shape, dtype=np.float32)
        for k, part in enumerate(parts):
            near = blur(part, 1.2)
            better = near > reach
            owner[better] = k
            reach[better] = near[better]
        keys = []
        for k, part in enumerate(parts):
            cols = np.nonzero(part.any(axis=0))[0]
            rows = np.nonzero(part.any(axis=1))[0]
            # A radical on the left (氵, 彳) is written first, then the rest top to bottom.
            radical = cols.mean() < w * 0.42 and cols.max() < w * 0.5
            keys.append((0 if radical else 1, rows.min(), cols.mean(), k))
        order = [k for *_key, k in sorted(keys)]
        weights = [float(parts[k].sum()) ** 0.5 for k in order]
        start = TITLE_AT + index * TITLE_STEP
        when = start
        for k, weight in zip(order, weights, strict=True):
            share = TITLE_EACH * weight / sum(weights)
            ink = m * (owner == k)
            rows, cols_k = np.nonzero(parts[k])
            r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols_k.min(), cols_k.max() + 1
            across = (c1 - c0) > (r1 - r0) * 1.3
            strokes.append((when, share, _stroke(ink, u, index * 31 + k), origin, QRectF(c0, r0, c1 - c0, r1 - r0), across))
            when += share
    lefts = [s[3].x() + s[4].left() for s in strokes]
    rights = [s[3].x() + s[4].right() for s in strokes]
    rect = QRectF(min(lefts), centre.y() - size / 2, max(rights) - min(lefts), size)
    return {"strokes": strokes, "rect": rect, "mist": _mist(rect, u)}


def _stroke(ink: np.ndarray, u: float, seed: int) -> QImage:
    """One stroke: deep jade ink, darker where it pools at its edges, with a fine brush grain, and a
    pale glow round it so it reads on the dark game."""
    h, w = ink.shape
    grain = noise(w, h, 1.5, 2, seed)
    pool = np.clip((ink - blur(ink, 1.6 * u)) * 1.8, 0, 1)
    color = rgb(INK) * (0.92 + 0.16 * grain)[..., None]
    color = color * (1 - pool[..., None] * 0.35) + rgb("#0c3526") * (pool[..., None] * 0.35)
    halo = np.clip(blur(ink, 3.5 * u) * 1.5, 0, 1) * 0.8
    alpha = np.maximum(ink, halo)
    shine = (halo * (1 - ink))[..., None] / np.maximum(alpha, 1e-4)[..., None]
    color = color * (1 - shine) + (rgb(CELADON) * 0.7 + rgb("#ffffff") * 0.3) * shine
    return picture(color, alpha + _dither(alpha.shape, seed) * (alpha > 0))


def _mist(rect: QRectF, u: float) -> tuple[QRectF, QImage]:
    """The soft light behind the title: a long glow of mist, grained, its ends fraying."""
    margin = 60 * u
    out = rect.adjusted(-margin, -margin * 0.8, margin, margin * 0.8)
    w, h = max(4, round(out.width())), max(4, round(out.height()))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (xs / w - 0.5) * 2, (ys / h - 0.5) * 2
    billow = noise(w, h, 30 * u, 3, 29)
    density = smooth(1.0, 0.25, np.sqrt(nx**2 * 0.9 + ny**2 * 1.4)) * (0.6 + 0.6 * billow)
    tint = smooth(0.3, 0.8, billow)[..., None]
    color = rgb(CELADON) * (1 - tint) + rgb(SUN) * tint
    alpha = np.clip(density * 0.5, 0, 1) + _dither(density.shape, 31)
    return out, picture(color, alpha)


def _title_paint(p: QPainter, t: float, title: dict, wisp: dict, life: float, u: float) -> None:
    """The mist comes up, the strokes write themselves one after another, a light at the brush's tip,
    and the wisp of wind sweeps under them."""
    shown = ease_out(win(t, TITLE_AT - 0.25, TITLE_AT + 0.3))
    if shown <= 0:
        return
    rect, image = title["mist"]
    p.save()
    p.setOpacity(life * shown * (0.9 + 0.1 * math.sin(t * 2.0)))
    p.drawImage(rect, image)
    p.setOpacity(life)
    for when, share, image, origin, box, across in title["strokes"]:
        k = ease_in_out(win(t, when, when + share))
        if k <= 0:
            continue
        w, h = image.width(), image.height()
        target = QRectF(origin.x(), origin.y(), w, h)
        if k >= 1:
            p.drawImage(target, image)
            continue
        if across:
            front = box.left() + box.width() * k
            clip = QRectF(origin.x(), origin.y(), front + 4 * u, h)
            tip = QPointF(origin.x() + front, origin.y() + box.center().y())
        else:
            front = box.top() + box.height() * k
            clip = QRectF(origin.x(), origin.y(), w, front + 4 * u)
            tip = QPointF(origin.x() + box.center().x(), origin.y() + front)
        p.save()
        p.setClipRect(clip)
        p.drawImage(target, image)
        p.restore()
        soft_dot(p, tip.x(), tip.y(), 12 * u, SUN, 0.55 * life)
    p.restore()
    _ribbon_paint(p, t, wisp, life)


# The 嘉宾 marks -------------------------------------------------------------------------------

_MADE: dict[tuple, object] = {}


def _kept(key: tuple, build):  # noqa: ANN001, ANN202
    if key not in _MADE:
        _MADE[key] = build()
    return _MADE[key]


def _sharpness(p: QPainter) -> float:
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return round(max(1.0, ratio * math.hypot(p.transform().m11(), p.transform().m12())), 2)


def _glass(rect: QRectF, scale: float) -> QImage:
    """The card per pixel: frosted celadon glass, lighter at its top, frost grain in it, a faint
    leaf's veins showing through on its right, a pale edge and a jade line round it."""
    w, h = max(4, math.ceil(rect.width() * scale)), max(4, math.ceil(rect.height() * scale))
    body = rect.adjusted(0.5, CARD_TOP + 0.5, -0.5, -0.5)

    def shape(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(-rect.left(), -rect.top())
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawRoundedRect(body, 9, 9)

    def veins(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(-rect.left(), -rect.top())
        q.translate(body.right() - body.height() * 0.55, body.center().y() + body.height() * 0.1)
        q.rotate(-32)
        length = body.height() * 1.5
        q.setPen(QPen(Qt.white, 1.1, Qt.SolidLine, Qt.RoundCap))
        q.setBrush(Qt.NoBrush)
        q.drawLine(QPointF(-length / 2, 0), QPointF(length / 2, 0))
        q.setPen(QPen(Qt.white, 0.7, Qt.SolidLine, Qt.RoundCap))
        for i in range(1, 7):
            x = -length / 2 + length * i / 7.5
            reach = length * 0.32 * math.sin(math.pi * i / 7.5)
            for side in (-1, 1):
                q.drawLine(QPointF(x, 0), QPointF(x + reach * 0.6, side * reach))
        outline = QPainterPath(QPointF(-length / 2, 0))
        outline.quadTo(QPointF(0, -length * 0.42), QPointF(length / 2, 0))
        outline.quadTo(QPointF(0, length * 0.42), QPointF(-length / 2, 0))
        q.drawPath(outline)

    inside = mask(w, h, shape)
    vein = mask(w, h, veins) * inside
    ys, _xs = np.mgrid[0:h, 0:w].astype(np.float32)
    v = np.clip((ys / scale - CARD_TOP) / max(1.0, body.height()), 0, 1)[..., None]
    color = rgb(LOOK["card"][0]) * (1 - v) + rgb(LOOK["card"][1]) * v
    frost = noise(w, h, max(2.0, 1.4 * scale), 2, 13)
    color = color * (0.97 + 0.05 * frost)[..., None]
    color = color * (1 - vein[..., None] * 0.13) + rgb(JADE) * (vein[..., None] * 0.13)
    k = max(1, round(1.4 * scale))
    edge = np.clip(inside - np.roll(np.roll(inside, k, 0), k, 1) * np.roll(np.roll(inside, -k, 0), -k, 1), 0, 1)
    shine = np.clip(inside - np.roll(inside, k, 0), 0, 1)
    color = color * (1 - edge[..., None]) + rgb(LOOK["edge"]) * edge[..., None]
    color = color * (1 - shine[..., None] * 0.6) + rgb("#ffffff") * (shine[..., None] * 0.6)
    return _sprite(picture(color, inside * 0.93), scale)


def _sprig(scale: float) -> tuple[QImage, QPointF]:
    """A willow sprig for the card's corner: a thin twig with a few slender leaves, its top at the
    point given (in points, from the picture's top left)."""
    size = 11.0
    w, h = 30.0, 30.0
    leaf = _leaf_sprites("willow", LEAF, size, scale)[0]
    deep = _leaf_sprites("willow", "#5fb36c", size, scale)[0]
    image = QImage(math.ceil(w * scale), math.ceil(h * scale), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.scale(scale, scale)
    top = QPointF(6, 3)
    twig = QPainterPath(top)
    twig.cubicTo(QPointF(10, 8), QPointF(12, 16), QPointF(11, 26))
    q.setPen(QPen(col("#5f8a52", 0.95), 0.9, Qt.SolidLine, Qt.RoundCap))
    q.drawPath(twig)
    for k, (s, side) in enumerate(((0.25, 1), (0.42, -1), (0.6, 1), (0.78, -1), (0.95, 1))):
        at = twig.pointAtPercent(s)
        angle = twig.angleAtPercent(s)
        sprite = (leaf, deep)[k % 2]
        lw, lh = sprite.width() / scale, sprite.height() / scale
        q.save()
        q.translate(at)
        q.rotate(-angle - side * 30)
        q.drawImage(QRectF(0, -lh / 2, lw, lh), sprite)
        q.restore()
    q.end()
    return _sprite(image, scale), top


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """Frosted celadon glass with a willow sprig hanging over its top left corner, swaying."""
    scale = _sharpness(p)
    glass = _kept(("card", round(rect.width(), 1), round(rect.height(), 1), scale), lambda: _glass(rect, scale))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(rect, glass)
    sprig, top = _kept(("sprig", max(2.0, scale)), lambda: _sprig(max(2.0, scale)))
    w, h = sprig.width() / sprig.devicePixelRatio(), sprig.height() / sprig.devicePixelRatio()
    p.translate(rect.left() + 3, rect.top() + 1)
    p.rotate(-8 + 7 * math.sin(t * 1.6) + 3 * math.sin(t * 4.1))
    p.drawImage(QRectF(-top.x(), -top.y(), w, h), sprig)


def lead(size: float, index: int) -> QPixmap:
    """A small green leaf before each name, fresh leaf and jade in turn."""
    scale = 3.0
    sprite = _kept(("lead", round(size, 2), index % 2), lambda: _leaf_sprites("willow", (LEAF, JADE)[index % 2], size * 0.95, scale)[0])
    image = QImage(math.ceil(size * scale), math.ceil(size * scale), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.scale(scale, scale)
    w, h = sprite.width() / scale, sprite.height() / scale
    q.translate(size / 2, size / 2)
    q.rotate(-35)
    q.drawImage(QRectF(-w / 2, -h / 2, w, h), sprite)
    q.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def _ring_glow(cover: QRectF, scale: float) -> tuple[QRectF, QImage]:
    """A soft mint light round the button's edge, per pixel."""
    out = cover.adjusted(-9, -9, 9, 9)
    w, h = max(4, math.ceil(out.width() * scale)), max(4, math.ceil(out.height() * scale))
    radius = min(cover.height() * 0.3, 18.0)

    def line(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(-out.left(), -out.top())
        q.setPen(QPen(Qt.white, 2.0))
        q.setBrush(Qt.NoBrush)
        q.drawRoundedRect(cover.adjusted(2, 2, -2, -2), radius, radius)

    core = mask(w, h, line)
    light = (blur(core, 2.0 * scale) * 0.9 + blur(core, 5 * scale) * 0.6)[..., None] * rgb(JADE) + core[..., None] * rgb(MINT) * 0.5
    color, alpha = _lit(light)
    return out, _sprite(picture(color, alpha), scale)


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """Thin streamlines of wind circling the button, mint with white cores, and a leaf riding them."""
    scale = _sharpness(p)
    rect, glow = _kept(("ring-glow", round(cover.width(), 1), round(cover.height(), 1), scale), lambda: _ring_glow(cover, scale))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setOpacity(0.75 + 0.15 * math.sin(t * 2.0))
    p.drawImage(rect, glow)
    p.setOpacity(1.0)
    radius = min(cover.height() * 0.3, 18.0)
    for inset, speed, dash, alpha, width in ((1.5, 26.0, (9.0, 5.0, 2.0, 6.0), 0.95, 1.6), (4.5, -18.0, (5.0, 9.0), 0.65, 1.0), (-1.5, 40.0, (3.0, 14.0), 0.55, 0.9)):
        path = QPainterPath()
        box = cover.adjusted(inset, inset, -inset, -inset)
        path.addRoundedRect(box, max(1.0, radius - inset), max(1.0, radius - inset))
        for pen_width, color, k in ((width * 3.2, JADE, 0.35), (width, "#ffffff", 1.0)):
            pen = QPen(col(color, alpha * k), pen_width, Qt.CustomDashLine, Qt.RoundCap)
            pen.setDashPattern([d / pen_width * width for d in dash])
            pen.setDashOffset(t * speed / pen_width)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
    # A leaf riding round on the outer streamline.
    path = QPainterPath()
    path.addRoundedRect(cover.adjusted(-1.5, -1.5, 1.5, 1.5), radius + 1.5, radius + 1.5)
    share = (t * 0.11) % 1.0
    at = path.pointAtPercent(share)
    angle = -path.angleAtPercent(share)
    sprites = _kept(("ring-leaf", scale), lambda: _leaf_sprites("willow", LEAF, 15.0, max(2.0, scale)))
    _leaf(p, sprites, at.x(), at.y(), angle + 15 * math.sin(t * 5), t * 4.0, 1.0)


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A little glass wind chime with its jade strip, swaying, glinting now and then."""
    scale = _sharpness(p)
    side = box.width()
    u = side / 100
    chime = _kept(("badge", round(side, 1), scale), lambda: _chime(u * 1.0, max(2.0, scale)))
    soft_dot(p, box.center().x(), box.center().y(), side * 0.48, MINT, 0.32)
    soft_dot(p, box.center().x(), box.center().y(), side * 0.3, CELADON, 0.3)
    bell, strip = chime["bell"], chime["strip"]
    bw, bh = chime["bw"], chime["bh"]
    top = QPointF(box.center().x(), box.top() + side * 0.08)
    swing = 9 * math.sin(t * 2.2)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.translate(top)
    p.rotate(swing)
    string = side * 0.14
    p.setPen(QPen(col(MINT, 0.9), max(0.8, side * 0.012)))
    p.drawLine(QPointF(0, 0), QPointF(0, string))
    sw, sh = strip.width() / strip.devicePixelRatio(), strip.height() / strip.devicePixelRatio()
    p.save()
    p.translate(0, string + bh * 0.95)
    p.rotate(12 * math.sin(t * 2.2 - 1.0))
    p.drawImage(QRectF(-sw / 2, -bh * 0.55, sw, sh), strip)
    p.restore()
    iw, ih = bell.width() / bell.devicePixelRatio(), bell.height() / bell.devicePixelRatio()
    p.drawImage(QRectF(-iw / 2, string - (ih - bh * 1.12) / 2, iw, ih), bell)
    glint = clamp(1 - abs(t % 3.2 - 0.4) / 0.35)
    if glint > 0:
        gx, gy = -bw * 0.24, string + bh * 0.42
        soft_dot(p, gx, gy, side * 0.16, "#ffffff", 0.5 * glint)
        star(p, gx, gy, side * 0.13 * glint, "#ffffff", glint, 0.1)
