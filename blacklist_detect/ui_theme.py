"""Colors, type, spacing, and stylesheets for every window.

Everything visual comes from the tokens here, so a window never hard-codes a
size or a color:

    Type      BODY_PT 14 px · SMALL_PT 12 px · SECTION_PT 16 px · TITLE_PT 20 px
              OVERLAY_PT 18 px for names drawn over the game
    Spacing   a 4 px grid: GAP 12, PAD 24; controls CONTROL_H 32 tall; rows ROW_H 40
    Corners   RADIUS 6 for controls, CARD_RADIUS 8 for cards and lists
    Color     THEME, built from roles (accent, surface, border, text, muted, danger …)
              for 浅色 or 深色, with the user's accent color. Red means danger or a
              blacklist hit and nothing else; tags are neutral chips.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPalette,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QWidget,
)

_family: str | None = None


def chinese_family() -> str:
    """A face that actually contains simplified Chinese. Qt does not fall back by itself.

    Asking Qt for every installed family is slow, and a big list made thousands of fonts,
    so the answer is kept once a Chinese face is found.
    """
    global _family
    if _family is not None:
        return _family
    from PySide6.QtGui import QFontDatabase

    installed = set(QFontDatabase.families())
    for name in (
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "微软雅黑",
        "Sarasa Gothic SC",
        "Noto Sans CJK SC",
        "Noto Sans SC",
        "Source Han Sans SC",
        "思源黑体",
        "PingFang SC",
        "SimHei",
        "黑体",
    ):
        if name in installed:
            _family = name
            return name
    return "Microsoft YaHei"


def _mix(start: str, end: str, amount: float) -> QColor:
    left = QColor(start)
    right = QColor(end)
    amount = max(0.0, min(1.0, amount))
    return QColor(
        round(left.red() + (right.red() - left.red()) * amount),
        round(left.green() + (right.green() - left.green()) * amount),
        round(left.blue() + (right.blue() - left.blue()) * amount),
    )


# Type scale, in points. One point is 1.33 px at 100% Windows scaling.
BODY_PT = 10.5  # 14 px: labels, buttons, inputs, table cells
SMALL_PT = 9  # 12 px: hints, captions, tags
SECTION_PT = 12  # 16 px: section and card titles
TITLE_PT = 15  # 20 px: page titles, empty-state headings
DIALOG_TITLE_PT = 13.5  # 18 px: a dialog's title
OVERLAY_PT = 13.5  # 18 px: names drawn over the game, read at a glance

# Spacing on a 4 px grid.
PAD = 24
GAP = 12
DIALOG_PAD = 24
CONTROL_H = 32
ROW_H = 40
RADIUS = 6
CARD_RADIUS = 8


def chinese_font(point_size: float = BODY_PT) -> QFont:
    font = QFont(chinese_family())
    font.setPointSizeF(point_size)
    font.setWeight(QFont.Weight.Normal)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias)
    return font


def ui_font() -> QFont:
    """Buttons and labels."""
    return chinese_font(BODY_PT)


def record_font() -> QFont:
    """Record names and times."""
    return chinese_font(BODY_PT)


# Each accent, as the light window shows it:
# page, ink, muted, wash, border, accent, accent line, accent hover, accent press, text on accent.
_LIGHT = {
    "蓝色": ("#f2f6fb", "#172033", "#5d6d82", "#e4eef8", "#d3deec", "#12325a", "#2c6cb3", "#1a4578", "#0c243f", "#f4f8ff"),
    "棕色": ("#f7f3ee", "#2a2118", "#6f6256", "#f3ebe3", "#e6d9cc", "#6b4428", "#a67c52", "#7d5334", "#4a2e1a", "#fff8f2"),
    "紫色": ("#f6f4fb", "#241833", "#6a5d80", "#eee8f6", "#ddd4ec", "#4a2d73", "#7a5caf", "#5c3b8c", "#321d52", "#f8f5ff"),
    "绿色": ("#f3f7f4", "#17241c", "#5c6e64", "#e5f0ea", "#d2e2d8", "#1b5340", "#3d8f6e", "#24664e", "#12382b", "#f4fbf7"),
    "红色": ("#fbf5f4", "#2c1818", "#7a6565", "#f6e8e6", "#ead8d4", "#a24f28", "#c46a3e", "#92471f", "#6e3416", "#fdf6ec"),
}
# The same accents brightened for the dark window: accent, hover, press.
_DARK = {
    "蓝色": ("#6aa6f0", "#86b8f4", "#4f8fdc"),
    "棕色": ("#d0a06e", "#dcb285", "#b98955"),
    "紫色": ("#ad91e6", "#bea6ec", "#957ad2"),
    "绿色": ("#5cbf95", "#79cda9", "#47a67f"),
    "红色": ("#e8936a", "#eea683", "#d47c52"),
}
APPEARANCES = ("light", "dark", "system")


def _palette(name: str, dark: bool) -> dict[str, str]:
    """Every color a window uses, by role, for one accent in light or dark."""
    if dark:
        accent, accent_hover, accent_press = _DARK[name]
        page, surface, surface_alt, border = "#15171b", "#1d2025", "#252930", "#343944"
        text, muted = "#e7e9ee", "#9aa2b0"
        colors = {
            "bg": page,
            "surface": surface,
            "surface_alt": surface_alt,
            "border": border,
            "text": text,
            "muted": muted,
            "hover": "#2a2e36",
            "selected": _mix(surface, accent, 0.26).name(),
            "accent": accent,
            "accent_line": accent_hover,
            "accent_hover": accent_hover,
            "accent_press": accent_press,
            "accent_wash": _mix(surface, accent, 0.18).name(),
            "on_accent": "#0e1116",
            "red": "#f0817a",
            "red_wash": "#3a2325",
            "red_hover": "#4a2b2d",
            "green": "#5fcb8c",
            "green_wash": "#1b3125",
            "green_hover": "#22402f",
            "gray": "#8d95a3",
            "gray_wash": "#24282f",
            "gray_hover": "#2c313a",
            "danger": "#f0817a",
            "danger_hover": "#3a2325",
            "warning": "#e0a245",
            "chip_bg": "#2d323b",
            "chip_text": "#d5d9e0",
            "chip_off_bg": "#22262d",
            "chip_off_line": "#4a505c",
            "toast_bg": "#e7e9ee",
            "toast_text": "#15171b",
            "toast_action": _LIGHT[name][5],
        }
    else:
        page, ink, muted, wash, border, accent, accent_line, accent_hover, accent_press, on_accent = _LIGHT[name]
        colors = {
            "bg": page,
            "surface": "#ffffff",
            "surface_alt": wash,
            "border": border,
            "text": ink,
            "muted": muted,
            "hover": wash,
            "selected": _mix(wash, accent, 0.10).name(),
            "accent": accent,
            "accent_line": accent_line,
            "accent_hover": accent_hover,
            "accent_press": accent_press,
            "accent_wash": _mix("#ffffff", accent_line, 0.14).name(),
            "on_accent": on_accent,
            "red": "#c23b2e",
            "red_wash": "#fff3f2",
            "red_hover": "#fde4e1",
            "green": "#1c7a3e",
            "green_wash": "#effaf3",
            "green_hover": "#e3f6eb",
            "gray": "#6b7280",
            "gray_wash": "#f3f4f6",
            "gray_hover": "#e6e8ec",
            "danger": "#b3261e",
            "danger_hover": "#fbe9e7",
            "warning": "#b45309",
            "chip_bg": "#eef0f3",
            "chip_text": "#3f4654",
            "chip_off_bg": "#f7f8fa",
            "chip_off_line": "#c5cad3",
            "toast_bg": "#1f2633",
            "toast_text": "#f3f5f8",
            "toast_action": _DARK[name][0],
        }
    colors["scheme"] = "dark" if dark else "light"
    return colors


# The accents as the light window shows them, for the swatches in 设置.
THEMES = {name: _palette(name, False) for name in _LIGHT}
# One dict shared by every module. use_theme changes it in place, so nobody holds an old copy.
THEME = dict(THEMES["蓝色"])


def system_is_dark() -> bool:
    """Whether Windows apps are set to dark. Elsewhere, light."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return int(value) == 0
    except OSError:
        return False


def wants_dark(appearance: str) -> bool:
    return appearance == "dark" or (appearance == "system" and system_is_dark())


def use_theme(name: str, appearance: str = "light") -> None:
    THEME.clear()
    THEME.update(_palette(name if name in _LIGHT else "蓝色", wants_dark(appearance)))


def is_dark() -> bool:
    return THEME.get("scheme") == "dark"


def accent_of(name: str) -> str:
    """One accent as the current 浅色 or 深色 window draws it, for its swatch."""
    return _palette(name if name in _LIGHT else "蓝色", is_dark())["accent"]


def _apply_theme(app: QApplication | None = None) -> None:
    """Keep every native control on the same palette as the stylesheet."""
    app = app or QApplication.instance()
    if app is None:
        return
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark if is_dark() else Qt.ColorScheme.Light)
    t = THEME
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(t["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(t["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t["surface_alt"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(t["surface"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t["selected"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(t["surface"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(t["muted"]))
    palette.setColor(QPalette.ColorRole.Mid, QColor(t["border"]))
    app.setPalette(palette)


def _button_rules(family: str) -> str:
    """Secondary (outlined), primary (filled), danger, and text buttons. Every surface uses this."""
    t = THEME
    return f"""
            QPushButton {{
                font-family: "{family}";
                font-size: {BODY_PT}pt;
                font-weight: 400;
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["border"]};
                border-radius: {RADIUS}px;
                padding: 0 14px;
                min-height: {CONTROL_H - 2}px;
            }}
            QPushButton#primary {{
                background: {t["accent"]};
                border-color: {t["accent"]};
                color: {t["on_accent"]};
            }}
            QPushButton#danger {{
                background: {t["surface"]};
                color: {t["danger"]};
                border-color: {t["danger"]};
            }}
            QPushButton:hover {{
                background: {t["hover"]};
                border-color: {t["accent_line"]};
            }}
            QPushButton:pressed {{ background: {t["selected"]}; }}
            QPushButton:disabled {{
                color: {t["muted"]};
                background: {t["surface_alt"]};
                border-color: {t["border"]};
            }}
            QPushButton#primary:hover {{
                background: {t["accent_hover"]};
                border-color: {t["accent_hover"]};
                color: {t["on_accent"]};
            }}
            QPushButton#primary:pressed {{
                background: {t["accent_press"]};
                color: {t["on_accent"]};
            }}
            QPushButton#danger:hover {{
                background: {t["danger_hover"]};
                color: {t["danger"]};
                border-color: {t["danger"]};
            }}
            QPushButton#sideAction {{
                background: transparent;
                border: none;
                color: {t["muted"]};
                font-size: {SMALL_PT}pt;
                text-align: left;
                padding: 0 12px;
                min-height: 30px;
                border-radius: {RADIUS}px;
            }}
            QPushButton#sideAction:hover {{
                background: {t["hover"]};
                color: {t["text"]};
            }}
            QPushButton#link {{
                background: transparent;
                border: none;
                color: {t["accent_line"]};
                padding: 0 4px;
                min-height: 0;
                font-size: {SMALL_PT}pt;
            }}
            QPushButton#link:hover {{
                background: transparent;
                color: {t["accent_hover"]};
                text-decoration: underline;
            }}
            QPushButton#link:focus {{
                border: none;
                text-decoration: underline;
            }}
            """


def _input_rules(family: str) -> str:
    t = THEME
    return f"""
            QLineEdit, QPlainTextEdit {{
                font-family: "{family}";
                font-size: {BODY_PT}pt;
                font-weight: 400;
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["border"]};
                border-radius: {RADIUS}px;
                padding: 6px 10px;
                selection-background-color: {t["selected"]};
                selection-color: {t["text"]};
            }}
            QLineEdit {{
                padding: 0 10px;
                min-height: {CONTROL_H - 2}px;
            }}
            QLineEdit:hover, QPlainTextEdit:hover {{
                border: 1px solid {t["accent_line"]};
            }}
            QLineEdit:focus, QPlainTextEdit:focus {{
                border: 1px solid {t["accent"]};
            }}
            QLineEdit:disabled {{
                color: {t["muted"]};
                background: {t["surface_alt"]};
                border: 1px solid {t["border"]};
            }}
            """


def _card_rules() -> str:
    t = THEME
    return f"""
            QWidget#settingsCard, QWidget#recordCard, QWidget#noticeCard {{
                background: {t["surface"]};
                border: 1px solid {t["border"]};
                border-radius: {CARD_RADIUS}px;
            }}
            QWidget#settingsRow {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {t["border"]};
            }}
            QWidget#settingsRowLast {{
                background: transparent;
                border: none;
            }}
            """


# Focus that arrives this way came from the keyboard. Only then is a focus ring drawn.
KEYBOARD_FOCUS = (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ShortcutFocusReason)


class _FocusRing(QWidget):
    """The keyboard focus ring of one button, painted over it just inside its edge.

    A stylesheet cannot draw it: Qt puts a :focus outline around the label, and a
    thicker border moves the label. This child is painted last, so it sits on the fill.
    """

    def __init__(self, button: QPushButton) -> None:
        super().__init__(button)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.hide()
        button.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        kind = event.type()
        if kind == QEvent.Type.FocusIn:
            self.setGeometry(watched.rect())
            self.setVisible(event.reason() in KEYBOARD_FOCUS)
            self.raise_()
        elif kind == QEvent.Type.FocusOut:
            self.hide()
        elif kind == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return False

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        button = self.parentWidget()
        filled = button.objectName() == "primary" or (button.objectName() == "segment" and button.isChecked())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(THEME["on_accent"] if filled else THEME["text"]), 2))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(3, 3, -3, -3), RADIUS - 2, RADIUS - 2)


def _pointing(root) -> None:
    """Buttons show a hand, and take focus from Tab but not from a click, like Windows buttons.

    It also keeps the input method switchable everywhere in root (see keep_input_method).
    """
    for widget in (*root.findChildren(QPushButton), *root.findChildren(QCheckBox)):
        widget.setCursor(Qt.PointingHandCursor)
        if widget.focusPolicy() == Qt.NoFocus:
            continue
        widget.setFocusPolicy(Qt.TabFocus)
        if isinstance(widget, QPushButton) and widget.findChild(_FocusRing) is None and widget.objectName() != "link":
            _FocusRing(widget)
    keep_input_method(root)


# Widgets that take text decide about the input method themselves: a read-only box, like
# the hotkey box, turns it off on purpose so a key goes straight in.
_TAKES_TEXT = (QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox)


def keep_input_method(root: QWidget) -> None:
    """Keep 中文 input switchable while a list, a table or a button has the focus.

    Qt takes a window's input method away whenever the focused widget does not take text,
    and Windows then types only English in the whole window until a text box is clicked.
    Other Windows apps keep it, so 中/英 can be switched at any time. Marking every focusable
    widget as taking input keeps it; a list or a table even uses what is typed to jump to a row.
    """
    for widget in (root, *root.findChildren(QWidget)):
        if isinstance(widget, _TAKES_TEXT):
            continue
        if widget is root or widget.focusPolicy() != Qt.NoFocus:
            widget.setAttribute(Qt.WA_InputMethodEnabled, True)
        if isinstance(widget, QAbstractItemView) and widget.findChild(_InputMethodKeeper) is None:
            _InputMethodKeeper(widget)


class _InputMethodKeeper(QObject):
    """A list or a table turns the input method off again each time its current row changes
    to one that cannot be edited. This answers for it, when asked, that it takes input."""

    def __init__(self, view: QAbstractItemView) -> None:
        super().__init__(view)
        view.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        if event.type() != QEvent.Type.InputMethodQuery:
            return False
        asked = event.queries().value
        enabled = Qt.InputMethodQuery.ImEnabled
        if not asked & enabled.value:
            return False
        # Windows asks for several things at once, ImEnabled among them. Each is answered
        # as the view would answer it, except that it takes input.
        for bit in range(32):
            if not asked & (1 << bit) or 1 << bit == enabled.value:
                continue
            try:
                query = Qt.InputMethodQuery(1 << bit)
            except ValueError:
                continue
            event.setValue(query, watched.inputMethodQuery(query))
        event.setValue(enabled, watched.isEnabled())
        event.accept()
        return True


def _menu_style(family: str) -> str:
    t = THEME
    return f"""
            QMenu {{
                font-family: "{family}";
                font-size: {BODY_PT}pt;
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["border"]};
                border-radius: {CARD_RADIUS}px;
                padding: 4px;
            }}
            QMenu::item {{
                font-family: "{family}";
                background: transparent;
                color: {t["text"]};
                border-radius: {RADIUS}px;
                padding: 6px 14px;
            }}
            QMenu::item:selected {{ background: {t["selected"]}; }}
            """


def _kit_rules(family: str) -> str:
    """Switch-free parts of the control kit in ui_kit.py: segments, icon buttons, toasts, cards."""
    t = THEME
    return f"""
            QPushButton#segment {{
                border-radius: 0;
                margin: 0;
                padding: 0 14px;
            }}
            QPushButton#segment[place="first"] {{
                border-top-left-radius: {RADIUS}px;
                border-bottom-left-radius: {RADIUS}px;
            }}
            QPushButton#segment[place="middle"] {{ border-left: none; }}
            QPushButton#segment[place="last"] {{
                border-left: none;
                border-top-right-radius: {RADIUS}px;
                border-bottom-right-radius: {RADIUS}px;
            }}
            QPushButton#segment[place="only"] {{ border-radius: {RADIUS}px; }}
            QPushButton#segment:checked, QPushButton#segment:checked:hover {{
                background: {t["accent"]};
                border-color: {t["accent"]};
                color: {t["on_accent"]};
            }}
            QPushButton#iconButton {{
                background: transparent;
                border: none;
                border-radius: {RADIUS}px;
                padding: 0;
                min-height: 0;
            }}
            QPushButton#iconButton:hover {{ background: {t["hover"]}; }}
            QPushButton#iconButton:pressed {{ background: {t["selected"]}; }}
            QWidget#toast {{
                background: {t["toast_bg"]};
                border-radius: {CARD_RADIUS}px;
            }}
            QLabel#toastText {{
                font-family: "{family}";
                font-size: {BODY_PT}pt;
                color: {t["toast_text"]};
                background: transparent;
            }}
            QPushButton#toastAction {{
                font-family: "{family}";
                font-size: {BODY_PT}pt;
                font-weight: 600;
                color: {t["toast_action"]};
                background: transparent;
                border: none;
                padding: 0 6px;
                min-height: 0;
            }}
            QPushButton#toastAction:hover {{ background: transparent; text-decoration: underline; }}
            QFrame#section {{
                background: {t["surface"]};
                border: 1px solid {t["border"]};
                border-radius: {CARD_RADIUS}px;
            }}
            QLabel#sectionTitle {{
                font-family: "{family}";
                font-size: {SECTION_PT}pt;
                font-weight: 600;
                color: {t["text"]};
                background: transparent;
            }}
            QLabel#sectionTitle[group="true"] {{ font-size: {BODY_PT}pt; }}
            QFrame#sectionGroup {{ background: transparent; border: none; }}
            QLabel#dialogTitle {{
                font-family: "{family}";
                font-size: {DIALOG_TITLE_PT}pt;
                font-weight: 600;
                color: {t["text"]};
                background: transparent;
            }}
            QFrame#sectionLine {{ background: {t["border"]}; border: none; }}
            QWidget#sectionRow {{ background: transparent; }}
            QLabel#rowLabel {{
                font-family: "{family}";
                font-size: {BODY_PT}pt;
                color: {t["text"]};
                background: transparent;
            }}
            QLabel#rowHint, QLabel#emptyHint {{
                font-family: "{family}";
                font-size: {SMALL_PT}pt;
                color: {t["muted"]};
                background: transparent;
            }}
            QLabel#emptyIcon {{ background: transparent; }}
            """


def _popover_rules(family: str) -> str:
    """The small box that opens under 角色名称 in the header."""
    t = THEME
    return f"""
            QFrame#popover {{
                background: {t["surface"]};
                border: 1px solid {t["border"]};
                border-radius: {CARD_RADIUS}px;
            }}
            QLabel#popoverTitle {{
                font-family: "{family}";
                font-size: {BODY_PT}pt;
                font-weight: 600;
                color: {t["text"]};
                background: transparent;
            }}
            """


def _window_style(family: str) -> str:
    t = THEME
    return f"""
            QWidget#root, QLabel, QLineEdit, QPlainTextEdit, QCheckBox,
            QTabWidget, QTabBar, QListWidget, QTableWidget, QHeaderView, QTableWidget QWidget {{
                font-family: "{family}";
            }}
            QMainWindow, QWidget#root, QTabWidget, QTabBar, QTabWidget::pane {{
                background: {t["bg"]};
                color: {t["text"]};
                border: none;
                padding: 0;
                margin: 0;
            }}
            QLabel {{ color: {t["text"]}; }}
            QTabBar {{ height: 0; max-height: 0; }}
            QWidget#tabHeader {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {t["border"]};
            }}
            QWidget#tabHeader QLabel {{ background: transparent; }}
            QScrollArea#settingsScroll, QWidget#settingsBody {{
                background: transparent;
                border: none;
            }}
            QFrame#headerDivider {{
                background: {t["border"]};
                border: none;
            }}
            QLabel#sub {{
                font-family: "{family}";
                font-size: {SMALL_PT}pt;
                font-weight: 400;
                color: {t["muted"]};
            }}
            QLabel#emptyTitle {{
                font-family: "{family}";
                font-size: {TITLE_PT}pt;
                font-weight: 400;
                color: {t["text"]};
                background: transparent;
            }}
            """ + _popover_rules(family) + _kit_rules(family) + _input_rules(family) + f"""
            QPlainTextEdit, QTableWidget, QListWidget {{
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["border"]};
                border-radius: {CARD_RADIUS}px;
                padding: 6px 10px;
            }}
            QListWidget::item {{
                font-family: "{family}";
                background: transparent;
                color: {t["text"]};
                padding: 6px 10px;
                border: none;
            }}
            QListWidget#history {{
                font-family: "{family}";
                font-size: {BODY_PT}pt;
                font-weight: 400;
                color: {t["text"]};
                background: transparent;
                border: none;
                padding: 0;
                outline: none;
            }}
            QListWidget#history:focus {{
                border: none;
                outline: none;
            }}
            QListWidget#history::item {{
                padding: 2px 8px;
                margin: 1px 0;
                border: none;
                border-radius: {RADIUS}px;
                outline: none;
                font-weight: 400;
                color: {t["text"]};
            }}
            QListWidget#history::item:selected, QListWidget#history::item:selected:hover {{
                color: {t["text"]};
                font-weight: 400;
            }}
            QListWidget#tags {{
                background: transparent;
                border: none;
                padding: 0;
                outline: none;
            }}
            QListWidget#tags:focus {{
                border: none;
                outline: none;
            }}
            QListWidget#tags::item {{
                padding: 0;
                margin: 1px 0;
                border: none;
                border-radius: {RADIUS}px;
                outline: none;
            }}
            QLabel#sideTitle {{
                font-family: "{family}";
                font-size: {SMALL_PT}pt;
                font-weight: 600;
                color: {t["muted"]};
                background: transparent;
            }}
            QListWidget::item:hover {{ background: {t["hover"]}; }}
            QListWidget::item:selected, QListWidget::item:selected:hover {{
                background: {t["selected"]};
                color: {t["text"]};
            }}
            QTableWidget::item {{
                background: {t["surface"]};
                color: {t["text"]};
                border: none;
            }}
            QTableWidget::item:hover {{ background: {t["hover"]}; }}
            QTableWidget::item:selected, QTableWidget::item:selected:hover {{
                background: {t["selected"]};
                color: {t["text"]};
            }}
            QTableWidget#recordNames::item,
            QTableWidget#recordNames::item:hover,
            QTableWidget#recordNames::item:selected {{
                background: transparent;
            }}
            QTableWidget#blacklist {{
                background: {t["surface"]};
                border-radius: {CARD_RADIUS}px;
                padding: 0;
                outline: none;
            }}
            QTableWidget#blacklist:focus {{
                border: 1px solid {t["border"]};
                outline: none;
            }}
            QTableWidget#blacklist::item {{
                background: {t["surface"]};
                padding: 8px 12px;
                border: none;
                outline: none;
            }}
            QTableWidget#blacklist::item:hover {{
                background: {t["surface"]};
                color: {t["text"]};
            }}
            QTableWidget#blacklist::item:selected,
            QTableWidget#blacklist::item:selected:hover {{
                background: {t["hover"]};
                color: {t["text"]};
            }}
            QHeaderView {{ background: {t["surface"]}; }}
            QHeaderView::section, QTableCornerButton::section {{
                background: {t["surface_alt"]};
                color: {t["muted"]};
                border: none;
                padding: 8px 14px;
                font-size: {SMALL_PT}pt;
                font-weight: 400;
            }}
            QScrollBar:vertical, QScrollBar:horizontal {{
                background: transparent;
                border: none;
                margin: 0;
            }}
            QScrollBar:vertical {{ width: 10px; }}
            QScrollBar:horizontal {{ height: 10px; }}
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background: {t["border"]};
                border-radius: 5px;
                min-height: 24px;
                min-width: 24px;
            }}
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
                background: {t["accent_line"]};
            }}
            QScrollBar::add-line, QScrollBar::sub-line,
            QScrollBar::add-page, QScrollBar::sub-page {{
                background: transparent;
                height: 0;
                width: 0;
            }}
            QWidget#tableHead {{
                background: {t["surface_alt"]};
                border: none;
                border-bottom: 1px solid {t["border"]};
                border-top-left-radius: {CARD_RADIUS - 1}px;
                border-top-right-radius: {CARD_RADIUS - 1}px;
            }}
            QWidget#tableHead QLabel {{
                font-family: "{family}";
                color: {t["text"]};
                background: transparent;
            }}
            QWidget#tableHead QLabel#recordTitle {{ font-size: {BODY_PT}pt; }}
            QWidget#recordCard QTableWidget#recordNames {{
                background: {t["surface"]};
                border: none;
                border-radius: 0;
                padding: 0;
            }}
            """ + _card_rules() + f"""
            QCheckBox {{
                spacing: 8px;
                min-height: 28px;
                color: {t["text"]};
                background: transparent;
            }}
            QCheckBox:hover {{ color: {t["accent_line"]}; }}
            QToolTip {{
                font-family: "{family}";
                font-size: {SMALL_PT}pt;
                color: {t["text"]};
                background: {t["surface"]};
                border: 1px solid {t["border"]};
                padding: 4px 8px;
            }}
            """ + _button_rules(family) + f"""
            QPushButton#rowDelete {{
                background: transparent;
                color: {t["danger"]};
                border: none;
                border-radius: {RADIUS}px;
                padding: 0;
                min-width: 0;
                min-height: 0;
                max-height: 22px;
                font-size: {BODY_PT}pt;
                font-weight: 400;
            }}
            QPushButton#rowDelete:hover {{
                background: {t["danger_hover"]};
                color: {t["danger"]};
            }}
            QPushButton[clearPair="true"] {{
                padding: 0 8px;
            }}
            """ + _menu_style(family) + f"""
            QPushButton#mode:checked,
            QPushButton#mode:checked:hover {{
                background: {t["accent"]};
                border-color: {t["accent"]};
                color: {t["on_accent"]};
            }}
            """


def _dialog_style(family: str) -> str:
    t = THEME
    return f"""
            QDialog, QMessageBox {{
                font-family: "{family}";
                background: {t["bg"]};
                color: {t["text"]};
            }}
            QDialog#modal {{ background: transparent; }}
            QFrame#dialogCard {{
                background: {t["surface"]};
                border: 1px solid {t["border"]};
                border-radius: 12px;
            }}
            QLabel {{
                font-family: "{family}";
                font-size: {BODY_PT}pt;
                background: transparent;
                color: {t["text"]};
            }}
            QLabel#field {{
                font-family: "{family}";
                font-size: {BODY_PT}pt;
                font-weight: 400;
                color: {t["text"]};
                background: transparent;
            }}
            QLabel#sub {{
                font-family: "{family}";
                font-size: {SMALL_PT}pt;
                font-weight: 400;
                color: {t["muted"]};
                background: transparent;
            }}
            QFrame#dialogFooter {{
                background: {t["bg"]};
                border: none;
                border-top: 1px solid {t["border"]};
                border-bottom-left-radius: 11px;
                border-bottom-right-radius: 11px;
            }}
            QLabel#error {{
                font-family: "{family}";
                font-size: {SMALL_PT}pt;
                color: {t["red"]};
                background: transparent;
            }}
            QCheckBox {{
                font-family: "{family}";
                background: transparent;
                spacing: 8px;
                min-height: 28px;
                padding: 2px 4px;
                color: {t["text"]};
            }}
            QCheckBox:hover {{
                background: {t["hover"]};
                color: {t["text"]};
            }}
            QToolTip {{
                font-family: "{family}";
                font-size: {SMALL_PT}pt;
                color: {t["text"]};
                background: {t["surface"]};
                border: 1px solid {t["border"]};
                padding: 4px 8px;
            }}
            """ + _input_rules(family) + _button_rules(family) + _kit_rules(family)


def _colorref(value: str):
    import ctypes

    color = QColor(value)
    return ctypes.c_uint((color.blue() << 16) | (color.green() << 8) | color.red())


def _caption_color(widget) -> None:
    """Match the window caption to the chrome, dark or light. Windows only."""
    if sys.platform != "win32":
        return
    import ctypes

    hwnd = int(widget.winId())
    dark = ctypes.c_int(1 if is_dark() else 0)
    dwm = ctypes.windll.dwmapi
    values = (
        (20, dark),
        (19, dark),
        (34, _colorref(THEME["border"])),
        (35, _colorref(THEME["bg"])),
        (36, _colorref(THEME["text"])),
    )
    for attribute, value in values:
        dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))


def _page(layout) -> None:
    layout.setContentsMargins(0, GAP, 0, 0)
    layout.setSpacing(GAP)
