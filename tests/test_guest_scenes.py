"""The 场景 beside a 嘉宾's, a 组合's and 我's own fields (ScenePane): 放场景 off is 不放, on with none ticked
随机, on with ticks those; saved by the dialog's 添加 / 保存 alone, and untouched kept exactly."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog, QLabel, QListWidget, QWidget  # noqa: E402

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
    store.add_like("心动小鹿", "小鹿", scenes=Scenes(("fluffy", "stars")))
    store.add_like("心动星星")
    store.add_like("晚风吹过", scenes=OFF)
    store.set_combos([Combo(("心动小鹿", "心动星星"), Scenes(("angel",)))])
    store.set_me(Scenes(("lace",)))
    return store


def _like(store, index: int):  # noqa: ANN001, ANN202
    from blacklist_detect.ui_likes import LikeDialog

    like = store.likes[index]
    return LikeDialog(like.name, like.nickname, like.reason, allow_delete=True, scenes=like.scenes)


def _combo(store, number: int = 0):  # noqa: ANN001, ANN202
    from blacklist_detect.ui_guests import ComboDialog

    return ComboDialog(store.likes, store.combos[number])


def _me(store):  # noqa: ANN001, ANN202
    from blacklist_detect.ui_likes import MeDialog

    return MeDialog(store.me, store.player_name)


def _page(store):  # noqa: ANN001, ANN202
    from blacklist_detect.ui_likes import LikesPage

    return LikesPage(store, lambda *_args, **_kwargs: None)


def _tick(pane, *keys: str) -> None:  # noqa: ANN001
    """A click on each scene's box, as the player ticks or unticks it."""
    for key in keys:
        button = pane.buttons[key]
        QTest.mouseClick(button, Qt.LeftButton, Qt.NoModifier, QPoint(button.width() - 24, button.height() // 2))


def _boxes_on(pane) -> bool:  # noqa: ANN001
    """Whether the list's boxes can be ticked: all of them, or (放场景 off) none."""
    on = {button.box_enabled for button in pane.buttons.values()}
    assert len(on) == 1 and pane.scenes.isEnabled()
    return on.pop()


def _opened(pane) -> tuple[bool, tuple[str, ...]]:  # noqa: ANN001
    return pane.play_box.isChecked(), pane.scenes.chosen()


def test_the_three_states_load_in_each_dialog(store):
    # 编辑嘉宾: ticks, 随机, 不放.
    ticks, anything, nothing = _like(store, 0), _like(store, 1), _like(store, 2)
    assert _opened(ticks.pane) == (True, ("stars", "fluffy")) and _opened(anything.pane) == (True, ())
    off = nothing.pane
    assert _opened(off) == (False, ()) and not _boxes_on(off) and off.hint.text() == "不放场景"
    # 编辑组合 and 我的场景, each on its one scene.
    for dialog, key in ((_combo(store), "angel"), (_me(store), "lace")):
        pane = dialog.pane
        assert _opened(pane) == (True, (key,)) and _boxes_on(pane) and not dialog.has_changes()
        # Its ticked plays.
        assert pane.key == key and pane.preview.scene == key
        dialog.done(QDialog.Rejected)
    # A new 嘉宾 or 组合 starts on 随机.
    from blacklist_detect.ui_guests import ComboDialog
    from blacklist_detect.ui_likes import LikeDialog

    for dialog in (LikeDialog(), ComboDialog(store.likes)):
        assert _opened(dialog.pane) == (True, ()) and dialog.pane.hint.text() == "随机放一个场景"
        assert dialog.pane.value() == ANY_SCENE
        dialog.done(QDialog.Rejected)


def test_the_hint_says_what_plays_now(store):
    dialog = _like(store, 1)
    pane = dialog.pane
    assert pane.hint.text() == "随机放一个场景"
    _tick(pane, "ice")
    assert pane.hint.text() == "放冰蓝极光" and pane.value() == Scenes(("ice",))
    _tick(pane, "claw")
    assert pane.hint.text() == "2个里随机放一个" and pane.value() == Scenes(("ice", "claw"))
    pane.play_box.click()
    assert pane.hint.text() == "不放场景" and pane.value() == OFF
    # Short: the longest scene name in it is 8 字 all told.
    from blacklist_detect.ui_guest_scenes import hint

    assert hint(Scenes(("fluffy",))) == "放毛茸茸保护协会" and hint(Scenes(("no_such_scene",))) == "随机放一个场景"
    dialog.done(QDialog.Rejected)


def test_a_guest_s_three_states_are_saved_both_ways(store, tmp_path, monkeypatch):
    """Through the 嘉宾 page: 放场景 off saves 不放, on with none ticked 随机, on with ticks those."""
    from blacklist_detect.ui_likes import LikeDialog

    page = _page(store)

    def answer(on: bool, *keys: str):  # noqa: ANN202
        def run(dialog) -> int:  # noqa: ANN001
            pane = dialog.pane
            if pane.play_box.isChecked() != on:
                pane.play_box.click()
            for key in pane.buttons:
                if (key in keys) != bool(pane.buttons[key].chosen):
                    pane.buttons[key].set_chosen(key in keys)
            pane._edited()
            dialog._accept()
            return dialog.result()

        return run

    for on, keys, saved in ((False, (), OFF), (True, (), ANY_SCENE), (True, ("ice", "claw"), Scenes(("ice", "claw")))):
        for index in range(3):
            monkeypatch.setattr(LikeDialog, "exec", answer(on, *keys))
            page.edit(index)
            assert store.likes[index].scenes == saved == Store(tmp_path).likes[index].scenes, (index, saved)
    # Off with ticks under it: 不放, the ticks not saved.
    monkeypatch.setattr(LikeDialog, "exec", answer(False, "ice"))
    page.edit(0)
    assert store.likes[0].scenes == OFF
    assert [like.name for like in store.likes] == ["心动小鹿", "心动星星", "晚风吹过"]


def test_a_combo_s_members_and_scenes_are_saved_together(store, tmp_path, monkeypatch):
    from blacklist_detect.ui_guests import ComboDialog

    page = _page(store)
    seen = []

    def run(dialog) -> int:  # noqa: ANN001
        seen.append(dialog.windowTitle())
        dialog.people_buttons["晚风吹过"].click()
        dialog.people_buttons["心动小鹿"].click()
        _tick(dialog.pane, "angel", "ice", "neon")
        assert dialog.has_changes()
        dialog._accept()
        return dialog.result()

    monkeypatch.setattr(ComboDialog, "exec", run)
    page.edit_combo(0)
    assert seen == ["编辑组合"]
    for read in (store, Store(tmp_path)):
        assert read.combos == [Combo(("心动星星", "晚风吹过"), Scenes(("ice", "neon")))]
    # 放场景 off: 不放.
    monkeypatch.setattr(ComboDialog, "exec", lambda dialog: dialog.pane.play_box.click() or dialog._accept() or dialog.result())
    page.edit_combo(0)
    assert store.combos == [Combo(("心动星星", "晚风吹过"), OFF)]


def test_the_me_dialog_sets_the_player_s_own_scenes(store, tmp_path, monkeypatch):
    from blacklist_detect.ui_likes import NO_NAME, MeDialog

    page = _page(store)
    page.refresh()
    seen = []

    def run(dialog) -> int:  # noqa: ANN001
        seen.append((dialog.windowTitle(), dialog.name_label.text()))
        _tick(dialog.pane, "lace", "ice")
        dialog._accept()
        return dialog.result()

    monkeypatch.setattr(MeDialog, "exec", run)
    # The 我 row, any cell of it, opens it.
    page.table.cellClicked.emit(0, 2)
    assert seen == [("我的场景", "测试主播")]
    assert store.me == Scenes(("ice",)) == Store(tmp_path).me and store.likes[0].scenes == Scenes(("fluffy", "stars"))
    assert MeDialog(OFF).name_label.text() == NO_NAME


def test_cancel_close_and_esc_keep_nothing(store, monkeypatch):
    from blacklist_detect.ui_guests import ComboDialog
    from blacklist_detect.ui_likes import LikeDialog, MeDialog

    before = (list(store.likes), list(store.combos), store.me)
    for close in ("x", "esc"):
        for make in (lambda: _like(store, 0), lambda: _combo(store), lambda: _me(store)):
            dialog = make()
            _tick(dialog.pane, "ice")
            dialog.pane.play_box.click()
            assert dialog.has_changes()
            if close == "x":
                dialog.close_button.click()
            else:
                QApplication.sendEvent(dialog, QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Escape, Qt.NoModifier))
            assert dialog.result() == QDialog.Rejected, close
    # Through the page: closed, nothing is written.
    page = _page(store)
    for kind in (LikeDialog, ComboDialog, MeDialog):
        monkeypatch.setattr(kind, "exec", lambda dialog: _tick(dialog.pane, "ice") or QDialog.Rejected)
    page.edit(0)
    page.edit_combo(0)
    page.edit_me()
    assert (store.likes, store.combos, store.me) == before


def test_saved_untouched_each_keeps_exactly_what_it_had(store, tmp_path, monkeypatch):
    """Scenes this version lacks, alone (shown as 随机) or beside one it has, and 随机 with ticks from an
    older version: saved without its 场景 touched, each is written back as it was."""
    from blacklist_detect.guests import lobby_choice
    from blacklist_detect.ui_guests import ComboDialog
    from blacklist_detect.ui_likes import LikeDialog, MeDialog

    gone, mixed, old = Scenes(("no_such_scene",)), Scenes(("ice", "no_such_scene")), Scenes(("ice",), random=True)
    store.update_like(0, "心动小鹿", "小鹿", "", gone)
    store.update_like(1, "心动星星", "", "", mixed)
    store.set_combos([Combo(("心动小鹿", "心动星星"), old)])
    store.set_me(gone)
    assert lobby_choice(store.likes, [], store.likes[:1], "classic") == "random"
    # As it plays: the gone one 随机, nothing ticked; 随机 with ticks 随机, its stale ticks not shown.
    shown = [_like(store, 0), _like(store, 1), _combo(store)]
    assert _opened(shown[0].pane) == (True, ()) and shown[0].pane.hint.text() == "随机放一个场景"
    assert _opened(shown[1].pane) == (True, ("ice",)) and _opened(shown[2].pane) == (True, ())
    for dialog in shown:
        dialog.done(QDialog.Rejected)
    page = _page(store)
    for kind in (LikeDialog, ComboDialog, MeDialog):
        # 放场景 off and on again is no change either.
        monkeypatch.setattr(kind, "exec", lambda dialog: dialog.pane.play_box.click() or dialog.pane.play_box.click() or dialog._accept() or dialog.result())
    page.edit(0)
    page.edit(1)
    page.edit_combo(0)
    page.edit_me()
    for read in (store, Store(tmp_path)):
        assert [like.scenes for like in read.likes[:2]] == [gone, mixed]
        assert read.combos[0].scenes == old and read.me == gone
    # Changed, it is saved as the boxes say: the gone one ticked to 冰蓝极光, 随机 with ticks to 不放.
    monkeypatch.setattr(LikeDialog, "exec", lambda dialog: _tick(dialog.pane, "ice") or dialog._accept() or dialog.result())
    monkeypatch.setattr(ComboDialog, "exec", lambda dialog: dialog.pane.play_box.click() or dialog._accept() or dialog.result())
    page.edit(0)
    page.edit_combo(0)
    assert store.likes[0].scenes == Scenes(("ice",)) and store.combos[0].scenes == OFF


def test_off_greys_the_boxes_and_keeps_its_ticks_and_a_name_still_plays(store):
    dialog = _like(store, 0)
    pane = dialog.pane
    pane.play_box.click()
    assert not _boxes_on(pane) and pane.scenes.chosen() == ("stars", "fluffy") and pane.value() == OFF
    # A click where the box is highlights the name and plays it, and ticks nothing; so does Space.
    pane.show()
    _tick(pane, "lace")
    assert pane.key == "lace" and pane.preview.scene == "lace" and pane.scenes.chosen() == ("stars", "fluffy")
    QTest.keyClick(pane.buttons["ice"], Qt.Key_Space)
    assert pane.key == "ice" and pane.scenes.chosen() == ("stars", "fluffy")
    pane.buttons["ice"].grab()
    # On again: its ticks back as they were, no change at all.
    pane.play_box.click()
    assert _boxes_on(pane) and pane.value() == Scenes(("fluffy", "stars")) and not pane.has_changes()
    pane.stop()


def test_one_scene_per_row_a_box_ticks_and_a_name_plays(store):
    from blacklist_detect import love_scenes

    dialog = _like(store, 0)
    pane = dialog.pane
    dialog.show()
    QApplication.processEvents()
    places = [pane.buttons[key].geometry().topLeft() for key in love_scenes.KEYS]
    assert len({place.x() for place in places}) == 1 and [place.y() for place in places] == sorted({place.y() for place in places})
    # Every name whole, highlighted (bold) or not, its box clear of it.
    for key, title in love_scenes.SCENES:
        assert pane.buttons[key].shown_name(True) == pane.buttons[key].shown_name(False) == title, title
    # A click on a box ticks it and the highlight stays; one on the name highlights it and plays it.
    _tick(pane, "ice")
    assert pane.scenes.chosen() == ("ice", "stars", "fluffy") and pane.key == "stars"
    ice = pane.buttons["ice"]
    QTest.mouseClick(ice, Qt.LeftButton, Qt.NoModifier, QPoint(30, ice.height() // 2))
    assert pane.key == "ice" and pane.preview.scene == "ice" and pane.scenes.chosen() == ("ice", "stars", "fluffy")
    # Space ticks or unticks; a click anywhere on 放场景's row ticks it.
    QTest.keyClick(pane.buttons["stars"], Qt.Key_Space)
    assert pane.value() == Scenes(("ice", "fluffy")) and dialog.has_changes()
    box = pane.play_box
    QTest.mouseClick(box, Qt.LeftButton, Qt.NoModifier, QPoint(box.width() - 4, box.height() // 2))
    assert pane.value() == OFF
    dialog.done(QDialog.Rejected)


def test_no_dialog_lists_other_guests_but_the_combo_its_members(store):
    def words(root: QWidget) -> str:
        said = [widget.text() for kind in (QAbstractButton, QLabel) for widget in root.findChildren(kind)]
        return " ".join(said + [widget.toolTip() for widget in root.findChildren(QWidget)])

    for dialog in (_like(store, 0), _me(store)):
        assert not dialog.findChildren(QListWidget)
        assert not [name for name in ("心动星星", "晚风吹过") if name in words(dialog)]
        dialog.done(QDialog.Rejected)
    combo = _combo(store)
    # By 昵称 or name, as the 嘉宾 list shows them, one per row, its own ticked first.
    assert [box.text() for box in combo.people_buttons.values()] == ["心动星星", "小鹿", "晚风吹过"]
    assert [box.isChecked() for box in combo.people_buttons.values()] == [True, True, False]
    rows = [box.geometry().y() for box in combo.people_buttons.values()]
    assert rows == sorted(rows) and len(set(rows)) == 3
    combo.done(QDialog.Rejected)


def test_the_preview_is_silent_and_replays_from_its_start(store):
    dialog = _like(store, 0)
    pane = dialog.pane
    assert dialog.isAncestorOf(pane.preview) and pane.play_button.toolTip() == "从头播放"
    QTest.qWait(80)
    before = pane.preview._clock.elapsed()
    pane.play_button.click()
    assert pane.preview.scene == "stars" and pane.preview._clock.elapsed() < before
    # No music anywhere in it.
    assert not hasattr(dialog, "music") and not hasattr(pane, "music")
    dialog.done(QDialog.Rejected)
    assert not pane.preview._tick.isActive()
