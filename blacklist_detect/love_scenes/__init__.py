"""The 心动 scenes: what plays over the game for 心动 players in one lobby (as many as 心动人数 says).

Each scene is a module with DURATION (seconds) and make(stage) -> paint(painter, t), where paint
draws the scene t seconds in, on stage.width by stage.height, and keeps stage.gap (the button and
its marks at the bottom) clear. Heavy scenes set MAX_RATIO, the most pixels per point they are
drawn at; a sharper screen gets them scaled up, which their soft light hides.

Scenes are drawn for a lobby about 1635 by 848 points and scale with the stage.
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
    ("ribbon", "缎带"),
    ("chiffon", "雪纺"),
    ("petals", "花雨"),
    ("ice", "冰蓝极光"),
    ("stars", "星河许愿"),
    ("cranes", "纸鹤晚霞"),
    ("butterfly", "蝶梦"),
    ("champagne", "香槟"),
)
KEYS = tuple(key for key, _name in SCENES)
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


def choose(choice: str, last: str, rng: random.Random) -> str:
    """The scene to play for a 心动特效 choice: a key, "random" (any but the last one), or "off" ("").
    A key this version does not have (命运红线, gone in v0.8.2) plays 经典花边, the default."""
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
