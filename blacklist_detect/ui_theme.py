"""Colors, fonts, and stylesheets for every window."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QPushButton,
)


def chinese_family() -> str:
    """A face that actually contains simplified Chinese. Qt does not fall back by itself."""
    from PySide6.QtGui import QFontDatabase

    installed = set(QFontDatabase.families())
    for name in (
        "Microsoft YaHei",
        "微软雅黑",
        "Microsoft YaHei UI",
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


READ_PT = 13
SMALL_PT = 11
TITLE_PT = 15


def chinese_font(point_size: int = READ_PT) -> QFont:
    font = QFont(chinese_family())
    font.setPointSize(point_size)
    font.setWeight(QFont.Weight.Normal)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias)
    return font


def ui_font() -> QFont:
    """Buttons use the same size and weight as the names."""
    return chinese_font(READ_PT)


def record_font() -> QFont:
    """Record names and times, the same reading size as the rest of the window."""
    return chinese_font(READ_PT)


# One inset and one corner for the whole window.
PAD = 24
GAP = 12
DIALOG_PAD = 20
RADIUS = 8

def _palette(
    page: str,
    ink: str,
    muted: str,
    wash: str,
    edge: str,
    accent: str,
    accent_line: str,
    accent_hover: str,
    accent_press: str,
    on_accent: str,
) -> dict[str, str]:
    return {
        "bg": page,
        "text": ink,
        "muted": muted,
        "surface": "#ffffff",
        "line": edge,
        "button": "#ffffff",
        "button_line": edge,
        "selected": wash,
        "head": wash,
        "head_text": ink,
        "gold": accent,
        "gold_line": accent_line,
        "on_gold": on_accent,
        "green": "#1c7a3e",
        "green_wash": "#f3fbf6",
        "green_hover": "#e3f6eb",
        "red": "#c23b2e",
        "red_wash": "#fff6f6",
        "red_hover": "#fde4e1",
        "gray": "#6b7280",
        "gray_wash": "#f3f4f6",
        "gray_hover": "#e6e8ec",
        "add": accent,
        "danger": "#a33b2c",
        "hover": wash,
        "gold_hover": accent_hover,
        "gold_press": accent_press,
        "danger_hover": "#f8e6e1",
    }


THEMES = {
    "蓝色": _palette("#f2f6fb", "#172033", "#5d6d82", "#e4eef8", "#d3deec", "#12325a", "#2c6cb3", "#1a4578", "#0c243f", "#f4f8ff"),
    "棕色": _palette("#f7f3ee", "#2a2118", "#6f6256", "#f3ebe3", "#e6d9cc", "#6b4428", "#a67c52", "#7d5334", "#4a2e1a", "#fff8f2"),
    "紫色": _palette("#f6f4fb", "#241833", "#6a5d80", "#eee8f6", "#ddd4ec", "#4a2d73", "#7a5caf", "#5c3b8c", "#321d52", "#f8f5ff"),
    "绿色": _palette("#f3f7f4", "#17241c", "#5c6e64", "#e5f0ea", "#d2e2d8", "#1b5340", "#3d8f6e", "#24664e", "#12382b", "#f4fbf7"),
    "红色": _palette("#fbf5f4", "#2c1818", "#7a6565", "#f6e8e6", "#ead8d4", "#a24f28", "#c46a3e", "#92471f", "#6e3416", "#fdf6ec"),
}
# One dict shared by every module. use_theme changes it in place, so nobody holds an old copy.
THEME = dict(THEMES["蓝色"])


def use_theme(name: str) -> None:
    THEME.clear()
    THEME.update(THEMES.get(name, THEMES["蓝色"]))


def _apply_theme(app: QApplication | None = None) -> None:
    """Keep every native control on the same palette, even when Windows is dark."""
    app = app or QApplication.instance()
    if app is None:
        return
    scheme = Qt.ColorScheme.Light
    app.styleHints().setColorScheme(scheme)
    t = THEME
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(t["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(t["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t["head"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(t["button"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t["selected"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(t["surface"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(t["muted"]))
    palette.setColor(QPalette.ColorRole.Mid, QColor(t["line"]))
    app.setPalette(palette)


def _button_rules(family: str) -> str:
    """Ghost buttons, filled primary, and the danger outline. Every surface uses this."""
    t = THEME
    return f"""
            QPushButton {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                background: {t["button"]};
                color: {t["text"]};
                border: 1px solid {t["button_line"]};
                border-radius: 8px;
                padding: 0 16px;
                min-height: 36px;
            }}
            QPushButton#primary {{
                background: {t["gold"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#danger {{
                background: {t["button"]};
                color: {t["danger"]};
                border-color: {t["danger"]};
            }}
            QPushButton:hover {{
                background: {t["hover"]};
                border-color: {t["gold_line"]};
            }}
            QPushButton:pressed {{ background: {t["selected"]}; }}
            QPushButton#primary:hover {{
                background: {t["gold_hover"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#primary:pressed {{
                background: {t["gold_press"]};
                color: {t["on_gold"]};
            }}
            QPushButton#danger:hover {{
                background: {t["danger_hover"]};
                color: {t["danger"]};
                border-color: {t["danger"]};
            }}
            QPushButton#recheck {{
                font-size: 11pt;
                background: {t["gold"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
                border-radius: 8px;
                padding: 0 10px;
                min-height: 26px;
            }}
            QPushButton#recheck:hover {{
                background: {t["gold_hover"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#recheck:pressed {{
                background: {t["gold_press"]};
                color: {t["on_gold"]};
            }}
            """


def _input_rules(family: str) -> str:
    t = THEME
    return f"""
            QLineEdit, QPlainTextEdit {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                border-radius: 8px;
                padding: 8px 12px;
            }}
            QLineEdit {{
                padding: 4px 12px;
                min-height: 28px;
            }}
            QLineEdit:hover, QPlainTextEdit:hover {{
                border: 1px solid {t["gold_line"]};
            }}
            QLineEdit:focus, QPlainTextEdit:focus {{
                border: 1px solid {t["gold"]};
            }}
            QLineEdit:disabled {{
                color: {t["muted"]};
                background: {t["head"]};
                border: 1px solid {t["line"]};
            }}
            """


def _card_rules() -> str:
    t = THEME
    return f"""
            QWidget#settingsCard, QWidget#recordCard, QWidget#noticeCard {{
                background: {t["surface"]};
                border: 1px solid {t["line"]};
                border-radius: 12px;
            }}
            QWidget#settingsRow {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {t["line"]};
            }}
            QWidget#settingsRowLast {{
                background: transparent;
                border: none;
            }}
            """


def _pointing(root) -> None:
    for widget in (*root.findChildren(QPushButton), *root.findChildren(QCheckBox)):
        widget.setCursor(Qt.PointingHandCursor)


def _menu_style(family: str) -> str:
    t = THEME
    return f"""
            QMenu {{
                font-family: "{family}";
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                font-family: "{family}";
                background: transparent;
                color: {t["text"]};
                border-radius: 6px;
                padding: 8px 14px;
            }}
            QMenu::item:selected {{ background: {t["selected"]}; }}
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
            QTabBar {{ height: 0; max-height: 0; }}
            QWidget#tabHeader {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {t["line"]};
            }}
            QWidget#tabHeader QLabel {{ background: transparent; }}
            QWidget#tabHeader QWidget#modeCluster, QWidget#modeCycle {{
                background: transparent;
                border: none;
            }}
            QLabel#sub {{
                font-family: "{family}";
                font-size: 11pt;
                font-weight: 400;
                color: {t["muted"]};
            }}
            QLabel#emptyTitle {{
                font-family: "{family}";
                font-size: 15pt;
                font-weight: 400;
                color: {t["text"]};
                background: transparent;
            }}
            QLabel#clear {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: {t["green"]};
                background: transparent;
            }}
            QLabel#hit {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: {t["red"]};
                background: transparent;
            }}
            QLabel#idle {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: {t["muted"]};
                background: transparent;
            }}
            QLabel#status {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: {t["text"]};
                background: transparent;
            }}
            QLabel#watchOn {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: {t["green"]};
                background: transparent;
            }}
            QLabel#watchOff {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: #6b4428;
                background: transparent;
            }}
            QLabel#hotkey {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: #6b4428;
                background: transparent;
            }}
            """ + _input_rules(family) + f"""
            QPlainTextEdit, QTableWidget, QListWidget {{
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                border-radius: 8px;
                padding: 8px 12px;
            }}
            QListWidget::item {{
                font-family: "{family}";
                background: transparent;
                color: {t["text"]};
                padding: 8px 12px;
                border: none;
            }}
            QListWidget#history {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: {t["text"]};
                padding: 0;
                outline: none;
                border-radius: 12px;
            }}
            QListWidget#history:focus {{
                border: 1px solid {t["line"]};
                outline: none;
            }}
            QListWidget#history::item {{
                padding: 2px 8px;
                margin: 1px 4px;
                border: none;
                border-radius: 8px;
                outline: none;
                font-weight: 400;
                color: {t["text"]};
            }}
            QListWidget#history::item:selected, QListWidget#history::item:selected:hover {{
                color: {t["text"]};
                font-weight: 400;
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
                border-radius: 12px;
                padding: 0;
                outline: none;
            }}
            QTableWidget#blacklist:focus {{
                border: 1px solid {t["line"]};
                outline: none;
            }}
            QTableWidget#blacklist::item {{
                background: {t["surface"]};
                padding: 10px 14px;
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
                background: {t["head"]};
                color: {t["head_text"]};
                border: none;
                padding: 10px 16px;
                font-size: 13pt;
                font-weight: 400;
            }}
            QScrollBar:vertical, QScrollBar:horizontal {{
                background: {t["surface"]};
                border: none;
                margin: 0;
            }}
            QScrollBar:vertical {{ width: 10px; }}
            QScrollBar:horizontal {{ height: 10px; }}
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background: {t["button_line"]};
                border-radius: 5px;
                min-height: 24px;
                min-width: 24px;
            }}
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
                background: {t["gold_line"]};
            }}
            QScrollBar::add-line, QScrollBar::sub-line,
            QScrollBar::add-page, QScrollBar::sub-page {{
                background: transparent;
                height: 0;
                width: 0;
            }}
            QWidget#tableHead {{
                background: {t["head"]};
                border: none;
                border-bottom: 1px solid {t["line"]};
                border-top-left-radius: 11px;
                border-top-right-radius: 11px;
            }}
            QWidget#tableHead QLabel {{
                font-family: "{family}";
                color: {t["head_text"]};
                background: transparent;
            }}
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
            QCheckBox:hover {{ color: {t["gold"]}; }}
            """ + _button_rules(family) + f"""
            QPushButton#rowDelete {{
                background: transparent;
                color: {t["danger"]};
                border: none;
                border-radius: 6px;
                padding: 0;
                min-width: 0;
                min-height: 0;
                max-height: 22px;
                font-size: 13pt;
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
            QPushButton#tab {{
                color: {t["muted"]};
                background: transparent;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                margin: 0 2px;
                min-height: 28px;
                max-height: 28px;
            }}
            QPushButton#tab:hover {{
                color: {t["text"]};
                background: {t["hover"]};
                border: none;
            }}
            QPushButton#tab:checked,
            QPushButton#tab:checked:hover,
            QPushButton#tab:checked:pressed {{
                color: {t["gold"]};
                background: {t["selected"]};
                border: none;
            }}
            QPushButton#tab:pressed {{
                background: {t["hover"]};
                border: none;
            }}
            QPushButton#mode:checked,
            QPushButton#mode:checked:hover {{
                background: {t["gold"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#tagNew {{
                background: transparent;
                border: none;
                padding: 0;
                margin: 0;
                min-width: 0;
                min-height: 0;
                font-size: 11pt;
                font-weight: 400;
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
            QLabel {{
                font-family: "{family}";
                background: transparent;
                color: {t["text"]};
            }}
            QLabel#field, QLabel#sub {{
                font-family: "{family}";
                font-size: 11pt;
                font-weight: 400;
                color: {t["muted"]};
                background: transparent;
            }}
            QLabel#error {{
                font-family: "{family}";
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
            """ + _input_rules(family) + _button_rules(family)


def _colorref(value: str):
    import ctypes

    color = QColor(value)
    return ctypes.c_uint((color.blue() << 16) | (color.green() << 8) | color.red())


def _caption_color(widget) -> None:
    """Match the window caption to the chrome. Windows only."""
    if sys.platform != "win32":
        return
    import ctypes

    hwnd = int(widget.winId())
    dark = ctypes.c_int(0)
    dwm = ctypes.windll.dwmapi
    values = (
        (20, dark),
        (19, dark),
        (34, _colorref(THEME["line"])),
        (35, _colorref(THEME["bg"])),
        (36, _colorref(THEME["text"])),
    )
    for attribute, value in values:
        dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))


def _page(layout) -> None:
    layout.setContentsMargins(0, GAP, 0, 0)
    layout.setSpacing(GAP)
