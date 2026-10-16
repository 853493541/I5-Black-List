"""Layout that held in the UI test: dialogs fit short screens, and long text is never cut where it matters.

A screen is measured by the room Windows leaves for windows: 1366×768 with its taskbar leaves 728 px,
1080p at 150% (1280×720) leaves 672. Every dialog fits the second, with its buttons in view.
"""

from math import ceil

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QLabel, QPushButton

from blacklist_detect.model import Combo, Entry, Scenes
from blacklist_detect.ui import MainWindow
from blacklist_detect.ui_dialogs import StreamGuideDialog
from blacklist_detect.ui_kit import ConfirmDialog, Modal, _height_for
from blacklist_detect.ui_theme import DIALOG_PAD
from blacklist_detect.ui_widgets import TagPill

LAPTOP = 728
SHORT = 672


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.store.add("示例坏人", tags=("炸房",), reason="开局就退")
    window.store.add("路过的捣蛋鬼", tags=("场外", "挂机"), reason="场外报点，还在频道里骂人，这是一段很长很长的原因")
    window.store.add_like("心动小鹿", nickname="小鹿")
    window.store.add_like("心动星星")
    window.store.set_combos([Combo(("心动小鹿", "心动星星"), Scenes(("angel",)))])
    yield window
    window.close()


def _card_height(dialog: Modal) -> int:
    """The card with its shadow, as tall as it will be on the screen."""
    card = dialog.card
    width = max(card.minimumWidth(), min(card.maximumWidth(), card.sizeHint().width()))
    margins = dialog.layout().contentsMargins()
    return _height_for(card, width) + margins.top() + margins.bottom()


def _dialogs(window, monkeypatch) -> dict[str, Modal]:
    """Every dialog the window opens, as it builds it, without showing any."""
    opened: dict[str, Modal] = {}
    name = {"now": ""}

    def keep(dialog, *_args):  # noqa: ANN001, ANN202
        opened[name["now"]] = dialog
        return QDialog.Rejected

    for kind in (Modal, ConfirmDialog, StreamGuideDialog):
        monkeypatch.setattr(kind, "exec", keep)
        monkeypatch.setattr(kind, "open", keep)
    from blacklist_detect.diagnostics import FlowTest
    from blacklist_detect.ui_dialogs import FlowReportDialog, PictureResultDialog
    from blacklist_detect.ui_sound_trim import SoundTrimDialog

    song = (np.sin(np.arange(20 * 44100) / 44100 * 2 * np.pi * 440) * 12000).astype(np.int16)
    runs = [{"capture": 0.08, "find": 0.04, "read": 0.06}] * 3
    openers = {
        "添加": window._add_by_dialog,
        "批量导入": window._add_many_by_dialog,
        "编辑": lambda: window._edit_entry(1),
        "清空黑名单": window._clear_list,
        "添加嘉宾": window.likes_page.add_one,
        "编辑嘉宾": lambda: window.likes_page.edit(0),
        "添加组合": window.likes_page.add_combo,
        "编辑组合": lambda: window.likes_page.edit_combo(0),
        "嘉宾场景": lambda: window.likes_page.edit_scenes(("like", 1)),
        "场景管理": window.likes_page.scenes_button.click,
        "选择片段": lambda: SoundTrimDialog(song, 44100, "心动音乐.mp3", lambda _start, _length: None, lambda: None, window).exec(),
        "显示说明": window._show_display_guide,
        "直播模式说明": window._show_stream_guide,
        "使用声明": window._show_disclaimer,
        "截图检查": lambda: PictureResultDialog("截图检查", error="这张图打不开", parent=window).open(),
        "环境测试": lambda: FlowReportDialog(FlowTest(size=(1920, 1080), runs=runs, right=12), lambda: None, window).open(),
    }
    for title, opener in openers.items():
        name["now"] = title
        opener()
    assert set(opened) == set(openers)
    return opened


def test_every_dialog_fits_a_short_screen_with_its_buttons(window, monkeypatch):
    for title, dialog in _dialogs(window, monkeypatch).items():
        dialog.fit_height(SHORT)
        assert _card_height(dialog) <= SHORT - 8, title


def test_the_scene_editor_and_the_guest_dialogs_fit_a_short_screen_without_scrolling(window, monkeypatch):
    """嘉宾场景, the tallest of them, shows 随机, every scene, the preview and 确定 at once on 1080p at 150%."""
    dialogs = _dialogs(window, monkeypatch)
    for title in ("嘉宾场景", "添加嘉宾", "编辑嘉宾", "添加组合", "编辑组合"):
        dialogs[title].fit_height(SHORT)
        assert dialogs[title].scroll is None and _card_height(dialogs[title]) <= SHORT - 8, title
    editor = dialogs["嘉宾场景"]
    used = next(button for button in editor.findChildren(QPushButton) if button.text() == "确定")
    assert used.isVisibleTo(editor) and editor.random_box.isVisibleTo(editor) and editor.preview.isVisibleTo(editor)
    assert editor.who == ("like", 1)


def test_scene_manager_with_three_songs_fits_a_short_screen_without_scrolling(window, monkeypatch):
    """场景管理 at its tallest: 默认 and three songs, 恢复默认 shown, 已静音 and a note under the hotkey, every
    row in view on 1080p at 150% with no scroll. Its scene list is as tall as the rest beside it."""
    from blacklist_detect.paths import custom_sound_dir

    folder = custom_sound_dir(window.store.root)
    folder.mkdir(parents=True, exist_ok=True)
    for number, name in enumerate(("一个名字很长很长很长很长很长很长的心动音乐.mp3", "小星星.wav", "心动音乐.mp3"), 1):
        (folder / f"fluffy-{number}.wav").write_bytes(b"")
        window.store.add_scene_song("fluffy", {"file": f"fluffy-{number}.wav", "name": name, "start": 0.0, "length": 5.0})
    window.mute_box.click()
    page = window.effects_page
    page.select("fluffy")
    page.say(f"检查已在用 {window.store.hotkey}，场景快捷键未设置", held=True)
    dialog = _dialogs(window, monkeypatch)["场景管理"]
    assert dialog is window.scenes_dialog
    assert [choice.isVisibleTo(page) for choice in page.sounds.choices] == [True] * 4 and page.reset_button.isVisibleTo(page)
    dialog.fit_height(SHORT)
    assert dialog.scroll is None and _card_height(dialog) <= SHORT - 8
    assert page.preview.width() == page.PREVIEW_W and page.note.isVisibleTo(page) and page.level_note.text() == "已静音"
    window.mute_box.click()


def test_more_scenes_make_the_preview_smaller_not_the_scene_editor_taller(window, monkeypatch):
    """With 16 scenes, six rows of three, the preview gives up the room the sixth row takes."""
    from blacklist_detect import love_scenes
    from blacklist_detect.ui_guest_scenes import GuestScenesDialog

    today = GuestScenesDialog(window.store, parent=window)
    fake = [(f"fake{number}", f"示例场景{number}") for number in range(16 - len(love_scenes.SCENES))]
    monkeypatch.setattr(love_scenes, "SCENES", [*love_scenes.SCENES, *fake])
    more = GuestScenesDialog(window.store, parent=window)
    assert len(more.buttons) == 16 and len(today.buttons) <= 15
    assert more.preview.width() < GuestScenesDialog.PREVIEW_W == today.preview.width()
    for dialog in (today, more):
        dialog.fit_height(SHORT)
        assert dialog.scroll is None and _card_height(dialog) <= SHORT - 8
    assert _card_height(more) <= _card_height(today) + (5 - ceil(len(today.buttons) / 3)) * 36
    for dialog in (today, more):
        dialog.done(QDialog.Rejected)


def _guests(count: int) -> list[Entry]:
    """嘉宾 with long names, 12 characters each."""
    return [Entry(f"心动小鹿的好朋友{index:04d}") for index in range(count)]


@pytest.mark.parametrize("count", [0, 2, 20, 60])
def test_the_combo_dialogs_fit_a_short_screen_however_many_guests(window, count):
    """添加组合 and 编辑组合 list every 嘉宾 to pick: past a few rows the list scrolls inside them, so
    neither grows, and 保存 stays in view even with 至少选两位嘉宾 under the list."""
    from blacklist_detect.ui_guests import ComboDialog

    likes = _guests(count)
    combo = Combo((*(like.name for like in likes[:2]), "已删掉的嘉宾"), Scenes(("angel",)))
    for dialog in (ComboDialog(likes, parent=window), ComboDialog(likes, combo, parent=window)):
        for button in dialog.people_buttons.values():
            button.setChecked(False)
        dialog._accept()
        assert dialog.result() != QDialog.Accepted and dialog.people_error.isVisibleTo(dialog)
        dialog.fit_height(SHORT)
        assert dialog.scroll is None and _card_height(dialog) <= SHORT - 8, count
        # The list's own width in the card: past 4½ rows of these names it stops growing and scrolls.
        people, width = dialog.people_scroll, dialog.card.minimumWidth() - 2 * DIALOG_PAD
        assert (_height_for(dialog.people, width) > people.maximumHeight()) == (count >= 20), count
        assert people.heightForWidth(width) == min(_height_for(dialog.people, width), people.maximumHeight())


def test_the_combo_dialog_opens_on_its_own_guests_however_far_down_the_list_they_are(window):
    """The 组合's 嘉宾 come first, the oldest and one taken off the list too, so none is scrolled out of sight."""
    from blacklist_detect.ui_guests import ComboDialog

    likes = _guests(60)
    combo = Combo((likes[0].name, likes[1].name, "已删掉的嘉宾"), Scenes(("angel",)))
    dialog = ComboDialog(likes, combo, parent=window)
    ticked = [button.isChecked() for button in dialog.people_buttons.values()]
    assert ticked == [True] * 3 + [False] * 58
    # Placed as in the dialog, beside its scroll bar, they sit within the rows it shows.
    people = dialog.people_scroll
    width = dialog.card.minimumWidth() - 2 * DIALOG_PAD - people.verticalScrollBar().sizeHint().width()
    dialog.people._arrange(width, place=True)
    for name in combo.names:
        assert dialog.people_buttons[name].geometry().bottom() < people.maximumHeight(), name
    dialog._accept()
    assert dialog.result() == QDialog.Accepted and set(dialog.combo.names) == set(combo.names)


def test_a_guest_far_down_the_combo_list_is_picked_as_any_other(window):
    from blacklist_detect.ui_guests import ComboDialog

    likes = _guests(60)
    dialog = ComboDialog(likes, parent=window)
    dialog.people_buttons[likes[0].name].click()
    dialog.people_buttons[likes[-1].name].click()
    dialog._accept()
    assert dialog.result() == QDialog.Accepted and set(dialog.combo.names) == {likes[0].name, likes[-1].name}


def test_a_long_hotkey_is_shown_whole(window):
    window.hotkey_edit.setText("Ctrl+Shift+Alt+F12")
    metrics = window.hotkey_edit.fontMetrics()
    assert window.hotkey_edit.width() >= metrics.horizontalAdvance("Ctrl+Shift+Alt+F12") + 16


def test_the_check_panel_rows_are_alike_and_each_info_mark_is_beside_its_choice(window):
    # 显示 is two joined choices, its ⓘ right after them; 方式 has 手动检查 beside its hotkey; 直播模式 has
    # its ⓘ right after its switch, and 测试效果 after that while it is on.
    window.show()
    window.check_panel.toggle()
    for _ in range(5):
        QApplication.processEvents()
    panel = window.check_panel
    assert list(window.auto_mode.buttons) == ["auto", "manual"]
    end = window.display_mode.mapTo(panel, QPoint(window.display_mode.width(), 0)).x()
    assert 0 <= window.display_guide.mapTo(panel, QPoint(0, 0)).x() - end <= 16
    manual = window.auto_mode.buttons["manual"]
    assert window.hotkey_edit.mapTo(panel, QPoint(0, 0)).x() - manual.mapTo(panel, QPoint(manual.width(), 0)).x() <= 16
    switch = window.stream_switch
    left = window.display_mode.mapTo(panel, QPoint(0, 0)).x()
    assert switch.mapTo(panel, QPoint(0, 0)).x() == left and window.auto_mode.mapTo(panel, QPoint(0, 0)).x() == left
    switch_end = switch.mapTo(panel, QPoint(switch.width(), 0)).x()
    assert 0 <= window.stream_guide.mapTo(panel, QPoint(0, 0)).x() - switch_end <= 16
    assert not window.stream_test.isVisible()
    # With 直播模式 on, 测试效果 comes on the same row, after the ⓘ, and the card, wider, stays under the pill.
    window._set_stream_mode(True)
    for _ in range(5):
        QApplication.processEvents()
    test = window.stream_test
    assert test.isVisible() and panel.isAncestorOf(test)
    assert abs(test.mapTo(panel, test.rect().center()).y() - switch.mapTo(panel, switch.rect().center()).y()) <= 2
    guide_end = window.stream_guide.mapTo(panel, QPoint(window.stream_guide.width(), 0)).x()
    assert 0 <= test.mapTo(panel, QPoint(0, 0)).x() - guide_end <= 16
    card = panel.card.geometry().translated(panel.pos())
    chip = window.status_chip
    pill = chip.geometry().translated(chip.parentWidget().mapTo(window.centralWidget(), QPoint(0, 0)))
    assert abs(card.right() - pill.right()) <= 1 and card.left() >= 0
    assert panel.card.rect().contains(QRect(test.mapTo(panel.card, QPoint(0, 0)), test.size()))
    window._set_stream_mode("")
    window.check_panel.close_panel()


def test_clickable_tags_take_clicks_over_a_full_target():
    assert TagPill("炸房", clickable=True).sizeHint().height() >= TagPill.TARGET
    assert TagPill("炸房").sizeHint().height() < TagPill.TARGET


def test_a_seat_keeps_the_name_read_and_cuts_the_list_name(window):
    window.store.add("一个名字特别特别长的玩家")
    window.store.add_scan([{"seat": 1, "name": "一个名字特别长的测试", "unclear": False}])
    window._reload_history()
    seat = window.history_table.cellWidget(0, 0)
    tile = seat.findChild(QFrame, "seat")
    name, listed = seat.findChild(QLabel, "rowName"), seat.findChild(QLabel, "rowListed")
    assert listed.text() == "黑名单：一个名字特别特别长的玩家"
    tile.layout().setGeometry(QRect(0, 0, 330, 32))
    assert name.width() == name.sizeHint().width()
    assert listed.width() < listed.sizeHint().width()
