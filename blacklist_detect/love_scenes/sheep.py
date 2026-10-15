"""喜羊羊: a sunny morning on 青青草原 comes to the lobby's edges, and the cartoon's best-known gag plays in it.

A rolling meadow rises along the bottom, its grass grained per pixel and its blades swaying, a few
little flowers in it and a wooden signpost reading 青青草原; a soft sky haze and puffy clouds drift in
along the top, and a warm sun glows in the top left corner. 喜羊羊 hops in from the left to the corner
beside the names, a quarter of the screen tall, and 美羊羊, 懒羊羊 and 沸羊羊 hop in behind him along the
bottom. Nearer, in the long grass on the right, 灰太狼 tiptoes in, rocking on his toes, and 红太狼 after
him, her frying pan standing up at her side. She swings it down through the grass and up onto the side
of his head: 咣! between them. He is squashed flat, then spins out and up past the names, back in high up
with 我一定会回来的！ trailing him, and twinkles out as a star. The lambs jump for joy, the meadow sways,
and it all sinks back and fades.

The cast are the show's own pictures (assets/sheep), each scaled once to its size on the stage and only
moved, turned and squashed per frame; their shadows on the grass, the pan and all the rest are drawn
here. Nothing covers a name: 喜羊羊 stands in the room left of the names, the lambs under them as tall as
the room there lets them be, and the wolves, taller than 喜羊羊, stand down past the bottom edge with
only their heads and shoulders up in that room.

Its marks: the card a sunny meadow card, cream paper with shaded grass along its bottom and a little
cloud on its corner, the names in a rounded hand (幼圆 where it is installed), each after a golden
bell; the ring a garland of wool puffs round the button, bobbing; the badge 喜羊羊's golden bell on its
blue ribbon, swinging and glinting now and then.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QRadialGradient,
    QTransform,
)

from blacklist_detect.love_scenes.draw import (
    clamp,
    col,
    ease_back,
    ease_in,
    ease_in_out,
    ease_out,
    glint,
    soft_dot,
    spring,
    star,
    win,
)
from blacklist_detect.love_scenes.light import bloom, blur, glow, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from collections.abc import Callable

    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# 青青草原's colors: its grass, sky and sun; the wool, the bell and its ribbon; the pan's iron, and the
# ink of every outline.
GRASS = "#7ccf4a"
GRASS_LIGHT = "#b8e86e"
GRASS_DEEP = "#3f8f2e"
SKY = "#8fd3ff"
SUN = "#ffd36b"
WOOL = "#f2f4f9"
BELL = "#f5c542"
RIBBON = "#2c7be5"
IRON = "#34363d"
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
    "heart": ("#7fb4ff", RIBBON),
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

# The cast, as the show draws them, front on and standing.
CAST_PICTURES = Path(__file__).resolve().parent.parent / "assets" / "sheep"
CAST = {"xi": "xiyangyang", "mei": "meiyangyang", "lan": "lanyangyang", "fei": "feiyangyang", "hui": "huitailang", "hong": "hongtailang"}
# How tall each stands, as a share of the stage's height: 喜羊羊 over a quarter; the other lambs at most a
# little smaller, as tall as the room under the names lets them be; the wolves taller than 喜羊羊.
TALL = {"xi": 0.27, "mei": 0.23, "lan": 0.23, "fei": 0.23, "hui": 0.275, "hong": 0.275}
# Points at full size kept free over the lambs under the names, for their hops and jumps, and over the
# wolves, for their tiptoes.
JUMP_ROOM = 14.0
WOLF_ROOM = 10.0
# 喜羊羊 beside the names: how much wider he may squash as he lands, how far he may lean (degrees) once
# there, and the share of him that may stand past the screen's left edge (a horn's tip).
XI_SQUASH = 0.06
XI_LEAN = 2.5
CUT = 0.04
# 红太狼's paw, as a share of her picture's width and height; the pan's bowl, as a share of her height.
PAW = (0.373, 0.797)
BOWL = 0.16
# The lambs hop in from the left: (who, sets off, lands, hops). The ones along the bottom first, the one
# going furthest leading, behind 喜羊羊 as he hops into his corner.
ENTRANCES = (("fei", 0.2, 1.2, 5), ("lan", 0.3, 1.3, 4), ("mei", 0.4, 1.4, 4), ("xi", 0.5, 1.2, 3))
# They jump for joy twice: (takes off, lands).
JUMPS = ((3.42, 3.8), (3.88, 4.26))
# 灰太狼 tiptoes in; 红太狼 walks in after him; the pan swings down through the grass and up onto his
# head, bounces off it and goes back the way it came; he is squashed, then flies off and becomes a
# star, his words trailing him.
SNEAK = (1.3, 2.3)
WALK = (1.7, 2.3)
SWING = 2.4
HIT = 2.68
LOWER = (3.05, 3.6)
FLIGHT = (2.82, 3.66)
BUBBLE_AT = 3.08
# The grass blades sway through these pictures, one after another.
SWAYS = 10


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    ground = height - 6 * u
    names = stage.names()
    sun = QPointF(30 * u, 22 * u)
    pictures = {who: QImage(str(CAST_PICTURES / f"{name}.png")) for who, name in CAST.items()}
    aspect = {who: image.width() / max(1, image.height()) for who, image in pictures.items()}
    # Under the names: from the lowest name's bottom to the ground.
    ceiling = max((name.bottom() for name in names), default=height * 0.82) + 4 * u
    band = max(24 * u, ground - ceiling)
    tall = {who: min(TALL[who] * height, band - JUMP_ROOM * u) for who in ("mei", "lan", "fei")}
    # 喜羊羊 in the corner left of the names, as tall as he may be there, landing and leaning included.
    xi = TALL["xi"] * height
    for _ in range(3):
        beside = [name.left() for name in names if name.bottom() > ground - xi - 60 * u]
        room = min(beside, default=width) - 4 * u
        xi = max(tall["mei"], min(xi, room / (aspect["xi"] * (1 + XI_SQUASH / 2 - CUT) + 0.75 * math.sin(math.radians(XI_LEAN)))))
    tall["xi"] = xi
    # The wolves nearer than the lambs: taller than 喜羊羊, their heads under the names and the rest of
    # them down past the bottom edge, in the long grass there.
    tall.update({who: max(TALL[who] * height, band - WOLF_ROOM * u) for who in ("hui", "hong")})
    feet = {who: max(ground, ceiling + WOLF_ROOM * u + tall[who]) for who in ("hui", "hong")}
    wide = {who: tall[who] * aspect[who] for who in CAST}
    # Where each stands: 喜羊羊 in the corner, a sliver of him past the edge; the others along the bottom
    # up to the gap.
    rest = {"xi": min(4 * u + wide["xi"] / 2, room - wide["xi"] * (1 + XI_SQUASH) / 2 - 0.75 * xi * math.sin(math.radians(XI_LEAN)))}
    start, end = rest["xi"] + wide["xi"] / 2 + 6 * u, gap.left() - 8 * u
    row = ("mei", "lan", "fei")
    spare = (end - start) - sum(wide[who] for who in row)
    x = start + max(0.0, spare) / (len(row) + 1)
    step = max(0.0, spare) / (len(row) + 1) if spare > 0 else spare / (len(row) - 1)
    for who in row:
        rest[who] = x + wide[who] / 2
        x += wide[who] + step
    # 灰太狼 just right of the gap; 红太狼 further right, room between them for the signpost and the 咣.
    burst_r = clamp(band / 2.7, 12 * u, 54 * u)
    rest["hui"] = gap.right() + wide["hui"] / 2 + 24 * u
    between = clamp(width - 4 * u - (rest["hui"] + wide["hui"] / 2) - wide["hong"], 0.0, 2.4 * burst_r)
    rest["hong"] = rest["hui"] + wide["hui"] / 2 + between + wide["hong"] / 2
    middle = rest["hui"] + wide["hui"] / 2 + between / 2
    sign_at = QPointF(middle, ground + 2 * u)
    bang = QPointF(middle, max(feet["hui"] - 0.66 * tall["hui"], ceiling + 1.35 * burst_r))
    # The pan: held down in the grass at her side, swung up from below onto the side of his head.
    head = QPointF(rest["hui"] + 0.46 * wide["hui"], feet["hui"] - 0.66 * tall["hui"])
    grip = QPointF(rest["hong"] - 0.3 * wide["hong"], min(feet["hong"] - (1 - PAW[1]) * tall["hong"], height + 10 * u))
    reach = math.hypot(head.x() - grip.x(), head.y() - grip.y())
    bowl = BOWL * tall["hong"]
    swing_to = math.degrees(math.atan2(head.y() - grip.y(), head.x() - grip.x())) % 360
    # At rest it stands up by her right side, as high as the names let it.
    rest_angle = -math.degrees(math.asin(clamp((grip.y() - ceiling - 2 * u - bowl) / reach, 0.17, 0.98)))
    # He flies from the blow out right along the bottom, up past the names beyond them, and back in
    # high up to where he twinkles out.
    top_names = min((name.top() for name in names), default=height * 0.48)
    names_right = max((name.right() for name in names), default=width)
    beyond = names_right + 0.3 * tall["hui"]
    launch = QPointF(rest["hui"], feet["hui"] - 0.4 * tall["hui"])
    twinkle = QPointF(width - 0.12 * width, max(60 * u, 0.14 * height))
    flight = (launch, QPointF(beyond, launch.y()), QPointF(beyond, (ceiling + top_names) / 2), QPointF(beyond, top_names - 0.25 * tall["hui"] - 4 * u), twinkle)
    # (x, y, how wide, which way it drifts in from)
    clouds = [(255 * u, 82 * u, 140 * u, -1), (585 * u, 58 * u, 96 * u, -1), (width - 118 * u, 70 * u, 128 * u, 1)]
    makers = [
        ("sky", lambda _scale: _sky(width, u)),
        ("sun", lambda _scale: _sun(sun, u)),
        ("rays", lambda _scale: _rays(u)),
        ("shadow", lambda _scale: _shadow_picture()),
        ("star-glow", lambda _scale: _star_glow(20 * u)),
        *((("cast", who), lambda scale, who=who: _sprite(pictures[who], tall[who], scale)) for who in CAST),
        *((("cloud", index), lambda scale, wide=wide_, index=index: _cloud(wide, scale, 5 + index)) for index, (_x, _y, wide_, _from) in enumerate(clouds)),
        *((("meadow", side), lambda scale, side=side: _meadow(width, height, gap, u, scale, side)) for side in (-1, 1)),
        *((("blades", side, phase), lambda scale, side=side, phase=phase: _blades(width, height, gap, u, scale, side, phase)) for phase in range(SWAYS) for side in (-1, 1)),
        *((("long grass", phase), lambda scale, phase=phase: _blades(width, height, gap, u, scale, 1, phase, front=True)) for phase in range(SWAYS)),
        ("sign", lambda scale: _sign(u, scale)),
        ("pan", lambda scale: _pan(reach, bowl, scale)),
        ("burst", lambda scale: _burst(burst_r, scale)),
        ("bubble", lambda scale: _bubble(u, scale)),
        ("star", lambda scale: _star(20 * u, scale)),
    ]
    how = dict(makers)
    baked: dict[tuple, object] = {}
    soft_light = ("sky", "sun", "rays", "shadow", "star-glow")

    def picture_of(name: object, scale: float) -> object:
        # The soft light is the same at every sharpness.
        if name in soft_light:
            scale = 0.0
        if (name, scale) not in baked:
            baked[name, scale] = how[name](scale)
        return baked[name, scale]

    for name, _how in makers:
        picture_of(name, 1.0)
    layout = {"u": u, "ground": ground, "feet": feet, "tall": tall, "wide": wide, "rest": rest, "bang": bang, "ceiling": ceiling}
    layout.update({"grip": grip, "rest_angle": rest_angle, "swing_to": swing_to, "flight": flight, "top_names": top_names, "width": width, "height": height})

    def paint(p: QPainter, t: float) -> None:
        # Up from below as it comes in, down again at the end.
        up = ease_out(win(t, 0.0, 0.7)) * (1 - ease_in(win(t, 4.4, 5.0)))
        life = 1 - ease_in(win(t, 4.55, 5.0))
        if up <= 0 or life <= 0:
            return
        scale = _sharpness(p)

        def get(name: object) -> object:
            return picture_of(name, scale)

        drop = (1 - up) * 150 * u
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setOpacity(life * up)
        rect, image = get("sun")
        p.drawImage(rect, image)
        p.save()
        p.translate(sun)
        p.rotate(t * 7)
        p.setOpacity(life * up * (0.8 + 0.2 * math.sin(t * 2.3)))
        rect, image = get("rays")
        p.drawImage(rect, image)
        p.restore()
        p.setOpacity(life * ease_out(win(t, 0.05, 0.75)))
        rect, image = get("sky")
        p.drawImage(rect.translated(0, -(1 - up) * 50 * u), image)
        for index, (x, y, wide_, side) in enumerate(clouds):
            come = ease_out(win(t, 0.05 + 0.12 * index, 0.85 + 0.12 * index))
            if come <= 0:
                continue
            image, box = get(("cloud", index))
            drift = side * (1 - come) * (wide_ + 160 * u) - side * 6 * u * t
            bob = 2.5 * u * math.sin(t * 1.4 + index * 2)
            p.setOpacity(life * come * (1 - ease_in(win(t, 4.4, 4.9))))
            p.drawImage(box.translated(x + drift, y + bob - (1 - up) * 40 * u), image)
        p.setOpacity(life)
        for side in (-1, 1):
            rect, image = get(("meadow", side))
            p.drawImage(rect.translated(0, drop), image)
        # The blades sway in a breeze that gusts as the lambs jump for joy.
        breeze = t * 0.65 + 1.6 * ease_in_out(win(t, 3.35, 4.45))
        step_ = (breeze * SWAYS) % SWAYS
        first, mix_in = int(step_), step_ - int(step_)
        for side in (-1, 1):
            for phase, alpha in ((first, 1.0), ((first + 1) % SWAYS, mix_in)):
                rect, image = get(("blades", side, phase))
                p.setOpacity(life * alpha)
                p.drawImage(rect.translated(0, drop), image)
        p.setOpacity(life)
        image, box = get("sign")
        p.drawImage(box.translated(sign_at.x(), sign_at.y() + drop), image)
        _paint_lambs(p, t, get, layout, drop)
        _paint_bang(p, t, get, layout)
        _paint_wolves(p, t, get, layout, drop)
        for phase, alpha in ((first, 1.0), ((first + 1) % SWAYS, mix_in)):
            rect, image = get(("long grass", phase))
            p.setOpacity(life * alpha)
            p.drawImage(rect.translated(0, drop), image)
        p.setOpacity(life)
        _paint_gag(p, t, get, layout)
        p.restore()

    return paint


def _sharpness(p: QPainter) -> float:
    """Pixels per point where p draws: its screen's and its own scaling."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return round(ratio * math.hypot(p.transform().m11(), p.transform().m12()), 2)


# The cast.


def _sprite(image: QImage, tall: float, scale: float) -> tuple[QImage, QRectF]:
    """One of the cast's pictures scaled smoothly, once, to tall points at scale pixels to the point,
    and its box standing on (0, 0)."""
    wide = tall * image.width() / max(1, image.height())
    pixels = image.scaled(max(1, round(wide * scale)), max(1, round(tall * scale)), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return pixels.convertToFormat(QImage.Format_ARGB32_Premultiplied), QRectF(-wide / 2, -tall, wide, tall)


def _stand(p: QPainter, picture: tuple[QImage, QRectF], at: QPointF, lift: float = 0.0, squash: float = 0.0, tilt: float = 0.0) -> None:
    """A character standing on at, lift points up off it, squash wider and shorter (less than 0
    stretched taller), tilt degrees about its feet."""
    image, box = picture
    p.save()
    p.translate(at.x(), at.y() - lift)
    p.rotate(tilt)
    p.scale(1 + squash, 1 - squash)
    p.drawImage(box, image)
    p.restore()


def _shadow_picture() -> tuple[QImage, QRectF]:
    """A soft round shadow on the grass, per pixel, a unit across, to be stretched under each one."""
    n = 96
    xs = (np.arange(n, dtype=np.float32) + 0.5) / n * 2 - 1
    d = np.hypot(xs[None, :], xs[:, None])
    alpha = np.exp(-((d / 0.55) ** 2) * 1.6) * smooth(1.0, 0.75, d)
    color = np.broadcast_to(rgb("#1d4a14"), (n, n, 3))
    return picture(color, alpha), QRectF(-0.5, -0.5, 1, 1)


def _shadow(p: QPainter, get: Callable, at: QPointF, wide: float, lift: float, u: float) -> None:
    """A character's shadow on the grass, wide across, smaller and fainter the higher it is."""
    image, box = get("shadow")
    away = 1 / (1 + lift / (40 * u))
    p.save()
    p.setOpacity(p.opacity() * 0.55 * away)
    p.translate(at)
    p.scale(wide * (0.55 + 0.45 * away), wide * 0.16 * (0.55 + 0.45 * away))
    p.drawImage(box, image)
    p.restore()


def _hop(t: float, start: float, land: float, hops: int, x0: float, x1: float, high: float) -> tuple[float, float, float, float]:
    """Hopping from x0 to x1 in hops hops between start and land: x, how high, how squashed (stretched
    in the air, squashed as it lands) and its lean into the hop."""
    k = clamp((t - start) / (land - start))
    x = x0 + (x1 - x0) * k
    if k >= 1:
        return x1, 0.0, 0.0, 0.0
    hop = min(hops - 1, int(k * hops))
    kk = k * hops - hop
    lift = high * 4 * kk * (1 - kk)
    squash = -0.07 * math.sin(math.pi * kk) + (0.1 * (1 - kk * 6) if hop and kk < 1 / 6 else 0.0)
    return x, lift, squash, 7 * math.sin(math.pi * kk) * (1 if x1 >= x0 else -1)


def _paint_lambs(p: QPainter, t: float, get: Callable, at: dict, drop: float) -> None:
    """The lambs hopping in from the left, bobbing where they stand, jumping for joy; the ones along the
    bottom first, 喜羊羊 in front. None of them reaches a name: the ones under the names hop and stretch
    within the room over them, 喜羊羊 squashes and leans no further than he has room for."""
    u, ground = at["u"], at["ground"] + drop
    for who, start, land, hops in sorted(ENTRANCES, key=lambda entrance: entrance[0] == "xi"):
        if t < start:
            continue
        tall, wide = at["tall"][who], at["wide"][who]
        room = 60 * u if who == "xi" else JUMP_ROOM * u
        high = 0.7 * room if who == "xi" else 0.45 * room
        x, lift, squash, tilt = _hop(t, start, land, hops, -wide * 0.7, at["rest"][who], high)
        index = "xfml".index(who[0])
        if t >= land:
            squash = 0.14 * spring(t - land, 2.4, 7.0) + 0.012 * math.sin(t * 5.0 + index)
            tilt = 2.0 * math.sin(t * 2.2 + index * 1.7)
            for up, down in JUMPS:
                if up <= t < down:
                    k = (t - up) / (down - up)
                    lift = high * 4 * k * (1 - k)
                    squash = -0.07 * math.sin(math.pi * k)
                    tilt = 5 * math.sin(2 * math.pi * k) * (1 if index % 2 else -1)
                elif t >= down:
                    squash += 0.12 * spring(t - down, 2.4, 7.0)
        if who == "xi":
            if x > at["rest"]["xi"] - 0.2 * wide:
                tilt = clamp(tilt, -XI_LEAN, XI_LEAN)
            squash = min(squash, XI_SQUASH)
        else:
            squash = max(squash, -0.2 * room / tall)
            tilt = clamp(tilt, -3.0, 3.0)
        foot = QPointF(x, ground)
        _shadow(p, get, foot, wide * 0.9, lift, u)
        _stand(p, get(("cast", who)), foot, lift, squash, tilt)


def _paint_wolves(p: QPainter, t: float, get: Callable, at: dict, drop: float) -> None:
    """灰太狼 tiptoeing in on the right, rocking on his toes, squashed down into the grass by the pan;
    红太狼 walking in after him with it, and swinging it. Both stand in the long grass, their feet past
    the bottom edge, and stay within the room under the names."""
    u, width = at["u"], at["width"]
    room = WOLF_ROOM * u
    if t >= WALK[0]:
        k = ease_out(win(t, *WALK))
        shift = (width + at["wide"]["hong"] - at["rest"]["hong"]) * (1 - k)
        walking = 1 - win(t, WALK[1] - 0.1, WALK[1] + 0.05)
        steps = (t - WALK[0]) / 0.18
        lift = 0.5 * room * abs(math.sin(math.pi * steps)) * walking
        tilt = 2 * math.sin(math.pi * steps) * walking
        # A little hop of glee after the blow.
        glee = win(t, HIT + 0.08, HIT + 0.42)
        if 0 < glee < 1:
            lift = 0.5 * room * 4 * glee * (1 - glee)
        foot = QPointF(at["rest"]["hong"] + shift, at["feet"]["hong"] + drop)
        _stand(p, get(("cast", "hong")), foot, lift, 0.006 * math.sin(t * 4.0), tilt)
        if t < SWING:
            _paint_pan(p, t, get, at, QPointF(shift, drop - lift))
    if SNEAK[0] <= t < FLIGHT[0]:
        k = win(t, *SNEAK)
        x = at["rest"]["hui"] + (width + at["wide"]["hui"] - at["rest"]["hui"]) * (1 - k) ** 1.3
        # On tiptoe: up on each step and leaning into it; then rocking on his toes, scheming.
        steps = (t - SNEAK[0]) / 0.24
        lift = 0.5 * room * abs(math.sin(math.pi * steps))
        tilt = -1 + 1.5 * math.sin(math.pi * steps)
        squash = 0.0
        if t >= HIT:
            # Hit: squashed flat from below, his face where it was, shaking, then springing back.
            squash = 0.14 * (1 - ease_out(win(t, HIT, FLIGHT[0]))) + 0.03 * spring(t - HIT, 6.0, 9.0)
            lift, tilt = squash * at["tall"]["hui"], 2.0 * math.sin((t - HIT) * 70) * (1 - win(t, HIT, FLIGHT[0]))
        _stand(p, get(("cast", "hui")), QPointF(x, at["feet"]["hui"] + drop), lift, squash, tilt)
    if t >= max(WALK[0], SWING):
        _paint_pan(p, t, get, at, QPointF(0, drop))


def _pan_angle(t: float, rest: float, hit: float) -> float:
    """The pan's angle at t (degrees, 0 pointing right, 90 down): standing up by her side, swung down
    through the grass and up onto his head, bouncing off it, and lowered back the way it came."""
    if t < SWING:
        return rest + 3 * math.sin(t * 3.0)
    if t < HIT:
        return rest + (hit - rest) * ease_in(win(t, SWING, HIT))
    bounce = hit - 14 * (1 - spring(t - HIT, 2.2, 5.0))
    return bounce + (rest - bounce) * ease_in_out(win(t, *LOWER))


def _paint_pan(p: QPainter, t: float, get: Callable, at: dict, shift: QPointF) -> None:
    """The pan in 红太狼's grip down in the grass, smeared through the air as it swings."""
    rest, hit = at["rest_angle"], at["swing_to"]
    hit += 360 if hit < rest else 0
    grip = at["grip"] + shift
    image, box = get("pan")
    swinging = win(t, SWING + 0.1, HIT) * (1 - win(t, HIT, HIT + 0.05))
    for back, alpha in ((0.04, 0.3), (0.02, 0.5), (0.0, 1.0)):
        if back and swinging <= 0:
            continue
        p.save()
        p.setOpacity(p.opacity() * alpha * (swinging if back else 1.0))
        p.translate(grip)
        p.rotate(_pan_angle(t - back, rest, hit))
        p.drawImage(box, image)
        p.restore()


def _bezier(points: tuple[QPointF, ...], k: float) -> QPointF:
    a, b, c, d = points
    m = 1 - k
    return a * m**3 + b * 3 * m * m * k + c * 3 * m * k * k + d * k**3


def _flight(flight: tuple[QPointF, ...], t: float) -> tuple[QPointF, float]:
    """Where 灰太狼 is as he flies off, and how far along (0..1): out right along the bottom, turning up
    beyond the names, and up and back in to where he twinkles out."""
    k = win(t, *FLIGHT)
    e = 1 - (1 - k) ** 1.6
    launch, corner, middle, high, end = flight
    if e < 0.5:
        return _bezier((launch, corner, corner, middle), e * 2), k
    return _bezier((middle, high, high, end), e * 2 - 1), k


def _paint_bang(p: QPainter, t: float, get: Callable, at: dict) -> None:
    """咣! as the pan lands: a flash and a burst behind the wolves, between them, lines flying out of it."""
    if not HIT <= t < HIT + 0.42:
        return
    u, bang, ceiling = at["u"], at["bang"], at["ceiling"]
    k = t - HIT
    room = bang.y() - ceiling
    soft_dot(p, bang.x(), bang.y(), min(room, 90 * u) * (0.7 + k), "#fff8d0", 0.8 * (1 - win(k, 0.0, 0.2)))
    pop = ease_back(win(k, 0.0, 0.1), 2.4) * (1 - ease_in(win(k, 0.28, 0.42)))
    # Lines fly out of the blow, sideways and down, away from the names.
    p.setPen(QPen(col("#ffffff", 0.9 * (1 - win(k, 0.1, 0.3))), 3.2 * u, Qt.SolidLine, Qt.RoundCap))
    for index in range(7):
        angle = math.radians(-5 + index * 31.5)
        inner, outer = 0.9 * room + 70 * u * k, 1.1 * room + 110 * u * k
        p.drawLine(bang + QPointF(math.cos(angle), math.sin(angle)) * inner, bang + QPointF(math.cos(angle), math.sin(angle)) * outer)
    _place(p, get("burst"), bang, 6 * math.sin(k * 40) * (1 - k * 2.4), pop, 1.0)


def _paint_gag(p: QPainter, t: float, get: Callable, at: dict) -> None:
    """灰太狼 spinning up and away with his words trailing him, and the star he becomes."""
    u, flight = at["u"], at["flight"]
    if FLIGHT[0] <= t < FLIGHT[1] + 0.05:
        middle, k = _flight(flight, t)
        image, box = get(("cast", "hui"))
        p.save()
        p.setOpacity(p.opacity() * (1 - win(t, FLIGHT[1] - 0.12, FLIGHT[1] + 0.02)))
        p.translate(middle)
        p.rotate(-760 * ease_out(k))
        size = 1 - 0.78 * ease_out(k)
        p.scale(size, size)
        p.drawImage(box.translated(0, box.height() / 2), image)
        p.restore()
    if t >= BUBBLE_AT:
        trail, _k = _flight(flight, t - 0.1)
        image, box, tip = get("bubble")
        pop = ease_back(win(t, BUBBLE_AT, BUBBLE_AT + 0.2), 2.0)
        # Up and to his left, its tail toward him, never down over the names.
        where = trail + QPointF(-34 * u, -6 * u) - tip
        where.setY(min(where.y(), at["top_names"] - 6 * u - box.bottom()))
        where.setX(min(where.x(), at["width"] - 6 * u - box.right()))
        p.save()
        p.translate(where + tip)
        p.scale(pop, pop)
        p.translate(-tip)
        p.setOpacity(p.opacity() * (1 - win(t, 4.3, 4.6)))
        p.drawImage(box, image)
        p.restore()
    star_k = win(t, FLIGHT[1] - 0.03, FLIGHT[1] + 0.15)
    end = flight[-1]
    if star_k > 0:
        flash = 1 - win(t, FLIGHT[1], FLIGHT[1] + 0.3)
        soft_dot(p, end.x(), end.y(), 70 * u, "#fff6c8", 0.9 * flash)
        rect, light = get("star-glow")
        twinkle = 0.5 + 0.5 * math.sin((t - FLIGHT[1]) * 9)
        p.save()
        p.setOpacity(p.opacity() * (0.55 + 0.45 * twinkle) * ease_out(star_k))
        p.drawImage(rect.translated(end), light)
        p.restore()
        size = ease_back(star_k, 2.6) * (1 + 0.1 * math.sin((t - FLIGHT[1]) * 9))
        _place(p, get("star"), end, 12 * math.sin((t - FLIGHT[1]) * 3), size, 1.0)
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


def _pan(reach: float, r: float, scale: float) -> tuple[QImage, QRectF]:
    """红太狼's frying pan, held by its handle's end at (0, 0) and pointing right, reach from there to
    the middle of its bowl, r the bowl's radius: black cast iron, a dished bowl with a hard shine, a
    light caught along its rim, the handle wrapped where she holds it."""
    box = QRectF(-0.12 * r, -1.2 * r, reach + 2.3 * r, 2.4 * r)
    art = _Art(box, scale, cool="#4b5878", seed=47)
    line = max(0.8, 0.07 * r)
    handle = QPainterPath()
    handle.addRoundedRect(QRectF(-0.06 * r, -0.15 * r, reach - 0.7 * r, 0.3 * r), 0.15 * r, 0.15 * r)
    art.fill(handle, "#24252a", 0.12 * r, gloss=0.6, line=line)
    grip = QPainterPath()
    grip.addRoundedRect(QRectF(-0.08 * r, -0.19 * r, 0.75 * r, 0.38 * r), 0.17 * r, 0.17 * r)
    art.fill(grip, "#6b3b22", 0.12 * r, grain=0.2, line=line)
    art.fill(_ellipse(reach, 0, r, r), IRON, 0.22 * r, gloss=0.9, line=line)
    art.fill(_ellipse(reach, 0, 0.8 * r, 0.8 * r), "#26282e", 0.5 * r, swell=-0.45, rest=1.0, gloss=0.8, grain=0.03, line=line * 0.5)

    def rim(q: QPainter) -> None:
        q.setPen(QPen(col("#c9d2e6", 0.75), max(0.6, 0.07 * r), Qt.SolidLine, Qt.RoundCap))
        q.drawArc(QRectF(reach - 0.9 * r, -0.9 * r, 1.8 * r, 1.8 * r), 100 * 16, 75 * 16)
        q.setPen(QPen(col("#8a5a3a", 0.8), max(0.5, 0.04 * r), Qt.SolidLine, Qt.RoundCap))
        for x in (0.15, 0.32, 0.49):
            q.drawLine(QPointF(x * r, -0.18 * r), QPointF((x + 0.08) * r, 0.18 * r))
        q.setPen(Qt.NoPen)
        q.setBrush(col("#0f1013"))
        q.drawEllipse(QPointF(reach - 1.08 * r, 0), 0.06 * r, 0.06 * r)

    return art.render(rim, ao=0.2, rim=0.5), box


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
    art.fill(word, "#e0393e", 0.06 * r, swell=0.9, rest=0.5, gloss=0.4, line=max(0.6, 0.025 * r))
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


def _blades(width: float, height: float, gap: QRectF, u: float, scale: float, side: int, phase: int, front: bool = False) -> tuple[QRectF, QImage]:
    """The blades along the top of one side's near hill, swayed phase of SWAYS along a wave passing
    through them: each a curved blade darker at its root, the whole grained per pixel. front: instead
    the long grass along the bottom edge right of the gap, which the wolves stand in."""
    rect = _meadow_rect(width, height, gap, u, side)
    if front:
        rect = QRectF(gap.right(), height - 44 * u, max(1.0, width - gap.right()), 44 * u)
    w, h = max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale))
    image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(scale, scale)
    q.translate(-rect.left(), -rect.top())
    q.setPen(Qt.NoPen)
    rnd = random.Random(90 + side + 7 * front)
    x = rect.left() + rnd.uniform(0, 2) * u
    while x < rect.right():
        if front:
            top, stand = height + 2 * u, rnd.uniform(0.9, 1.7)
        else:
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
        x += (rnd.uniform(1.6, 2.8) if front else rnd.uniform(2.4, 4.2)) * u
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
    """The badge's blue ribbon, side wide, about the badge's middle, sagging a little."""
    box = QRectF(-side / 2 - 2, -side / 2, side + 4, side)
    art = _Art(box, scale, seed=73)
    strip = _limb([(-side * 0.44, -side * 0.26), (0, -side * 0.06), (side * 0.44, -side * 0.26)], side * 0.2)
    art.fill(strip, RIBBON, side * 0.05, gloss=0.4, line=max(0.7, side * 0.025))

    def stitches(q: QPainter) -> None:
        pen = QPen(col("#d6e8ff", 0.75), max(0.4, side * 0.012), Qt.DashLine, Qt.RoundCap)
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
    """喜羊羊's golden bell on its blue ribbon in a warm glow, swinging; now and then it jingles and a
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
