"""嘉宾: players worth meeting again, the other side of 黑名单."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QLabel  # noqa: E402

from blacklist_detect.importing import plan_import  # noqa: E402
from blacklist_detect.model import Scenes  # noqa: E402
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


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect.ui import MainWindow

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    made = MainWindow()
    # The marks over the game, as before 基础模式: 完整模式 and 自动检查, agreed to once.
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
    # The 我 row on top; then newest first; 昵称 beside the name; 随机 under 场景 for any scene; a
    # dash for 最近遇到 until they are met.
    assert rows == [
        ["点右上角填写游戏名", "", "", "", ""],
        ["小红", "", "随机", "", "—"],
        ["救人很稳的小明", "明哥", "随机", "上把救了我", "—"],
    ]
    page.search.setText("明哥")
    assert page.table.rowCount() == 1
    page.search.setText("没有这个")
    assert page.table.isHidden() and "没有找到" in page.empty.title.text()


def test_scene_manager_opens_from_beside_the_search_and_from_the_empty_list(window):
    """场景管理 is no tab: it opens from the 嘉宾 page, right of the search, or beside 添加 while the list is
    empty, whose toolbar is hidden then. A search that finds nobody keeps it beside the search."""
    page, dialog = window.likes_page, window.scenes_dialog
    window.show()
    window._show_likes_page()
    QApplication.processEvents()
    assert page.empty_scenes_button.isVisible() and not page.scenes_button.isVisible()
    page.empty_scenes_button.click()
    QApplication.processEvents()
    assert dialog.isVisible() and window.effects_page.preview.is_still
    dialog.reject()
    window.store.add_like("心动小鹿")
    page.refresh()
    QApplication.processEvents()
    assert page.scenes_button.isVisible() and not page.empty_scenes_button.isVisible()
    search, button = page.search.geometry(), page.scenes_button.geometry()
    assert 0 < button.left() - search.right() <= 16 and button.center().y() == search.center().y()
    page.search.setText("没有这个")
    assert page.scenes_button.isVisible() and not page.empty_scenes_button.isVisible()
    page.scenes_button.click()
    assert dialog.isVisible() and window.tabs.currentIndex() == window.likes_tab
    dialog.reject()
    window.hide()


def test_the_effect_column_shows_every_scene_name_whole(window):
    from PySide6.QtGui import QFontMetrics

    from blacklist_detect import love_scenes
    from blacklist_detect.ui_likes import DOTS_WIDE, THEME_COLUMN, _dots_wide
    from blacklist_detect.ui_love_pick import SceneChoice
    from blacklist_detect.ui_theme import chinese_font

    # 毛茸茸保护协会, the longest, after its dot, with the cell's padding on both sides; and a few dots side
    # by side before N个场景.
    metrics = QFontMetrics(chinese_font())
    longest = max(metrics.horizontalAdvance(name) for _key, name in love_scenes.SCENES)
    width = window.likes_page.table.columnWidth(THEME_COLUMN)
    assert width >= _dots_wide(1) + longest + 2 * 12
    assert width >= _dots_wide(DOTS_WIDE) + metrics.horizontalAdvance(f"{len(love_scenes.SCENES)}个场景") + 2 * 12
    # Every scene ticked: all their dots as close as they go (half over one another) and 11个场景 whole.
    every = len(love_scenes.SCENES)
    assert width >= (every - 1) * SceneChoice.DOT + _dots_wide(1) + metrics.horizontalAdvance(f"{every}个场景") + 2 * 12


def _scenes_cells(page):  # noqa: ANN001, ANN202
    """The 我 row on its own 场景, 心动小鹿 on 竖琴清风, 心动星星 on 随机, 阿星 on three, 示例坏人 and a 组合
    on 不放, and 我 on 不放 too when me_off."""
    from blacklist_detect.model import Combo

    store = page.store
    store.add_like("示例坏人", scenes=Scenes())
    store.add_like("阿星", scenes=Scenes(("ice", "fluffy", "claw")))
    store.add_like("心动星星", scenes=Scenes(random=True))
    store.add_like("心动小鹿", scenes=Scenes(("lyre",)))
    store.set_combos([Combo(("心动小鹿", "心动星星"), Scenes())])
    page.refresh()


def test_a_row_on_no_scene_shows_nothing_under_scene(window):
    """不放: the 嘉宾's, the 组合's and 我's 场景 cell is empty, no words and no dot."""
    from blacklist_detect.ui_likes import SCENES_ROLE, THEME_COLUMN

    page, table = window.likes_page, window.likes_page.table
    _scenes_cells(page)
    table.resize(900, 400)
    picture = _picture(table)
    # 我, the 组合, then 示例坏人 at the foot.
    for row in (0, 1, table.rowCount() - 1):
        item = table.item(row, THEME_COLUMN)
        assert item.text() == "" and not item.data(SCENES_ROLE) and not item.toolTip()
        cell = table.visualItemRect(item)
        ground = picture.pixelColor(cell.left() + 1, cell.top() + 2)
        # Above the row's divider, the cell is its ground all over.
        assert all(
            picture.pixelColor(x, y) == ground for x in range(cell.left(), cell.right()) for y in range(cell.top(), cell.bottom() - 2)
        ), row


def test_the_scene_cell_has_each_scene_s_dot_before_its_words(window):
    """One 场景: its dot and its name; 随机: 随机's dot; several: each one's dot side by side, then N个场景, their
    names in the tooltip. The dots are painted in scene_dot's colour, left of the words."""
    from blacklist_detect.ui_likes import SCENES_ROLE, THEME_COLUMN
    from blacklist_detect.ui_love_pick import SceneChoice, scene_dot

    page, store, table = window.likes_page, window.store, window.likes_page.table
    _scenes_cells(page)
    store.set_me(Scenes(("angel",)))
    page.refresh()
    said = {table.item(row, 0).text(): table.item(row, THEME_COLUMN) for row in range(table.rowCount())}
    assert [(said[name].text(), list(said[name].data(SCENES_ROLE))) for name in ("心动小鹿", "心动星星", "阿星")] == [
        ("竖琴清风", ["lyre"]),
        ("随机", ["random"]),
        ("3个场景", ["ice", "fluffy", "claw"]),
    ]
    assert said["阿星"].toolTip() == "冰蓝极光、毛茸茸保护协会、演说家遇袭" and not said["心动小鹿"].toolTip()
    assert table.item(0, THEME_COLUMN).text() == "金色传说" and list(table.item(0, THEME_COLUMN).data(SCENES_ROLE)) == ["angel"]
    table.resize(900, 400)
    picture = _picture(table)

    def near(color, want) -> bool:  # noqa: ANN001
        return max(abs(color.red() - want.red()), abs(color.green() - want.green()), abs(color.blue() - want.blue())) <= 12

    for name, keys in (("心动小鹿", ["lyre"]), ("心动星星", ["random"]), ("阿星", ["ice", "fluffy", "claw"]), (table.item(0, 0).text(), ["angel"])):
        cell = table.visualItemRect(said[name])
        y = cell.top() + cell.height() // 2
        ground = picture.pixelColor(cell.left() + 1, y)
        spans = []
        for key in keys:
            xs = [x for x in range(cell.left(), cell.right()) if near(picture.pixelColor(x, y), scene_dot(key))]
            # The dot's run, not a pixel of the words' tinted edge that happens to be near its colour.
            xs = [x for number, x in enumerate(xs) if x == xs[0] + number]
            # As wide as the 场景 lists' dot, and centred on the row as they are.
            assert 2 * SceneChoice.DOT - 3 <= len(xs) <= 2 * SceneChoice.DOT + 1, (name, key, len(xs))
            middle = (min(xs) + max(xs)) // 2
            column = [y2 for y2 in range(cell.top(), cell.bottom()) if near(picture.pixelColor(middle, y2), scene_dot(key))]
            assert abs((min(column) + max(column)) / 2 - (cell.top() + cell.height() / 2)) <= 1.5, (name, key)
            spans.append((min(xs), max(xs)))
        # Side by side in the order ticked, from near the cell's left.
        assert spans == sorted(spans) and spans[0][0] - cell.left() < 16, name
        # Nothing before the first dot; the words after the last.
        assert all(picture.pixelColor(x, y2) == ground for x in range(cell.left(), spans[0][0] - 1) for y2 in range(y - 8, y + 8))
        words = [x for x in range(spans[-1][1] + 2, cell.right()) for y2 in range(y - 8, y + 8) if picture.pixelColor(x, y2) != ground]
        assert words and min(words) > spans[-1][1] + 4, name


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
    # A 黑名单 player leaves it playing, over the red glow; leaving the lobby lets the next one play it.
    window._hide_panel_after_title()
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names, button_box=button))
    assert window.love.playing()
    hit = Hit(2, "坏人", "坏人", "", False, "", ())
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.love.playing() and window.panel.mode == "both" and window.alert.isVisible()
    window._hide_panel_after_title()
    assert not window.love.playing()


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
    # Both on 不放: no scene, 小明's own neither, and 经典's look.
    for index, like in enumerate(window.store.likes):
        window.store.update_like(index, like.name, scenes=Scenes())
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


def test_every_check_tells_about_both_lists(window):
    """提醒 is gone from the 检查 panel: a check always tells about 黑名单 and 嘉宾 players, also when an
    older version saved either left out."""
    import json

    settings = json.loads(window.store.settings_path.read_text(encoding="utf-8"))
    window.store.settings_path.write_text(json.dumps({**settings, "check_blacklist": False, "check_likes": False}), encoding="utf-8")
    window.store = Store(window.store.root)
    # Read back in 完整模式 (safe_mode is 基础模式), so the cards show on the game.
    assert window.store.safe_mode is False
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
    assert not hasattr(window, "remind_boxes") and not hasattr(window.store, "check_blacklist")
    assert "提醒" not in window.settings_line()
    assert not [label for label in window.check_panel.findChildren(QLabel) if label.text() == "提醒"]
    window._live_check = True
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.panel.mode == "both" and window.hit_card.isVisible() and window.like_card.isVisible()
    window._hide_panel_after_title()
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names[:1], button_box=button))
    assert window.panel.mode == "liked" and window.like_card.isVisible()
    window._hide_panel_after_title()
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names[1:], button_box=button))
    assert window.panel.mode == "clear" and window.panel.toolTip() == "未发现黑名单"
    window._hide_panel_after_title()
    # Saved again, the old keys are gone.
    window.store.save_settings()
    saved = window.store.settings_path.read_text(encoding="utf-8")
    assert "check_blacklist" not in saved and "check_likes" not in saved


def test_the_corner_message_says_no_blacklist_when_none_is_there():
    from blacklist_detect.ui_notice import result_messages

    assert result_messages([], [], 0)[0].title == "未发现黑名单"
    assert result_messages([], ["小明"], 1)[0].title == "未发现黑名单"


def test_a_guest_picks_a_theme_and_the_page_shows_and_orders_them(window, monkeypatch):
    from blacklist_detect.ui_likes import LikeDialog

    dialog = LikeDialog(parent=window)
    dialog.name_edit.setText("小明")
    assert dialog.windowTitle() == "添加嘉宾" and dialog.has_changes()
    assert LikeDialog("小明", allow_delete=True, parent=window).windowTitle() == "编辑嘉宾"
    page = window.likes_page
    # A new 嘉宾 starts on 不放 (播放场景 off); 编辑嘉宾 ticks theirs beside the name.
    monkeypatch.setattr(LikeDialog, "exec", lambda dialog: dialog.name_edit.setText("小明") or dialog._accept() or dialog.result())
    page.add_one()
    assert window.store.likes[0].name == "小明" and window.store.likes[0].scenes == Scenes()
    seen: list = []
    monkeypatch.setattr(LikeDialog, "exec", _tick(seen, "cyber"))
    page.edit(0)
    assert seen[0].windowTitle() == "编辑嘉宾" and window.store.likes[0].scenes == Scenes(("cyber",))
    assert window.store.likes[0].name == "小明"
    window.store.add_like("小红")
    window.store.add_like("阿星", scenes=Scenes(("angel",)))
    window.store.player_name = "测试主播"
    page.refresh()
    shown = lambda: [(page.table.item(r, 0).text(), page.table.item(r, 2).text()) for r in range(1, page.table.rowCount())]  # noqa: E731
    assert shown() == [("阿星", "金色传说"), ("小红", "随机"), ("小明", "赛博朋克（一）")]
    assert page.table.dragEnabled() and page.table.fixed == 1
    # A row dragged to the top decides first, under the 我 row, which stays where it is.
    page.table.moved.emit(3, 1)
    assert shown()[0] == ("小明", "赛博朋克（一）") and window.store.likes[-1].name == "小明"
    page._moved(1, 0)
    page._moved(0, 2)
    assert page.table.item(0, 0).text() == "测试主播" and window.store.likes[-1].name == "小明"
    # 置顶 from the row menu does the same.
    page.to_top(window.store.like_index("小红"))
    assert shown()[0][0] == "小红"
    # While searching, rows don't drag.
    page.search.setText("小")
    assert not page.table.dragEnabled()


def _tick(seen: list, *keys: str):  # noqa: ANN202
    """The exec of a dialog with its 场景 beside it (编辑嘉宾, 编辑组合, 我的场景): 播放场景 on with these scenes
    alone ticked, then 保存."""

    def answer(dialog) -> int:  # noqa: ANN001
        seen.append(dialog)
        dialog.pane.play_box.setChecked(True)
        dialog.pane.scenes.set_chosen(keys)
        dialog._accept()
        return dialog.result()

    return answer


def test_a_combination_needs_two_guests_and_greets_them_with_its_theme(window):
    from blacklist_detect.model import Combo
    from blacklist_detect.ui_guests import ComboDialog
    from blacklist_detect.ui_music import ThemeMusic
    from blacklist_detect.ui_overlay import love_look

    store = window.store
    store.add_like("小明", scenes=Scenes(("cyber",)))
    store.add_like("小红")
    editor = ComboDialog(store.likes, parent=window)
    assert editor.windowTitle() == "添加组合"
    editor.people_buttons["小明"].click()
    editor._accept()
    assert editor.combo is None and editor.people_error.text() == "至少选两位嘉宾"
    editor.people_buttons["小红"].click()
    editor._accept()
    # A new combination starts as a new 嘉宾 does: no scene; 播放场景 ticks it on.
    assert editor.combo == Combo(("小明", "小红"), Scenes())
    store.set_combos([Combo(editor.combo.names, Scenes(("equation",)))])
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


def _rows(page) -> list[list[str]]:  # noqa: ANN001
    """The rows under the 我 row."""
    start = int(page._is_me(0))
    return [[page.table.item(r, c).text() for c in range(5)] for r in range(start, page.table.rowCount())]


def test_combinations_head_the_list_tagged_and_open_to_edit(window, monkeypatch):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QMenu

    from blacklist_detect.model import Combo
    from blacklist_detect.ui_guests import ComboDialog
    from blacklist_detect.ui_likes import COMBO_ROLE, PEOPLE_ROLE, LikeDialog

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
        ["阿星", "", "赛博朋克（一）", "", "—"],
        ["小红", "", "随机", "", "—"],
        ["小明", "明哥", "随机", "", "—"],
    ]
    # Under the 我 row.
    assert page._is_me(0) and not any(page._is_me(r) for r in range(1, 6))
    assert page.table.item(1, 0).data(PEOPLE_ROLE) == [("明哥", True), ("小红", True)]
    assert [page._combo_at(r) for r in range(6)] == [-1, 0, 1, -1, -1, -1]
    assert [page._index_at(r) for r in range(6)] == [-1, -1, -1, 2, 1, 0]
    assert page.table.item(2, 3).data(COMBO_ROLE) == 1 and not page.table.grab().isNull()
    changed, said = [], []
    page.changed.connect(lambda: changed.append(1))
    monkeypatch.setattr(page, "_say", lambda text, undo=None: said.append((text, undo)))
    opened = []

    def edit(dialog) -> int:  # noqa: ANN001
        opened.append(dialog)
        dialog._accept()
        return dialog.result()

    monkeypatch.setattr(ComboDialog, "exec", edit)
    # A click on a 组合 opens it to edit.
    page.table.cellClicked.emit(2, 0)
    assert opened[0].windowTitle() == "编辑组合"
    assert {name for name, button in opened[0].people_buttons.items() if button.isChecked()} == {"小红", "阿星"}
    assert store.combos[1] == Combo(("小红", "阿星"), Scenes(("fluffy",))) and changed
    # Its 场景 cell opens 编辑组合 too, its 场景 there beside its 嘉宾.
    monkeypatch.setattr(ComboDialog, "exec", _tick(opened, "ice"))
    page.table.cellClicked.emit(2, 2)
    assert len(opened) == 2 and opened[1].windowTitle() == "编辑组合"
    assert store.combos[1] == Combo(("小红", "阿星"), Scenes(("ice",))) and _rows(page)[1][2] == "冰蓝极光"
    monkeypatch.setattr(ComboDialog, "exec", edit)
    # Enter on one opens 编辑组合.
    page.table.setCurrentCell(1, 0)
    QApplication.sendEvent(page.table, QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Return, Qt.NoModifier))
    assert len(opened) == 3 and opened[2].combo == Combo(("小明", "小红"), Scenes(("angel",)))
    # Its menu has 编辑 and 删除; 删除 offers 撤销.
    menus = []
    monkeypatch.setattr(QMenu, "popup", lambda menu, *_args: menus.append(menu))
    page._row_menu(page.table.visualItemRect(page.table.item(2, 0)).center())
    actions = menus[0].actions()
    assert [action.text() for action in actions] == ["编辑", "", "删除"]
    actions[0].trigger()
    assert len(opened) == 4 and opened[3].combo == Combo(("小红", "阿星"), Scenes(("ice",)))
    actions[-1].trigger()
    assert store.combos == [Combo(("小明", "小红"), Scenes(("angel",)))] and said[-1][0] == "已删除组合「小红 + 阿星」"
    said[-1][1]()
    assert store.combos[1] == Combo(("小红", "阿星"), Scenes(("ice",))) and _rows(page)[1][0] == "小红 + 阿星"
    # A 嘉宾's row keeps its own menu; its 场景 cell opens 编辑嘉宾 as its other cells do.
    page._row_menu(page.table.visualItemRect(page.table.item(4, 0)).center())
    assert [action.text() for action in menus[-1].actions()] == ["编辑", "复制名字", "置顶", "", "删除"]
    seen: list = []
    monkeypatch.setattr(LikeDialog, "exec", _tick(seen, "ice"))
    menus[-1].actions()[0].trigger()
    page.table.cellClicked.emit(3, 2)
    assert [dialog.windowTitle() for dialog in seen] == ["编辑嘉宾"] * 2 and seen[1].name == "阿星"
    assert store.likes[store.like_index("小红")].scenes == Scenes(("ice",)) == store.likes[store.like_index("阿星")].scenes
    # A 嘉宾 since taken off the list shows struck out, and the 组合 stays to edit or delete.
    page.delete(store.like_index("阿星"))
    assert page.table.item(2, 0).data(PEOPLE_ROLE) == [("小红", True), ("阿星", False)] and not page.table.grab().isNull()
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
    # The 我 row and a 组合 neither drag nor take a drop: rows that aim at one move nothing.
    table = page.table
    assert table.fixed == 3 and table.dragEnabled()
    assert not any(table.item(row, 0).flags() & Qt.ItemIsDragEnabled for row in (0, 1)) and table.item(3, 0).flags() & Qt.ItemIsDragEnabled
    order = [like.name for like in store.likes]
    for row, to in ((0, 4), (1, 4), (5, 2), (5, 0)):
        table.moved.emit(row, to)
    assert [like.name for like in store.likes] == order
    # 嘉宾 rows still drag among themselves, mapped past the 我 row and the 组合 above them.
    table.moved.emit(5, 3)
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


def test_the_toolbar_adds_a_guest_or_a_combination(window, monkeypatch):
    from blacklist_detect.model import Combo
    from blacklist_detect.ui_guests import ComboDialog
    from blacklist_detect.ui_likes import TOO_FEW, LikeDialog

    page, store = window.likes_page, window.store
    said, dialogs = [], []
    monkeypatch.setattr(page, "_say", lambda text, undo=None: said.append(text))
    monkeypatch.setattr(LikeDialog, "exec", lambda dialog: dialogs.append(dialog) or QDialog.Rejected)
    # The empty list offers 添加嘉宾 alone: with no 嘉宾 there is no 组合 to make.
    assert page.add_like_button.isHidden() and page.add_combo_button.isHidden() and not page.empty_add_button.isHidden()
    assert page.empty_add_button.text() == "添加嘉宾"
    page.empty_add_button.click()
    assert [dialog.windowTitle() for dialog in dialogs] == ["添加嘉宾"]
    # One 嘉宾: both buttons, 添加嘉宾 the primary; 添加组合 waits for a second 嘉宾, and says why.
    store.add_like("小明")
    page.refresh()
    assert page.empty_add_button.isHidden() and not page.add_like_button.isHidden() and not page.add_combo_button.isHidden()
    assert (page.add_like_button.text(), page.add_combo_button.text()) == ("添加嘉宾", "添加组合")
    assert page.add_like_button.objectName() == "primary" and page.add_combo_button.objectName() != "primary"
    assert not page.add_combo_button.isEnabled() and page.add_combo_button.toolTip() == TOO_FEW
    page.add_combo()
    assert said == [TOO_FEW] and store.combos == []
    page.add_like_button.click()
    assert [dialog.windowTitle() for dialog in dialogs] == ["添加嘉宾", "添加嘉宾"]
    store.add_like("小红")
    page.refresh()
    assert page.add_combo_button.isEnabled() and page.add_combo_button.toolTip() == ""

    def add(dialog) -> int:  # noqa: ANN001
        dialogs.append(dialog)
        dialog.people_buttons["小明"].click()
        dialog.people_buttons["小红"].click()
        dialog._accept()
        return dialog.result()

    monkeypatch.setattr(ComboDialog, "exec", add)
    page.add_combo_button.click()
    assert dialogs[-1].windowTitle() == "添加组合" and store.combos == [Combo(("小明", "小红"), Scenes())]
    assert _rows(page)[0][:3] == ["小明 + 小红", "", ""]
    # 场景管理 stays beside the search.
    assert page.scenes_button in page.toolbar_buttons


def test_the_list_is_empty_only_with_no_guest_and_no_combination(window):
    from blacklist_detect.model import Combo

    page, store = window.likes_page, window.store
    store.add_like("小明")
    store.add_like("小红")
    store.set_combos([Combo(("小明", "小红"), Scenes(("angel",)))])
    store.clear_likes()
    page.refresh()
    # Its 嘉宾 gone, the 组合 waits for them, in the list.
    assert page.empty.isHidden() and not page.table.isHidden() and not page.add_like_button.isHidden()
    assert page.table.item(1, 0).text() == "小明 + 小红"
    # 复制名单 and 清空嘉宾列表 have no 嘉宾 to work on, so 更多 is not offered.
    assert page.more_button.isHidden()
    store.add_like("阿星")
    page.refresh()
    assert not page.more_button.isHidden()
    # The 我 row's name and a 组合's 嘉宾 run on across 昵称, which they have none of; a 嘉宾's row keeps its own 昵称.
    assert [page.table.columnSpan(row, 0) for row in range(3)] == [2, 2, 1]
    store.set_combos([])
    page.refresh()
    assert page.table.columnSpan(1, 0) == 1
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


def _picture(table):  # noqa: ANN001, ANN202
    """The list as drawn, one pixel per pixel of its viewport whatever the screen's scale."""
    return table.viewport().grab().toImage().scaled(table.viewport().size())


def test_the_me_row_heads_the_list_in_green_with_the_players_name(window, monkeypatch):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QMenu

    from blacklist_detect.model import Combo
    from blacklist_detect.ui_guests import ComboDialog
    from blacklist_detect.ui_kit import ConfirmDialog
    from blacklist_detect.ui_likes import ME_ROLE, MET, NAME, NO_NAME, REASON, THEME_COLUMN, LikeDialog
    from blacklist_detect.ui_theme import THEME

    page, store, table = window.likes_page, window.store, window.likes_page.table
    store.add_like("小明", "明哥", "救人很稳")
    store.add_like("小红")
    store.set_combos([Combo(("小明", "小红"), Scenes(("angel",)))])
    page.refresh()
    window._show_list()
    # On top, above the 组合: where to fill in the name until there is one, and 我's own 场景.
    assert page._is_me(0) and table.item(0, NAME).data(ME_ROLE) == ""
    assert [table.item(0, column).text() for column in range(5)] == [NO_NAME, "", "", "", ""]
    assert page._combo_at(1) == 0 and page._index_at(0) == -1 and page._combo_at(0) == -1
    # The header's name, saved, is the row's.
    window.player_edit.setText("测试主播")
    window._save_player_name()
    assert table.item(0, NAME).text() == "测试主播" and table.item(0, NAME).data(ME_ROLE) == "测试主播"
    store.set_me(Scenes(("cyber",)))
    page.refresh()
    assert table.item(0, THEME_COLUMN).text() == "赛博朋克（一）"
    # It neither drags nor takes a drop, and is not one of the 嘉宾 the tab counts or 复制名单 copies.
    assert not table.item(0, NAME).flags() & (Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled) and table.fixed == 2
    assert window._tab_buttons[window.likes_tab].count() == 2
    page.copy_list()
    assert "测试主播" not in QApplication.clipboard().text()
    # Green, all across; the 组合 under it on the card.
    table.resize(900, 400)
    picture = _picture(table)

    def at(row: int, column: int) -> str:
        # Near the cell's left edge: in the test's window the table can be narrower than its columns.
        cell = table.visualItemRect(table.item(row, column))
        return picture.pixelColor(cell.left() + 6, cell.center().y()).name()

    assert at(0, MET) == at(0, REASON) == THEME["green_wash"]
    assert at(1, REASON) == THEME["surface"]
    # A click on any cell or Enter on it opens 我的场景 (edit_me), never 编辑嘉宾 or 编辑组合; Delete deletes
    # nothing, and its menu has 编辑 alone.
    opened, asked, menus = [], [], []
    monkeypatch.setattr(LikeDialog, "exec", lambda dialog: opened.append(dialog) or QDialog.Rejected)
    monkeypatch.setattr(ComboDialog, "exec", lambda dialog: opened.append(dialog) or QDialog.Rejected)
    monkeypatch.setattr(page, "edit_me", lambda: asked.append(1))
    monkeypatch.setattr(QMenu, "popup", lambda menu, *_args: menus.append(menu))
    table.cellClicked.emit(0, NAME)
    table.cellClicked.emit(0, THEME_COLUMN)
    table.setCurrentCell(0, NAME)
    for key in (Qt.Key_Return, Qt.Key_Delete):
        QApplication.sendEvent(table, QKeyEvent(QEvent.Type.KeyPress, key, Qt.NoModifier))
    page._row_menu(table.visualItemRect(table.item(0, NAME)).center())
    assert [action.text() for action in menus[0].actions()] == ["编辑"]
    menus[0].actions()[0].trigger()
    assert opened == [] and asked == [1, 1, 1, 1]
    assert len(store.likes) == 2 and len(store.combos) == 1
    # Searched for: there while the search is in the player's name.
    page.search.setText("主播")
    assert page._is_me(0) and table.rowCount() == 1 and not table.isHidden()
    page.search.setText("明哥")
    assert not page._is_me(0) and [row[0] for row in _rows(page)] == ["明哥 + 小红", "小明"]
    page.search.setText("")
    # 清空嘉宾列表 leaves it and its 场景; with nobody on the list the page is empty again.
    monkeypatch.setattr(ConfirmDialog, "ask", lambda *_args, **_kwargs: True)
    page.clear()
    assert page._is_me(0) and store.me == Scenes(("cyber",))
    store.set_combos([])
    page.refresh()
    assert table.isHidden() and not page.empty.isHidden()


def test_a_combinations_tag_is_blue_and_the_me_tag_green(window):
    from PySide6.QtGui import QColor, QImage, QPainter

    from blacklist_detect.model import Combo
    from blacklist_detect.ui_theme import THEME
    from blacklist_detect.ui_widgets import _draw_pill

    # A pill in the ink it is given; red without one.
    for ink, wanted in (("#0000ff", "#0000ff"), ("", THEME["red"])):
        picture = QImage(120, 40, QImage.Format_RGB32)
        picture.fill(QColor("#ffffff"))
        painter = QPainter(picture)
        painter.setFont(window.font())
        _draw_pill(painter, QRect(0, 0, 120, 40), "组合组合组合", True, 8, "#ffffff", ink)
        painter.end()
        colors = {picture.pixelColor(x, y).name() for x in range(120) for y in range(40)}
        assert wanted in colors, ink

    def inks(row: int) -> set[str]:
        rect = page.table.visualItemRect(page.table.item(row, 0))
        picture = _picture(page.table)
        return {picture.pixelColor(x, y).name() for x in range(rect.left(), rect.left() + 80) for y in range(rect.top(), rect.bottom())}

    page, store = window.likes_page, window.store
    store.add_like("小明")
    store.add_like("小红")
    store.set_combos([Combo(("小明", "小红"), Scenes(("angel",)))])
    page.refresh()
    window._show_list()
    page.table.resize(900, 400)
    assert {THEME["blue_wash"], THEME["blue"]} <= inks(1) and THEME["red"] not in inks(1)
    # The 我 tag, a chip of the card's color on the row's green.
    assert {THEME["green_wash"], THEME["surface"], THEME["green"]} <= inks(0) and THEME["blue"] not in inks(0)


def test_batch_import_is_on_the_blacklist_page_only(window):
    from PySide6.QtWidgets import QPushButton

    from blacklist_detect.ui_dialogs import BatchAddDialog

    page = window.likes_page
    assert not any(button.text() == "批量导入" for button in page.findChildren(QPushButton))
    assert not hasattr(page, "import_many") and not hasattr(window.store, "import_likes")
    assert window.toolbar_buttons[0].text() == "批量导入" and window.empty_batch_button.text() == "批量导入"
    with pytest.raises(TypeError):
        BatchAddDialog(likes=True)


def test_a_combination_with_the_same_guests_as_another_cannot_be_saved(window, monkeypatch):
    from blacklist_detect.model import Combo
    from blacklist_detect.ui_guests import ComboDialog

    page, store = window.likes_page, window.store
    store.add_like("小明")
    store.add_like("小红")
    store.add_like("阿星")
    store.set_combos([Combo(("小明", "小红"), Scenes(("angel",)))])
    page.refresh()
    opened, members = [], {"names": ("小红", "小明")}

    def pick(dialog) -> int:  # noqa: ANN001
        opened.append(dialog)
        for name, button in dialog.people_buttons.items():
            button.setChecked(name in members["names"])
        dialog._accept()
        return dialog.result()

    monkeypatch.setattr(ComboDialog, "exec", pick)
    # 小红 + 小明 is 小明 + 小红 already: refused, with why.
    page.add_combo()
    assert opened[-1].combo is None and opened[-1].people_error.text() == "已有这几位嘉宾的组合"
    assert store.combos == [Combo(("小明", "小红"), Scenes(("angel",)))]
    # Another three are fine.
    members["names"] = ("小红", "阿星")
    page.add_combo()
    assert len(store.combos) == 2
    # Edited, a 组合 keeps its own 嘉宾; it cannot take the other's.
    members["names"] = ("小明", "小红")
    page.edit_combo(0)
    assert opened[-1].result() == QDialog.Accepted and store.combos[0].names == ("小明", "小红")
    page.edit_combo(1)
    assert opened[-1].people_error.text() == "已有这几位嘉宾的组合" and store.combos[1].names == ("小红", "阿星")
