"""嘉宾音乐: wedding music for the 嘉宾人数 chosen (two or more until changed), the tune chosen in
嘉宾特效 or a random one, once per lobby."""

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


def test_hearts_get_music_once_per_lobby():
    """The window asks only for a lobby with as many 嘉宾 players as 嘉宾人数 plays for."""
    music, played, clock = _music()
    assert music.lobby([], "random") == ""
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
    # One player is a lobby too, when 1人 is ticked.
    assert music.lobby(["小红"], "random")
    assert len(played) == 4


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
    window.store.love_counts = (1,)
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda *_args: True)
    window._ask_reset()
    assert (window.store.love_music, window.store.love_scene) == ("organ", "classic")
    assert window.store.love_counts == (2, 3)
    assert window.love.choice == "classic"


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


@pytest.mark.parametrize(
    ("counts", "played_for"),
    [
        ((2, 3), (2, 3)),  # the default: two or more
        ((1,), (1,)),
        ((1, 2, 3), (1, 2, 3)),  # every 嘉宾 player
        ((3,), (3,)),  # 2人以上 only: three or more
    ],
)
def test_the_effect_plays_for_the_numbers_ticked(window, counts, played_for):
    """嘉宾人数: the border and the music both play for a lobby with as many 嘉宾 players as ticked."""
    from blacklist_detect.storage import DEFAULT_LOVE_COUNTS

    assert window.store.love_counts == DEFAULT_LOVE_COUNTS == (2, 3)
    window.store.add_like("阿强")
    window.store.love_counts = counts
    window.store.safe_mode = False
    window.store.consented = ["full"]
    window._on_display_mode("full")
    for likes in (1, 2, 3):
        window.tunes.clear()
        window.music._last_lobby = None
        window._love_played = False
        window._show_panel(_likes(likes))
        plays = likes in played_for
        assert window.love.playing() is plays, likes
        assert (window.tunes == [TUNES["organ"]]) is plays, likes
        # The marks show whatever the count: the 嘉宾 card names them.
        assert window.panel.mode == "liked" and window.like_card.isVisible()
        window._hide_panel_after_title()


def test_a_scene_brings_its_own_tune_but_never_by_chance():
    """遇袭 plays its own tune (the 指挥家's music and the notice) in place of the chosen one; 随机 never
    picks it."""
    from blacklist_detect.ui_music import SCENE_TUNES

    tune = SCENE_TUNES["ambush"]
    with wave.open(str(tune)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 44100)
        assert 6.0 <= w.getnframes() / w.getframerate() <= 7.0
    music, played, _clock = _music()
    assert music.preview("ambush") == "ambush" and played == [tune]
    assert all(music.pick("random") in KEYS for _ in range(30))
