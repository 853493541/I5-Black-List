"""The 场景 beside a 嘉宾's, a 组合's and 我's own fields (ScenePane): 播放场景 off is 不放, on with none ticked
随机, on with ticks those; saved by the dialog's 添加 / 保存 alone, and untouched kept exactly."""

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, Qt  # noqa: E402
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
    """Whether the list's boxes can be ticked: all of them, or (播放场景 off) none."""
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
    assert _opened(off) == (False, ()) and not _boxes_on(off) and off.hint.text() == ""
    # 编辑组合 and 我的场景, each on its one scene.
    for dialog, key in ((_combo(store), "angel"), (_me(store), "lace")):
        pane = dialog.pane
        assert _opened(pane) == (True, (key,)) and _boxes_on(pane) and not dialog.has_changes()
        # Its ticked plays.
        assert pane.key == key and pane.preview.scene == key
        dialog.done(QDialog.Rejected)
    # A new 嘉宾 or 组合 starts on 不放, its boxes gray and no hint; 播放场景 ticked, 随机.
    from blacklist_detect.ui_guest_scenes import HINT
    from blacklist_detect.ui_guests import ComboDialog
    from blacklist_detect.ui_likes import LikeDialog

    for dialog in (LikeDialog(), ComboDialog(store.likes)):
        pane = dialog.pane
        assert _opened(pane) == (False, ()) and not _boxes_on(pane) and pane.hint.text() == "" and pane.value() == OFF
        assert not dialog.has_changes()
        pane.play_box.click()
        assert _boxes_on(pane) and pane.hint.text() == HINT and pane.value() == ANY_SCENE
        dialog.done(QDialog.Rejected)


def test_the_hint_shows_only_while_scenes_play_whatever_is_ticked(store):
    from blacklist_detect.ui_guest_scenes import HINT

    assert HINT == "不勾选场景则随机播放"
    dialog = _like(store, 1)
    pane = dialog.pane
    assert pane.hint.text() == HINT
    _tick(pane, "ice")
    assert pane.hint.text() == HINT and pane.value() == Scenes(("ice",))
    _tick(pane, "claw")
    assert pane.hint.text() == HINT and pane.value() == Scenes(("ice", "claw"))
    pane.play_box.click()
    assert pane.hint.text() == "" and pane.value() == OFF
    pane.play_box.click()
    assert pane.hint.text() == HINT and pane.value() == Scenes(("ice", "claw"))
    dialog.done(QDialog.Rejected)


def test_a_guest_s_three_states_are_saved_both_ways(store, tmp_path, monkeypatch):
    """Through the 嘉宾 page: 播放场景 off saves 不放, on with none ticked 随机, on with ticks those."""
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
    # 播放场景 off: 不放.
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
    assert _opened(shown[0].pane) == (True, ()) and shown[0].pane.hint.text() == "不勾选场景则随机播放"
    assert _opened(shown[1].pane) == (True, ("ice",)) and _opened(shown[2].pane) == (True, ())
    for dialog in shown:
        dialog.done(QDialog.Rejected)
    page = _page(store)
    for kind in (LikeDialog, ComboDialog, MeDialog):
        # 播放场景 off and on again is no change either.
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
    # Space ticks or unticks; a click anywhere on 播放场景's row ticks it.
    QTest.keyClick(pane.buttons["stars"], Qt.Key_Space)
    assert pane.value() == Scenes(("ice", "fluffy")) and dialog.has_changes()
    box = pane.play_box
    QTest.mouseClick(box, Qt.LeftButton, Qt.NoModifier, QPoint(box.width() - 4, box.height() // 2))
    assert pane.value() == OFF
    dialog.done(QDialog.Rejected)


def test_the_box_says_play_scenes_in_every_dialog(store):
    for dialog in (_like(store, 0), _combo(store), _me(store)):
        assert dialog.pane.play_box.text() == "播放场景" and "播放" in dialog.pane.play_box.toolTip()
        dialog.done(QDialog.Rejected)


def _spread(image, rect: QRect) -> int:  # noqa: ANN001
    """How far from gray the most coloured pixel in rect is: 0 for black, white and every gray between."""
    widest = 0
    for x in range(rect.left(), rect.right() + 1):
        for y in range(rect.top(), rect.bottom() + 1):
            color = image.pixelColor(x, y)
            rgb = (color.red(), color.green(), color.blue())
            widest = max(widest, max(rgb) - min(rgb))
    return widest


@pytest.mark.parametrize("dark", [False, True])
def test_with_play_scenes_off_no_box_ticks_and_every_box_and_dot_is_gray(store, dark):
    """播放场景 off: no box takes a click or Space, and each box, ticked or not, and each dot is gray; on again,
    the ticks are back and coloured. The names still play. The same in 编辑嘉宾 and 编辑组合."""
    from blacklist_detect.ui_love_pick import SceneChoice
    from blacklist_detect.ui_theme import use_theme

    use_theme("蓝色", "dark" if dark else "light")
    try:
        for dialog in (_like(store, 0), _combo(store)):
            pane = dialog.pane
            _tick(pane, "ice")
            ticked = pane.scenes.chosen()
            pane.play_box.click()
            assert not _boxes_on(pane)
            for key, button in pane.buttons.items():
                _tick(pane, key)
                QTest.keyClick(button, Qt.Key_Space)
            assert pane.scenes.chosen() == ticked and pane.value() == OFF
            # Ticked and not, away from the highlighted row so its band is not in the way.
            ice, plain = pane.buttons["ice"], pane.buttons["lace"]
            assert pane.key not in ("ice", "lace")
            box = QRect(ice.width() - 33, (ice.height() - SceneChoice.BOX) // 2 - 1, SceneChoice.BOX + 2, SceneChoice.BOX + 2)
            dot = QRect(16, ice.height() // 2 - SceneChoice.DOT, 2 * SceneChoice.DOT, 2 * SceneChoice.DOT)
            for button in (ice, plain):
                image = button.grab().toImage()
                assert _spread(image, box) <= 12 and _spread(image, dot) <= 12, (type(dialog).__name__, button.key)
            pane.play_box.click()
            assert _boxes_on(pane) and pane.scenes.chosen() == ticked
            image = ice.grab().toImage()
            assert _spread(image, box) > 40 and _spread(image, dot) > 40
            # A click on a name plays it either way.
            pane.play_box.click()
            QTest.mouseClick(ice, Qt.LeftButton, Qt.NoModifier, QPoint(30, ice.height() // 2))
            assert pane.key == "ice" and pane.scenes.chosen() == ticked
            dialog.done(QDialog.Rejected)
    finally:
        use_theme("蓝色", "light")


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
    # It opens on the scene still, nothing made; ▶ plays it from its start, a click on a name plays that one.
    assert pane.preview.scene == "stars" and pane.preview.is_still and not pane.preview._tick.isActive()
    pane.play_button.click()
    assert not pane.preview.is_still and pane.preview._tick.isActive() and pane.preview._clock.elapsed() < 80
    pane.buttons["ice"].click()
    assert pane.preview.scene == "ice" and not pane.preview.is_still
    # No music anywhere in it.
    assert not hasattr(dialog, "music") and not hasattr(pane, "music")
    dialog.done(QDialog.Rejected)
    assert not pane.preview._tick.isActive()


def _laid_out(dialog) -> None:  # noqa: ANN001
    """Shown (off screen) on a 1080p-at-150% screen, so its widgets have their places."""
    dialog.fit_height(672)
    dialog.show()
    QApplication.processEvents()


def _at(dialog, widget: QWidget) -> QRect:  # noqa: ANN001
    return QRect(widget.mapTo(dialog, QPoint(0, 0)), widget.size())


def test_a_guest_s_name_and_nickname_share_a_row_with_the_reason_and_preview_under_them(store):
    from blacklist_detect.ui_likes import LikeDialog

    places = []
    for dialog in (LikeDialog(), _like(store, 0)):
        _laid_out(dialog)
        name, nickname, reason, preview = (_at(dialog, widget) for widget in (dialog.name_edit, dialog.nickname_edit, dialog.detail_edit, dialog.pane.preview))
        # 名字 and 昵称 on one row, 名字 the wider (about 3:2); 原因 under them as wide as both; the preview under it.
        assert name.y() == nickname.y() and name.right() < nickname.left()
        assert 1.3 < name.width() / nickname.width() < 1.7
        assert reason.top() > name.bottom() and (reason.left(), reason.right()) == (name.left(), nickname.right())
        assert reason.height() >= 3 * dialog.fontMetrics().lineSpacing()
        assert preview.top() > reason.bottom() and preview.width() == dialog.pane.PREVIEW_W
        places.append((name, nickname, reason, preview, dialog.width()))
        # 名字's error under it keeps 昵称 on its row.
        dialog.name_edit.clear()
        dialog._accept()
        QApplication.processEvents()
        assert dialog.name_error.isVisible() and _at(dialog, dialog.name_edit).y() == _at(dialog, dialog.nickname_edit).y()
        assert _at(dialog, dialog.name_error).top() > name.bottom()
        dialog.done(QDialog.Rejected)
    # 编辑嘉宾 is laid out as 添加嘉宾 is.
    assert places[0] == places[1]


def test_a_combo_s_guests_are_boxed_over_the_preview_at_the_column_s_foot(store):
    from blacklist_detect.model import Entry
    from blacklist_detect.ui_guest_scenes import TickBox
    from blacklist_detect.ui_guests import ComboDialog

    places = []
    for dialog in (ComboDialog(store.likes), _combo(store)):
        _laid_out(dialog)
        label = next(label for label in dialog.findChildren(QLabel) if label.text() == "已添加的嘉宾")
        box, preview, pane = (_at(dialog, widget) for widget in (dialog.people_box, dialog.pane.preview, dialog.pane))
        # The label, the box under it, the preview at the column's foot, level with the 场景 beside it.
        assert dialog.people_box.objectName() == "section" and dialog.people_box.isAncestorOf(dialog.people_scroll)
        assert _at(dialog, label).bottom() < box.top() and box.bottom() < preview.top()
        assert preview.bottom() == pane.bottom() and preview.left() == box.left()
        # The box takes the free height: more than its three 嘉宾 need, so they do not scroll.
        assert box.height() > 3 * TickBox.H + 2 * ComboDialog.PAD
        assert dialog.people_scroll.verticalScrollBar().maximum() == 0
        places.append((box, preview, dialog.width(), dialog.height()))
        dialog.done(QDialog.Rejected)
    # 编辑组合 is laid out as 添加组合 is.
    assert places[0] == places[1]
    # Many 嘉宾 scroll in the box, the dialog no taller.
    many = ComboDialog([Entry(f"心动小鹿的好朋友{index:02d}") for index in range(40)])
    _laid_out(many)
    assert many.people_scroll.verticalScrollBar().maximum() > 0 and _at(many, many.people_box) == places[0][0]
    many.done(QDialog.Rejected)
