"""心动: players worth meeting again, the other side of 黑名单."""

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
    assert again.entries == [], "心动 is not 黑名单"
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
    # No 标签 on 心动: 炸房 in the note is just words.
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
    # Newest first; 昵称 beside the name.
    assert rows == [["小红", "", "", ""], ["救人很稳的小明", "明哥", "上把救了我", ""]]
    page.search.setText("明哥")
    assert page.table.rowCount() == 1
    page.search.setText("没有这个")
    assert page.table.isHidden() and "没有找到" in page.empty.title.text()


def test_adding_a_blacklisted_name_asks_to_move_it(window, monkeypatch):
    from blacklist_detect import ui_likes

    window.store.add("小明", reason="炸房")
    asked: list[str] = []
    monkeypatch.setattr(ui_likes.ConfirmDialog, "ask", staticmethod(lambda _p, _t, text, *_a, **_k: asked.append(text) or True))

    class Picked:
        def __init__(self, *_args, **_kwargs) -> None:
            self.name, self.nickname, self.detail, self.deleted = "小明", "明哥", "其实还行", False

        def exec(self) -> int:
            return QDialog.Accepted

    monkeypatch.setattr(ui_likes, "LikeDialog", Picked)
    said: list[tuple[str, object]] = []
    window.likes_page._say = lambda text, undo=None: said.append((text, undo))
    window.likes_page.add_one()
    assert asked == ["「小明」在黑名单中，要移到心动列表吗？"]
    assert window.store.entries == [] and [e.name for e in window.store.likes] == ["小明"]
    assert said[0][0] == "已将「明哥」加入心动列表"
    # 撤销 puts both lists back.
    said[0][1]()
    assert [e.name for e in window.store.entries] == ["小明"] and window.store.likes == []


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
    assert "匹配心动「救人很稳的小明」" in item.toolTip()
    # A seat no one listed offers both lists.
    assert [a.text() for a in window._seat_menu(0, 1).actions() if a.text()] == ["加入黑名单", "加入心动列表", "复制名字"]
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
    # No 黑名单, 心动 players: a rose ring, a heart badge on the right, their names on the left.
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
    # A blacklisted player alone: the red ring, and no 心动 card.
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
    # One 心动 player: the marks, no border.
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


def test_the_border_ends_by_itself(window, monkeypatch):
    from blacklist_detect.ui_love import DURATION

    window.love.play(QApplication.primaryScreen().geometry(), QRect(500, 700, 300, 80))
    assert window.love.isVisible() and window.love.playing()
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
