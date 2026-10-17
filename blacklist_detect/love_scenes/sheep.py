"""喜羊羊: a sunny morning on 青青草原 comes to the lobby's edges, and the cartoon's best-known gag plays in it.

A rolling meadow rises along the bottom, its grass grained per pixel and its blades swaying, a few
little flowers in it and a wooden signpost reading 青青草原; a soft sky haze and puffy clouds drift in
along the top, and a warm sun glows in the top left corner. A little white lamb, round cloud-puff wool,
big shining eyes, curled horns and a golden bell on a red collar, bounces in from the left in three
hops, lands and waves. A grey wolf in a patched yellow hat, a scar on his cheek, tiptoes in on the
right half behind a bush, rubbing his paws and grinning, until a frying pan flies in from the top
right: 咣! He spins up and away into the sky, 我一定会回来的！ trailing him, and twinkles out as a star.
The lamb jumps for joy, the meadow sways, and it all sinks back and fades. Both are drawn here, in
code, in the spirit of 喜羊羊与灰太狼; nothing is traced from the show.

Its marks: the card a sunny meadow card, cream paper with shaded grass along its bottom and a little
cloud on its corner, the names in a rounded hand (幼圆 where it is installed), each after a golden
bell; the ring a garland of wool puffs round the button, bobbing; the badge the golden bell on its red
collar, swinging and glinting now and then.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPainterPathStroker, QPen, QPixmap, QRadialGradient, QTransform

from blacklist_detect.love_scenes.draw import clamp, col, ease_back, ease_in, ease_in_out, ease_out, glint, soft_dot, spring, star, win
from blacklist_detect.love_scenes.light import bloom, blur, glow, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from collections.abc import Callable

    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# 青青草原's colors: its grass, sky and sun; the lamb's wool, face, horns, hooves, bell and collar; the
# wolf's greys, hat and its patch; the pan's iron, the signpost's wood, and the ink of every outline.
GRASS = "#7ccf4a"
GRASS_LIGHT = "#b8e86e"
GRASS_DEEP = "#3f8f2e"
SKY = "#8fd3ff"
SUN = "#ffd36b"
WOOL = "#f2f4f9"
CREAM = "#fde6c4"
PINK = "#f7a3b2"
HORN = "#f0d29a"
HOOF = "#6b4a35"
BELL = "#f5c542"
COLLAR = "#e0393e"
GREY = "#8d929c"
GREY_LIGHT = "#d6d9df"
GREY_DEEP = "#666b77"
HAT = "#f6c838"
PATCH = "#d8742c"
IRON = "#34363d"
WOOD = "#c98d52"
INK = "#2f2622"
PAPER = "#fffaee"
LOOK = {
    "glow": (255, 214, 102),
    "rim": BELL,
    "band": (GRASS, "#fff3c4"),
    "card": (PAPER, "#fdf1d4"),
    "edge": "#8fc85a",
    "ink": "#4a3420",
    "flowers": (("#fffbe8", BELL, "#c9922a"), ("#f4ffe8", "#a6dc72", GRASS_DEEP)),
    "disc": (PAPER, "#ffe9a8"),
    "heart": ("#ff7f86", COLLAR),
    "deep": "#d9a520",
    "deep_glow": (245, 197, 66),
}
MARKS_ANIMATED = True
# Room over the card for the little cloud on its corner.
CARD_TOP = 14
# The grass along the card's bottom takes room there.
CARD_PAD = (12, 8, 12, 15)
# A rounded hand; the app's Chinese face where it is not installed.
CARD_FONT = "YouYuan"
ROUNDED = ["YouYuan", "Microsoft YaHei", "Microsoft YaHei UI"]

# Light from the upper left, and halfway between it and the eye, for gloss.
LIGHT = np.array([-0.5, -0.62, 0.6]) / np.linalg.norm([-0.5, -0.62, 0.6])
HALF = (LIGHT + [0, 0, 1]) / np.linalg.norm(LIGHT + [0, 0, 1])
# The lamb's three hops in from the left: (takes off, lands, from x, to x, how high), x from the
# screen's left edge and heights in points at full size.
HOPS = ((0.5, 0.84, -80.0, 22.0, 58.0), (0.84, 1.18, 22.0, 88.0, 46.0), (1.18, 1.52, 88.0, 150.0, 36.0))
# It waves, and later jumps for joy: (takes off, lands, how high).
WAVE = (1.58, 2.62)
JUMPS = ((3.45, 3.85, 52.0), (3.92, 4.32, 42.0))
# The wolf tiptoes in; the pan flies in and hits; he flies off and becomes a star; his words trail him.
SNEAK = (1.5, 2.35)
PAN = (2.52, 2.75)
FLIGHT = (2.82, 3.6)
BUBBLE_AT = 3.2
# The lamb and the wolf, how tall, in points at full size.
LAMB = 126.0
WOLF = 128.0
# The grass blades sway through these pictures, one after another.
SWAYS = 10


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    lamb_s, wolf_s = LAMB * u, WOLF * u
    ground_l, ground_r = height - 30 * u, height - 24 * u
    wolf_x = width - 108 * u
    bush_at = QPointF(wolf_x - 22 * u, height - 8 * u)
    sign_at = QPointF(max(gap.left() - 92 * u, 250 * u), height - 34 * u)
    sun = QPointF(30 * u, 22 * u)
    # Where the pan hits his hat, and the flight from there up the right edge to where he twinkles out.
    hit = QPointF(wolf_x, ground_r - 0.9 * wolf_s)
    twinkle = QPointF(width - 238 * u, 92 * u)
    flight = (QPointF(wolf_x, ground_r - 0.5 * wolf_s), QPointF(width - 18 * u, height * 0.5), QPointF(width - 40 * u, 120 * u), twinkle)
    # (x, y, how wide, which way it drifts in from)
    clouds = [(255 * u, 82 * u, 140 * u, -1), (585 * u, 58 * u, 96 * u, -1), (width - 118 * u, 70 * u, 128 * u, 1)]
    makers = [
        ("sky", lambda _scale: _sky(width, u)),
        ("sun", lambda _scale: _sun(sun, u)),
        ("rays", lambda _scale: _rays(u)),
        *((("cloud", index), lambda scale, wide=wide, index=index: _cloud(wide, scale, 5 + index)) for index, (_x, _y, wide, _from) in enumerate(clouds)),
        *((("meadow", side), lambda scale, side=side: _meadow(width, height, gap, u, scale, side)) for side in (-1, 1)),
        *((("blades", side, phase), lambda scale, side=side, phase=phase: _blades(width, height, gap, u, scale, side, phase)) for phase in range(SWAYS) for side in (-1, 1)),
        ("sign", lambda scale: _sign(u, scale)),
        ("bush", lambda scale: _bush(132 * u, scale)),
        *((("lamb", face), lambda scale, face=face: _lamb(lamb_s, scale, face)) for face in ("open", "happy")),
        ("arm", lambda scale: _arm(lamb_s, scale)),
        ("bell", lambda scale: _bell(0.062 * lamb_s, scale)),
        ("wolf", lambda scale: _wolf(wolf_s, scale, "sneak")),
        ("paw", lambda scale: _paw(wolf_s, scale)),
        ("pan", lambda scale: _pan(34 * u, scale)),
        ("hit", lambda scale: _wolf(wolf_s, scale, "hit")),
        ("burst", lambda scale: _burst(54 * u, scale)),
        ("bubble", lambda scale: _bubble(u, scale)),
        ("star", lambda scale: _star(20 * u, scale)),
        ("star-glow", lambda _scale: _star_glow(20 * u)),
    ]
    how = dict(makers)
    baked: dict[tuple, object] = {}

    def picture_of(name: object, scale: float) -> object:
        # The soft light is the same at every sharpness.
        if name in ("sky", "sun", "rays", "star-glow"):
            scale = 0.0
        if (name, scale) not in baked:
            baked[name, scale] = how[name](scale)
        return baked[name, scale]

    def paint(p: QPainter, t: float) -> None:
        # Up from below as it comes in, down again at the end.
        up = ease_out(win(t, 0.0, 0.7)) * (1 - ease_in(win(t, 4.4, 5.0)))
        life = 1 - ease_in(win(t, 4.55, 5.0))
        if up <= 0 or life <= 0:
            return
        scale = _sharpness(p)
        drop = (1 - up) * 150 * u
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setOpacity(life * up)
        rect, image = picture_of("sun", scale)
        p.drawImage(rect, image)
        p.save()
        p.translate(sun)
        p.rotate(t * 7)
        p.setOpacity(life * up * (0.8 + 0.2 * math.sin(t * 2.3)))
        rect, image = picture_of("rays", scale)
        p.drawImage(rect, image)
        p.restore()
        p.setOpacity(life * ease_out(win(t, 0.05, 0.75)))
        rect, image = picture_of("sky", scale)
        p.drawImage(rect.translated(0, -(1 - up) * 50 * u), image)
        for index, (x, y, wide, side) in enumerate(clouds):
            come = ease_out(win(t, 0.05 + 0.12 * index, 0.85 + 0.12 * index))
            if come <= 0:
                continue
            image, box = picture_of(("cloud", index), scale)
            drift = side * (1 - come) * (wide + 160 * u) - side * 6 * u * t
            bob = 2.5 * u * math.sin(t * 1.4 + index * 2)
            p.setOpacity(life * come * (1 - ease_in(win(t, 4.4, 4.9))))
            p.drawImage(box.translated(x + drift, y + bob - (1 - up) * 40 * u), image)
        p.setOpacity(life)
        for side in (-1, 1):
            rect, image = picture_of(("meadow", side), scale)
            p.drawImage(rect.translated(0, drop), image)
        image, box = picture_of("sign", scale)
        p.drawImage(box.translated(sign_at.x(), sign_at.y() + drop), image)
        # The blades sway in a breeze that gusts as the lamb jumps for joy.
        breeze = t * 0.65 + 1.6 * ease_in_out(win(t, 3.35, 4.45))
        step = (breeze * SWAYS) % SWAYS
        first, mix_in = int(step), step - int(step)
        for side in (-1, 1):
            for phase, alpha in ((first, 1.0), ((first + 1) % SWAYS, mix_in)):
                rect, image = picture_of(("blades", side, phase), scale)
                p.setOpacity(life * alpha)
                p.drawImage(rect.translated(0, drop), image)
        p.setOpacity(life)
        _paint_lamb(p, t, lambda name: picture_of(name, scale), u, lamb_s, ground_l + drop)
        _paint_wolf(p, t, lambda name: picture_of(name, scale), u, wolf_s, wolf_x, width, ground_r + drop, bush_at + QPointF(0, drop))
        _paint_gag(p, t, lambda name: picture_of(name, scale), u, wolf_s, hit, flight, width, height)
        p.restore()
        # One picture worked out ahead each frame, so no frame waits long for it.
        for name, _how in makers:
            key = (name, 0.0 if name in ("sky", "sun", "rays", "star-glow") else scale)
            if key not in baked:
                picture_of(name, scale)
                break

    return paint


def _sharpness(p: QPainter) -> float:
    """Pixels per point where p draws: its screen's and its own scaling."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return round(ratio * math.hypot(p.transform().m11(), p.transform().m12()), 2)


# The lamb.


def _lamb_pose(t: float) -> tuple[float, float, float, str, float, float, float] | None:
    """Where the lamb is at t, or None before it comes: x from the left edge and how high off the
    ground (points at full size), how squashed (wider and shorter; less than 0 stretched), its face,
    its left and right arms' turn from hanging down (degrees) and its bell's swing."""
    if t < HOPS[0][0]:
        return None
    x, lift, squash, swing = HOPS[-1][3], 0.0, 0.0, 0.0
    arms = [16.0, -16.0]
    landed = None
    for start, land, x0, x1, high in HOPS:
        if start <= t < land:
            k = (t - start) / (land - start)
            x = x0 + (x1 - x0) * k
            lift = high * 4 * k * (1 - k)
            squash = -0.13 * math.sin(math.pi * k)
            fling = 36 + 46 * math.sin(math.pi * k)
            arms = [fling, -fling]
            swing = -24 * math.cos(math.pi * k)
            break
        if t >= land:
            landed = land
    face = "happy" if 3.38 <= t < 4.75 else "open"
    for start, land, high in JUMPS:
        if start <= t < land:
            k = (t - start) / (land - start)
            lift = high * 4 * k * (1 - k)
            squash = -0.11 * math.sin(math.pi * k)
            swing = -20 * math.cos(math.pi * k)
        if t >= land:
            landed = land
    if lift == 0 and landed is not None:
        squash += 0.17 * spring(t - landed, 2.4, 7.0)
        swing = 26 * spring(t - landed, 1.9, 3.5)
    squash += 0.012 * math.sin(t * 6.0)
    # It waves with its right arm, and throws both up for joy.
    wave = ease_out(win(t, WAVE[0], WAVE[0] + 0.18)) * (1 - ease_in_out(win(t, WAVE[1] - 0.15, WAVE[1])))
    if wave > 0:
        arms[1] += (-150 + 22 * math.sin(2 * math.pi * 2.6 * (t - WAVE[0])) - arms[1]) * wave
    joy = ease_out(win(t, 3.38, 3.5)) * (1 - ease_in_out(win(t, 4.4, 4.6)))
    if joy > 0:
        cheer = 10 * math.sin(2 * math.pi * 3.0 * t)
        arms = [arms[0] + (150 + cheer - arms[0]) * joy, arms[1] + (-150 + cheer - arms[1]) * joy]
    return x, lift, squash, face, arms[0], arms[1], swing


def _paint_lamb(p: QPainter, t: float, picture_of: Callable, u: float, s: float, ground: float) -> None:
    """The lamb hopping in, waving and jumping for joy, its shadow on the grass under it."""
    pose = _lamb_pose(t)
    if pose is None:
        return
    x, lift, squash, face, left, right, swing = pose
    at = QPointF(x * u, ground - lift * u)
    _shadow(p, QPointF(at.x(), ground), 0.26 * s, 0.05 * s, 1 / (1 + lift / 50))
    body, box = picture_of(("lamb", face))
    arm, arm_box = picture_of("arm")
    bell, bell_box = picture_of("bell")
    p.save()
    p.translate(at)
    p.scale(1 + squash, 1 - squash)
    p.drawImage(box, body)
    for side, turn in ((-1, left), (1, right)):
        p.save()
        p.translate(side * 0.15 * s, -0.43 * s)
        p.rotate(turn)
        p.drawImage(arm_box, arm)
        p.restore()
    p.translate(0, -0.415 * s)
    p.rotate(swing)
    p.drawImage(bell_box, bell)
    p.restore()


def _shadow(p: QPainter, at: QPointF, rx: float, ry: float, strength: float) -> None:
    """A soft shadow on the grass."""
    p.save()
    p.translate(at)
    p.scale(1, ry / rx)
    shade = QRadialGradient(QPointF(0, 0), rx)
    shade.setColorAt(0, col("#1d4a14", 0.45 * strength))
    shade.setColorAt(0.6, col("#1d4a14", 0.22 * strength))
    shade.setColorAt(1, col("#1d4a14", 0))
    p.setPen(Qt.NoPen)
    p.setBrush(shade)
    p.drawEllipse(QPointF(0, 0), rx, rx)
    p.restore()


# The wolf and the pan.


def _paint_wolf(
    p: QPainter, t: float, picture_of: Callable, u: float, s: float, rest: float, width: float, ground: float, bush_at: QPointF
) -> None:
    """The wolf tiptoeing in on the right and rubbing his paws, then hit, half behind the bush, which
    is always there."""
    if SNEAK[0] <= t < FLIGHT[0]:
        k = win(t, *SNEAK)
        x = rest + (width + 90 * u - rest) * (1 - k) ** 1.2
        # Tiptoe: up on each step, leaning into it, until he is there.
        walking = 1 - ease_in(win(t, SNEAK[1] - 0.15, SNEAK[1] + 0.05))
        steps = (t - SNEAK[0]) / 0.21
        bob = -abs(math.sin(math.pi * steps)) * 5 * u * walking
        lean = 3.5 * math.sin(math.pi * steps) * walking
        _shadow(p, QPointF(x, ground), 0.24 * s, 0.045 * s, 1.0)
        p.save()
        p.translate(x, ground + bob)
        p.rotate(lean)
        if t < PAN[1]:
            image, box = picture_of("wolf")
            p.drawImage(box, image)
            paw, paw_box = picture_of("paw")
            rub = math.sin(t * 26) * 0.014 * s * win(t, SNEAK[1] - 0.2, SNEAK[1])
            for dx, dy in ((0.03 * s + rub, -0.008 * s), (-rub, 0.004 * s)):
                p.drawImage(paw_box.translated(-0.105 * s + dx, -0.47 * s + dy), paw)
        else:
            # Hit: squashed flat for a moment.
            flat = 0.22 * (1 - ease_out(win(t, PAN[1], FLIGHT[0])))
            p.scale(1 + flat, 1 - flat)
            image, box = picture_of("hit")
            p.drawImage(box, image)
        p.restore()
    image, box = picture_of("bush")
    p.drawImage(box.translated(bush_at), image)


def _bezier(points: tuple[QPointF, ...], k: float) -> QPointF:
    a, b, c, d = points
    m = 1 - k
    return a * m**3 + b * 3 * m * m * k + c * 3 * m * k * k + d * k**3


def _flight(flight: tuple[QPointF, ...], t: float) -> tuple[QPointF, float]:
    """Where the wolf is as he flies off, and how far along (0..1)."""
    k = win(t, *FLIGHT)
    return _bezier(flight, 1 - (1 - k) ** 1.6), k


def _paint_gag(
    p: QPainter, t: float, picture_of: Callable, u: float, s: float, hit: QPointF, flight: tuple[QPointF, ...], width: float, height: float
) -> None:
    """The pan flying in and back out, 咣!, the wolf spinning up and away with his words trailing him,
    and the star he becomes."""
    if PAN[0] <= t < PAN[1] + 0.4:
        pan = picture_of("pan")
        if t < PAN[1]:
            k = ease_in(win(t, *PAN))
            start = QPointF(width + 90 * u, height * 0.42)
            bend = QPointF(width - 10 * u, height * 0.55)
            at = start * (1 - k) ** 2 + bend * 2 * (1 - k) * k + hit * k * k
            angle, size, alpha = 160 - 520 * k, 1.0, 1.0
        else:
            k = ease_out(win(t, PAN[1], PAN[1] + 0.4))
            at = hit + (QPointF(width + 70 * u, height * 0.5) - hit) * k
            angle, size, alpha = -360 - 400 * k, 1.0, 1 - k
        # A soft light behind it, so the black pan shows on the dark game.
        soft_dot(p, at.x(), at.y(), 60 * u, "#ffffff", 0.3 * alpha)
        _place(p, pan, at, angle, size, alpha)
    if FLIGHT[0] <= t < FLIGHT[1] + 0.05:
        at, k = _flight(flight, t)
        image, box = picture_of("hit")
        fade = 1 - win(t, FLIGHT[1] - 0.12, FLIGHT[1] + 0.02)
        p.save()
        p.setOpacity(p.opacity() * fade)
        p.translate(at)
        p.rotate(-760 * ease_out(k))
        size = 1 - 0.8 * k
        p.scale(size, size)
        p.drawImage(box.translated(0, 0.5 * s), image)
        p.restore()
    if PAN[1] <= t < PAN[1] + 0.4:
        k = t - PAN[1]
        middle = hit + QPointF(32 * u, -6 * u)
        soft_dot(p, middle.x(), middle.y(), 90 * u * (0.6 + k), "#fff8d0", 0.8 * (1 - win(k, 0.0, 0.18)))
        pop = ease_back(win(k, 0.0, 0.1), 2.4) * (1 - ease_in(win(k, 0.26, 0.4)))
        # Lines fly out of the blow.
        p.setPen(QPen(col("#ffffff", 0.9 * (1 - win(k, 0.1, 0.3))), 3.2 * u, Qt.SolidLine, Qt.RoundCap))
        for index in range(7):
            # Out to the right and down, away from the names.
            angle = math.radians(-80 + index * 30)
            inner, outer = 58 * u + 90 * u * k, 74 * u + 130 * u * k
            p.drawLine(middle + QPointF(math.cos(angle), math.sin(angle)) * inner, middle + QPointF(math.cos(angle), math.sin(angle)) * outer)
        _place(p, picture_of("burst"), middle, 6 * math.sin(k * 40) * (1 - k * 2.5), pop, 1.0)
    star_k = win(t, FLIGHT[1] - 0.03, FLIGHT[1] + 0.15)
    end = flight[-1]
    if t >= BUBBLE_AT:
        trail, _k = _flight(flight, t - 0.08)
        image, box, tip = picture_of("bubble")
        pop = ease_back(win(t, BUBBLE_AT, BUBBLE_AT + 0.2), 2.0)
        p.save()
        p.translate(trail + QPointF(-34 * u, 6 * u))
        p.scale(pop, pop)
        p.translate(-tip)
        p.drawImage(box, image)
        p.restore()
    if star_k > 0:
        flash = 1 - win(t, FLIGHT[1], FLIGHT[1] + 0.3)
        soft_dot(p, end.x(), end.y(), 70 * u, "#fff6c8", 0.9 * flash)
        rect, light = picture_of("star-glow")
        twinkle = 0.5 + 0.5 * math.sin((t - FLIGHT[1]) * 9)
        p.save()
        p.setOpacity(p.opacity() * (0.55 + 0.45 * twinkle) * ease_out(star_k))
        p.drawImage(rect.translated(end), light)
        p.restore()
        size = ease_back(star_k, 2.6) * (1 + 0.1 * math.sin((t - FLIGHT[1]) * 9))
        _place(p, picture_of("star"), end, 12 * math.sin((t - FLIGHT[1]) * 3), size, 1.0)
        star(p, end.x() + 13 * u, end.y() - 14 * u, 13 * u * twinkle, "#ffffff", 0.9 * twinkle, 0.12)
        star(p, end.x() - 15 * u, end.y() + 9 * u, 9 * u * (1 - twinkle), "#ffffff", 0.8 * (1 - twinkle), 0.12)
        if flash > 0:
            for index in range(6):
                angle = math.radians(index * 60 + 30)
                reach = (18 + 46 * (1 - flash)) * u
                star(p, end.x() + math.cos(angle) * reach, end.y() + math.sin(angle) * reach, 6 * u * flash, "#fff1a8", flash, 0.15)


def _place(p: QPainter, picture: tuple[QImage, QRectF], at: QPointF, angle: float, size: float, alpha: float) -> None:
    """A picture made about its own middle put at at, turned by angle degrees and sized by size."""
    if size <= 0.01 or alpha <= 0.01:
        return
    image, box = picture
    p.save()
    p.setOpacity(p.opacity() * alpha)
    p.translate(at)
    p.rotate(angle)
    p.scale(size, size)
    p.drawImage(box, image)
    p.restore()


# Pictures worked out per pixel.


class _Art:
    """A picture shaded per pixel, built up shape by shape in box (points) at scale pixels to the point:
    each shape its color, rounded up from its edges like a soft pillow or piled up as wool puffs, a later
    shape over an earlier one; then all of it lit from the upper left, its creases shaded, a rim of
    light on its lit edges and a little sky on the others, a gloss where it shines, a grain, and the
    outlines of the shapes that have them in ink, a later shape hiding an earlier one's."""

    def __init__(self, box: QRectF, scale: float, *, ink: str = INK, cool: str = "#46508a", seed: int = 1) -> None:
        self.box, self.scale, self.ink_color, self.cool, self.seed = box, scale, ink, cool, seed
        self.w, self.h = max(1, math.ceil(box.width() * scale)), max(1, math.ceil(box.height() * scale))
        self.sx, self.sy = self.w / box.width(), self.h / box.height()
        shape = (self.h, self.w)
        self.color = np.zeros((*shape, 3), dtype=np.float32)
        self.alpha = np.zeros(shape, dtype=np.float32)
        self.bump = np.zeros(shape, dtype=np.float32)
        self.gloss = np.zeros(shape, dtype=np.float32)
        self.grain = np.zeros(shape, dtype=np.float32)
        self.ink = np.zeros(shape, dtype=np.float32)

    def place(self, q: QPainter) -> None:
        q.scale(self.sx, self.sy)
        q.translate(-self.box.left(), -self.box.top())

    def shape(self, path: QPainterPath) -> np.ndarray:
        def draw(q: QPainter) -> None:
            self.place(q)
            q.fillPath(path, QColor("#ffffff"))

        return mask(self.w, self.h, draw)

    def fill(
        self, path: QPainterPath, tint: str, soft: float, swell: float = 1.0, rest: float = 0.0, gloss: float = 0.0, grain: float = 0.05, line: float = 0.0
    ) -> None:
        """A shape in tint, rounded up from its edges over soft points to swell times that high (less
        than 0 dished in), resting on what is under it by rest."""
        m = self.shape(path)
        px = max(1.0, soft * self.scale)
        height = np.sqrt(np.clip(2 * blur(m, px) - 1, 0, 1)) * px * swell
        if rest:
            height = height + blur(self.bump, px) * rest
        self._lay(m, tint, height, gloss, grain)
        if line:
            self.outline(path, line)

    def puffs(
        self,
        puffs: list[tuple[float, float, float]],
        tint: str,
        flat: float = 0.8,
        gloss: float = 0.0,
        grain: float = 0.05,
        line: float = 0.0,
        curl: float = 0.3,
        clip: QPainterPath | None = None,
    ) -> None:
        """Round puffs (x, y, r) piled up into one soft heap, each a ball flat times as deep as it is
        wide, with little curls all over them like wool's: where two meet, a crease."""
        m = np.zeros((self.h, self.w), dtype=np.float32)
        height = np.zeros((self.h, self.w), dtype=np.float32)
        xs = np.arange(self.w, dtype=np.float32) + 0.5
        ys = np.arange(self.h, dtype=np.float32) + 0.5
        outline = QPainterPath()
        outline.setFillRule(Qt.WindingFill)
        for x, y, r in puffs:
            cx, cy, rp = (x - self.box.left()) * self.sx, (y - self.box.top()) * self.sy, r * self.sx
            x0, x1 = max(0, int(cx - rp - 2)), min(self.w, int(cx + rp + 3))
            y0, y1 = max(0, int(cy - rp - 2)), min(self.h, int(cy + rp + 3))
            outline.addEllipse(QPointF(x, y), r, r)
            if x0 >= x1 or y0 >= y1:
                continue
            d = np.hypot(xs[None, x0:x1] - cx, ys[y0:y1, None] - cy)
            disc = np.clip(rp - d + 0.5, 0, 1)
            ball = np.sqrt(np.clip(1 - (d / rp) ** 2, 0, 1)) * rp * flat
            m[y0:y1, x0:x1] = np.maximum(m[y0:y1, x0:x1], disc)
            height[y0:y1, x0:x1] = np.maximum(height[y0:y1, x0:x1], ball)
        if clip is not None:
            m *= self.shape(clip)
            outline = outline.simplified().intersected(clip)
        if curl:
            height += (noise(self.w, self.h, 1.6 * self.scale, 2, self.seed) - 0.5) * curl * 4 * self.scale * m
        self._lay(m, tint, height, gloss, grain)
        if line:
            self.outline(outline.simplified(), line)

    def blush(self, path: QPainterPath, tint: str, soft: float, amount: float) -> None:
        """A soft flush of tint over what is there, as on a cheek."""
        k = (blur(self.shape(path), max(1.0, soft * self.scale)) * amount)[..., None]
        self.color += (rgb(tint) - self.color) * k

    def outline(self, path: QPainterPath, width: float) -> None:
        stroker = QPainterPathStroker()
        stroker.setWidth(width)
        stroker.setCapStyle(Qt.RoundCap)
        stroker.setJoinStyle(Qt.RoundJoin)
        self.ink = np.maximum(self.ink, self.shape(stroker.createStroke(path)))

    def _lay(self, m: np.ndarray, tint: str, height: np.ndarray, gloss: float, grain: float) -> None:
        self.color += (rgb(tint) - self.color) * m[..., None]
        self.alpha = np.maximum(self.alpha, m)
        self.bump += (height - self.bump) * m
        self.gloss += (gloss - self.gloss) * m
        self.grain += (grain - self.grain) * m
        self.ink *= 1 - m

    def render(self, after: Callable[[QPainter], None] | None = None, ao: float = 0.35, rim: float = 0.3) -> QImage:
        gy, gx = np.gradient(self.bump)
        nz = 1 / np.sqrt(1 + gx * gx + gy * gy)
        nx, ny = -gx * nz, -gy * nz
        diffuse = np.clip(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0, 1)
        # Flat parts keep their own color; what faces the light is lighter, what turns away darker.
        shade = 1 + 0.85 * (diffuse - LIGHT[2])
        reach = max(1.5, 2.5 * self.scale)
        crease = np.clip((blur(self.bump, reach * 2) - self.bump) / (reach * 1.5), 0, 1)
        shade = np.clip(shade * (1 - ao * crease), 0.2, 1.3)
        side = np.hypot(nx, ny)
        flat_light = np.hypot(LIGHT[0], LIGHT[1])
        toward = (nx * LIGHT[0] + ny * LIGHT[1]) / np.maximum(side * flat_light, 1e-4)
        edge_light = side**1.5 * np.clip(toward, 0, 1) * rim
        sky = side**2.5 * np.clip(-toward, 0, 1) * 0.2
        sheen = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1) ** 36 * self.gloss
        texture = 1 + self.grain * (noise(self.w, self.h, 2.0 * self.scale, 2, self.seed + 7) - 0.5) * 2
        lit = (
            self.color * (shade * texture)[..., None]
            + (np.clip(1 - shade, 0, 1) * 0.3)[..., None] * rgb(self.cool)
            + edge_light[..., None] * rgb("#fff4d6")
            + sky[..., None] * rgb(SKY)
            + sheen[..., None]
        )
        lit = lit * (1 - self.ink[..., None]) + rgb(self.ink_color) * self.ink[..., None]
        image = picture(lit, np.maximum(self.alpha, self.ink)).convertToFormat(QImage.Format_ARGB32_Premultiplied)
        if after is not None:
            q = QPainter(image)
            q.setRenderHint(QPainter.Antialiasing)
            self.place(q)
            after(q)
            q.end()
        image.setDevicePixelRatio(self.sx)
        return image


def _ellipse(x: float, y: float, rx: float, ry: float, angle: float = 0.0) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QPointF(0, 0), rx, ry)
    return QTransform().translate(x, y).rotate(angle).map(path)


def _limb(points: list[tuple[float, float]], width: float) -> QPainterPath:
    """A rounded limb through points (two, or three for a bend), width wide."""
    line = QPainterPath(QPointF(*points[0]))
    if len(points) == 3:
        line.quadTo(QPointF(*points[1]), QPointF(*points[2]))
    else:
        line.lineTo(QPointF(*points[1]))
    stroker = QPainterPathStroker()
    stroker.setWidth(width)
    stroker.setCapStyle(Qt.RoundCap)
    stroker.setJoinStyle(Qt.RoundJoin)
    return stroker.createStroke(line).simplified()


def _polygon(points: list[tuple[float, float]], round_by: float = 0.0) -> QPainterPath:
    """A closed shape through points; its corners rounded off round_by of the way along each side."""
    if not round_by:
        path = QPainterPath(QPointF(*points[0]))
        for point in points[1:]:
            path.lineTo(QPointF(*point))
        path.closeSubpath()
        return path
    corners = [QPointF(*point) for point in points]
    n = len(corners)

    def toward(a: QPointF, b: QPointF) -> QPointF:
        return a + (b - a) * round_by

    path = QPainterPath(toward(corners[0], corners[1]))
    for i in range(1, n + 1):
        corner, after = corners[i % n], corners[(i + 1) % n]
        path.lineTo(toward(corner, corners[i - 1]))
        path.quadTo(corner, toward(corner, after))
    path.closeSubpath()
    return path


def _ring_of(x: float, y: float, rx: float, ry: float, count: int, r: float, rnd: random.Random) -> list[tuple[float, float, float]]:
    """Wool puffs round an ellipse, each about r, and one filling its middle."""
    out = []
    start = rnd.random()
    for i in range(count):
        a = 2 * math.pi * (i / count + start)
        out.append((x + rx * math.cos(a), y + ry * math.sin(a), r * rnd.uniform(0.86, 1.14)))
    out.append((x, y, min(rx, ry) + r * 0.6))
    return out


def _font(families: list[str], size: float, weight: QFont.Weight = QFont.Weight.Bold) -> QFont:
    font = QFont()
    font.setFamilies(families)
    font.setPixelSize(max(1, round(size)))
    font.setWeight(weight)
    return font


def _text_path(text: str, font: QFont, middle: QPointF) -> QPainterPath:
    path = QPainterPath()
    path.addText(QPointF(0, 0), font, text)
    box = path.boundingRect()
    return QTransform().translate(middle.x() - box.center().x(), middle.y() - box.center().y()).map(path)


def _lamb(s: float, scale: float, face: str) -> tuple[QImage, QRectF]:
    """The lamb, s tall, standing on (0, 0) and facing us, without its arms and bell, which move: round
    cloud-puff wool on its body and all round its head, a cream face with big shining eyes, floppy ears,
    little curled horns, a red collar; face "open" or "happy" (eyes shut in smiles, mouth wide)."""
    box = QRectF(-0.44 * s, -1.04 * s, 0.88 * s, 1.08 * s)
    art = _Art(box, scale, seed=31)
    rnd = random.Random(12)
    line, thin = max(0.8, 0.022 * s), max(0.6, 0.014 * s)
    for side in (-1, 1):
        art.fill(_limb([(side * 0.075 * s, -0.28 * s), (side * 0.082 * s, -0.06 * s)], 0.095 * s), CREAM, 0.04 * s, line=line)
        art.fill(_ellipse(side * 0.085 * s, -0.04 * s, 0.062 * s, 0.04 * s), HOOF, 0.025 * s, gloss=0.3, line=line)
    art.puffs(_ring_of(0, -0.32 * s, 0.15 * s, 0.1 * s, 10, 0.072 * s, rnd), WOOL, line=line)
    art.fill(_limb([(-0.125 * s, -0.455 * s), (0, -0.405 * s), (0.125 * s, -0.455 * s)], 0.05 * s), COLLAR, 0.02 * s, gloss=0.35, line=thin)
    for side in (-1, 1):
        ear = _ellipse(side * 0.27 * s, -0.6 * s, 0.095 * s, 0.045 * s, side * 14)
        art.fill(ear, CREAM, 0.03 * s, line=line)
        art.fill(_ellipse(side * 0.285 * s, -0.598 * s, 0.06 * s, 0.022 * s, side * 14), PINK, 0.015 * s, rest=0.8)
    head = _ring_of(0, -0.69 * s, 0.235 * s, 0.195 * s, 13, 0.085 * s, rnd)
    head += [(0.03 * s, -0.93 * s, 0.072 * s), (-0.05 * s, -0.94 * s, 0.06 * s)]
    art.puffs(head, WOOL, line=line)
    for side in (-1, 1):
        curl = QPainterPath(QPointF(side * 0.11 * s, -0.87 * s))
        curl.cubicTo(QPointF(side * 0.12 * s, -0.94 * s), QPointF(side * 0.2 * s, -0.96 * s), QPointF(side * 0.215 * s, -0.91 * s))
        curl.quadTo(QPointF(side * 0.22 * s, -0.865 * s), QPointF(side * 0.18 * s, -0.875 * s))
        stroker = QPainterPathStroker()
        stroker.setWidth(0.046 * s)
        stroker.setCapStyle(Qt.RoundCap)
        horn = stroker.createStroke(curl).simplified()
        art.fill(horn, HORN, 0.022 * s, gloss=0.25, grain=0.08, line=thin)
    cheeks = QPainterPath(QPointF(-0.2 * s, -0.6 * s))
    cheeks.cubicTo(QPointF(-0.21 * s, -0.81 * s), QPointF(0.21 * s, -0.81 * s), QPointF(0.2 * s, -0.6 * s))
    cheeks.cubicTo(QPointF(0.2 * s, -0.42 * s), QPointF(-0.2 * s, -0.42 * s), QPointF(-0.2 * s, -0.6 * s))
    art.fill(cheeks, CREAM, 0.045 * s, swell=0.5, rest=0.85, line=thin)
    blush = QPainterPath()
    for side in (-1, 1):
        blush.addEllipse(QPointF(side * 0.135 * s, -0.535 * s), 0.04 * s, 0.022 * s)
    art.blush(blush, PINK, 0.02 * s, 0.75)

    def features(q: QPainter) -> None:
        ink = col(INK)
        for side in (-1, 1):
            eye = QPointF(side * 0.08 * s, -0.63 * s)
            if face == "happy":
                smile = QPainterPath(QPointF(eye.x() - 0.048 * s, eye.y() + 0.012 * s))
                smile.quadTo(QPointF(eye.x(), eye.y() - 0.055 * s), QPointF(eye.x() + 0.048 * s, eye.y() + 0.012 * s))
                q.strokePath(smile, QPen(ink, 0.02 * s, Qt.SolidLine, Qt.RoundCap))
                continue
            white = QPainterPath()
            white.addEllipse(eye, 0.064 * s, 0.08 * s)
            q.fillPath(white, QColor("#ffffff"))
            iris = QRadialGradient(QPointF(eye.x(), eye.y() + 0.03 * s), 0.06 * s)
            iris.setColorAt(0, QColor("#7a4a2e"))
            iris.setColorAt(0.6, QColor("#3a2318"))
            iris.setColorAt(1, QColor("#1a110d"))
            q.setPen(Qt.NoPen)
            q.setBrush(iris)
            q.drawEllipse(QPointF(eye.x() - side * 0.008 * s, eye.y() + 0.01 * s), 0.05 * s, 0.064 * s)
            q.setBrush(QColor("#140c09"))
            q.drawEllipse(QPointF(eye.x() - side * 0.008 * s, eye.y() + 0.012 * s), 0.028 * s, 0.036 * s)
            q.setBrush(QColor("#ffffff"))
            q.drawEllipse(QPointF(eye.x() - 0.02 * s, eye.y() - 0.022 * s), 0.021 * s, 0.021 * s)
            q.drawEllipse(QPointF(eye.x() + 0.017 * s, eye.y() + 0.03 * s), 0.009 * s, 0.009 * s)
            q.strokePath(white, QPen(ink, 0.011 * s))
            lash = QPainterPath(QPointF(eye.x() + side * 0.045 * s, eye.y() - 0.058 * s))
            lash.quadTo(QPointF(eye.x() + side * 0.068 * s, eye.y() - 0.072 * s), QPointF(eye.x() + side * 0.08 * s, eye.y() - 0.088 * s))
            q.strokePath(lash, QPen(ink, 0.012 * s, Qt.SolidLine, Qt.RoundCap))
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#d08a7c"))
        q.drawEllipse(QPointF(0, -0.567 * s), 0.014 * s, 0.009 * s)
        wide, deep = (0.068, 0.445) if face == "happy" else (0.045, 0.478)
        mouth = QPainterPath(QPointF(-wide * s, -0.535 * s))
        mouth.quadTo(QPointF(0, -0.525 * s), QPointF(wide * s, -0.535 * s))
        mouth.quadTo(QPointF(0, -deep * s), QPointF(-wide * s, -0.535 * s))
        q.fillPath(mouth, QColor("#a8333d"))
        q.save()
        q.setClipPath(mouth)
        q.setBrush(QColor(PINK))
        q.drawEllipse(QPointF(0, (-0.5 if face == "open" else -0.47) * s), wide * 0.6 * s, 0.022 * s)
        q.restore()
        q.strokePath(mouth, QPen(ink, 0.011 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

    return art.render(features, ao=0.4, rim=0.35), box


def _arm(s: float, scale: float) -> tuple[QImage, QRectF]:
    """One of the lamb's arms, hanging from its shoulder at (0, 0): cream, a little dark hoof at its end."""
    box = QRectF(-0.07 * s, -0.06 * s, 0.14 * s, 0.28 * s)
    art = _Art(box, scale, seed=33)
    line = max(0.8, 0.02 * s)
    art.fill(_limb([(0, 0), (0, 0.15 * s)], 0.072 * s), CREAM, 0.03 * s, line=line)
    art.fill(_ellipse(0, 0.17 * s, 0.045 * s, 0.035 * s), HOOF, 0.02 * s, gloss=0.3, line=line)
    return art.render(), box


def _bell_path(r: float) -> tuple[QPainterPath, QPainterPath, QPainterPath, QPainterPath]:
    """A bell r wide hanging from (0, 0): its loop, its body, its rim and its clapper."""
    stroker = QPainterPathStroker()
    stroker.setWidth(0.16 * r)
    ring = QPainterPath()
    ring.addEllipse(QPointF(0, 0.12 * r), 0.2 * r, 0.2 * r)
    loop = stroker.createStroke(ring).simplified()
    body = QPainterPath(QPointF(-0.86 * r, 1.45 * r))
    body.cubicTo(QPointF(-0.78 * r, 0.9 * r), QPointF(-0.68 * r, 0.3 * r), QPointF(0, 0.3 * r))
    body.cubicTo(QPointF(0.68 * r, 0.3 * r), QPointF(0.78 * r, 0.9 * r), QPointF(0.86 * r, 1.45 * r))
    body.quadTo(QPointF(0, 1.62 * r), QPointF(-0.86 * r, 1.45 * r))
    rim = _ellipse(0, 1.47 * r, 0.9 * r, 0.16 * r)
    clapper = _ellipse(0, 1.66 * r, 0.17 * r, 0.15 * r)
    return loop, body, rim, clapper


def _bell(r: float, scale: float) -> tuple[QImage, QRectF]:
    """A golden bell r wide, polished, hanging from its loop at (0, 0)."""
    box = QRectF(-1.25 * r, -0.25 * r, 2.5 * r, 2.3 * r)
    art = _Art(box, scale, cool="#8a4a10", seed=35)
    loop, body, rim, clapper = _bell_path(r)
    line = max(0.6, 0.11 * r)
    art.fill(loop, "#d9a02a", 0.08 * r, gloss=0.7, line=line * 0.8)
    art.fill(clapper, "#c48a1c", 0.12 * r, gloss=0.7, line=line)
    art.fill(body, BELL, 0.45 * r, gloss=0.95, grain=0.02, line=line)
    art.fill(rim, "#e8ad2c", 0.1 * r, gloss=0.9, rest=0.4, line=line)

    def slit(q: QPainter) -> None:
        q.setPen(QPen(col("#8a5a12", 0.8), max(0.5, 0.08 * r), Qt.SolidLine, Qt.RoundCap))
        q.drawLine(QPointF(0, 0.95 * r), QPointF(0, 1.3 * r))

    return art.render(slit, ao=0.2, rim=0.4), box


def _wolf(s: float, scale: float, pose: str) -> tuple[QImage, QRectF]:
    """The wolf, s tall, on (0, 0) and facing left: grey, a light belly and muzzle, a bushy tail, pointed
    ears through a yellow hat with a darker patch stitched on, a scar on his cheek. Pose "sneak": on
    tiptoe, hunched, sly half-shut eyes and a toothy grin, his arm out to his paws (drawn apart, to rub);
    "hit": arms and legs flung out, hat knocked askew, eyes spinning and mouth an O."""
    hit = pose == "hit"
    box = QRectF(-0.48 * s, -1.12 * s, 0.98 * s, 1.18 * s)
    art = _Art(box, scale, cool="#3d4670", seed=41)
    rnd = random.Random(19)
    line, thin = max(0.8, 0.02 * s), max(0.6, 0.012 * s)
    bend = QPointF(0.1, -0.34), QPointF(0.36, -0.36), QPointF(0.4, -0.6), QPointF(0.28, -0.72)
    tail, tip = [], []
    for i in range(11):
        k = i / 10
        at = _bezier(bend, k)
        r = (0.045 + 0.06 * math.sin(math.pi * min(1, k * 1.1))) * rnd.uniform(0.9, 1.1)
        (tip if k > 0.75 else tail).append((at.x() * s, at.y() * s, r * s))
    art.puffs(tail, GREY, flat=0.7, grain=0.1, line=line, curl=0.4)
    art.puffs(tip, "#b4b8c1", flat=0.7, grain=0.1, line=line, curl=0.4)
    if hit:
        legs = (([(0.06, -0.3), (0.14, -0.18), (0.18, -0.07)], (0.2, -0.05, 25), GREY_DEEP), ([(-0.03, -0.3), (-0.12, -0.22), (-0.18, -0.1)], (-0.21, -0.08, -40), GREY))
    else:
        legs = (([(0.07, -0.3), (0.13, -0.17), (0.08, -0.06)], (0.055, -0.03, 32), GREY_DEEP), ([(-0.02, -0.3), (-0.09, -0.16), (-0.05, -0.06)], (-0.075, -0.028, 30), GREY))
    for points, (fx, fy, angle), tint in legs:
        art.fill(_limb([(x * s, y * s) for x, y in points], 0.072 * s), tint, 0.03 * s, line=line)
        art.fill(_ellipse(fx * s, fy * s, 0.06 * s, 0.03 * s, angle), "#4a4e58", 0.02 * s, line=line)
    art.fill(_ellipse(0.02 * s, -0.43 * s, 0.14 * s, 0.17 * s, -12), GREY, 0.08 * s, grain=0.08, line=line)
    art.fill(_ellipse(-0.035 * s, -0.41 * s, 0.085 * s, 0.12 * s, -12), GREY_LIGHT, 0.05 * s, rest=0.6, grain=0.08)
    arms = (
        [[(-0.02, -0.55), (-0.13, -0.68), (-0.17, -0.83)], [(0.06, -0.54), (0.18, -0.6), (0.24, -0.75)]]
        if hit
        else [[(0.02, -0.55), (0.07, -0.44), (-0.09, -0.47)]]
    )
    for points in arms:
        art.fill(_limb([(x * s, y * s) for x, y in points], 0.064 * s), GREY, 0.03 * s, grain=0.08, line=line)
        if hit:
            x, y = points[-1]
            art.fill(_ellipse(x * s, y * s, 0.045 * s, 0.04 * s), GREY, 0.025 * s, line=line)
    # His head, with the hat and its ears knocked askew when he is hit.
    tilt = QTransform().translate(0, -0.86 * s).rotate(24).translate(0.03 * s, -0.9 * s) if hit else QTransform()
    for points in (((-0.11, -0.84), (-0.085, -1.01), (-0.01, -0.86)), ((0.05, -0.85), (0.13, -1.0), (0.14, -0.81))):
        ear = tilt.map(_polygon([(x * s, y * s) for x, y in points], 0.25))
        art.fill(ear, GREY, 0.025 * s, line=line)
        inner = [(x * s, y * s) for x, y in points]
        middle = QPointF(sum(x for x, _y in inner) / 3, sum(y for _x, y in inner) / 3)
        art.fill(tilt.map(QTransform().translate(middle.x(), middle.y()).scale(0.5, 0.5).translate(-middle.x(), -middle.y()).map(_polygon(inner, 0.25))), "#b79d9f", 0.015 * s, rest=0.8)
    head = _ellipse(-0.02 * s, -0.7 * s, 0.17 * s, 0.15 * s)
    tufts = [(0.1, -0.78), (0.215, -0.69), (0.13, -0.67), (0.2, -0.58), (0.11, -0.6), (0.13, -0.51), (0.03, -0.58)]
    head = head.united(_polygon([(x * s, y * s) for x, y in tufts], 0.12)).simplified()
    art.fill(head, GREY, 0.09 * s, grain=0.08, line=line)
    snout = _ellipse(-0.215 * s, -0.66 * s, 0.145 * s, 0.068 * s, -6)
    art.fill(snout, GREY, 0.045 * s, rest=0.5, grain=0.06, line=line)
    muzzle = _ellipse(-0.2 * s, -0.625 * s, 0.135 * s, 0.04 * s, -6).intersected(snout)
    art.fill(muzzle, GREY_LIGHT, 0.03 * s, rest=0.85, grain=0.05)
    art.fill(_ellipse(-0.355 * s, -0.692 * s, 0.035 * s, 0.028 * s), "#232327", 0.02 * s, gloss=0.9, rest=0.4, line=thin)
    crown = _ellipse(-0.01 * s, -0.86 * s, 0.16 * s, 0.085 * s, -8).united(_ellipse(-0.015 * s, -0.835 * s, 0.17 * s, 0.035 * s, -6))
    brim = _ellipse(-0.15 * s, -0.825 * s, 0.11 * s, 0.03 * s, -10)
    art.fill(tilt.map(brim), "#e2b22a", 0.02 * s, gloss=0.15, line=line)
    art.fill(tilt.map(crown), HAT, 0.07 * s, gloss=0.15, grain=0.1, line=line)
    patch = QTransform().translate(0.035 * s, -0.885 * s).rotate(14).map(_polygon([(-0.04 * s, -0.03 * s), (0.04 * s, -0.032 * s), (0.042 * s, 0.03 * s), (-0.038 * s, 0.032 * s)], 0.2))
    art.fill(tilt.map(patch), PATCH, 0.02 * s, rest=0.9, grain=0.12, line=thin)

    def features(q: QPainter) -> None:
        ink = col(INK)
        q.save()
        q.setTransform(tilt, True)
        stitch = QPen(col("#7a3f10"), max(0.4, 0.007 * s), Qt.SolidLine, Qt.RoundCap)
        q.setPen(stitch)
        corners = [QPointF(-0.04 * s, -0.03 * s), QPointF(0.04 * s, -0.032 * s), QPointF(0.042 * s, 0.03 * s), QPointF(-0.038 * s, 0.032 * s)]
        place = QTransform().translate(0.035 * s, -0.885 * s).rotate(14)
        for a, b in zip(corners, corners[1:] + corners[:1], strict=True):
            for k in (0.25, 0.5, 0.75):
                at = place.map(a + (b - a) * k)
                q.drawLine(at + QPointF(-0.008 * s, -0.008 * s), at + QPointF(0.008 * s, 0.008 * s))
        band = QPainterPath(QPointF(-0.17 * s, -0.83 * s))
        band.quadTo(QPointF(-0.01 * s, -0.8 * s), QPointF(0.15 * s, -0.86 * s))
        q.strokePath(band, QPen(col("#c48f1e"), max(0.5, 0.012 * s), Qt.SolidLine, Qt.RoundCap))
        q.restore()
        eyes = ((QPointF(-0.1 * s, -0.745 * s), 0.036 * s, 0.043 * s), (QPointF(-0.178 * s, -0.752 * s), 0.03 * s, 0.037 * s))
        for at, rx, ry in eyes:
            white = QPainterPath()
            white.addEllipse(at, rx, ry)
            q.fillPath(white, QColor("#fffbe6"))
            if hit:
                spiral = QPainterPath(at)
                for k in range(1, 40):
                    a = k * 0.5
                    reach = rx * 0.95 * k / 40
                    spiral.lineTo(at + QPointF(math.cos(a) * reach, math.sin(a) * reach * ry / rx))
                q.strokePath(spiral, QPen(ink, max(0.4, 0.008 * s), Qt.SolidLine, Qt.RoundCap))
            else:
                q.setPen(Qt.NoPen)
                q.setBrush(QColor("#1e1a18"))
                q.drawEllipse(at + QPointF(-rx * 0.35, ry * 0.25), rx * 0.48, ry * 0.5)
                q.setBrush(QColor("#ffffff"))
                q.drawEllipse(at + QPointF(-rx * 0.5, ry * 0.05), rx * 0.14, rx * 0.14)
                # Sly: the lids half down.
                q.save()
                q.setClipPath(white)
                q.fillRect(QRectF(at.x() - rx, at.y() - ry, 2 * rx, ry * 0.95), QColor(GREY_DEEP))
                q.restore()
                q.drawLine(at + QPointF(-rx, -0.05 * ry), at + QPointF(rx, -0.05 * ry))
                q.setPen(QPen(ink, max(0.5, 0.012 * s), Qt.SolidLine, Qt.RoundCap))
                q.drawLine(at + QPointF(-rx * 1.05, -0.05 * ry), at + QPointF(rx * 1.05, -0.05 * ry))
            q.strokePath(white, QPen(ink, max(0.4, 0.009 * s)))
        brows = ((-0.218, -0.808, -0.158, -0.79), (-0.135, -0.792, -0.065, -0.816)) if not hit else ((-0.215, -0.83, -0.155, -0.825), (-0.135, -0.825, -0.07, -0.835))
        q.setPen(QPen(ink, max(0.6, 0.016 * s), Qt.SolidLine, Qt.RoundCap))
        for x0, y0, x1, y1 in brows:
            q.drawLine(QPointF(x0 * s, y0 * s), QPointF(x1 * s, y1 * s))
        scar = QPainterPath(QPointF(-0.005 * s, -0.79 * s))
        scar.quadTo(QPointF(0.04 * s, -0.73 * s), QPointF(0.045 * s, -0.66 * s))
        q.strokePath(scar, QPen(col("#7a3b3b"), max(0.5, 0.012 * s), Qt.SolidLine, Qt.RoundCap))
        q.setPen(QPen(col("#7a3b3b"), max(0.4, 0.008 * s), Qt.SolidLine, Qt.RoundCap))
        for k in (0.25, 0.5, 0.75):
            at = scar.pointAtPercent(k)
            q.drawLine(at + QPointF(-0.018 * s, -0.004 * s), at + QPointF(0.018 * s, 0.004 * s))
        if hit:
            mouth = _ellipse(-0.245 * s, -0.618 * s, 0.038 * s, 0.032 * s)
            q.fillPath(mouth, QColor("#6e1f2b"))
            q.save()
            q.setClipPath(mouth)
            q.setPen(Qt.NoPen)
            q.setBrush(QColor(PINK))
            q.drawEllipse(QPointF(-0.245 * s, -0.592 * s), 0.028 * s, 0.016 * s)
            q.restore()
            q.strokePath(mouth, QPen(ink, max(0.5, 0.01 * s)))
            return
        mouth = QPainterPath(QPointF(-0.325 * s, -0.636 * s))
        mouth.quadTo(QPointF(-0.22 * s, -0.572 * s), QPointF(-0.122 * s, -0.622 * s))
        mouth.quadTo(QPointF(-0.23 * s, -0.622 * s), QPointF(-0.325 * s, -0.636 * s))
        q.fillPath(mouth, QColor("#6e1f2b"))
        q.save()
        q.setClipPath(mouth)
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#fffdf2"))
        x = -0.31
        while x < -0.135:
            # Fangs at the ends, a row of little teeth between.
            long = 0.03 if x < -0.29 or x > -0.165 else 0.017
            y = -0.632 + (x + 0.325) * 0.06
            q.drawPolygon([QPointF((x - 0.012) * s, (y - 0.01) * s), QPointF((x + 0.012) * s, (y - 0.01) * s), QPointF(x * s, (y + long) * s)])
            x += 0.026
        q.restore()
        q.strokePath(mouth, QPen(ink, max(0.5, 0.01 * s), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        smirk = QPainterPath(QPointF(-0.128 * s, -0.622 * s))
        smirk.quadTo(QPointF(-0.1 * s, -0.63 * s), QPointF(-0.095 * s, -0.655 * s))
        q.strokePath(smirk, QPen(ink, max(0.5, 0.012 * s), Qt.SolidLine, Qt.RoundCap))

    return art.render(features, ao=0.4, rim=0.3), box


def _paw(s: float, scale: float) -> tuple[QImage, QRectF]:
    """One of the wolf's paws, about its middle."""
    box = QRectF(-0.07 * s, -0.06 * s, 0.14 * s, 0.12 * s)
    art = _Art(box, scale, cool="#3d4670", seed=43)
    art.fill(_ellipse(0, 0, 0.05 * s, 0.04 * s, -15), GREY, 0.025 * s, grain=0.08, line=max(0.8, 0.02 * s))

    def toes(q: QPainter) -> None:
        q.setPen(QPen(col(INK), max(0.4, 0.008 * s), Qt.SolidLine, Qt.RoundCap))
        for dx in (-0.018, 0.0):
            q.drawLine(QPointF(-0.045 * s, (dx + 0.004) * s), QPointF(-0.025 * s, (dx + 0.008) * s))

    return art.render(toes), box


def _pan(r: float, scale: float) -> tuple[QImage, QRectF]:
    """A black frying pan, r its rim's radius, about its middle, its handle out to the right: cast iron
    with a dished bowl and a hard shine."""
    box = QRectF(-1.15 * r, -1.15 * r, 3.55 * r, 2.3 * r)
    art = _Art(box, scale, cool="#4b5878", seed=47)
    line = max(0.8, 0.07 * r)
    handle = QPainterPath()
    handle.addRoundedRect(QRectF(0.9 * r, -0.14 * r, 1.45 * r, 0.28 * r), 0.14 * r, 0.14 * r)
    art.fill(handle, "#24252a", 0.1 * r, gloss=0.6, line=line)
    art.fill(_ellipse(0, 0, r, r), IRON, 0.22 * r, gloss=0.9, line=line)
    art.fill(_ellipse(0, 0, 0.8 * r, 0.8 * r), "#26282e", 0.5 * r, swell=-0.45, rest=1.0, gloss=0.8, grain=0.03, line=line * 0.5)

    def hole(q: QPainter) -> None:
        q.setPen(QPen(col("#0f1013"), line * 0.6))
        q.setBrush(col("#0f1013"))
        q.drawEllipse(QPointF(2.15 * r, 0), 0.06 * r, 0.06 * r)

    return art.render(hole, ao=0.2, rim=0.5), box


def _burst(r: float, scale: float) -> tuple[QImage, QRectF]:
    """The blow: a jagged comic star, yellow round orange, and 咣 on it in heavy red letters edged in white."""
    box = QRectF(-1.2 * r, -1.2 * r, 2.4 * r, 2.4 * r)
    art = _Art(box, scale, cool="#a0402a", seed=53)
    rnd = random.Random(7)
    points = []
    for i in range(26):
        a = 2 * math.pi * i / 26 - math.pi / 2
        reach = r * (rnd.uniform(0.92, 1.08) if i % 2 == 0 else rnd.uniform(0.55, 0.66))
        points.append((math.cos(a) * reach, math.sin(a) * reach))
    outer = _polygon(points)
    art.fill(outer, "#ffe14a", 0.14 * r, swell=0.6, gloss=0.2, line=max(0.8, 0.05 * r))
    art.fill(QTransform().scale(0.62, 0.62).rotate(8).map(outer), "#ff9a2e", 0.1 * r, swell=0.5, rest=0.6)
    word = _text_path("咣", _font(["STHupo", "Microsoft YaHei", "Microsoft YaHei UI"], 1.15 * r, QFont.Weight.Black), QPointF(0, 0.02 * r))
    stroker = QPainterPathStroker()
    stroker.setWidth(0.2 * r)
    stroker.setJoinStyle(Qt.RoundJoin)
    art.fill(stroker.createStroke(word).united(word), "#ffffff", 0.05 * r, swell=0.6, rest=0.5, line=max(0.7, 0.035 * r))
    art.fill(word, COLLAR, 0.06 * r, swell=0.9, rest=0.5, gloss=0.4, line=max(0.6, 0.025 * r))
    return art.render(ao=0.3, rim=0.4), box


def _bubble(u: float, scale: float) -> tuple[QImage, QRectF, QPointF]:
    """His speech bubble, 我一定会回来的！ in it, its tail pointing right to him: the picture, its box about
    the bubble's middle and where the tail's tip is."""
    font = _font(ROUNDED, 22 * u)
    words = "我一定会回来的！"
    wide, high = QFontMetricsF(font).horizontalAdvance(words) + 34 * u, 46 * u
    tip = QPointF(wide / 2 + 26 * u, 4 * u)
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(-wide / 2, -high / 2, wide, high), high / 2, high / 2)
    shape = shape.united(_polygon([(wide / 2 - 22 * u, -8 * u), (tip.x(), tip.y()), (wide / 2 - 20 * u, 12 * u)])).simplified()
    box = QRectF(-wide / 2 - 6 * u, -high / 2 - 6 * u, wide + 38 * u, high + 12 * u)
    art = _Art(box, scale, cool="#6a7cb0", seed=59)
    art.fill(shape, "#f4f7fd", 8 * u, swell=0.5, grain=0.03, line=2.4 * u)

    def text(q: QPainter) -> None:
        q.setFont(font)
        q.setPen(col(INK))
        q.drawText(QRectF(-wide / 2, -high / 2, wide, high), Qt.AlignCenter, words)

    return art.render(text, ao=0.2, rim=0.4), box, tip


def _star_path(r: float) -> QPainterPath:
    points = []
    for i in range(10):
        a = math.pi * i / 5 - math.pi / 2
        reach = r if i % 2 == 0 else r * 0.5
        points.append((math.cos(a) * reach, math.sin(a) * reach))
    return _polygon(points, 0.12)


def _star(r: float, scale: float) -> tuple[QImage, QRectF]:
    """The star he becomes: plump and golden, outlined."""
    box = QRectF(-1.2 * r, -1.2 * r, 2.4 * r, 2.4 * r)
    art = _Art(box, scale, cool="#b06a10", seed=61)
    art.fill(_star_path(r), "#ffe25a", 0.3 * r, gloss=0.8, line=max(0.6, 0.08 * r))

    def eyes(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(col(INK))
        for side in (-1, 1):
            q.drawEllipse(QPointF(side * 0.17 * r, -0.02 * r), 0.06 * r, 0.09 * r)

    return art.render(eyes, ao=0.2, rim=0.5), box


def _star_glow(r: float) -> tuple[QRectF, QImage]:
    """The star's glow, about its middle, bloom worked out per pixel."""
    scale = 0.75
    area = QRectF(-5 * r, -5 * r, 10 * r, 10 * r)
    w = math.ceil(area.width() * scale)

    def draw(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(5 * r, 5 * r)
        q.fillPath(_star_path(r), QColor("#ffffff"))

    core = mask(w, w, draw)
    return area, bloom(core, SUN, ((r * 0.4 * scale, 0.9), (r * 1.4 * scale, 0.8), (r * 3.0 * scale, 0.5)))


def _cloud(wide: float, scale: float, seed: int) -> tuple[QImage, QRectF]:
    """A puffy cloud wide across, about its middle: a heap of soft puffs, flat underneath, its puffs
    shaded blue-grey where they tuck under each other and lit warm along their tops."""
    rnd = random.Random(seed)
    box = QRectF(-0.62 * wide, -0.46 * wide, 1.24 * wide, 0.62 * wide)
    art = _Art(box, scale, ink="#7ea3cf", cool="#6f8fc4", seed=seed)
    base = 0.1 * wide
    puffs = [
        (-0.36, 0.03, 0.15), (-0.2, -0.1, 0.2), (0.02, -0.17, 0.25), (0.24, -0.09, 0.2), (0.4, 0.03, 0.14),
        (-0.12, 0.04, 0.18), (0.12, 0.04, 0.18),
    ]  # fmt: skip
    puffs = [(x * wide * rnd.uniform(0.95, 1.05), y * wide, r * wide * rnd.uniform(0.92, 1.08)) for x, y, r in puffs]
    under = QPainterPath()
    under.addRect(QRectF(box.left(), box.top(), box.width(), base - box.top()))
    art.puffs(puffs, "#f4f8ff", flat=0.6, grain=0.06, line=max(0.6, 0.012 * wide), curl=0.12, clip=under)
    return art.render(ao=0.5, rim=0.5), box.translated(0, -base * 0.4)


def _bush(wide: float, scale: float) -> tuple[QImage, QRectF]:
    """A round leafy bush wide across, standing on (0, 0) by its middle, a few little flowers on it."""
    rnd = random.Random(29)
    box = QRectF(-0.6 * wide, -0.46 * wide, 1.2 * wide, 0.5 * wide)
    art = _Art(box, scale, cool="#1f4a3a", seed=29)
    puffs = [(-0.38, -0.08, 0.13), (-0.2, -0.18, 0.17), (0.04, -0.22, 0.18), (0.26, -0.17, 0.16), (0.4, -0.07, 0.12), (-0.1, -0.06, 0.17), (0.15, -0.06, 0.17)]
    puffs = [(x * wide, y * wide, r * wide * rnd.uniform(0.92, 1.08)) for x, y, r in puffs]
    ground = QPainterPath()
    ground.addRect(QRectF(box.left(), box.top(), box.width(), -box.top()))
    art.puffs(puffs, "#5cb33c", flat=0.7, grain=0.16, line=max(0.8, 0.018 * wide), curl=0.7, clip=ground)
    spots = [(rnd.uniform(-0.4, 0.4) * wide, rnd.uniform(-0.32, -0.08) * wide) for _ in range(7)]

    def flowers(q: QPainter) -> None:
        for index, (x, y) in enumerate(spots):
            _flower(q, x, y, 0.035 * wide, ("#ffffff", "#ffd2dc", "#fff2a0")[index % 3])

    return art.render(flowers, ao=0.5, rim=0.3), box


def _flower(q: QPainter, x: float, y: float, r: float, tint: str) -> None:
    """A little five-petalled flower, r across its petals, a yellow middle."""
    q.setPen(QPen(col("#6b8f3a", 0.6), max(0.3, r * 0.08)))
    for k in range(5):
        a = 2 * math.pi * k / 5 - math.pi / 2
        petal = QRadialGradient(QPointF(x + math.cos(a) * r * 0.45 - r * 0.1, y + math.sin(a) * r * 0.45 - r * 0.1), r * 0.6)
        petal.setColorAt(0, QColor("#ffffff"))
        petal.setColorAt(1, QColor(tint))
        q.setBrush(petal)
        q.drawEllipse(QPointF(x + math.cos(a) * r * 0.5, y + math.sin(a) * r * 0.5), r * 0.42, r * 0.42)
    middle = QRadialGradient(QPointF(x - r * 0.08, y - r * 0.08), r * 0.32)
    middle.setColorAt(0, QColor("#fff3a0"))
    middle.setColorAt(1, QColor("#e8a21c"))
    q.setPen(Qt.NoPen)
    q.setBrush(middle)
    q.drawEllipse(QPointF(x, y), r * 0.28, r * 0.28)


def _sign(u: float, scale: float) -> tuple[QImage, QRectF]:
    """The wooden signpost standing on (0, 0): a post and a board nailed on, 青青草原 on it."""
    box = QRectF(-62 * u, -88 * u, 124 * u, 92 * u)
    art = _Art(box, scale, cool="#5a3418", seed=67)
    line = 1.8 * u
    post = QPainterPath()
    post.addRoundedRect(QRectF(-5 * u, -66 * u, 10 * u, 68 * u), 3 * u, 3 * u)
    art.fill(post, "#a8743f", 3 * u, grain=0.2, line=line)
    board = QTransform().rotate(-3).map(_polygon([(-56 * u, -82 * u), (54 * u, -84 * u), (56 * u, -50 * u), (-55 * u, -48 * u)], 0.08))
    art.fill(board, "#dca266", 4 * u, swell=0.6, grain=0.18, line=line)
    font = _font(ROUNDED, 19 * u)

    def words(q: QPainter) -> None:
        q.save()
        q.rotate(-3)
        q.setFont(font)
        area = QRectF(-54 * u, -82 * u, 110 * u, 33 * u)
        q.setPen(col("#f6d6a0", 0.9))
        q.drawText(area.translated(0, 0.9 * u), Qt.AlignCenter, "青青草原")
        q.setPen(col("#5a3418"))
        q.drawText(area, Qt.AlignCenter, "青青草原")
        q.setPen(Qt.NoPen)
        q.setBrush(col("#5a3a22"))
        for x in (-48 * u, 48 * u):
            q.drawEllipse(QPointF(x, -66 * u), 1.8 * u, 1.8 * u)
        q.restore()
        # Grain along the wood.
        q.setPen(QPen(col("#7a4c22", 0.35), 0.8 * u))
        for y in (-58 * u, -40 * u, -22 * u, -6 * u):
            q.drawLine(QPointF(-1.5 * u, y), QPointF(-1.5 * u, y + 9 * u))

    return art.render(words, ao=0.3, rim=0.3), box


# The meadow and the sky.


def _meadow_rect(width: float, height: float, gap: QRectF, u: float, side: int) -> QRectF:
    """Where one side's meadow lies, from the screen's edge to the gap."""
    tall = 150 * u
    if side < 0:
        return QRectF(0, height - tall, max(1.0, gap.left()), tall)
    return QRectF(gap.right(), height - tall, max(1.0, width - gap.right()), tall)


def _hills(out: np.ndarray, u: float) -> tuple[np.ndarray, np.ndarray]:
    """How high the near hill and the far one stand, in points, out from the gap's edge: rolling, and
    sloping down to nothing at the gap."""
    near = u * (80 + 12 * np.sin(out / (88 * u) + 0.6) + 7 * np.sin(out / (37 * u) + 2.0)) * smooth(0, 120 * u, out) ** 0.8
    far = u * (110 + 16 * np.sin(out / (140 * u) + 2.4)) * smooth(40 * u, 220 * u, out)
    return near, far


def _out(xs: np.ndarray, gap: QRectF, side: int) -> np.ndarray:
    return gap.left() - xs if side < 0 else xs - gap.right()


def _streaks(width: int, height: int, cell_x: float, cell_y: float, seed: int) -> np.ndarray:
    """Value noise in cells cell_x by cell_y pixels, 0..1: long streaks one way, as grass has."""
    rnd = np.random.default_rng(seed)
    grid = rnd.random((int(height / cell_y) + 3, int(width / cell_x) + 3), dtype=np.float32)
    fx = np.arange(width, dtype=np.float32) / cell_x
    fy = np.arange(height, dtype=np.float32) / cell_y
    x0, y0 = fx.astype(int), fy.astype(int)
    sx, sy = fx - x0, (fy - y0)[:, None]
    sx, sy = sx * sx * (3 - 2 * sx), sy * sy * (3 - 2 * sy)
    across = grid[:, x0] * (1 - sx) + grid[:, x0 + 1] * sx
    return across[y0] * (1 - sy) + across[y0 + 1] * sy


def _meadow(width: float, height: float, gap: QRectF, u: float, scale: float, side: int) -> tuple[QRectF, QImage]:
    """One side's meadow, worked out per pixel: a far hill hazy with the sky, and in front of it the near
    one's grass, streaked with blades, patched with sun and shade, lit along its crests where they face
    the sun and deeper toward the bottom; a few little flowers in it."""
    rect = _meadow_rect(width, height, gap, u, side)
    w, h = max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale))
    xs = rect.left() + (np.arange(w, dtype=np.float32) + 0.5) / scale
    ys = rect.top() + (np.arange(h, dtype=np.float32) + 0.5) / scale
    near, far = _hills(_out(xs, gap, side), u)
    near_top, far_top = height - near, height - far
    below = ys[:, None] - near_top[None, :]
    in_near = np.clip(below * scale + 0.5, 0, 1)
    in_far = np.clip((ys[:, None] - far_top[None, :]) * scale + 0.5, 0, 1)
    # The near hill's crest, lit where it faces the sun in the upper left.
    slope = np.gradient(near_top, xs)
    facing = (slope * LIGHT[0] - LIGHT[1]) / np.sqrt(slope * slope + 1) / np.hypot(LIGHT[0], LIGHT[1])
    lit = 0.9 + 0.22 * facing[None, :] * np.exp(-np.maximum(below, 0) / (30 * u))
    depth = np.clip(below / (95 * u), 0, 1)[..., None]
    grass = rgb(GRASS_LIGHT) * np.clip(1 - depth * 3, 0, 1) + rgb(GRASS) * np.clip(1 - np.abs(depth * 3 - 1), 0, 1)
    grass += rgb(GRASS_DEEP) * np.clip(depth * 1.5 - 0.5, 0, 1)
    blades = _streaks(w, h, max(1.0, 1.3 * scale), 9 * scale, 71 + side)
    fine = noise(w, h, 1.6 * scale, 1, 73 + side)
    patch = noise(w, h, 44 * u * scale, 2, 75 + side)
    tone = (0.84 + 0.28 * blades + 0.08 * (fine - 0.5)) * lit
    grass = grass * tone[..., None]
    grass += (patch - 0.5)[..., None] * 0.35 * (rgb("#d8e25a") - grass)
    hazy = rgb("#9fd86a") * 0.8 + rgb(SKY) * 0.2
    far_color = np.broadcast_to(hazy, (h, w, 3)) * (0.95 + 0.08 * (noise(w, h, 20 * u * scale, 2, 77 + side) - 0.5))[..., None]
    color = far_color * (1 - in_near[..., None]) + grass * in_near[..., None]
    image = picture(color, np.maximum(in_near, in_far * 0.92)).convertToFormat(QImage.Format_ARGB32_Premultiplied)
    rnd = random.Random(80 + side)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(scale, scale)
    q.translate(-rect.left(), -rect.top())
    for index in range(7):
        x = rect.left() + rnd.uniform(0.08, 0.92) * rect.width()
        top = float(height - _hills(_out(np.array([x]), gap, side), u)[0][0])
        if height - top < 30 * u:
            continue
        _flower(q, x, rnd.uniform(top + 14 * u, min(height - 8 * u, top + 60 * u)), rnd.uniform(4.5, 6.5) * u, ("#ffffff", "#fff2a0", "#ffd2dc")[index % 3])
    q.end()
    image.setDevicePixelRatio(scale)
    return rect, image


def _blades(width: float, height: float, gap: QRectF, u: float, scale: float, side: int, phase: int) -> tuple[QRectF, QImage]:
    """The blades along the top of one side's near hill, swayed phase of SWAYS along a wave passing
    through them: each a curved blade darker at its root, the whole grained per pixel."""
    rect = _meadow_rect(width, height, gap, u, side)
    w, h = max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale))
    image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(scale, scale)
    q.translate(-rect.left(), -rect.top())
    q.setPen(Qt.NoPen)
    rnd = random.Random(90 + side)
    x = rect.left() + rnd.uniform(0, 2) * u
    while x < rect.right():
        top = float(height - _hills(_out(np.array([x]), gap, side), u)[0][0])
        stand = clamp((height - top) / (45 * u), 0.25, 1.0)
        tall, wide = rnd.uniform(8, 18) * u * stand, rnd.uniform(2.6, 3.8) * u
        lean = rnd.uniform(-0.3, 0.3) + 0.22 * math.sin(2 * math.pi * (phase / SWAYS - x / (230 * u)))
        root = QPointF(x, top + 3 * u)
        tip = QPointF(x + lean * tall, top + 3 * u - tall)
        blade = QPainterPath(QPointF(x - wide / 2, root.y()))
        blade.quadTo(QPointF(x - wide * 0.2 + lean * tall * 0.4, root.y() - tall * 0.6), tip)
        blade.quadTo(QPointF(x + wide * 0.3 + lean * tall * 0.4, root.y() - tall * 0.5), QPointF(x + wide / 2, root.y()))
        blade.closeSubpath()
        shade = rnd.uniform(0.25, 1.0)
        fill = QRadialGradient(root, tall * 1.1)
        fill.setColorAt(0, QColor(GRASS_DEEP))
        fill.setColorAt(1, QColor(GRASS_LIGHT).lighter(round(100 + 20 * shade)))
        q.setBrush(fill)
        q.drawPath(blade)
        x += rnd.uniform(2.4, 4.2) * u
    q.end()
    # Grain per pixel: the blades' color breaks up as real grass does.
    stride = image.bytesPerLine()
    pixels = np.frombuffer(image.constBits(), dtype=np.uint8, count=stride * h).reshape(h, stride)[:, : w * 4].reshape(h, w, 4).astype(np.float32)
    grain = 0.82 + 0.36 * _streaks(w, h, max(1.0, 1.1 * scale), 5 * scale, 95 + side)
    pixels[..., :3] = np.minimum(pixels[..., :3] * grain[..., None], pixels[..., 3:4])
    out = QImage(np.ascontiguousarray(pixels.astype(np.uint8)).data, w, h, w * 4, QImage.Format_ARGB32_Premultiplied).copy()
    out.setDevicePixelRatio(scale)
    return rect, out


def _sky(width: float, u: float) -> tuple[QRectF, QImage]:
    """A soft sky haze along the top, worked out per pixel at half size: sky blue at the edge, paler and
    thinner down to nothing, kept thin over the lobby's title, with soft wisps in it."""
    scale = 0.5
    rect = QRectF(0, 0, width, 240 * u)
    w, h = math.ceil(rect.width() * scale), math.ceil(rect.height() * scale)
    xs = (np.arange(w, dtype=np.float32) + 0.5) / scale
    ys = ((np.arange(h, dtype=np.float32) + 0.5) / scale)[:, None]
    fall = np.clip(1 - ys / rect.height(), 0, 1) ** 1.7
    title = ((xs[None, :] - width / 2) / (330 * u)) ** 2 + ((ys - 110 * u) / (150 * u)) ** 2
    keep = 0.3 + 0.7 * smooth(0.35, 1.3, title)
    wisps = noise(w, h, 60 * u * scale, 3, 101)
    alpha = 0.9 * fall * keep * (0.82 + 0.36 * wisps)
    color = rgb(SKY) * fall[..., None] + rgb("#e2f4ff") * (1 - fall[..., None])
    return rect, picture(np.broadcast_to(color, (h, w, 3)), alpha)


def _sun(sun: QPointF, u: float) -> tuple[QRectF, QImage]:
    """The sun in the top left corner: a white-hot core in a warm bloom, per pixel at half size."""
    scale = 0.5
    rect = QRectF(0, 0, 620 * u, 480 * u)
    w, h = math.ceil(rect.width() * scale), math.ceil(rect.height() * scale)
    xs = (np.arange(w, dtype=np.float32) + 0.5) / scale
    ys = ((np.arange(h, dtype=np.float32) + 0.5) / scale)[:, None]
    d = np.hypot(xs[None, :] - sun.x(), ys - sun.y())
    core = np.exp(-((d / (58 * u)) ** 2)) * 1.6
    halo = np.exp(-d / (140 * u)) * 0.5 + np.exp(-((d / (320 * u)) ** 2)) * 0.22
    light = core[..., None] * rgb("#fff6dc") + halo[..., None] * rgb(SUN)
    return rect, glow(light)


def _rays(u: float) -> tuple[QRectF, QImage]:
    """The sun's soft rays about its middle, per pixel at half size, to turn slowly."""
    scale = 0.5
    reach = 520 * u
    rect = QRectF(-reach, -reach, 2 * reach, 2 * reach)
    w = math.ceil(rect.width() * scale)
    xs = (np.arange(w, dtype=np.float32) + 0.5) / scale - reach
    dx, dy = xs[None, :], xs[:, None]
    d = np.hypot(dx, dy)
    a = np.arctan2(dy, dx)
    rays = (0.5 + 0.5 * np.cos(14 * a + 1.4 * np.sin(5 * a))) ** 5
    strength = rays * np.exp(-d / (230 * u)) * smooth(40 * u, 110 * u, d) * 0.4
    return rect, glow(strength[..., None] * rgb(SUN))


# The marks, each drawn once for each size and sharpness it is shown at.

_MARKS: dict[tuple, object] = {}
# The ring's wool bobs through these pictures, round and round, over RING_LOOP seconds.
RING_PHASES = 10
RING_LOOP = 2.4


def _mark(key: tuple, make_it: Callable[[], object]) -> object:
    if key not in _MARKS:
        _MARKS[key] = make_it()
    return _MARKS[key]


def _ring_wool(cover: QRectF, phase: int, scale: float) -> tuple[QRectF, QImage]:
    """The garland of wool puffs round the button, phase of RING_PHASES through their bobbing."""
    area = cover.adjusted(-9, -9, 9, 9)
    radius = min(cover.height() * 0.3, 18.0)
    route = QPainterPath()
    route.addRoundedRect(cover.adjusted(-1, -1, 1, 1), radius + 1, radius + 1)
    length = route.length()
    count = max(12, round(length / 6.6))
    middle = cover.center()
    puffs = []
    for i in range(count):
        k = route.percentAtLength(length * i / count)
        at = route.pointAtPercent(k)
        a = math.radians(route.angleAtPercent(k))
        normal = QPointF(math.sin(a), math.cos(a))
        if QPointF.dotProduct(normal, at - middle) < 0:
            normal = -normal
        turn = 2 * math.pi * phase / RING_PHASES + i * 0.9
        bob = math.sin(turn)
        r = (5.0 if i % 2 else 6.1) * (1 + 0.05 * math.sin(turn + 1.3))
        puffs.append((at.x() + normal.x() * bob, at.y() + normal.y() * bob, r))
    art = _Art(area, scale, seed=71)
    art.puffs(puffs, WOOL, flat=0.7, line=0.8, curl=0.5)
    return area, art.render(ao=0.45, rim=0.35)


def _ring_glow(cover: QRectF, scale: float) -> tuple[QRectF, QImage]:
    """A soft sunny glow round the ring, per pixel."""
    area = cover.adjusted(-9, -9, 9, 9)
    w, h = math.ceil(area.width() * scale), math.ceil(area.height() * scale)

    def draw(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(-area.left(), -area.top())
        q.setPen(QPen(QColor("#ffffff"), 6))
        q.setBrush(Qt.NoBrush)
        q.drawRoundedRect(cover, cover.height() * 0.3, cover.height() * 0.3)

    line = mask(w, h, draw)
    light = (blur(line, 2.5 * scale) * 0.7 + blur(line, 6 * scale) * 0.6)[..., None] * rgb("#ffe7a0")
    return area, glow(light)


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A garland of fluffy wool puffs round the button, bobbing gently, in a soft sunny glow."""
    scale = _sharpness(p)
    where = (round(cover.x(), 1), round(cover.y(), 1), round(cover.width(), 1), round(cover.height(), 1))
    area, light = _mark(("ring-glow", *where, scale), lambda: _ring_glow(cover, scale))
    p.save()
    p.setOpacity(0.6 + 0.25 * math.sin(t * 2.0))
    p.drawImage(area, light)
    p.restore()
    step = (t / RING_LOOP * RING_PHASES) % RING_PHASES
    first = int(step)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for phase, alpha in ((first, 1.0), ((first + 1) % RING_PHASES, step - first)):
        area, wool = _mark(("ring", *where, phase, scale), lambda phase=phase: _ring_wool(cover, phase, scale))
        p.setOpacity(alpha)
        p.drawImage(area, wool)
    p.setOpacity(1.0)


def _collar(side: float, scale: float) -> tuple[QImage, QRectF]:
    """The badge's red collar strip, side wide, about the badge's middle, sagging a little."""
    box = QRectF(-side / 2 - 2, -side / 2, side + 4, side)
    art = _Art(box, scale, seed=73)
    strip = _limb([(-side * 0.44, -side * 0.26), (0, -side * 0.06), (side * 0.44, -side * 0.26)], side * 0.2)
    art.fill(strip, COLLAR, side * 0.05, gloss=0.4, line=max(0.7, side * 0.025))

    def stitches(q: QPainter) -> None:
        pen = QPen(col("#ffd6d0", 0.75), max(0.4, side * 0.012), Qt.DashLine, Qt.RoundCap)
        q.setPen(pen)
        q.setBrush(Qt.NoBrush)
        seam = QPainterPath(QPointF(-side * 0.4, -side * 0.28))
        seam.quadTo(QPointF(0, -side * 0.04), QPointF(side * 0.4, -side * 0.28))
        q.drawPath(seam)

    return art.render(stitches, ao=0.2, rim=0.4), box


def _badge_glow(side: float, scale: float) -> tuple[QRectF, QImage]:
    area = QRectF(-side / 2 - 9, -side / 2 - 9, side + 18, side + 18)
    w = math.ceil(area.width() * scale)

    def draw(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(side / 2 + 9, side / 2 + 9)
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#ffffff"))
        q.drawEllipse(QPointF(0, side * 0.12), side * 0.28, side * 0.3)

    shape = mask(w, w, draw)
    return area, glow((blur(shape, 4 * scale) * 0.6 + blur(shape, 9 * scale) * 0.5)[..., None] * rgb("#ffd86a"))


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """The golden bell on its red collar strip in a warm glow, swinging; now and then it jingles and a
    glint catches it."""
    scale = _sharpness(p)
    side = box.width()
    key = (round(side, 1), scale)
    collar, collar_box = _mark(("badge-collar", *key), lambda: _collar(side, scale))
    bell, bell_box = _mark(("badge-bell", *key), lambda: _bell(side * 0.33, scale))
    area, light = _mark(("badge-glow", *key), lambda: _badge_glow(side, scale))
    middle = box.center()
    p.save()
    p.translate(middle)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setOpacity(0.65 + 0.3 * math.sin(t * 2.0))
    p.drawImage(area, light)
    p.setOpacity(1.0)
    p.drawImage(collar_box, collar)
    # A gentle swing, and a jingle every 2.6 seconds that dies away.
    since = t % 2.6
    swing = 7 * math.sin(t * 2.4) + 16 * spring(since, 3.2, 4.5) * (since < 1.5)
    p.save()
    p.translate(0, -side * 0.12)
    p.rotate(swing)
    p.drawImage(bell_box, bell)
    p.restore()
    shine = math.sin(math.pi * win(since, 0.15, 0.6))
    if shine > 0.02:
        glint(p, -side * 0.1, side * 0.12, side * 0.22 * shine, shine)
    p.restore()


def _card_paper(rect: QRectF, scale: float) -> QImage:
    """The card: cream paper grained per pixel, in a soft brown line, with a strip of shaded grass along
    its bottom, its blades up over the strip, and a few little flowers in it."""
    body = rect.adjusted(0.5, CARD_TOP + 0.5, -0.5, -0.5)
    page = QPainterPath()
    page.addRoundedRect(body, 9, 9)
    art = _Art(rect, scale, ink="#7a5a32", cool="#a07a40", seed=79)
    art.fill(page, PAPER, 2.5, swell=0.5, grain=0.06, line=1.1)
    rnd = random.Random(81)
    grass = QPainterPath()
    grass.addRect(QRectF(body.left(), body.bottom() - 10, body.width(), 11))
    x = body.left() + 3
    while x < body.right() - 3:
        tall = rnd.uniform(3.5, 7)
        lean = rnd.uniform(-1.5, 1.5)
        grass = grass.united(_polygon([(x - 1.6, body.bottom() - 9), (x + lean, body.bottom() - 9 - tall), (x + 1.6, body.bottom() - 9)]))
        x += rnd.uniform(2.6, 4.2)
    art.fill(grass.simplified().intersected(page), GRASS, 1.6, swell=0.8, rest=0.3, grain=0.14)
    spots = [body.left() + body.width() * k for k in (0.18, 0.55, 0.83)]

    def flowers(q: QPainter) -> None:
        for index, x in enumerate(spots):
            _flower(q, x, body.bottom() - 5, 2.6, ("#ffffff", "#fff2a0", "#ffd2dc")[index])

    return art.render(flowers, ao=0.3, rim=0.25)


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """The sunny meadow card, and a little cloud on its top right corner, bobbing."""
    scale = _sharpness(p)
    paper = _mark(("card", round(rect.width()), round(rect.height()), scale), lambda: _card_paper(rect, scale))
    p.drawImage(rect, paper)
    body = rect.adjusted(0, CARD_TOP, 0, 0)
    cloud, box = _mark(("card-cloud", max(2.0, scale)), lambda: _cloud(30.0, max(2.0, scale), 9))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(box.translated(body.right() - 22, body.top() + 3 + 1.2 * math.sin(t * 1.6)), cloud)


def lead(size: float, index: int) -> QPixmap:
    """A little golden bell before each name, leaning one way then the other."""
    scale = 3.0
    r = size * 0.33
    bell, box = _bell(r, scale)
    image = QImage(math.ceil(size * scale), math.ceil(size * scale), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.scale(scale, scale)
    q.translate(size / 2, size / 2 - r * 0.85)
    q.rotate(8 if index % 2 else -8)
    q.drawImage(box, bell)
    q.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(scale)
    return pixmap
