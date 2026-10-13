"""The 心动 scenes: what plays over the game for two or more 心动 players in one lobby.

Each scene is a module with DURATION (seconds) and make(stage) -> paint(painter, t), where paint
draws the scene t seconds in, on stage.width by stage.height, and keeps stage.gap (the button and
its marks at the bottom) clear. Heavy scenes set MAX_RATIO, the most pixels per point they are
drawn at; a sharper screen gets them scaled up, which their soft light hides.

Scenes are drawn for a lobby about 1635 by 848 points and scale with the stage.
"""

from __future__ import annotations

import importlib
import random
from dataclasses import dataclass, field
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
    ("thread", "命运红线"),
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
    cards: the middle of each 心动 player's card, for scenes that point at them.
    """

    width: float
    height: float
    gap: QRectF
    badge: QPointF | None = None
    cards: tuple[QPointF, ...] = field(default_factory=tuple)

    def unit(self) -> float:
        return min(self.width / DESIGN[0], self.height / DESIGN[1])

    def heart(self) -> QPointF:
        """The heart badge, or where it would be: just right of the gap's middle."""
        if self.badge is not None:
            return self.badge
        return QPointF(self.gap.center().x() + self.gap.width() * 0.33, self.gap.top() + 72 * self.unit())


def load(key: str) -> ModuleType:
    return importlib.import_module(f"{__name__}.{key}")


def needs_cards(key: str) -> bool:
    """命运红线 ties a thread round each 心动 player's card: without them it cannot play."""
    return key == "thread"


def choose(choice: str, last: str, cards: int, rng: random.Random) -> str:
    """The scene to play for a 设置 choice: a key, "random" (any but the last one), or "off" ("")."""
    if choice == "off":
        return ""
    playable = [key for key in KEYS if cards >= 2 or not needs_cards(key)]
    if choice in playable:
        return choice
    if choice in KEYS:
        # Chosen but not playable here (命运红线 with no cards to tie): the first border instead.
        return "classic"
    pool = [key for key in playable if key != last] or playable
    return rng.choice(pool)


def sample_stage(width: float = DESIGN[0], height: float = DESIGN[1]) -> Stage:
    """The fake-name sample lobby's stage: its button, heart and two 心动 cards (心动小鹿, 心动星星)."""
    s = width / DESIGN[0]
    # 准备案件还原 and the marks either side of it, as the app leaves them clear.
    keep = QRectF(549 * s, 749 * s, 556 * s, 94 * s)
    gap = QRectF(keep.left() - 28 * s, keep.top() - 30 * s, keep.width() + 56 * s, height - keep.top() + 30 * s)
    return Stage(
        width,
        height,
        gap,
        badge=QPointF(1052 * s, 796 * s),
        cards=(QPointF(1437 * s, 343 * s), QPointF(990 * s, 573 * s)),
    )
