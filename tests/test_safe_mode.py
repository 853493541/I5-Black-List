"""安全模式: a check on the hotkey, nothing over the game, the result in a box at the bottom right."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect.pipeline import CheckResult, Hit, NameSlot  # noqa: E402
from blacklist_detect.ui_notice import result_text  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect import ui
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    sounds: list[int] = []
    monkeypatch.setattr(ui, "play_hit_sound", lambda: sounds.append(1))
    made = MainWindow()
    made._watch_timer.stop()
    made.store.disclaimer_accepted = True
    made.sounds = sounds
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
    assert result_text([("坏人", ("炸房", "挂机")), ("乙", ())], ["小红"], 1) == (
        "hit",
        "发现 2 名黑名单玩家",
        ["坏人　炸房、挂机", "乙", "心动：小红", "1 人未识别"],
    )
    assert result_text([], [], 0) == ("clear", "未发现黑名单", [])
    assert result_text([], ["小红", "小明"], 0) == ("liked", "未发现黑名单", ["心动：小红、小明"])
    many = [(f"玩家{n}", ()) for n in range(7)]
    kind, title, lines = result_text(many, [], 0)
    assert title == "发现 7 名黑名单玩家"
    assert lines == ["玩家0", "玩家1", "玩家2", "玩家3", "还有 3 人"]


def test_the_empty_record_page_says_to_press_the_hotkey(window):
    assert window.history_empty.hint.text() == "在「推演成功」大厅按 Alt+1 检查"
    window.store.consented = ["full", "auto"]
    window.full_on.click()
    window.auto_on.click()
    assert window.history_empty.hint.text() == "进入「推演成功」大厅时自动检查"


def test_a_hit_shows_in_the_corner_and_sounds_with_nothing_over_the_game(window):
    window.store.add_like("小红")
    button, names = _lobby()
    window._live_check = True
    window._on_lobby_placed(button)
    assert _marks(window) == []
    hit = Hit(0, "坏人", "坏人", "", False, "", ("炸房",))
    window._show_panel(CheckResult(True, "", names=names, hits=[hit, hit], button_box=button))
    assert _marks(window) == []
    assert window.notice.isVisible()
    assert window.notice.kind == "hit"
    assert window.notice.title.text() == "发现 1 名黑名单玩家"
    assert window.notice.lines.text() == "坏人　炸房\n心动：小红\n1 人未识别"
    assert window.sounds == [1]
    # At the bottom right of the screen, above the taskbar.
    area = QApplication.primaryScreen().availableGeometry()
    box = window.notice.geometry()
    assert area.contains(box)
    assert area.right() - box.right() < 40 and area.bottom() - box.bottom() < 40
    # It is a plain solid window that takes clicks: no see-through, no click-through.
    from PySide6.QtCore import Qt

    assert not window.notice.testAttribute(Qt.WA_TranslucentBackground)
    assert not window.notice.testAttribute(Qt.WA_TransparentForMouseEvents)
    assert window.notice.windowFlags() & Qt.WindowDoesNotAcceptFocus
    assert window.notice._timer.interval() == 8_000


def test_a_clear_lobby_and_no_sound(window):
    button, names = _lobby()
    window._live_check = True
    window._show_panel(CheckResult(True, "", names=names, button_box=button))
    assert _marks(window) == []
    assert window.notice.kind == "clear"
    assert window.sounds == []


def test_the_sound_can_be_turned_off(window):
    window.sound_switch.click()
    assert window.store.hit_sound is False
    button, names = _lobby()
    window._live_check = True
    hit = Hit(0, "坏人", "坏人", "", False, "", ())
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.notice.kind == "hit"
    assert window.sounds == []


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
    assert window.notice.title.text() == "检查失败"


def test_a_click_puts_it_away(window):
    window.notice.show_missing(None)
    assert window.notice.isVisible()
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    point = QPointF(5, 5)
    event = QMouseEvent(QMouseEvent.Type.MouseButtonPress, point, point, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    window.notice.mousePressEvent(event)
    assert not window.notice.isVisible()


def test_an_automatic_check_that_finds_no_lobby_goes_quiet(window):
    window.notice.show_checking(None)
    window._live_check = True
    window._manual_check = False
    window._rescan_active = True
    window._on_checked("ok", CheckResult(False, "没有找到"))
    # Not 没有找到大厅: nobody pressed anything.
    assert not window.notice.isVisible()


def test_full_mode_brings_the_marks_back_and_the_sound_stays(window):
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
    assert window.sounds == [1]
    # Back to 安全模式: everything over the game goes at once.
    window.safe_on.click()
    assert window.store.safe_mode is True
    assert _marks(window) == []


def test_safe_mode_checks_on_the_hotkey_only(window):
    window.store.consented = ["full", "auto"]
    # 手动检查 comes first, and in 安全模式 自动检查 cannot be picked, from 设置 or the header.
    assert list(window.auto_mode.buttons) == ["manual", "auto"]
    assert window.auto_off.isChecked() and not window.auto_on.isEnabled()
    window.auto_on.click()
    window._cycle_capture_mode()
    assert window.store.auto_capture is False and not window._watch_timer.isActive()
    assert "安全模式" in window.status_chip.toolTip()
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


def test_the_sound_can_be_heard_from_settings(window):
    from blacklist_detect.ui_notice import HIT_SOUND

    assert HIT_SOUND.is_file()
    window.sound_play.click()
    assert window.sounds == [1]


def test_both_lists_are_always_checked(window):
    """提醒 is gone: 黑名单 and 心动 are both looked for, whatever an older version saved."""
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
    assert "心动" in window.notice.lines.text()
    assert not hasattr(window, "remind_blacklist")


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
    assert "游戏画面上" in body and "判定为异常" in body
    assert cancel == "保持安全模式"
    assert window.store.safe_mode is True
    assert window.safe_on.isChecked() is True
    # 自动检查 is asked about in 完整模式, the only place it can be picked.
    window.store.consented = ["full"]
    window.full_on.click()
    window.auto_on.click()
    title, body, cancel = asked[1]
    assert title == "开启自动检查"
    assert "截屏" in body and "判定为异常" in body
    assert cancel == "保持手动检查"
    assert window.store.auto_capture is False
    assert window.auto_off.isChecked() is True
    assert window.store.consented == ["full"]


def test_each_question_is_asked_once_and_the_answer_is_kept(window, monkeypatch):
    from blacklist_detect.storage import Store

    asked = _answer(monkeypatch, True)
    window.full_on.click()
    window.safe_on.click()
    window.full_on.click()
    window.auto_on.click()
    window.auto_off.click()
    window._cycle_capture_mode()
    assert [title for title, _body, _cancel in asked] == ["开启完整模式", "开启自动检查"]
    again = Store(window.store.root)
    assert sorted(again.consented) == ["auto", "full"]
    assert (again.safe_mode, again.auto_capture) == (False, True)
    # Manual checks and 安全模式 never ask.
    window.store.consented = []
    window.auto_off.click()
    window.safe_on.click()
    assert len(asked) == 2
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
