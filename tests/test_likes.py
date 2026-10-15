"""嘉宾: players worth meeting again, the other side of 黑名单."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QLabel  # noqa: E402

from blacklist_detect.importing import ELSEWHERE, MERGE, plan_import  # noqa: E402
from blacklist_detect.model import Entry, Scenes  # noqa: E402
from blacklist_detect.pipeline import CheckResult, Hit, NameSlot  # noqa: E402
from blacklist_detect.storage import Store  # noqa: E402


def test_the_list_is_saved_on_its_own(tmp_path):
    store = Store(tmp_path)
    like = store.add_like("救人很稳的小明", "小明", "上把救了我三次")
    assert like is not None and like.shown() == "小明"
    assert store.add_like("救人很稳的小明") is None, "one name once"
    store.add_like("无昵称的人")
    again = Store(tmp_path)
    assert [(e.name, e.nickname, e.reason) for e in again.likes] == [
        ("救人很稳的小明", "小明", "上把救了我三次"),
        ("无昵称的人", "", ""),
    ]
    # Without a 昵称 a lobby shows the full name.
    assert again.likes[1].shown() == "无昵称的人"
    assert again.entries == [], "嘉宾 is not 黑名单"
    assert (tmp_path / "likes.json").exists()
    assert again.update_like(0, "救人很稳的小明", "明哥", "")
    assert Store(tmp_path).likes[0].shown() == "明哥"
    before = again.snapshot_likes()
    again.clear_likes()
    assert Store(tmp_path).likes == []
    again.restore_likes(before)
    assert [e.nickname for e in Store(tmp_path).likes] == ["明哥", ""]
    again.reset()
    assert Store(tmp_path).likes == []


def test_importing_into_likes_keeps_the_note_whole_and_skips_blacklisted_names(tmp_path):
    store = Store(tmp_path)
    store.add("坑人的", reason="炸房")
    store.add_like("小明", "明哥")
    rows = {row.name: row for row in plan_import("小明（救人很稳）\n小红（开局就炸房也没事）\n坑人的（其实还行）", store.likes, (), store.entries)}
    assert rows["小明"].status == MERGE
    # No 标签 on 嘉宾: 炸房 in the note is just words.
    assert rows["小红"].tags == () and rows["小红"].reason == "开局就炸房也没事"
    assert rows["坑人的"].status == ELSEWHERE and not rows["坑人的"].checked
    chosen = [(r.name, r.tags, r.reason, r.target if r.status == MERGE else -1) for r in rows.values() if r.checked]
    assert store.import_likes(chosen) == (1, 1)
    saved = {e.name: (e.nickname, e.reason) for e in Store(tmp_path).likes}
    # A merge keeps one's own 昵称.
    assert saved == {"小明": ("明哥", "救人很稳"), "小红": ("", "开局就炸房也没事")}


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect.ui import MainWindow

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    made = MainWindow()
    # The marks over the game, as before 安全模式: 完整模式 and 自动检查, agreed to once.
    made.store.consented = ["full", "auto"]
    made._on_display_mode("full")
    made._on_auto_mode("auto")
    made._watch_timer.stop()
    yield made
    made.close()


def test_the_page_lists_names_with_their_nicknames(window):
    page = window.likes_page
    assert window.tabs.widget(window.likes_tab) is page
    assert page.table.isHidden() and page.empty.isHidden() is False
    assert page.empty_add_button.isHidden() is False
    window.store.add_like("救人很稳的小明", "明哥", "上把救了我")
    window.store.add_like("小红")
    page.refresh()
    window._show_list()
    assert window._tab_buttons[window.likes_tab].count() == 2
    rows = [[page.table.item(r, c).text() for c in range(5)] for r in range(page.table.rowCount())]
    # Newest first; 昵称 beside the name; 全部随机 under 场景 for none ticked (any scene); a dash for
    # 最近遇到 until they are met.
    assert rows == [["小红", "", "全部随机", "", "—"], ["救人很稳的小明", "明哥", "全部随机", "上把救了我", "—"]]
    page.search.setText("明哥")
    assert page.table.rowCount() == 1
    page.search.setText("没有这个")
    assert page.table.isHidden() and "没有找到" in page.empty.title.text()


def test_the_effect_column_shows_every_scene_name_whole(window):
    from PySide6.QtGui import QFontMetrics

    from blacklist_detect import love_scenes
    from blacklist_detect.ui_likes import THEME_COLUMN
    from blacklist_detect.ui_theme import chinese_font

    # 毛茸茸保护协会, the longest, with the cell's padding on both sides.
    longest = max(QFontMetrics(chinese_font()).horizontalAdvance(name) for _key, name in love_scenes.SCENES)
    assert window.likes_page.table.columnWidth(THEME_COLUMN) >= longest + 2 * 12


def test_a_blacklisted_name_is_refused_not_moved(window, monkeypatch):
    from blacklist_detect import ui_likes

    window.store.add("小明", reason="炸房")
    dialogs = []

    def run(dialog) -> int:  # noqa: ANN001
        dialogs.append(dialog)
        dialog.name_edit.setText("小明")
        dialog._accept()
        return dialog.result()

    monkeypatch.setattr(ui_likes.LikeDialog, "exec", run)
    window.likes_page.add_one()
    # A player is on one list: a 黑名单 name stays there and is not added to 嘉宾.
    assert dialogs[0].name_error.text() == "已经在黑名单里了"
    assert dialogs[0].result() != QDialog.Accepted
    assert [entry.name for entry in window.store.entries] == ["小明"] and window.store.likes == []


def test_a_record_shows_a_like_in_rose_with_its_nickname(window):
    from blacklist_detect.ui_theme import THEME

    window.store.add_like("救人很稳的小明", "明哥")
    window.store.add_scan([{"seat": 1, "name": "救人很稳", "unclear": False}, {"seat": 2, "name": "路人", "unclear": False}])
    window._reload_history()
    wrap = window.history_table.cellWidget(0, 0)
    assert wrap.findChild(QLabel, "seatHeart") is not None
    assert wrap.findChild(QLabel, "rowName").text() == "明哥"
    item = window.history_table.item(0, 0)
    assert item.foreground().color().name() == THEME["rose"]
    assert "是嘉宾「救人很稳的小明」" in item.toolTip()
    # A seat no one listed offers both lists.
    assert [a.text() for a in window._seat_menu(0, 1).actions() if a.text()] == ["加入黑名单", "加入嘉宾列表", "复制名字"]
    assert [a.text() for a in window._seat_menu(0, 0).actions() if a.text()] == ["编辑", "复制名字"]


def test_a_live_check_rings_likes_in_rose_and_splits_the_ring_with_a_hit(window):
    window.store.add_like("救人很稳的小明", "明哥")
    window.store.add_like("小红", scenes=Scenes(("lace",)))
    names = [
        NameSlot(0, (0, 0, 1, 1), "救人很稳", "救人很稳", False, 0.9, False),
        NameSlot(1, (0, 0, 1, 1), "小红", "小红", False, 0.9, False),
        NameSlot(2, (0, 0, 1, 1), "坏人", "坏人", False, 0.9, False),
    ]
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    window._live_check = True
    window._on_lobby_placed(button)
    # No 黑名单, 嘉宾 players, 小红's 玫瑰花边: a rose ring, a heart badge on the right, their names on the left.
    window._show_panel(CheckResult(True, "", names=names, button_box=button))
    card = window.like_card
    assert window.panel.mode == "liked" and window.panel.ring() == "#c2306b"
    assert card.isVisible() and window.clear_mark.isVisible() and window.clear_mark.heart
    assert [label.text() for label in card.findChildren(QLabel, "hitName")] == ["明哥", "小红"]
    assert [f.property("tone") for f in card.findChildren(QLabel, "likeFlower")] == ["pink", "blue"]
    cover = window.panel.cover_geometry()
    assert card.x() + card.width() <= cover.x() < window.clear_mark.x()
    # 黑名单 too: the ring rose on the left and crimson on the right, a card on each side.
    hit = Hit(2, "坏人", "坏人", "", False, "", ("炸房",))
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    hit_card = window.hit_card
    assert window.panel.mode == "both" and window.panel.rings() == ("#c2306b", "#a8262f")
    assert window.panel.ring() == "#a8262f" and not window.clear_mark.isVisible()
    assert hit_card.isVisible() and card.isVisible()
    assert card.x() + card.width() <= cover.x() and hit_card.x() >= cover.x() + cover.width()
    # Nobody liked in the lobby: the green check, and no card.
    window._show_panel(CheckResult(True, "", names=names[2:], button_box=button))
    assert window.panel.mode == "clear" and not window.clear_mark.heart
    assert card.isVisible() is False
    # A blacklisted player alone: the red ring, and no 嘉宾 card.
    window._show_panel(CheckResult(True, "", names=names[2:], hits=[hit], button_box=button))
    assert window.panel.mode == "hit" and hit_card.isVisible() and card.isVisible() is False
    window.panel.hide()
    window.clear_mark.hide()
    window.hit_card.hide()


def test_likes_and_no_hit_play_the_border_once_per_lobby(window):
    window.store.add_like("小明")
    window.store.add_like("小红")
    names = [
        NameSlot(0, (0, 0, 1, 1), "小明", "小明", False, 0.9, False),
        NameSlot(1, (0, 0, 1, 1), "小红", "小红", False, 0.9, False),
        NameSlot(2, (0, 0, 1, 1), "坏人", "坏人", False, 0.9, False),
    ]
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    window._live_check = True
    window._on_lobby_placed(button)
    # One 嘉宾 player is enough: the marks and the border, as each 嘉宾 picks what greets them.
    window._show_panel(CheckResult(True, "", names=names[:1], button_box=button))
    assert window.panel.mode == "liked" and window.love.playing()
    window.love.stop()
    window._hide_panel_after_title()
    window._on_lobby_placed(button)
    # Two: the border, over the screen, parted around the button and its marks.
    window._show_panel(CheckResult(True, "", names=names, button_box=button))
    assert window.love.playing()
    assert window.love.geometry() == (QApplication.screenAt(window.panel.cover_geometry().center()) or QApplication.primaryScreen()).geometry()
    gap = window.love._gap.translated(window.love.x(), window.love.y())
    assert gap.contains(window.like_card.geometry().toRectF()) and gap.contains(window.panel.cover_geometry().toRectF())
    # The 嘉宾 card is level with the cover round the button and as tall, its knot above.
    cover, card = window.panel.cover_geometry(), window.like_card
    assert card.y() + card.top == cover.y() and card.height() == cover.height() + card.top
    # The same lobby checked again does not play it again.
    window.love.stop()
    window._show_panel(CheckResult(True, "", names=names, button_box=button))
    assert not window.love.playing()
    # A 黑名单 player stops it; leaving the lobby lets the next one play it.
    window._hide_panel_after_title()
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names, button_box=button))
    assert window.love.playing()
    hit = Hit(2, "坏人", "坏人", "", False, "", ())
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert not window.love.playing()
    window._hide_panel_after_title()


def test_the_guest_card_is_as_tall_as_the_cover_whatever_the_names(qapp):
    from blacklist_detect.ui_overlay import LikeCard

    card = LikeCard()
    # One name, two, or three (which get a size smaller to fit), the card is the cover's height.
    for names in (["小明"], ["小明", "小红"], ["小明", "小红", "一起开黑的朋友"]):
        card.set_people([(name, ()) for name in names], 82)
        assert card.body.maximumHeight() == 82 and card.height() == 82 + card.top, names
    # More than three scroll.
    card.set_people([(f"嘉宾{n}", ()) for n in range(6)], 82)
    assert card.body.maximumHeight() == 82 and card.scroll.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    card.deleteLater()


def test_the_marks_wear_the_look_of_the_scene_that_greets_them(window):
    from blacklist_detect.ui_overlay import love_look

    window.store.add_like("小红", scenes=Scenes(("classic",)))
    window.store.add_like("小明", scenes=Scenes(("ice",)))
    names = [NameSlot(i, (0, 0, 1, 1), name, name, False, 0.9, False) for i, name in enumerate(("小明", "小红", "坏人"))]
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    window._live_check = True
    marks = (window.panel, window.clear_mark, window.like_card)
    # 小红 on 经典: the marks wear its look.
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names[1:2], button_box=button))
    assert window.love.playing() and window.love.scene == "classic" and all(mark.look is love_look("classic") for mark in marks)
    names_ink = window.like_card.findChild(QLabel, "hitName").styleSheet()
    assert love_look("classic").ink in names_ink
    window._hide_panel_after_title()
    # 小明 alone: his own scene greets him, and the marks wear its look.
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names[:1], button_box=button))
    assert window.love.playing() and window.love.scene == "ice" and all(mark.look is love_look("ice") for mark in marks)
    window.love.stop()
    # With a 黑名单 player too, the 嘉宾 half of the ring is the look's.
    hit = Hit(2, "坏人", "坏人", "", False, "", ())
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.panel.mode == "both" and window.panel.look is love_look("ice")
    window._hide_panel_after_title()
    # 嘉宾场景 off in 设置: no scene, 小明's own neither, and 经典's look.
    window._set_love_effects(False)
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names[:2], button_box=button))
    assert not window.love.playing() and all(mark.look is love_look("classic") for mark in marks)
    window._hide_panel_after_title()


def test_the_border_ends_by_itself(window, monkeypatch):
    window.love.play(QApplication.primaryScreen().geometry(), QRect(500, 700, 300, 80))
    assert window.love.isVisible() and window.love.playing()
    # Each scene has its own length.
    DURATION = window.love.duration()
    monkeypatch.setattr(window.love, "elapsed", lambda: DURATION - 0.5)
    window.love._step()
    assert window.love.playing()
    monkeypatch.setattr(window.love, "elapsed", lambda: DURATION)
    window.love._step()
    assert not window.love.playing() and not window.love.isVisible()


def test_copying_likes_reads_back_in_the_import(window):
    window.store.add_like("小明", "明哥", "救人很稳")
    window.store.add_like("小红")
    window.likes_page.copy_list()
    text = QApplication.clipboard().text()
    assert text == "小明（救人很稳）\n小红"
    rows = plan_import(text, [], ())
    assert [(r.name, r.reason) for r in rows] == [("小明", "救人很稳"), ("小红", "")]


def test_a_picture_check_marks_likes(window):
    from blacklist_detect.ui import PictureResultDialog

    names = [NameSlot(i, (0, 0, 1, 1), n, n, False, 0.9, False) for i, n in enumerate(["救人很稳", "路人"])]
    dialog = PictureResultDialog("截图检查", result=CheckResult(True, "", names=names), likes=[Entry("救人很稳的小明", nickname="明哥")])
    assert dialog.seats[0].text() == "明哥" and dialog.seats[1].text() == "路人"
    assert dialog.seats[0].parentWidget().findChild(QLabel, "seatHeart") is not None
    dialog.close()


def test_a_like_is_moved_to_the_blacklist_when_asked(window, monkeypatch):
    from blacklist_detect import ui

    window.store.add_like("小明", "明哥")
    monkeypatch.setattr(ui.ConfirmDialog, "ask", staticmethod(lambda *_a, **_k: True))
    assert window._take_from_likes("小明") is True
    assert window.store.likes == []
    assert Qt.UserRole  # the module imports stay used


def test_the_border_fits_a_game_in_a_window(window, monkeypatch):
    from PySide6.QtCore import QRect

    from blacklist_detect import ui

    window.store.add_like("小红")
    window.store.add_like("小明")
    screen = QApplication.primaryScreen()
    area, ratio = screen.geometry(), screen.devicePixelRatio()
    game = QRect(area.x() + 80, area.y() + 60, area.width() // 2 + 300, area.height() // 2 + 200)
    left = round(area.x() + (game.x() - area.x()) * ratio)
    top = round(area.y() + (game.y() - area.y()) * ratio)
    native = (left, top, left + round(game.width() * ratio), top + round(game.height() * ratio))
    monkeypatch.setattr(ui, "window_rect_at", lambda x, y, order=(), innermost=True: native)
    middle_x = area.x() + (game.x() - area.x() + game.width() // 2)
    middle_y = area.y() + (game.y() - area.y() + game.height() // 2)
    box = (round(middle_x * ratio) - 90, round(middle_y * ratio), round(middle_x * ratio) + 90, round(middle_y * ratio) + 60)
    names = [NameSlot(0, (0, 0, 1, 1), "小红", "小红", False, 0.9, False), NameSlot(1, (0, 0, 1, 1), "小明", "小明", False, 0.9, False)]
    window._live_check = True
    window._show_panel(CheckResult(True, "", names=names, button_box=box))
    assert window.love.playing()
    assert window.love.geometry() == game
    window._hide_panel_after_title()


def test_reminding_can_leave_out_either_list_and_keeps_one(window):
    """提醒 in the 检查 panel: 黑名单 and 嘉宾, each ticked (✓) until untouched. Unticked, a list's players
    are not told about in a check: no ring, card, glow, effect or corner message. One stays on."""
    window.store.add("坏人", tags=("炸房",))
    window.store.add_like("小明")
    names = [
        NameSlot(0, (0, 0, 1, 1), "小明", "小明", False, 0.9, False),
        NameSlot(1, (0, 0, 1, 1), "坏人", "坏人", False, 0.9, False),
    ]
    hit = Hit(1, "坏人", "坏人", "", False, "", ("炸房",))
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    boxes = window.remind_boxes
    assert [box.text() for box in boxes.values()] == ["黑名单", "嘉宾"]
    assert all(box.isChecked() and not box.icon().isNull() for box in boxes.values())
    assert "提醒 黑名单+嘉宾" in window.settings_line()
    # 黑名单 off: the listed player is not told about, and a lobby with nobody to tell about is 检查完成.
    boxes["blacklist"].click()
    assert window.store.check_blacklist is False and Store(window.store.root).check_blacklist is False
    assert boxes["blacklist"].icon().isNull() and "提醒 只有嘉宾" in window.settings_line()
    window._live_check = True
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.panel.mode == "liked" and not window.hit_card.isVisible() and window.like_card.isVisible()
    window._show_panel(CheckResult(True, "", names=names[1:], hits=[hit], button_box=button))
    assert window.panel.mode == "clear" and window.panel.toolTip() == "检查完成" and not window.hit_card.isVisible()
    window._hide_panel_after_title()
    # The last one ticked stays: unticking 嘉宾 now does nothing.
    boxes["likes"].click()
    assert boxes["likes"].isChecked() and window.store.check_likes is True
    # 嘉宾 off, 黑名单 back on: 嘉宾 players are not told about, nor greeted.
    boxes["blacklist"].click()
    boxes["likes"].click()
    assert (window.store.check_blacklist, window.store.check_likes) == (True, False)
    assert "提醒 只有黑名单" in window.settings_line()
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names[:1], button_box=button))
    assert window.panel.mode == "clear" and window.panel.toolTip() == "未发现黑名单"
    assert not window.like_card.isVisible() and not window.love.playing()
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.panel.mode == "hit" and window.hit_card.isVisible() and not window.like_card.isVisible()
    window._hide_panel_after_title()
    # 测试效果 still shows its two 嘉宾 players: it is a test of what viewers would see.
    window._demo_likes = [Entry("心动小鹿")]
    assert [like.name for like in window._likes_in(CheckResult(True, "", names=names))] == ["心动小鹿"]
    window._demo_likes = None


def test_the_corner_message_says_checked_when_the_blacklist_is_left_out():
    from blacklist_detect.ui_notice import result_messages

    assert result_messages([], [], 0)[0].title == "未发现黑名单"
    assert result_messages([], [], 0, blacklist=False)[0].title == "检查完成"
    assert result_messages([], ["小明"], 1, blacklist=False)[0].title == "检查完成"


def test_a_guest_picks_a_theme_and_the_page_shows_and_orders_them(window):
    from blacklist_detect.ui_likes import LikeDialog

    dialog = LikeDialog(parent=window)
    field = dialog.theme_field
    # A new 嘉宾 is greeted by any scene until they tick some.
    assert dialog.windowTitle() == "添加嘉宾" and field.name.text() == "全部场景 · 随机" and field.value() == Scenes()
    dialog.name_edit.setText("小明")
    _pick_in(field, "cyber")
    assert field.name.text() == "赛博朋克·一" and dialog.has_changes()
    dialog._accept()
    assert dialog.scenes == Scenes(("cyber",))
    assert LikeDialog("小明", allow_delete=True, scenes=Scenes(("cyber",)), parent=window).windowTitle() == "编辑嘉宾"
    page = window.likes_page
    window.store.add_like(dialog.name, scenes=dialog.scenes)
    window.store.add_like("小红")
    window.store.add_like("阿星", scenes=Scenes(("angel",)))
    page.refresh()
    shown = lambda: [(page.table.item(r, 0).text(), page.table.item(r, 2).text()) for r in range(page.table.rowCount())]  # noqa: E731
    assert shown() == [("阿星", "金色传说"), ("小红", "全部随机"), ("小明", "赛博朋克·一")]
    assert page.table.dragEnabled()
    # A row dragged to the top decides first.
    page.table.moved.emit(2, 0)
    assert shown()[0] == ("小明", "赛博朋克·一") and window.store.likes[-1].name == "小明"
    # 置顶 from the row menu does the same.
    page.to_top(window.store.like_index("小红"))
    assert shown()[0][0] == "小红"
    # While searching, rows don't drag.
    page.search.setText("小")
    assert not page.table.dragEnabled()


def _pick_in(field, key: str) -> None:  # noqa: ANN001
    """更换 › on a 场景 row, and 确定 on this scene alone ticked in 选择场景."""
    from blacklist_detect import ui_love_pick

    def choose(picker) -> int:  # noqa: ANN001
        picker.scenes.set_chosen((key,))
        picker.accept()
        return picker.result()

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(ui_love_pick.ScenePicker, "exec", choose)
        field.change_button.click()


def test_a_combination_needs_two_guests_and_greets_them_with_its_theme(window):
    from blacklist_detect.model import Combo
    from blacklist_detect.ui_guests import ComboDialog
    from blacklist_detect.ui_music import ThemeMusic
    from blacklist_detect.ui_overlay import love_look

    store = window.store
    store.add_like("小明", scenes=Scenes(("cyber",)))
    store.add_like("小红")
    editor = ComboDialog(store.likes, parent=window)
    # A new combination starts as a new 嘉宾 does: any scene.
    assert editor.windowTitle() == "添加组合" and editor.theme.value() == Scenes()
    editor.people_buttons["小明"].click()
    editor._accept()
    assert editor.combo is None and editor.people_error.text() == "至少选两位嘉宾"
    editor.people_buttons["小红"].click()
    _pick_in(editor.theme, "equation")
    editor._accept()
    assert editor.combo == Combo(("小明", "小红"), Scenes(("equation",)))
    store.set_combos([editor.combo])
    # Both in the lobby: the combination's 数学 dresses the marks, not 小明's own 赛博.
    names = [
        NameSlot(0, (0, 0, 1, 1), "小明", "小明", False, 0.9, False),
        NameSlot(1, (0, 0, 1, 1), "小红", "小红", False, 0.9, False),
    ]
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    window._live_check = True
    window._on_lobby_placed(button)
    # Quiet: the music a lobby gets plays nowhere here.
    window.music = ThemeMusic(play=lambda _tune: None)
    window._show_panel(CheckResult(True, "", names=names, button_box=button))
    assert window._lobby_choice == "equation" and window.like_card.look == love_look("equation")
    window.love.stop()
    window._hide_panel_after_title()
    window._on_lobby_placed(button)
    # 小明 alone: his own 赛博.
    window._show_panel(CheckResult(True, "", names=names[:1], button_box=button))
    assert window._lobby_choice == "cyber" and window.panel.look == love_look("cyber")
    window.love.stop()
    window._hide_panel_after_title()


def test_editing_a_combination_keeps_a_guest_since_taken_off_the_list(window):
    from blacklist_detect.model import Combo
    from blacklist_detect.ui_guests import ComboDialog

    store = window.store
    store.add_like("小明")
    store.add_like("小红")
    editor = ComboDialog(store.likes, Combo(("小明", "已删掉"), Scenes(("angel",))), parent=window)
    # The one taken off shows, struck out and still ticked, after the 组合's own on the list and before the rest.
    editor.ensurePolished()
    gone = editor.people_buttons["已删掉"]
    assert gone.font().pointSizeF() == editor.people_buttons["小明"].font().pointSizeF()
    assert list(editor.people_buttons) == ["小明", "已删掉", "小红"]
    assert gone.isChecked() and gone.font().strikeOut() and not editor.people_buttons["小明"].font().strikeOut()
    # 保存 keeps them.
    editor._accept()
    assert editor.combo == Combo(("小明", "已删掉"), Scenes(("angel",)))
    # Unticked, they go.
    editor = ComboDialog(store.likes, Combo(("小明", "已删掉"), Scenes(("angel",))), parent=window)
    editor.people_buttons["已删掉"].click()
    editor.people_buttons["小红"].click()
    editor._accept()
    assert editor.combo == Combo(("小明", "小红"), Scenes(("angel",)))


def test_the_picker_returns_the_scene_used_and_closing_changes_nothing(window, monkeypatch):
    from PySide6.QtGui import QColor

    from blacklist_detect import love_scenes
    from blacklist_detect.ui_guests import ThemeField
    from blacklist_detect.ui_love_pick import ScenePicker
    from blacklist_detect.ui_music import TUNES, ThemeMusic
    from blacklist_detect.ui_overlay import love_look

    played: list = []
    picker = ScenePicker("fluffy", "心动小鹿", ThemeMusic(play=played.append), parent=window)
    # Every scene by name, each with a dot in its colour; the current one highlighted and playing.
    assert picker.windowTitle() == "选择场景 · 心动小鹿"
    assert [(key, button.text()) for key, button in picker.buttons.items()] == list(love_scenes.SCENES)
    assert picker.buttons["ice"].dot == QColor(*love_look("ice").glow)
    assert picker.key == "fluffy" and picker.preview.scene == "fluffy" and picker.preview._tick.isActive()
    picker.buttons["stars"].click()
    assert picker.key == "stars" and picker.preview.scene == "stars" and played == [None]
    assert [key for key, button in picker.buttons.items() if button.isChecked()] == ["stars"]
    # ▶ plays it from its start with its music.
    picker.play_button.click()
    assert played[-1] == TUNES["stars"]
    for button in picker.buttons.values():
        button.grab()
    picker.accept()
    assert picker.result() == QDialog.Accepted and picker.key == "stars" and played[-1] is None
    assert not picker.preview._tick.isActive()
    # A scene this version no longer has starts on what replaced it, or 经典.
    assert ScenePicker("champagne").key == "angel" and ScenePicker("ribbon").key == "classic"
    assert ScenePicker().windowTitle() == "选择场景"

    # Closed without 确定: the 场景 row keeps what it had.
    def close(dialog) -> int:  # noqa: ANN001
        dialog.buttons["claw"].click()
        dialog.scenes.set_chosen(("claw",))
        dialog.reject()
        return dialog.result()

    monkeypatch.setattr(ScenePicker, "exec", close)
    field = ThemeField(Scenes(("angel",)), "小明", ThemeMusic(play=played.append))
    field.change_button.click()
    assert field.value() == Scenes(("angel",)) and field.name.text() == "金色传说"
    # ▶ on the row opens 选择场景 on the row's scene, playing with its music.
    seen = []
    monkeypatch.setattr(ScenePicker, "exec", lambda dialog: seen.append((dialog.key, dialog.windowTitle())) or QDialog.Rejected)
    field.play_button.click()
    assert seen == [("angel", "选择场景 · 小明")] and played[-1] == TUNES["angel"]


def _rows(page) -> list[list[str]]:  # noqa: ANN001
    return [[page.table.item(r, c).text() for c in range(5)] for r in range(page.table.rowCount())]


def test_combinations_head_the_list_tagged_and_open_to_edit(window, monkeypatch):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QMenu

    from blacklist_detect.model import Combo
    from blacklist_detect.ui_guests import ComboDialog
    from blacklist_detect.ui_likes import COMBO_ROLE, PEOPLE_ROLE

    page, store = window.likes_page, window.store
    store.add_like("小明", "明哥")
    store.add_like("小红")
    store.add_like("阿星", scenes=Scenes(("cyber",)))
    store.set_combos([Combo(("小明", "小红"), Scenes(("angel",))), Combo(("小红", "阿星"), Scenes(("fluffy",)))])
    page.refresh()
    window._show_list()
    # The tab counts 嘉宾, not 组合.
    assert window._tab_buttons[window.likes_tab].count() == 3
    # Each 组合 on top in its order, its 嘉宾 by 昵称 or name, its 场景; nothing under 昵称 or 原因.
    assert _rows(page) == [
        ["明哥 + 小红", "", "金色传说", "", "—"],
        ["小红 + 阿星", "", "毛茸茸保护协会", "", "—"],
        ["阿星", "", "赛博朋克·一", "", "—"],
        ["小红", "", "全部随机", "", "—"],
        ["小明", "明哥", "全部随机", "", "—"],
    ]
    assert page.table.item(0, 0).data(PEOPLE_ROLE) == [("明哥", True), ("小红", True)]
    assert [page._combo_at(r) for r in range(5)] == [0, 1, -1, -1, -1]
    assert [page._index_at(r) for r in range(5)] == [-1, -1, 2, 1, 0]
    assert page.table.item(1, 3).data(COMBO_ROLE) == 1 and not page.table.grab().isNull()
    changed, said = [], []
    page.changed.connect(lambda: changed.append(1))
    monkeypatch.setattr(page, "_say", lambda text, undo=None: said.append((text, undo)))
    opened = []

    def edit(dialog) -> int:  # noqa: ANN001
        opened.append(dialog)
        _pick_in(dialog.theme, "ice")
        dialog._accept()
        return dialog.result()

    monkeypatch.setattr(ComboDialog, "exec", edit)
    # A click on a 组合 opens it to edit.
    page.table.cellClicked.emit(1, 2)
    assert opened[0].windowTitle() == "编辑组合" and opened[0].theme.name.text() == "冰蓝极光"
    assert {name for name, button in opened[0].people_buttons.items() if button.isChecked()} == {"小红", "阿星"}
    assert store.combos[1] == Combo(("小红", "阿星"), Scenes(("ice",))) and changed
    assert _rows(page)[1][2] == "冰蓝极光"
    # Enter on one does the same.
    page.table.setCurrentCell(0, 0)
    QApplication.sendEvent(page.table, QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Return, Qt.NoModifier))
    assert len(opened) == 2 and opened[1].combo == Combo(("小明", "小红"), Scenes(("ice",)))
    # Its menu has 编辑 and 删除; 删除 offers 撤销.
    menus = []
    monkeypatch.setattr(QMenu, "popup", lambda menu, *_args: menus.append(menu))
    page._row_menu(page.table.visualItemRect(page.table.item(1, 0)).center())
    actions = menus[0].actions()
    assert [action.text() for action in actions] == ["编辑", "", "删除"]
    actions[-1].trigger()
    assert store.combos == [Combo(("小明", "小红"), Scenes(("ice",)))] and said[-1][0] == "已删除组合「小红 + 阿星」"
    said[-1][1]()
    assert store.combos[1] == Combo(("小红", "阿星"), Scenes(("ice",))) and _rows(page)[1][0] == "小红 + 阿星"
    # A 嘉宾's row keeps its own menu.
    page._row_menu(page.table.visualItemRect(page.table.item(3, 0)).center())
    assert [action.text() for action in menus[-1].actions()] == ["编辑", "复制名字", "置顶", "", "删除"]
    # A 嘉宾 since taken off the list shows struck out, and the 组合 stays to edit or delete.
    page.delete(store.like_index("阿星"))
    assert page.table.item(1, 0).data(PEOPLE_ROLE) == [("小红", True), ("阿星", False)] and not page.table.grab().isNull()
    assert window._tab_buttons[window.likes_tab].count() == 2


def test_a_combination_is_searched_by_its_guests_and_never_dragged(window):
    from blacklist_detect.model import Combo

    page, store = window.likes_page, window.store
    store.add_like("小明", "明哥")
    store.add_like("小红")
    store.add_like("阿星", scenes=Scenes(("cyber",)))
    store.set_combos([Combo(("小明", "小红"), Scenes(("angel",))), Combo(("小红", "阿星"), Scenes(("fluffy",)))])
    page.refresh()
    # By a 嘉宾's 昵称 or name.
    page.search.setText("明哥")
    assert [row[0] for row in _rows(page)] == ["明哥 + 小红", "小明"]
    page.search.setText("阿星")
    assert [row[0] for row in _rows(page)] == ["小红 + 阿星", "阿星"] and page.table.fixed == 1
    page.search.setText("")
    # A 组合 neither drags nor takes a drop: rows that aim at one move nothing.
    table = page.table
    assert table.fixed == 2 and table.dragEnabled()
    assert not table.item(0, 0).flags() & Qt.ItemIsDragEnabled and table.item(2, 0).flags() & Qt.ItemIsDragEnabled
    order = [like.name for like in store.likes]
    table.moved.emit(0, 3)
    table.moved.emit(4, 1)
    assert [like.name for like in store.likes] == order
    # 嘉宾 rows still drag among themselves, mapped past the 组合 above them.
    table.moved.emit(4, 2)
    assert [row[0] for row in _rows(page)] == ["明哥 + 小红", "小红 + 阿星", "小明", "阿星", "小红"]
    assert store.likes[-1].name == "小明"


def test_a_combination_shows_when_its_guests_were_last_all_in_one_lobby(window):
    from blacklist_detect.model import Combo
    from blacklist_detect.ui_likes import combos_met
    from blacklist_detect.ui_widgets import NEVER_MET

    page, store = window.likes_page, window.store
    store.add_like("小明")
    store.add_like("小红")
    store.add_like("阿星")
    store.set_combos([Combo(("小明", "小红"), Scenes(("angel",))), Combo(("小红", "阿星"), Scenes(("fluffy",)))])
    lobbies = (("小明", "路人"), ("小明", "小红"), ("小红", "阿星", "路人"))
    ats = [f"2026-10-1{day}T20:00:00+08:00" for day in (4, 3, 2)]
    store.scans = [
        {"at": at, "names": [{"seat": i + 1, "name": name, "unclear": False} for i, name in enumerate(names)]}
        for at, names in zip(ats, lobbies, strict=True)
    ]
    # Records are newest first: 小明 + 小红 met in the second, 小红 + 阿星 in the oldest.
    assert combos_met(store.combos, store.likes, store.scans) == {0: ats[1], 1: ats[2]}
    assert combos_met([Combo(("小明", "阿星"), Scenes(("neon",)))], store.likes, store.scans) == {}
    page.refresh()
    assert all(row[4] != NEVER_MET for row in _rows(page)[:2])


def test_a_combination_has_not_met_where_a_seat_was_another_guest_of_the_same_start(window):
    from blacklist_detect.model import Combo
    from blacklist_detect.ui_likes import combos_met
    from blacklist_detect.ui_widgets import NEVER_MET

    page, store = window.likes_page, window.store
    for name in ("心动星星", "心动星星呀", "心动小鹿"):
        store.add_like(name)
    store.set_combos([Combo(("心动星星呀", "心动小鹿"), Scenes(("angel",)))])
    store.scans = [
        {"at": "2026-10-14T20:00:00+08:00", "names": [{"seat": 1, "name": "心动星星", "unclear": False}, {"seat": 2, "name": "心动小鹿", "unclear": False}]}
    ]
    # The seat is 心动星星 itself, not 心动星星呀 cut short: that lobby never played the 组合's 场景.
    assert combos_met(store.combos, store.likes, store.scans) == {}
    page.refresh()
    assert _rows(page)[0][4] == NEVER_MET
    # A 嘉宾 since taken off the list still counts by name for the 组合 that keeps them.
    store.remove_like(1)
    assert combos_met(store.combos, store.likes, store.scans) == {}
    store.scans[0]["names"][0]["name"] = "心动星星呀"
    assert combos_met(store.combos, store.likes, store.scans) == {0: "2026-10-14T20:00:00+08:00"}


def test_add_offers_a_guest_or_a_combination(window, monkeypatch):
    from PySide6.QtWidgets import QMenu

    from blacklist_detect.model import Combo
    from blacklist_detect.ui_guests import ComboDialog
    from blacklist_detect.ui_likes import TOO_FEW, LikeDialog

    page, store = window.likes_page, window.store
    menus, said, dialogs = [], [], []
    monkeypatch.setattr(QMenu, "popup", lambda menu, *_args: menus.append(menu))
    monkeypatch.setattr(page, "_say", lambda text, undo=None: said.append(text))
    # The empty list's 添加 opens the menu too; with fewer than two 嘉宾 a 组合 waits, and says why.
    assert page.add_button.isHidden() and not page.empty_add_button.isHidden()
    page.empty_add_button.click()
    assert menus == [page.add_menu]
    assert [action.text() for action in page.add_menu.actions()] == ["添加嘉宾", "添加组合"]
    assert not page.add_combo_action.isEnabled() and page.add_combo_action.toolTip() == TOO_FEW
    page.add_combo()
    assert said == [TOO_FEW] and store.combos == []
    monkeypatch.setattr(LikeDialog, "exec", lambda dialog: dialogs.append(dialog) or QDialog.Rejected)
    page.add_like_action.trigger()
    assert dialogs[0].windowTitle() == "添加嘉宾"
    store.add_like("小明")
    store.add_like("小红")
    page.refresh()
    page.add_button.click()
    assert menus[-1] is page.add_menu and page.add_combo_action.isEnabled() and page.add_combo_action.toolTip() != TOO_FEW

    def add(dialog) -> int:  # noqa: ANN001
        dialogs.append(dialog)
        dialog.people_buttons["小明"].click()
        dialog.people_buttons["小红"].click()
        dialog._accept()
        return dialog.result()

    monkeypatch.setattr(ComboDialog, "exec", add)
    page.add_combo_action.trigger()
    assert dialogs[-1].windowTitle() == "添加组合" and store.combos == [Combo(("小明", "小红"), Scenes())]
    assert _rows(page)[0][:3] == ["小明 + 小红", "", "全部随机"]


def test_the_list_is_empty_only_with_no_guest_and_no_combination(window):
    from blacklist_detect.model import Combo

    page, store = window.likes_page, window.store
    store.add_like("小明")
    store.add_like("小红")
    store.set_combos([Combo(("小明", "小红"), Scenes(("angel",)))])
    store.clear_likes()
    page.refresh()
    # Its 嘉宾 gone, the 组合 waits for them, in the list.
    assert page.empty.isHidden() and not page.table.isHidden() and not page.add_button.isHidden()
    assert page.table.item(0, 0).text() == "小明 + 小红"
    # 复制名单 and 清空嘉宾列表 have no 嘉宾 to work on, so 更多 is not offered.
    assert page.more_button.isHidden()
    store.add_like("阿星")
    page.refresh()
    assert not page.more_button.isHidden()
    # A 组合's 嘉宾 run on across 昵称, which it has none of; a 嘉宾's row keeps its own 昵称.
    assert (page.table.columnSpan(0, 0), page.table.columnSpan(1, 0)) == (2, 1)
    store.set_combos([])
    page.refresh()
    assert page.table.columnSpan(0, 0) == 1
    store.set_combos([Combo(("小明", "小红"), Scenes(("angel",)))])
    store.clear_likes()
    store.set_combos([])
    page.refresh()
    assert not page.empty.isHidden() and page.table.isHidden() and not page.empty_add_button.isHidden()


def test_a_theme_with_its_own_music_plays_it(window):
    """Its own sound, whatever 声音 is: ThemeMusic decides how loud, or 静音 none."""
    assert window._tune_for("claw") == "claw"
    assert window._tune_for("stars") == "stars"
    window.mute_box.click()
    assert window._tune_for("claw") == "claw" and window.music.muted
