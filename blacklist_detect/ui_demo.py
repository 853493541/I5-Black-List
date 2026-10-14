"""测试效果's stand-in for a game: the app's sample lobby (made-up names) as a whole 16:9 game
screen, in a window of its own, which the 心动 marks then frame as they would a real lobby.

The sample lobby is a crop of a lobby. Around it lies the whole screen the app's own model puts
around a lobby (layout.game_screen, measured on the crop): from (-56, -52) to (3544, 1973) in the
crop's pixels, the parts the crop lacks in the lobby's dark edge color.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

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


class DemoLobby(QWidget):
    """The sample screen on the screen, where 测试效果 shows: under the marks, never taking a click
    or the keyboard."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput,
        )
        self.setWindowTitle("测试效果")
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)

    def show_at(self, area: QRect) -> None:
        self.setGeometry(area)
        self.show()
        self.raise_()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        picture = sample_screen()
        painter.drawPixmap(QRectF(self.rect()), picture, QRectF(picture.rect()))
        painter.end()
