"""The app's sample lobby (made-up names) as a whole 16:9 game screen, and where 准备案件还原 sits on
it: the 场景 hotkey puts its marks there on a game no check has seen, and tools/ui_shots.py paints the
on-game cards over it.

The sample lobby is a crop of a lobby. Around it lies the whole screen the app's own model puts
around a lobby (layout.game_screen, measured on the crop): from (-56, -52) to (3544, 1973) in the
crop's pixels, the parts the crop lacks in the lobby's dark edge color.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap

SAMPLE_LOBBY = Path(__file__).resolve().parent / "assets" / "sample-lobby.jpg"
SCREEN_IN_CROP = (-56, -52, 3544, 1973)
EDGE = QColor(12, 16, 23)
# 准备案件还原 on that whole screen, in fractions of it.
BUTTON = (0.430, 0.776, 0.572, 0.846)
# Built at half size: a whole-screen picture at full size would hold some 30 MB.
_SCALE = 0.5
_screen: QPixmap | None = None


def sample_screen() -> QPixmap:
    """The sample lobby as a whole 16:9 game screen. Made once, then kept."""
    global _screen
    if _screen is None:
        left, top, right, bottom = SCREEN_IN_CROP
        screen = QPixmap(round((right - left) * _SCALE), round((bottom - top) * _SCALE))
        screen.fill(EDGE)
        lobby = QPixmap(str(SAMPLE_LOBBY))
        painter = QPainter(screen)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(
            QRectF(-left * _SCALE, -top * _SCALE, lobby.width() * _SCALE, lobby.height() * _SCALE), lobby, QRectF(lobby.rect())
        )
        painter.end()
        _screen = screen
    return _screen
