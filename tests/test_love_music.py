"""心动音乐: wedding music for two or more 心动 players, a random take each time, once per lobby."""

import random
import wave

import pytest

from blacklist_detect.ui_music import SAME_LOBBY_S, TUNES, WeddingMusic


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _music():  # noqa: ANN202
    played: list = []
    clock = Clock()
    return WeddingMusic(play=played.append, rng=random.Random(1), clock=clock), played, clock


def test_the_tunes_are_short_and_like_the_chime():
    """Three takes, each under five seconds, mono 16-bit 44.1 kHz as hit.wav is."""
    assert len(TUNES) == 3
    for tune in TUNES:
        assert tune.is_file(), tune.name
        with wave.open(str(tune)) as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 44100)
            assert w.getnframes() / w.getframerate() <= 5.0


def test_two_or_more_hearts_get_music_once_per_lobby():
    music, played, clock = _music()
    assert music.lobby([]) is None
    assert music.lobby(["小红"]) is None
    assert played == []
    first = music.lobby(["小红", "小明"])
    assert first in TUNES and played == [first]
    # The same lobby checked again: the same players a moment later, in any order.
    clock.now += 5
    assert music.lobby(["小明", "小红"]) is None
    # The next lobby: other players, or the same two a minute later.
    assert music.lobby(["小红", "阿强"]) is not None
    clock.now += SAME_LOBBY_S + 1
    assert music.lobby(["小红", "阿强"]) is not None
    assert len(played) == 3


def test_the_take_is_random_but_never_twice_running():
    music, played, _clock = _music()
    for _ in range(40):
        music.preview()
    assert set(played) == set(TUNES)
    assert all(a != b for a, b in zip(played, played[1:], strict=False))


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from blacklist_detect import ui
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    chimes: list[int] = []
    monkeypatch.setattr(ui, "play_hit_sound", lambda: chimes.append(1))
    made = MainWindow()
    made._watch_timer.stop()
    made.store.disclaimer_accepted = True
    tunes: list = []
    made.music = WeddingMusic(play=tunes.append, rng=random.Random(2))
    made.chimes, made.tunes = chimes, tunes
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
        NameSlot(0, (0, 0, 1, 1), "坏人", "坏人", False, 0.9, False),
        NameSlot(1, (0, 0, 1, 1), "小红", "小红", False, 0.9, False),
        NameSlot(2, (0, 0, 1, 1), "小明", "小明", False, 0.9, False),
    ]
    hits = [Hit(0, "坏人", "坏人", "", False, "", ())] if hit else []
    return CheckResult(True, "", names=names, hits=hits, button_box=button)


def test_music_is_off_until_turned_on(window):
    window.store.add_like("小红")
    window.store.add_like("小明")
    window._live_check = True
    assert window.store.love_music is False and not window.music_switch.isChecked()
    window._show_panel(_lobby())
    assert window.tunes == []
    window.music_switch.click()
    assert window.store.love_music is True
    from blacklist_detect.storage import Store

    assert Store(window.store.root).love_music is True
    window._show_panel(_lobby())
    assert len(window.tunes) == 1


@pytest.mark.parametrize("safe", [True, False])
def test_music_plays_in_either_display_mode(window, safe):
    """安全模式 draws nothing over the game, but the music is only sound: it plays there too."""
    window.store.add_like("小红")
    window.store.add_like("小明")
    window.store.safe_mode = safe
    window.store.love_music = True
    window._live_check = True
    window._show_panel(_lobby())
    assert len(window.tunes) == 1


def test_a_blacklist_player_means_the_chime_not_the_music(window):
    window.store.add_like("小红")
    window.store.add_like("小明")
    window.store.love_music = True
    window._live_check = True
    window._show_panel(_lobby(hit=True))
    assert window.tunes == [] and window.chimes == [1]


def test_music_can_be_heard_from_settings_and_is_reset(window, monkeypatch):
    window.music_play.click()
    assert len(window.tunes) == 1
    window.music_switch.click()
    assert window.store.love_music is True
    # 清空数据 turns it off again, switch and all.
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda *_args: True)
    window._ask_reset()
    assert window.store.love_music is False and not window.music_switch.isChecked()
