"""The environment check shown the first time the app opens, and after an update.

A card over the window: a progress bar and three steps (屏幕截图, 识别模型, 识别测试).
When all pass it says 环境确认 and fades away; when one fails it says which and why,
and offers 重试. The window runs the steps; this widget only shows them.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect.ui_icons import pixmap as line_pixmap
from blacklist_detect.ui_theme import (
    DIALOG_PAD,
    GAP,
    SMALL_PT,
    THEME,
    TITLE_PT,
    _pointing,
    chinese_font,
)
from blacklist_detect.ui_widgets import _watch_mark

STEPS = ("屏幕截图", "识别模型", "识别测试")
_SCALE = 1000


class SetupCheck(QWidget):
    """Covers the window while the environment is checked."""

    retry = Signal()
    dismissed = Signal()

    def __init__(self, host: QWidget) -> None:
        super().__init__(host)
        self.setObjectName("setupScrim")
        self.setAttribute(Qt.WA_StyledBackground, True)
        outer = QVBoxLayout(self)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.card = QFrame()
        self.card.setObjectName("setupCard")
        self.card.setFixedWidth(440)
        row.addWidget(self.card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

        column = QVBoxLayout(self.card)
        column.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        column.setSpacing(GAP)
        heading = QHBoxLayout()
        heading.setSpacing(8)
        self.mark = QLabel()
        self.mark.setFixedSize(22, 22)
        self.mark.hide()
        heading.addWidget(self.mark)
        self.title = QLabel("")
        self.title.setObjectName("setupTitle")
        self.title.setFont(chinese_font(TITLE_PT))
        heading.addWidget(self.title)
        heading.addStretch(1)
        column.addLayout(heading)
        self.bar = QProgressBar()
        self.bar.setObjectName("setupProgress")
        self.bar.setRange(0, _SCALE)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        column.addWidget(self.bar)
        column.addSpacing(4)
        self.icons: list[QLabel] = []
        self.notes: list[QLabel] = []
        for name in STEPS:
            line = QHBoxLayout()
            line.setSpacing(10)
            icon = QLabel()
            icon.setFixedSize(16, 16)
            icon.setAlignment(Qt.AlignCenter)
            line.addWidget(icon)
            label = QLabel(name)
            line.addWidget(label)
            line.addStretch(1)
            note = QLabel("")
            note.setObjectName("setupNote")
            note.setFont(chinese_font(SMALL_PT))
            line.addWidget(note)
            column.addLayout(line)
            self.icons.append(icon)
            self.notes.append(note)
        self.message = QLabel("")
        self.message.setObjectName("setupMessage")
        self.message.setWordWrap(True)
        self.message.hide()
        column.addWidget(self.message)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 4, 0, 0)
        buttons.setSpacing(8)
        buttons.addStretch(1)
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self._dismiss)
        buttons.addWidget(self.close_button)
        self.retry_button = QPushButton("重试")
        self.retry_button.setObjectName("primary")
        self.retry_button.clicked.connect(self.retry)
        buttons.addWidget(self.retry_button)
        self.buttons = QWidget()
        self.buttons.setLayout(buttons)
        self.buttons.hide()
        column.addWidget(self.buttons)

        self._target = 0.0
        self._value = 0.0
        self._tick = QTimer(self)
        self._tick.setInterval(30)
        self._tick.timeout.connect(self._advance)
        self._fade = QGraphicsOpacityEffect(self)
        self._fade.setOpacity(1.0)
        self.setGraphicsEffect(self._fade)
        self._anim = QPropertyAnimation(self._fade, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._after_fade)
        self.state = "idle"
        host.installEventFilter(self)
        self.hide()

    # The card follows the window's size and theme.
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
        return False

    def apply_theme(self, failed: bool = False) -> None:
        t = THEME
        chunk = t["red"] if failed else t["green"] if self.state == "ok" else t["accent_line"]
        self.setStyleSheet(
            f"""
            QWidget#setupScrim {{ background: {t["bg"]}; }}
            QFrame#setupCard {{
                background: {t["surface"]};
                border: 1px solid {t["border"]};
                border-radius: 12px;
            }}
            QFrame#setupCard QLabel {{ background: transparent; color: {t["text"]}; }}
            QFrame#setupCard QLabel#setupNote {{ color: {t["muted"]}; }}
            QFrame#setupCard QLabel#setupMessage {{ color: {t["red"]}; }}
            QProgressBar#setupProgress {{
                background: {t["surface_alt"]};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar#setupProgress::chunk {{
                background: {chunk};
                border-radius: 3px;
            }}
            """
        )
        _pointing(self)

    def start(self) -> None:
        self.state = "running"
        self.title.setText("正在检查环境")
        self.mark.hide()
        self.message.hide()
        self.buttons.hide()
        for index in range(len(STEPS)):
            self.step(index, "wait")
        self._value = self._target = 0.0
        self.bar.setValue(0)
        self.apply_theme()
        self._anim.stop()
        self._fade.setOpacity(1.0)
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self._tick.start()

    def step(self, index: int, state: str, note: str = "") -> None:
        """wait, run, ok or fail. While a step runs, the bar eases toward its end."""
        icon = self.icons[index]
        if state == "ok":
            icon.setPixmap(line_pixmap("check", 16, THEME["green"]))
            self._target = max(self._target, (index + 1) / len(STEPS))
        elif state == "fail":
            icon.setPixmap(line_pixmap("warning", 16, THEME["red"]))
        elif state == "run":
            icon.setPixmap(_watch_mark(THEME["accent_line"]))
            self._target = max(self._target, (index + 0.9) / len(STEPS))
        else:
            icon.setPixmap(_watch_mark(THEME["border"]))
        self.notes[index].setText(note)

    def succeed(self) -> None:
        """环境确认, a full green bar, then the card fades away by itself."""
        self.state = "ok"
        self._target = 1.0
        self.title.setText("环境确认")
        self.mark.setPixmap(line_pixmap("check", 22, THEME["green"]))
        self.mark.show()
        self.apply_theme()
        QTimer.singleShot(1300, self._fade_out)

    def fail(self, index: int, message: str) -> None:
        self.state = "failed"
        self.step(index, "fail")
        self.title.setText("环境有问题")
        self.mark.setPixmap(line_pixmap("warning", 22, THEME["red"]))
        self.mark.show()
        self.message.setText(message)
        self.message.show()
        self.buttons.show()
        self.apply_theme(failed=True)
        self.retry_button.setFocus()

    def _advance(self) -> None:
        # Ease toward the target; a long step (loading the models) keeps creeping, never jumps back.
        gap = self._target - self._value
        if gap > 0.0005:
            self._value += max(gap * 0.12, 0.0015)
        elif self.state in ("ok", "failed"):
            self._tick.stop()
        self._value = min(self._value, self._target)
        self.bar.setValue(round(self._value * _SCALE))

    def _fade_out(self) -> None:
        if self.state != "ok":
            return
        self._anim.stop()
        self._anim.setStartValue(self._fade.opacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _after_fade(self) -> None:
        if self._fade.opacity() <= 0.01:
            self._dismiss()

    def _dismiss(self) -> None:
        self._tick.stop()
        self.hide()
        self.state = "idle"
        self.dismissed.emit()
