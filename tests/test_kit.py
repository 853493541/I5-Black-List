"""The standard controls in ui_kit.py behave like their platform counterparts."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QWidget  # noqa: E402
from test_theme import contrast  # noqa: E402

from blacklist_detect import ui_icons  # noqa: E402
from blacklist_detect.ui_kit import (  # noqa: E402
    ConfirmDialog,
    EmptyState,
    IconButton,
    SegmentedControl,
    SettingsSection,
    Switch,
    Toast,
)
from blacklist_detect.ui_theme import THEME, _palette  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settle(app, rounds: int = 30) -> None:
    for _ in range(rounds):
        app.processEvents()


def test_every_icon_draws(qapp):
    for name in ui_icons.DRAWINGS:
        image = ui_icons.pixmap(name, 20).toImage()
        assert not image.isNull()
        assert any(image.pixelColor(x, y).alpha() for x in range(image.width()) for y in range(image.height())), name


def test_the_switch_toggles_by_click_and_by_space(qapp):
    switch = Switch(False)
    seen: list[bool] = []
    switch.toggled.connect(seen.append)
    switch.click()
    assert switch.isChecked() is True
    switch.setFocus()
    qapp.sendEvent(switch, QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Space, Qt.NoModifier))
    qapp.sendEvent(switch, QKeyEvent(QKeyEvent.Type.KeyRelease, Qt.Key_Space, Qt.NoModifier))
    assert switch.isChecked() is False
    assert seen == [True, False]
    assert switch.focusPolicy() == Qt.StrongFocus
    assert switch.grab().width() > 0


def test_a_segmented_control_keeps_one_choice(qapp):
    control = SegmentedControl([("light", "浅色"), ("dark", "深色"), ("system", "跟随系统")], "light")
    picked: list[str] = []
    control.changed.connect(picked.append)
    control.buttons["dark"].click()
    control.buttons["dark"].click()
    assert picked == ["dark"]
    assert control.current() == "dark"
    assert [b.isChecked() for b in control.buttons.values()] == [False, True, False]
    assert control.buttons["light"].property("place") == "first"
    assert control.buttons["system"].property("place") == "last"
    control.set_current("system")
    assert control.buttons["system"].isChecked()


def test_an_icon_button_is_named_for_screen_readers(qapp):
    button = IconButton("edit", "修改")
    assert button.toolTip() == "修改"
    assert button.accessibleName() == "修改"
    assert not button.icon().isNull()


def test_a_toast_shows_offers_an_action_and_goes_away(qapp):
    host = QWidget()
    host.resize(600, 400)
    host.show()
    toast = Toast(host)
    undone: list[bool] = []
    toast.show_message("已删除「甲」", "撤销", lambda: undone.append(True), ms=50)
    _settle(qapp)
    assert toast.isVisible()
    assert toast.text.text() == "已删除「甲」"
    assert toast.action.isVisible()
    assert toast.y() + toast.height() <= host.height()
    toast.action.click()
    assert undone == [True]
    assert not toast.isVisible()
    toast.show_message("已复制", ms=30)
    assert toast.action.isHidden()
    import time

    deadline = time.monotonic() + 2
    while toast.isVisible() and time.monotonic() < deadline:
        qapp.processEvents()
    assert not toast.isVisible()
    host.close()


def test_a_confirm_dialog_defaults_to_the_safe_choice(qapp):
    dialog = ConfirmDialog(None, "清空黑名单？", "将删除全部名字。", "清空", danger=True)
    assert dialog.cancel_button.isDefault()
    assert not dialog.confirm_button.isDefault()
    assert dialog.confirm_button.objectName() == "danger"
    dialog.confirm_button.click()
    assert dialog.result() == QDialog.Accepted
    other = ConfirmDialog(None, "提示", "正文", "好")
    assert other.confirm_button.objectName() == "primary"
    other.reject()


def test_an_empty_state_has_a_heading_hint_and_action(qapp):
    empty = EmptyState("records", "还没有记录", "进入大厅后会显示在这里。")
    action = empty.add_action(QPushButton("测试一下"))
    assert empty.title.text() == "还没有记录"
    assert empty.hint.isVisibleTo(empty)
    assert action.parentWidget() is empty
    empty.set_text("没有找到", "")
    assert not empty.hint.isVisibleTo(empty)
    assert not empty.icon.pixmap().isNull()


def test_a_settings_section_lays_out_rows(qapp):
    section = SettingsSection("检查", 80)
    section.add_row("提示音", Switch(True), hint="发现黑名单时响一声")
    section.add_row("快捷键", QPushButton("Alt+1"))
    labels = [label.text() for label in section.findChildren(QLabel)]
    assert labels[0] == "检查"
    assert "提示音" in labels and "快捷键" in labels and "发现黑名单时响一声" in labels
    assert len([w for w in section.findChildren(QWidget) if w.objectName() == "sectionLine"]) == 1


@pytest.mark.parametrize("dark", [False, True])
def test_toast_colors_are_readable(dark):
    for name in ("蓝色", "棕色", "紫色", "绿色", "红色"):
        t = _palette(name, dark)
        assert contrast(t["toast_text"], t["toast_bg"]) >= 4.5
        assert contrast(t["toast_action"], t["toast_bg"]) >= 3.0, name


def test_theme_has_kit_roles():
    for key in ("toast_bg", "toast_text", "toast_action"):
        assert key in THEME
