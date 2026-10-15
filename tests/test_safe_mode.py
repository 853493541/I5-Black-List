"""安全模式: a check on the hotkey, nothing marked on the game, the result in messages at the bottom right."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect.pipeline import CheckResult, Hit, NameSlot  # noqa: E402
from blacklist_detect.ui_notice import Message, result_messages  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    made = MainWindow()
    made._watch_timer.stop()
    made.store.disclaimer_accepted = True
    yield made
    made.notice.hide()
    made.close()


def _lobby():  # noqa: ANN202
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    names = [
        NameSlot(0, (0, 0, 1, 1), "坏人", "坏人", False, 0.9, False),
        NameSlot(1, (0, 0, 1, 1), "小红", "小红", False, 0.9, False),
        NameSlot(2, (0, 0, 1, 1), "", "", False, 0.2, True),
    ]
    return button, names


def _arrive(notice) -> None:  # noqa: ANN001
    """Let the second message come in now, not a moment later."""
    if notice._next.isActive():
        notice._next.stop()
        notice._enter_next()


def _marks(window) -> list[str]:  # noqa: ANN001
    marks = {
        "panel": window.panel,
        "hit_card": window.hit_card,
        "like_card": window.like_card,
        "clear_mark": window.clear_mark,
    }
    shown = [name for name, mark in marks.items() if mark.isVisible()]
    if window.alert.showing():
        shown.append("alert")
    return shown


def test_the_words_for_each_result():
    """黑名单 and 嘉宾 are two messages: what was found at the bottom, 嘉宾 on its own card above."""
    assert result_messages([("坏人", ("炸房", "挂机")), ("乙", ())], ["小红"], 1) == [
        Message("hit", "2 名黑名单", "1 人未识别", (("坏人", ("炸房", "挂机")), ("乙", ()))),
        Message("liked", "嘉宾", "", (("小红", ()),)),
    ]
    assert result_messages([], [], 0) == [Message("clear", "未发现黑名单")]
    assert result_messages([], ["小红", "小明"], 0) == [
        Message("clear", "未发现黑名单"),
        Message("liked", "嘉宾", "", (("小红", ()), ("小明", ()))),
    ]
    many = [(f"玩家{n}", ()) for n in range(7)]
    (first,) = result_messages(many, [], 0)
    assert first.title == "7 名黑名单"
    assert [name for name, _tags in first.people] == ["玩家0", "玩家1", "玩家2", "玩家3"]
    assert first.more == 3


def test_the_empty_record_page_says_to_press_the_hotkey(window):
    assert window.history_empty.hint.text() == "在「推演成功」大厅按 Alt+1 检查"
    window.store.consented = ["full", "auto"]
    window.full_on.click()
    window.auto_on.click()
    assert window.history_empty.hint.text() == "进入「推演成功」大厅时自动检查"


def test_a_hit_shows_in_the_corner_with_nothing_over_the_game(window):
    window.store.add_like("小红")
    button, names = _lobby()
    window._live_check = True
    window._on_lobby_placed(button)
    assert _marks(window) == []
    hit = Hit(0, "坏人", "坏人", "", False, "", ("炸房",))
    window._show_panel(CheckResult(True, "", names=names, hits=[hit, hit], button_box=button))
    assert _marks(window) == []
    notice = window.notice
    assert notice.isVisible()
    assert notice.kind == "hit"
    # The 黑名单 players on one card, in the colors of the card beside the button ...
    assert notice.main.kind == "hit"
    assert notice.main.title.text() == "1 名黑名单"
    assert notice.main.note.text() == "1 人未识别"
    assert notice.main.names() == ["坏人"]
    # ... and 嘉宾 on a card of its own, which comes a moment later, above it.
    _arrive(notice)
    assert notice.likes.isVisible() and notice.likes.kind == "liked"
    assert notice.likes.title.text() == "嘉宾"
    assert notice.likes.names() == ["小红"]
    # At the bottom right of the screen, above the taskbar; 嘉宾 just above the other.
    area = QApplication.primaryScreen().availableGeometry()
    box, above = notice.main.geometry(), notice.likes.geometry()
    assert area.contains(box) and area.contains(above)
    assert area.right() - box.right() < 40 and area.bottom() - box.bottom() < 40
    assert above.bottom() < box.top() and above.right() == box.right()
    # Plain solid windows that take clicks: no see-through, no click-through.
    from PySide6.QtCore import Qt

    for card in notice.cards():
        assert not card.testAttribute(Qt.WA_TranslucentBackground)
        assert not card.testAttribute(Qt.WA_TransparentForMouseEvents)
        assert card.windowFlags() & Qt.WindowDoesNotAcceptFocus
    assert notice._timer.interval() == 8_000


def test_a_clear_lobby(window):
    button, names = _lobby()
    window._live_check = True
    window._show_panel(CheckResult(True, "", names=names, button_box=button))
    assert _marks(window) == []
    assert window.notice.kind == "clear"
    _arrive(window.notice)
    assert not window.notice.likes.isVisible()


def test_a_hotkey_check_says_checking_then_no_lobby(window, monkeypatch):
    monkeypatch.setattr(window.worker, "request", lambda fn, kind="check": True)
    window.check_now()
    assert window.notice.isVisible() and window.notice.kind == "checking"
    window._rescan_active = True  # The second look found nothing either.
    window._on_checked("ok", CheckResult(False, "没有找到"))
    assert window.notice.kind == "missing"
    assert _marks(window) == []


def test_a_failed_check_says_so_in_the_corner(window):
    window._live_check = True
    window._manual_check = True
    window._rescan_active = True
    window._on_checked("err", RuntimeError("boom"))
    assert window.notice.kind == "error"
    assert window.notice.main.title.text() == "检查失败"


def test_checking_turns_into_the_result_where_it_is(window):
    """The hotkey's 检查中 is the message the result takes over: no second card at the bottom."""
    notice = window.notice
    notice.show_checking(QApplication.primaryScreen())
    assert notice.main.kind == "checking" and notice.main.left is None
    for rise in notice._rises.values():
        rise.setCurrentTime(rise.duration())
    bottom = notice.main.geometry().bottom()
    window.store.add_like("小红")
    button, names = _lobby()
    window._live_check = True
    window._show_panel(CheckResult(True, "", names=names, button_box=button))
    assert notice.main.kind == "clear" and notice.main.geometry().bottom() == bottom
    assert notice.main.left == 1.0
    _arrive(notice)
    assert notice.kind == "liked" and notice.likes.names() == ["小红"]


def test_the_pointer_over_a_message_holds_it(window):
    notice = window.notice
    notice.show_result([("坏人", ())], ["小红"], 0, None)
    _arrive(notice)
    notice.likes.hovered.emit(True)
    assert not notice._timer.isActive()
    held = notice._remaining()
    notice.likes.hovered.emit(False)
    assert notice.isVisible() and notice._timer.isActive()
    assert notice._timer.interval() == held
    # A click on either message puts both away.
    notice.likes.clicked.emit()
    assert not notice.main.isVisible() and not notice.likes.isVisible()


def test_a_click_puts_it_away(window):
    window.notice.show_missing(None)
    assert window.notice.isVisible()
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    point = QPointF(5, 5)
    event = QMouseEvent(QMouseEvent.Type.MouseButtonPress, point, point, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    window.notice.main.mousePressEvent(event)
    assert not window.notice.isVisible()


def test_an_automatic_check_that_finds_no_lobby_goes_quiet(window):
    window.notice.show_checking(None)
    window._live_check = True
    window._manual_check = False
    window._rescan_active = True
    window._on_checked("ok", CheckResult(False, "没有找到"))
    # Not 没有找到大厅: nobody pressed anything.
    assert not window.notice.isVisible()


def test_full_mode_brings_the_marks_back(window):
    window.store.consented = ["full"]
    window.full_on.click()
    assert window.store.safe_mode is False
    button, names = _lobby()
    window._live_check = True
    window._on_lobby_placed(button)
    hit = Hit(0, "坏人", "坏人", "", False, "", ("炸房",))
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert "panel" in _marks(window) and "hit_card" in _marks(window) and "alert" in _marks(window)
    assert not window.notice.isVisible()
    # Back to 安全模式: everything over the game goes at once.
    window.safe_on.click()
    assert window.store.safe_mode is True
    assert _marks(window) == []


def test_safe_mode_checks_on_the_hotkey_only(window):
    window.store.consented = ["full", "auto"]
    # 手动检查 sits beside its hotkey, and in 安全模式 自动检查 cannot be picked.
    assert list(window.auto_mode.buttons) == ["auto", "manual"]
    assert window.auto_off.isChecked() and not window.auto_on.isEnabled()
    window.auto_on.click()
    assert window.store.auto_capture is False and not window._watch_timer.isActive()
    # 完整模式 allows it; back to 安全模式, it is 手动检查 again.
    window.full_on.click()
    assert window.auto_on.isEnabled()
    window.auto_on.click()
    assert window.store.auto_capture is True
    window.safe_on.click()
    assert (window.store.safe_mode, window.store.auto_capture) == (True, False)
    assert window.auto_off.isChecked() and not window.auto_on.isEnabled()
    # A settings file saying both comes back as 安全模式 with 手动检查.
    from blacklist_detect.storage import Store

    window.store.auto_capture = True
    window.store.save_settings()
    assert Store(window.store.root).auto_capture is False


def test_both_lists_are_always_checked(window):
    """提醒 is gone: 黑名单 and 嘉宾 are both looked for, whatever an older version saved."""
    from blacklist_detect.storage import Store

    window.store.settings_path.parent.mkdir(parents=True, exist_ok=True)
    window.store.settings_path.write_text('{"check_blacklist": false, "check_likes": false}', encoding="utf-8")
    window.store = Store(window.store.root)
    window.store.add_like("小红")
    button, names = _lobby()
    hit = Hit(0, "坏人", "坏人", "", False, "", ("炸房",))
    window._live_check = True
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.notice.kind == "hit"
    _arrive(window.notice)
    assert window.notice.likes.names() == ["小红"]
    assert not hasattr(window, "remind_blacklist") and not hasattr(window, "remind_boxes")


def _answer(monkeypatch, answer: bool) -> list[tuple[str, str, str]]:  # noqa: ANN001
    from blacklist_detect import ui

    asked: list[tuple[str, str, str]] = []

    def ask(_parent, title, body, confirm, **kwargs):  # noqa: ANN001, ANN202
        asked.append((title, body, kwargs.get("cancel", "")))
        return answer

    monkeypatch.setattr(ui.ConfirmDialog, "ask", staticmethod(ask))
    return asked


def test_turning_down_the_questions_changes_nothing(window, monkeypatch):
    asked = _answer(monkeypatch, False)
    window.full_on.click()
    title, body, cancel = asked[0]
    assert title == "开启完整模式"
    assert body == "提醒和场景直接显示在游戏窗口，可能被游戏当成异常。"
    assert cancel == "保持安全模式"
    assert window.store.safe_mode is True
    assert window.safe_on.isChecked() is True
    assert window.store.consented == []


def test_each_question_is_asked_once_and_the_answer_is_kept(window, monkeypatch):
    from blacklist_detect.storage import Store

    asked = _answer(monkeypatch, True)
    window.full_on.click()
    window.safe_on.click()
    window.full_on.click()
    window.auto_on.click()
    window.auto_off.click()
    window.auto_on.click()
    # Only 完整模式 asks; 自动检查 is turned on without a question.
    assert [title for title, _body, _cancel in asked] == ["开启完整模式"]
    again = Store(window.store.root)
    assert again.consented == ["full"]
    assert (again.safe_mode, again.auto_capture) == (False, True)
    # Manual checks and 安全模式 never ask.
    window.store.consented = []
    window.auto_off.click()
    window.safe_on.click()
    assert len(asked) == 1
    # 清空数据 forgets it: the next player is asked again.
    window.store.reset()
    assert Store(window.store.root).consented == []


def test_full_mode_adds_the_corner_message_over_an_exclusive_full_screen_game(window, monkeypatch):
    from blacklist_detect import ui

    window.store.consented = ["full"]
    window.full_on.click()
    button, names = _lobby()
    hit = Hit(0, "坏人", "坏人", "", False, "", ("炸房",))
    window._live_check = True
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert not window.notice.isVisible(), "a borderless or windowed game sees the marks"
    monkeypatch.setattr(ui, "exclusive_fullscreen", lambda: True)
    window._hide_panel_after_title()
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.notice.isVisible() and window.notice.kind == "hit"


def test_the_heart_card_grows_for_more_names_after_fewer(window):
    """Two 嘉宾 names after one were cut to the height of one: the card kept its old size."""
    from blacklist_detect.ui_notice import CornerNotice

    notice = CornerNotice()
    screen = QApplication.primaryScreen()
    heights = []
    for likes in (["小红"], ["小红", "小明"], ["小红", "小明", "阿强"], ["小红"]):
        notice.show_result([], likes, 0, screen)
        _arrive(notice)
        assert notice.likes.height() >= notice.likes.sizeHint().height(), likes
        heights.append(notice.likes.height())
        notice.hide()
    assert heights[0] < heights[1] < heights[2] and heights[3] == heights[0]
    notice.close()

