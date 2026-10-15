"""嘉宾音乐: each 嘉宾特效 theme's own sound whenever a 嘉宾 is in the lobby, once per lobby; 音乐 only
turns it on (跟随特效) or off (无)."""

import wave

import pytest

from blacklist_detect import love_scenes
from blacklist_detect.ui_music import MUSIC_CHOICES, SAME_LOBBY_S, TUNES, ThemeMusic


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
    assert MUSIC_CHOICES == (("theme", "跟随特效"), ("off", "无"))


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
    made.music = ThemeMusic(play=tunes.append)
    made.tunes = tunes
    made.store.add_like("小红")
    made.store.add_like("小明")
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


def test_the_theme_brings_its_sound_until_music_is_off(window):
    from blacklist_detect.storage import Store

    assert window.store.love_music == "theme" and window.store.love_scene == "classic"
    # 经典 greets in silence.
    window._show_panel(_lobby())
    assert window.tunes == []
    window._hide_panel_after_title()
    window.store.update_like(1, "小明", "", "", "lace")
    window._on_lobby_placed(_lobby().button_box)
    window.music._last_lobby = frozenset()
    window._show_panel(_lobby())
    assert window.tunes == [TUNES["lace"]]
    window.store.love_music = "off"
    window.store.save_settings()
    assert Store(window.store.root).love_music == "off"


def test_an_old_tune_choice_follows_the_theme(tmp_path):
    """The five wedding tunes and 随机 were 音乐's choices once: they follow the theme now; 无 stays off."""
    import json

    from blacklist_detect.storage import Store

    Store(tmp_path).save_settings()
    path = tmp_path / "settings.json"
    for saved, now in (("organ", "theme"), ("8bit", "theme"), ("random", "theme"), ("off", "off"), (None, "theme")):
        settings = json.loads(path.read_text(encoding="utf-8"))
        settings["love_music"] = saved
        path.write_text(json.dumps(settings), encoding="utf-8")
        assert Store(tmp_path).love_music == now, saved


@pytest.mark.parametrize("safe", [True, False])
def test_music_plays_in_either_display_mode(window, safe):
    """安全模式 draws nothing over the game, but the music is only sound: it plays there too."""
    window.store.safe_mode = safe
    window.store.update_like(1, "小明", "", "", "angel")
    window._show_panel(_lobby())
    assert window.tunes == [TUNES["angel"]]


def test_a_blacklist_player_means_no_music(window):
    window._show_panel(_lobby(hit=True))
    assert window.tunes == []


def test_clearing_the_data_puts_the_effects_back_to_their_defaults(window, monkeypatch):
    window.love_music_choice.buttons["off"].click()
    window.love_switch.click()
    assert (window.store.love_music, window.store.love_scene) == ("off", "off")
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda *_args: True)
    window._ask_reset()
    assert (window.store.love_music, window.store.love_scene) == ("theme", "classic")
    assert window.love.choice == "classic"
    assert window.love_switch.isChecked() and window.love_music_choice.current() == "theme"
    assert not window.love_music_choice.isHidden()


def test_the_settings_switch_turns_guest_effects_off_with_music_beside_it(window):
    """设置 › 嘉宾 › 嘉宾特效: on, each 嘉宾 and 组合 is greeted with its 特效 (经典 for none) and 音乐
    sits on the same row, its default first; off, no scene greets anyone and 音乐 goes."""
    from blacklist_detect.storage import Store

    window.store.update_like(1, "小明", "", "", "angel")
    assert window.love_switch.isChecked() and window.love_switch.accessibleName() == "嘉宾特效"
    assert [(key, button.text()) for key, button in window.love_music_choice.buttons.items()] == list(MUSIC_CHOICES)
    assert window.love_music_choice.current() == "theme" and not window.love_music_label.isHidden()
    assert window._choice_for(window.store.likes) == "angel"
    window.love_switch.click()
    assert window.store.love_scene == "off" and Store(window.store.root).love_scene == "off"
    assert window.love_music_choice.isHidden() and window.love_music_label.isHidden()
    assert window._choice_for(window.store.likes) == "off"
    window._show_panel(_lobby())
    assert not window.love.playing() and window.tunes == []
    window._hide_panel_after_title()
    window.love_switch.click()
    assert window.store.love_scene == "classic" and not window.love_music_choice.isHidden()
    window.love_music_choice.buttons["off"].click()
    assert Store(window.store.root).love_music == "off"


def test_an_old_saved_off_stays_off(tmp_path, monkeypatch):
    """嘉宾特效 set to 无 before 设置 had the switch: it opens off."""
    import json

    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from blacklist_detect.storage import Store
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    store = Store()
    store.save_settings()
    settings = json.loads(store.settings_path.read_text(encoding="utf-8"))
    settings["love_scene"] = "off"
    store.settings_path.write_text(json.dumps(settings), encoding="utf-8")
    window = MainWindow()
    window._watch_timer.stop()
    assert window.store.love_scene == "off" and not window.love_switch.isChecked()
    assert window.love_music_choice.isHidden() and window.love.choice == "off"
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
    """嘉宾特效 plays whenever a 嘉宾 is in the lobby, one or more: each 嘉宾 and 组合 picks what greets them."""
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
    """A 嘉宾's own 特效 brings its own sound: 演说家遇袭 the 指挥家's music with the notice in it."""
    with wave.open(str(TUNES["claw"])) as w:
        assert 6.0 <= w.getnframes() / w.getframerate() <= 7.0
    # 阿强, added last, tops the list: his 演说家遇袭 greets the lobby, and its sound with it.
    window.store.add_like("阿强", theme="claw")
    window._show_panel(_likes(3))
    assert window.tunes == [TUNES["claw"]]
