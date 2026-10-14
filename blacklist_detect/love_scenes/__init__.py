"""The 心动 scenes: what plays over the game for 心动 players in one lobby (as many as 心动人数 says).

Each scene is a module with DURATION (seconds) and make(stage) -> paint(painter, t), where paint
draws the scene t seconds in, on stage.width by stage.height, and keeps stage.gap (the button and
its marks at the bottom) clear. Heavy scenes set MAX_RATIO, the most pixels per point they are
drawn at; a sharper screen gets them scaled up, which their soft light hides. A heavy scene with a
small part that must stay crisp (a jewel) gives paint a `sharp` attribute, paint(painter, t) for
that part alone, and takes paint(painter, t, sharp=False) to draw the rest; the part is then drawn
on top at the screen's own sharpness.

Scenes are drawn for a lobby about 1635 by 848 points and scale with the stage.

The 心动 marks (the ring on 准备案件还原, the badge beside it and the card of names) wear the look of
the scene that greets them. A scene colors them with LOOK, and can go further and draw them itself,
as a theme of its own, with any of these (each optional; without one, that mark is drawn as before,
in LOOK's colors). None of them may import ui_overlay; draw and light are theirs to use.

    LOOK: dict            ui_overlay.LoveLook's fields but marks: glow, rim, band, card, edge, ink,
                          flowers, disc, heart, deep, deep_glow. Still used for the ring shared with
                          黑名单 players, the card's names, scroll bar and fade, and any mark the
                          scene does not draw. A scene in ui_overlay.LOOKS takes that look instead.
    ring(painter, cover: QRectF, t: float)
                          The ring on the button, in its window: cover is the button and its outset,
                          with ui_overlay._GLOW (9) points round it for a glow, the window's edge.
                          Keep the button's words readable: nothing opaque over its middle.
    badge(painter, box: QRectF, t: float)
                          The badge beside the button: box is its square, _GLOW points inside the
                          window's edges. Any symbol, not only a heart.
    card(painter, rect: QRectF, t: float)
                          The card's whole background and ornaments, behind the names: rect is the
                          card's window, CARD_TOP points of room on top of the card's body. The names
                          are drawn over it, in LOOK's ink.
    CARD_TOP: int         Room above the card's body for an ornament (12, the flower knot's).
    CARD_PAD: tuple       The body's margins round the names (left, top, right, bottom), in points at
                          full size (12, 8, 12, 8); they shrink with the names on a smaller game.
    CARD_FONT: str        The names' font family (the app's Chinese face).
    lead(size: float, index: int) -> QPixmap | None
                          What goes before the index-th name (from 0), about size points high; None
                          for nothing. Make it at devicePixelRatio 2 or more, so it stays sharp.
    MARKS_ANIMATED: bool  The marks move: about 30 times a second while one shows, t is the seconds
                          since it showed, on and on (loop it yourself). Otherwise t is 0.

Painters come antialiased, in the mark's window's points, saved and restored around each call.
"""

from __future__ import annotations

import importlib
import random
from dataclasses import dataclass
from types import ModuleType

from PySide6.QtCore import QPointF, QRectF

# (key, name in 设置), in the order 设置 lists them. 经典 is the border the app first had.
SCENES: tuple[tuple[str, str], ...] = (
    ("classic", "经典花边"),
    ("ice", "冰蓝极光"),
    ("stars", "星河许愿"),
    ("cyber", "赛博"),
    ("neon", "霓虹都市"),
    ("angel", "天使"),
    ("equation", "数学"),
    ("fluffy", "毛茸茸"),
)
KEYS = tuple(key for key, _name in SCENES)
# A scene that is gone, and the one a player who chose it gets now: 天使 took 香槟's place.
REPLACED = {"champagne": "angel"}
# The design size the scenes were drawn at.
DESIGN = (1635.0, 848.0)


@dataclass
class Stage:
    """Where a scene plays, in the border window's own points.

    gap: the bottom area around the button and its marks, which stays bare.
    badge: the 心动 heart beside the button.
    """

    width: float
    height: float
    gap: QRectF
    badge: QPointF | None = None

    def unit(self) -> float:
        return min(self.width / DESIGN[0], self.height / DESIGN[1])

    def heart(self) -> QPointF:
        """The heart badge, or where it would be: just right of the gap's middle."""
        if self.badge is not None:
            return self.badge
        return QPointF(self.gap.center().x() + self.gap.width() * 0.33, self.gap.top() + 72 * self.unit())


def load(key: str) -> ModuleType:
    return importlib.import_module(f"{__name__}.{key}")


def shown(choice: str) -> str:
    """A saved 心动特效 choice as this version has it: a scene that was replaced is its replacement."""
    return REPLACED.get(choice, choice)


def choose(choice: str, last: str, rng: random.Random) -> str:
    """The scene to play for a 心动特效 choice: a key, "random" (any but the last one), or "off" ("").
    香槟 plays 天使, which replaced it. Any other key this version does not have (命运红线, gone in
    v0.8.2; 雪纺, gone in v0.9.0; 缎带, 花雨, 纸鹤晚霞 and 蝶梦, gone in the next version) plays
    经典花边, the default."""
    choice = shown(choice)
    if choice == "off":
        return ""
    if choice in KEYS:
        return choice
    if choice != "random":
        return "classic"
    pool = [key for key in KEYS if key != last] or list(KEYS)
    return rng.choice(pool)


def sample_stage(width: float = DESIGN[0], height: float = DESIGN[1]) -> Stage:
    """The fake-name sample lobby's stage: its button and the heart beside it."""
    s = width / DESIGN[0]
    # 准备案件还原 and the marks either side of it, as the app leaves them clear.
    keep = QRectF(549 * s, 749 * s, 556 * s, 94 * s)
    gap = QRectF(keep.left() - 28 * s, keep.top() - 30 * s, keep.width() + 56 * s, height - keep.top() + 30 * s)
    return Stage(width, height, gap, badge=QPointF(1052 * s, 796 * s))
