"""心动音乐: wedding music for two or more 心动 players, the one chosen in 设置 or a random one, once per lobby."""

import random
import wave

import pytest

from blacklist_detect.ui_music import KEYS, SAME_LOBBY_S, TUNES, WeddingMusic


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _music():  # noqa: ANN202
    played: list = []
    clock = Clock()
    return WeddingMusic(play=played.append, rng=random.Random(1), clock=clock), played, clock


def test_the_tunes_are_short():
    """Five tunes, each about five seconds, mono 16-bit 44.1 kHz."""
    assert KEYS == ("organ", "music-box", "8bit", "canon", "bells")
    for key, tune in TUNES.items():
        assert tune.is_file(), key
        with wave.open(str(tune)) as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 44100)
            assert w.getnframes() / w.getframerate() <= 5.25


def test_two_or_more_hearts_get_music_once_per_lobby():
    music, played, clock = _music()
    assert music.lobby([], "random") == ""
    assert music.lobby(["小红"], "random") == ""
    assert played == []
    first = music.lobby(["小红", "小明"], "random")
    assert first in KEYS and played == [TUNES[first]]
    # The same lobby checked again: the same players a moment later, in any order.
    clock.now += 5
    assert music.lobby(["小明", "小红"], "random") == ""
    # The next lobby: other players, or the same two a minute later.
    assert music.lobby(["小红", "阿强"], "random")
    clock.now += SAME_LOBBY_S + 1
    assert music.lobby(["小红", "阿强"], "random")
    assert len(played) == 3


def test_a_chosen_tune_plays_every_time_and_off_plays_none():
    music, played, clock = _music()
    assert music.lobby(["小红", "小明"], "off") == ""
    assert played == []
    for _ in range(3):
        clock.now += SAME_LOBBY_S + 1
        assert music.lobby(["小红", "小明"], "canon") == "canon"
    assert played == [TUNES["canon"]] * 3
    # Something it does not know, from a newer or older version: no music.
    assert music.pick("harpsichord") == ""


def test_random_is_never_the_same_tune_twice_running():
    music, played, _clock = _music()
    for _ in range(60):
        music.preview("random")
    assert set(played) == set(TUNES.values())
    assert all(a != b for a, b in zip(played, played[1:], strict=False))
    music.stop()
    assert played[-1] is None


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
    made.music = WeddingMusic(play=tunes.append, rng=random.Random(2))
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


def test_the_organ_plays_until_another_is_chosen(window):
    from blacklist_detect.storage import Store

    assert window.store.love_music == "organ"
    window._show_panel(_lobby())
    assert window.tunes == [TUNES["organ"]]
    window.store.love_music = "off"
    window.store.save_settings()
    assert Store(window.store.root).love_music == "off"


@pytest.mark.parametrize("safe", [True, False])
def test_music_plays_in_either_display_mode(window, safe):
    """安全模式 draws nothing over the game, but the music is only sound: it plays there too."""
    window.store.safe_mode = safe
    window.store.love_music = "bells"
    window._show_panel(_lobby())
    assert window.tunes == [TUNES["bells"]]


def test_a_blacklist_player_means_no_music(window):
    window.store.love_music = "random"
    window._show_panel(_lobby(hit=True))
    assert window.tunes == []


def test_clearing_the_data_puts_the_effects_back_to_their_defaults(window, monkeypatch):
    window.store.love_music = "canon"
    window.store.love_scene = "ice"
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda *_args: True)
    window._ask_reset()
    assert (window.store.love_music, window.store.love_scene) == ("organ", "classic")
    assert window.love.choice == "classic"
