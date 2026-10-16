"""The standard controls in ui_kit.py behave like their platform counterparts."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFontMetrics, QImage, QKeyEvent, QPixmap  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QWidget  # noqa: E402
from test_theme import contrast  # noqa: E402

from blacklist_detect import ui_icons  # noqa: E402
from blacklist_detect.ui_kit import (  # noqa: E402
    ChoiceBox,
    ConfirmDialog,
    EmptyState,
    IconButton,
    SegmentedControl,
    SettingsPane,
    SettingsSection,
    Switch,
    TabButton,
    Toast,
)
from blacklist_detect.ui_theme import THEME, _choice_rules, _palette, _window_style, chinese_family, choice_colors  # noqa: E402


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


def test_a_switch_with_text_toggles_from_its_words(qapp):
    plain = Switch(False)
    labelled = Switch(False, text="自动检查")
    assert labelled.accessibleName() == "自动检查"
    assert labelled.sizeHint().width() > plain.sizeHint().width()
    labelled.resize(labelled.sizeHint())
    assert labelled.hitButton(QPoint(4, labelled.height() // 2))
    labelled.click()
    assert labelled.isChecked()


def test_a_tab_button_grows_a_badge_for_its_count(qapp):
    tab = TabButton("黑名单")
    bare = tab.sizeHint().width()
    tab.set_count(3)
    assert tab.count() == 3
    assert tab.sizeHint().width() > bare
    assert tab.accessibleName() == "黑名单"
    tab.set_count(250)
    assert tab._badge_text() == "99+"
    tab.set_count(0)
    assert tab.sizeHint().width() == bare
    tab.setChecked(True)
    tab.resize(tab.sizeHint())
    assert not tab.grab().isNull()


def test_focus_rings_show_for_the_keyboard_only(qapp):
    host = QWidget()
    tab = TabButton("记录", host)
    switch = Switch(True, host)
    host.show()
    for widget in (tab, switch):
        widget.setFocus(Qt.FocusReason.MouseFocusReason)
        _settle(qapp)
        assert widget.hasFocus() or not host.isActiveWindow()
        assert widget.show_ring() is False
        widget.clearFocus()
        _settle(qapp)
        widget.setFocus(Qt.FocusReason.TabFocusReason)
        _settle(qapp)
        assert widget.show_ring() is widget.hasFocus()
    host.close()


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
    assert control.current() == "system"
    # Set from code, then clicked back: the click still counts as a change.
    control.buttons["light"].setChecked(True)
    assert control.current() == "light"
    control.buttons["system"].click()
    assert picked == ["dark", "system"]


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
    toast.show_message("已删除「甲」", "撤销", lambda: undone.append(True), ms=60_000)
    _settle(qapp)
    assert toast.isVisible()
    assert toast.text.text() == "已删除「甲」"
    assert toast.action.isVisible()
    assert toast.y() + toast.height() <= host.height()
    toast.action.click()
    assert undone == [True]
    assert not toast.isVisible()
    # Still fading out: 撤销 must still work, however slow the machine is.
    toast.show_message("已删除「乙」", "撤销", lambda: undone.append(True), ms=60_000)
    toast.dismiss()
    toast.action.click()
    assert undone == [True, True]
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
    section = SettingsSection(80, "常规")
    section.add_row("开机启动", Switch(True), hint="开机后在右下角托盘里运行")
    section.add_row("快捷键", QPushButton("Alt+1"))
    labels = [label.text() for label in section.findChildren(QLabel)]
    assert labels[0] == "常规"
    assert "开机启动" in labels and "快捷键" in labels and "开机后在右下角托盘里运行" in labels
    assert len([w for w in section.findChildren(QWidget) if w.objectName() == "sectionLine"]) == 1


def test_the_lines_between_settings_are_one_device_pixel_at_every_scale(qapp):
    """A styled QFrame came out 1 or 2 px by where it fell at 125 and 150 %: the lines are hairlines now."""
    from blacklist_detect.ui_kit import _Hairline

    pane = SettingsPane("常规")
    for name in ("开机启动", "快捷键", "全局声音"):
        pane.add_row(name, None, QPushButton("x"))
    section = SettingsSection(80)
    section.add_row("显示", QPushButton("基础模式"))
    section.add_row("方式", QPushButton("自动"))
    lines = [w for w in pane.findChildren(QWidget) if w.objectName() == "settingsLine"]
    lines += [w for w in section.findChildren(QWidget) if w.objectName() == "sectionLine"]
    assert len(lines) == 3 and all(isinstance(line, _Hairline) and line.height() == 1 for line in lines)
    line = lines[0]
    line.resize(200, 1)
    border = QColor(THEME["border"]).rgb()
    for ratio in (1.0, 1.25, 1.5, 2.0):
        picture = QImage(round(200 * ratio), 4, QImage.Format_RGB32)
        picture.setDevicePixelRatio(ratio)
        picture.fill(QColor("#ffffff"))
        line.render(picture)
        rows = [y for y in range(picture.height()) if picture.pixel(100, y) == border]
        assert rows == [0], ratio


def test_a_settings_section_without_a_title_starts_with_its_rows(qapp):
    from blacklist_detect.ui_kit import ElidedLabel

    section = SettingsSection(80)
    info = QPushButton("i")
    words = ElidedLabel("一句很长很长很长很长很长很长的话")
    section.add_row("直播模式", QPushButton("开启"), words, info=info)
    assert section.findChild(QLabel, "sectionTitle") is None
    assert [label.text() for label in section.findChildren(QLabel)][0] == "直播模式"
    # The mark sits in the names' column, right after the name; the words, cut short, say all of it on hover.
    name = next(label for label in section.findChildren(QLabel) if label.text() == "直播模式")
    assert name.parentWidget() is info.parentWidget() and name.parentWidget().width() == 80
    assert words.toolTip() == words.text() and words.minimumSizeHint().width() == 0
    words.setText("短")
    assert words.toolTip() == "短"


@pytest.mark.parametrize("dark", [False, True])
def test_toast_colors_are_readable(dark):
    for name in ("蓝色", "棕色", "紫色", "绿色", "红色"):
        t = _palette(name, dark)
        assert contrast(t["toast_text"], t["toast_bg"]) >= 4.5
        assert contrast(t["toast_action"], t["toast_bg"]) >= 3.0, name


def test_theme_has_kit_roles():
    for key in ("toast_bg", "toast_text", "toast_action"):
        assert key in THEME


def test_a_switch_set_quietly_is_drawn_where_it_is(qapp):
    from blacklist_detect.ui_kit import Switch

    switch = Switch(False)
    switch.blockSignals(True)
    switch.setChecked(True)
    switch.blockSignals(False)
    assert switch._pos == 1.0
    switch.blockSignals(True)
    switch.setChecked(False)
    switch.blockSignals(False)
    assert switch._pos == 0.0


def _choice_host(qapp):  # noqa: ANN001, ANN202
    """A ChoiceBox near the right of a styled window, the way 设置 holds one."""
    host = QWidget()
    host.setStyleSheet(_window_style(chinese_family()))
    host.resize(360, 200)
    host.move(40, 40)
    box = ChoiceBox([("light", "浅色"), ("dark", "深色"), ("system", "跟随系统")], "light", host)
    host.show()
    _settle(qapp)
    box.resize(box.sizeHint())
    box.move(host.width() - box.width() - 20, 20)
    _settle(qapp)
    return host, box


def _drawn(box: ChoiceBox) -> QImage:
    """The box drawn alone on a page of one color, so whatever it paints of its own shows against it."""
    page = QPixmap(box.size())
    page.fill(QColor("#123456"))
    box.render(page)
    return page.toImage()


def test_a_choice_box_is_only_its_words_until_hovered(qapp):
    host, box = _choice_host(qapp)
    image = _drawn(box)
    middle = box.height() // 2
    # No border and no fill: its edges, and the room left of its right-aligned words, are the page.
    for x, y in ((0, 0), (box.width() - 1, 0), (0, box.height() - 1), (1, middle), (box.width() - 2, middle), (box.width() // 2, 1)):
        assert image.pixelColor(x, y) == QColor("#123456"), (x, y)
    # On hover a soft fill comes under the words, the fill the open list's rows take.
    box.setAttribute(Qt.WA_UnderMouse, True)
    image = _drawn(box)
    assert image.pixelColor(3, middle) == QColor(choice_colors()["hover"])
    assert image.pixelColor(box.width() - 4, middle) == QColor(choice_colors()["hover"])
    box.setEnabled(False)
    assert not box.is_lit()
    host.close()


def test_a_choice_box_is_as_wide_as_its_words(qapp):
    host, box = _choice_host(qapp)
    assert not hasattr(ChoiceBox, "WIDTH")
    short = box.sizeHint().width()
    words = QFontMetrics(box.font()).horizontalAdvance("跟随系统") - QFontMetrics(box.font()).horizontalAdvance("浅色")
    box.set_current("system")
    assert box.sizeHint().width() == short + words
    host.close()


def test_a_click_opens_the_list_right_aligned_under_the_words(qapp):
    host, box = _choice_host(qapp)
    view = box.view()
    assert not view.isVisible()
    QTest.mouseClick(box, Qt.LeftButton)
    _settle(qapp)
    assert view.isVisible() and box.is_lit()
    panel = view.window()
    side = box._SHADOW
    corner = box.mapToGlobal(QPoint(box.width(), box.height()))
    geometry = panel.geometry()
    assert geometry.right() + 1 - side == corner.x()
    assert geometry.top() + side == corner.y() + box._DROP
    # As wide as its longest choice, the default first.
    assert geometry.width() - 2 * side == box.list_width() > box.width()
    assert [box.itemText(row) for row in range(box.count())] == ["浅色", "深色", "跟随系统"]
    # A panel with no hard line round it, its chosen row in the hover's fill.
    image = panel.grab().toImage()
    colors = choice_colors()
    chosen = view.mapTo(panel, view.visualRect(box.model().index(0, 0)).center())
    assert image.pixelColor(view.x() + 2, view.y() + view.height() // 2) == QColor(colors["panel"])
    assert image.pixelColor(view.x() + 6, chosen.y()) == QColor(colors["hover"])
    rules = _choice_rules("x")
    assert f"background: {colors['hover']};" in rules.split("::item:selected")[1]
    assert "border: 1px" not in rules
    box.hidePopup()
    _settle(qapp)
    assert not view.isVisible() and not box.is_lit()
    host.close()


def test_the_keyboard_still_works_a_choice_box(qapp):
    host, box = _choice_host(qapp)
    picked: list[str] = []
    box.changed.connect(picked.append)
    # The window gives it focus as it opens, with no ring; Tab onto it shows one.
    assert not box.show_ring()
    box.clearFocus()
    _settle(qapp)
    box.setFocus(Qt.FocusReason.TabFocusReason)
    _settle(qapp)
    assert box.show_ring() is box.hasFocus()
    for key in (Qt.Key_Down, Qt.Key_Down, Qt.Key_Up):
        QApplication.sendEvent(box, QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))
    assert picked == ["dark", "system", "dark"] and box.current() == "dark"
    for key in (Qt.Key_Space, Qt.Key_Return):
        QApplication.sendEvent(box, QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))
        _settle(qapp)
        assert box.view().isVisible(), key
        box.hidePopup()
        _settle(qapp)
        # Back from its list, the ring the keyboard put there stays.
        assert box.show_ring() is box.hasFocus()
    host.close()
