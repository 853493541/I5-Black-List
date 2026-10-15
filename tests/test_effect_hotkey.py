"""特效: the page where the 特效 hotkey's scene is picked, and that hotkey, which plays it at once over
the game with no check, on the screen and in 直播画面."""

import json
import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QRect, Qt  # noqa: E402
from PySide6.QtGui import QFocusEvent, QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect import hotkey, livehime, love_scenes  # noqa: E402
from blacklist_detect.pipeline import CheckResult  # noqa: E402
from blacklist_detect.storage import DEFAULT_EFFECT_HOTKEY, Store  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect import ui
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    made = MainWindow()
    made._watch_timer.stop()
    made.store.disclaimer_accepted = True
    made.store.consented = ["full"]
    made._on_display_mode("full")
    played: list[str] = []
    monkeypatch.setattr(made.music, "preview", lambda choice: played.append(choice) or choice)
    monkeypatch.setattr(made.music, "stop", lambda: played.append("stop"))
    made.played = played

    # No screen copy and no recognition: the hotkey checks nothing.
    def never(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("the 特效 hotkey copied the screen or read it")

    for name in ("capture_displays", "capture_top_band", "check_frames", "check_image", "glance_title"):
        monkeypatch.setattr(ui, name, never)
    jobs: list[str] = []
    monkeypatch.setattr(made.worker, "request", lambda fn, kind="check": jobs.append(kind) or False)
    made.jobs = jobs
    QApplication.processEvents()
    yield made
    made._end_quick_play()
    made.notice.hide()
    made.close()


def _wait(ms: int) -> None:
    end = time.time() + ms / 1000
    while time.time() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def _press(edit, key, modifiers=Qt.KeyboardModifier.NoModifier) -> None:  # noqa: ANN001
    app = QApplication.instance()
    app.sendEvent(edit, QFocusEvent(QEvent.Type.FocusIn))
    app.sendEvent(edit, QKeyEvent(QEvent.Type.KeyPress, key, modifiers))


def test_the_settings_save_and_load_and_bad_ones_fall_back(tmp_path):
    root = tmp_path / "store"
    store = Store(root)
    assert store.quick_scene == "classic" and store.effect_hotkey == DEFAULT_EFFECT_HOTKEY == "Alt+F12"
    store.quick_scene = "claw"
    store.effect_hotkey = "Ctrl+K"
    store.save_settings()
    again = Store(root)
    assert again.quick_scene == "claw" and again.effect_hotkey == "Ctrl+K"

    def saved(**settings) -> Store:  # noqa: ANN003
        (root / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        return Store(root)

    # A scene this version does not have is 经典; one that was replaced is its replacement.
    assert saved(quick_scene="ribbon").quick_scene == "classic"
    assert saved(quick_scene="champagne").quick_scene == "angel"
    assert saved(quick_scene=7).quick_scene == "classic"
    # A key that is no hotkey is the default; three keys keep two; 检查's own key is none.
    assert saved(effect_hotkey="Ctrl+Alt").effect_hotkey == "Alt+F12"
    assert saved(effect_hotkey=["F8"]).effect_hotkey == "Alt+F12"
    assert saved(effect_hotkey="ctrl+alt+f9").effect_hotkey == "Ctrl+F9"
    assert saved(hotkey="Alt+F12").effect_hotkey == ""
    assert saved(hotkey="Alt+1", effect_hotkey="alt+1").effect_hotkey == ""
    store = saved(quick_scene="stars", effect_hotkey="F9")
    store.reset()
    assert store.quick_scene == "classic" and store.effect_hotkey == "Alt+F12"


def test_the_page_lists_every_scene_and_saves_the_one_picked(window):
    assert window.tabs.tabText(window.effects_tab) == "特效"
    assert window.likes_tab < window.effects_tab < window.settings_tab
    page = window.effects_page
    assert [(key, button.text()) for key, button in page.scenes.buttons.items()] == list(love_scenes.SCENES)
    assert page.scenes.key == "classic" and page.scenes.buttons["classic"].isChecked()
    window.tabs.setCurrentIndex(window.effects_tab)
    window.show()
    QApplication.processEvents()
    assert page.preview.scene == "classic" and page.preview._tick.isActive()
    page.scenes.buttons["fluffy"].click()
    assert window.store.quick_scene == "fluffy" and Store(window.store.root).quick_scene == "fluffy"
    assert [key for key, button in page.scenes.buttons.items() if button.isChecked()] == ["fluffy"]
    # It plays quietly; ▶ plays it with its music.
    assert page.preview.scene == "fluffy" and window.played == ["stop"]
    page.preview.play_button.click()
    assert window.played[-1] == "fluffy"
    # Out of sight, the preview rests.
    window.tabs.setCurrentIndex(window.settings_tab)
    assert not page.preview._tick.isActive()
    # Labels only: the hotkey and 播放, in one row.
    assert window.effect_hotkey_edit.text() == "Alt+F12" and page.play_button.text() == "播放"
    assert page.note.isHidden()
    window.hide()


def test_the_page_fits_the_smallest_window(window):
    window.resize(900, 560)
    window.tabs.setCurrentIndex(window.effects_tab)
    window.show()
    _wait(50)
    page = window.effects_page
    preview = page.preview.geometry().translated(page.preview.parentWidget().mapTo(page, page.preview.pos()) - page.preview.pos())
    assert page.rect().contains(preview) and preview.width() >= 560
    button = page.play_button
    assert page.rect().contains(button.geometry().translated(button.parentWidget().mapTo(page, button.pos()) - button.pos()))
    last = page.scenes.buttons["claw"]
    assert page.rect().contains(last.geometry().translated(last.parentWidget().mapTo(page, last.pos()) - last.pos()))
    window.hide()


def test_the_two_hotkeys_register_each_with_its_own_id(window):
    ids = {ident for ident, _modifiers, _vk in hotkey.registered}
    assert window.hotkey._id == 1 and window.effect_hotkey._id == 2
    assert window.effect_hotkey.active == "Alt+F12" and 2 in ids
    f12 = [(modifiers, vk) for ident, modifiers, vk in hotkey.registered if ident == 2][-1]
    assert f12 == (hotkey.parse_hotkey("Alt+F12").win_modifiers, 0x7B)
    # Its callback is the play.
    assert window.effect_hotkey.callback == window.play_quick_scene
    # 自动检查 lets go of 检查's hotkey, never of the 特效 hotkey.
    window._on_auto_mode("auto")
    assert window.hotkey.active == "" and window.effect_hotkey.active == "Alt+F12"


def test_a_new_effect_hotkey_is_saved_and_taken_at_once(window):
    edit = window.effect_hotkey_edit
    _press(edit, Qt.Key_9, Qt.KeyboardModifier.ControlModifier)
    assert window.store.effect_hotkey == "Ctrl+9" and Store(window.store.root).effect_hotkey == "Ctrl+9"
    assert edit.text() == "Ctrl+9" and window.effect_hotkey.active == "Ctrl+9"
    # Taking it let go of 检查's for a moment, and has it back.
    QApplication.instance().sendEvent(edit, QFocusEvent(QEvent.Type.FocusOut))
    assert window.hotkey.active == "Alt+1" and window.effect_hotkey.active == "Ctrl+9"
    # Three keys are refused as for 检查, under the box.
    three = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
    _press(edit, Qt.Key_K, three)
    assert window.store.effect_hotkey == "Ctrl+9" and window.effects_page.note.text() == "最多两个键，比如 Alt+1"


def test_the_two_hotkeys_never_share_a_key(window):
    edit = window.effect_hotkey_edit
    _press(edit, Qt.Key_1, Qt.KeyboardModifier.AltModifier)
    assert window.store.effect_hotkey == "Alt+F12" and window.effects_page.note.text() == "检查已在用这个键，换一个"
    assert not window.effects_page.note.isHidden()
    QApplication.instance().sendEvent(edit, QFocusEvent(QEvent.Type.FocusOut))
    assert edit.text() == "Alt+F12" and window.effect_hotkey.active == "Alt+F12"
    # And 检查's box refuses the 特效 hotkey's key.
    _press(window.hotkey_edit, Qt.Key_F12, Qt.KeyboardModifier.AltModifier)
    assert window.store.hotkey == "Alt+1" and window.settings_label.text() == "特效已在用这个键，换一个"


def test_the_hotkey_plays_the_scene_at_once_with_no_check(window):
    window.store.quick_scene = "stars"
    assert window.effect_hotkey.callback()
    # The rose ring and the badge on where 准备案件还原 is, the scene and its music. No 嘉宾 card.
    assert window.panel.isVisible() and window.panel.mode == "liked" and window.clear_mark.isVisible()
    assert window.clear_mark.heart and not window.like_card.isVisible() and not window.hit_card.isVisible()
    assert window.love.playing() and window.love.scene == "stars" and window.played[-1] == "stars"
    assert window.panel.look == window.clear_mark.look
    # Over the screen under the pointer, as a full-screen game: the ring at its 准备案件还原.
    game = window.love.geometry()
    assert abs(game.width() / game.height() - 16 / 9) < 0.01
    cover = window.panel.cover_geometry()
    assert game.contains(cover) and cover.center().y() > game.top() + 0.7 * game.height()
    _wait(150)
    # Nothing was copied or read, and no look for the lobby started.
    assert window.jobs == [] and not window._watch_timer.isActive()
    assert window.store.scans == []


def test_it_goes_by_itself_and_puts_everything_back(window, monkeypatch):
    from blacklist_detect import ui

    monkeypatch.setattr(ui, "QUICK_HOLD_MS", 50)
    monkeypatch.setattr(window.love, "duration", lambda: 0.1)
    assert window.play_quick_scene()
    assert window._game_box is not None
    _wait(400)
    assert not window.panel.isVisible() and not window.clear_mark.isVisible() and not window.love.playing()
    assert window._quick_scene == "" and window._game_box is None and window._quick_area is None
    assert window.love.choice == window.store.love_scene


def test_pressed_again_it_starts_over(window):
    window.store.quick_scene = "ice"
    assert window.play_quick_scene()
    first = window._quick_round
    window.store.quick_scene = "lace"
    assert window.play_quick_scene()
    assert window._quick_round > first and window.love.scene == "lace" and window.love.elapsed() < 1
    assert window.played[-2:] == ["stop", "lace"]


def test_it_plays_with_the_love_effects_switched_off(window):
    window._set_love_effects(False)
    assert window.store.love_scene == "off"
    window.store.quick_scene = "claw"
    assert window.play_quick_scene()
    assert window.love.playing() and window.love.scene == "claw"
    window._end_quick_play()
    assert window.love.choice == "off"
    # 音乐 无: it plays with no music.
    window.store.love_music = "off"
    assert window.play_quick_scene()
    assert window.played[-1] == "" and window.love.playing()


def test_it_plays_over_the_last_lobby_when_there_was_one(window):
    from blacklist_detect.ui import native_to_logical, virtual_origin

    # Desktop pixels from the virtual screen's corner, as a check gives them.
    button = (600, 700, 800, 760)
    window._game_box = button
    window._game_screen = (0, 0, 1600, 900)
    assert window.play_quick_scene()
    origin_x, origin_y = virtual_origin()
    middle, _y, _ratio = native_to_logical(700 + origin_x, 730 + origin_y)
    cover = window.panel.cover_geometry()
    assert abs(cover.center().x() - middle) <= 2 and window._quick_area is None
    window._end_quick_play()
    assert window._game_box == button


def test_a_real_lobby_comes_first(window, monkeypatch):
    # A check running: the press does nothing.
    window._check_started = time.perf_counter()
    assert not window.play_quick_scene() and not window.love.playing()
    window._check_started = None
    # A real lobby's marks showing: nothing either.
    window._live_check = True
    screen = window.screen().geometry()
    button = (screen.x() + 600, screen.y() + 700, screen.x() + 800, screen.y() + 760)
    window._show_panel(CheckResult(header_found=True, message="", button_box=button))
    assert window.panel.isVisible() and window.panel.mode == "clear"
    assert not window.play_quick_scene() and window._quick_scene == ""
    window._hide_panel_after_title()
    # Playing, a check starts: the play is taken down, its music stopped.
    assert window.play_quick_scene()
    monkeypatch.setattr(window.worker, "request", lambda fn, kind="check": True)
    window._start(window._capture_job, live=True)
    assert window._quick_scene == "" and not window.love.playing() and window.played[-1] == "stop"
    # A glance that finds no lobby leaves the play alone.
    window._check_started = None
    window._live_check = False
    assert window.play_quick_scene()
    window._on_glanced("ok", False)
    assert window.panel.isVisible() and window.love.playing()


def test_it_gives_way_to_nothing_but_takes_over_the_stream_test(window):
    window._set_stream_mode(True)
    assert window.start_stream_test()
    _wait(150)
    assert window.play_quick_scene()
    assert window._demo_likes is None and not window.demo_lobby.isVisible() and window._quick_scene
    # 测试效果 then takes the play down in turn.
    assert window.start_stream_test()
    assert window._quick_scene == ""


def test_in_stream_mode_it_reaches_the_stream_window(window, monkeypatch):
    # 安全模式 with 直播模式: the marks only in 直播画面, never on the streamer's screen.
    window._on_display_mode("safe")
    window._set_stream_mode(True)
    assert window._overlay_target() == "stream"
    screen = window.screen().geometry()
    ratio = window.screen().devicePixelRatio()
    game_window = livehime.Capture("MuMu安卓设备", "Qt5QWindowIcon", "MuMuNxDevice.exe", True)
    native = (screen.x() + round(100 * ratio), screen.y() + round(80 * ratio), screen.x() + round(900 * ratio), screen.y() + round(580 * ratio))
    monkeypatch.setattr(livehime, "game_capture", lambda scene, title: game_window)
    monkeypatch.setattr(livehime, "client_rect", lambda capture: native)
    assert window.play_quick_scene()
    # The game's window is the one 直播姬 captures; the game, 16:9, in it.
    captured = QRect(screen.x() + 100, screen.y() + 80, 800, 500)
    assert window.stream._frame == captured
    assert captured.contains(window.love.geometry()) and window.love.geometry().width() == 800
    for mark in (window.panel, window.clear_mark, window.love):
        assert mark.testAttribute(Qt.WA_DontShowOnScreen)
    assert window.panel in window.stream._marks() and window.clear_mark in window.stream._marks()
    assert window.stream._borders() == [window.love] and window.stream.busy()
    assert not window.stream.grab().isNull()
    window._end_quick_play()
    assert window.stream._frame == QRect() and not window.stream.busy()


def test_in_full_mode_without_stream_mode_it_plays_on_the_screen(window):
    assert window._overlay_target() == "screen" and not window.store.stream_mode
    assert window.play_quick_scene()
    for mark in (window.panel, window.clear_mark, window.love):
        assert not mark.testAttribute(Qt.WA_DontShowOnScreen) and mark.isVisible()


def test_the_play_is_logged(window, caplog):
    import logging

    window.store.quick_scene = "angel"
    with caplog.at_level(logging.INFO):
        window.play_quick_scene()
        window._end_quick_play()
    said = caplog.text
    assert "特效 hotkey: angel over the screen under the pointer" in said
    assert "特效 hotkey shown: 嘉宾特效 (angel" in said and "特效 hotkey: done." in said
