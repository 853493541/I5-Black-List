"""场景管理 (ui_effects): the 场景 page shows a 场景 apart from the one the hotkey plays, and sets each 场景's
sound (the player's own, cut in 选择片段 when it is long) and 音量. Made-up sounds and file dialogs only:
nothing is played aloud, and every file is in the test's own folder."""

import json
import os
import time
import wave

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog, QFileDialog  # noqa: E402

from blacklist_detect import sound_import  # noqa: E402
from blacklist_detect.paths import custom_sound_dir  # noqa: E402
from blacklist_detect.storage import Store  # noqa: E402
from blacklist_detect.ui_love_pick import SceneList  # noqa: E402
from blacklist_detect.ui_music import _COPY, TUNES, sound_dir  # noqa: E402
from blacklist_detect.ui_sound_trim import SoundTrimDialog  # noqa: E402

SOUNDS = os.path.join(os.path.dirname(__file__), "fixtures", "sounds")


def _wav(path, seconds: float, pitch: float = 440.0):  # noqa: ANN001, ANN202
    """A made-up tone, mono 16-bit at 44.1 kHz."""
    t = np.arange(round(seconds * 44100)) / 44100
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes((np.sin(2 * np.pi * pitch * t) * 12000).astype("<i2").tobytes())
    return path


def _wait(ms: int) -> None:
    end = time.time() + ms / 1000
    while time.time() < end:
        QApplication.processEvents()
        time.sleep(0.01)


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    made = MainWindow()
    made._watch_timer.stop()
    made.store.disclaimer_accepted = True
    made.store.consented = ["full"]
    made._on_display_mode("full")
    # What would be played, never aloud: a file, or None to stop.
    played: list = []
    made.music._play = played.append
    made.played = played
    QApplication.processEvents()
    yield made
    made._end_quick_play()
    made.notice.hide()
    made.close()


@pytest.fixture
def pick(monkeypatch):  # noqa: ANN201
    """上传's file dialog, answered with the file set in chosen; asked keeps how it was asked."""
    state = {"chosen": "", "asked": []}

    def ask(*args):  # noqa: ANN002, ANN202
        state["asked"].append(args)
        return str(state["chosen"]), ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", ask)
    return state


@pytest.fixture
def trim(monkeypatch):  # noqa: ANN201
    """选择片段, answered by do(dialog) -> accepted or not; opened keeps each one opened."""
    state = {"opened": [], "do": lambda dialog: True}

    def run(dialog):  # noqa: ANN001, ANN202
        state["opened"].append(dialog)
        return QDialog.Accepted if state["do"](dialog) else QDialog.Rejected

    monkeypatch.setattr(SoundTrimDialog, "exec", run)
    return state


def _copies(stem: str) -> list:
    """The quieter copies of the tune called stem in sounds/."""
    return [copy for copy in sound_dir().iterdir() if (found := _COPY.fullmatch(copy.name)) and found[2] == stem]


def _shown(window, key: str):  # noqa: ANN001, ANN202
    page = window.effects_page
    page.scenes.buttons[key].click()
    return page


def test_a_click_shows_a_scene_and_only_its_button_gives_it_the_hotkey(window):
    page = _shown(window, "stars")
    store = window.store
    assert page.scenes.key == "stars" and store.quick_scene == "classic"
    # ✓ on the hotkey's, the band on the one shown.
    assert page.scenes.buttons["classic"].tick and not page.scenes.buttons["stars"].tick
    assert page.scenes.buttons["stars"].isChecked() and not page.scenes.buttons["classic"].isChecked()
    assert page.assign_button.isEnabled()
    page.assign_button.click()
    assert store.quick_scene == "stars" and Store(store.root).quick_scene == "stars"
    assert page.scenes.buttons["stars"].tick and not page.scenes.buttons["classic"].tick
    assert not page.assign_button.isEnabled()
    _shown(window, "ice")
    assert page.assign_button.isEnabled() and store.quick_scene == "stars"


def test_the_picker_dialog_keeps_its_tick_on_the_one_picked():
    QApplication.instance() or QApplication([])
    scenes = SceneList("ice")
    assert scenes.buttons["ice"].tick is None
    scenes.buttons["stars"].click()
    assert scenes.key == "stars" and all(button.tick is None and not button.own for button in scenes.buttons.values())


def test_play_plays_the_one_shown_and_the_hotkey_its_own(window):
    page = _shown(window, "fluffy")
    page.play_button.click()
    assert window._quick_scene == "fluffy" and window.love.scene == "fluffy" and window.store.quick_scene == "classic"
    window._end_quick_play()
    assert window.effect_hotkey.callback()
    assert window._quick_scene == "classic"


def test_the_rows_say_what_each_effect_plays(window):
    page = _shown(window, "classic")
    assert page.sound_text.full == "默认 · 无" and page.upload_button.text() == "上传"
    assert page.reset_button.isHidden() and not page.volume_slider.isEnabled()
    _shown(window, "ice")
    assert page.sound_text.full == "默认" and page.reset_button.isHidden() and page.volume_slider.isEnabled()
    assert page.volume_slider.value() * 5 == 100 and page.volume_label.text() == "100%" and page.level_note.text() == ""


def test_an_old_volume_folded_below_5_says_what_it_plays_until_moved(window):
    """声音 folded in from v0.9.14 may leave a 场景 at 1 to 4%: the slider stands at 0, the label and the sound say
    what is heard, and moved it goes back to steps of 5."""
    window.store.scene_sounds = {"ice": {"volume": 2}}
    page = _shown(window, "ice")
    assert page.volume_slider.value() == 0 and page.volume_label.text() == "2%" and window.music.level("ice") == 2
    page.volume_slider.setValue(1)
    assert window.store.scene_sounds == {"ice": {"volume": 5}} and page.volume_label.text() == "5%"

def test_volume_is_saved_per_effect_and_heard_as_it_is_let_go(window):
    page = _shown(window, "ice")
    window.played.clear()
    page.volume_slider.setValue(16)
    store = window.store
    assert store.scene_sounds == {"ice": {"volume": 80}} and Store(store.root).scene_sound("ice") == (None, 80)
    assert page.volume_label.text() == "80%"
    # A moment of it at that.
    assert window.played[-1].name.startswith(f"80-{TUNES['ice'].stem}-") and window.played[-1].parent == sound_dir()
    # Dragged, it is heard once let go.
    window.played.clear()
    page.volume_slider.setSliderDown(True)
    page.volume_slider.setValue(10)
    assert window.played == [] and store.scene_sounds["ice"] == {"volume": 50}
    page.volume_slider.setSliderDown(False)
    assert window.played[-1].name.startswith("50-")
    # Back at 100%, nothing is kept for it.
    page.volume_slider.setValue(20)
    assert store.scene_sounds == {} and "ice" not in Store(store.root).scene_sounds
    # Another 场景 shows its own.
    _shown(window, "stars")
    assert page.volume_slider.value() == 20
    # Under 静音 it is saved, and nothing plays.
    window.mute_box.click()
    window.played.clear()
    page.volume_slider.setValue(12)
    assert window.played == [] and store.scene_sounds["stars"] == {"volume": 60}


def test_the_note_beside_volume_says_only_that_it_is_muted(window):
    """音量 is how loud a 场景 is heard, so beside it is only 已静音, under 设置's 静音."""
    page = _shown(window, "ice")
    page.volume_slider.setValue(16)
    assert page.level_note.text() == ""
    window.mute_box.click()
    assert page.level_note.text() == "已静音"
    # 经典 with none of the player's has no 音量 to speak of.
    _shown(window, "classic")
    assert page.level_note.text() == ""
    _shown(window, "ice")
    assert page.level_note.text() == "已静音"
    window.mute_box.click()
    assert page.level_note.text() == ""
    # 清空数据's 静音 off again.
    window.mute_box.click()
    window.store.sound_muted = False
    window._sync_sound()
    assert page.level_note.text() == "" and not window.mute_box.isChecked()


def test_a_short_sound_is_kept_whole_marked_and_played_once(window, pick, trim, tmp_path):
    page = _shown(window, "ice")
    page.volume_slider.setValue(14)
    window.played.clear()
    pick["chosen"] = _wav(tmp_path / "心动音乐.wav", 3.0)
    page.upload_button.click()
    parent, title, folder, kinds = pick["asked"][-1]
    assert parent is page and "冰蓝极光" in title and folder == ""
    assert kinds in (f"声音或视频 ({sound_import.FILTER})", f"WAV 声音 ({sound_import.WAV_FILTER})")
    assert trim["opened"] == []
    own = custom_sound_dir(window.store.root) / "ice.wav"
    assert own.is_file()
    entry = window.store.scene_sounds["ice"]
    assert entry["volume"] == 70 and entry["file"] == "ice.wav" and entry["name"] == "心动音乐.wav"
    assert entry["start"] == 0 and entry["length"] == pytest.approx(3.0)
    assert Store(window.store.root).scene_sounds["ice"] == entry
    # ♪ on it, its rows its own, and a moment of it at its 音量.
    assert page.scenes.buttons["ice"].own and not page.scenes.buttons["stars"].own
    assert page.sound_text.full == "自定义 · 心动音乐.wav · 3.0 秒"
    assert page.upload_button.text() == "替换" and not page.reset_button.isHidden()
    assert window.played[-2] is None and window.played[-1].name.startswith("70-ice-")
    assert window.music.pick("ice") == "ice" and page.note.isHidden()


def test_a_long_sound_is_cut_to_the_part_picked(window, pick, trim, tmp_path):
    page = _shown(window, "stars")
    pick["chosen"] = _wav(tmp_path / "long.wav", 12.0)

    def choose(dialog) -> bool:  # noqa: ANN001
        assert dialog.windowTitle() == "选择片段" and dialog.play_button.isEnabled()
        dialog.wave.set_selection(4.0, 3.0)
        # 试听: the part as it will sound, from a folder of the page's own.
        window.played.clear()
        dialog.toggle_preview()
        trial = window.played[-1]
        assert trial.is_file() and trial.parent != sound_dir() and custom_sound_dir(window.store.root) not in trial.parents
        trim["trial"] = trial
        with wave.open(str(trial)) as wav:
            assert wav.getnframes() == round(3.0 * 44100)
        return True

    trim["do"] = choose
    page.upload_button.click()
    assert len(trim["opened"]) == 1
    # The trial and its folder go with the dialog.
    assert not trim["trial"].exists() and not trim["trial"].parent.exists()
    entry = window.store.scene_sounds["stars"]
    assert (entry["start"], entry["length"]) == (pytest.approx(4.0), pytest.approx(3.0))
    with wave.open(str(custom_sound_dir(window.store.root) / "stars.wav")) as wav:
        assert wav.getnframes() == round(3.0 * 44100)
    assert page.sound_text.full == "自定义 · long.wav · 3.0 秒"


def test_a_trial_plays_at_the_effect_s_level(window, pick, trim, tmp_path):
    page = _shown(window, "stars")
    page.volume_slider.setValue(10)
    pick["chosen"] = _wav(tmp_path / "long.wav", 8.0)

    def listen(dialog) -> bool:  # noqa: ANN001
        dialog.toggle_preview()
        trim["heard"] = window.played[-1].name
        return False

    trim["do"] = listen
    page.upload_button.click()
    assert trim["heard"].startswith("50-trial-")


def test_closing_the_part_picker_changes_nothing(window, pick, trim, tmp_path):
    page = _shown(window, "stars")
    pick["chosen"] = _wav(tmp_path / "long.wav", 8.0)
    trim["do"] = lambda dialog: False
    window.played.clear()
    page.upload_button.click()
    assert len(trim["opened"]) == 1 and window.store.scene_sounds == {}
    assert not (custom_sound_dir(window.store.root) / "stars.wav").exists() and not page.scenes.buttons["stars"].own
    assert all(tune is None for tune in window.played)
    # Nor does a file dialog closed.
    pick["chosen"] = ""
    page.upload_button.click()
    assert window.store.scene_sounds == {} and len(trim["opened"]) == 1


def test_under_mute_a_trial_cannot_be_played_and_nothing_is(window, pick, trim, tmp_path):
    window.mute_box.click()
    page = _shown(window, "stars")
    pick["chosen"] = _wav(tmp_path / "long.wav", 8.0)

    def muted(dialog) -> bool:  # noqa: ANN001
        assert not dialog.play_button.isEnabled() and dialog.play_button.toolTip() == "已静音"
        dialog.toggle_preview()
        assert not dialog.playing
        return True

    trim["do"] = muted
    window.played.clear()
    page.upload_button.click()
    assert window.store.scene_sounds["stars"]["file"] == "stars.wav"
    assert all(tune is None for tune in window.played)


def test_a_file_that_cannot_be_used_says_why_until_another_is_shown(window, pick, trim, tmp_path):
    page = _shown(window, "stars")
    empty = tmp_path / "empty.mp3"
    empty.write_bytes(b"")
    pick["chosen"] = empty
    page.upload_button.click()
    assert page.note.text() == "这个文件是空的" and not page.note.isHidden()
    assert window.store.scene_sounds == {} and trim["opened"] == []
    assert QApplication.overrideCursor() is None and window.isEnabled()
    _shown(window, "ice")
    assert page.note.isHidden()
    # A note about the hotkey as it stands comes back after one about a sound.
    page.say("这个键被别的程序占了，换一个", held=True)
    page.upload_button.click()
    assert page.note.text() == "这个文件是空的"
    _shown(window, "stars")
    assert page.note.text() == "这个键被别的程序占了，换一个" and page.held


def test_nothing_changes_under_a_file_being_read(window, pick, trim, tmp_path, monkeypatch):
    page = _shown(window, "lace")
    read = sound_import.decode
    seen = {}

    def slow(path):  # noqa: ANN001, ANN202
        # The player clicks around while it is read, as a video's nested event loop would let them.
        seen["enabled"] = window.isEnabled()
        page.scenes.buttons["ice"].click()
        page.upload_button.click()
        page.reset_button.click()
        window._tab_buttons[window.settings_tab].click()
        seen["note"] = page.note.text()
        return read(path)

    monkeypatch.setattr(sound_import, "decode", slow)
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    assert seen == {"enabled": False, "note": "正在读取…"}
    assert len(pick["asked"]) == 1 and window.tabs.currentIndex() != window.settings_tab
    # The sound is the 场景's shown when 上传 was pressed, and the page says so.
    assert window.isEnabled() and page.scenes.key == "lace" and list(window.store.scene_sounds) == ["lace"]
    assert page.sound_text.full == "自定义 · a.wav · 2.0 秒" and page.scenes.buttons["lace"].own


def test_a_silent_part_says_so_in_the_part_picker_and_is_not_kept(window, pick, trim, tmp_path):
    page = _shown(window, "stars")
    # 5 s of nothing before the music, as a video's intro may be.
    t = np.arange(12 * 44100) / 44100
    tone = np.where(t >= 5.0, np.sin(2 * np.pi * 440 * t) * 12000, 0).astype("<i2")
    with wave.open(str(tmp_path / "intro.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(tone.tobytes())
    pick["chosen"] = tmp_path / "intro.wav"

    def choose(dialog) -> bool:  # noqa: ANN001
        window.played.clear()
        dialog.toggle_preview()
        assert not dialog.playing and dialog.play_button.text() == "试听"
        assert dialog.times.text() == "选的这段没有声音" and dialog.times.objectName() == "error"
        assert all(tune is None for tune in window.played)
        # 确定 keeps the dialog open on it, so another part can be picked.
        dialog.accept()
        assert dialog.result() != QDialog.Accepted and dialog.times.text() == "选的这段没有声音"
        dialog.wave.set_selection(6.0, 3.0)
        assert dialog.times.text().endswith("3.0 秒") and dialog.times.objectName() == ""
        dialog.toggle_preview()
        assert dialog.playing and window.played[-1] is not None
        dialog.accept()
        assert dialog.result() == QDialog.Accepted
        return True

    trim["do"] = choose
    page.upload_button.click()
    entry = window.store.scene_sounds["stars"]
    assert (entry["start"], entry["length"]) == (pytest.approx(6.0), pytest.approx(3.0)) and page.note.isHidden()


def test_where_only_wav_can_be_read_the_dialog_says_so(window, pick, monkeypatch):
    monkeypatch.setattr(sound_import, "available", lambda: False)
    page = _shown(window, "stars")
    page.upload_button.click()
    _parent, title, _folder, kinds = pick["asked"][-1]
    assert "WAV" in title and kinds == f"WAV 声音 ({sound_import.WAV_FILTER})"


def test_restoring_the_default_drops_the_file_and_its_copies_and_keeps_the_volume(window, pick, trim, tmp_path):
    page = _shown(window, "ice")
    page.volume_slider.setValue(12)
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    # Another 场景's copy, and this one's, are in sounds/.
    _shown(window, "stars")
    page.volume_slider.setValue(10)
    assert [copy.name[:3] for copy in _copies("ice")] == ["60-"] and _copies(TUNES["stars"].stem)
    _shown(window, "ice")
    page.reset_button.click()
    assert not (custom_sound_dir(window.store.root) / "ice.wav").exists()
    assert window.store.scene_sounds["ice"] == {"volume": 60} and Store(window.store.root).scene_sounds["ice"] == {"volume": 60}
    assert _copies("ice") == [] and _copies(TUNES["stars"].stem) and _copies(TUNES["ice"].stem)
    assert page.sound_text.full == "默认" and page.reset_button.isHidden() and page.upload_button.text() == "上传"
    assert not page.scenes.buttons["ice"].own and window.music.pick("ice") == "ice"


def test_replacing_a_sound_drops_the_old_one_s_copies(window, pick, trim, tmp_path):
    page = _shown(window, "ice")
    page.volume_slider.setValue(12)
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    first = _copies("ice")
    assert first
    pick["chosen"] = _wav(tmp_path / "b.wav", 2.5, pitch=660)
    page.upload_button.click()
    assert not any(copy.exists() for copy in first)
    assert window.store.scene_sounds["ice"]["name"] == "b.wav" and page.sound_text.full == "自定义 · b.wav · 2.5 秒"


def test_classic_may_have_one_too(window, pick, trim, tmp_path):
    page = _shown(window, "classic")
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    assert page.volume_slider.isEnabled() and window.music.pick("classic") == "classic"
    assert page.scenes.buttons["classic"].own and page.sound_text.full == "自定义 · a.wav · 2.0 秒"
    page.reset_button.click()
    assert not page.volume_slider.isEnabled() and window.music.pick("classic") == "" and page.sound_text.full == "默认 · 无"


def test_starting_over_takes_the_marks_and_rows_back(window, pick, trim, tmp_path, monkeypatch):
    page = _shown(window, "ice")
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    page.assign_button.click()
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda *_args: True)
    window._ask_reset()
    assert page.scenes.key == "classic" and page.scenes.buttons["classic"].tick
    assert not page.scenes.buttons["ice"].own and page.sound_text.full == "默认 · 无"


def test_an_mp3_is_read_and_kept(window, pick, trim):
    if not sound_import.available():
        pytest.skip("QtMultimedia cannot be loaded here")
    page = _shown(window, "angel")
    # 1.5 s of organ: kept whole.
    pick["chosen"] = os.path.join(SOUNDS, "organ.mp3")
    page.upload_button.click()
    entry = window.store.scene_sounds["angel"]
    assert entry["name"] == "organ.mp3" and entry["length"] == pytest.approx(1.5, abs=0.1) and trim["opened"] == []


def test_the_page_with_its_own_sound_fits_the_smallest_window(window, pick, trim, tmp_path):
    window.resize(900, 560)
    window.tabs.setCurrentIndex(window.effects_tab)
    window.show()
    _wait(50)
    page = _shown(window, "fluffy")
    pick["chosen"] = _wav(tmp_path / "一个名字很长很长很长很长很长很长很长的心动音乐.wav", 2.0)
    page.upload_button.click()
    # 已静音 beside 音量 too.
    window.mute_box.click()
    _wait(30)

    def placed(widget):  # noqa: ANN001, ANN202
        return widget.geometry().translated(widget.parentWidget().mapTo(page, widget.pos()) - widget.pos())

    for control in (page.sound_text, page.upload_button, page.reset_button, page.level_note, page.play_button, page.assign_button):
        assert page.rect().contains(placed(control)), control
    # A name too long for its room is cut in the middle, whole in its tooltip.
    assert page.sound_text.text() != page.sound_text.full and page.sound_text.toolTip() == page.sound_text.full
    assert page.sound_text.text().endswith("2.0 秒")
    window.hide()


def test_settings_saved_by_the_page_load_as_they_were(window, pick, trim, tmp_path):
    page = _shown(window, "cyber")
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    page.volume_slider.setValue(9)
    saved = json.loads(window.store.settings_path.read_text(encoding="utf-8"))["scene_sounds"]
    assert saved["cyber"]["volume"] == 45 and saved["cyber"]["file"] == "cyber.wav"
    again = type(window)()
    assert again.effects_page.scenes.buttons["cyber"].own
    again.close()



def test_the_tab_row_keeps_clear_of_the_chips_in_the_smallest_window(window):
    window.resize(900, 560)
    window.show()
    # The longest it gets: every count 99+, 有更新 shown and a long 游戏名.
    for index in (window.history_tab, window.blacklist_tab, window.likes_tab):
        window._set_tab_count(index, 150)
    window.update_pill.show()
    window.profile_chip.set_name("一二三四五六七八九十")
    _wait(30)
    last = window._tab_buttons[-1]
    assert window.tabs.tabText(window.effects_tab) == "场景管理"
    assert last.mapTo(window, last.rect().topRight()).x() < window.update_pill.mapTo(window, window.update_pill.rect().topLeft()).x()
    window.hide()
