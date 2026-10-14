"""嘉宾: players worth meeting again, the other side of 黑名单."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QLabel  # noqa: E402

from blacklist_detect.importing import ELSEWHERE, MERGE, plan_import  # noqa: E402
from blacklist_detect.model import Entry  # noqa: E402
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
    rows = [[page.table.item(r, c).text() for c in range(4)] for r in range(page.table.rowCount())]
    # Newest first; 昵称 beside the name; a dash for 最近遇到 until they are met.
    assert rows == [["小红", "", "", "—"], ["救人很稳的小明", "明哥", "上把救了我", "—"]]
    page.search.setText("明哥")
    assert page.table.rowCount() == 1
    page.search.setText("没有这个")
    assert page.table.isHidden() and "没有找到" in page.empty.title.text()


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
    window.store.add_like("小红")
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
    # No 黑名单, 嘉宾 players: a rose ring, a heart badge on the right, their names on the left.
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


def test_two_likes_and_no_hit_play_the_border_once_per_lobby(window):
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
    # One 嘉宾 player: the marks, no border.
    window._show_panel(CheckResult(True, "", names=names[:1], button_box=button))
    assert window.panel.mode == "liked" and not window.love.playing()
    # Two: the border, over the screen, parted around the button and its marks.
    window._show_panel(CheckResult(True, "", names=names, button_box=button))
    assert window.love.playing()
    assert window.love.geometry() == (QApplication.screenAt(window.panel.cover_geometry().center()) or QApplication.primaryScreen()).geometry()
    gap = window.love._gap.translated(window.love.x(), window.love.y())
    assert gap.contains(window.like_card.geometry().toRectF()) and gap.contains(window.panel.cover_geometry().toRectF())
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


def test_the_marks_wear_the_look_of_the_scene_that_greets_them(window):
    from blacklist_detect.ui_overlay import CLASSIC_LOOK, love_look

    window.store.add_like("小明")
    window.store.add_like("小红")
    names = [NameSlot(i, (0, 0, 1, 1), name, name, False, 0.9, False) for i, name in enumerate(("小明", "小红", "坏人"))]
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    window._live_check = True
    marks = (window.panel, window.clear_mark, window.like_card)
    # 随机: the scene is settled before the marks show, and they wear its look.
    window.store.love_scene = "random"
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names[:2], button_box=button))
    assert window.love.playing() and all(mark.look is love_look(window.love.scene) for mark in marks)
    names_ink = window.like_card.findChild(QLabel, "hitName").styleSheet()
    assert love_look(window.love.scene).ink in names_ink
    window._hide_panel_after_title()
    # One 嘉宾 player, so no scene plays: the chosen one's look all the same.
    window.store.love_scene = "ice"
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names[:1], button_box=button))
    assert not window.love.playing() and all(mark.look is love_look("ice") for mark in marks)
    # With a 黑名单 player too, the 嘉宾 half of the ring is the look's.
    hit = Hit(2, "坏人", "坏人", "", False, "", ())
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.panel.mode == "both" and window.panel.look is love_look("ice")
    window._hide_panel_after_title()
    # 无: 经典花边's look.
    window.store.love_scene = "off"
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names[:2], button_box=button))
    assert not window.love.playing() and all(mark.look is CLASSIC_LOOK for mark in marks)
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
