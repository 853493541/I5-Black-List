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


def _rows(page) -> list[str]:  # noqa: ANN001
    """声音's rows as shown: 默认, then each song."""
    return [choice.full for choice in page.sounds.choices if not choice.isHidden()]


def _chosen(page) -> str:  # noqa: ANN001
    """The words of the row checked."""
    return next(choice.full for choice in page.sounds.choices if choice.isChecked())


def test_the_rows_say_what_each_effect_plays(window):
    page = _shown(window, "classic")
    assert _rows(page) == ["默认（无声）"] and _chosen(page) == "默认（无声）" and page.upload_button.text() == "上传"
    assert not page.sounds.play_buttons[0].isEnabled() and page.upload_button.isEnabled()
    assert page.reset_button.isHidden() and not page.volume_slider.isEnabled()
    _shown(window, "ice")
    assert _rows(page) == ["默认"] and page.reset_button.isHidden() and page.volume_slider.isEnabled()
    assert page.sounds.play_buttons[0].isEnabled()
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


def test_a_short_sound_is_kept_whole_and_marked_and_nothing_plays(window, pick, trim, tmp_path):
    page = _shown(window, "ice")
    page.volume_slider.setValue(14)
    window.played.clear()
    pick["chosen"] = _wav(tmp_path / "心动音乐.wav", 3.0)
    page.upload_button.click()
    parent, title, folder, kinds = pick["asked"][-1]
    assert parent is page and "冰蓝极光" in title and folder == ""
    assert kinds in (f"声音或视频 ({sound_import.FILTER})", f"WAV 声音 ({sound_import.WAV_FILTER})")
    assert trim["opened"] == []
    own = custom_sound_dir(window.store.root) / "ice-1.wav"
    assert own.is_file()
    entry = window.store.scene_sounds["ice"]
    assert entry["volume"] == 70 and entry["chosen"] == "ice-1.wav"
    song = entry["songs"][0]
    assert song["file"] == "ice-1.wav" and song["name"] == "心动音乐.wav"
    assert song["start"] == 0 and song["length"] == pytest.approx(3.0)
    assert Store(window.store.root).scene_sounds["ice"] == entry
    # ♪ on it, it chosen under 默认, and nothing plays by itself: whatever played stops for the new sound.
    assert page.scenes.buttons["ice"].own and not page.scenes.buttons["stars"].own
    assert _rows(page) == ["默认", "心动音乐.wav · 3.0 秒"] and _chosen(page) == "心动音乐.wav · 3.0 秒"
    assert page.upload_button.text() == "上传" and page.upload_button.isEnabled() and not page.reset_button.isHidden()
    assert window.played and all(tune is None for tune in window.played)
    assert window.music.pick("ice") == "ice" and page.note.isHidden()


def test_ok_after_an_upload_plays_nothing_by_itself(window, pick, trim, tmp_path, monkeypatch):
    """Once kept, the sound is not played on its own: neither a short file nor the part picked of a long one."""
    tasted = []
    monkeypatch.setattr(window.music, "taste", tasted.append)
    page = _shown(window, "stars")
    pick["chosen"] = _wav(tmp_path / "short.wav", 2.0)
    page.upload_button.click()
    pick["chosen"] = _wav(tmp_path / "long.wav", 9.0)
    window.played.clear()
    page.upload_button.click()
    assert [song["name"] for song in window.store.scene_songs("stars")] == ["short.wav", "long.wav"]
    assert tasted == [] and all(tune is None for tune in window.played)


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
    entry = window.store.scene_songs("stars")[0]
    assert (entry["start"], entry["length"]) == (pytest.approx(4.0), pytest.approx(3.0))
    with wave.open(str(custom_sound_dir(window.store.root) / "stars-1.wav")) as wav:
        assert wav.getnframes() == round(3.0 * 44100)
    assert _chosen(page) == "long.wav · 3.0 秒"


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


def test_the_part_picker_plays_the_song_from_the_playhead_at_the_effect_s_level(window, pick, trim, tmp_path):
    page = _shown(window, "stars")
    page.volume_slider.setValue(10)
    pick["chosen"] = _wav(tmp_path / "long.wav", 8.0)
    heard = []

    def listen(dialog) -> bool:  # noqa: ANN001
        window.played.clear()
        dialog.show()
        song = window.played[-1]
        assert window.played[-2] is None and song.is_file() and song.parent != sound_dir()
        assert custom_sound_dir(window.store.root) not in song.parents
        heard.append(song)
        # From where the playhead is pressed, a new file each time; the last one, no longer held, goes.
        dialog._seek(3.0, True)
        later = window.played[-1]
        assert later != song and later.parent == song.parent and not song.exists()
        heard.append(later)
        # The rest of the song from there, at the 场景's 50%.
        with wave.open(str(later)) as wav:
            assert wav.getnframes() == round(5.0 * 44100)
            frames = np.frombuffer(wav.readframes(wav.getnframes()), "<i2").astype(np.int32)
        with wave.open(str(tmp_path / "long.wav")) as wav:
            source = np.frombuffer(wav.readframes(wav.getnframes()), "<i2")[round(3.0 * 44100) :].astype(np.int32)
        assert np.abs(frames - source / 2).max() <= 1
        # 确定 stops it, and nothing plays after.
        dialog.cut()
        dialog.accept()
        return True

    trim["do"] = listen
    page.upload_button.click()
    assert not heard[-1].exists() and not heard[-1].parent.exists()
    assert window.store.scene_sounds["stars"]["chosen"] == "stars-1.wav"
    assert window.played[-1] is None


def test_closing_the_part_picker_changes_nothing(window, pick, trim, tmp_path):
    page = _shown(window, "stars")
    pick["chosen"] = _wav(tmp_path / "long.wav", 8.0)
    trim["do"] = lambda dialog: False
    window.played.clear()
    page.upload_button.click()
    assert len(trim["opened"]) == 1 and window.store.scene_sounds == {}
    assert not (custom_sound_dir(window.store.root) / "stars-1.wav").exists() and not page.scenes.buttons["stars"].own
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
    assert window.store.scene_sounds["stars"]["chosen"] == "stars-1.wav"
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
    assert _chosen(page) == "a.wav · 2.0 秒" and page.scenes.buttons["lace"].own


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
    entry = window.store.scene_songs("stars")[0]
    assert (entry["start"], entry["length"]) == (pytest.approx(6.0), pytest.approx(3.0)) and page.note.isHidden()


def test_where_only_wav_can_be_read_the_dialog_says_so(window, pick, monkeypatch):
    monkeypatch.setattr(sound_import, "available", lambda: False)
    page = _shown(window, "stars")
    page.upload_button.click()
    _parent, title, _folder, kinds = pick["asked"][-1]
    assert "WAV" in title and kinds == f"WAV 声音 ({sound_import.WAV_FILTER})"


def test_restoring_the_default_chooses_it_and_keeps_the_songs_and_the_volume(window, pick, trim, tmp_path):
    page = _shown(window, "ice")
    page.volume_slider.setValue(12)
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    window.played.clear()
    page.reset_button.click()
    own = custom_sound_dir(window.store.root) / "ice-1.wav"
    assert own.is_file() and window.store.scene_sounds["ice"]["chosen"] == ""
    assert Store(window.store.root).scene_sound("ice") == (None, 60)
    assert _rows(page) == ["默认", "a.wav · 2.0 秒"] and _chosen(page) == "默认" and page.reset_button.isHidden()
    assert not page.scenes.buttons["ice"].own and window.music.pick("ice") == "ice" and window.played == []


def test_deleting_a_song_drops_its_file_and_copies_and_the_chosen_one_falls_back_to_the_default(window, pick, trim, tmp_path):
    page = _shown(window, "ice")
    page.volume_slider.setValue(12)
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    pick["chosen"] = _wav(tmp_path / "b.wav", 2.5, pitch=660)
    page.upload_button.click()
    # Heard at its 音量 (as the slider plays it), b has a copy, and so has a, played with its ▶.
    window.music.taste("ice")
    page.sounds.play_buttons[1].click()
    # Another 场景's copy is in sounds/ too.
    _shown(window, "stars")
    page.volume_slider.setValue(10)
    _shown(window, "ice")
    assert _copies("ice-1") and _copies("ice-2") and _copies(TUNES["stars"].stem)
    # ✕ on a, not the chosen: b plays on.
    page.sounds.delete_buttons[0].click()
    folder = custom_sound_dir(window.store.root)
    assert not (folder / "ice-1.wav").exists() and _copies("ice-1") == [] and _copies("ice-2")
    assert _rows(page) == ["默认", "b.wav · 2.5 秒"] and _chosen(page) == "b.wav · 2.5 秒"
    # ✕ on b, the chosen: 默认 plays, the 音量 stays.
    page.sounds.delete_buttons[0].click()
    assert not (folder / "ice-2.wav").exists() and _copies("ice-2") == [] and _copies(TUNES["stars"].stem)
    assert window.store.scene_sounds["ice"] == {"volume": 60} and Store(window.store.root).scene_sounds["ice"] == {"volume": 60}
    assert _rows(page) == ["默认"] and _chosen(page) == "默认" and page.reset_button.isHidden()
    assert not page.scenes.buttons["ice"].own and window.music.pick("ice") == "ice"


def test_a_click_chooses_a_row_and_plays_nothing(window, pick, trim, tmp_path):
    page = _shown(window, "lace")
    for name in ("a.wav", "b.wav"):
        pick["chosen"] = _wav(tmp_path / name, 2.0)
        page.upload_button.click()
    assert _chosen(page) == "b.wav · 2.0 秒"
    window.played.clear()
    page.sounds.choices[1].click()
    assert window.store.scene_sound("lace")[0].name == "lace-1.wav" and _chosen(page) == "a.wav · 2.0 秒"
    assert Store(window.store.root).scene_sound("lace")[0].name == "lace-1.wav"
    # One at a time, like a radio button.
    assert [choice.isChecked() for choice in page.sounds.choices[:3]] == [False, True, False]
    page.sounds.choices[0].click()
    assert window.store.scene_sound("lace")[0] is None and not page.scenes.buttons["lace"].own and window.music.pick("lace") == "lace"
    page.sounds.choices[2].click()
    assert window.store.scene_sound("lace")[0].name == "lace-2.wav" and page.scenes.buttons["lace"].own
    assert window.played == []


def test_each_row_s_play_plays_it_at_the_effect_s_volume_chosen_or_not(window, pick, trim, tmp_path):
    page = _shown(window, "stars")
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    page.volume_slider.setValue(10)
    window.played.clear()
    # 默认: the scene's own tune, whole, at 50%, though the song is chosen.
    page.sounds.play_buttons[0].click()
    assert window.played[-1].name.startswith(f"50-{TUNES['stars'].stem}-") and not window.played[-1].name.endswith("ms.wav")
    page.sounds.play_buttons[1].click()
    assert window.played[-1].name.startswith("50-stars-1-") and page.sounding
    assert window.store.scene_sounds["stars"]["chosen"] == "stars-1.wav"
    # 经典's 默认 has nothing to play.
    _shown(window, "classic")
    assert not page.sounds.play_buttons[0].isEnabled()
    # Under 静音, nothing.
    _shown(window, "stars")
    window.mute_box.click()
    window.played.clear()
    page.sounds.play_buttons[1].click()
    assert all(tune is None for tune in window.played) and not page.sounding


def test_upload_is_off_at_three_songs_until_one_is_deleted(window, pick, trim, tmp_path):
    page = _shown(window, "cyber")
    for number in range(3):
        pick["chosen"] = _wav(tmp_path / f"{number}.wav", 1.0 + number)
        page.upload_button.click()
    assert [song["file"] for song in window.store.scene_songs("cyber")] == ["cyber-1.wav", "cyber-2.wav", "cyber-3.wav"]
    assert len(_rows(page)) == 4 and _chosen(page) == "2.wav · 3.0 秒"
    assert not page.upload_button.isEnabled() and page.upload_button.toolTip() == "最多 3 首，先删掉一首"
    # Asked anyway (a shortcut, a click under way), nothing is.
    page.upload()
    assert len(pick["asked"]) == 3
    # ✕ on the second: its number is free again, and the next one takes it.
    page.sounds.delete_buttons[1].click()
    assert page.upload_button.isEnabled() and page.upload_button.toolTip() == ""
    pick["chosen"] = _wav(tmp_path / "new.wav", 1.5)
    page.upload_button.click()
    files = [song["file"] for song in window.store.scene_songs("cyber")]
    assert files == ["cyber-1.wav", "cyber-3.wav", "cyber-2.wav"] and window.store.scene_sounds["cyber"]["chosen"] == "cyber-2.wav"
    assert _rows(page)[1:] == ["0.wav · 1.0 秒", "2.wav · 3.0 秒", "new.wav · 1.5 秒"]


def test_a_new_song_never_takes_a_file_still_there(window, pick, trim, tmp_path):
    """A song's file that could not be deleted (winsound held it) keeps its name: the next song takes another."""
    page = _shown(window, "ice")
    folder = custom_sound_dir(window.store.root)
    folder.mkdir(parents=True, exist_ok=True)
    _wav(folder / "ice-1.wav", 1.0)
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    assert window.store.scene_songs("ice")[0]["file"] == "ice-2.wav"
    with wave.open(str(folder / "ice-1.wav")) as wav:
        assert wav.getnframes() == 44100


def test_classic_may_have_one_too(window, pick, trim, tmp_path):
    page = _shown(window, "classic")
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    assert page.volume_slider.isEnabled() and window.music.pick("classic") == "classic"
    assert page.scenes.buttons["classic"].own and _chosen(page) == "a.wav · 2.0 秒"
    page.reset_button.click()
    assert window.music.pick("classic") == "" and _chosen(page) == "默认（无声）" and not page.scenes.buttons["classic"].own
    # Its song is there still, to be heard at its 音量.
    assert page.volume_slider.isEnabled()
    page.sounds.delete_buttons[0].click()
    assert not page.volume_slider.isEnabled() and _rows(page) == ["默认（无声）"]


def test_starting_over_takes_the_marks_and_rows_back(window, pick, trim, tmp_path, monkeypatch):
    page = _shown(window, "ice")
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    page.assign_button.click()
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda *_args: True)
    window._ask_reset()
    assert page.scenes.key == "classic" and page.scenes.buttons["classic"].tick
    assert not page.scenes.buttons["ice"].own and _rows(page) == ["默认（无声）"]


def test_an_mp3_is_read_and_kept(window, pick, trim):
    if not sound_import.available():
        pytest.skip("QtMultimedia cannot be loaded here")
    page = _shown(window, "angel")
    # 1.5 s of organ: kept whole.
    pick["chosen"] = os.path.join(SOUNDS, "organ.mp3")
    page.upload_button.click()
    entry = window.store.scene_songs("angel")[0]
    assert entry["name"] == "organ.mp3" and entry["length"] == pytest.approx(1.5, abs=0.1) and trim["opened"] == []


def test_the_page_with_three_songs_fits_the_smallest_window(window, pick, trim, tmp_path):
    window.resize(900, 560)
    window.tabs.setCurrentIndex(window.effects_tab)
    window.show()
    _wait(50)
    page = _shown(window, "fluffy")
    for name in ("一个名字很长很长很长很长很长很长很长很长很长很长很长很长的心动音乐.wav", "b.wav", "c.wav"):
        pick["chosen"] = _wav(tmp_path / name, 2.0)
        page.upload_button.click()
    page.sounds.choices[1].click()
    # 已静音 beside 音量 too.
    window.mute_box.click()
    _wait(30)

    def placed(widget):  # noqa: ANN001, ANN202
        return widget.geometry().translated(widget.parentWidget().mapTo(page, widget.pos()) - widget.pos())

    controls = (*page.sounds.choices, *page.sounds.play_buttons, *page.sounds.delete_buttons, page.upload_button, page.reset_button)
    for control in (*controls, page.volume_slider, page.level_note, page.play_button, page.assign_button):
        assert page.rect().contains(placed(control)), control
    assert page.preview.width() >= page.stage.MIN_W
    # A name too long for its room is cut in the middle, whole in its tooltip.
    long = page.sounds.choices[1]
    assert long.text() != long.full and long.toolTip() == long.full and long.text().endswith("2.0 秒")
    window.hide()


def test_settings_saved_by_the_page_load_as_they_were(window, pick, trim, tmp_path):
    page = _shown(window, "cyber")
    pick["chosen"] = _wav(tmp_path / "a.wav", 2.0)
    page.upload_button.click()
    pick["chosen"] = _wav(tmp_path / "b.wav", 2.0)
    page.upload_button.click()
    page.sounds.choices[1].click()
    page.volume_slider.setValue(9)
    saved = json.loads(window.store.settings_path.read_text(encoding="utf-8"))["scene_sounds"]
    # The one chosen beside the songs, as v0.9.15 reads it.
    assert saved["cyber"]["volume"] == 45 and saved["cyber"]["chosen"] == saved["cyber"]["file"] == "cyber-1.wav"
    assert saved["cyber"]["name"] == "a.wav" and [song["file"] for song in saved["cyber"]["songs"]] == ["cyber-1.wav", "cyber-2.wav"]
    again = type(window)()
    assert again.effects_page.scenes.buttons["cyber"].own
    again.effects_page.scenes.buttons["cyber"].click()
    assert _rows(again.effects_page) == ["默认", "a.wav · 2.0 秒", "b.wav · 2.0 秒"] and _chosen(again.effects_page) == "a.wav · 2.0 秒"
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
