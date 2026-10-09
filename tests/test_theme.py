"""Colors come from roles, in 浅色 and 深色, and stay readable."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect import ui_theme  # noqa: E402
from blacklist_detect.storage import Store  # noqa: E402
from blacklist_detect.ui_theme import _palette  # noqa: E402

ACCENTS = tuple(ui_theme.THEMES)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _luminance(value: str) -> float:
    color = QColor(value)

    def channel(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(color.red()) + 0.7152 * channel(color.green()) + 0.0722 * channel(color.blue())


def contrast(a: str, b: str) -> float:
    light, dark = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_every_accent_has_the_same_roles_in_light_and_dark():
    keys = set(_palette("蓝色", False))
    for name in ACCENTS:
        for dark in (False, True):
            palette = _palette(name, dark)
            assert set(palette) == keys, (name, dark)
            assert palette["scheme"] == ("dark" if dark else "light")


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("name", ACCENTS)
def test_text_meets_wcag_aa(name, dark):
    """4.5:1 for body text and buttons; 3:1 for muted captions and the hit/clear colors on their wash."""
    t = _palette(name, dark)
    assert contrast(t["text"], t["bg"]) >= 4.5
    assert contrast(t["text"], t["surface"]) >= 4.5
    assert contrast(t["on_accent"], t["accent"]) >= 4.5, "text on the primary button"
    assert contrast(t["chip_text"], t["chip_bg"]) >= 4.5, "tag chips"
    assert contrast(t["muted"], t["surface"]) >= 3.0
    assert contrast(t["red"], t["red_wash"]) >= 4.5, "red tag pills"
    assert contrast(t["green"], t["green_wash"]) >= 3.0
    assert contrast(t["danger"], t["surface"]) >= 4.5


def test_tags_are_red_pills_in_both_modes(qapp):
    from blacklist_detect.ui import TagPill

    for dark in (False, True):
        ui_theme.use_theme("蓝色", "dark" if dark else "light")
        pill = TagPill("炸房")
        assert pill._wash == ui_theme.THEME["red_wash"]
        assert pill._ink == ui_theme.THEME["red"]
    ui_theme.use_theme("蓝色", "light")


def test_the_appearance_is_saved(tmp_path):
    store = Store(tmp_path)
    assert store.appearance == "light"
    store.appearance = "system"
    store.save_settings()
    assert Store(tmp_path).appearance == "system"
    store.reset()
    assert Store(tmp_path).appearance == "light"


def test_dark_switches_the_window_and_back(qapp, tmp_path, monkeypatch):
    from blacklist_detect.ui import MainWindow, TagPill

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window._watch_timer.stop()
    assert ui_theme.is_dark() is False
    window.appearance_buttons["dark"].click()
    assert window.store.appearance == "dark"
    assert ui_theme.is_dark() is True
    assert ui_theme.THEME["bg"] in window.styleSheet()
    assert window.theme_buttons["蓝色"]._color == ui_theme.accent_of("蓝色") == _palette("蓝色", True)["accent"]
    chip = TagPill("炸房")
    assert chip._wash == ui_theme.THEME["red_wash"]
    window.appearance_buttons["light"].click()
    assert ui_theme.is_dark() is False
    assert window.theme_buttons["蓝色"]._color == _palette("蓝色", False)["accent"]
    window.close()


def test_follow_system_reads_windows(qapp, tmp_path, monkeypatch):
    from blacklist_detect.ui import MainWindow

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    dark_system = [True]
    monkeypatch.setattr(ui_theme, "system_is_dark", lambda: dark_system[0])
    window = MainWindow()
    window._watch_timer.stop()
    window.appearance_buttons["system"].click()
    assert window._appearance_timer.isActive()
    assert ui_theme.is_dark() is True
    dark_system[0] = False
    window._follow_system()
    assert ui_theme.is_dark() is False
    window.appearance_buttons["light"].click()
    assert not window._appearance_timer.isActive()
    window.close()
