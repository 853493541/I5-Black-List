"""设置 the way desktop apps lay it out: a catalog of sections on the left, the chosen one on the right, each
setting a row of its own with its name and a gray line on the left and its control on the right."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QColor, QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

from blacklist_detect import autostart  # noqa: E402
from blacklist_detect.ui import MainWindow  # noqa: E402
from blacklist_detect.ui_kit import SettingsCatalog, SettingsPane, SettingsSection, Switch  # noqa: E402
from blacklist_detect.ui_theme import THEME  # noqa: E402
from blacklist_detect.updater import Release  # noqa: E402

ROWS = {
    "general": [
        ("开机启动", "Windows 启动时自动打开"),
        ("关闭窗口时", "点 × 时最小化到托盘或直接退出"),
        ("声音", "每个场景的音量在场景管理里调"),
    ],
    "look": [("模式", "浅色、深色或跟着 Windows")],
    "help": [("环境测试", "检查这台电脑能不能正常识别"), ("导出日志", "出问题时发给朋友看")],
    "about": [
        ("检查更新", "当前版本"),
        ("使用声明", "免费自制工具，和官方无关"),
        ("清空数据", "删掉黑名单、嘉宾、记录和设置，回到刚安装时"),
    ],
}


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201
    return QApplication.instance() or QApplication([])


def _settle(times: int = 5) -> None:
    for _ in range(times):
        QApplication.processEvents()


def _key(widget: QWidget, key: Qt.Key) -> None:
    QApplication.sendEvent(widget, QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))


@pytest.fixture
def opened(qapp, tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    """The window on 设置, its buttons' answers caught: what each was asked to do, by name."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    asked: list[str] = []
    monkeypatch.setattr(MainWindow, "_export_logs", lambda _self: asked.append("导出日志"))
    monkeypatch.setattr(MainWindow, "_show_disclaimer", lambda _self: asked.append("使用声明"))
    window = MainWindow()
    window._watch_timer.stop()
    window.asked = asked
    window.resize(900, 560)
    window.tabs.setCurrentIndex(window.settings_tab)
    window.show()
    _settle()
    yield window
    window.close()


def _shown(window) -> list[str]:  # noqa: ANN001
    return [key for key, pane in window.settings_sections.items() if pane.isVisible()]


def test_the_catalog_lists_the_sections_and_shows_the_chosen_one(opened):
    catalog = opened.settings_catalog
    assert catalog.keys() == ["general", "look", "help", "about"]
    assert [catalog.item(row).text() for row in range(catalog.count())] == ["常规", "外观", "帮助", "关于"]
    assert [catalog.item(row).data(Qt.UserRole + 1) for row in range(catalog.count())] == ["settings", "palette", "help", "info"]
    assert catalog.width() == SettingsCatalog.WIDTH and catalog.currentRow() == 0
    assert _shown(opened) == ["general"]
    # A click on 关于 shows it alone, its heading at the top.
    rect = catalog.visualItemRect(catalog.item(3))
    from PySide6.QtTest import QTest

    QTest.mouseClick(catalog.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, rect.center())
    _settle()
    assert catalog.current_key() == "about" and _shown(opened) == ["about"]
    assert opened.settings_sections["about"].heading.text() == "关于"
    # ↑ and ↓ move through the sections as a click does.
    catalog.setFocus()
    _key(catalog, Qt.Key_Up)
    assert _shown(opened) == ["help"]
    _key(catalog, Qt.Key_Up)
    _key(catalog, Qt.Key_Up)
    assert _shown(opened) == ["general"]
    _key(catalog, Qt.Key_Down)
    assert _shown(opened) == ["look"]


def test_enter_goes_on_into_the_chosen_section(opened):
    catalog = opened.settings_catalog
    catalog.choose("help")
    catalog.setFocus()
    _key(catalog, Qt.Key_Return)
    assert opened.test_button.hasFocus()
    catalog.choose("look")
    catalog.setFocus()
    _key(catalog, Qt.Key_Enter)
    assert opened.appearance_buttons["light"].hasFocus(), "a segmented control takes focus on its first button"


def test_each_section_has_its_rows_in_order_with_a_line_on_what_each_does(opened):
    for key, rows in ROWS.items():
        pane = opened.settings_sections[key]
        assert len(pane.rows) == len(rows)
        assert [(row.name.text(), row.description_text()[: len(text)]) for row, (_, text) in zip(pane.rows, rows, strict=True)] == rows
        # A thin line between rows, none above the first; no card around them.
        assert len(pane.findChildren(QWidget, "settingsLine")) == len(rows) - 1
        assert pane.findChildren(SettingsSection) == []
        for row in pane.rows:
            assert len(row.description_text()) <= 22, row.description_text()
    controls = {row.name.text(): row.controls for pane in opened.settings_sections.values() for row in pane.rows}
    assert controls == {
        "开机启动": (opened.autostart_switch,),
        "关闭窗口时": (opened.close_mode,),
        "声音": (opened.mute_box,),
        "模式": (opened.appearance_control,),
        "环境测试": (opened.test_button,),
        "导出日志": (opened.export_button,),
        "检查更新": (opened.update_note, opened.update_button),
        "使用声明": (opened.disclaimer_button,),
        "清空数据": (opened.reset_button,),
    }
    # Every choice lists its default first.
    assert list(opened.close_mode.buttons) == ["tray", "quit"]
    assert list(opened.appearance_buttons) == ["light", "dark", "system"]


def test_names_and_lines_on_the_left_and_controls_on_the_right(opened):
    """开机启动 and 关闭窗口时 are two rows (they shared one), and every control ends at the same right edge."""
    catalog = opened.settings_catalog
    places = set()
    for key, pane in opened.settings_sections.items():
        opened._show_settings_section(key)
        _settle()
        # The catalog keeps its place beside every section.
        places.add((catalog.mapTo(opened, catalog.rect().topLeft()), catalog.size()))
        assert len(places) == 1
        assert opened.settings_scroll.horizontalScrollBar().maximum() == 0, f"{key} scrolls sideways"
        assert opened.settings_scroll.verticalScrollBar().maximum() == 0, f"{key} scrolls at the smallest window"
        rights = set()
        for row in pane.rows:
            name = row.name.mapTo(opened, row.name.rect().topLeft())
            description = row.description.mapTo(opened, row.description.rect().topLeft())
            assert description.x() == name.x() and description.y() > name.y()
            last = row.controls[-1]
            rights.add(last.mapTo(opened, last.rect().topRight()).x())
            assert last.mapTo(opened, last.rect().topLeft()).x() > name.x() + 150
        assert len(rights) == 1, f"{key}'s controls do not line up on the right"
    opened._show_settings_section("general")
    _settle()
    middle = lambda widget: widget.mapTo(opened, widget.rect().center()).y()  # noqa: E731
    assert middle(opened.close_mode) - middle(opened.autostart_switch) > 30, "关闭窗口时 has its own row"


def test_every_control_still_does_what_it_did(opened, monkeypatch, tmp_path):
    # 开机启动, in the registry the tests keep in memory, as the installed app with its launcher.
    exe = tmp_path / "模仿者小工具.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(autostart, "launcher", lambda: exe)
    opened.autostart_switch.setEnabled(autostart.available())
    assert opened.autostart_switch.isChecked() is False
    opened._show_settings_section("general")
    opened.autostart_switch.click()
    assert autostart.is_enabled() and opened.autostart_switch.isChecked()
    opened.autostart_switch.click()
    assert not autostart.is_enabled()
    # 关闭窗口时.
    assert opened.store.close_to_tray is True
    opened.close_mode.buttons["quit"].click()
    assert opened.store.close_to_tray is False
    opened.close_mode.buttons["tray"].click()
    assert opened.store.close_to_tray is True
    # 静音, a checkbox.
    opened.mute_box.click()
    assert opened.store.sound_muted is True and opened.music.muted is True
    opened.mute_box.click()
    assert opened.store.sound_muted is False
    # 模式.
    opened._show_settings_section("look")
    opened.appearance_buttons["dark"].click()
    assert opened.store.appearance == "dark"
    opened.appearance_buttons["light"].click()
    assert opened.store.appearance == "light"
    # 开始 and 导出日志.
    started: list[bool] = []
    monkeypatch.setattr(opened, "start_environment_check", lambda force=False: started.append(force))
    opened._show_settings_section("help")
    opened.test_button.click()
    assert started == [True]
    opened.export_button.click()
    # 检查更新, 使用声明 and 清空数据, which asks first.
    opened._show_settings_section("about")
    checked: list[int] = []
    monkeypatch.setattr(opened.updates, "check", lambda: checked.append(1) or False)
    opened.update_button.click()
    assert checked or opened.update_note.text(), "检查更新 checked, or said why it cannot"
    opened.disclaimer_button.click()
    assert opened.asked == ["导出日志", "使用声明"]
    asked: list[tuple] = []
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda *args: asked.append(args) or False)
    opened.store.add("示例坏人")
    opened.reset_button.click()
    assert len(asked) == 1 and [entry.name for entry in opened.store.entries] == ["示例坏人"]


def test_a_waiting_version_shows_in_about(opened):
    opened._offer_update(Release(version="v9.0.0", url="", sha256="", size=0, base="v0.1.0", notes=("更快",)))
    opened._announce_soon = False
    opened.update_panel.close_panel()
    opened._show_settings_section("about")
    _settle()
    assert opened.tabs.currentIndex() == opened.settings_tab and _shown(opened) == ["about"]
    assert opened.update_button.isVisible() and opened.update_button.text() == "有更新"
    assert opened.update_button.objectName() == "primary"
    opened._offered = None


@pytest.mark.parametrize("appearance", ["light", "dark"])
def test_rows_read_in_both_themes(opened, appearance):
    opened._set_appearance(appearance)
    _settle()
    row = opened.settings_sections["general"].rows[0]
    assert row.name.palette().color(row.name.foregroundRole()) == QColor(THEME["text"])
    assert row.description.palette().color(row.description.foregroundRole()) == QColor(THEME["muted"])
    opened._set_appearance("light")


def test_the_check_card_keeps_its_look(opened):
    """The 检查 card under the pill is still a titled card, its names in a fixed column, controls after them."""
    card = opened.check_panel.findChild(SettingsSection)
    assert card.objectName() == "section" and card.findChild(QLabel, "sectionTitle").text() == "检查"
    assert not opened.tabs.widget(opened.settings_tab).isAncestorOf(card)
    names = [label for label in card.findChildren(QLabel, "rowLabel") if label.text() in ("显示", "方式")]
    assert len(names) == 2 and names[0].width() == names[1].width()
    margins = card.layout().contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (20, 14, 20, 6)


def test_a_pane_draws_lines_between_rows_only(qapp):
    pane = SettingsPane("常规")
    pane.add_row("开机启动", "Windows 启动时自动打开", Switch(False))
    pane.add_row("导出日志", "出问题时发给朋友看", QPushButton("导出"))
    assert pane.heading.text() == "常规" and len(pane.findChildren(QWidget, "settingsLine")) == 1
    assert [row.description_text() for row in pane.rows] == ["Windows 启动时自动打开", "出问题时发给朋友看"]
    assert pane.rows[0].description.toolTip() == "Windows 启动时自动打开", "a line cut short is whole on hover"
