"""竖琴清风: the screen framed in jade wind, played by 温迪's lyre.

A band of green air breathes in from every edge, and a wind current, mint with a white core, draws
itself round the screen clockwise from the top left, where the lyre Der Frühling (斐林) fades in,
rising, leaning as when it is played. Its strings shimmer left to right as if strummed, and the wind
leaves them in three strands, the longest running on to become the top border, letting go two white
feathers and a red maple leaf. Red maple leaves tumble in a wind curl in the top right and ride an
updraft in the bottom right, white feathers sway along the top and down the left, and a sprig of
white cecilias nods in the bottom left. Three chubby teal birds keep the frame: one on the lyre's crossbar
bobbing to each strum, one flying in on the gust to sit on the curl in the top right, one among the cecilias
puffing up on the downbeat. Now and then the strings are strummed again: they brighten in
turn, the glow swells and a breath of light runs out along the strands, while light runs clockwise
round the current. At the end the breeze lifts the feathers and leaves away and the band fades.

Its marks: the card is deep-jade glass with a mint edge, a white feather before the first name and a
red maple leaf before the second; the ring is a thin mint wind ribbon with a white core and a shimmer
running round it; the badge is the lyre, small, on a jade disc.
"""

from __future__ import annotations

import math
import os
import random
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPainterPathStroker, QPen, QPixmap, QPolygonF, QTransform

from blacklist_detect.love_scenes import DESIGN, Stage
from blacklist_detect.love_scenes.draw import ease_out, soft_dot, win
from blacklist_detect.love_scenes.light import blur, mask, noise, rgb, smooth
from blacklist_detect.love_scenes.light import picture as _picture

DURATION = 5.0
# The frame: deep pine at the edge, jade, meadow and anemo green inward; the wind mint with a white core.
PINE, JADE, MEADOW, ANEMO = "#0e4436", "#1f8a62", "#3fae7a", "#4fd1a0"
MINT, CORE = "#a8ecd0", "#f4fffa"
# Maple red, from lit vermilion to the deep red of its veins, and the ember on one leaf in five.
VERMILION, DEEP_MAPLE, EMBER = "#e2452b", "#8a1420", "#ec7a35"
FEATHER, FEATHER_SHADE = "#f7fbf8", "#c5d8d0"
HEART = "#e3f0b4"
LOOK = {
    # Its dot in the scene lists too: a jade green, well clear of 毛茸茸保护协会's teal beside it.
    "glow": (56, 182, 106),
    "rim": MINT,
    "band": (ANEMO, MINT),
    "card": ("#1d7a58", PINE),
    "edge": MINT,
    "ink": "#eefff7",
    "flowers": ((FEATHER, MINT, JADE), ("#fde3dc", VERMILION, "#c8202a")),
    "disc": (MEADOW, PINE),
    "heart": (MINT, JADE),
    "deep": JADE,
    "deep_glow": (63, 174, 122),
}
MARKS_ANIMATED = True
# Nothing stands over the card's top.
CARD_TOP = 0

# Light from the upper left.
LIGHT = np.array([-0.55, -0.68, 0.85], dtype=np.float32)
LIGHT /= np.linalg.norm(LIGHT)
# The moment the approved still shows; the drifting things are where it has them then.
STILL = 2.5
# The strums: when each starts and how long it takes from one string to the next. The first, slower,
# releases the feathers.
STRUMS = ((0.9, 0.06), (2.9, 0.07), (4.4, 0.07))
# The lyre's middle, in design points, and how far it leans when played.
LYRE_AT = (140.0, 146.0)
LEAN = 12.0
# The lyre's picture is made this many times the screen's sharpness, and made small as it is laid on.
SHARP = 1.5
# The birds (see _bird). One sits on the lyre's crossbar right of its pegs (in ref from the lyre's middle), facing
# right, and bobs on every strum. One flies in from off the right edge on the entrance's gust, from FLY[0] to FLY[1]
# seconds in, a flap every FLAP seconds, and lands on the curl in the top right facing left (its way in design points,
# a curve whose last point is the curl). One sits among the cecilias in the bottom left facing right, and puffs up on
# the music's downbeat, the first strum. Sitting, each breathes, sways a little, blinks and flicks a wing now and then.
PERCH = (53.0, -129.0)
FLY, FLAP = (0.25, 1.35), 0.24
WAY_IN = ((1690, 410), (1590, 390), (1575, 90), (1529, 121))
# The bird among the cecilias sits a little in front of the current, over the stalks' feet.
NEST = (88, 845)
# Each bird's small life as it sits (the lyre's, the flyer's, the cecilias'): when it blinks, when its wing flutters,
# and where in its breath it starts.
IDLE = (((2.2, 3.75), (1.55, 3.3), 0.0), ((2.3, 3.9), (2.6, 4.15), 1.9), ((1.7, 3.35, 4.15), (2.45, 3.9), 3.7))


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()

    def at(x: float, y: float, side: bool = False) -> QPointF:
        """A design point on this stage, kept to its corner, or (side) at its share of the edge's height."""
        sx = x * u if x < DESIGN[0] / 2 else width - (DESIGN[0] - x) * u
        if side:
            return QPointF(sx, y / DESIGN[1] * height)
        return QPointF(sx, y * u if y < DESIGN[1] / 2 else height - (DESIGN[1] - y) * u)

    def xy(x: float, y: float, side: bool = False) -> tuple[float, float]:
        point = at(x, y, side)
        return point.x(), point.y()

    lyre_at = at(*LYRE_AT)
    pt = U * LYRE_SCALE * u  # points per lyre ref

    def lyre_pt(x: float, y: float, angle: float, rise: float = 0.0) -> tuple[float, float]:
        rad = math.radians(angle)
        x, y = x * pt, y * pt
        return lyre_at.x() + x * math.cos(rad) - y * math.sin(rad), lyre_at.y() + rise + x * math.sin(rad) + y * math.cos(rad)

    still_angle = _angle(STILL)
    route = _route(width, height, 14 * u, 44 * u)
    run = _arclen(route)
    normals = _normals(route)
    strands = _strand_lines(lambda x, y: lyre_pt(x, y, still_angle), xy, u)
    # Where light may run along the current: not where it thins away into the gap round the button.
    open_run = ~((route[:, 1] > height - 60 * u) & (route[:, 0] > gap.left() - 50 * u) & (route[:, 0] < gap.right() + 50 * u))

    # (x, y, its angle, length, seed, kept to the side's height, drift in points a second, the way the breeze takes it)
    feathers = [
        (408, 58, -18, 62, 1, False, (9, 0), (1.0, -0.8)), (590, 38, 12, 50, 2, False, (8, 0), (1.0, -0.8)),
        (1190, 54, -30, 56, 3, False, (8, 0), (1.0, -0.8)), (1340, 100, 24, 46, 4, False, (9, -1), (1.0, -0.8)),
        (66, 320, 72, 66, 5, True, (0, -8), (-0.15, -1.0)), (106, 480, 108, 54, 6, True, (0, -7), (-0.15, -1.0)),
        (56, 620, 84, 60, 7, True, (0, -8), (-0.15, -1.0)),
    ]  # fmt: skip
    # (x, y, size, angle, flip phase, ember, kept to the side, drift, the way out)
    leaves = [
        (1584, 300, 29, 20, 0.4, False, True, (0, 8), (0.3, -1.0)), (1574, 470, 27, 130, 2.2, True, True, (0, 8), (0.3, -1.0)),
        (1590, 614, 28, 60, 4.0, False, True, (0, 7), (0.3, -1.0)), (1262, 796, 28, 200, 1.1, False, False, (-7, 0), (1.0, -0.35)),
        (1384, 774, 26, 300, 2.9, False, False, (-6, 0), (1.0, -0.35)), (420, 800, 27, 150, 5.2, False, False, (-7, 0), (-0.8, -0.6)),
    ]  # fmt: skip
    leaves = [(*rest[:4], _matched(rest[4], 1.7, 0.7), *rest[5:]) for rest in leaves]
    # Clear of the bird that lands on the curl between them.
    hero_leaves = [(1440, 80, 46, -24, 0.3, False, 1), (1598, 156, 38, 38, 1.9, True, 2), (1504, 162, 32, 76, 3.1, False, 3)]
    hero_leaves = [(x, y, r, a, _matched(ph, 1.1, 0.82), e, s) for x, y, r, a, ph, e, s in hero_leaves]
    updraft = [(1548, 766, 26, -40, _matched(0.9, 2.0, 0.6)), (1592, 698, 23, 30, _matched(2.4, 2.0, 0.6))]
    seeds = [(470, 118, 18, -20, False), (1424, 206, 15, 25, False), (152, 644, 16, 10, True), (1560, 690, 14, -30, True)]
    # The two feathers and the leaf the first strum lets go: where they settle, their angle, size and seed.
    released = [(262, 66, -32, 38, 31), (346, 128, -12, 34, 32)]
    released_leaf = (326, 50, 22, _matched(0.7, 1.6, 0.6))
    # The cecilia sprig: (stalk from, bend, flower at, size, angle); buds the same.
    sprig = [((60, 838), (40, 780), (72, 735), 30, -8), ((96, 842), (110, 790), (138, 768), 25, 14),
             ((34, 840), (20, 805), (30, 772), 21, -24)]  # fmt: skip
    buds = [((76, 840), (92, 760), (110, 722), 15, 18), ((48, 842), (60, 800), (160, 815), 13, 50)]

    def jobs(scale: float) -> list[tuple[float, str, object]]:
        """The pictures for this sharpness: (when first wanted, name, how)."""
        d = u * scale  # pixels per design point
        ss = 2 * d  # sprites are drawn twice too big and made small
        out = [
            (0.0, "band", lambda: _band(width, height, lyre_at, u, scale)),
            (0.2, "border", lambda: _border(route, run, normals, width, height, xy, u, scale)),
            (0.2, "strands", lambda: [_strokes_image([line], scale, d) for line in strands]),
            (0.2, "glint", lambda: _glint(scale)),
            (0.3, "curls", lambda: _curls(xy, u, scale)),
            (0.3, "lyre", lambda: _lyre_image(LEAN, SHARP * pt * scale)),
            (0.3, "aura", lambda: _aura(SHARP * pt * scale)),
            (0.3, "string", lambda: _string_glow(SHARP * pt * scale)),
        ]
        for k, (_b0, _b1, _top, size, angle) in enumerate(sprig):
            out.append((0.3, ("cecilia", k), lambda size=size, angle=angle, k=k: _cecilia(size * 0.72, angle, 40 + k, ss)))
        for k, (_b0, _b1, _top, size, angle) in enumerate(buds):
            out.append((0.3, ("bud", k), lambda size=size, angle=angle: _bud(size * 1.7, angle, ss)))
        for k, (_x, _y, r, angle, _ph, ember, seed) in enumerate(hero_leaves):
            out.append((0.3, ("hero", k), lambda r=r, angle=angle, ember=ember, seed=seed: _maple_pair(r, angle, ember, seed, ss)))
        for k, (x, _y, r, angle, _ph) in enumerate(updraft):
            out.append((0.3, ("updraft", k), lambda r=r, angle=angle, x=x: _maple_pair(r, angle, False, int(x), ss)))
        for k, (_x, _y, angle, length, seed) in enumerate(released):
            out.append((0.85, ("released", k), lambda angle=angle, length=length, seed=seed: _feather(length, angle, seed, ss)))
        out.append((0.85, "released-leaf", lambda: _maple_pair(released_leaf[2], 30.0, True, 33, ss)))
        for k, (_x, _y, angle, length, seed, *_rest) in enumerate(feathers):
            out.append((0.85, ("feather", k), lambda angle=angle, length=length, seed=seed: _feather(length, angle, seed, ss)))
        for k, (_x, _y, r, angle, _ph, ember, *_rest) in enumerate(leaves):
            out.append((0.85, ("leaf", k), lambda r=r, angle=angle, ember=ember, k=k: _maple_pair(r, angle, ember, 10 + k, ss)))
        out.append((0.85, "seed", lambda: _seed(18, ss)))
        for pose in ("up", "mid", "down", "sit", "blink", "lift"):
            out.append((0.2, ("bird", -1, pose), lambda pose=pose: _bird(pose, -1, ss)))
        for pose in ("sit", "blink", "lift"):
            out.append((0.3, ("bird", 1, pose), lambda pose=pose: _bird(pose, 1, ss)))
        return sorted(out, key=lambda job: job[0])

    # What the pictures hang on: the stage's size alone. The gap round the button (the cards' size with it) is
    # cut out of the band and the current as they are laid on (_Pictures.bared), so a new card size makes none again.
    shape = (round(width), round(height))

    def paint(p: QPainter, t: float) -> None:
        want = _sharpness(p)
        made = _made_near(shape, want) or _pictures(shape, want, jobs)
        # Drawn from pictures made for another sharpness (直播画面 from the screen's), sized by theirs.
        scale = made.scale
        art = made.bared(made.upto(t), gap, u)
        px = 2 * scale  # sprite pixels per point
        foot = FOOT * BIRD * u  # from a bird's middle down to its feet
        leave = smooth(0.0, 1.0, win(t, 4.4, 5.0))
        fade = 1 - leave
        life = t - 1.3
        lift = 160 * u * leave
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        # The band breathes in, and at the end fades.
        p.setOpacity(ease_out(win(t, 0.0, 0.5)) * fade)
        for rect, image in art["band"]:
            p.drawImage(rect, image)
        # The current draws itself clockwise from the lyre, its head a bright breath of wind.
        if "border" in art:
            reveal = smooth(0.0, 1.0, win(t, 0.2, 1.0))
            p.setOpacity(min(1.0, fade * 1.4))
            if reveal >= 1:
                for rect, image, _near in art["border"]:
                    p.drawImage(rect, image)
            elif reveal > 0:
                n = int(np.searchsorted(run, reveal * run[-1]))
                for rect, image, near in art["border"]:
                    if near[0] > n:
                        continue
                    if near[-1] <= n:
                        p.drawImage(rect, image)
                        continue
                    p.save()
                    p.setClipPath(_runs_path(route, near[near <= n], 160 * u))
                    p.drawImage(rect, image)
                    p.restore()
                hx, hy = route[min(n, len(route) - 1)]
                soft_dot(p, hx, hy, 18 * u, MINT, 0.7 * math.sin(math.pi * reveal) + 0.2)
                soft_dot(p, hx, hy, 7 * u, CORE, 0.8)
            _current_light(p, t, route, run, normals, open_run, art.get("glint"), u, fade)
        hero = ease_out(win(t, 0.3, 1.1)) * fade
        if "curls" in art and hero > 0:
            p.setOpacity(hero)
            for rect, image in art["curls"]:
                p.drawImage(rect, image)
        p.setOpacity(1.0)
        # Bottom left: the cecilias nod on their stalks.
        if hero > 0 and ("bud", 1) in art:
            nod = math.sin(life * 1.6) * 3
            _stalks(p, sprig, buds, xy, u, hero)
            if ("bird", 1, "blink") in art:
                x = t - STRUMS[0][0]
                puff = (1 - math.exp(-x / 0.06)) * math.exp(-x / 0.4) if x > 0 else 0.0
                pose, sx, sy, sway = _idle(t, 2)
                _sat(p, art["bird", 1, pose], *xy(*NEST), sway, 1.05 * sx * (1 + 0.1 * puff), 1.05 * sy * (1 + 0.08 * puff), hero, px, foot)
            for k, (_b0, _b1, top, _size, angle) in enumerate(sprig):
                turn = angle + nod * (1 if k % 2 else -1)
                _place(p, art["cecilia", k], *xy(*top), turn, 1, 0.82, hero, px)
            for k, (_b0, _b1, top, _size, angle) in enumerate(buds):
                _place(p, art["bud", k], *xy(*top), angle + nod, 1, 1, hero, px)
        # The lyre fades in rising 12 points, swaying as it plays.
        lyre_a = ease_out(win(t, 0.3, 0.9)) * fade
        rise = 12 * u * (1 - ease_out(win(t, 0.3, 0.9)))
        angle = _angle(t)
        strum = _strum(t)
        if lyre_a > 0 and "string" in art:
            _lyre(p, art, lyre_at.x(), lyre_at.y() + rise, angle, pt, SHARP * pt * scale, strum, lyre_a)
        # The wind leaves the strings in three strands, drawing out from them; each strum sends light along them.
        reveal = win(t, 0.2, 1.0)
        if reveal > 0 and "strands" in art:
            p.save()
            p.translate(0, rise)
            p.setOpacity(fade)
            for k, ((rect, image), (line, _widths, _level)) in enumerate(zip(art["strands"], strands, strict=True)):
                share = min(1.0, ease_out(reveal) * (2.2 - 0.3 * k))
                if share >= 1:
                    p.drawImage(rect, image)
                elif share > 0:
                    p.save()
                    p.setClipPath(_along_path(line[: max(2, int(len(line) * share))], 64 * u, Qt.RoundCap))
                    p.drawImage(rect, image)
                    p.restore()
            p.restore()
            _strand_light(p, t, strands, art.get("glint"), rise, u, fade)
            glow_k = sum(strum) / len(strum)
            for (x, y), r in zip(STARTS, (16, 13, 11), strict=True):
                sx, sy = lyre_pt(x, y, angle, rise)
                soft_dot(p, sx, sy, r * 2.0 * u, "#9ff5e0", min(1.0, 0.8 * reveal + 0.3 * glow_k) * fade)
                soft_dot(p, sx, sy, r * 0.9 * u, CORE, (0.45 * reveal + 0.3 * glow_k) * fade)
        # On the crossbar: the bird bobs on each strum, down and up and settling.
        if lyre_a > 0 and ("bird", 1, "blink") in art:
            bob = _bob(t)
            pose, sx, sy, sway = _idle(t, 0)
            _sat(p, art["bird", 1, pose], *lyre_pt(*PERCH, angle, rise), 0.35 * angle + 0.6 * sway, 0.66 * sx * (1 + 0.07 * bob),
                 0.66 * sy * (1 - 0.11 * bob), lyre_a, px, foot)
        # The feathers and the leaf the first strum lets go, carried from the strings to where they ride.
        parts = ease_out(win(t, 0.9, 1.4)) * fade
        if parts > 0 and "released-leaf" in art:
            carry = ease_out(win(t, 0.9, 1.6))
            for k, (x, y, ang, _length, _seed) in enumerate(released):
                sx, sy = lyre_pt(*STARTS[k], angle, rise)
                tx, ty = xy(x, y)
                tx += 5 * u * math.sin(life + k) + 8 * u * (t - STILL) + lift
                ty -= 3 * u * math.sin(life * 1.2 + k) + 2 * u * (t - STILL) + lift * 0.8
                sway = 8 * math.sin(life * 1.5 + k * 2)
                _place(p, art["released", k], sx + (tx - sx) * carry, sy + (ty - sy) * carry, ang + sway, 1,
                       0.92 + 0.08 * math.cos(life * 1.2 + k), parts, px)
            x, y, _r, phase = released_leaf
            tx, ty = xy(x, y)
            tx += 4 * u * math.sin(life) + 8 * u * (t - STILL) + lift
            ty -= lift * 0.8
            sx, sy = lyre_pt(*STARTS[0], angle, rise)
            _tumble(p, art["released-leaf"], sx + (tx - sx) * carry, sy + (ty - sy) * carry, 30 + life * 50, _flip(phase, 1.6, life), parts, px)
        # Top right: three maple leaves tumbling in the wind curl.
        if hero > 0 and ("hero", 2) in art:
            for k, (x, y, r, ang, phase, _ember, _seed) in enumerate(hero_leaves):
                cx, cy = xy(x, y)
                swirl = (t - STILL) * 0.9 + k * 2.1
                cx += 6 * u * (math.sin(swirl) - math.sin(k * 2.1)) + lift
                cy += 4 * u * (math.cos(swirl) - math.cos(k * 2.1)) - lift * 0.6
                spin = life * 40 * (0.3 if r > 25 else 0.6)
                _tumble(p, art["hero", k], cx, cy, ang + spin, _flip(phase, 1.1, life), hero, px)
        # The particles, all inside the band: feathers sway along the top and down the left, leaves tumble
        # down the right and along the bottom, a few seeds float.
        if parts > 0 and "seed" in art:
            drift = t - STILL
            for k, (x, y, ang, _length, _seed, side, (vx, vy), (ox, oy)) in enumerate(feathers):
                fx, fy = xy(x, y, side)
                sway = 7 * math.sin(life * 1.3 + k * 1.7)
                fx += 6 * u * math.sin(life * 0.9 + k) + vx * u * drift + ox * lift
                fy += vy * u * drift + oy * lift
                _place(p, art["feather", k], fx, fy, ang + sway, 1, 0.9 + 0.1 * math.cos(life * 1.1 + k * 2.3), parts * 0.97, px)
            for k, (x, y, _r, ang, phase, _ember, side, (vx, vy), (ox, oy)) in enumerate(leaves):
                lx, ly = xy(x, y, side)
                lx += vx * u * drift + ox * lift
                ly += vy * u * drift + oy * lift
                spin = life * 60 * (1 if k % 2 else -1)
                _tumble(p, art["leaf", k], lx, ly, ang + spin, _flip(phase, 1.7, life), parts, px)
            for x, y, size, ang, side in seeds:
                sx, sy = xy(x, y, side)
                sx += 4 * u * math.sin(life + x) + 0.5 * lift
                sy += -6 * u * drift - lift
                _place(p, art["seed"], sx, sy, ang + 6 * math.sin(life * 1.3 + y), size / 18, size / 18, parts * 0.4, px)
        # Leaves riding the updraft in the bottom right, rising with it.
        if hero > 0 and ("updraft", 1) in art:
            for k, (x, y, _r, ang, phase) in enumerate(updraft):
                lx, ly = xy(x, y)
                rise_k = (t - STILL) * 6 * u
                _tumble(p, art["updraft", k], lx + 3 * u * math.sin(life * 1.4 + k) + 0.3 * lift, ly - rise_k - lift,
                        ang + life * 90, _flip(phase, 2.0, life), hero, px)
        # The bird on the wind, flapping in from the right and landing on the curl.
        if t > FLY[0] and ("bird", -1, "blink") in art:
            way, pose, squash, hop = _flight(t)
            fx, fy = _bezier_at([xy(*point) for point in WAY_IN], way)
            if way < 1:
                nx, ny = _bezier_at([xy(*point) for point in WAY_IN], min(1.0, way + 0.02))
                tilt = max(-18.0, min(18.0, -math.degrees(math.atan2(ny - fy, fx - nx)) * 0.5)) if (nx, ny) != (fx, fy) else 0.0
                beat = math.sin((t - FLY[0]) / FLAP * 2 * math.pi)
                size = 0.88 + 0.12 * smooth(0.85, 1.0, way)
                _sat(p, art["bird", -1, pose], fx, fy - 3 * u * beat * (1 - way), tilt, size * 1.05, size * 0.95, fade, px, foot)
            else:
                idle, sx, sy, sway = _idle(t, 1)
                _sat(p, art["bird", -1, idle if pose == "sit" else pose], fx, fy - hop * u, sway, sx * (1 + 0.08 * squash),
                     sy * (1 - 0.12 * squash), fade, px, foot)
        p.restore()

    def warm(scale: float) -> None:
        """Every picture for scale pixels a point made now, off the screen's thread, and the gap cut out of them:
        the border starts the scene once they are, so its entrance plays from its first frame."""
        made = _pictures(shape, round(scale, 2), jobs)
        made.finish()
        made.bared(made.art, gap, u)

    paint.warm = warm
    return paint


def warm(width: float, height: float, scale: float) -> None:
    """The pictures for a stage this size at scale pixels a point made ahead, off the screen's thread, before a
    lobby asks for the scene: they do not hang on the gap, so a play there starts at once."""
    make(Stage(width, height, QRectF())).warm(scale)


class _Pictures:
    """One stage's pictures at one sharpness: those made, and the jobs still waiting, first wanted first."""

    def __init__(self, scale: float, jobs: list) -> None:
        self.scale = scale
        self.art: dict = {}
        self.waiting = jobs
        self.done = False
        self.lock = threading.Lock()
        # The band's and the current's squares near a gap, faded into it, by the gap: the last few kept.
        self._cut: dict[tuple, list] = {}

    def bared(self, art: dict, gap: QRectF, u: float) -> dict:
        """art with the gap round the button bare: the band's and the current's squares near it faded into it,
        as _bare fades them, made once for each gap."""
        if gap.isEmpty() or not ("band" in art or "border" in art):
            return art
        out = dict(art)
        for name in ("band", "border"):
            if name not in art:
                continue
            key = (name, gap.x(), gap.y(), gap.width(), gap.height(), u)
            cut = self._cut.get(key)
            if cut is None:
                cut = self._cut[key] = _cut_gap(art[name], gap, u, self.scale)
                while len(self._cut) > 8:
                    del self._cut[next(iter(self._cut))]
            out[name] = cut
        return out

    def upto(self, t: float) -> dict:
        """The pictures wanted t seconds in, made at once, and one more a frame ahead of time, so no frame waits long."""
        if not self.done:
            with self.lock:
                ran = False
                while self.waiting and (self.waiting[0][0] <= t + 0.05 or not ran):
                    _need, name, job = self.waiting.pop(0)
                    self.art[name] = job()
                    ran = True
                self.done = not self.waiting
        return self.art

    def finish(self) -> None:
        """Every picture still waiting, made several at a time."""
        with self.lock:
            jobs, self.waiting = self.waiting, []
            with ThreadPoolExecutor(WORKERS) as pool:
                made = list(pool.map(lambda job: job[2](), jobs))
            self.art.update((name, picture) for (_need, name, _job), picture in zip(jobs, made, strict=True))
            self.done = True


# How many pictures are made at once ahead of a play.
WORKERS = min(4, os.cpu_count() or 1)
# The pictures made for the last few stages and sharpnesses: a lobby on the same game, the 场景 hotkey pressed
# again and 直播画面 find theirs made.
KEEP = 4
_made: dict[tuple, _Pictures] = {}
_made_lock = threading.Lock()


def _pictures(shape: tuple, scale: float, jobs) -> _Pictures:  # noqa: ANN001
    """The pictures for a stage of this shape at scale pixels a point, kept; jobs(scale) lists what makes them."""
    with _made_lock:
        key = (*shape, scale)
        made = _made.pop(key, None) or _Pictures(scale, jobs(scale))
        _made[key] = made
        while len(_made) > KEEP:
            del _made[next(iter(_made))]
        return made


def _made_near(shape: tuple, scale: float) -> _Pictures | None:
    """This stage's pictures all made at scale, else at the sharpness nearest it; None when none are all made."""
    with _made_lock:
        done = [made for key, made in _made.items() if key[:-1] == shape and made.done]
    return min(done, key=lambda made: abs(made.scale - scale), default=None)


def _cut_gap(tiles: list, gap: QRectF, u: float, scale: float) -> list:
    """Squares (where, picture, ...) with the gap bare: those near it faded as _bare has it, those in it left out,
    the rest as they are."""
    reach = 46 * u
    out = []
    for tile in tiles:
        rect, image = tile[0], tile[1]
        if rect.right() < gap.left() - reach or rect.left() > gap.right() + reach or rect.bottom() < gap.top() - reach:
            out.append(tile)
            continue
        xs = rect.left() + np.arange(image.width(), dtype=np.float32) / scale
        ys = rect.top() + np.arange(image.height(), dtype=np.float32) / scale
        keep = _bare(xs[None, :], ys[:, None], gap, u)
        if keep.max() <= 0:
            continue
        if keep.min() >= 1:
            out.append(tile)
            continue
        level = np.ascontiguousarray((keep * 255 + 0.5).astype(np.uint8))
        mask = QImage(level.data, level.shape[1], level.shape[0], level.shape[1], QImage.Format_Alpha8)
        mask.setDevicePixelRatio(image.devicePixelRatio())
        faded = image.copy()
        p = QPainter(faded)
        p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        p.drawImage(0, 0, mask)
        p.end()
        out.append((rect, faded, *tile[2:]))
    return out


def _sharpness(p: QPainter) -> float:
    """Pixels per point where p draws: its screen's and its own scaling."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return round(ratio * math.hypot(p.transform().m11(), p.transform().m12()), 2)


def _angle(t: float) -> float:
    """The lyre's lean t seconds in: it sways a degree or so either way as it plays."""
    return LEAN + 1.2 * math.sin((t - 1.3) * 1.4)


def _strum(t: float) -> list[float]:
    """How bright each string is t seconds in: plucked in turn, left to right, dying away."""
    out = []
    for i in range(7):
        v = 0.0
        for when, step in STRUMS:
            x = t - when - i * step
            if x > 0:
                v += (1 - math.exp(-x / 0.025)) * math.exp(-x * 3.2)
        out.append(min(1.0, v))
    return out


def _flip(phase: float, speed: float, life: float) -> float:
    """A tumbling leaf's squash across its turn: -1..1, through edge-on (0) quickly, the sign its side."""
    c = math.cos(phase + life * speed)
    return math.copysign(math.sqrt(abs(c)), c)


def _matched(phase: float, speed: float, floor: float) -> float:
    """The phase that makes _flip at the still what the approved still has there: the leaf at the same
    squash, on the same side, turning the same way."""
    theta = phase + (STILL - 1.3) * speed
    c = math.cos(theta)
    target = math.copysign(max(floor, abs(c)), c)
    new = math.acos(math.copysign(target * target, target))
    if math.sin(theta) < 0:
        new = -new
    return new - (STILL - 1.3) * speed


def _place(p: QPainter, image: QImage, x: float, y: float, angle: float, sx: float, sy: float, alpha: float, px: float) -> None:
    """A picture of px pixels a point, centred on (x, y), turned by angle and squashed by sx and sy."""
    if alpha <= 0.01 or image is None:
        return
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.scale(sx / px, sy / px)
    p.setOpacity(alpha)
    p.drawImage(QPointF(-image.width() / 2, -image.height() / 2), image)
    p.restore()


def _tumble(p: QPainter, pair: tuple[QImage, QImage], x: float, y: float, angle: float, flip: float, alpha: float, px: float) -> None:
    """A maple leaf turning over: its face or its back as the side it shows, squashed by flip."""
    if abs(flip) < 0.04:
        return
    _place(p, pair[0] if flip > 0 else pair[1], x, y, angle, 1, flip, alpha, px)


def _sat(p: QPainter, image: QImage, x: float, y: float, angle: float, sx: float, sy: float, alpha: float, px: float, foot: float) -> None:
    """A bird's picture of px pixels a point, its feet (foot points below its middle) on (x, y), turned by angle
    and squashed by sx and sy about them."""
    if alpha <= 0.01 or image is None:
        return
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.scale(sx, sy)
    p.translate(0, -foot)
    p.scale(1 / px, 1 / px)
    p.setOpacity(alpha)
    p.drawImage(QPointF(-image.width() / 2, -image.height() / 2), image)
    p.restore()


def _idle(t: float, which: int) -> tuple[str, float, float, float]:
    """Sitting bird which's small life t seconds in (see IDLE): its pose, its eyes shut a moment now and then and
    its wing flicking off its side three times, its breath (its width and height, a few hundredths either way) and
    its sway, in degrees."""
    blinks, flutters, phase = IDLE[which]
    pose = "sit"
    if any(0 <= t - when < 0.36 and int((t - when) / 0.06) % 2 == 0 for when in flutters):
        pose = "lift"
    if any(0 <= t - when < 0.13 for when in blinks):
        pose = "blink"
    breath = math.sin(2 * math.pi * t / 1.7 + phase)
    return pose, 1 - 0.01 * breath, 1 + 0.025 * breath, 2.2 * math.sin(2 * math.pi * t / 2.9 + phase * 1.3)


def _bob(t: float) -> float:
    """How far the bird on the lyre is squashed (above 0) or stretched (below) t seconds in: down on each strum,
    up past where it sits, settling."""
    out = 0.0
    for when, _step in STRUMS:
        x = t - when
        if x > 0:
            out += math.sin(x * 2 * math.pi / 0.42) * math.exp(-x / 0.22)
    return out


def _flight(t: float) -> tuple[float, str, float, float]:
    """The flying bird t seconds in: how far along its way in (0..1, slowing to land), its pose, its squash as it
    lands, and (in points) how high it hops as it flaps once on the second strum."""
    k = win(t, *FLY)
    if k < 1:
        if k > 0.88:
            return 1 - (1 - k) ** 2, "up", 0.0, 0.0
        return 1 - (1 - k) ** 2, ("up", "mid", "down", "mid")[int((t - FLY[0]) / FLAP * 4) % 4], 0.0, 0.0
    x = t - FLY[1]
    squash = math.sin(x * 2 * math.pi / 0.4) * math.exp(-x / 0.16)
    if x < 0.1:
        return 1.0, "mid", squash, 0.0
    x = t - STRUMS[1][0]
    if 0 <= x < 0.32:
        pose = "mid" if x < 0.03 or 0.17 <= x < 0.25 else "up" if x < 0.17 else "down"
        return 1.0, pose, squash, 4 * math.sin(math.pi * x / 0.32)
    return 1.0, "sit", squash, 0.0


def _bezier_at(points: list, k: float) -> tuple[float, float]:
    """The point k along the cubic curve through points."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = points
    m = 1 - k
    return (m**3 * x0 + 3 * m * m * k * x1 + 3 * m * k * k * x2 + k**3 * x3, m**3 * y0 + 3 * m * m * k * y1 + 3 * m * k * k * y2 + k**3 * y3)


# Wind: lines of the current, gathered and lit together.


def _resample(points: np.ndarray, step: float) -> np.ndarray:
    s = _arclen(points)
    n = max(2, int(s[-1] / step))
    at = np.linspace(0, s[-1], n)
    return np.stack([np.interp(at, s, points[:, 0]), np.interp(at, s, points[:, 1])], axis=1)


def _arclen(points: np.ndarray) -> np.ndarray:
    return np.concatenate([[0], np.cumsum(np.hypot(*np.diff(points, axis=0).T))])


def _tangents(points: np.ndarray) -> np.ndarray:
    d = np.gradient(points, axis=0)
    return d / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-6)[:, None]


def _normals(points: np.ndarray) -> np.ndarray:
    """Unit normals to the right of travel: inward, for a line going round the screen clockwise."""
    t = _tangents(points)
    return np.stack([-t[:, 1], t[:, 0]], axis=1)


def _route(width: float, height: float, inset: float, radius: float) -> np.ndarray:
    """The current's line, clockwise from just right of the top-left corner, back round to it."""
    i, r = inset, radius
    pts = []

    def line(a: tuple[float, float], b: tuple[float, float]) -> None:
        for k in np.linspace(0, 1, 200, endpoint=False):
            pts.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))

    def arc(cx: float, cy: float, a0: float) -> None:
        for k in np.linspace(0, 1, 30, endpoint=False):
            a = math.radians(a0 + 90 * k)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    w, h = width, height
    line((i + r, i), (w - i - r, i))
    arc(w - i - r, i + r, -90)
    line((w - i, i + r), (w - i, h - i - r))
    arc(w - i - r, h - i - r, 0)
    line((w - i - r, h - i), (i + r, h - i))
    arc(i + r, h - i - r, 90)
    line((i, h - i - r), (i, i + r))
    arc(i + r, i + r, 180)
    pts.append((i + r, i))
    return _resample(np.array(pts, dtype=np.float64), 2.0)


def _bezier(p0, p1, p2, p3, n: int = 120) -> np.ndarray:  # noqa: ANN001
    k = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = (np.array(q, dtype=np.float64) for q in (p0, p1, p2, p3))
    return (1 - k) ** 3 * p0 + 3 * (1 - k) ** 2 * k * p1 + 3 * (1 - k) * k * k * p2 + k ** 3 * p3


def _curl(end: np.ndarray, tangent: np.ndarray, r0: float, turns: float, side: int, shrink: float = 0.6) -> np.ndarray:
    """A spiral carrying on from end along tangent, turning to side (+1 right of travel, -1 left)."""
    perp = np.array([-tangent[1], tangent[0]]) * side
    c = end + perp * r0
    a0 = math.atan2(end[1] - c[1], end[0] - c[0])
    inc = np.array([-math.sin(a0), math.cos(a0)])
    sign = 1 if inc @ tangent > 0 else -1
    th = np.linspace(0, 2 * math.pi * turns, int(120 * turns) + 2)
    r = r0 * (1 - shrink * th / th[-1])
    return np.stack([c[0] + r * np.cos(a0 + sign * th), c[1] + r * np.sin(a0 + sign * th)], axis=1)


def _ribbon_polygon(points: np.ndarray, widths: np.ndarray) -> QPolygonF:
    n = _normals(points)
    edge = np.concatenate([points + n * (widths / 2)[:, None], (points - n * (widths / 2)[:, None])[::-1]])
    return QPolygonF([QPointF(float(x), float(y)) for x, y in edge])


def _along_path(points: np.ndarray, wide: float, cap: Qt.PenCapStyle = Qt.FlatCap) -> QPainterPath:
    """The area within wide / 2 of a line, to show what has been drawn of it."""
    step = max(1, len(points) // 400)
    line = QPainterPath(QPointF(*points[0]))
    for x, y in points[step::step]:
        line.lineTo(QPointF(x, y))
    line.lineTo(QPointF(*points[-1]))
    stroker = QPainterPathStroker()
    stroker.setWidth(wide)
    stroker.setCapStyle(cap)
    stroker.setJoinStyle(Qt.RoundJoin)
    return stroker.createStroke(line)


def _over(color: np.ndarray, alpha: np.ndarray, c: np.ndarray, a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """c at a laid over color at alpha, all straight color: color and alpha changed in place, only over
    the box where a is."""
    rows, cols = np.flatnonzero(a.max(axis=1) > 0), np.flatnonzero(a.max(axis=0) > 0)
    if not len(rows):
        return color, alpha
    box = (slice(rows[0], rows[-1] + 1), slice(cols[0], cols[-1] + 1))
    a = np.clip(a[box], 0, 1)
    c = c[box] if np.ndim(c) == 3 and c.shape[:2] == alpha.shape else c
    below = alpha[box]
    out = a + below * (1 - a)
    color[box] = (np.broadcast_to(c, a.shape + (3,)) * a[..., None] + color[box] * (below * (1 - a))[..., None]) / np.maximum(out, 1e-5)[..., None]
    alpha[box] = out
    return color, alpha


def _light(light: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Light (may run over 1) as straight color and alpha, as light.glow makes it."""
    light = np.maximum(light, 0)
    light = light + np.clip(light.max(axis=-1, keepdims=True) - 1, 0, None) * 0.6
    alpha = np.clip(light.max(axis=-1), 0, 1)
    return np.clip(light, 0, 1) / np.maximum(alpha, 1e-4)[..., None], alpha


def _relief(height: np.ndarray, gain: float, light: np.ndarray = LIGHT) -> tuple[np.ndarray, np.ndarray]:
    """Diffuse and specular light on a height field."""
    gy, gx = np.gradient(height)
    nx, ny, nz = -gx * gain, -gy * gain, np.ones_like(height)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / n, ny / n, nz / n
    diffuse = np.clip(nx * light[0] + ny * light[1] + nz * light[2], 0, 1)
    half = light + np.array([0, 0, 1], dtype=np.float32)
    half /= np.linalg.norm(half)
    spec = np.clip(nx * half[0] + ny * half[1] + nz * half[2], 0, 1) ** 28
    return diffuse, spec


def _lit_strokes(lines: list, rect: QRectF, scale: float, d: float) -> tuple[np.ndarray, np.ndarray]:
    """Ribbons (points, widths, level) of the current over rect, lit from the upper left: a shadow in deep
    pine, a halo of anemo green, the mint body and its white core, as straight color and alpha."""
    w, h = max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale))

    def draw(core: bool):  # noqa: ANN202
        def go(q: QPainter) -> None:
            q.scale(scale, scale)
            q.translate(-rect.left(), -rect.top())
            q.setPen(Qt.NoPen)
            for points, widths, level in lines:
                level = np.broadcast_to(np.asarray(level, dtype=np.float64), widths.shape)
                for i in range(0, len(points) - 1, 16):
                    j = min(len(points), i + 18)
                    wide = widths[i:j] * (0.26 if core else 1.0)
                    if core:
                        wide = np.where(widths[i:j] > 1.2 * d / scale, np.maximum(wide, 0.9 * d / scale), wide * 0.6)
                    if wide.max() < 0.15 * d / scale:
                        continue
                    v = float(level[i:j].mean()) if not core else 1.0
                    q.setBrush(QColor.fromRgbF(v, v, v))
                    q.drawPolygon(_ribbon_polygon(points[i:j], wide))
        return go

    body, core = mask(w, h, draw(False)), mask(w, h, draw(True))
    solid = np.clip(body * 3, 0, 1)
    shift = max(1, round(2 * d))
    shadow = np.roll(np.roll(blur(solid, 2.2 * d), shift, axis=0), shift, axis=1)
    color = np.zeros((h, w, 3), dtype=np.float32)
    alpha = np.zeros((h, w), dtype=np.float32)
    color, alpha = _over(color, alpha, rgb(PINE), shadow * 0.55)
    halo = blur(body, 4.0 * d) * 0.55 + blur(body, 12.0 * d) * 0.35
    color, alpha = _over(color, alpha, *_light(halo[..., None] * rgb(ANEMO)[None, None, :] * 0.85))
    diffuse, _ = _relief(blur(solid, 1.1 * d), 3.0 * d)
    lit = np.clip(0.55 + 0.6 * diffuse, 0, 1.2)
    body_c = rgb(MINT) * lit[..., None] * (0.82 + 0.25 * body)[..., None] * (1 - 0.35 * (1 - body))[..., None]
    color, alpha = _over(color, alpha, body_c, solid * 0.92)
    color, alpha = _over(color, alpha, *_light(blur(core, 0.6 * d)[..., None] * rgb(CORE)[None, None, :] * 1.15))
    return color, alpha


def _bounds(lines: list, room: float) -> QRectF:
    pts = np.concatenate([points for points, _w, _l in lines])
    return QRectF(pts[:, 0].min() - room, pts[:, 1].min() - room, np.ptp(pts[:, 0]) + 2 * room, np.ptp(pts[:, 1]) + 2 * room)


def _strokes_image(lines: list, scale: float, d: float) -> tuple[QRectF, QImage]:
    rect = _bounds(lines, 34 * d / scale)
    color, alpha = _lit_strokes(lines, rect, scale, d)
    return rect, _picture(color, alpha)


def _tiles(color: np.ndarray, alpha: np.ndarray, scale: float, size: int = 128, origin: QPointF | None = None) -> list[tuple[QRectF, QImage]]:
    """A picture made at scale with its top left at origin, cut into squares, leaving out the empty ones:
    (where, picture)."""
    left, top = (origin.x(), origin.y()) if origin is not None else (0.0, 0.0)
    out = []
    h, w = alpha.shape
    for y in range(0, h, size):
        for x in range(0, w, size):
            a = alpha[y : y + size, x : x + size]
            if a.max() < 0.5 / 255:
                continue
            image = _picture(color[y : y + size, x : x + size], a)
            out.append((QRectF(left + x / scale, top + y / scale, a.shape[1] / scale, a.shape[0] / scale), image))
    return out


def _bare(xs: np.ndarray, ys: np.ndarray, gap: QRectF, u: float) -> np.ndarray:
    """1 away from the gap round the button, fading to 0 in it."""
    dx = np.maximum(np.maximum(gap.left() - xs, xs - gap.right()), 0)
    dy = np.maximum(gap.top() - ys, 0)
    return smooth(0.0, 46 * u, np.hypot(dx, dy))


def _grid(w: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    return xs, ys


def _ramp(stops: list[tuple[float, str]], k: np.ndarray) -> np.ndarray:
    """A color per pixel along stops (position, color)."""
    at = [where for where, _color in stops]
    colors = np.array([rgb(color) for _where, color in stops])
    return np.stack([np.interp(k, at, colors[:, channel]).astype(np.float32) for channel in range(3)], axis=-1)


def _band(width: float, height: float, lyre: QPointF, u: float, scale: float) -> list[tuple[QRectF, QImage]]:
    """The green air from every edge inward, strong at the edge and gone well before the names, thinner
    over the title, streaked along each edge so it reads as moving air, a meadow glow behind the lyre. The gap
    round the button is cut out as it is laid on (_cut_gap)."""
    w, h = math.ceil(width * scale), math.ceil(height * scale)
    d = u * scale
    xs, ys = _grid(w, h)
    xs, ys = xs / scale, ys / scale
    title = np.exp(-(((xs - width * 890 / DESIGN[0]) / (230 * u)) ** 4))
    sides = [(xs, 190.0, 1.0), (width - xs, 110.0, 1.0), (ys, 210.0 - 70 * title, 1.0 - 0.3 * title), (height - ys, 120.0, 1.0)]
    keep = np.ones((h, w), dtype=np.float32)
    depth = np.full((h, w), 9.0, dtype=np.float32)
    for dist, reach, strength in sides:
        reach = reach * u
        a = 1 - smooth(0.0, 1.0, (dist - 22 * u) / (reach - 22 * u))
        keep *= 1 - 0.84 * a ** 1.25 * strength
        depth = np.minimum(depth, dist / reach)
    alpha = 1 - keep
    columns = (np.arange(w) // 12).astype(int)
    rows = (np.arange(h) // 12).astype(int)
    across = blur(noise(w // 12 + 3, h, 4.0 * d, 3, 21)[:, columns], 2.0 * d)
    down = blur(noise(w, h // 12 + 3, 4.0 * d, 3, 22)[rows, :], 2.0 * d)
    horizontal = blur((np.minimum(ys, height - ys) / 1.6 < np.minimum(xs, width - xs)).astype(np.float32), 30 * d)
    streak = across * horizontal + down * (1 - horizontal)
    clouds = noise(w, h, 140 * d, 4, 23)
    fine = np.random.default_rng(5).random((h, w), dtype=np.float32)
    alpha = alpha * (0.78 + 0.45 * (streak - 0.5) + 0.3 * (clouds - 0.5))
    color = _ramp([(0.0, PINE), (0.16, "#14573f"), (0.38, JADE), (0.72, ANEMO), (1.0, ANEMO)], depth)
    tone = 1 + 0.22 * (streak - 0.5) + 0.06 * (fine - 0.5)
    tone *= 1.08 - 0.16 * np.clip((xs / width) * 0.6 + (ys / height) * 0.4, 0, 1)
    color = color * tone[..., None]
    g = (1 - smooth(0, 270 * u, np.hypot(xs - lyre.x(), ys - lyre.y()))) ** 1.6
    color = color * (1 - 0.6 * g[..., None]) + rgb(MEADOW) * (0.6 * g[..., None]) + rgb("#bff5dc") * (0.18 * g ** 3)[..., None]
    alpha = np.maximum(alpha, 0.8 * g)
    alpha = np.clip(alpha, 0, 0.9)
    return _tiles(color, alpha, scale)


def _border(route, run, normals, width, height, xy, u, scale) -> list[tuple[QRectF, QImage]]:  # noqa: ANN001
    """The current round the edge, as at the still: swelling and thinning in long waves, a thinner strand
    braiding inside it, and twice a side a ribbon peeling off in one loose open turn. It fades into the gap
    round the button as it is laid on (_cut_gap)."""
    d = u * scale
    phase = (STILL - 1.3) * 2.2
    s = run
    line = route + normals * (2.0 * u * np.sin(2 * np.pi * s / (360 * u) - phase * 0.8 + 0.7))[:, None]
    wide = (3.9 + 1.0 * np.sin(2 * np.pi * s / (420 * u) - phase) + 0.3 * np.sin(2 * np.pi * s / (170 * u) + 1.3)) * u
    level = 0.72 + 0.28 * (0.5 + 0.5 * np.sin(2 * np.pi * s / (520 * u) - phase * 1.2))
    lines = [(line, wide, level)]
    envelope = np.clip(np.sin(2 * np.pi * s / (760 * u) - phase * 0.5 + 1.0), 0, 1) ** 1.5
    braid = route + normals * ((7 + 3.5 * np.sin(2 * np.pi * s / (240 * u) - phase * 1.3)) * u)[:, None]
    thin = 1.6 * u * envelope
    lines.append((braid, thin, 0.6))
    tang = _tangents(route)
    peels = [((428, 14, False), 22), ((1298, 14, False), 20), ((1621, 325, True), 17), ((1621, 565, True), 17),
             ((1243, 834, False), 20), ((293, 834, False), 22), ((14, 489, True), 18), ((14, 189, True), 18)]  # fmt: skip
    for (x, y, side), r in peels:
        px, py = xy(x, y, side)
        i = int(np.argmin(np.hypot(route[:, 0] - px, route[:, 1] - py)))
        r = r * u
        psi = np.linspace(0, 2 * np.pi, 160)
        n = r * (1 - np.cos(psi))
        a = 0.62 * r * psi + r * np.sin(psi) + 0.35 * n  # leaning with the wind
        loop = line[i] + tang[i] * a[:, None] + normals[i] * n[:, None]
        lines.append((loop, (0.6 + 2.4 * np.sin(psi / 2) ** 0.8) * u, 0.95))
    # Worked out in four strips along the edges, each with room round it so its glow has no seams.
    deep, room = math.ceil(124 * u * scale) / scale, math.ceil(40 * u * scale) / scale
    strips = [QRectF(0, 0, width, deep), QRectF(0, height - deep, width, deep),
              QRectF(0, deep, deep, height - 2 * deep), QRectF(width - deep, deep, deep, height - 2 * deep)]  # fmt: skip
    tiles = []
    for strip in strips:
        grown = strip.adjusted(-room, -room, room, room)
        color, alpha = _lit_strokes(lines, grown, scale, d)
        cut = round(room * scale)
        color, alpha = color[cut:-cut, cut:-cut], alpha[cut:-cut, cut:-cut]
        tiles += _tiles(color, alpha, scale, origin=strip.topLeft())
    # For each square, the points of the current near it, to show it as the current is drawn.
    out = []
    for rect, image in tiles:
        near = rect.adjusted(-90 * u, -90 * u, 90 * u, 90 * u)
        inside = (route[:, 0] > near.left()) & (route[:, 0] < near.right()) & (route[:, 1] > near.top()) & (route[:, 1] < near.bottom())
        out.append((rect, image, np.flatnonzero(inside) if inside.any() else np.array([0])))
    return out


def _runs_path(route: np.ndarray, index: np.ndarray, wide: float) -> QPainterPath:
    """The area within wide / 2 of the stretches of the route at these points (indices, in order)."""
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    for run in np.split(index, np.flatnonzero(np.diff(index) > 1) + 1):
        if len(run) > 1:
            path.addPath(_along_path(route[run], wide))
    return path


def _curls(xy, u: float, scale: float) -> list[tuple[QRectF, QImage]]:  # noqa: ANN001
    """The wind in the two right corners: a curl leaving the top border, the leaves' home, and an updraft
    of two rising arcs in the bottom right."""
    d = u * scale
    top = []
    lead = _bezier(xy(1390, 14), xy(1450, 16), xy(1500, 22), xy(1540, 34), 60)
    line = np.concatenate([lead, _curl(lead[-1], _tangents(lead)[-1], 52 * u, 1.05, 1, 0.62)[1:]])
    k = np.linspace(0, 1, len(line))
    top.append((line, (3.4 * (1 - k) ** 0.7 + 0.4) * u, 0.9))
    lead = _bezier(xy(1450, 14), xy(1500, 20), xy(1560, 30), xy(1592, 52), 60)
    line = np.concatenate([lead, _curl(lead[-1], _tangents(lead)[-1], 34 * u, 0.8, 1, 0.5)[1:]])
    top.append((line, (1.8 * (1 - np.linspace(0, 1, len(line))) + 0.3) * u, 0.7))
    low = []
    for p0, p1, p2, p3, r0, wmax in (((1452, 846), (1515, 836), (1560, 790), (1574, 728), 22, 4.2),
                                     ((1530, 848), (1585, 838), (1612, 800), (1612, 752), 15, 3.0)):  # fmt: skip
        arc = _bezier(xy(*p0), xy(*p1), xy(*p2), xy(*p3), 70)
        line = np.concatenate([arc, _curl(arc[-1], _tangents(arc)[-1], r0 * u, 0.85, -1, 0.5)[1:]])
        k = np.linspace(0, 1, len(line))
        low.append((line, (wmax * np.sin(np.pi * np.clip(k * 1.3, 0, 1) * 0.5 + 0.2) * (1 - k) ** 0.4 + 0.3) * u, 0.85))
    return [_strokes_image(lines, scale, d) for lines in (top, low)]


def _strand_lines(lyre_pt, xy, u: float) -> list:  # noqa: ANN001
    """The three strands of wind leaving the strings, above the lilies: (points, widths, level), the
    longest running on into the top border, the others ending in a curl."""
    strands = [
        (lyre_pt(*STARTS[0]), lyre_pt(95, -150), xy(250, 30), xy(350, 15), 1.2, 4.8, None),
        (lyre_pt(*STARTS[1]), lyre_pt(115, -110), xy(262, 72), xy(310, 62), 1.1, 4.0, (17, 0.95, -1)),
        (lyre_pt(*STARTS[2]), lyre_pt(110, -80), xy(268, 122), xy(302, 110), 0.9, 3.2, (13, 0.9, -1)),
    ]
    out = []
    life = STILL - 1.3
    for k, (p0, p1, p2, p3, w0, w1, end) in enumerate(strands):
        line = _bezier(p0, p1, p2, p3, 140)
        if end is not None:
            r0, turns, side = end
            line = np.concatenate([line, _curl(line[-1], _tangents(line)[-1], r0 * u, turns, side, 0.55)[1:]])
        k_ = np.linspace(0, 1, len(line))
        if end is None:
            wide = w0 + (w1 - w0) * k_ ** 0.8
        else:
            wide = (w0 + (w1 - w0) * np.sin(np.pi * np.clip(k_ * 1.25, 0, 1) / 2)) * (1 - k_) ** 0.35 + 0.25
        wide = wide * (0.85 + 0.15 * np.sin(2 * np.pi * k_ * 3 - life * 3 + k)) * u
        out.append((line, wide, 0.95 - 0.08 * k))
    return out


def _glint(scale: float) -> QImage:
    """A breath of light along the wind: a soft streak, white at its heart, 40 by 9 points, made at scale."""
    w, h = math.ceil(40 * scale), math.ceil(9 * scale)
    xs, ys = _grid(w, h)
    x, y = (xs / w - 0.5) * 2, (ys / h - 0.5) * 2
    k = np.exp(-(x * x) * 3.0 - (y * y) * 5.0)
    light = k[..., None] * rgb(MINT) * 0.9 + (k ** 4)[..., None] * rgb(CORE) * 0.8
    return _picture(*_light(light))


def _current_light(p: QPainter, t: float, route, run, normals, open_run, glint: QImage | None, u: float, fade: float) -> None:  # noqa: ANN001
    """Breaths of light running clockwise along the current once it is drawn."""
    if glint is None or t < 0.9:
        return
    on = win(t, 0.9, 1.4) * fade
    total = run[-1]
    for j in range(7):
        age = (t - 0.9 - j * 0.45) % 3.15
        if age > 1.3:
            continue
        where = (j * 0.37 * total + 300 * u * (t - 0.9)) % total
        i = min(len(route) - 1, int(np.searchsorted(run, where)))
        if not open_run[i]:
            continue
        x, y = route[i]
        angle = math.degrees(math.atan2(-normals[i][0], normals[i][1]))
        _place(p, glint, x, y, angle, u, u, on * math.sin(math.pi * age / 1.3) * 0.85, glint.width() / 40)


def _strand_light(p: QPainter, t: float, strands: list, glint: QImage | None, rise: float, u: float, fade: float) -> None:
    """After each strum a breath of light runs out along each strand from the strings."""
    if glint is None:
        return
    for when, _step in STRUMS:
        for k, (line, _w, _l) in enumerate(strands):
            q = (t - when - 0.2 - 0.06 * k) / 0.9
            if not 0 < q < 1:
                continue
            i = min(len(line) - 2, int(q * (len(line) - 1)))
            dx, dy = line[i + 1] - line[i]
            _place(p, glint, line[i][0], line[i][1] + rise, math.degrees(math.atan2(dy, dx)), 0.8 * u, 0.8 * u,
                   math.sin(math.pi * q) * fade, glint.width() / 40)


def _stalks(p: QPainter, sprig: list, buds: list, xy, u: float, alpha: float) -> None:  # noqa: ANN001
    """The cecilias' curved stalks and the two slender blade leaves at their root."""
    p.save()
    p.setOpacity(alpha)
    for b0, b1, b2, _size, _angle in sprig + buds:
        path = QPainterPath(QPointF(*xy(*b0)))
        path.quadTo(QPointF(*xy(*b1)), QPointF(*xy(*b2)))
        p.setPen(QPen(QColor(PINE), 3.4 * u, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path.translated(1 * u, 1 * u))
        p.setPen(QPen(QColor("#4f9f6e"), 2.4 * u, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
        p.setPen(QPen(QColor("#9be0b4"), 0.8 * u, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path.translated(-0.6 * u, -0.4 * u))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#3c8f5e"))
    for x0, y0, cx, cy, x1, y1 in ((50, 846, 70, 800, 112, 790), (40, 846, 18, 812, 8, 770)):
        blade = QPainterPath(QPointF(*xy(x0, y0)))
        blade.quadTo(QPointF(*xy(cx + 6, cy)), QPointF(*xy(x1, y1)))
        blade.quadTo(QPointF(*xy(cx - 6, cy + 10)), QPointF(*xy(x0 + 6, y0)))
        p.drawPath(blade)
    p.restore()


# The lyre: Der Frühling (斐林), drawn close to its in-game render: a tall rose-brown U on a small flat foot,
# its horn tips standing above a thin crossbar with 7 pale-gold pegs, 7 glowing strings in one bright block
# down to a pale bridge, a teal gem in a pale-gold star with gold blade flourishes on the bowl, and two white
# cecilias with long leaves over the lower right arm. Drawn in the reference picture's pixels ("ref": the
# lyre is 357 ref tall), centred on (CX, CY), U * LYRE_SCALE design points a ref.

WOOD = [(-0.2, "#4a2c20"), (0.15, "#6e4836"), (0.45, "#956450"), (0.7, "#a8765f"), (0.92, "#bf8e72"), (1.2, "#dcb298")]
GOLD = [(-0.1, "#6a4e28"), (0.25, "#a8843f"), (0.55, "#d6b26c"), (0.85, "#f0d79e"), (1.15, "#fff6dc")]
GEM = [(0.0, "#0a4a44"), (0.4, "#14897a"), (0.75, "#2fc0aa"), (1.05, "#b9f6e8")]
LEAF = [(0.0, "#3a5428"), (0.4, "#62803f"), (0.75, "#8aa55a"), (1.05, "#bfd08d")]
BRIDGE = [(0.0, "#5e4a30"), (0.45, "#9c875f"), (0.85, "#d2c196"), (1.15, "#f1e8cc")]
PETAL, PETAL_SHADE, PETAL_LINE = "#f7f4d8", "#c9c8a2", "#5d6448"
STAMEN, STAMEN_LIT = "#7f6ad0", "#cbbcf6"
STRING_CORE, ANEMO_TEAL = "#e8fffa", "#5fd3d0"
OUTLINE = "#2e1a12"
LYRE_SCALE = 1.14
U = 0.533
CX, CY = 155.0, 190.0
PEG_X = [129.3 + 8.8 * i for i in range(7)]
STRING_X = [121.5 + 11.17 * i for i in range(7)]
STRING_Y = (58.0, 206.5)
# Where the wind leaves the strings, in ref from the lyre's middle.
STARTS = [(11.2, -110.0), (22.3, -75.0), (0.0, -40.0)]
# The left half of the outline: the outer edge from the horn tip down to the foot, and the inner edge from
# the tip down to the bottom of the opening beside the tongue that carries the bridge.
OUTER = [(80, 9), (82, 22), (84, 34), (86, 48), (86, 64), (83, 80), (79, 96), (74, 112), (69, 128), (64, 144), (59, 160),
         (55, 176), (51, 192), (49, 208), (48, 224), (49, 240), (51, 256), (56, 272), (64, 288), (76, 304), (93, 320),
         (107, 330), (121, 337)]  # fmt: skip
INNER = [(80, 9), (86, 19), (91, 28), (95, 37), (98, 47), (100, 58), (101, 70), (101, 84), (100, 98), (98, 112), (95, 128),
         (92, 144), (89, 160), (87, 176), (85, 192), (86, 206), (89, 219), (96, 229), (106, 234), (114, 235)]  # fmt: skip
# The gold blade left of the gem: its smooth upper edge, then the feathers cut along its lower edge.
BLADE_TOP = [(57, 220), (78, 231), (100, 245), (119, 260), (133, 276), (142, 294)]
BLADE_LOW = [(131, 290), (127, 285), (107, 304), (112, 276), (101, 267), (82, 295), (86, 256), (77, 248), (67, 238)]
BLADE_SMALL = [(149, 300), (131, 302), (114, 309), (128, 310), (134, 314), (141, 325), (143, 313), (148, 309)]
# Leaves (base, control, tip, width), and lilies: their middle, then each petal (angle, length, width as a
# share of length) from the back to the front.
LEAVES = [((262, 196), (300, 170), (318, 112), 12.5), ((240, 178), (244, 160), (252, 140), 8.0),
          ((258, 236), (288, 228), (311, 213), 8.0)]  # fmt: skip
LILIES = [((249, 183), [(-70, 46, 0.5), (-133, 42, 0.5), (0, 48, 0.55), (95, 38, 0.5), (41, 44, 0.58), (164, 52, 0.66)]),
          ((223, 236), [(-62, 36, 0.5), (-127, 38, 0.52), (131, 42, 0.55), (0, 48, 0.62), (190, 48, 0.66), (64, 66, 0.34)])]  # fmt: skip


def _local_light(angle: float, flip: float = 1.0) -> np.ndarray:
    """The light as a picture turned by angle degrees (Qt, clockwise) and flipped by flip sees it."""
    a = math.radians(-angle)
    x = LIGHT[0] * math.cos(a) - LIGHT[1] * math.sin(a)
    y = LIGHT[0] * math.sin(a) + LIGHT[1] * math.cos(a)
    v = np.array([x, y * (1 if flip >= 0 else -1), LIGHT[2]], dtype=np.float32)
    return v / np.linalg.norm(v)


def _spline(points, n: int = 10) -> np.ndarray:  # noqa: ANN001
    """A Catmull-Rom curve through points, n samples a span."""
    pts = np.array(points, dtype=np.float64)
    pts = np.vstack([pts[0] * 2 - pts[1], pts, pts[-1] * 2 - pts[-2]])
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-2])
    return np.array(out)


def _mirror(points) -> np.ndarray:  # noqa: ANN001
    pts = np.array(points, dtype=np.float64)
    return np.stack([2 * CX - pts[:, 0], pts[:, 1]], axis=1)


def _poly(points) -> QPainterPath:  # noqa: ANN001
    """A closed path through points (ref), moved to the lyre's middle."""
    path = QPainterPath()
    path.addPolygon(QPolygonF([QPointF(float(x) - CX, float(y) - CY) for x, y in points]))
    path.closeSubpath()
    return path


def _ref(x: float, y: float) -> QPointF:
    return QPointF(x - CX, y - CY)


def _strip(line: np.ndarray, w: np.ndarray) -> QPainterPath:
    """A filled ribbon of widths w along line."""
    n = _normals(line)
    edge = np.concatenate([line + n * (w / 2)[:, None], (line - n * (w / 2)[:, None])[::-1]])
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    path.addPolygon(QPolygonF([QPointF(float(x), float(y)) for x, y in edge]))
    path.closeSubpath()
    return path


def _lyre_parts() -> dict:
    """The lyre's parts upright, in ref, about its middle."""
    outer, inner = _spline(OUTER), _spline(INNER)
    tongue = [(196, 235), (191, 216), (119, 216), (114, 235)]
    body = _poly(np.concatenate([outer, _mirror(outer)[::-1], _mirror(inner), tongue, inner[::-1]]))
    foot = QPainterPath()
    foot.addRect(QRectF(_ref(120, 332), _ref(190, 348)))
    base = QPainterPath()
    base.addRoundedRect(QRectF(_ref(108, 347), _ref(202, 366)), 3, 3)
    bridge = QPainterPath()
    bridge.addRoundedRect(QRectF(_ref(115, 206.5), _ref(195, 216)), 2, 2)
    rod = QPainterPath()
    rod.addRoundedRect(QRectF(_ref(74, 46.5), _ref(238, 57.5)), 3, 3)
    rod.addPath(_poly([(44, 52), (58, 46.5), (68, 46), (72, 48.5), (72, 56), (68, 58), (58, 57.5)]))
    rod.addRect(QRectF(_ref(238, 48.8), _ref(241, 55.6)))
    rod.setFillRule(Qt.WindingFill)
    cap = QPainterPath()
    cap.addEllipse(_ref(248.5, 52.2), 8.5, 5.0)
    collars = QPainterPath()
    for x in (71.5, 233.5):
        collars.addRoundedRect(QRectF(_ref(x, 45.5), _ref(x + 5, 59)), 1.5, 1.5)
    pegs = QPainterPath()
    for x in PEG_X:
        pegs.addEllipse(_ref(x, 41.2), 2.8, 4.6)
    star = []
    for i in range(16):
        a = math.radians(-90 + 22.5 * i)
        r = 12.5 if i % 2 else {0: 31.0, 4: 22.0, 8: 34.0, 12: 22.0}.get(i, 19.0)
        star.append((155 + r * math.cos(a), 263 + r * math.sin(a)))
    setting = _poly(star)
    setting.addEllipse(_ref(155, 263), 15.0, 18.5)
    setting.setFillRule(Qt.WindingFill)
    gem = QPainterPath()
    gem.addEllipse(_ref(155, 263), 10.5, 13.5)
    blades = QPainterPath()
    blades.setFillRule(Qt.WindingFill)
    for pts in (np.concatenate([_spline(BLADE_TOP, 8), np.array(BLADE_LOW, dtype=np.float64)]), np.array(BLADE_SMALL, dtype=np.float64)):
        blades.addPath(_poly(pts))
        blades.addPath(_poly(_mirror(pts)))
    # The blade's lit upper face, cut off from its darker lower face by a ridge, as a carved blade.
    top = _spline(BLADE_TOP, 8)
    k = np.linspace(0, 1, len(top))[:, None]
    ridge = top + np.sin(np.pi * k) ** 0.7 * np.array([1.5, 6.0])
    facet = QPainterPath()
    pts = np.concatenate([top, ridge[::-1]])
    facet.addPath(_poly(pts))
    facet.addPath(_poly(_mirror(pts)))
    # Faint carved leaves on the arms: slim almonds with a vein, a curl low on each arm, a small sprig.
    carving = QPainterPath()
    for side in (1, -1):
        def q(x: float, y: float, side: int = side) -> QPointF:
            return _ref(CX + side * (x - CX), y)

        for x0, y0, xm, ym, x1, y1 in ((92, 66, 99, 90, 92, 114), (75, 150, 86, 168, 70, 196)):
            carving.moveTo(q(x0, y0))
            carving.quadTo(q(xm + 4, ym), q(x1, y1))
            carving.quadTo(q(xm - 6, ym), q(x0, y0))
            carving.moveTo(q(x0 + 0.5, y0 + 6))
            carving.quadTo(q(xm - 1, ym), q(x1, y1 - 5))
        carving.moveTo(q(58, 232))
        carving.cubicTo(q(64, 214), q(80, 214), q(78, 228))
        carving.cubicTo(q(76, 236), q(68, 234), q(70, 228))
        for x1, y1 in ((84, 104), (100, 104)):
            carving.moveTo(q(92, 92))
            carving.quadTo(q((92 + x1) / 2 + 3, (92 + y1) / 2 - 3), q(x1, y1))
            carving.quadTo(q((92 + x1) / 2 - 3, (92 + y1) / 2 + 3), q(92, 92))
    # The inner faces of the arms, along the opening, sit a shade darker.
    faces = QPainterPath()
    for pts in (inner, _mirror(inner)):
        faces.moveTo(_ref(*pts[3]))
        for x, y in pts[4:-3]:
            faces.lineTo(_ref(x, y))
    return {"body": body, "foot": foot, "base": base, "bridge": bridge, "rod": rod, "cap": cap, "collars": collars, "pegs": pegs,
            "setting": setting, "gem": gem, "blades": blades, "facet": facet, "carving": carving, "faces": faces}  # fmt: skip


def _petal_points(ln: float, a: float, wf: float) -> np.ndarray:
    """A pointed lily petal from the flower's heart along angle a, wf of its length wide."""
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    w = wf * ln
    side1 = _bezier((0, 0), d * 0.12 * ln + n * w * 1.0, d * 0.62 * ln + n * w * 0.7, d * ln, 24)
    side2 = _bezier(d * ln, d * 0.62 * ln - n * w * 0.62, d * 0.12 * ln - n * w * 1.0, (0, 0), 24)
    return np.concatenate([side1, side2[1:]])


def _lyre_image(angle: float, ppr: float, halo: bool = True) -> QImage:
    """The lyre shaded per pixel, lit from the upper left as it stands turned by angle, in the flat painted
    way of its render: rose-brown wood with a lit bevel, pale gold, a teal gem, strings glowing white-mint at
    rest, white lilies. ppr pixels a ref; the picture is centred on the lyre's middle."""
    parts = _lyre_parts()
    size = int(450 * ppr) // 2 * 2
    light = _local_light(angle)

    def filled(path: QPainterPath) -> np.ndarray:
        def go(q: QPainter) -> None:
            q.translate(size / 2, size / 2)
            q.scale(ppr, ppr)
            q.setPen(Qt.NoPen)
            q.setBrush(QColor("white"))
            q.drawPath(path)
        return mask(size, size, go)

    def stroked(path: QPainterPath, width: float, offset: tuple[float, float] = (0.0, 0.0)) -> np.ndarray:
        def go(q: QPainter) -> None:
            q.translate(size / 2 + offset[0] * ppr, size / 2 + offset[1] * ppr)
            q.scale(ppr, ppr)
            q.setPen(QPen(QColor("white"), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.setBrush(Qt.NoBrush)
            q.drawPath(path)
        return mask(size, size, go)

    xs, ys = _grid(size, size)
    cx, cy = (xs - size / 2) / ppr + CX, (ys - size / 2) / ppr + CY

    def lit(m: np.ndarray, sigma: float, gain: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
        return _relief(blur(m, sigma * ppr) * m * 10 * ppr, gain, light)

    def edge(m: np.ndarray, sigma: float = 0.8) -> np.ndarray:
        return np.clip(1 - blur(m, sigma * ppr) * 1.8, 0, 1) * m

    def rim(m: np.ndarray, sigma: float, strength: float) -> np.ndarray:
        return np.clip(blur(m, sigma * ppr) * strength, 0, 1)

    color = np.zeros((size, size, 3), dtype=np.float32)
    alpha = np.zeros((size, size), dtype=np.float32)

    def over(c: np.ndarray, a: np.ndarray) -> None:
        nonlocal color, alpha
        color, alpha = _over(color, alpha, c, a)

    m_body = np.clip(filled(parts["body"]) + filled(parts["foot"]), 0, 1)
    m_base, m_bridge, m_rod = filled(parts["base"]), filled(parts["bridge"]), filled(parts["rod"])
    m_collar, m_pegs, m_cap = filled(parts["collars"]), filled(parts["pegs"]), filled(parts["cap"])
    m_set, m_gem, m_blade = filled(parts["setting"]), filled(parts["gem"]), filled(parts["blades"])
    whole = np.clip(m_body + m_base + m_rod + m_pegs + m_cap, 0, 1)

    # Wood, flat as painted: an even face, a crisp lit bevel on the edges facing the upper left and a dark one
    # on the others, a broad fall from the lit upper left, a faint grain.
    def wood(m: np.ndarray, sigma: float, k0: float = 0.0) -> np.ndarray:
        d, sp = lit(m, sigma, 1.6)
        return _ramp(WOOD, k0 - 0.2 + 1.12 * d - 0.0012 * (cx - CX) - 0.0009 * (cy - CY)) + sp[..., None] * 0.1

    grain = noise(size, size, 3 * ppr, 2, 5)
    c_body = wood(m_body, 1.7, 0.12) * (1 + 0.05 * (grain - 0.5))[..., None]
    c_body = c_body * (1 - 0.17 * blur(stroked(parts["faces"], 9.0), 1.0 * ppr) * m_body)[..., None]
    carve = stroked(parts["carving"], 1.0)
    carve_lit = stroked(parts["carving"], 1.0, (0.8, 0.8)) * (1 - carve)
    c_body = c_body * (1 - 0.3 * carve * m_body)[..., None] + (rgb("#d8a98c") - c_body) * (0.4 * carve_lit * m_body)[..., None]
    c_base, c_rod, c_collar = wood(m_base, 2.0, 0.12), wood(m_rod, 1.6, 0.35), wood(m_collar, 0.9, -0.15)

    def gold(m: np.ndarray, sigma: float, k0: float = 0.0) -> np.ndarray:
        d, sp = lit(m, sigma, 1.4)
        return _ramp(GOLD, k0 - 0.2 + 1.3 * d) * (1 - 0.25 * edge(m))[..., None] + sp[..., None] * 0.3

    c_blade, c_set, c_pegs, c_cap = gold(m_blade, 1.3, 0.1), gold(m_set, 1.4), gold(m_pegs, 0.8, 0.55), gold(m_cap, 1.2, 0.4)
    m_facet = filled(parts["facet"]) * m_blade
    c_blade = c_blade * (1 - 0.14 * (1 - m_facet) * m_blade)[..., None] + (rgb("#fff3d2") - c_blade) * (0.3 * m_facet)[..., None]
    d_br, _ = lit(m_bridge, 1.0, 1.4)
    c_bridge = _ramp(BRIDGE, -0.1 + 1.2 * d_br - 0.5 * smooth(211.5, 216, cy))
    # The gem: a teal dome, a white glint upper left, light pooled low inside it.
    dome = np.clip(1 - ((cx - 155) / 9.8) ** 2 - ((cy - 263) / 12.6) ** 2, 0, 1)
    d_gem, sp_gem = _relief(np.sqrt(dome) * 5 * ppr, 1.0, light)
    pool = np.exp(-((cx - 157) ** 2 + (cy - 268) ** 2) / 5.0 ** 2)
    c_gem = _ramp(GEM, 0.15 + 0.6 * d_gem + 0.45 * pool) + sp_gem[..., None] * 0.5
    glint = np.exp(-((cx - 151.5) ** 2 + (cy - 256.5) ** 2) / 2.0 ** 2)
    c_gem = c_gem + (1 - c_gem) * glint[..., None] * 0.9

    # The strings, at rest: one bright white-mint block between the crossbar and the bridge, each a white core.
    def strings(q: QPainter) -> None:
        q.translate(size / 2, size / 2)
        q.scale(ppr, ppr)
        q.setPen(QPen(QColor.fromRgbF(0.85, 0.85, 0.85), 2.7, Qt.SolidLine, Qt.FlatCap))
        for x in STRING_X:
            q.drawLine(_ref(x, STRING_Y[0]), _ref(x, STRING_Y[1]))

    m_str = mask(size, size, strings)
    block = np.clip((40 - np.abs(cx - 155)) / 4, 0, 1) * ((cy > STRING_Y[0]) & (cy < STRING_Y[1]))
    block = blur(block.astype(np.float32), 1.2 * ppr)
    if halo:
        aura = np.exp(-(((cx - 155) / 60) ** 2 + ((cy - 132) / 95) ** 2) ** 1.4)
        over(rgb(ANEMO_TEAL), aura * 0.2)
        over(rgb(MINT), blur(whole, 10 * ppr) * 0.22)
        cast = np.roll(np.roll(blur(whole, 5 * ppr), int(6 * ppr), axis=0), int(5 * ppr), axis=1)
        over(rgb(PINE), cast * 0.45)
    # The bright block glows into the dark between the arms.
    over(rgb("#2c8f7c"), blur(block, 6 * ppr) * 0.6)
    spread = blur(m_str, 2.2 * ppr)
    over(rgb("#a7c9b9") * (0.55 + 0.45 * spread / max(1e-3, float(spread.max())))[..., None], block * 0.95)
    over(rgb(OUTLINE), rim(whole, 0.9, 2.4) * 0.9)
    over(c_body, m_body)
    over(rgb(OUTLINE), rim(m_base, 0.7, 2.2) * 0.8)
    over(c_base, m_base)
    # The flourishes and the setting sit on the bowl with a thin dark line and a small shadow.
    deco = np.clip(m_blade + m_set, 0, 1)
    over(rgb("#4a2a1c"), np.roll(np.roll(blur(deco, 1.2 * ppr), int(1.5 * ppr), axis=0), int(1.2 * ppr), axis=1) * 0.45)
    over(rgb("#5a3a20"), rim(deco, 0.6, 2.2) * 0.75)
    over(c_blade, m_blade)
    over(c_set, m_set)
    over(rgb("#3f2a14"), rim(m_gem, 0.5, 2.2) * 0.8)
    over(c_gem, m_gem)
    over(rgb("#5a3a20"), rim(m_bridge, 0.6, 2.2) * 0.8)
    over(c_bridge, m_bridge)
    over(rgb("#dcfff1"), np.clip(blur(m_str, 1.2 * ppr) * 1.3, 0, 0.9) * block)
    over(rgb(STRING_CORE), m_str * np.clip(block * 1.6, 0, 1))
    over(rgb(OUTLINE), rim(m_rod, 0.7, 2.2) * 0.85)
    over(c_rod, m_rod)
    over(c_collar * 0.85, m_collar)
    over(rgb("#5a3a20"), rim(m_cap, 0.6, 2.2) * 0.8)
    over(c_cap, m_cap)
    over(rgb("#5a3a20"), rim(m_pegs, 0.6, 2.2) * 0.7)
    over(c_pegs, m_pegs)
    # Leaves, then the two lilies, petal by petal, back to front.
    for b, c, tip, wid in LEAVES:
        line = _bezier(b, c, c, tip, 60)
        k = np.linspace(0, 1, len(line))
        m_leaf = filled(_strip(line - np.array([CX, CY]), wid * np.sin(np.pi * np.clip(k, 0.02, 1)) ** 0.8 * (1 - k * 0.3)))
        d, sp = lit(m_leaf, 1.6, 1.2)
        rib = QPainterPath(_ref(*b))
        rib.cubicTo(_ref(*c), _ref(*c), _ref(*tip))
        c_leaf = _ramp(LEAF, -0.1 + 1.1 * d) + sp[..., None] * 0.15
        c_leaf = c_leaf + (rgb("#c4d690") - c_leaf) * (0.35 * stroked(rib, 0.7))[..., None]
        over(rgb("#1f2a14"), rim(m_leaf, 0.6, 2.2) * 0.7)
        over(c_leaf, m_leaf)
    for seed, ((fx, fy), shape) in enumerate(LILIES):
        span = 48.0
        for ang, ln, wf in shape:
            pts = _petal_points(ln, math.radians(ang), wf) + np.array([fx - CX, fy - CY])
            path = QPainterPath()
            path.addPolygon(QPolygonF([QPointF(float(x), float(y)) for x, y in pts]))
            path.closeSubpath()
            m = filled(path)
            d, _ = lit(m, 2.2, 0.9)
            r = np.hypot(cx - fx, cy - fy) / span
            k = np.clip(0.25 + 0.8 * d, 0, 1.05)
            c = rgb(PETAL_SHADE) * (1 - k[..., None]) + rgb(PETAL) * k[..., None]
            c = c + (rgb("#e2e7b8") - c) * (0.45 * (1 - smooth(0.05, 0.35, r)))[..., None]
            tip = pts[len(pts) // 2] + np.array([CX, CY])
            mid = QPainterPath(_ref(fx, fy))
            mid.lineTo(_ref(fx + (tip[0] - fx) * 0.75, fy + (tip[1] - fy) * 0.75))
            c = c * (1 - 0.12 * blur(stroked(mid, 0.8), 0.5 * ppr))[..., None]
            over(rgb("#20261a"), rim(m, 0.6, 2.2) * (1 - m) * 0.35)
            over(rgb(PETAL_LINE), rim(m, 0.6, 2.0) * 0.75)
            over(c, m * 0.995)
        # The heart: a cluster of pale purple stamens round a yellow-green pistil.
        over(rgb("#d9e2a0"), np.exp(-((cx - fx) ** 2 + (cy - fy) ** 2) / (0.12 * span) ** 2) * 0.8)
        for j in range(5):
            a = math.radians(seed * 40 + 72 * j)
            sx, sy = fx + 0.075 * span * math.cos(a), fy + 0.06 * span * math.sin(a)
            dot = np.exp(-((cx - sx) ** 2 + (cy - sy) ** 2) / (0.042 * span) ** 2)
            over(rgb("#4a3a8a"), np.clip(dot * 1.6, 0, 1) * 0.6)
            over(rgb(STAMEN), np.clip(dot * 1.4 - 0.15, 0, 1))
            over(rgb(STAMEN_LIT), np.exp(-((cx - sx + 0.6) ** 2 + (cy - sy + 0.6) ** 2) / (0.022 * span) ** 2) * 0.8)
    return _picture(color, alpha)


def _aura(ppr: float) -> QImage:
    """The swell of anemo light about the strings when they are strummed, at its fullest."""
    size = int(450 * ppr) // 2 * 2
    xs, ys = _grid(size, size)
    cx, cy = (xs - size / 2) / ppr + CX, (ys - size / 2) / ppr + CY
    aura = np.exp(-(((cx - 155) / 60) ** 2 + ((cy - 132) / 95) ** 2) ** 1.4)
    return _picture(np.broadcast_to(rgb(ANEMO_TEAL), aura.shape + (3,)), aura * 0.22)


def _string_glow(ppr: float) -> QImage:
    """One string as it rings: a white core in a mint glow, the string's length and 14 ref wide."""
    w, h = math.ceil(14 * ppr), math.ceil((STRING_Y[1] - STRING_Y[0] + 8) * ppr)
    xs, ys = _grid(w, h)
    x = (xs + 0.5) / ppr - 7
    y = (ys + 0.5) / ppr - 4
    along = smooth(0, 6, y) * smooth(0, 6, STRING_Y[1] - STRING_Y[0] - y)
    core = np.exp(-(x / 1.6) ** 2) * along
    halo = np.exp(-(x / 4.5) ** 2) * along
    light = halo[..., None] * rgb("#9ff5e0") * 0.6 + core[..., None] * rgb(CORE) * 1.1
    return _picture(*_light(light))


def _lyre(p: QPainter, art: dict, x: float, y: float, angle: float, pt: float, ppr: float, strum: list[float], alpha: float) -> None:
    """The lyre at (x, y), leaning by angle, the glow about it swelling with the strum and each string
    brightening as it rings."""
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.scale(pt, pt)
    glow_k = sum(strum) / len(strum)
    image = art["lyre"]
    side = image.width() / ppr
    p.setOpacity(alpha * min(1.0, glow_k * 1.5))
    if glow_k > 0.01:
        p.drawImage(QRectF(-side / 2, -side / 2, side, side), art["aura"])
    p.setOpacity(alpha)
    p.drawImage(QRectF(-side / 2, -side / 2, side, side), image)
    ring = art["string"]
    w, h = ring.width() / ppr, ring.height() / ppr
    for i, sx in enumerate(STRING_X):
        if strum[i] > 0.02:
            # A ringing string shivers a little sideways.
            shiver = 0.6 * strum[i] * math.sin(strum[i] * 40 + i)
            p.setOpacity(alpha * strum[i] * 0.85)
            p.drawImage(QRectF(sx - CX - w / 2 + shiver, STRING_Y[0] - CY - 4, w, h), ring)
    p.restore()


# Maple leaves, feathers, cecilias and seeds, each drawn ss pixels a design point.

# The right half of a maple leaf, tip to petiole, in its length R from where the veins meet: a long toothed
# middle lobe, two broad toothed side lobes, two small lower lobes, deep notches between them.
MAPLE_HALF = [(0.0, -1.0), (0.1, -0.8), (0.23, -0.85), (0.215, -0.63), (0.31, -0.63), (0.21, -0.41),
              (0.4, -0.5), (0.5, -0.46), (0.6, -0.64), (0.665, -0.51), (0.93, -0.53), (0.78, -0.35), (0.88, -0.25),
              (0.64, -0.17), (0.38, -0.07), (0.57, 0.05), (0.7, 0.22), (0.46, 0.2), (0.22, 0.19), (0.07, 0.13)]  # fmt: skip
MAPLE_VEINS = [(0.0, -0.94), (0.86, -0.51), (-0.86, -0.51), (0.64, 0.2), (-0.64, 0.2), (0.21, -0.81), (-0.21, -0.81),
               (0.58, -0.6), (-0.58, -0.6)]  # fmt: skip


def _maple_path(r: float) -> QPainterPath:
    half = [(x * r, y * r) for x, y in MAPLE_HALF]
    pts = half + [(-x, y) for x, y in reversed(half[1:])]
    path = QPainterPath()
    path.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
    path.closeSubpath()
    return path


def _maple_pair(r: float, angle: float, ember: bool, seed: int, ss: float) -> tuple[QImage, QImage]:
    """A maple leaf's face and its back."""
    return _maple(r, angle, 1.0, ember, seed, ss), _maple(r, angle, -1.0, ember, seed, ss)


def _maple(r: float, angle: float, flip: float, ember: bool, seed: int, ss: float) -> QImage:
    """A red maple leaf shaded per pixel: vermilion lit upper left, crimson body, deep maple at the base and
    veins, a long petiole, and a soft pine shadow under it so it reads on the green."""
    path = _maple_path(r)
    size = int(2.7 * r * ss) // 2 * 2
    light = _local_light(angle, flip)
    off = 0.2 * r  # the leaf's middle sits at the picture's middle

    def go_fill(q: QPainter) -> None:
        q.translate(size / 2, size / 2 + off * ss)
        q.scale(ss, ss)
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("white"))
        q.drawPath(path)

    def go_veins(q: QPainter) -> None:
        q.translate(size / 2, size / 2 + off * ss)
        q.scale(ss, ss)
        for k, (x, y) in enumerate(MAPLE_VEINS):
            q.setPen(QPen(QColor("white"), max(0.55, (0.055 if k < 5 else 0.035) * r), Qt.SolidLine, Qt.RoundCap))
            if k < 5:
                q.drawLine(QPointF(0, 0.04 * r), QPointF(x * r, y * r))
            else:
                # Side veins off the main ones, out to the big teeth.
                bx, by = (0.0, -0.45) if k < 7 else (0.3 * np.sign(x), -0.2)
                q.drawLine(QPointF(bx * r, by * r), QPointF(x * r, y * r))
        q.setPen(QPen(QColor("white"), max(1.0, 0.085 * r), Qt.SolidLine, Qt.RoundCap))
        stalk = QPainterPath(QPointF(0, 0.02 * r))
        stalk.quadTo(QPointF(0.02 * r, 0.35 * r), QPointF(0.12 * r, 0.62 * r))
        q.setBrush(Qt.NoBrush)
        q.drawPath(stalk)

    m = mask(size, size, go_fill)
    veins = mask(size, size, go_veins)
    petiole = veins * (1 - m)
    veins = veins * m
    xs, ys = _grid(size, size)
    cx, cy = (xs - size / 2) / (r * ss), (ys - size / 2 - off * ss) / (r * ss)
    k = np.hypot(cx, cy)
    h = blur(m, 0.09 * r * ss) * m - 0.22 * blur(veins, 0.5 * ss) + 0.1 * blur(veins, 2.5 * ss)
    d, sp = _relief(h * 30 * ss / 2, 1.0, light)
    base = _ramp([(0.0, DEEP_MAPLE), (0.2, "#a81c2a"), (0.5, "#d0262a"), (1.0, "#dc3a2c")], k)
    color = base * (0.74 + 0.4 * d)[..., None]
    color = color + (rgb(VERMILION) - color) * (np.clip((d - 0.5) * 2.2, 0, 1) * 0.9)[..., None]
    if ember:
        e = smooth(0.6, 1.0, k) * np.clip(-cy * 1.2 + 0.2, 0, 1)
        color = color + (rgb(EMBER) - color) * (0.7 * e)[..., None]
    color = color + (rgb(DEEP_MAPLE) - color) * (0.65 * blur(veins, 0.5 * ss))[..., None]
    # A hair of light along each vein's upper-left side.
    sh = max(1, int(ss))
    vl = np.clip(blur(np.roll(np.roll(veins, -sh, 0), -sh, 1), 0.5 * ss) - veins, 0, 1)
    color = color + (rgb("#ff8a6a") - color) * (0.3 * vl * m)[..., None]
    # A deep rim just inside the edge, so the teeth stay sharp at half size.
    edge = np.clip(1 - blur(m, 0.8 * ss) * 1.7, 0, 1) * m
    color = color * (1 - 0.4 * edge)[..., None] + sp[..., None] * 0.2
    if flip < 0:
        color = color * 0.84 + rgb("#b23a40") * 0.1
    rnd = np.random.default_rng(seed)
    color = color * (1 + 0.06 * (blur(rnd.random((size, size), dtype=np.float32), 1.2) - 0.5))[..., None]
    shape = np.clip(m + petiole, 0, 1)
    color = np.where((petiole > m)[..., None], rgb("#7a1822"), color)
    # A shadow down and right on the screen, worked back into the leaf's own turned frame.
    a = math.radians(-angle)
    dx, dy = 2.2 * math.cos(a) - 3.0 * math.sin(a), 2.2 * math.sin(a) + 3.0 * math.cos(a)
    dy *= 1 if flip >= 0 else -1
    shadow = np.roll(np.roll(blur(shape, 1.6 * ss), int(dy * ss / 2), 0), int(dx * ss / 2), 1) * (1 - shape)
    return _picture(*_over(np.broadcast_to(rgb(PINE), color.shape).copy(), shadow * 0.45, color, shape))


def _feather(length: float, angle: float, seed: int, ss: float, bend: float = 0.06) -> QImage:
    """A white feather, base left, tip right, shaded per pixel: a bare quill, a rachis down the middle, a
    wide upper vane and a narrower lower one of barbs slanting to the tip, a split or two, downy barbs at
    the base, a cool shadow side, and a soft pine shadow under it."""
    L = length  # noqa: N806
    size = int(1.3 * L * ss) // 2 * 2
    rnd = random.Random(seed)
    wu, wl = 0.22 * L, 0.14 * L
    u0 = 0.14  # where the vane starts on the quill
    k = np.linspace(u0, 1.0, 110)

    def sy(kk):  # noqa: ANN001, ANN202
        return bend * L * (kk - 0.4) ** 2 * 2

    def prof(kk):  # noqa: ANN001, ANN202
        v = np.clip((kk - u0) / (1 - u0), 0, 1)
        return v ** 0.4 * np.clip(1 - v ** 1.6, 0, 1) ** 0.8 / 0.56

    x = (k - 0.5) * L
    top = np.stack([x, sy(k) - wu * prof(k)], axis=1)
    bot = np.stack([x, sy(k) + wl * prof(k)], axis=1)
    vane = QPainterPath()
    vane.addPolygon(QPolygonF([QPointF(float(a), float(b)) for a, b in np.concatenate([top, bot[::-1]])]))
    vane.closeSubpath()
    # Splits along the barbs: a thin gap from the edge in toward the rachis, slanting back to the base.
    for side, us in ((-1, rnd.uniform(0.42, 0.5)), (-1, rnd.uniform(0.68, 0.76)), (1, rnd.uniform(0.52, 0.62))):
        w = (wu if side < 0 else wl) * float(prof(np.array(us)))
        x0, y0 = (us - 0.5) * L, float(sy(np.array(us)))
        gap = max(1.1, 0.035 * L)
        wedge = QPainterPath(QPointF(x0 - 0.62 * w, y0 + side * 0.3 * w))
        wedge.lineTo(QPointF(x0 + 0.2 * w + gap, y0 + side * 1.15 * w))
        wedge.lineTo(QPointF(x0 + 0.2 * w - gap, y0 + side * 1.15 * w))
        wedge.closeSubpath()
        vane = vane.subtracted(wedge)

    def go_vane(q: QPainter) -> None:
        q.translate(size / 2, size / 2)
        q.scale(ss, ss)
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("white"))
        q.drawPath(vane)

    def go_shaft(q: QPainter) -> None:
        q.translate(size / 2, size / 2)
        q.scale(ss, ss)
        n = 34
        for i in range(n):
            a, b = -0.1 + 1.06 * i / n, -0.1 + 1.06 * (i + 1) / n
            q.setPen(QPen(QColor("white"), max(0.6, 0.045 * L * (1 - 0.7 * max(a, 0))), Qt.SolidLine, Qt.RoundCap))
            q.drawLine(QPointF((a - 0.5) * L, float(sy(np.array(a)))), QPointF((b - 0.5) * L, float(sy(np.array(b)))))

    def go_down(q: QPainter) -> None:
        # Loose downy barbs at the base of the vane.
        q.translate(size / 2, size / 2)
        q.scale(ss, ss)
        q.setPen(QPen(QColor("white"), max(0.35, 0.012 * L), Qt.SolidLine, Qt.RoundCap))
        r2 = random.Random(seed + 7)
        for i in range(6):
            side = -1 if i % 2 else 1
            kk = u0 + r2.uniform(-0.03, 0.12)
            bx, by = (kk - 0.5) * L, float(sy(np.array(kk)))
            ln = L * r2.uniform(0.09, 0.16)
            path = QPainterPath(QPointF(bx, by))
            path.quadTo(QPointF(bx + ln * 0.2, by + side * ln * 0.7), QPointF(bx + ln * 0.55 * r2.uniform(-0.4, 1), by + side * ln))
            q.drawPath(path)

    m = mask(size, size, go_vane)
    shaft = mask(size, size, go_shaft)
    down = mask(size, size, go_down) * (1 - m)
    xs, ys = _grid(size, size)
    lx, ly = (xs - size / 2) / ss, (ys - size / 2) / ss
    kk = np.clip(lx / L + 0.5, 0, 1)
    rel = ly - sy(kk)
    width = np.where(rel < 0, wu, wl) * np.maximum(prof(kk), 0.05)
    d = np.clip(np.abs(rel) / width, 0, 1)
    light = _local_light(angle)
    # Each vane curves a little: the upper one faces up, the lower one down.
    ny = np.where(rel < 0, -0.6, 0.6) * d
    diffuse = np.clip(ny * light[1] + np.sqrt(np.clip(1 - ny * ny, 0, 1)) * light[2], 0, 1)
    # Barbs: fine streaks slanting out from the rachis toward the tip.
    q = (lx - np.abs(rel) * 1.5) * ss * 0.75
    line = np.random.default_rng(seed).random(4096).astype(np.float32)
    line = np.convolve(line, np.ones(2) / 2, mode="same")
    barbs = line[np.mod(q.astype(int), 4096)]
    k = np.clip(0.16 + 0.9 * diffuse + 0.3 * (barbs - 0.5) - 0.14 * d ** 4, 0, 1)
    color = rgb(FEATHER_SHADE) * (1 - k[..., None]) + rgb(FEATHER) * k[..., None]
    # The groove either side of the rachis a touch shaded; a faint mint at the edges.
    groove = np.exp(-(rel / max(0.6, 0.03 * L)) ** 2) * (kk > u0)
    color = color * (1 - 0.1 * groove)[..., None]
    color = color + (rgb(MINT) - color) * (0.16 * smooth(0.75, 1, d))[..., None]
    # Downy and see-through near the base; ragged at the very edge.
    fluff = noise(size, size, 2.5 * ss, 2, seed)
    a = m * (1 - smooth(0.84, 1.0, d) * (0.45 + 0.55 * fluff))
    base = smooth(u0, u0 + 0.14, kk)
    a = a * (0.35 + 0.65 * np.maximum(base, (fluff > 0.6 - 0.4 * base)))
    a = np.maximum(a, down * 0.45)
    # The rachis: grey-teal by the quill, paling to the tip, with a lit upper side.
    shaft_c = _ramp([(0.0, "#34525b"), (0.3, "#6f9092"), (1.0, "#aac4c2")], np.clip((kk - 0.02) / 0.7, 0, 1))
    shaft_c = shaft_c + (1 - shaft_c) * (0.35 * np.clip(-rel / max(0.4, 0.018 * L), 0, 1))[..., None]
    shape = np.clip(a + shaft, 0, 1)
    color = (color * a[..., None] * (1 - shaft[..., None]) + shaft_c * shaft[..., None]) / np.maximum(shape, 1e-4)[..., None]
    # A shadow down and right on the screen, worked back into the feather's turned frame.
    r = math.radians(-angle)
    dx, dy = 2.0 * math.cos(r) - 3.0 * math.sin(r), 2.0 * math.sin(r) + 3.0 * math.cos(r)
    shadow = np.roll(np.roll(blur(shape, 1.8 * ss), int(dy * ss / 2), 0), int(dx * ss / 2), 1) * (1 - shape)
    return _picture(*_over(np.broadcast_to(rgb(PINE), color.shape).copy(), shadow * 0.42, color, shape))


def _cecilia(length: float, angle: float, seed: int, ss: float) -> QImage:
    """A white star lily, five pointed petals round a pale yellow-green heart."""
    L = length  # noqa: N806
    size = int(2.4 * L * ss) // 2 * 2
    light = _local_light(angle)
    rnd = random.Random(seed)
    color = np.zeros((size, size, 3), dtype=np.float32)
    alpha = np.zeros((size, size), dtype=np.float32)
    xs, ys = _grid(size, size)
    cx, cy = (xs - size / 2) / ss, (ys - size / 2) / ss
    for i in range(5):
        a = math.radians(-90 + 72 * i + rnd.uniform(-6, 6))
        ln = L * rnd.uniform(0.9, 1.05)
        w = 0.5 * ln
        d = np.array([math.cos(a), math.sin(a)])
        n = np.array([-d[1], d[0]])
        path = QPainterPath(QPointF(0, 0))
        path.cubicTo(QPointF(*(d * 0.3 * ln + n * w)), QPointF(*(d * 0.78 * ln + n * 0.42 * w)), QPointF(*(d * ln)))
        path.cubicTo(QPointF(*(d * 0.78 * ln - n * 0.42 * w)), QPointF(*(d * 0.3 * ln - n * w)), QPointF(0, 0))

        def go(q: QPainter, path: QPainterPath = path) -> None:
            q.translate(size / 2, size / 2)
            q.scale(ss, ss)
            q.setPen(Qt.NoPen)
            q.setBrush(QColor("white"))
            q.drawPath(path)

        m = mask(size, size, go)
        along = (cx * d[0] + cy * d[1]) / ln
        across = (-cx * d[1] + cy * d[0]) / ln
        # A petal is a shallow trough with a raised midrib.
        h = blur(m, 2.0 * ss) * m - 0.15 * np.exp(-(across / 0.04) ** 2) * m
        dif, _ = _relief(h * 12.5 * ss, 1.0, light)
        k = np.clip(0.35 + 0.75 * dif, 0, 1)
        c = rgb(FEATHER_SHADE) * (1 - k[..., None]) + rgb(FEATHER) * k[..., None]
        c = c + (rgb("#cdebd8") - c) * (0.5 * (1 - smooth(0.05, 0.4, along)))[..., None]
        # Each petal sits on the last with a faint seam shadow.
        color = color * (1 - 0.12 * blur(m, 1.2 * ss) * (1 - m))[..., None]
        color, alpha = _over(color, alpha, c, m)
    r = np.hypot(cx, cy) / L
    color = color + (rgb(HEART) - color) * (0.9 * np.exp(-(r / 0.17) ** 2))[..., None]
    for i in range(5):
        a = math.radians(-54 + 72 * i)
        dot = np.exp(-((cx - 0.1 * L * math.cos(a)) ** 2 + (cy - 0.1 * L * math.sin(a)) ** 2) / (0.035 * L) ** 2)
        color = color + (rgb("#c7da78") - color) * (0.8 * dot)[..., None]
    return _picture(color, alpha)


def _bud(length: float, angle: float, ss: float) -> QImage:
    """A cecilia bud, white, in its green calyx."""
    L = length  # noqa: N806
    size = int(1.6 * L * ss) // 2 * 2
    light = _local_light(angle)
    body = QPainterPath(QPointF(0, -0.5 * L))
    body.cubicTo(QPointF(0.26 * L, -0.15 * L), QPointF(0.22 * L, 0.3 * L), QPointF(0, 0.38 * L))
    body.cubicTo(QPointF(-0.22 * L, 0.3 * L), QPointF(-0.26 * L, -0.15 * L), QPointF(0, -0.5 * L))
    calyx = QPainterPath()
    for sx in (-1, 0, 1):
        leaf = QPainterPath(QPointF(0, 0.45 * L))
        leaf.quadTo(QPointF(sx * 0.2 * L - 0.1 * L, 0.3 * L), QPointF(sx * 0.14 * L, 0.05 * L))
        leaf.quadTo(QPointF(sx * 0.2 * L + 0.1 * L, 0.3 * L), QPointF(0, 0.45 * L))
        calyx.addPath(leaf)

    def filled(path: QPainterPath) -> np.ndarray:
        def go(q: QPainter) -> None:
            q.translate(size / 2, size / 2)
            q.scale(ss, ss)
            q.setPen(Qt.NoPen)
            q.setBrush(QColor("white"))
            q.drawPath(path)
        return mask(size, size, go)

    mb, mc = filled(body), filled(calyx)
    db, _ = _relief(blur(mb, 2.5 * ss) * mb * 12.5 * ss, 1.0, light)
    kb = np.clip(0.3 + 0.8 * db, 0, 1)
    cb = rgb(FEATHER_SHADE) * (1 - kb[..., None]) + rgb(FEATHER) * kb[..., None]
    dc, _ = _relief(blur(mc, 1.2 * ss) * mc * 10 * ss, 1.0, light)
    cc = rgb("#2e7a52") * (1 - dc[..., None]) + rgb("#8fd8a8") * dc[..., None]
    out = mc + mb * (1 - mc)
    color = (cc * mc[..., None] + cb * (mb * (1 - mc))[..., None]) / np.maximum(out, 1e-5)[..., None]
    return _picture(color, out)


def _seed(length: float, ss: float) -> QImage:
    """A dandelion seed, white: a stalk and a fan of hairs."""
    L = length  # noqa: N806
    size = int(1.4 * L * ss) // 2 * 2

    def go(q: QPainter) -> None:
        q.translate(size / 2, size / 2)
        q.scale(ss, ss)
        q.setPen(QPen(QColor("white"), 0.7))
        q.drawLine(QPointF(0, 0.45 * L), QPointF(0, -0.05 * L))
        for i in range(13):
            a = math.radians(-90 + (i - 6) * 13)
            q.drawLine(QPointF(0, -0.05 * L), QPointF(0.5 * L * math.cos(a), -0.05 * L + 0.5 * L * math.sin(a)))
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("white"))
        q.drawEllipse(QPointF(0, 0.47 * L), 0.05 * L, 0.08 * L)

    m = mask(size, size, go)
    return _picture(np.broadcast_to(rgb(CORE), (size, size, 3)), np.clip(blur(m, 0.5 * ss) * 1.4, 0, 1))


# The birds, drawn flat as the friend's picture is: a round little ball, a touch wider than tall and widest low, on a
# slightly flattened bottom, two rounded crest feathers on its round head, teal over the head and back, a white face
# round the eyes and a white belly with a band of teal between them where the wing lies, a white wing with scalloped
# feathers and teal tips, dark teal tail feathers, small red-brown eyes, pink blush beside them, a tiny white beak,
# all in a hand-drawn dark-teal line. BIRD design points tall; its bottom, where it sits, FOOT of that below its middle.
BIRD_TOP, BIRD_SHADE, BIRD_DEEP, BIRD_DEEP_SHADE = "#6fd3b8", "#46b39a", "#2e8f78", "#236f5e"
BIRD_WHITE, BIRD_WHITE_SHADE, BIRD_LINE, BIRD_EYE = "#f2fffb", "#cfece4", "#2f6f62", "#5a1f1f"
BLUSH, BEAK = "#f59aae", "#fffdf6"
BIRD = 64.0
FOOT = 0.45
# Its wing's turn (degrees, raised as it grows) and how far it is spread, for each pose; folded at rest, and "lift"
# holds it a little off its side, for a flutter.
WINGS = {"sit": (-32.0, 1.0), "blink": (-32.0, 1.0), "lift": (-14.0, 1.0), "up": (62.0, 1.05), "mid": (16.0, 1.05),
         "down": (-62.0, 1.0)}  # fmt: skip
SHOULDER = (-0.15, 0.12)
EYES = ((0.13, -0.15), (0.39, -0.16))


def _bird(pose: str, face: int, ss: float) -> QImage:
    """A bird facing right (face 1) or left (-1), flat as a drawing: each colour a base and one soft-edged shade
    away from the light (upper left), a faint paper grain, and a dark-teal line that thickens, thins and breaks
    here and there as a hand draws it. pose: "sit", "blink" (its eyes shut), "lift" (its wing a little off its
    side) or a flap, its wings spread "up", "mid" or "down". Centred on its body's middle, ss pixels a design point."""
    L = BIRD  # noqa: N806
    unit = L * ss  # pixels a bird's height
    size = int(2.0 * unit) // 2 * 2
    xs, ys = _grid(size, size)
    bx, by = (xs - size / 2) / unit * face, (ys - size / 2) / unit  # in its heights, as if it faced right
    turn, spread = WINGS[pose]
    flap = pose in ("up", "mid", "down")

    def q(x: float, y: float) -> QPointF:
        return QPointF(x, y)

    def filled(path: QPainterPath, pen: float = 0.0) -> np.ndarray:
        def go(p: QPainter) -> None:
            p.translate(size / 2, size / 2)
            p.scale(face * unit, unit)
            if pen:
                p.setPen(QPen(QColor("white"), pen, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.setBrush(Qt.NoBrush)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("white"))
            p.drawPath(path)
        return mask(size, size, go)

    def oval(x: float, y: float, rx: float, ry: float) -> np.ndarray:
        path = QPainterPath()
        path.addEllipse(q(x, y), rx, ry)
        return filled(path)

    def leaf(base: tuple[float, float], angle: float, length: float, wide: float, tip: float = 0.4) -> QPainterPath:
        """A feather from base along angle, wide at its widest, its tip as round as tip."""
        a = math.radians(angle)
        d = np.array([math.cos(a), math.sin(a)])
        n = np.array([-d[1], d[0]])
        b = np.array(base)
        path = QPainterPath(q(*(b - n * wide * 0.4)))
        path.cubicTo(q(*(b + d * length * 0.45 - n * wide)), q(*(b + d * length * 0.9 - n * wide * tip)), q(*(b + d * length)))
        path.cubicTo(q(*(b + d * length * 0.9 + n * wide * tip)), q(*(b + d * length * 0.45 + n * wide)), q(*(b + n * wide * 0.4)))
        path.closeSubpath()
        return path

    def wing(shoulder: tuple[float, float], angle: float, scale: float) -> tuple[QPainterPath, QPainterPath]:
        """A rounded wing pointing back from its shoulder, scalloped along its trailing edge, and the strokes of
        its feathers."""
        shape = QPainterPath(q(0.05, -0.05))
        shape.cubicTo(q(-0.12, -0.14), q(-0.36, -0.11), q(-0.47, 0.02))
        shape.quadTo(q(-0.46, 0.13), q(-0.35, 0.1))
        shape.quadTo(q(-0.31, 0.19), q(-0.21, 0.13))
        shape.quadTo(q(-0.13, 0.2), q(-0.05, 0.11))
        shape.quadTo(q(0.07, 0.05), q(0.05, -0.05))
        strokes = QPainterPath(q(-0.33, 0.02))
        strokes.quadTo(q(-0.3, 0.07), q(-0.34, 0.09))
        strokes.moveTo(q(-0.21, 0.04))
        strokes.quadTo(q(-0.18, 0.09), q(-0.22, 0.12))
        strokes.moveTo(q(-0.1, 0.05))
        strokes.quadTo(q(-0.07, 0.09), q(-0.1, 0.11))
        move = QTransform().translate(*shoulder).rotate(angle).scale(scale, scale)
        return move.map(shape), move.map(strokes)

    def shade(m: np.ndarray, reach: float) -> np.ndarray:
        """Where m turns from the light: a soft-edged crescent along its lower right, reach of a height deep."""
        shift = max(1, round(reach * unit))
        lit = np.roll(np.roll(blur(m, 0.5 * reach * unit), -shift, axis=0), -shift, axis=1)
        return (1 - smooth(0.42, 0.56, lit)) * m

    def tones(k: np.ndarray, base: str, dark: str) -> np.ndarray:
        return rgb(base) * (1 - k[..., None]) + rgb(dark) * k[..., None]

    seeds = iter(range(60, 100))

    def line(m: np.ndarray, wide: float = 0.022) -> np.ndarray:
        """A drawn line round m, about wide (of a height) out from its edge: thicker and thinner along it, broken
        in a few places."""
        reach = blur(m, wide * unit)
        level = 0.06 + 0.36 * noise(size, size, 0.22 * unit, 2, next(seeds))
        ring = smooth(level - 0.04, level + 0.04, reach) * (1 - smooth(0.4, 0.6, m))
        return ring * smooth(0.16, 0.24, noise(size, size, 0.1 * unit, 1, next(seeds)))

    color = np.zeros((size, size, 3), dtype=np.float32)
    alpha = np.zeros((size, size), dtype=np.float32)

    def over(c: np.ndarray, a: np.ndarray) -> None:
        nonlocal color, alpha
        color, alpha = _over(color, alpha, c, a)

    # A ball a touch wider than tall, widest low, its bottom a little flattened, its head round on top.
    body = QPainterPath(q(0.0, 0.45))
    body.lineTo(q(0.2, 0.45))
    body.cubicTo(q(0.46, 0.45), q(0.56, 0.32), q(0.54, 0.1))
    body.cubicTo(q(0.52, -0.32), q(0.32, -0.55), q(0.03, -0.55))
    body.cubicTo(q(-0.27, -0.55), q(-0.51, -0.32), q(-0.53, 0.1))
    body.cubicTo(q(-0.56, 0.32), q(-0.46, 0.45), q(-0.2, 0.45))
    body.closeSubpath()
    m_body = smooth(0.45, 0.55, blur(filled(body), 0.03 * unit))
    ears = [filled(leaf((-0.06, -0.47), -106, 0.3, 0.12, 0.8)), filled(leaf((0.16, -0.5), -82, 0.27, 0.11, 0.8))]
    tail = QPainterPath()
    tail.setFillRule(Qt.WindingFill)
    for angle, length in ((166, 0.27), (150, 0.23), (182, 0.2)):
        tail.addPath(leaf((-0.4, 0.32), angle, length, 0.075))
    m_tail = filled(tail)
    near, near_strokes = wing(SHOULDER, turn, spread)
    m_wing, m_strokes = filled(near), filled(near_strokes, 0.02)
    grain = noise(size, size, 1.5 * ss, 1, 9) - 0.5

    # Behind the body, back to front: the far wing in a flap, the tail, the crest feathers (teal, pale inside).
    if flap:
        far, _ = wing((-0.08, -0.06), turn + 12, spread * 0.92)
        m_far = filled(far)
        over(tones(shade(m_far, 0.04), BIRD_SHADE, BIRD_DEEP), m_far)
        over(rgb(BIRD_LINE), line(m_far))
    over(tones(shade(m_tail, 0.03), BIRD_DEEP, BIRD_DEEP_SHADE), m_tail)
    over(rgb(BIRD_LINE), line(m_tail, 0.022))
    for m in ears:
        inner = smooth(0.76, 0.86, blur(m, 0.03 * unit)) * m
        c = tones(shade(m, 0.03), BIRD_TOP, BIRD_SHADE)
        c = c + (tones(shade(m, 0.03), BIRD_WHITE, BIRD_WHITE_SHADE) - c) * inner[..., None]
        over(c, m)
        over(rgb(BIRD_LINE), line(m, 0.022))

    # The body: teal, a white face round the eyes and a white belly below, a band of teal between, one shade.
    k = shade(m_body, 0.09)
    # The face wraps round the front of the head, its top a curve just over the eyes.
    k_white = np.clip(oval(0.36, -0.19, 0.31, 0.16) + oval(0.12, 0.33, 0.46, 0.26), 0, 1) * m_body
    c = tones(k, BIRD_TOP, BIRD_SHADE)
    c = c + (tones(k, BIRD_WHITE, BIRD_WHITE_SHADE) - c) * k_white[..., None]
    over(c, m_body)
    over(rgb(BIRD_LINE), line(m_body, 0.03))

    # The face: blush beside the eyes, the eyes (shut, a soft curve), the beak between them.
    for (ex, ey), side in zip(EYES, (-1, 1), strict=True):
        r = np.hypot((bx - ex - side * 0.075) / 0.05, (by - ey - 0.035) / 0.03)
        over(rgb(BLUSH), (1 - smooth(0.7, 1.0, r)) * 0.85)
    eyes = QPainterPath()
    for ex, ey in EYES:
        if pose == "blink":
            eyes.moveTo(q(ex - 0.04, ey - 0.004))
            eyes.quadTo(q(ex, ey + 0.034), q(ex + 0.04, ey - 0.004))
        else:
            eyes.addEllipse(q(ex, ey), 0.034, 0.044)
    over(rgb(BIRD_EYE), filled(eyes, 0.022) if pose == "blink" else filled(eyes))
    beak = QPainterPath(q(0.235, -0.13))
    beak.lineTo(q(0.305, -0.13))
    beak.lineTo(q(0.27, -0.075))
    beak.closeSubpath()
    over(rgb(BIRD_LINE), filled(beak, 0.016))
    over(rgb(BEAK), filled(beak))

    # The near wing over the band: white, teal at its tips, its feathers drawn in, its line.
    a = math.radians(turn)
    along = np.clip(-((bx - SHOULDER[0]) * math.cos(a) + (by - SHOULDER[1]) * math.sin(a)) / (0.47 * spread), 0, 1.2)
    kw = shade(m_wing, 0.035)
    c = tones(kw, BIRD_WHITE, BIRD_WHITE_SHADE)
    c = c + (tones(kw, BIRD_TOP, BIRD_SHADE) - c) * smooth(0.68, 0.76, along)[..., None]
    c = c + (rgb(BIRD_LINE) - c) * (0.85 * m_strokes)[..., None]
    over(c, m_wing)
    over(rgb(BIRD_LINE), line(m_wing, 0.022))
    return _picture(color * (1 + 0.03 * grain)[..., None], alpha)


# The marks, each made once for each size and sharpness it is shown at.

_MARKS: dict[tuple, object] = {}


def _mark(key: tuple, make_it) -> object:  # noqa: ANN001
    if key not in _MARKS:
        _MARKS[key] = make_it()
    return _MARKS[key]


def _ring_route(cover: QRectF) -> np.ndarray:
    path = QPainterPath()
    r = cover.height() * 0.32
    path.addRoundedRect(cover, r, r)
    pts = np.array([[q.x(), q.y()] for q in path.toFillPolygon()], dtype=np.float64)
    return _resample(pts, 1.0)


def _ring_art(cover: QRectF, scale: float) -> tuple[QRectF, QImage, np.ndarray, np.ndarray]:
    """The ring: a thin mint wind ribbon round the button, swelling and thinning, with a white core and an
    anemo glow, and where it runs."""
    area = cover.adjusted(-9, -9, 9, 9)
    pts = _ring_route(cover)
    s = _arclen(pts)
    wide = 2.8 + 0.8 * np.sin(2 * np.pi * s / (s[-1] / 3))
    w, h = math.ceil(area.width() * scale), math.ceil(area.height() * scale)
    local = pts - np.array([area.left(), area.top()])

    def draw(widths: np.ndarray):  # noqa: ANN202
        def go(q: QPainter) -> None:
            q.scale(scale, scale)
            q.setPen(Qt.NoPen)
            q.setBrush(QColor("white"))
            for i in range(0, len(local) - 1, 10):
                j = min(len(local), i + 12)
                q.drawPolygon(_ribbon_polygon(local[i:j], widths[i:j]))
        return go

    body = mask(w, h, draw(wide))
    core = mask(w, h, draw(np.maximum(wide * 0.32, 0.7)))
    color = np.zeros((h, w, 3), dtype=np.float32)
    alpha = np.zeros((h, w), dtype=np.float32)
    halo = blur(body, 2.2 * scale) * 0.9 + blur(body, 4.5 * scale) * 0.5
    color, alpha = _over(color, alpha, *_light(halo[..., None] * rgb(ANEMO)))
    color, alpha = _over(color, alpha, rgb(MINT), np.clip(body * 1.2, 0, 1) * 0.92)
    color, alpha = _over(color, alpha, *_light(blur(core, 0.5 * scale)[..., None] * rgb(CORE) * 1.2))
    return area, _picture(color, alpha), pts, s


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A thin mint wind ribbon round the button, a strum of light running round it."""
    scale = _sharpness(p)
    where = (round(cover.x(), 1), round(cover.y(), 1), round(cover.width(), 1), round(cover.height(), 1), scale)
    area, image, pts, s = _mark(("ring", *where), lambda: _ring_art(cover, scale))
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setOpacity(0.85 + 0.15 * math.sin(t * 2.0))
    p.drawImage(area, image)
    p.setOpacity(1.0)
    # The shimmer: once round every 2.2 seconds, a bloom with a bright tail.
    total = s[-1]
    head = ((t - 0.2) * 0.45 % 1.0) * total
    for k in range(8):
        i = int(np.searchsorted(s, (head - k * 5) % total)) % len(pts)
        x, y = pts[i]
        if k == 0:
            soft_dot(p, x, y, 12, MINT, 0.55)
        soft_dot(p, x, y, 3.2 - 0.25 * k, CORE, 0.9 * (1 - k / 8))
    p.restore()


def _badge_art(box: QRectF, scale: float) -> QImage:
    """The badge: a small Der Frühling on a jade disc lit from the upper left, nothing else."""
    side = box.width()
    w, h = math.ceil(side * scale), math.ceil(box.height() * scale)
    radius = min(side, box.height()) * 0.375
    xs, ys = _grid(w, h)
    cx, cy = (xs + 0.5) / scale - side / 2, (ys + 0.5) / scale - box.height() / 2
    r = np.hypot(cx, cy)
    disc = np.clip((radius + 0.5 - r) * scale, 0, 1)
    d, sp = _relief(np.sqrt(np.clip(1 - (r / radius) ** 2, 0, 1)) * radius * 0.8 * scale, 1.0)
    k = np.clip(0.15 + 0.95 * d, 0, 1.1)
    color = _ramp([(0.0, PINE), (0.45, JADE), (0.85, MEADOW), (1.1, "#7fd6a8")], k) + sp[..., None] * 0.25
    edge = smooth(radius - 2.5, radius, r)
    color = color + (rgb(MINT) - color) * (0.55 * edge * np.clip(-(cx + cy) / radius, 0, 1))[..., None]
    shadow = np.clip(radius + 3 - np.hypot(cx - 2, cy - 2.5), 0, 4) / 4 * 0.45 * (1 - disc)
    color = np.where((disc > 0)[..., None], color, rgb(PINE))
    image = _picture(color, np.clip(disc + shadow, 0, 1))
    # The lyre on it, the same as the scene's, drawn twice as sharp and made small, standing in the disc's middle.
    per = radius * 1.58 / 357  # points a ref
    lyre = _lyre_image(0.0, 2 * per * scale, halo=False)
    q = QPainter(image)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(scale, scale)
    big = lyre.width() / (2 * scale)
    across, down = _ink_middle(lyre)
    q.drawImage(QRectF(side / 2 - across * big, box.height() / 2 - down * big, big, big), lyre)
    q.end()
    return image


def _ink_middle(image: QImage) -> tuple[float, float]:
    """Where the lyre's middle is in its picture, as fractions of its width and height: across, the middle of its
    crossbar and horns (the top quarter of what shows, alpha past a sixth, which the lilies at its right do not
    reach), so the lyre itself stands in the middle and its lilies reach out to the right; down, the middle of all
    of it."""
    argb = image.convertToFormat(QImage.Format_ARGB32)
    rows = np.frombuffer(argb.constBits(), np.uint8, argb.sizeInBytes()).reshape(argb.height(), argb.bytesPerLine())
    shows = rows[:, 3 : argb.width() * 4 : 4] > 40
    ys, xs = np.nonzero(shows)
    if not len(xs):
        return 0.5, 0.5
    top = shows[ys.min() : ys.min() + (ys.max() - ys.min() + 1) // 4]
    tx = np.nonzero(top.any(axis=0))[0]
    return (tx.min() + tx.max() + 1) / 2 / argb.width(), (ys.min() + ys.max() + 1) / 2 / argb.height()


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A small lyre on a jade disc; a breath of mint light swells round it as it is strummed."""
    scale = _sharpness(p)
    image = _mark(("badge", round(box.width(), 1), round(box.height(), 1), scale), lambda: _badge_art(box, scale))
    since = t % 3.2
    swell = (1 - math.exp(-since / 0.05)) * math.exp(-since * 2.2)
    radius = min(box.width(), box.height()) * 0.375
    soft_dot(p, box.center().x(), box.center().y(), radius * 1.35, ANEMO, 0.18 + 0.3 * swell)
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(box, image)
    p.restore()


def _card_art(rect: QRectF, scale: float) -> QImage:
    """The card: deep-jade glass, lit upper left, a soft sheen across its top, a mint edge and a faint
    white line inside it."""
    body = rect.adjusted(0.65, CARD_TOP + 0.65, -0.65, -0.65)
    radius = min(12.0, body.height() / 3)
    path = QPainterPath()
    path.addRoundedRect(body, radius, radius)
    w, h = math.ceil(rect.width() * scale), math.ceil(rect.height() * scale)

    def go(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(-rect.left(), -rect.top())
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("white"))
        q.drawPath(path)

    m = mask(w, h, go)
    xs, ys = _grid(w, h)
    k = np.clip(0.55 * xs / w + 0.45 * ys / h, 0, 1)
    color = rgb("#1d7a58") * (1 - k[..., None]) + rgb(PINE) * k[..., None]
    sheen = np.exp(-((ys / h - 0.12) / 0.16) ** 2) * (1 - xs / w * 0.6)
    color = color + (rgb(MINT) - color) * (0.22 * sheen)[..., None]
    color = color * (1 + 0.05 * (noise(w, h, 10 * scale, 2, 3) - 0.5))[..., None]
    image = _picture(color, m * 0.78)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(scale, scale)
    q.translate(-rect.left(), -rect.top())
    q.setBrush(Qt.NoBrush)
    q.setPen(QPen(QColor(MINT), 1.3))
    q.drawPath(path)
    inner = QPainterPath()
    inner.addRoundedRect(body.adjusted(2.2, 2.2, -2.2, -2.2), radius - 2, radius - 2)
    q.setPen(QPen(QColor(255, 255, 255, 70), 0.8))
    q.drawPath(inner)
    q.end()
    return image


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """Deep-jade glass with a mint edge, behind the names."""
    scale = _sharpness(p)
    image = _mark(("card", round(rect.width(), 1), round(rect.height(), 1), scale), lambda: _card_art(rect, scale))
    p.drawImage(rect, image)


def lead(size: float, index: int) -> QPixmap:
    """A white feather before the first name, a small red maple leaf before the second, and so on in turn."""
    ratio = 3.0
    image = QImage(math.ceil(size * ratio), math.ceil(size * ratio), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    q = QPainter(image)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(ratio, ratio)
    unit = size / 18
    ss = 2 * ratio * unit
    if index % 2 == 0:
        _place(q, _feather(21, -50, 99, ss, 0.04), size / 2, size / 2, -50, 1, 1, 1.0, ss / unit)
    else:
        _place(q, _maple(9, 18, 1.0, False, 98, ss), size / 2, size / 2, 18, 1, 1, 1.0, ss / unit)
    q.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap
