"""场景: the page where the 场景 hotkey's scene is picked (快捷键放这个), and that hotkey, which plays it at
once over the game with no check, on the screen and in 直播画面. tests/test_effects_manager.py has the rest of
the page: each 场景's sound and 音量."""

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
        raise AssertionError("the 场景 hotkey copied the screen or read it")

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


def _started(window) -> None:  # noqa: ANN001
    """Its 场景 started, its music with it: 演说家遇袭's pictures are made off the screen's thread first."""
    end = time.time() + 60
    while window.love.waiting() and time.time() < end:
        window.love._step()
        time.sleep(0.01)
    assert not window.love.waiting()


def _opened_with(tmp_path, monkeypatch, **settings):  # noqa: ANN001, ANN003, ANN202
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    root = Store().root
    root.mkdir(parents=True, exist_ok=True)
    (root / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    window = MainWindow()
    window._watch_timer.stop()
    return window


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
    # One in everyday use, from before it was refused or written in by hand, is the default too.
    for key in ("Q", "Shift+Q", "Shift+7", "Ctrl+C", "Ctrl+Shift+V", "Alt+F4", "Win+D"):
        assert saved(effect_hotkey=key).effect_hotkey == "Alt+F12", key
    assert saved(hotkey="Alt+F12", effect_hotkey="Ctrl+V").effect_hotkey == ""
    # 检查's, which v0.9.11 took, is its default again: nothing taken from typing, and 手动检查 still has a key.
    for key in ("Q", "Shift+A", "Ctrl+S", "ctrl+v", "Alt+F4", "Win+D", "Shift+F10", "F12", "Ctrl+Shift+C"):
        store = saved(hotkey=key)
        assert (store.hotkey, store.dropped_hotkey, store.effect_hotkey) == ("Alt+1", key, "Alt+F12"), key
    assert saved(hotkey="alt+q").hotkey == "Alt+Q" and saved(hotkey="alt+q").dropped_hotkey == ""
    # Alt+1 is the 场景 hotkey's by then: it keeps it, and 检查 is none.
    store = saved(hotkey="Shift+A", effect_hotkey="Alt+1")
    assert (store.hotkey, store.effect_hotkey) == ("", "Alt+1")
    store = saved(effect_hotkey="Shift+A")
    assert (store.effect_hotkey, store.dropped_effect_hotkey, store.dropped_hotkey) == ("Alt+F12", "Shift+A", "")
    store.save_settings()
    assert (Store(root).hotkey, Store(root).effect_hotkey, Store(root).dropped_effect_hotkey) == ("Alt+1", "Alt+F12", "")
    assert saved(hotkey="Alt+F12").effect_hotkey == ""
    assert saved(hotkey="Alt+1", effect_hotkey="alt+1").effect_hotkey == ""
    # 检查 had no key and the 场景 hotkey took Alt+1, where 检查 would come back: the 场景 hotkey keeps it.
    store = saved(hotkey="", effect_hotkey="Alt+1")
    assert (store.hotkey, store.effect_hotkey) == ("", "Alt+1")
    # None saved (turned off, or 检查's key once) stays none: Alt+F12 is not taken behind the player's back.
    store = saved(hotkey="Ctrl+K", effect_hotkey="")
    assert (store.hotkey, store.effect_hotkey) == ("Ctrl+K", "")
    store = saved(hotkey="Ctrl+Alt+K", effect_hotkey="Ctrl+Shift+K")
    assert (store.hotkey, store.effect_hotkey) == ("Ctrl+K", "")
    store.save_settings()
    assert (Store(root).hotkey, Store(root).effect_hotkey) == ("Ctrl+K", "")
    # A v0.9.11 player with 检查 on Alt+F12 who moves 检查 later keeps the 场景 hotkey none.
    store = saved(hotkey="Alt+F12")
    store.hotkey = "Alt+2"
    store.save_settings()
    assert (Store(root).hotkey, Store(root).effect_hotkey) == ("Alt+2", "")
    # None saved for 场景 at all (v0.9.11): the default.
    assert saved(hotkey="Ctrl+K").effect_hotkey == "Alt+F12"
    store = saved(quick_scene="stars", hotkey="Q", effect_hotkey="F9")
    store.reset()
    assert store.quick_scene == "classic" and store.effect_hotkey == "Alt+F12"
    assert store.dropped_hotkey == store.dropped_effect_hotkey == ""


def test_the_page_lists_every_scene_and_saves_the_one_given_the_hotkey(window):
    assert "场景管理" not in [window.tabs.tabText(index) for index in range(window.tabs.count())]
    page = window.effects_page
    assert page.window() is window.scenes_dialog and window.scenes_dialog.windowTitle() == "场景管理"
    assert [(key, button.text()) for key, button in page.scenes.buttons.items()] == list(love_scenes.SCENES)
    assert page.scenes.key == "classic" and page.scenes.buttons["classic"].isChecked()
    window.show()
    window._show_scene_manager()
    QApplication.processEvents()
    # It opens on the scene still: nothing made, nothing playing.
    assert page.preview.scene == "classic" and page.preview.is_still and not page.preview._tick.isActive()
    # A click on a name shows a scene; one on its spot gives it the hotkey.
    page.scenes.buttons["fluffy"].click()
    assert window.store.quick_scene == "classic"
    page.scenes.ticked.emit("fluffy")
    assert window.store.quick_scene == "fluffy" and Store(window.store.root).quick_scene == "fluffy"
    assert [key for key, button in page.scenes.buttons.items() if button.isChecked()] == ["fluffy"]
    assert [key for key, button in page.scenes.buttons.items() if button.tick] == ["fluffy"]
    # It plays quietly; ▶ 播放 plays it with its music, which the next pick stops.
    assert page.preview.scene == "fluffy" and window.played == []
    page.play_button.click()
    assert window.played[-1] == "fluffy"
    page.scenes.buttons["fluffy"].click()
    assert window.played[-1] == "stop"
    # Closed, the preview rests.
    window.scenes_dialog.reject()
    assert not page.preview._tick.isActive()
    # Labels only: the hotkey, and 播放 beside 音量.
    assert window.effect_hotkey_edit.text() == "Alt+F12" and page.play_button.text() == "播放"
    assert page.note.isHidden()
    window.hide()


def test_the_dialog_shows_every_control_over_the_smallest_window(window):
    """Over a window at 900x560 every control is in view, a note under the rows too, and the preview at its
    full size (test_effects_manager has a 场景 with the player's own songs)."""
    window.resize(900, 560)
    window.show()
    window._show_scene_manager()
    _wait(50)
    page = window.effects_page
    page._tell("这个视频里没有能放的声音")
    _wait(20)

    def placed(widget):  # noqa: ANN001, ANN202
        return widget.geometry().translated(widget.parentWidget().mapTo(page, widget.pos()) - widget.pos())

    assert page.rect().contains(placed(page.preview)) and page.preview.width() == page.PREVIEW_W
    # Every scene in view, the list down to the page's foot.
    claw = page.scenes.buttons["claw"]
    assert page.scene_scroll.viewport().rect().contains(claw.geometry().translated(0, -page.scene_scroll.verticalScrollBar().value()))
    assert placed(page.scene_scroll).bottom() == page.rect().bottom()
    card = window.scenes_dialog.card.size()
    page.say("这个键被别的程序占了，换一个", held=True)
    _wait(20)
    controls = (page.sounds, page.upload_button, page.volume_slider, page.volume_label, page.level_note, page.play_button,
                page.sound_note, window.effect_hotkey_edit, page.hotkey_hint, page.note)  # fmt: skip
    for control in controls:
        assert page.rect().contains(placed(control)), control
    # The hotkey's note under it, over the list, which gives it the room; the 配乐's under the songs.
    assert placed(window.effect_hotkey_edit).bottom() < placed(page.note).top()
    assert placed(page.note).bottom() < placed(page.scene_scroll).top()
    assert placed(page.sounds).bottom() < placed(page.sound_note).top()
    assert window.scenes_dialog.card.size() == card and placed(page.scene_scroll).bottom() == page.rect().bottom()
    page.say("")
    window.scenes_dialog.reject()
    window.hide()


def test_the_two_hotkeys_register_each_with_its_own_id(window):
    ids = {ident for ident, _modifiers, _vk in hotkey.registered}
    assert window.hotkey._id == 1 and window.effect_hotkey._id == 2
    assert window.effect_hotkey.active == "Alt+F12" and 2 in ids
    f12 = [(modifiers, vk) for ident, modifiers, vk in hotkey.registered if ident == 2][-1]
    assert f12 == (hotkey.parse_hotkey("Alt+F12").win_modifiers, 0x7B)
    # Its callback is the play.
    assert window.effect_hotkey.callback == window.play_quick_scene
    # 自动检查 lets go of 检查's hotkey, never of the 场景 hotkey.
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


def test_the_effect_hotkey_can_be_none(window):
    edit = window.effect_hotkey_edit
    for key in (Qt.Key_Backspace, Qt.Key_Delete):
        _press(edit, Qt.Key_9, Qt.KeyboardModifier.ControlModifier)
        assert window.store.effect_hotkey == "Ctrl+9"
        # Backspace or Delete in its box: none, its key free in every other program, and so after a restart.
        _press(edit, key)
        QApplication.instance().sendEvent(edit, QFocusEvent(QEvent.Type.FocusOut))
        assert window.store.effect_hotkey == "" and Store(window.store.root).effect_hotkey == ""
        assert edit.text() == "" and edit.placeholderText() == "未设置"
        assert window.effect_hotkey.active == "" and window.hotkey.active == "Alt+1" and window.effects_page.note.isHidden()
    again = type(window)()
    assert again.store.effect_hotkey == "" and again.effect_hotkey.active == "" and again.effect_hotkey_edit.text() == ""
    again.close()
    # 检查's own box has no none: it is how a lobby is checked.
    _press(window.hotkey_edit, Qt.Key_Backspace)
    assert window.store.hotkey == "Alt+1" and window.settings_label.text() == "用字母、数字或 F1–F12"


def test_a_letter_or_number_alone_is_no_hotkey(window, monkeypatch):
    monkeypatch.setattr(hotkey, "_register", lambda ident, modifiers, vk: True)
    shift = Qt.KeyboardModifier.ShiftModifier
    # It would be taken from every program: typing it anywhere would press it. With Shift too.
    for edit, note in ((window.effect_hotkey_edit, window.effects_page.note), (window.hotkey_edit, window.settings_label)):
        for key, modifiers in ((Qt.Key_Q, Qt.KeyboardModifier.NoModifier), (Qt.Key_7, Qt.KeyboardModifier.NoModifier),
                               (Qt.Key_Q, shift), (Qt.Key_7, shift)):  # fmt: skip
            note.setText("")
            _press(edit, key, modifiers)
            assert note.text() == "加上 Ctrl 或 Alt，比如 Alt+1"
    assert (window.store.hotkey, window.store.effect_hotkey) == ("Alt+1", "Alt+F12")
    # Nor a shortcut every program has: copying, pasting, closing a window.
    ctrl, alt = Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.AltModifier
    for edit, note in ((window.effect_hotkey_edit, window.effects_page.note), (window.hotkey_edit, window.settings_label)):
        for key, modifiers in ((Qt.Key_C, ctrl), (Qt.Key_V, ctrl), (Qt.Key_Z, ctrl), (Qt.Key_S, ctrl), (Qt.Key_F4, alt),
                               (Qt.Key_D, Qt.KeyboardModifier.MetaModifier)):  # fmt: skip
            note.setText("")
            _press(edit, key, modifiers)
            assert note.text() == "这是常用的键，换一个"
    assert (window.store.hotkey, window.store.effect_hotkey) == ("Alt+1", "Alt+F12")
    # An F key alone is no letter anyone types.
    _press(window.effect_hotkey_edit, Qt.Key_F8)
    assert window.store.effect_hotkey == "F8"


def test_a_player_whose_check_key_was_alt_f12_is_told_the_effect_hotkey_is_not_set(tmp_path, monkeypatch):
    window = _opened_with(tmp_path, monkeypatch, hotkey="Alt+F12")
    edit = window.effect_hotkey_edit
    assert window.store.effect_hotkey == "" and window.effect_hotkey.active == ""
    assert edit.text() == "" and edit.placeholderText() == "未设置"
    assert window.effects_page.note.text() == "检查已在用 Alt+F12，场景快捷键未设置"
    # 检查's own box still says 无 when it has none.
    assert window.hotkey_edit.placeholderText() == "无"
    # The same key pressed again in 检查's box: still so, still said.
    _press(window.hotkey_edit, Qt.Key_F12, Qt.KeyboardModifier.AltModifier)
    assert window.effects_page.note.text() == "检查已在用 Alt+F12，场景快捷键未设置"
    # 检查 moves off it: no longer so, so no longer said; a note about a key pressed for 场景 stays.
    _press(window.hotkey_edit, Qt.Key_2, Qt.KeyboardModifier.AltModifier)
    assert window.store.hotkey == "Alt+2" and window.effects_page.note.isHidden()
    window.effects_page.say("最多两个键，比如 Alt+1")
    _press(window.hotkey_edit, Qt.Key_3, Qt.KeyboardModifier.AltModifier)
    assert window.store.hotkey == "Alt+3" and window.effects_page.note.text() == "最多两个键，比如 Alt+1"
    window.close()


def test_the_hotkey_box_keeps_its_width_while_it_waits(window):
    app = QApplication.instance()
    for edit in (window.effect_hotkey_edit, window.hotkey_edit):
        width = edit.width()
        app.sendEvent(edit, QFocusEvent(QEvent.Type.FocusIn))
        assert edit.placeholderText() == "请按下快捷键" and edit.width() == width
        app.sendEvent(edit, QFocusEvent(QEvent.Type.FocusOut))
        assert edit.width() == width


def test_the_two_hotkeys_never_share_a_key(window):
    edit = window.effect_hotkey_edit
    _press(edit, Qt.Key_1, Qt.KeyboardModifier.AltModifier)
    assert window.store.effect_hotkey == "Alt+F12" and window.effects_page.note.text() == "检查已在用这个键，换一个"
    assert not window.effects_page.note.isHidden()
    QApplication.instance().sendEvent(edit, QFocusEvent(QEvent.Type.FocusOut))
    assert edit.text() == "Alt+F12" and window.effect_hotkey.active == "Alt+F12"
    # And 检查's box refuses the 场景 hotkey's key.
    _press(window.hotkey_edit, Qt.Key_F12, Qt.KeyboardModifier.AltModifier)
    assert window.store.hotkey == "Alt+1" and window.settings_label.text() == "场景已在用这个键，换一个"


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
    assert window.love.choice == "classic"


def test_pressed_again_it_starts_over(window):
    window.store.quick_scene = "ice"
    assert window.play_quick_scene()
    first = window._quick_round
    window.store.quick_scene = "lace"
    assert window.play_quick_scene()
    assert window._quick_round > first and window.love.scene == "lace" and window.love.elapsed() < 1
    assert window.played[-2:] == ["stop", "lace"]


def test_it_plays_with_every_guest_on_no_scene(window):
    from blacklist_detect.model import Scenes

    window.store.add_like("心动小鹿", scenes=Scenes())
    assert window._choice_for(window.store.likes) == ("", "off")
    window.store.quick_scene = "claw"
    assert window.play_quick_scene()
    assert window.love.playing() and window.love.scene == "claw"
    window._end_quick_play()
    assert window.love.choice == "classic"
    # 静音: it plays with no sound.
    from blacklist_detect.ui_music import ThemeMusic

    tunes: list = []
    window.music = ThemeMusic(play=tunes.append)
    window.mute_box.click()
    assert window.play_quick_scene()
    assert window.love.playing() and tunes and all(tune is None for tune in tunes)


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
    # A glance that finds no lobby leaves the play alone, its marks held after the scene too (while the
    # scene is over the screen a glance does not count: it looks through it).
    window._check_started = None
    window._live_check = False
    assert window.play_quick_scene()
    window.love.stop()
    assert not window._border_on_screen()
    window._on_glanced("ok", False)
    assert window.panel.isVisible() and window.clear_mark.isVisible() and window._quick_scene


def test_in_stream_mode_it_reaches_the_stream_window(window, monkeypatch):
    from blacklist_detect import ui

    # 基础模式 with 直播模式: a check's marks go only into 直播画面; the hotkey's play is on the screen too, the
    # player pressed it to see it.
    window._on_display_mode("safe")
    window._set_stream_mode(True)
    assert window._overlay_target() == "stream"
    screen = window.screen().geometry()
    ratio = window.screen().devicePixelRatio()
    game_window = livehime.Capture("MuMu安卓设备", "Qt5QWindowIcon", "MuMuNxDevice.exe", True)
    left, top = screen.x(), screen.y()
    native = (left + round(100 * ratio), top + round(80 * ratio), left + round(900 * ratio), top + round(580 * ratio))
    monkeypatch.setattr(livehime, "game_capture", lambda scene, title: game_window)
    monkeypatch.setattr(livehime, "client_rect", lambda capture: native)
    monkeypatch.setattr(ui, "inner_rect_of", lambda _hwnd, _x, _y: None)
    assert window.play_quick_scene()
    # The game's window is the one 直播姬 captures; the game, 16:9, in it.
    captured = QRect(screen.x() + 100, screen.y() + 80, 800, 500)
    assert window.stream._frame == captured
    assert captured.contains(window.love.geometry()) and window.love.geometry().width() == 800
    for mark in (window.panel, window.clear_mark, window.love):
        assert not mark.testAttribute(Qt.WA_DontShowOnScreen) and mark.isVisible()
    assert window.panel in window.stream._marks() and window.clear_mark in window.stream._marks()
    assert window.stream._borders() == [window.love] and window.stream.busy()
    assert not window.stream.grab().isNull()
    window._end_quick_play()
    assert window.stream._frame == QRect() and not window.stream.busy()
    # Over: a check's marks only for the stream again.
    marks = (window.panel, window.hit_card, window.like_card, window.clear_mark, window.love, window.alert)
    assert all(mark.testAttribute(Qt.WA_DontShowOnScreen) for mark in marks)


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
    assert "场景 hotkey: angel over the screen under the pointer" in said
    assert "场景 hotkey shown: 嘉宾场景 (angel" in said and "场景 hotkey: done." in said


def test_in_safe_mode_without_stream_mode_it_plays_on_the_screen_all_the_same(window):
    # 基础模式, as every player starts: a check draws nothing over the game, but the hotkey, pressed to see its
    # 场景, plays it on the screen, under the pointer, music and all.
    window._on_display_mode("safe")
    assert window._overlay_target() == "" and not window.store.stream_mode
    assert window.effect_hotkey.callback()
    for mark in (window.panel, window.clear_mark, window.love):
        assert not mark.testAttribute(Qt.WA_DontShowOnScreen) and mark.isVisible()
    assert window.love.playing() and window._quick_scene and window.played and window.played[-1] != "stop"
    window._end_quick_play()
    assert not window.panel.isVisible() and not window.love.playing() and window._quick_scene == ""


def test_safe_mode_takes_a_play_down_music_and_all(window):
    window.store.quick_scene = "claw"
    assert window.play_quick_scene()
    window._on_display_mode("safe")
    assert window._quick_scene == "" and window._game_box is None and window._quick_area is None
    assert not window.panel.isVisible() and not window.love.playing() and window.played[-1] == "stop"


def test_stream_mode_off_in_safe_mode_takes_a_play_down_music_and_all(window):
    window._on_display_mode("safe")
    window._set_stream_mode(True)
    window.store.quick_scene = "claw"
    assert window.play_quick_scene()
    _started(window)
    assert window.played == ["claw"]
    window._set_stream_mode(False)
    assert window._quick_scene == "" and window._quick_area is None and window._game_box is None
    assert not window.panel.isVisible() and not window.love.playing() and window.played[-1] == "stop"
    # In 完整模式 the play goes on over the screen.
    window._on_display_mode("full")
    window._set_stream_mode(True)
    assert window.play_quick_scene()
    window._set_stream_mode(False)
    assert window._quick_scene == "claw" and window.played[-1] == "claw"


def test_picking_a_scene_mid_play_leaves_the_plays_music(window):
    page = window.effects_page
    window.show()
    window._show_scene_manager()
    QApplication.processEvents()
    window.store.quick_scene = "stars"
    assert window.play_quick_scene()
    assert window.played == ["stars"]
    page.scenes.buttons["fluffy"].click()
    assert window.played == ["stars"] and window.love.scene == "stars"
    # ▶ 播放 takes the music over; the play cut short then leaves it, and a pick stops it.
    page.play_button.click()
    assert window.played[-1] == "fluffy" and page.sounding
    window._end_quick_play()
    assert window.played[-1] == "fluffy"
    page.scenes.buttons["ice"].click()
    assert window.played[-1] == "stop"
    window.hide()


def test_nothing_plays_before_the_disclaimer_is_agreed_to(window):
    window.store.disclaimer_accepted = False
    assert not window.play_quick_scene() and not window.love.playing() and not window.panel.isVisible()


def _native(window, rect: QRect) -> tuple[int, int, int, int]:  # noqa: ANN001
    """A rect in Qt's units on the window's screen, in desktop pixels, as Windows gives them."""
    screen = window.screen().geometry()
    ratio = window.screen().devicePixelRatio()
    left = screen.x() + round((rect.x() - screen.x()) * ratio)
    top = screen.y() + round((rect.y() - screen.y()) * ratio)
    return left, top, left + round(rect.width() * ratio), top + round(rect.height() * ratio)


def test_with_stream_mode_it_plays_on_the_game_not_on_mumus_bar(window, monkeypatch):
    from blacklist_detect import ui

    window._on_display_mode("safe")
    window._set_stream_mode(True)
    screen = window.screen().geometry()
    game_window = livehime.Capture("MuMu安卓设备", "Qt5QWindowIcon", "MuMuNxDevice.exe", True)
    # MuMu's window: its own bar of 49 px over a 16:9 game.
    whole = QRect(screen.x() + 100, screen.y() + 80, 800, 499)
    game = QRect(screen.x() + 100, screen.y() + 129, 800, 450)
    monkeypatch.setattr(livehime, "game_capture", lambda scene, title: game_window)
    monkeypatch.setattr(livehime, "client_rect", lambda capture: _native(window, whole))
    monkeypatch.setattr(livehime, "window_of", lambda capture: 77)
    # Another program's window in front of MuMu's middle on the screen: 直播姬 captures MuMu all the same.
    cover = QRect(screen.x() + 400, screen.y() + 250, 420, 300)
    monkeypatch.setattr(ui, "window_rect_at", lambda _x, _y, _order=(), innermost=True: _native(window, cover))
    asked: list[int] = []
    monkeypatch.setattr(ui, "inner_rect_of", lambda hwnd, _x, _y: asked.append(hwnd) or _native(window, game))
    assert window.play_quick_scene()
    # The game is MuMu's own window in its middle, never what covers it.
    assert asked == [77]
    assert window.love.geometry() == game and game.contains(window.panel.cover_geometry())
    # 直播画面 is the whole window, bar and all, as 直播姬 captures it.
    assert window.stream._frame == whole
    window._end_quick_play()
    # MuMu's own window not found: the whole window it is.
    monkeypatch.setattr(ui, "inner_rect_of", lambda hwnd, _x, _y: None)
    assert window.play_quick_scene()
    assert window.love.geometry() == window._sixteen_nine(whole)


def test_with_no_lobby_yet_it_plays_on_the_window_under_the_pointer(window, monkeypatch):
    from blacklist_detect import ui

    screen = window.screen().geometry()
    # An emulator in a window, not the whole screen.
    game = QRect(screen.x() + 40, screen.y() + 30, 640, 360)
    monkeypatch.setattr(ui, "window_rect_at", lambda _x, _y, _order=(), innermost=True: _native(window, game))
    assert window.play_quick_scene()
    assert window.love.geometry() == game and game.contains(window.panel.cover_geometry())
    window._end_quick_play()
    # A small one (a button, a tooltip) is not the game: the screen is.
    tip = QRect(screen.x() + 40, screen.y() + 30, 60, 30)
    monkeypatch.setattr(ui, "window_rect_at", lambda _x, _y, _order=(), innermost=True: _native(window, tip))
    assert window.play_quick_scene()
    assert window.love.geometry().width() > 640


def test_in_stream_mode_the_hotkey_plays_on_mumus_game(window, monkeypatch):
    from blacklist_detect import ui

    screen = window.screen().geometry()
    # In 直播模式, MuMu's game, not the window under the pointer.
    window._set_stream_mode(True)
    game_window = livehime.Capture("MuMu安卓设备", "Qt5QWindowIcon", "MuMuNxDevice.exe", True)
    whole = QRect(screen.x() + 100, screen.y() + 80, 800, 499)
    game = QRect(screen.x() + 100, screen.y() + 129, 800, 450)
    monkeypatch.setattr(livehime, "game_capture", lambda scene, title: game_window)
    monkeypatch.setattr(livehime, "client_rect", lambda capture: _native(window, whole))
    monkeypatch.setattr(livehime, "window_of", lambda capture: 77)
    monkeypatch.setattr(ui, "inner_rect_of", lambda hwnd, _x, _y: _native(window, game))
    assert window.play_quick_scene()
    assert window.love.geometry() == game and window.stream._frame == whole
    window._end_quick_play()
    window._set_stream_mode(False)


def test_each_hotkey_runs_only_its_own_action(window):
    import ctypes

    if not window.hotkey.supported:
        pytest.skip("Windows' hotkeys only")
    from ctypes import wintypes

    calls: list[str] = []
    window.hotkey.callback = lambda: calls.append("check")
    window.effect_hotkey.callback = lambda: calls.append("effect")
    for ident in (1, 2, 3):
        msg = wintypes.MSG()
        msg.message = 0x0312
        msg.wParam = ident
        for keeper in (window.hotkey, window.effect_hotkey):
            keeper._filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))
    assert calls == ["check", "effect"]


def test_the_window_shortcuts_are_keys_for_the_box_while_it_waits(window):
    from PySide6.QtTest import QTest

    window.show()
    window.activateWindow()
    window.check_panel.open_panel()
    edit = window.hotkey_edit
    edit.setFocus()
    QApplication.processEvents()
    assert window.hotkey.active == "" and window.effect_hotkey.active == ""
    # Ctrl+3 is 嘉宾's shortcut elsewhere; here it is the key pressed for 检查.
    QTest.keyClick(edit, Qt.Key_3, Qt.KeyboardModifier.ControlModifier)
    assert window.store.hotkey == "Ctrl+3" and window.tabs.currentIndex() == window.history_tab
    # Closed while it waits, the box lets go: both hotkeys work again.
    edit.setFocus()
    QApplication.processEvents()
    assert window.hotkey.active == ""
    window.check_panel.close_panel()
    assert not edit.hasFocus() and window.hotkey.active == "Ctrl+3" and window.effect_hotkey.active == "Alt+F12"
    window.hide()


@pytest.mark.parametrize("key", ["Q", "Shift+Q", "Ctrl+S", "ctrl+v", "Alt+F4", "Win+D", "Shift+F10", "F12", "Ctrl+Shift+C"])
def test_a_check_key_from_before_that_is_no_hotkey_now_is_alt_1_and_the_player_is_told(tmp_path, monkeypatch, key):
    window = _opened_with(tmp_path, monkeypatch, hotkey=key)
    assert window.store.hotkey == "Alt+1" and window.hotkey.active == "Alt+1" and window.hotkey_edit.text() == "Alt+1"
    # The header shows the key that checks, never the one that no longer does.
    assert window.status_chip.text() == "手动检查" and window.status_chip.key_text() == "Alt+1"
    assert window.settings_label.text() == f"快捷键 {key} 已不能用，换成了 Alt+1" and not window.settings_label.isHidden()
    assert window._how_to_check() == "在「推演成功」大厅按 Alt+1 检查"
    assert "手动检查 (Alt+1)" in window.settings_line()
    # Saved as Alt+1: the next start says nothing.
    window.store.save_settings()
    window.close()
    again = type(window)()
    again._watch_timer.stop()
    assert again.store.hotkey == "Alt+1" and again.settings_label.text() == ""
    again.close()


def test_a_dropped_check_key_whose_default_the_effect_hotkey_has_asks_for_another(tmp_path, monkeypatch):
    window = _opened_with(tmp_path, monkeypatch, hotkey="Shift+A", effect_hotkey="Alt+1")
    assert window.store.hotkey == "" and window.hotkey.active == "" and window.effect_hotkey.active == "Alt+1"
    assert window.status_chip.key_text() == "" and window.settings_label.text() == "快捷键 Shift+A 已不能用，换一个"
    window.close()


def test_a_dropped_effect_key_is_alt_f12_and_the_page_says_so(tmp_path, monkeypatch):
    window = _opened_with(tmp_path, monkeypatch, effect_hotkey="Ctrl+C")
    assert window.effect_hotkey.active == "Alt+F12" and window.effect_hotkey_edit.text() == "Alt+F12"
    assert window.effects_page.note.text() == "场景快捷键 Ctrl+C 已不能用，换成了 Alt+F12"
    assert window.settings_label.text() == ""
    window.close()


def test_the_header_never_shows_a_check_key_that_is_none(window):
    window.store.hotkey = "Shift+Q"
    window._sync_watch_idle()
    assert window.status_chip.text() == "手动检查" and window.status_chip.key_text() == ""
    window.store.hotkey = "alt+q"
    window._sync_watch_idle()
    assert window.status_chip.key_text() == "Alt+Q"


def test_a_key_another_program_holds_keeps_the_one_before(window, monkeypatch):
    held = (0x31, 0x70)  # 1 and F1: another program has them.
    monkeypatch.setattr(hotkey, "_register", lambda ident, modifiers, vk: vk not in held)
    edit = window.effect_hotkey_edit
    _press(edit, Qt.Key_F1, Qt.KeyboardModifier.AltModifier)
    assert window.effects_page.note.text() == "这个键被别的程序占了，换一个"
    assert window.store.effect_hotkey == "Alt+F12" and Store(window.store.root).effect_hotkey == "Alt+F12"
    assert edit.text() == "Alt+F12" and window.effect_hotkey.active == "Alt+F12"
    # F12 alone Windows keeps for itself: refused as no key, not blamed on another program.
    _press(edit, Qt.Key_F12)
    assert window.effects_page.note.text() == "这个键用不了，换一个" and window.store.effect_hotkey == "Alt+F12"
    assert hotkey.parse_hotkey("F12") is None and hotkey.parse_hotkey("Alt+F12") is not None


def test_a_hotkey_that_did_not_register_at_start_says_so(window, monkeypatch):
    window.effect_hotkey.clear()
    window.hotkey.clear()
    monkeypatch.setattr(hotkey, "_register", lambda ident, modifiers, vk: False)
    window._restore_hotkey()
    assert window.effect_hotkey_edit.text() == "Alt+F12" and window.effect_hotkey.active == ""
    assert window.effects_page.note.text() == "这个键被别的程序占了，换一个"
    assert window.settings_label.text() == "这个键被别的程序占了，换一个"
    # So it does for a key in place of one dropped: that it does not work is what the player needs to know.
    window.store.dropped_hotkey = "Shift+Q"
    window.store.dropped_effect_hotkey = "Ctrl+C"
    window._restore_hotkey()
    assert window.effects_page.note.text() == "这个键被别的程序占了，换一个"
    assert window.settings_label.text() == "这个键被别的程序占了，换一个"


def test_the_note_that_the_effect_key_did_not_register_goes_once_it_does(window, monkeypatch):
    window.effect_hotkey.clear()
    monkeypatch.setattr(hotkey, "_register", lambda ident, modifiers, vk: False)
    window._sync_effect_hotkey()
    assert window.effects_page.note.text() == "这个键被别的程序占了，换一个" and not window.effects_page.note.isHidden()
    # The other program let go of it: taken as 检查's box lets go of both, the note goes.
    monkeypatch.setattr(hotkey, "_register", lambda ident, modifiers, vk: True)
    window._end_hotkey(window.hotkey_edit)
    assert window.effect_hotkey.active == "Alt+F12" and window.effects_page.note.isHidden()
    # A note about a key pressed in the box stays, the key before it taken back; so does 播放's.
    monkeypatch.setattr(hotkey, "_register", lambda ident, modifiers, vk: vk != 0x70)
    _press(window.effect_hotkey_edit, Qt.Key_F1, Qt.KeyboardModifier.AltModifier)
    assert window.effect_hotkey.active == "Alt+F12" and window.effects_page.note.text() == "这个键被别的程序占了，换一个"
    window.effects_page.say("正在检查，稍后再试")
    window._end_hotkey(window.hotkey_edit)
    assert window.effects_page.note.text() == "正在检查，稍后再试"


def test_the_note_that_checks_key_did_not_register_goes_once_it_does(window, monkeypatch):
    window.hotkey.clear()
    monkeypatch.setattr(hotkey, "_register", lambda ident, modifiers, vk: False)
    window._sync_hotkey_mode()
    assert window.settings_label.text() == "这个键被别的程序占了，换一个" and not window.settings_label.isHidden()
    # The other program let go of it: taken as the 场景 box lets go of both, the note goes.
    monkeypatch.setattr(hotkey, "_register", lambda ident, modifiers, vk: True)
    window._end_hotkey(window.effect_hotkey_edit)
    assert window.hotkey.active == "Alt+1" and window.settings_label.isHidden()
    # And with 自动检查, which takes no hotkey.
    window.hotkey.clear()
    monkeypatch.setattr(hotkey, "_register", lambda ident, modifiers, vk: False)
    window._sync_hotkey_mode()
    assert not window.settings_label.isHidden()
    window._on_auto_mode("auto")
    assert window.settings_label.isHidden() and window.settings_label.text() == ""
    # A note about a key pressed in the box stays, the key before it taken back or not.
    window._on_auto_mode("manual")
    monkeypatch.setattr(hotkey, "_register", lambda ident, modifiers, vk: vk != 0x70)
    _press(window.hotkey_edit, Qt.Key_F1, Qt.KeyboardModifier.AltModifier)
    assert window.hotkey.active == "Alt+1" and window.settings_label.text() == "这个键被别的程序占了，换一个"


def test_starting_over_puts_the_effect_hotkey_and_page_back(window, monkeypatch):
    page = window.effects_page
    page.scenes.buttons["claw"].click()
    page.scenes.ticked.emit("claw")
    _press(window.effect_hotkey_edit, Qt.Key_9, Qt.KeyboardModifier.ControlModifier)
    QApplication.instance().sendEvent(window.effect_hotkey_edit, QFocusEvent(QEvent.Type.FocusOut))
    page.say("最多两个键，比如 Alt+1")
    assert window.play_quick_scene()
    # Opened again, the app has them as they were saved.
    again = type(window)()
    assert again.store.effect_hotkey == "Ctrl+9" and again.effect_hotkey_edit.text() == "Ctrl+9"
    assert again.effect_hotkey.active == "Ctrl+9" and again.effects_page.scenes.key == "claw"
    again.close()
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda *_args: True)
    window._ask_reset()
    assert window._quick_scene == "" and not window.love.playing()
    assert window.store.quick_scene == "classic" and window.store.effect_hotkey == "Alt+F12"
    assert window.effect_hotkey.active == "Alt+F12" and window.effect_hotkey_edit.text() == "Alt+F12"
    assert page.scenes.key == "classic" and page.scenes.buttons["classic"].isChecked() and page.note.isHidden()


def test_the_hotkey_row_is_whole_the_first_time_the_dialog_opens(window):
    window.resize(900, 560)
    window.show()
    QApplication.processEvents()
    window._show_scene_manager()
    QApplication.processEvents()
    page = window.effects_page
    for widget in (window.effect_hotkey_edit, page.play_button):
        assert widget.mapTo(page, widget.rect().bottomLeft()).y() < page.height()
    # A note under it comes and goes without moving the preview or the dialog.
    size, card = page.preview.size(), window.scenes_dialog.card.size()
    page.say("最多两个键，比如 Alt+1")
    QApplication.processEvents()
    assert page.preview.size() == size and window.scenes_dialog.card.size() == card
    page.say("")
    QApplication.processEvents()
    assert page.preview.size() == size and window.scenes_dialog.card.size() == card
    window.scenes_dialog.reject()
    window.hide()


def test_the_dialog_opens_on_the_scene_list_and_closes_with_esc_or_its_x(window):
    """The hotkey box would take the next key pressed for the 场景 hotkey: the dialog never opens on it,
    even after it was used last."""
    from PySide6.QtTest import QTest

    page, dialog = window.effects_page, window.scenes_dialog
    window.show()
    for close in (lambda: QTest.keyClick(dialog, Qt.Key_Escape), dialog.close_button.click):
        window._show_scene_manager()
        QApplication.processEvents()
        assert dialog.isVisible() and dialog.focusWidget() is page.scenes.buttons[page.scenes.key]
        assert not window.effect_hotkey_edit.hasFocus() and window.effect_hotkey.active == "Alt+F12"
        window.effect_hotkey_edit.setFocus()
        QApplication.processEvents()
        assert dialog.focusWidget() is window.effect_hotkey_edit
        close()
        QApplication.processEvents()
        assert not dialog.isVisible() and not page.preview._tick.isActive()
    window.hide()


def test_the_dialog_opens_on_a_still_and_a_click_plays(window):
    """A scene takes up to a second to make: 场景管理 opens on the shown one still, a click in the list plays one
    (made just after the click is seen), ▶ plays at once, and coming back opens on a still again."""
    page = window.effects_page
    window.show()
    window._show_scene_manager()
    QApplication.processEvents()
    assert page.preview.is_still and page.preview._paint is None and not page.preview._tick.isActive()
    page.scenes.buttons["ice"].click()
    assert page.preview.scene == "ice" and not page.preview.is_still
    _wait(60)
    made = page.preview._paint
    assert made is not None and page.preview._tick.isActive() and window.played == []
    window.scenes_dialog.reject()
    window._show_scene_manager()
    QApplication.processEvents()
    assert page.preview.is_still and page.preview.scene == "ice" and not page.preview._tick.isActive()
    # ▶ plays it with its music, not made again.
    page.play_button.click()
    assert page.preview._paint is made and page.preview._tick.isActive() and window.played[-1] == "ice"
    # With another app in front, it rests; it plays again as the app comes back.
    page._app_state(Qt.ApplicationState.ApplicationInactive)
    assert not page.preview._tick.isActive()
    page._app_state(Qt.ApplicationState.ApplicationActive)
    assert page.preview._tick.isActive() and page.preview._paint is made
    window.hide()


def test_the_preview_keeps_in_step_with_its_music_and_rests_while_minimized(window):
    page = window.effects_page
    window.show()
    window._show_scene_manager()
    QApplication.processEvents()
    page.play_button.click()
    _wait(120)
    # Another app in front and back: ▶'s music played on, and the scene goes on with it.
    page._app_state(Qt.ApplicationState.ApplicationInactive)
    page._app_state(Qt.ApplicationState.ApplicationActive)
    assert page.preview._tick.isActive() and page.preview._clock.elapsed() >= 100
    # With no music, from its start.
    page.scenes.buttons["fluffy"].click()
    _wait(120)
    page._app_state(Qt.ApplicationState.ApplicationInactive)
    page._app_state(Qt.ApplicationState.ApplicationActive)
    assert page.preview._clock.elapsed() < 100
    # Minimized, it rests, the app in front or not; restored, it plays.
    window.showMinimized()
    QApplication.processEvents()
    page._app_state(Qt.ApplicationState.ApplicationActive)
    assert window.isMinimized() and not page.preview._tick.isActive()
    window.showNormal()
    QApplication.processEvents()
    page._app_state(Qt.ApplicationState.ApplicationActive)
    assert page.preview._tick.isActive()
    window.hide()


def test_music_from_the_preview_stops_as_the_dialog_closes(window):
    page = window.effects_page
    window.show()
    window._show_scene_manager()
    QApplication.processEvents()
    page.play_button.click()
    assert window.played == ["classic"]
    window.scenes_dialog.reject()
    assert window.played == ["classic", "stop"]
    # The hotkey's play's music, though, plays on.
    window._show_scene_manager()
    assert window.play_quick_scene()
    window.scenes_dialog.reject()
    assert window.played[-1] == "classic"
    window.hide()


def test_a_real_lobbys_music_plays_on_whatever_the_page_does(window, monkeypatch):
    from blacklist_detect import ui

    page = window.effects_page
    window.show()
    window._show_scene_manager()
    QApplication.processEvents()
    page.play_button.click()
    assert page.sounding and window.played == ["classic"]
    # A real lobby with a 嘉宾 in it, its music after ▶'s.
    monkeypatch.setattr(window, "_likes_in", lambda _result: [ui.Entry("心动小鹿")])
    monkeypatch.setattr(window, "_choice_for", lambda _likes, _blacklisted: ("guest", "stars"))
    window._live_check = True
    screen = window.screen().geometry()
    button = (screen.x() + 600, screen.y() + 700, screen.x() + 800, screen.y() + 760)
    window._show_panel(CheckResult(header_found=True, message="", button_box=button))
    assert window.played == ["classic", "stars"] and not page.sounding
    # Picking on 场景 and leaving it stop nothing.
    page.scenes.buttons["fluffy"].click()
    window.scenes_dialog.reject()
    assert len(window.played) == 2
    window._hide_panel_after_title()
    window.hide()


def test_stream_mode_switched_on_in_safe_mode_takes_a_play_down_music_and_all(window):
    """基础模式 alone plays the hotkey's 场景 on the screen; 直播模式 switched on meanwhile ends it, as switched off
    does, and a check's marks are only for the stream again."""
    window._on_display_mode("safe")
    assert window.play_quick_scene() and window.love.playing()
    window._set_stream_mode(True)
    assert window._quick_scene == "" and not window.love.playing() and window.played[-1] == "stop"
    assert all(mark.testAttribute(Qt.WA_DontShowOnScreen) for mark in (window.panel, window.love, window.clear_mark))
