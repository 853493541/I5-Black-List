"""遇袭 Ambush: you are the one attacked, as in 模仿者狂欢's 迷离 and its kill.

For a moment nothing. Then the 指挥家's fog rolls in from the edges, heavy at the borders, blue-grey
and drifting two ways at once, and as it comes every player's name is lost in it, a ??? in its place,
as 迷离 scrambles them; white music notes swirl through the haze. At three seconds the strike, the
game's own kill mark made bigger than the screen's middle: three tapered slashes rip up across it,
white-hot at their cores and purple at their edges, a lilac flash, a jolt, a puff of pink smoke; and
at that moment 演说家遇袭 slides up into the top right as the game shows it, its own art: the BIG NEWS
newspaper tossed up into place, the words coming into focus over a dark band. The slashes fray away,
the fog clears and the names come back. Its tune (MUSIC) is the 指挥家's music, with the notice's
sound in it at the strike once that sound is recorded (build/ambush_tune.py).

The 嘉宾 marks wear it: a misty glass card scored by three claw marks, a lilac rim round the button
with claw marks at two corners that now and then strike again, and a claw-mark X on a dark disc for a
badge. No heart.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QImage, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient

from blacklist_detect.love_scenes.draw import clamp, col, ease_back, ease_in, ease_in_out, ease_out, soft_dot, win
from blacklist_detect.love_scenes.light import bloom, blur, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 6.6
# The tune it brings (ui_music.SCENE_TUNES), played instead of 音乐's choice unless that is 无.
MUSIC = "ambush"
# The fog rolls in and clears; the names go and come back with it.
FOG_IN = (0.35, 1.4)
FOG_OUT = (4.75, 5.9)
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
# The soft layers (the fog, the flash) are worked out at this share of the stage's size.
SOFT = 0.5
# The strike: when it lands, the angle its slashes run at (degrees, screen y down), and the three
# slashes' offsets across it and their delays.
STRIKE = (3.0, -34.0)
SLASHES = ((-1.0, 0.0), (0.0, 0.035), (1.0, 0.07))
# A slash's length and its thickest, in points at the design size; how far apart the three are.
LENGTH = 1000.0
THICK = 32.0
SPACING = 96.0
# When the strike has all landed: the flash, the jolt and the smoke start then.
LANDED = STRIKE[0] + SLASHES[-1][1] + 0.075
# It grows over this long; then it holds, and frays away over FRAY.
GROW = 0.075
HOLD = 0.32
FRAY = 0.55
# Steps of fraying worked out once: each a little more of the slash eaten away.
FRAYS = 6
# 演说家遇袭: shown from the strike for this long, then gone over NOTICE_OUT.
NOTICE_HOLD = 2.35
NOTICE_OUT = 0.45
NOTICE_SLIDE = 0.32
# The notice's art from the game (assets, cut by build/orator_notice_art.py), and where each piece sat
# in the picture it was cut from, (left, top), (width, height) in its pixels; the words show this high.
ASSETS = Path(__file__).resolve().parent.parent / "assets"
NOTICE_PAPER = ((0, 335), (572, 416))
NOTICE_WORDS = ((585, 455), (1026, 177))
NOTICE_HIGH = 42.0


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(19)
    # Where the strike lands: the middle of the screen, high enough that no slash or its glow
    # reaches the button below.
    reach = LENGTH * 0.5 * math.sin(math.radians(abs(STRIKE[1]))) + SPACING * math.cos(math.radians(STRIKE[1])) + 80
    centre = QPointF(width * 0.5, min(height * 0.43, gap.top() - reach * u))
    sprite = _slash_sprite(LENGTH * u, THICK * u, u)
    frayed = [_frayed(sprite, k / FRAYS, seed) for seed, k in enumerate(range(1, FRAYS + 1))]
    fog = (_fog_layer(width, height, u, 11, 1.0), _fog_layer(width, height, u, 23, 0.85))
    keep = _keep(width, height, gap, u)
    veil = QImage(max(1, round(width * SOFT)), max(1, round(height * SOFT)), QImage.Format_ARGB32_Premultiplied)
    notes = _notes(width, height, gap, u, rnd)
    seats = stage.names()
    cloud = _cloud(u)
    unknown = _unknown(seats)
    notice = _notice_art(u)
    notice_at = QPointF(width - 26 * u, height * 0.165)
    puff = [(rnd.uniform(0, math.tau), rnd.uniform(40, 150) * u, rnd.uniform(26, 60) * u, rnd.uniform(0.0, 0.12)) for _ in range(16)]

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.25) * (1 - ease_in(win(t, DURATION - 0.4, DURATION)))
        if life <= 0:
            return
        p.save()
        p.setOpacity(life)
        p.translate(_jolt(t - LANDED, u))
        _veil(p, t, veil, fog, keep, width, height, u)
        _lost_names(p, t, seats, cloud, unknown, u)
        _notes_paint(p, t, notes, u)
        _strike(p, t - STRIKE[0], STRIKE[1], centre, sprite, frayed, u)
        _impact(p, t - LANDED, centre, u)
        _puff(p, t - LANDED, centre, puff, u)
        p.restore()
        # The notice does not shake: it is the game telling you, not the blow.
        p.save()
        p.setOpacity(life)
        _notice(p, t - STRIKE[0], notice, notice_at, u)
        p.restore()

    return paint


# The fog --------------------------------------------------------------------------------------


def _fog_layer(width: float, height: float, u: float, seed: int, strength: float) -> QImage:
    """One layer of the 迷离 fog at SOFT size, a little bigger than the stage so it can drift: blue-
    grey haze, thick at the edges and thin over the middle, with its own billows."""
    w, h = max(1, round(width * SOFT * 1.16)), max(1, round(height * SOFT * 1.16))
    billows = noise(w, h, 120 * u * SOFT, 4, seed)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (xs / w - 0.5) * 2, (ys / h - 0.5) * 2
    # Thick at the edges, thin over the middle: an ellipse's distance out from the centre.
    edge = smooth(0.3, 1.1, np.sqrt(nx * nx * 0.8 + ny * ny))
    density = np.clip((0.18 + 1.1 * edge) * (0.6 + 0.7 * billows) * strength, 0, 1)
    light = smooth(0.35, 0.9, billows)[..., None]
    color = rgb(FOG_DEEP) * (1 - light) + rgb(FOG) * light
    return picture(color, density * 0.96)


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


def _veil(p: QPainter, t: float, veil: QImage, fog: tuple, keep: QImage, width: float, height: float, u: float) -> None:
    """The fog rolling in and clearing, and the strike's flash, put together small, cleared over the
    button, and laid on."""
    thick = _fog_level(t)
    flash = _flash_level(t - LANDED)
    if thick <= 0.005 and flash <= 0.005:
        return
    come = ease_out(win(t, *FOG_IN))
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


def _fog_level(t: float) -> float:
    """How thick the fog is: rolling in, then clearing."""
    return ease_out(win(t, *FOG_IN)) * (1 - ease_in_out(win(t, *FOG_OUT)))


def _cloud(u: float) -> QImage:
    """A puff of the fog, per pixel, for laying over one name: thick in the middle, wisps at the edge."""
    w, h = max(8, round(220 * u)), max(8, round(90 * u))
    billows = noise(w, h, 26 * u, 3, 41)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (xs + 0.5) / w * 2 - 1, (ys + 0.5) / h * 2 - 1
    # A solid middle, wide enough for a long name, and billowing wisps round it.
    r = np.sqrt((nx / 1.0) ** 2 + (ny / 1.0) ** 2)
    core = smooth(0.82, 0.55, np.maximum(np.abs(nx) * 0.95, np.abs(ny) * 1.15))
    wisps = smooth(1.0, 0.6, r) * (0.55 + 0.6 * billows)
    density = np.clip(np.maximum(core, wisps), 0, 1)
    light = smooth(0.3, 0.85, billows)[..., None]
    color = rgb("#4b5d71") * (1 - light) + rgb("#9fb1c4") * light
    return picture(color, density)


def _unknown(seats: tuple[QRectF, ...]) -> list[tuple[QPainterPath, float]]:
    """??? for each name, as a path the height of its box, centred on the origin, and its width."""
    out = []
    for seat in seats:
        font = QFont("Microsoft YaHei")
        font.setPixelSize(max(6, round(seat.height() * 0.9)))
        font.setWeight(QFont.Weight.Bold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, seat.height() * 0.08)
        path = QPainterPath()
        path.addText(QPointF(0, 0), font, "???")
        box = path.boundingRect()
        out.append((path.translated(-box.center()), box.width()))
    return out


def _lost_names(p: QPainter, t: float, seats: tuple[QRectF, ...], cloud: QImage, unknown: list[tuple], u: float) -> None:
    """Each name lost in a puff of fog as the fog comes in, a ??? there instead that now and then
    flickers as 迷离 scrambles it; the names come back as the fog clears."""
    a = _fog_level(t)
    if a <= 0:
        return
    for index, seat in enumerate(seats):
        c = seat.center()
        w, h = max(seat.width() * 1.6, 150 * u), seat.height() * 2.3
        drift = 4 * u * math.sin(t * 1.3 + index)
        p.save()
        p.setOpacity(p.opacity() * a)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(QRectF(c.x() - w / 2 + drift, c.y() - h / 2, w, h), cloud)
        path, width = unknown[index]
        # 迷离 scrambles it: now and then it jumps sideways and dims for a frame or two.
        glitch = math.sin(t * 17 + index * 3.1) > 0.94
        p.translate(c.x() + (3 * u if glitch else 0), c.y())
        soft_dot(p, 0, 0, max(width, 30 * u) * 0.75, "#dfe6ff", 0.25)
        p.setPen(Qt.NoPen)
        p.setBrush(col("#f4f6ff", 0.55 if glitch else 0.95))
        p.drawPath(path)
        p.restore()


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
        # On the right, below where 演说家遇袭 comes up.
        y = height * rnd.uniform(0.12 if side < 0 else 0.3, 0.72)
        out.append((QPointF(x, y), rnd.choice(shapes), rnd.uniform(0.7, 1.5), rnd.uniform(0, math.tau), side, 0.55 + i * 0.15))
    return out


def _notes_paint(p: QPainter, t: float, notes: list[tuple], u: float) -> None:
    for at, shape, size, phase, side, born in notes:
        a = ease_out(win(t, born, born + 0.5)) * (1 - ease_in(win(t, FOG_OUT[0], FOG_OUT[1] - 0.3)))
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
    """The strike's flash: at once, then gone in under a third of a second."""
    if age < 0 or age > 0.3:
        return 0.0
    return (1 - age / 0.3) ** 2


def _jolt(age: float, u: float) -> QPointF:
    """The screen's jolt as the strike lands: a hard shake dying away."""
    if age < 0 or age > 0.35:
        return QPointF(0, 0)
    fall = math.exp(-age * 14)
    return QPointF(14 * u * fall * math.sin(age * 95), 9 * u * fall * math.cos(age * 77))


def _impact(p: QPainter, age: float, centre: QPointF, u: float) -> None:
    """Where the strike lands: a burst of purple light and a white core."""
    if age < 0 or age > 0.6:
        return
    k = 1 - age / 0.6
    soft_dot(p, centre.x(), centre.y(), 300 * u * (0.7 + 0.5 * (1 - k)), PURPLE, 0.45 * k)
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


# 演说家遇袭 --------------------------------------------------------------------------------------


def _notice_art(u: float) -> tuple[QImage, QImage, QImage, QImage, QRectF, QRectF]:
    """The notice's own art from the game (build/orator_notice_art.py): the newspaper, the words, the
    words blurred (for fading in) and the dark band behind them, made at twice the size they show; and
    where the newspaper and the words sit, in points, from the words' right middle, as the game spaces
    them."""
    k = NOTICE_HIGH * u / NOTICE_WORDS[1][1]

    def at(box: tuple[tuple[int, int], tuple[int, int]]) -> QRectF:
        (x, y), (w, h) = box
        right, middle = NOTICE_WORDS[0][0] + NOTICE_WORDS[1][0], NOTICE_WORDS[0][1] + NOTICE_WORDS[1][1] / 2
        return QRectF((x - right) * k, (y - middle) * k, w * k, h * k)

    paper_box, words_box = at(NOTICE_PAPER), at(NOTICE_WORDS)

    def load(name: str, box: QRectF) -> QImage:
        image = QImage(str(ASSETS / name)).convertToFormat(QImage.Format_ARGB32_Premultiplied)
        size = (max(1, round(box.width() * 2)), max(1, round(box.height() * 2)))
        return image.scaled(*size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    paper, words = load("orator_paper.png", paper_box), load("orator_words.png", words_box)
    soft = _blurred(words, 5 * u * 2)
    bw, bh = round(words_box.width() * 1.3 + 90 * u), round(words_box.height() * 1.9)
    ys, xs = np.mgrid[0:bh, 0:bw].astype(np.float32)
    across = smooth(0.0, 0.35, xs / bw) * smooth(1.0, 0.85, xs / bw)
    down = smooth(0.0, 0.3, ys / bh) * smooth(1.0, 0.7, ys / bh)
    band = picture(np.zeros((bh, bw, 3), dtype=np.float32), across * down * 0.62)
    return paper, words, soft, band, paper_box, words_box


def _blurred(image: QImage, sigma: float) -> QImage:
    """A picture softened, its glow spread: the words before they come into focus."""
    pixels = _rgba(image).astype(np.float32) / 255.0
    out = np.dstack([blur(pixels[..., c], sigma) for c in range(4)])
    alpha = np.clip(out[..., 3] * 1.3, 0, 1)
    return picture(out[..., :3] / np.maximum(out[..., 3:], 1e-4), alpha)


def _notice(p: QPainter, age: float, art: tuple, right_middle: QPointF, u: float) -> None:
    """演说家遇袭 in the top right, as the game shows it: the whole notice slides up from below into place,
    the newspaper tossed up with it, wobbling, a blur behind it; then the words come into focus over the
    dark band; held; then it rises a little and is gone."""
    if age < 0 or age > NOTICE_HOLD + NOTICE_OUT:
        return
    paper, words, soft, band, paper_box, words_box = art
    leave = ease_in(win(age, NOTICE_HOLD, NOTICE_HOLD + NOTICE_OUT))
    # Up from below in a third of a second, a touch past its place and back.
    slide = 70 * u * (1 - ease_back(clamp(age / NOTICE_SLIDE), 1.4))
    p.save()
    p.translate(right_middle.x(), right_middle.y() + slide - 10 * u * leave)
    p.setOpacity(p.opacity() * clamp(age / 0.1))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    base = p.opacity()
    focus = ease_out(win(age, 0.12, 0.34)) * (1 - leave)
    if focus > 0:
        bw, bh = band.width(), band.height()
        p.setOpacity(base * focus)
        p.drawImage(QRectF(words_box.right() - bw + 30 * u, words_box.center().y() - bh / 2, bw, bh), band)
        p.setOpacity(base * (1 - focus) * min(1.0, focus * 3))
        p.drawImage(words_box, soft)
        p.setOpacity(base * focus)
        p.drawImage(words_box, words)
    # The newspaper rises 40 points in a fifth of a second, turning into its tilt with a wobble.
    rise = ease_out(clamp(age / 0.2))
    settle = max(0.0, age - 0.2)
    turn = -16 * (1 - rise) + 7 * math.exp(-settle * 9) * math.sin(settle * 30)
    alpha = clamp(age / 0.05) * (1 - leave)
    c = paper_box.center()
    box = QRectF(-paper_box.width() / 2, -paper_box.height() / 2, paper_box.width(), paper_box.height())
    for ghost in (2, 1, 0) if rise < 1 else (0,):
        p.save()
        p.setOpacity(base * alpha * (1.0 if ghost == 0 else 0.22 / ghost))
        p.translate(c.x(), c.y() + 40 * u * (1 - rise) + ghost * 9 * u * (1 - rise))
        p.rotate(turn)
        p.drawImage(box, paper)
        p.restore()
    p.restore()


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

