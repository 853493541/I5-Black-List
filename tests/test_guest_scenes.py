"""嘉宾场景: who gets which 场景, 我, the 组合 and the 嘉宾 in one dialog, saved by 确定 alone."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from blacklist_detect.model import ANY_SCENE, Combo, Scenes  # noqa: E402
from blacklist_detect.storage import Store  # noqa: E402

OFF = Scenes()


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201
    return QApplication.instance() or QApplication([])


@pytest.fixture
def store(qapp, tmp_path):  # noqa: ANN001, ANN201
    """心动小鹿 on two scenes, 心动星星 on 随机, 晚风吹过 on 不放, their 组合 on 金色传说, 我 on 玫瑰花边."""
    store = Store(tmp_path)
    store.player_name = "测试主播"
    store.add_like("心动小鹿", scenes=Scenes(("fluffy", "stars")))
    store.add_like("心动星星")
    store.add_like("晚风吹过", scenes=OFF)
    store.set_combos([Combo(("心动小鹿", "心动星星"), Scenes(("angel",)))])
    store.set_me(Scenes(("lace",)))
    return store


def _dialog(store, who=("me", 0)):  # noqa: ANN001, ANN202
    from blacklist_detect.ui_guest_scenes import GuestScenesDialog

    return GuestScenesDialog(store, who)


def _rows(dialog) -> list:  # noqa: ANN001
    from blacklist_detect.ui_guest_scenes import SAID_ROLE, WHO_ROLE

    people = dialog.people
    return [(people.item(row).data(WHO_ROLE), people.item(row).data(SAID_ROLE)) for row in range(people.count())]


def _tick(dialog, *keys: str) -> None:  # noqa: ANN001
    """A click on each scene's box, as the player ticks or unticks it."""
    for key in keys:
        button = dialog.buttons[key]
        QTest.mouseClick(button, Qt.LeftButton, Qt.NoModifier, QPoint(button.width() - 24, button.height() // 2))


def _boxes_on(dialog) -> bool:  # noqa: ANN001
    """Whether the grid's boxes can be ticked: all of them, or (on 随机) none."""
    on = {button.box_enabled for button in dialog.buttons.values()}
    assert len(on) == 1 and dialog.scenes.isEnabled()
    return on.pop()


def test_everyone_is_listed_in_the_list_s_order_and_it_opens_on_the_one_asked(store):
    dialog = _dialog(store, ("like", 0))
    assert dialog.windowTitle() == "嘉宾场景"
    # 我, the 组合, then the 嘉宾 with the last saved on top, each with its 场景 in a word or two.
    assert _rows(dialog) == [
        (("me", 0), "玫瑰花边"),
        (("combo", 0), "金色传说"),
        (("like", 2), "不放"),
        (("like", 1), "随机"),
        (("like", 0), "2个场景"),
    ]
    assert dialog.who == ("like", 0) and dialog.people.currentRow() == 4
    assert dialog.scenes.chosen() == ("stars", "fluffy") and not dialog.random_box.isChecked()
    # Its first ticked plays.
    assert dialog.key == "stars" and dialog.preview.scene == "stars" and not dialog.has_changes()
    for who, row, ticked in ((("combo", 0), 1, ("angel",)), (("me", 0), 0, ("lace",))):
        other = _dialog(store, who)
        assert other.who == who and other.people.currentRow() == row and other.scenes.chosen() == ticked
        other.done(QDialog.Rejected)
    # One gone since (a 嘉宾 deleted from another window) opens on 我.
    assert _dialog(store, ("like", 9)).who == ("me", 0)
    dialog.people.grab()
    dialog.done(QDialog.Rejected)


def test_ticks_random_and_no_scene_are_saved_by_ok_alone(store, tmp_path):
    dialog = _dialog(store, ("like", 0))
    _tick(dialog, "fluffy", "ice")
    assert dialog.value(("like", 0)) == Scenes(("ice", "stars")) and dialog.has_changes()
    # Nothing saved yet; the list says the edit already.
    assert store.likes[0].scenes == Scenes(("fluffy", "stars")) and _rows(dialog)[4][1] == "2个场景"
    dialog.select(("like", 1))
    assert dialog.random_box.isChecked() and not _boxes_on(dialog) and dialog.scenes.chosen() == ()
    dialog.random_box.click()
    assert dialog.value(("like", 1)) == OFF and _rows(dialog)[3][1] == "不放" and not dialog.hint.isHidden()
    dialog.select(("like", 2))
    _tick(dialog, "claw")
    dialog.select(("combo", 0))
    dialog.random_box.click()
    dialog.ok_button.click()
    assert dialog.result() == QDialog.Accepted
    saved = Store(tmp_path)
    for read in (store, saved):
        assert [like.scenes for like in read.likes] == [Scenes(("ice", "stars")), OFF, Scenes(("claw",))]
        assert read.combos == [Combo(("心动小鹿", "心动星星"), Scenes(("angel",), random=True))]
        assert read.me == Scenes(("lace",))
    assert [like.name for like in saved.likes] == ["心动小鹿", "心动星星", "晚风吹过"]


def test_cancel_close_and_esc_keep_nothing(store):
    from PySide6.QtGui import QKeyEvent

    for close in ("cancel", "x", "esc"):
        dialog = _dialog(store, ("like", 0))
        _tick(dialog, "ice")
        dialog.select(("me", 0))
        dialog.random_box.click()
        assert dialog.has_changes()
        if close == "cancel":
            next(button for button in dialog.findChildren(type(dialog.ok_button)) if button.text() == "取消").click()
        elif close == "x":
            dialog.close_button.click()
        else:
            QApplication.sendEvent(dialog, QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        assert dialog.result() == QDialog.Rejected, close
        assert store.likes[0].scenes == Scenes(("fluffy", "stars")) and store.me == Scenes(("lace",)), close


def test_another_one_picked_keeps_the_first_one_s_edit(store):
    dialog = _dialog(store, ("like", 0))
    _tick(dialog, "fluffy")
    dialog.select(("like", 1))
    dialog.select(("like", 0))
    assert dialog.scenes.chosen() == ("stars",) and dialog.value(("like", 0)) == Scenes(("stars",))
    # Back as it was saved, it is no change at all.
    _tick(dialog, "fluffy")
    assert not dialog.has_changes() and dialog.edits == {}
    # A click on a row in the list picks it.
    rect = dialog.people.visualItemRect(dialog.people.item(1))
    QTest.mouseClick(dialog.people.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center())
    assert dialog.who == ("combo", 0) and dialog.scenes.chosen() == ("angel",)
    dialog.done(QDialog.Rejected)


def test_the_me_row_saves_the_player_s_own_scenes(store, monkeypatch):
    from blacklist_detect.ui_guest_scenes import GuestScenesDialog
    from blacklist_detect.ui_likes import LikesPage

    dialog = _dialog(store)
    assert dialog.who == ("me", 0) and dialog.scenes.chosen() == ("lace",)
    _tick(dialog, "lace", "ice")
    dialog.ok_button.click()
    assert store.me == Scenes(("ice",)) and store.likes[0].scenes == Scenes(("fluffy", "stars"))
    # The 嘉宾 page's edit_me opens it on 我.
    seen = []
    monkeypatch.setattr(GuestScenesDialog, "exec", lambda dialog: seen.append(dialog.who) or QDialog.Rejected)
    page = LikesPage(store, lambda *_args, **_kwargs: None)
    page.edit_me()
    assert seen == [("me", 0)]


def test_the_scenes_sit_in_three_columns_and_a_box_ticks_without_moving_the_highlight(store):
    from blacklist_detect import love_scenes

    dialog = _dialog(store, ("like", 0))
    dialog.show()
    QApplication.processEvents()
    places = [dialog.buttons[key].geometry().topLeft() for key in love_scenes.KEYS]
    assert places[0].y() == places[1].y() == places[2].y() < places[3].y() and places[3].x() == places[0].x()
    assert places[0].x() < places[1].x() < places[2].x()
    assert len({dialog.buttons[key].width() for key in love_scenes.KEYS}) == 1
    # 场景管理's list keeps one column.
    from blacklist_detect.ui_love_pick import SceneList

    single = SceneList("ice")
    single.show()
    QApplication.processEvents()
    assert len({button.geometry().x() for button in single.buttons.values()}) == 1
    single.close()
    # A click on a box ticks it and the highlight stays; one on the name highlights it and plays it.
    _tick(dialog, "ice")
    assert dialog.scenes.chosen() == ("ice", "stars", "fluffy") and dialog.key == "stars"
    ice = dialog.buttons["ice"]
    QTest.mouseClick(ice, Qt.LeftButton, Qt.NoModifier, QPoint(30, ice.height() // 2))
    assert dialog.key == "ice" and dialog.preview.scene == "ice" and dialog.scenes.chosen() == ("ice", "stars", "fluffy")
    # Space ticks or unticks.
    QTest.keyClick(dialog.buttons["stars"], Qt.Key_Space)
    assert dialog.value(("like", 0)) == Scenes(("ice", "fluffy"))
    dialog.done(QDialog.Rejected)


def test_random_greys_the_boxes_and_keeps_its_ticks(store):
    dialog = _dialog(store, ("like", 0))
    dialog.random_box.click()
    assert not _boxes_on(dialog) and dialog.hint.isHidden()
    assert dialog.scenes.chosen() == ("stars", "fluffy") and dialog.value(("like", 0)) == Scenes(("stars", "fluffy"), random=True)
    assert _rows(dialog)[4][1] == "随机"
    dialog.buttons["ice"].grab()
    dialog.random_box.click()
    assert _boxes_on(dialog) and not dialog.hint.isHidden() and not dialog.has_changes()
    # Saved 随机 with ticks opens greyed, the ticks shown.
    store.update_like(0, "心动小鹿", scenes=Scenes(("ice",), random=True))
    again = _dialog(store, ("like", 0))
    assert again.random_box.isChecked() and not _boxes_on(again) and again.scenes.chosen() == ("ice",)
    assert again.value(("like", 0)) != ANY_SCENE
    for each in (dialog, again):
        each.done(QDialog.Rejected)


def test_on_random_a_name_still_plays_by_click_or_keyboard_and_a_box_does_not_tick(store):
    dialog = _dialog(store, ("like", 1))
    dialog.show()
    QApplication.processEvents()
    assert dialog.random_box.isChecked() and not _boxes_on(dialog)
    ice = dialog.buttons["ice"]
    assert ice.isEnabled() and ice.focusPolicy() == Qt.StrongFocus
    QTest.mouseClick(ice, Qt.LeftButton, Qt.NoModifier, QPoint(30, ice.height() // 2))
    assert dialog.key == "ice" and dialog.preview.scene == "ice"
    # A click where the box is highlights the name too, and ticks nothing.
    _tick(dialog, "lace")
    assert dialog.key == "lace" and dialog.scenes.chosen() == () and not dialog.has_changes()
    # The keyboard: Space on a name highlights it, and ticks nothing.
    QTest.keyClick(dialog.buttons["stars"], Qt.Key_Space)
    assert dialog.key == "stars" and dialog.preview.scene == "stars" and dialog.scenes.chosen() == ()
    assert not dialog.has_changes()
    dialog.done(QDialog.Rejected)


def test_one_on_scenes_this_version_lacks_shows_as_random_and_only_a_change_is_saved(store, tmp_path):
    from blacklist_detect.guests import lobby_choice

    gone = Scenes(("no_such_scene",))
    store.update_like(0, "心动小鹿", scenes=gone)
    assert lobby_choice(store.likes, [], store.likes[:1], "classic") == "random"
    dialog = _dialog(store, ("like", 0))
    # As the list says it and as it plays: 随机, nothing ticked, no 都不勾：不放.
    assert _rows(dialog)[4][1] == "随机" and dialog.random_box.isChecked() and dialog.hint.isHidden()
    assert dialog.scenes.chosen() == () and not _boxes_on(dialog) and not dialog.has_changes()
    # Just looking saves nothing; 随机 off and on again is no change either.
    dialog.random_box.click()
    dialog.random_box.click()
    assert not dialog.has_changes()
    dialog.ok_button.click()
    assert store.likes[0].scenes == gone and Store(tmp_path).likes[0].scenes == gone
    # Unticking 随机 to leave nothing ticked is 不放, and saved.
    again = _dialog(store, ("like", 0))
    again.random_box.click()
    assert again.value(("like", 0)) == OFF and _rows(again)[4][1] == "不放" and again.has_changes()
    again.ok_button.click()
    assert store.likes[0].scenes == OFF and Store(tmp_path).likes[0].scenes == OFF


def test_every_scene_name_shows_whole_in_the_grid_with_its_name_as_a_tooltip(store):
    from blacklist_detect import love_scenes

    dialog = _dialog(store, ("like", 0))
    dialog.show()
    QApplication.processEvents()
    assert len(dialog.buttons) == len(love_scenes.SCENES)
    for key, title in love_scenes.SCENES:
        button = dialog.buttons[key]
        # Highlighted (bold) or not, it is not cut with …, and its box sits clear of it.
        assert button.shown_name(True) == button.shown_name(False) == title, title
        assert button.toolTip() == title
    dialog.done(QDialog.Rejected)


def test_the_preview_is_silent_and_replays_from_its_start(store):
    dialog = _dialog(store, ("like", 0))
    assert dialog.preview.width() == dialog.PREVIEW_W and dialog.play_button.toolTip() == "从头播放"
    QTest.qWait(80)
    before = dialog.preview._clock.elapsed()
    dialog.play_button.click()
    assert dialog.preview.scene == "stars" and dialog.preview._clock.elapsed() < before
    # No music anywhere in it.
    assert not hasattr(dialog, "music")
    dialog.done(QDialog.Rejected)
    assert not dialog.preview._tick.isActive()
