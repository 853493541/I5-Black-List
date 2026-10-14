"""遇袭 Ambush: you are the one attacked, as in 模仿者狂欢's 迷离 and its kill.

For a moment nothing. Then the 指挥家's fog rolls in from the edges, blue-grey and drifting two ways
at once, and the view closes to an eye-shaped slit while white music notes swirl through the haze.
Then the strike, the game's own kill mark made as big as the screen: three tapered slashes rip up
across the middle, white-hot at their cores and purple at their edges, and a second set crosses them
a beat later. A lilac flash, a jolt, a puff of pink smoke; the slashes fray away and the fog clears.

The 嘉宾 marks wear it: a misty glass card scored by three claw marks, a lilac rim round the button
with claw marks at two corners that now and then strike again, and a claw-mark X on a dark disc for a
badge. No heart.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QImage, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient

from blacklist_detect.love_scenes.draw import clamp, col, ease_in, ease_in_out, ease_out, soft_dot, win
from blacklist_detect.love_scenes.light import bloom, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 4.8
FOG = "#8fa3b8"
FOG_DEEP = "#55687d"
LILAC = "#c9b6ff"
PURPLE = "#8a5cff"
CORE = "#fbf8ff"
PINK = "#ff9ad5"
LOOK = {
    "glow": (176, 140, 255),
    "rim": LILAC,
    "band": (PURPLE, "#e4dcff"),
    "card": ("#252c3d", "#141925"),
    "edge": "#9d86e8",
    "ink": "#efeaff",
    "flowers": (("#ffffff", "#e4dcff", "#a98bff"), ("#f4f7ff", "#c7d3e6", FOG)),
    "disc": ("#2a3142", "#141925"),
    "heart": ("#e4dcff", PURPLE),
    "deep": PURPLE,
    "deep_glow": (150, 110, 255),
}
MARKS_ANIMATED = True
# Room above the card body: the claw marks cut across its top edge.
CARD_TOP = 6
# The soft layers (fog, the eye, the flash) are worked out at this share of the stage's size.
SOFT = 0.5
# The strike: when each set lands, the angle its slashes run at (degrees, screen y down), and the
# three slashes' offsets across it and their delays.
SET_A = (1.75, -34.0)
SET_B = (1.95, 36.0)
SLASHES = ((-1.0, 0.0), (0.0, 0.035), (1.0, 0.07))
# A slash's length and its thickest, in points at the design size; how far apart the three are.
LENGTH = 780.0
THICK = 24.0
SPACING = 74.0
# It grows over this long; then it holds, and frays away over FRAY.
GROW = 0.075
HOLD = 0.32
FRAY = 0.55
# Steps of fraying worked out once: each a little more of the slash eaten away.
FRAYS = 6


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(19)
    # Where the strike lands: the middle of the screen, high enough that no slash or its glow
    # reaches the button below.
    centre = QPointF(width * 0.5, min(height * 0.43, gap.top() - (LENGTH * 0.5 * math.sin(math.radians(36)) + SPACING + 70) * u))
    sprite = _slash_sprite(LENGTH * u, THICK * u, u)
    frayed = [_frayed(sprite, k / FRAYS, seed) for seed, k in enumerate(range(1, FRAYS + 1))]
    fog = (_fog_layer(width, height, u, 11, 0.9), _fog_layer(width, height, u, 23, 0.7))
    keep = _keep(width, height, gap, u)
    veil = QImage(max(1, round(width * SOFT)), max(1, round(height * SOFT)), QImage.Format_ARGB32_Premultiplied)
    notes = _notes(width, height, gap, u, rnd)
    puff = [(rnd.uniform(0, math.tau), rnd.uniform(40, 150) * u, rnd.uniform(26, 60) * u, rnd.uniform(0.0, 0.12)) for _ in range(16)]

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.25) * (1 - ease_in(win(t, 4.45, DURATION)))
        if life <= 0:
            return
        p.save()
        p.setOpacity(life)
        jolt = _jolt(t - SET_B[0] - GROW, u)
        p.translate(jolt)
        _veil(p, t, veil, fog, keep, width, height, gap, u)
        _notes_paint(p, t, notes, u)
        for when, angle in (SET_A, SET_B):
            _strike(p, t - when, angle, centre, sprite, frayed, u)
        _impact(p, t - SET_B[0] - GROW, centre, u)
        _puff(p, t - SET_B[0] - GROW, centre, puff, u)
        p.restore()

    return paint


# The fog and the eye --------------------------------------------------------------------------


def _fog_layer(width: float, height: float, u: float, seed: int, strength: float) -> QImage:
    """One layer of the 迷离 fog at SOFT size, a little bigger than the stage so it can drift: blue-
    grey haze, thick at the edges and thin over the middle, with its own billows."""
    w, h = max(1, round(width * SOFT * 1.16)), max(1, round(height * SOFT * 1.16))
    billows = noise(w, h, 120 * u * SOFT, 4, seed)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (xs / w - 0.5) * 2, (ys / h - 0.5) * 2
    # Thick at the edges, thin over the middle: an ellipse's distance out from the centre.
    edge = smooth(0.35, 1.25, np.sqrt(nx * nx * 0.8 + ny * ny))
    density = np.clip((0.22 + 0.78 * edge) * (0.55 + 0.75 * billows) * strength, 0, 1)
    light = smooth(0.35, 0.9, billows)[..., None]
    color = rgb(FOG_DEEP) * (1 - light) + rgb(FOG) * light
    return picture(color, density * 0.82)


def _keep(width: float, height: float, gap: QRectF, u: float) -> QImage:
    """Everywhere at SOFT size but the button and its marks: 1 outside, easing to 0 over a soft edge
    around the gap, so nothing laid through it reaches the button."""
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = (xs + 0.5) / SOFT, (ys + 0.5) / SOFT
    feather = 95 * u
    dx = np.maximum(np.maximum(gap.left() - x, x - gap.right()), 0)
    dy = np.maximum(np.maximum(gap.top() - y, y - gap.bottom()), 0)
    away = np.sqrt(dx * dx + dy * dy)
    alpha = smooth(0, feather, away) ** 0.8
    return picture(np.ones((h, w, 3), dtype=np.float32), alpha)


def _veil(p: QPainter, t: float, veil: QImage, fog: tuple, keep: QImage, width: float, height: float, gap: QRectF, u: float) -> None:
    """The fog rolling in, the eye closing to a slit and opening again, and the strike's flash, put
    together small, cleared over the button, and laid on."""
    come = ease_out(win(t, 0.45, 1.55))
    go = ease_in_out(win(t, 3.0, 4.25))
    thick = come * (1 - go)
    eye = ease_in_out(win(t, 0.9, 1.7)) * (1 - ease_in_out(win(t, 2.9, 3.9)))
    flash = _flash_level(t - SET_B[0] - GROW)
    if thick <= 0.005 and eye <= 0.005 and flash <= 0.005:
        return
    veil.fill(Qt.transparent)
    q = QPainter(veil)
    q.setRenderHint(QPainter.Antialiasing)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.scale(SOFT, SOFT)
    if thick > 0:
        # Each layer drifts its own way and breathes; it comes in from beyond the edges as it thickens.
        for index, layer in enumerate(fog):
            way = 1 if index == 0 else -1
            push = 1 + 0.35 * (1 - come)
            w, h = width * 1.16 * push, height * 1.16 * push
            x = (width - w) / 2 + way * (30 * u * math.sin(t * 0.7 + index) + 22 * u * t)
            y = (height - h) / 2 + 12 * u * math.sin(t * 0.9 + index * 2)
            q.setOpacity(thick * (0.85 + 0.15 * math.sin(t * 1.3 + index)))
            q.drawImage(QRectF(x, y, w, h), layer)
        q.setOpacity(1.0)
    if eye > 0:
        _eye(q, eye, t, width, height, u)
    if flash > 0:
        bright = QRadialGradient(QPointF(width * 0.5, height * 0.45), width * 0.75)
        bright.setColorAt(0, col("#f3eeff", 0.55 * flash))
        bright.setColorAt(0.5, col(LILAC, 0.32 * flash))
        bright.setColorAt(1, col(PURPLE, 0.12 * flash))
        q.fillRect(QRectF(0, 0, width, height), bright)
    q.resetTransform()
    q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    q.drawImage(0, 0, keep)
    q.end()
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, width, height), veil)
    p.restore()


def _eye(q: QPainter, k: float, t: float, width: float, height: float, u: float) -> None:
    """Dark all round an almond-shaped slit that closes in as k grows, its edge soft, swaying a little."""
    cx, cy = width * 0.5, height * 0.47
    half_w = width * (0.95 - 0.27 * k)
    half_h = height * (1.05 - 0.66 * k)
    tilt = 1.4 * math.sin(t * 1.1) * k
    q.save()
    q.translate(cx, cy)
    q.rotate(tilt)
    dark = QPainterPath()
    dark.addRect(QRectF(-width, -height, width * 2, height * 2))
    q.setPen(Qt.NoPen)
    steps = 7
    for step in range(steps):
        grow = 1 + 0.07 * (steps - 1 - step) / (steps - 1)
        almond = _almond(half_w * grow, half_h * grow)
        q.setBrush(col("#04060b", 0.86 * k / steps))
        q.drawPath(dark.subtracted(almond))
    q.restore()


def _almond(half_w: float, half_h: float) -> QPainterPath:
    """An eye's opening: two arcs meeting in points at either side."""
    path = QPainterPath(QPointF(-half_w, 0))
    path.quadTo(QPointF(0, -half_h * 2), QPointF(half_w, 0))
    path.quadTo(QPointF(0, half_h * 2), QPointF(-half_w, 0))
    path.closeSubpath()
    return path


def _notes(width: float, height: float, gap: QRectF, u: float, rnd: random.Random) -> list[tuple]:
    """The 指挥家's music in the fog: notes drifting on slow curves round the screen's edges."""
    font = QFont("Segoe UI Symbol")
    font.setPixelSize(max(6, round(34 * u)))
    shapes = []
    for glyph in "♪♫♩♬":
        path = QPainterPath()
        path.addText(QPointF(0, 0), font, glyph)
        box = path.boundingRect()
        shapes.append(path.translated(-box.center()))
    out = []
    for i in range(10):
        side = -1 if i % 2 == 0 else 1
        x = width * (0.5 + side * rnd.uniform(0.3, 0.46))
        y = height * rnd.uniform(0.12, 0.72)
        out.append((QPointF(x, y), rnd.choice(shapes), rnd.uniform(0.7, 1.5), rnd.uniform(0, math.tau), side, 0.75 + i * 0.12))
    return out


def _notes_paint(p: QPainter, t: float, notes: list[tuple], u: float) -> None:
    for at, shape, size, phase, side, born in notes:
        a = ease_out(win(t, born, born + 0.5)) * (1 - ease_in(win(t, 2.6, 3.4)))
        if a <= 0:
            continue
        age = t - born
        x = at.x() + side * 26 * u * math.sin(age * 1.4 + phase) - side * 18 * u * age
        y = at.y() - 30 * u * age + 10 * u * math.cos(age * 2.1 + phase)
        p.save()
        p.translate(x, y)
        p.rotate(18 * math.sin(age * 1.7 + phase))
        p.scale(size, size)
        soft_dot(p, 0, 0, 30 * u, "#e9f1ff", 0.22 * a)
        p.setPen(Qt.NoPen)
        p.setBrush(col("#f6f9ff", 0.85 * a))
        p.drawPath(shape)
        p.restore()


# The strike -----------------------------------------------------------------------------------


def _crescent(length: float, thick: float, bend: float = 0.05) -> QPainterPath:
    """One slash, lying along +x and centred on 0: pointed at both ends, thickest a little past its
    middle, bowed slightly, as a claw tears."""
    top, bottom = [], []
    n = 48
    for i in range(n + 1):
        s = i / n
        x = (s - 0.5) * length
        mid = -bend * length * 4 * s * (1 - s)
        half = thick * 0.5 * math.sin(math.pi * s) ** 0.9 * (0.7 + 0.3 * s)
        top.append(QPointF(x, mid - half))
        bottom.append(QPointF(x, mid + half * 0.7))
    path = QPainterPath(top[0])
    for point in top[1:]:
        path.lineTo(point)
    for point in reversed(bottom):
        path.lineTo(point)
    path.closeSubpath()
    return path


def _slash_sprite(length: float, thick: float, u: float) -> QImage:
    """A slash lit per pixel, as big as it plays: a white-hot core, lilac round it, a purple glow
    spreading out. Centred in its picture, along +x."""
    margin = 70 * u
    w, h = max(8, round(length + margin * 2)), max(8, round(thick + margin * 2))
    shape = _crescent(length, thick)

    def draw(q: QPainter) -> None:
        q.translate(w / 2, h / 2)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(shape)

    def thin(q: QPainter) -> None:
        # The white-hot core: the same slash, flattened to its middle.
        q.translate(w / 2, h / 2)
        q.scale(1.0, 0.45)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(shape)

    core = mask(w, h, draw)
    inner = mask(w, h, thin)
    sharp = max(1.0, 1.2 * u)
    lit = bloom(core, LILAC, ((sharp * 1.5, 1.0), (6 * u, 0.9), (18 * u, 0.6), (40 * u, 0.45)), white=0.6)
    halo = np.asarray(_rgba(lit), dtype=np.float32) / 255.0
    color = halo[..., :3] / np.maximum(halo[..., 3:], 1e-4)
    alpha = halo[..., 3]
    hot = np.clip(inner * 1.2, 0, 1)
    color = color * (1 - hot[..., None]) + rgb(CORE) * hot[..., None]
    alpha = np.maximum(alpha, hot)
    deep = np.clip(alpha - core, 0, 1)
    color = color * (1 - 0.35 * deep[..., None]) + rgb(PURPLE) * (0.35 * deep[..., None])
    return picture(color, alpha)


def _rgba(image: QImage) -> np.ndarray:
    """A picture's pixels as (h, w, 4) premultiplied RGBA bytes."""
    image = image.convertToFormat(QImage.Format_RGBA8888_Premultiplied)
    rows = np.frombuffer(image.constBits(), dtype=np.uint8, count=image.bytesPerLine() * image.height())
    return rows.reshape(image.height(), image.bytesPerLine())[:, : image.width() * 4].reshape(image.height(), image.width(), 4)


def _frayed(sprite: QImage, k: float, seed: int) -> QImage:
    """The slash a share k frayed away: eaten from its ends in and along wisps, its glow thinning."""
    pixels = _rgba(sprite).astype(np.float32) / 255.0
    h, w = pixels.shape[:2]
    grain = noise(w, h, 34.0, 2, 100 + seed)
    xs = np.abs(np.linspace(-1, 1, w, dtype=np.float32))[None, :]
    # The ends go first, the middle last, in soft wisps where the grain says.
    gone = smooth(-0.15, 0.45, (1 - k) * 1.25 - xs * 0.55 - (grain - 0.5) * 0.8)
    keep = np.clip(gone, 0, 1)[..., None] * (1 - 0.5 * k)
    out = pixels * keep
    alpha = out[..., 3]
    return picture(out[..., :3] / np.maximum(alpha, 1e-4)[..., None], alpha)


def _strike(p: QPainter, age: float, angle: float, centre: QPointF, sprite: QImage, frayed: list[QImage], u: float) -> None:
    """One set of three slashes: each grows from its tail to its tip in GROW, a hot point leading it,
    holds, then frays away."""
    if age < 0 or age > max(d for _o, d in SLASHES) + GROW + HOLD + FRAY:
        return
    sw, sh = sprite.width(), sprite.height()
    length = LENGTH * u
    for offset, delay in SLASHES:
        a = age - delay
        if a < 0:
            continue
        grown = ease_out(clamp(a / GROW))
        p.save()
        p.translate(centre)
        p.rotate(angle)
        # Each slash a little shorter and later the further it is from the middle one.
        p.translate(-offset * 26 * u, offset * SPACING * u)
        p.scale(1 - 0.08 * abs(offset), 1)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        box = QRectF(-sw / 2, -sh / 2, sw, sh)
        if a < GROW:
            p.setClipRect(QRectF(-sw / 2, -sh / 2, sw / 2 - length / 2 + length * grown + 30 * u, sh))
            p.drawImage(box, sprite)
            p.setClipping(False)
            tip = -length / 2 + length * grown
            soft_dot(p, tip, -2 * u, 46 * u, LILAC, 0.75)
            soft_dot(p, tip, -2 * u, 14 * u, "#ffffff", 1.0)
        elif a < GROW + HOLD:
            shimmer = 0.9 + 0.1 * math.sin(a * 40 + offset)
            p.setOpacity(p.opacity() * shimmer)
            p.drawImage(box, sprite)
        else:
            k = clamp((a - GROW - HOLD) / FRAY)
            step = min(len(frayed) - 1, int(k * len(frayed)))
            p.setOpacity(p.opacity() * (1 - ease_in(k) * 0.6))
            p.drawImage(box, frayed[step])
        p.restore()


def _flash_level(age: float) -> float:
    """The strike's flash: at once, then gone in a quarter of a second."""
    if age < 0 or age > 0.3:
        return 0.0
    return (1 - age / 0.3) ** 2


def _jolt(age: float, u: float) -> QPointF:
    """The screen's jolt as the second set lands: a hard shake dying away."""
    if age < 0 or age > 0.35:
        return QPointF(0, 0)
    fall = math.exp(-age * 14)
    return QPointF(14 * u * fall * math.sin(age * 95), 9 * u * fall * math.cos(age * 77))


def _impact(p: QPainter, age: float, centre: QPointF, u: float) -> None:
    """Where the sets cross: a burst of purple light and a white core."""
    if age < 0 or age > 0.6:
        return
    k = 1 - age / 0.6
    soft_dot(p, centre.x(), centre.y(), 260 * u * (0.7 + 0.5 * (1 - k)), PURPLE, 0.45 * k)
    soft_dot(p, centre.x(), centre.y(), 90 * u, "#ffffff", 0.8 * k ** 2)


def _puff(p: QPainter, age: float, centre: QPointF, puff: list[tuple], u: float) -> None:
    """A puff of pink smoke thrown out from the strike, swelling and rising as it thins."""
    if age < 0 or age > 1.2:
        return
    for angle, reach, size, delay in puff:
        a = age - delay
        if a <= 0:
            continue
        k = clamp(a / 1.0)
        out = ease_out(k)
        x = centre.x() + math.cos(angle) * reach * out
        y = centre.y() + math.sin(angle) * reach * out * 0.6 - 40 * u * k
        soft_dot(p, x, y, size * (0.6 + 0.9 * out), PINK, 0.32 * (1 - k) ** 1.4)


# The 嘉宾 marks -------------------------------------------------------------------------------

_MADE: dict[tuple, QImage] = {}


def _kept(key: tuple, build):  # noqa: ANN001, ANN202
    if key not in _MADE:
        _MADE[key] = build()
    return _MADE[key]


def _sharpness(p: QPainter) -> float:
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return round(max(1.0, ratio * math.hypot(p.transform().m11(), p.transform().m12())), 2)


def _claw_marks(length: float, thick: float, scale: float, angle: float, count: int = 3, spacing: float | None = None) -> QImage:
    """A small set of claw marks lit per pixel, at scale pixels to the point, centred in its picture."""
    spacing = spacing if spacing is not None else thick * 2.6
    margin = thick * 2.5
    side = length + margin * 2 + spacing * count
    w = h = max(4, math.ceil(side * scale))
    marks = [_crescent(length * (1 - 0.1 * abs(i - (count - 1) / 2)), thick) for i in range(count)]

    def draw(q: QPainter) -> None:
        q.translate(w / 2, h / 2)
        q.scale(scale, scale)
        q.rotate(angle)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        for i, mark in enumerate(marks):
            q.save()
            q.translate(0, (i - (count - 1) / 2) * spacing)
            q.drawPath(mark)
            q.restore()

    core = mask(w, h, draw)
    image = bloom(core, LILAC, ((0.8 * scale, 1.0), (2.5 * scale, 0.8), (6 * scale, 0.5)), white=0.8)
    image.setDevicePixelRatio(scale)
    return image


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A fine lilac rim round the button in a purple haze, claw marks torn across two of its corners;
    every few seconds they strike again."""
    scale = _sharpness(p)
    radius = min(cover.height() * 0.3, 18.0)
    halo = QRadialGradient(cover.center(), cover.width() * 0.62)
    halo.setColorAt(0.6, col(PURPLE, 0.0))
    halo.setColorAt(0.85, col(PURPLE, 0.22))
    halo.setColorAt(1.0, col(PURPLE, 0.0))
    p.setPen(Qt.NoPen)
    p.setBrush(halo)
    p.drawRoundedRect(cover.adjusted(-8, -8, 8, 8), radius + 8, radius + 8)
    p.setBrush(Qt.NoBrush)
    for inset, color, alpha, width in ((1.0, LILAC, 0.9, 2.0), (3.6, "#ffffff", 0.5, 0.9)):
        p.setPen(QPen(col(color, alpha), width))
        p.drawRoundedRect(cover.adjusted(inset, inset, -inset, -inset), max(1.0, radius - inset), max(1.0, radius - inset))
    size = min(cover.height() * 0.62, 44.0)
    marks = _kept(("ring", round(size, 1), scale), lambda: _claw_marks(size, max(1.6, size * 0.09), scale, -40))
    side = marks.width() / scale
    cycle = t % 3.6
    for corner, at in ((0, QPointF(cover.left() + side * 0.26, cover.top() + side * 0.24)), (1, QPointF(cover.right() - side * 0.26, cover.bottom() - side * 0.24))):
        strike = clamp((cycle - corner * 0.12) / 0.12)
        pulse = 0.75 + 0.25 * math.sin(t * 2.4 + corner)
        p.save()
        p.translate(at)
        if strike < 1:
            p.setClipRect(QRectF(-side / 2, -side / 2, side * strike, side))
        p.setOpacity(pulse)
        p.drawImage(QRectF(-side / 2, -side / 2, side, side), marks)
        p.restore()


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A dark misty disc in a lilac rim with a claw-mark X glowing on it, the X pulsing."""
    scale = _sharpness(p)
    side = box.width()
    disc = _kept(("disc", round(side, 1), scale), lambda: _disc(side, scale))
    halo = QRadialGradient(box.center(), side * 0.75)
    halo.setColorAt(0.55, col(PURPLE, 0.35))
    halo.setColorAt(1.0, col(PURPLE, 0.0))
    p.setPen(Qt.NoPen)
    p.setBrush(halo)
    p.drawEllipse(box.center(), side * 0.75, side * 0.75)
    p.drawImage(box, disc)
    marks_a = _kept(("x_a", round(side, 1), scale), lambda: _claw_marks(side * 0.6, max(1.8, side * 0.075), scale, -45, spacing=side * 0.13))
    marks_b = _kept(("x_b", round(side, 1), scale), lambda: _claw_marks(side * 0.6, max(1.8, side * 0.075), scale, 45, spacing=side * 0.13))
    pulse = 0.82 + 0.18 * math.sin(t * 3.0)
    for marks in (marks_a, marks_b):
        m = marks.width() / scale
        p.setOpacity(pulse)
        p.drawImage(QRectF(box.center().x() - m / 2, box.center().y() - m / 2, m, m), marks)
    p.setOpacity(1.0)


def _disc(side: float, scale: float) -> QImage:
    """The badge's disc per pixel: slate glass with fog in it, lit at the top, a lilac rim."""
    w = h = max(4, math.ceil(side * scale))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot(xs + 0.5 - w / 2, ys + 0.5 - h / 2) / (w / 2)
    inside = smooth(1.0, 0.94, r)
    mist = noise(w, h, max(2.0, w / 5), 3, 31)
    v = (ys + 0.5) / h
    color = rgb("#2f3a4f") * (1 - v)[..., None] + rgb("#121722") * v[..., None]
    color = color + rgb(FOG) * (mist * 0.22 * (1 - r * 0.5))[..., None]
    rim = smooth(0.8, 0.9, r) * smooth(1.0, 0.92, r)
    color = color * (1 - rim)[..., None] + rgb(LILAC) * rim[..., None]
    shine = np.exp(-(((xs / w - 0.42) / 0.22) ** 2 + ((ys / h - 0.22) / 0.1) ** 2)) * 0.25
    color = color + shine[..., None]
    image = picture(color, inside)
    image.setDevicePixelRatio(scale)
    return image


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """Misty slate glass: fog stirring in it, a lilac edge, and three claw marks torn across its top
    right corner, glowing faintly."""
    scale = _sharpness(p)
    glass = _kept(("card", round(rect.width(), 1), round(rect.height(), 1), scale), lambda: _glass(rect, scale))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(rect, glass)
    size = min(rect.height() * 0.62, 46.0)
    marks = _kept(("card_marks", round(size, 1), scale), lambda: _claw_marks(size, max(1.5, size * 0.08), scale, -38))
    side = marks.width() / scale
    p.setOpacity(0.7 + 0.2 * math.sin(t * 1.8))
    p.drawImage(QRectF(rect.right() - side * 0.62, rect.top() + CARD_TOP - side * 0.36, side, side), marks)
    p.setOpacity(1.0)


def _glass(rect: QRectF, scale: float) -> QImage:
    """The card per pixel: slate glass, darker toward its foot, fog drifting in it, a lilac edge."""
    w, h = max(4, math.ceil(rect.width() * scale)), max(4, math.ceil(rect.height() * scale))
    body = rect.adjusted(0, CARD_TOP, 0, 0)
    radius = 8.0

    def shape(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(-rect.left(), -rect.top())
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawRoundedRect(body, radius, radius)

    inside = mask(w, h, shape)
    ys, _xs = np.mgrid[0:h, 0:w].astype(np.float32)
    v = np.clip((ys / scale - CARD_TOP) / max(1.0, body.height()), 0, 1)
    color = rgb(LOOK["card"][0]) * (1 - v)[..., None] + rgb(LOOK["card"][1]) * v[..., None]
    mist = noise(w, h, max(3.0, 26 * scale), 3, 7)
    color = color + rgb(FOG) * (smooth(0.45, 0.9, mist) * 0.16)[..., None]
    k = max(1, round(1.2 * scale))
    edge = np.clip(inside - np.roll(np.roll(inside, k, 0), k, 1) * np.roll(np.roll(inside, -k, 0), -k, 1), 0, 1)
    color = color * (1 - edge)[..., None] + rgb(LOOK["edge"]) * edge[..., None]
    image = picture(color, inside * 0.94)
    image.setDevicePixelRatio(scale)
    return image


def lead(size: float, index: int) -> QPixmap:
    """A small glowing claw mark before each name."""
    scale = 3.0
    image = _kept(("lead", round(size, 2), index % 2), lambda: _claw_marks(size * 0.62, max(0.9, size * 0.07), scale, -50 + 12 * (index % 2), count=2, spacing=size * 0.16))
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(scale)
    return pixmap

