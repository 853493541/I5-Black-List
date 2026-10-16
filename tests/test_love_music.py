"""嘉宾音乐: each 嘉宾场景 theme's own sound whenever a 嘉宾 is in the lobby, once per lobby, as loud as
its 场景's own 音量 in 场景管理 says, or not at all with 设置 › 常规 › 声音 › 静音."""

import os
import shutil
import wave

import numpy as np
import pytest

from blacklist_detect import love_scenes
from blacklist_detect.model import Scenes
from blacklist_detect.sound_import import RATE, Decoded, save_rest
from blacklist_detect.ui_music import SAME_LOBBY_S, SAMPLE_S, TUNES, ThemeMusic, scaled_tune


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _music():  # noqa: ANN202
    played: list = []
    clock = Clock()
    return ThemeMusic(play=played.append, clock=clock), played, clock


def test_every_theme_has_its_own_sound_as_long_as_it():
    """One sound for each scene but 经典, which greets in silence: mono 16-bit 44.1 kHz, no longer than
    the scene (演说家遇袭's runs its 6.6 s)."""
    assert set(TUNES) == set(love_scenes.KEYS) - {"classic"}
    for key, tune in TUNES.items():
        assert tune.is_file(), key
        with wave.open(str(tune)) as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 44100)
            assert 4.0 <= w.getnframes() / w.getframerate() <= love_scenes.load(key).DURATION + 0.6, key
    # Each its own: no two themes share a sound.
    assert len(set(TUNES.values())) == len(TUNES)


def test_hearts_get_music_once_per_lobby():
    """The window asks for a lobby with any 嘉宾 player in it, greeted by its scene."""
    music, played, clock = _music()
    assert music.lobby([], "stars") == ""
    assert played == []
    assert music.lobby(["小红", "小明"], "stars") == "stars" and played == [TUNES["stars"]]
    # The same lobby checked again: the same players a moment later, in any order.
    clock.now += 5
    assert music.lobby(["小明", "小红"], "stars") == ""
    # The next lobby: other players, or the same two a minute later.
    assert music.lobby(["小红", "阿强"], "cyber")
    clock.now += SAME_LOBBY_S + 1
    assert music.lobby(["小红", "阿强"], "cyber")
    # One player is a lobby too.
    assert music.lobby(["小红"], "claw")
    assert played == [TUNES["stars"], TUNES["cyber"], TUNES["cyber"], TUNES["claw"]]


def test_no_scene_plays_no_sound():
    music, played, clock = _music()
    # 无, or a scene from a newer or older version this one does not have.
    assert music.lobby(["小红", "小明"], "") == "" and music.pick("ribbon") == ""
    assert played == []
    music.preview("")
    music.stop()
    assert played == [None, None]


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    made = MainWindow()
    made._watch_timer.stop()
    made.store.disclaimer_accepted = True
    tunes: list = []
    made.music = ThemeMusic(play=tunes.append, sounds=made.store.scene_sound)
    made.tunes = tunes
    # Both on 经典, which greets in silence, unless a test gives them another.
    made.store.add_like("小红", scenes=Scenes(("classic",)))
    made.store.add_like("小明", scenes=Scenes(("classic",)))
    made._live_check = True
    yield made
    made.notice.hide()
    made.love.stop()
    made.close()


def _lobby(hit: bool = False):  # noqa: ANN202
    from PySide6.QtWidgets import QApplication

    from blacklist_detect.pipeline import CheckResult, Hit, NameSlot

    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    names = [
        NameSlot(0, (100, 100, 200, 130), "坏人", "坏人", False, 0.9, False),
        NameSlot(1, (300, 100, 400, 130), "小红", "小红", False, 0.9, False),
        NameSlot(2, (500, 100, 600, 130), "小明", "小明", False, 0.9, False),
    ]
    hits = [Hit(0, "坏人", "坏人", "", False, "", ())] if hit else []
    return CheckResult(True, "", names=names, hits=hits, button_box=button)


def test_the_theme_brings_its_sound_until_muted(window):
    from blacklist_detect.storage import Store

    assert not window.store.sound_muted
    # 经典 greets in silence.
    window._show_panel(_lobby())
    assert window.tunes == []
    window._hide_panel_after_title()
    window.store.update_like(1, "小明", "", "", Scenes(("lace",)))
    window._on_lobby_placed(_lobby().button_box)
    window.music._last_lobby = frozenset()
    window._show_panel(_lobby())
    assert window.tunes == [TUNES["lace"]]
    window.mute_box.click()
    assert Store(window.store.root).sound_muted is True
    window._hide_panel_after_title()
    window.music._last_lobby = frozenset()
    window.tunes.clear()
    window._show_panel(_lobby())
    assert all(tune is None for tune in window.tunes), "the lobby is greeted in silence"


def test_music_off_before_is_mute_now(tmp_path):
    """设置 › 嘉宾场景 › 音乐 无 (up to v0.9.12) opens with 静音 ticked, once: what is saved since counts. The
    five wedding tunes, 随机 and 跟随场景 that came before play."""
    import json

    from blacklist_detect.storage import Store

    Store(tmp_path).save_settings()
    path = tmp_path / "settings.json"
    for saved, muted in (("organ", False), ("8bit", False), ("random", False), ("theme", False), ("off", True), (None, False)):
        settings = json.loads(path.read_text(encoding="utf-8"))
        settings.pop("sound_muted", None)
        settings["love_music"] = saved
        path.write_text(json.dumps(settings), encoding="utf-8")
        store = Store(tmp_path)
        assert store.sound_muted is muted and store.scene_sounds == {}, saved
        store.save_settings()
        settings = json.loads(path.read_text(encoding="utf-8"))
        assert "love_music" not in settings and settings["sound_muted"] is muted
    # 静音 since turned off stays off, the old 无 still in the file or not.
    settings["love_music"], settings["sound_muted"] = "off", False
    path.write_text(json.dumps(settings), encoding="utf-8")
    assert Store(tmp_path).sound_muted is False


@pytest.mark.parametrize("safe", [True, False])
def test_music_plays_in_either_display_mode(window, safe):
    """基础模式 draws nothing over the game, but the music is only sound: it plays there too."""
    window.store.safe_mode = safe
    window.store.update_like(1, "小明", "", "", Scenes(("angel",)))
    window._show_panel(_lobby())
    assert window.tunes == [TUNES["angel"]]


def test_a_blacklist_player_means_no_music(window):
    window._show_panel(_lobby(hit=True))
    assert window.tunes == []


def _own_sound(store, key: str, like: str = "ice", volume: int = 100):  # noqa: ANN001, ANN202
    """The player's own sound for a 场景 as 场景管理 keeps it, its one song, chosen: here a copy of another scene's tune."""
    from blacklist_detect.paths import custom_sound_dir

    own = custom_sound_dir(store.root) / f"{key}-1.wav"
    own.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TUNES[like], own)
    store.scene_sounds[key] = {"volume": volume, "songs": [{"file": own.name, "name": "我的声音.mp3"}], "chosen": own.name}
    return own


def test_clearing_the_data_puts_the_effects_and_the_sound_back_to_their_defaults(window, monkeypatch):
    from blacklist_detect.ui_music import sound_dir

    own = _own_sound(window.store, "classic", volume=30)
    # Heard below 100%, the player's own sound has quieter copies too.
    assert window.music.preview("classic") == "classic" and window.music.taste("classic")
    assert len([tune for tune in sound_dir().iterdir() if tune.name.startswith("30-classic-")]) == 2
    window.mute_box.click()
    assert window.store.sound_muted
    window.store.scene_sounds["ice"] = {"volume": 40}
    window.store.save_settings()
    window.tunes.clear()
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda *_args: True)
    window._ask_reset()
    # The player's own sounds go too, nothing playing them first.
    assert window.tunes[0] is None and window.store.scene_sounds == {} and not own.parent.exists()
    assert not sound_dir().exists()
    assert window.music.pick("classic") == "" and window.music.level("ice") == 100
    assert window.store.sound_muted is False and not window.mute_box.isChecked() and not window.music.muted
    assert window.love.choice == "classic"
    assert all(tune is None for tune in window.tunes), "清空数据 plays no sample"


def test_settings_has_no_scene_switch_and_no_place_turns_scenes_off(window):
    """设置 › 嘉宾 › 场景 is gone, and its section with it: each 嘉宾 and 组合 is greeted with its 场景 (经典 for
    none), none on 不放, which turns a scene and its sound off now."""
    from PySide6.QtWidgets import QLabel

    window.store.update_like(1, "小明", "", "", Scenes(("angel",)))
    assert not hasattr(window, "love_switch") and not hasattr(window, "_set_love_effects")
    titles = [label.text() for label in window.settings_scroll.widget().findChildren(QLabel)]
    assert "常规" in titles and "嘉宾" not in titles
    assert window._choice_for(window.store.likes) == ("guest", "angel")
    for index, like in enumerate(window.store.likes):
        window.store.update_like(index, like.name, "", "", Scenes())
    assert window._choice_for(window.store.likes) == ("", "off")
    window._show_panel(_lobby())
    assert not window.love.playing() and window.tunes == []
    assert "嘉宾场景" not in window.settings_line()


def test_an_old_saved_off_puts_every_guest_on_no_scene(tmp_path, monkeypatch):
    """嘉宾场景 left off in 设置 (up to v0.9.14): the window opens with every 嘉宾 and 组合 on 不放, so no scene
    greets them, nor its sound."""
    import json

    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from blacklist_detect.model import Combo
    from blacklist_detect.storage import Store
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    store = Store()
    store.add_like("小红", scenes=Scenes(("lace",)))
    store.add_like("小明", scenes=Scenes(("angel", "stars")))
    store.set_combos([Combo(("小红", "小明"), Scenes(("cyber",)))])
    store.save_settings()
    settings = json.loads(store.settings_path.read_text(encoding="utf-8"))
    settings["love_scene"] = "off"
    store.settings_path.write_text(json.dumps(settings), encoding="utf-8")
    window = MainWindow()
    window._watch_timer.stop()
    tunes: list = []
    window.music = ThemeMusic(play=tunes.append, sounds=window.store.scene_sound)
    assert [like.scenes for like in window.store.likes] == [Scenes(), Scenes()]
    assert window.store.combos[0].scenes == Scenes()
    assert window._choice_for(window.store.likes) == ("", "off") and window.love.choice == "classic"
    window._live_check = True
    window._show_panel(_lobby())
    assert not window.love.playing() and tunes == []
    window._hide_panel_after_title()
    window.notice.hide()
    window.close()


def _likes(count: int):  # noqa: ANN202
    """A lobby with this many 嘉宾 players (小红, 小明, 阿强 in turn) and nobody on the 黑名单."""
    from PySide6.QtWidgets import QApplication

    from blacklist_detect.pipeline import CheckResult, NameSlot

    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    names = [NameSlot(i, (100 * i, 100, 100 * i + 80, 130), name, name, False, 0.9, False) for i, name in enumerate(["小红", "小明", "阿强"][:count])]
    names.append(NameSlot(5, (600, 100, 680, 130), "路人", "路人", False, 0.9, False))
    return CheckResult(True, "", names=names, button_box=button)


def test_the_effect_plays_for_one_guest_or_more(window):
    """嘉宾场景 plays whenever a 嘉宾 is in the lobby, one or more: each 嘉宾 and 组合 picks what greets them."""
    window.store.add_like("阿强")
    window.store.safe_mode = False
    window.store.consented = ["full"]
    window._on_display_mode("full")
    for likes in (1, 2, 3):
        window.tunes.clear()
        window.music._last_lobby = None
        window._love_played = False
        window._show_panel(_likes(likes))
        assert window.love.playing(), likes
        assert window.tunes == [], "经典 greets in silence"
        assert window.panel.mode == "liked" and window.like_card.isVisible()
        window._hide_panel_after_title()


def test_a_guest_with_a_theme_brings_its_sound(window):
    """A 嘉宾's own 场景 brings its own sound: 演说家遇袭 the 指挥家's music with the notice in it."""
    with wave.open(str(TUNES["claw"])) as w:
        assert 6.0 <= w.getnframes() / w.getframerate() <= 7.0
    # 阿强, added last, tops the list: his 演说家遇袭 greets the lobby, and its sound with it.
    window.store.add_like("阿强", scenes=Scenes(("claw",)))
    window._show_panel(_likes(3))
    assert window.tunes == [TUNES["claw"]]


def _samples(path):  # noqa: ANN001, ANN202
    with wave.open(str(path)) as w:
        return w.getparams(), np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.int64)


def test_a_quieter_tune_is_its_samples_scaled_made_once(tmp_path):
    """winsound plays at the system volume: a quieter tune is a copy with every sample scaled, made once
    and kept by tune and volume; 100% is the tune itself. The folder keeps one copy of each tune, each at
    its own volume (场景管理 gives each 场景 its own)."""
    tune = TUNES["ice"]
    assert scaled_tune(tune, 100, tmp_path) == tune and not any(tmp_path.iterdir())
    quiet = scaled_tune(tune, 40, tmp_path)
    assert quiet.parent == tmp_path and quiet != tune
    params, samples = _samples(quiet)
    first, original = _samples(tune)
    assert params[:3] == first[:3] and len(samples) == len(original)
    assert np.abs(samples - np.rint(original * 0.4)).max() <= 1
    assert np.abs(samples).max() < np.abs(original).max() * 0.41
    # Asked again: the same copy, not made again.
    made = quiet.stat().st_mtime_ns
    assert scaled_tune(tune, 40, tmp_path) == quiet and quiet.stat().st_mtime_ns == made
    # Another tune sits beside it, at that volume or another; the tune at another volume takes its place.
    other = scaled_tune(TUNES["stars"], 40, tmp_path)
    third = scaled_tune(TUNES["cyber"], 85, tmp_path)
    assert quiet.is_file() and other.is_file() and third.is_file()
    louder = scaled_tune(tune, 75, tmp_path)
    assert sorted(tmp_path.iterdir()) == sorted([louder, other, third])
    assert np.abs(_samples(louder)[1] - np.rint(original * 0.75)).max() <= 1
    assert not _samples(scaled_tune(tune, 0, tmp_path))[1].any()
    # No copy can be made: nothing, rather than the tune too loud.
    assert scaled_tune(tmp_path / "gone.wav", 50, tmp_path) is None


def test_an_updated_tune_leaves_no_old_copies_behind(tmp_path):
    """An update rewrites every tune: the next copy at the same volume takes the old ones' place (whole
    and moment alike), and a copy left half written goes too, while other tunes' copies stay."""
    source, folder = tmp_path / "assets", tmp_path / "sounds"
    source.mkdir()
    tune, other = source / TUNES["lace"].name, source / TUNES["ice"].name
    shutil.copyfile(TUNES["lace"], tune)
    shutil.copyfile(TUNES["ice"], other)
    old = [scaled_tune(tune, 70, folder), scaled_tune(tune, 70, folder, SAMPLE_S)]
    kept = scaled_tune(other, 70, folder)
    (folder / "70-broken.part").write_bytes(b"")
    stamp = tune.stat().st_mtime_ns + 10**9
    os.utime(tune, ns=(stamp, stamp))
    new = [scaled_tune(tune, 70, folder), scaled_tune(tune, 70, folder, SAMPLE_S)]
    assert set(new).isdisjoint(old)
    assert sorted(folder.iterdir()) == sorted([*new, kept])


def test_a_moment_is_the_tune_s_start_fading_out(tmp_path):
    """What 音量's slider in 场景管理 plays as it is let go: a moment of the 场景's tune, at the volume, ending
    softly; at 100% a moment too."""
    tune = TUNES["lace"]
    clip = scaled_tune(tune, 60, tmp_path, SAMPLE_S)
    params, samples = _samples(clip)
    _, original = _samples(tune)
    assert len(samples) == round(SAMPLE_S * params.framerate)
    head = len(samples) // 2
    assert np.abs(samples[:head] - np.rint(original[:head] * 0.6)).max() <= 1
    assert np.abs(samples[:head]).max() > 5000, "it is heard"
    assert np.abs(samples[-200:]).max() < np.abs(samples[:head]).max() / 20
    whole = scaled_tune(tune, 100, tmp_path, SAMPLE_S)
    assert whole != tune and len(_samples(whole)[1]) == len(samples)


def test_music_plays_at_its_volume_and_not_at_all_muted(tmp_path):
    music, played, clock = _managed(tmp_path, {"stars": (None, 50), "cyber": (None, 50)})
    assert music.lobby(["小红"], "stars") == "stars"
    assert played[-1].parent == tmp_path / "sounds"
    assert np.abs(_samples(played[-1])[1] - np.rint(_samples(TUNES["stars"])[1] * 0.5)).max() <= 1
    assert music.preview("cyber") == "cyber" and played[-1].parent == tmp_path / "sounds"
    assert music.taste("stars") and len(_samples(played[-1])[1]) == round(SAMPLE_S * 44100)
    # 静音: no sound, and the one playing stops.
    music.muted = True
    played.clear()
    clock.now += SAME_LOBBY_S + 1
    assert music.lobby(["小明"], "stars") == ""
    assert music.preview("stars") == "" and not music.taste("stars")
    assert played == [None, None]
    # Heard again, the lobby that had none a moment ago gets its sound.
    music.muted = False
    assert music.lobby(["小明"], "stars") == "stars" and played[-1].name.startswith("50-")


def test_the_sound_row_is_mute_alone(window):
    """设置 › 常规 › 全局声音: 播放 or 静音, no slider (each 场景 has its own 音量). On 静音, nothing is heard and
    nothing plays for it; kept for the next start."""
    from PySide6.QtWidgets import QSlider

    from blacklist_detect.storage import Store
    from blacklist_detect.ui import MainWindow

    box = window.mute_box
    assert not hasattr(window, "volume_slider") and not hasattr(window, "volume_label")
    assert window.settings_scroll.widget().findChildren(QSlider) == []
    assert box.currentText() == "播放" and not box.isChecked() and not window.music.muted
    assert not hasattr(window.music, "volume") and not hasattr(window.music, "sample")
    assert "声音 开" in window.settings_line()
    box.click()
    assert all(tune is None for tune in window.tunes) and window.music.muted
    assert Store(window.store.root).sound_muted is True and "声音 静音" in window.settings_line()
    again = MainWindow()
    again._watch_timer.stop()
    assert again.mute_box.isChecked() and again.music.muted
    again.close()


def test_ticking_mute_stops_the_sound_playing(window):
    window.store.update_like(1, "小明", "", "", Scenes(("lace",)))
    window._show_panel(_lobby())
    assert window.tunes == [TUNES["lace"]]
    window.mute_box.click()
    assert window.tunes[-1] is None and window.music.muted and window.store.sound_muted
    # Unticked, nothing starts by itself.
    window.mute_box.click()
    assert window.tunes == [TUNES["lace"], None] and not window.music.muted


def test_every_sound_goes_through_the_sound_control(window):
    """A lobby's, ▶ 播放 on 场景管理 and the 场景 hotkey: each at the 场景's own 音量, the player's own sound
    for it if any, none with 静音. 编辑嘉宾's preview is silent."""
    from blacklist_detect.ui_guest_scenes import ScenePane
    from blacklist_detect.ui_music import sound_dir

    window.effects_page.music = window.likes_page.music = window.music
    window.store.consented = ["full"]
    window._on_display_mode("full")
    window.store.update_like(1, "小明", "", "", Scenes(("angel",)))
    window.store.quick_scene = "stars"
    window.effects_page.select("stars")
    picker = ScenePane(window.store.likes[1].scenes)

    def every_path() -> list:
        window.tunes.clear()
        assert window.play_quick_scene()
        window._end_quick_play()
        window.effects_page.play_preview()
        picker.show_scene("fluffy")
        picker.replay()
        window.music._last_lobby = frozenset()
        window._show_panel(_lobby())
        window._hide_panel_after_title()
        return [tune for tune in window.tunes if tune is not None]

    # At 100% each 场景's tune itself.
    assert every_path() == [TUNES["stars"], TUNES["stars"], TUNES["angel"]]
    window.store.scene_sounds = {key: {"volume": 50} for key in ("stars", "fluffy", "angel")}
    heard = every_path()
    assert [tune.parent for tune in heard] == [sound_dir()] * 3
    assert all(tune.name.startswith("50-") for tune in heard)
    assert [TUNES[key].stem in tune.name for key, tune in zip(("stars", "stars", "angel"), heard, strict=True)] == [True] * 3
    # 场景管理: 星河许愿 the player's own sound at 60%, 天使 the player's at 100%.
    _own_sound(window.store, "stars", like="ice", volume=60)
    angel = _own_sound(window.store, "angel", like="cyber")
    heard = every_path()
    assert [tune.parent for tune in heard[:2]] == [sound_dir()] * 2 and heard[2] == angel
    assert [tune.name.startswith("60-stars-") for tune in heard[:2]] == [True] * 2
    _, ice = _samples(TUNES["ice"])
    assert np.abs(_samples(heard[0])[1] - np.rint(ice * 0.6)).max() <= 1
    window.mute_box.click()
    assert every_path() == []
    picker.stop()


def _managed(tmp_path, sounds: dict):  # noqa: ANN001, ANN202
    """ThemeMusic with 场景管理's sounds: by key, (the player's file or None, 音量)."""
    played: list = []
    clock = Clock()
    music = ThemeMusic(play=played.append, clock=clock, folder=tmp_path / "sounds", sounds=lambda key: sounds.get(key, (None, 100)))
    return music, played, clock


def test_an_effect_plays_at_its_own_volume(tmp_path):
    """场景管理's 音量 is how loud a 场景 plays: 60% is 60%. 静音 silences every 场景, and one at 0% plays
    nothing, so its lobby is greeted again once it is heard."""
    music, played, clock = _managed(tmp_path, {"stars": (None, 60), "ice": (None, 0)})
    assert (music.level("stars"), music.level("ice"), music.level("cyber")) == (60, 0, 100)
    assert music.lobby(["小红"], "stars") == "stars" and played[-1].name.startswith(f"60-{TUNES['stars'].stem}-")
    assert np.abs(_samples(played[-1])[1] - np.rint(_samples(TUNES["stars"])[1] * 0.6)).max() <= 1
    # At 100% the tune itself.
    assert music.preview("cyber") == "cyber" and played[-1] == TUNES["cyber"]
    played.clear()
    assert music.lobby(["小明"], "ice") == "" and music.preview("ice") == "" and not music.taste("ice")
    assert played == [None, None]
    music.muted = True
    played.clear()
    clock.now += SAME_LOBBY_S + 1
    assert music.lobby(["小红"], "stars") == "" and music.preview("stars") == "" and not music.taste("stars")
    assert played == [None, None]
    music.muted = False
    assert music.preview("cyber") == "cyber" and played[-1] == TUNES["cyber"]


def test_an_effect_plays_the_player_s_own_sound_classic_too(tmp_path):
    """A 场景 given the player's own sound plays it instead of its own; 经典, silent by itself, plays one
    given it. Its file gone, the 场景 plays its own again (经典 none)."""
    own = tmp_path / "custom_sounds"
    own.mkdir()
    classic, stars = own / "classic.wav", own / "stars.wav"
    shutil.copyfile(TUNES["ice"], classic)
    shutil.copyfile(TUNES["cyber"], stars)
    music, played, _clock = _managed(tmp_path, {"classic": (classic, 100), "stars": (stars, 50)})
    assert (music.pick("classic"), music.pick("stars"), music.pick("ribbon")) == ("classic", "stars", "")
    assert music.lobby(["小红"], "classic") == "classic" and played[-1] == classic
    assert music.preview("stars") == "stars" and played[-1].name.startswith("50-stars-")
    assert np.abs(_samples(played[-1])[1] - np.rint(_samples(TUNES["cyber"])[1] * 0.5)).max() <= 1
    classic.unlink()
    stars.unlink()
    assert music.pick("classic") == "" and music.preview("classic") == "" and played[-1] is None
    assert music.preview("stars") == "stars" and played[-1].name.startswith(f"50-{TUNES['stars'].stem}-")


def test_the_quietest_step_is_heard_and_zero_is_silence(tmp_path):
    """A 场景 at 5% plays at 5%; at 0% it is silence."""
    music, played, _clock = _managed(tmp_path, {"stars": (None, 5), "ice": (None, 0)})
    assert (music.level("stars"), music.level("ice")) == (5, 0)
    assert music.preview("stars") == "stars" and played[-1].name.startswith("5-")
    assert music.preview("ice") == "" and played[-1] is None


def test_a_trial_plays_at_the_effect_s_level_from_the_caller_s_folder(tmp_path):
    """选择片段's 试听: a sound not yet the 场景's, as loud as that 场景 plays, its copy made beside it and the
    sound itself left alone; nothing in sounds/, nothing under 静音."""
    music, played, _clock = _managed(tmp_path, {"ice": (None, 40)})
    folder = tmp_path / "trial"
    folder.mkdir()
    trial = folder / "trial.wav"
    shutil.copyfile(TUNES["fluffy"], trial)
    assert music.trial(trial, "ice")
    assert played[-1].parent == folder / "copies" and played[-1].name.startswith("40-trial-") and trial.is_file()
    assert np.abs(_samples(played[-1])[1] - np.rint(_samples(TUNES["fluffy"])[1] * 0.4)).max() <= 1
    assert not (tmp_path / "sounds").exists()
    # At 100% the sound itself.
    assert music.trial(trial, "cyber") and played[-1] == trial
    music.muted = True
    assert not music.trial(trial, "ice") and played[-1] is None


def test_any_of_a_scene_s_sounds_plays_whole_at_its_level_chosen_or_not(tmp_path):
    """▶ beside a row of 场景管理's 声音: 默认 (the scene's own, 经典's none) or a song not chosen, whole, at the
    场景's 音量; nothing under 静音."""
    own = tmp_path / "custom_sounds"
    own.mkdir()
    chosen, other = own / "ice-1.wav", own / "ice-2.wav"
    shutil.copyfile(TUNES["cyber"], chosen)
    shutil.copyfile(TUNES["fluffy"], other)
    music, played, _clock = _managed(tmp_path, {"ice": (chosen, 40), "classic": (None, 100)})
    assert music.song("ice", other) and played[-1].name.startswith("40-ice-2-") and not played[-1].name.endswith("ms.wav")
    assert np.abs(_samples(played[-1])[1] - np.rint(_samples(TUNES["fluffy"])[1] * 0.4)).max() <= 1
    assert music.song("ice") and played[-1].name.startswith(f"40-{TUNES['ice'].stem}-")
    assert not music.song("classic") and played[-1] is None
    music.muted = True
    assert not music.song("ice", other) and played[-1] is None


def test_dropping_one_tune_s_copies_keeps_every_other(tmp_path):
    """A player's song deleted: its quieter copies go, the other tunes' stay, a song of the same 场景's too."""
    own = tmp_path / "custom_sounds"
    own.mkdir()
    shutil.copyfile(TUNES["ice"], own / "ice-1.wav")
    shutil.copyfile(TUNES["cyber"], own / "ice-2.wav")
    music, played, _clock = _managed(tmp_path, {"ice": (own / "ice-1.wav", 50), "stars": (None, 50)})
    music.preview("ice")
    music.taste("ice")
    music.song("ice", own / "ice-2.wav")
    music.preview("stars")
    assert len(list((tmp_path / "sounds").iterdir())) == 4
    music.drop(own / "ice-1.wav")
    assert sorted(copy.name for copy in (tmp_path / "sounds").iterdir()) == sorted([played[-2].name, played[-1].name])
    # Nothing made yet, nothing to drop.
    bare, _played, _clock = _managed(tmp_path / "none", {})
    bare.drop(own / "ice.wav")


def test_the_song_from_a_moment_is_the_rest_of_it_at_a_volume_and_plays_as_it_is(tmp_path):
    """选择片段 plays the player's song from wherever its playhead is: winsound cannot start a file midway, so
    the rest of the song is written as a file of its own, as loud as the 场景's 音量, and played as it is."""
    song = np.rint(np.sin(np.arange(3 * RATE) / 7) * 20000).astype(np.int16)
    decoded = Decoded(song, 3.0, "心动音乐")
    rest = save_rest(decoded, 1.25, tmp_path / "trial" / "song-0.wav", 40)
    params, samples = _samples(rest)
    assert (params.nchannels, params.sampwidth, params.framerate) == (1, 2, RATE)
    assert len(samples) == len(song) - round(1.25 * RATE)
    assert np.abs(samples - np.rint(song[round(1.25 * RATE) :] * 0.4)).max() <= 1
    # From its very end, nothing; from before its start, all of it.
    assert len(_samples(save_rest(decoded, 9.0, tmp_path / "end.wav"))[1]) == 0
    assert np.array_equal(_samples(save_rest(decoded, -1.0, tmp_path / "all.wav"))[1], song)
    music, played, _clock = _managed(tmp_path, {})
    assert music.play_file(rest) and played == [rest]
    music.muted = True
    assert not music.play_file(rest) and played == [rest, None]


def test_a_taste_is_a_moment_of_the_effect_s_sound_as_loud_as_it_plays(tmp_path):
    """What a 场景's 音量 in 场景管理 plays as it is set: a moment of that 场景's sound, the player's own if
    it has one, at its 音量."""
    own = tmp_path / "custom_sounds"
    own.mkdir()
    shutil.copyfile(TUNES["fluffy"], own / "classic.wav")
    music, played, _clock = _managed(tmp_path, {"ice": (None, 30), "classic": (own / "classic.wav", 40)})
    assert music.taste("ice")
    params, samples = _samples(played[-1])
    assert played[-1].name.startswith(f"30-{TUNES['ice'].stem}-") and len(samples) == round(SAMPLE_S * params.framerate)
    _, ice = _samples(TUNES["ice"])
    head = len(samples) // 2
    assert np.abs(samples[:head] - np.rint(ice[:head] * 0.3)).max() <= 1
    assert music.taste("classic") and played[-1].name.startswith("40-classic-")
    # 经典 with none of the player's has nothing to taste.
    bare, played, _clock = _managed(tmp_path, {})
    assert not bare.taste("classic") and played == [None]


def test_effects_at_different_volumes_keep_their_copies_side_by_side(tmp_path):
    """Each 场景 at its own 音量: one quieter copy of each, made once, not one making the other's again."""
    music, played, _clock = _managed(tmp_path, {"ice": (None, 40), "stars": (None, 70)})
    music.preview("ice")
    music.preview("stars")
    music.taste("ice")
    first = list(played)
    assert len({tune.name for tune in first}) == 3 and all(tune.is_file() for tune in first)
    made = [tune.stat().st_mtime_ns for tune in first]
    played.clear()
    music.preview("ice")
    music.preview("stars")
    music.taste("ice")
    assert played == first and [tune.stat().st_mtime_ns for tune in first] == made
    assert sorted((tmp_path / "sounds").iterdir()) == sorted(first)


def test_the_window_greets_with_classic_s_own_sound_once_given_one(window):
    """经典 greets in silence until 场景管理 gives it the player's own sound."""
    window._show_panel(_lobby())
    assert window.tunes == []
    window._hide_panel_after_title()
    own = _own_sound(window.store, "classic", like="stars")
    window.music._last_lobby = frozenset()
    window._show_panel(_lobby())
    assert window.tunes == [own]


def test_only_the_app_running_for_the_player_makes_a_sound(monkeypatch):
    """Tests, tools/ui_shots.py and scripts that build the window stay silent: real sound is the app's alone."""
    import sys
    import types

    from blacklist_detect import ui_music

    calls = []
    fake = types.SimpleNamespace(PlaySound=lambda *args: calls.append(args), SND_FILENAME=1, SND_ASYNC=2, SND_NODEFAULT=4)
    monkeypatch.setitem(sys.modules, "winsound", fake)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ui_music, "AUDIBLE", False)
    ui_music.play_tune(TUNES["lace"])
    ui_music.play_tune(None)
    assert calls == []
    ui_music.allow_sound()
    ui_music.play_tune(TUNES["lace"])
    assert len(calls) == 1
