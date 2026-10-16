"""选择片段 (ui_sound_trim): picking the part of a long uploaded sound a 场景 plays, with made-up sounds only."""

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402
from test_theme import contrast  # noqa: E402

from blacklist_detect.ui_kit import _height_for  # noqa: E402
from blacklist_detect.ui_sound_trim import LIMIT_S, MIN_S, SoundTrimDialog, clock, peaks  # noqa: E402
from blacklist_detect.ui_theme import THEME, THEMES, use_theme  # noqa: E402

RATE = 8000
SHORT = 672


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _sound(seconds: float) -> np.ndarray:
    """A made-up sound: a tone growing louder, so each part looks its own."""
    t = np.arange(round(seconds * RATE)) / RATE
    return (np.sin(2 * np.pi * 440 * t) * (0.1 + 0.8 * t / max(seconds, 0.001)) * 32767).astype(np.int16)


class Player:
    """What the dialog asks to hear, instead of any sound, and the time it is told (moved on by hand)."""

    def __init__(self) -> None:
        self.played: list[tuple[float, float]] = []
        self.songs: list[float] = []
        self.stopped = 0
        self.time = 100.0

    def preview(self, start: float, length: float) -> None:
        self.played.append((start, length))

    def play(self, at: float) -> str:
        self.songs.append(at)
        return ""

    def stop(self) -> None:
        self.stopped += 1

    def now(self) -> float:
        return self.time


@pytest.fixture
def player():
    return Player()


def _dialog(player: Player, seconds: float = 20.0, **kwargs) -> SoundTrimDialog:  # noqa: ANN003
    kwargs.setdefault("play", player.play)
    return SoundTrimDialog(_sound(seconds), RATE, "心动音乐.mp3", player.preview, player.stop, now=player.now, **kwargs)


def _later(dialog: SoundTrimDialog, player: Player, seconds: float) -> None:
    """seconds go by, and the dialog's timer ticks once."""
    player.time += seconds
    dialog._advance()


def _mouse(widget, kind, x: float, buttons=Qt.LeftButton) -> None:  # noqa: ANN001
    at = QPointF(x, widget.height() / 2)
    button = Qt.NoButton if kind == QEvent.Type.MouseMove else Qt.LeftButton
    QApplication.sendEvent(widget, QMouseEvent(kind, at, widget.mapToGlobal(at), button, buttons, Qt.NoModifier))


def _drag(widget, from_x: float, to_x: float) -> None:  # noqa: ANN001
    _mouse(widget, QEvent.Type.MouseButtonPress, from_x)
    _mouse(widget, QEvent.Type.MouseMove, (from_x + to_x) / 2)
    _mouse(widget, QEvent.Type.MouseMove, to_x)
    _mouse(widget, QEvent.Type.MouseButtonRelease, to_x, Qt.NoButton)


def _key(widget, key) -> None:  # noqa: ANN001
    QApplication.sendEvent(widget, QKeyEvent(QEvent.Type.KeyPress, key, Qt.NoModifier))


def test_moments_read_as_minutes_seconds_and_tenths():
    assert clock(0) == "0:00.0"
    assert clock(12.34) == "0:12.3"
    assert clock(5) == "0:05.0"
    assert clock(65.0) == "1:05.0"
    assert clock(599.96) == "10:00.0"


def test_the_peaks_are_the_loudest_sample_of_each_stretch():
    samples = np.zeros(1000, dtype=np.int16)
    samples[10] = -32768
    samples[600] = 1200
    found = peaks(samples, 10)
    assert len(found) == 10 and found[0] == 32768 and found[6] == 1200 and found[3] == 0
    # Fewer samples than columns, and none at all.
    assert len(peaks(samples[:4], 10)) == 10
    assert not peaks(np.zeros(0, dtype=np.int16), 8).any()


def test_it_opens_on_the_first_five_seconds_with_the_name_and_length(qapp, player):
    dialog = _dialog(player)
    assert dialog.windowTitle() == "选择片段"
    assert dialog.selection() == (0.0, LIMIT_S)
    assert dialog.name.text() == "心动音乐.mp3"
    # 截取 says what it takes; no line says what is picked, or how to pick it.
    assert dialog.cut_button.text() == "截取刚听到的 5 秒" and dialog.why.text() == ""
    assert not hasattr(dialog, "hint") and not hasattr(dialog, "times")
    assert dialog.where.text() == "0:00.0 / 0:20.0" and dialog.wave.playhead == 0.0
    assert not dialog.has_changes()


def test_the_songs_time_is_at_the_end_of_the_row_with_cut(qapp, player):
    dialog = _dialog(player)
    dialog.show()
    qapp.processEvents()
    try:
        where, cut = dialog.where.geometry(), dialog.cut_button.geometry()
        wave = dialog.wave.geometry()
        assert abs(where.center().y() - cut.center().y()) <= 2 and where.left() > cut.right()
        assert abs(where.right() - wave.right()) <= 2 and where.top() > wave.bottom()
    finally:
        dialog.reject()


def test_the_song_plays_from_its_start_as_it_opens_and_the_playhead_follows_the_clock(qapp, player):
    dialog = _dialog(player)
    assert player.songs == [] and not dialog.running
    dialog.show()
    try:
        assert player.songs == [0.0] and dialog.running and dialog._tick.isActive()
        assert dialog.pause_button.text() == "暂停"
        _later(dialog, player, 2.5)
        assert dialog.head() == pytest.approx(2.5) and dialog.wave.playhead == pytest.approx(2.5)
        assert dialog.where.text() == "0:02.5 / 0:20.0"
        # Shown again, it does not start over.
        dialog.hide()
        dialog.show()
        assert player.songs == [0.0]
    finally:
        dialog.reject()


def test_pause_and_play_go_on_from_the_playhead(qapp, player):
    dialog = _dialog(player)
    dialog._start_song()
    _later(dialog, player, 3.0)
    dialog.pause_button.click()
    assert not dialog.running and player.stopped == 1 and dialog.pause_button.text() == "播放"
    # Paused, the playhead stays.
    _later(dialog, player, 4.0)
    assert dialog.head() == pytest.approx(3.0)
    dialog.pause_button.click()
    assert player.songs == [0.0, pytest.approx(3.0)] and dialog.running
    _later(dialog, player, 1.0)
    assert dialog.head() == pytest.approx(4.0)


def test_at_its_end_the_song_stops_and_play_starts_it_over(qapp, player):
    dialog = _dialog(player)
    dialog._start_song()
    _later(dialog, player, 25.0)
    assert not dialog.running and dialog.head() == 20.0 and dialog.pause_button.text() == "播放"
    assert not dialog._tick.isActive() and dialog.where.text() == "0:20.0 / 0:20.0"
    dialog.pause_button.click()
    assert player.songs == [0.0, 0.0] and dialog.running


def test_a_press_on_the_strip_moves_the_playhead_and_the_song_goes_on_from_there(qapp, player):
    dialog = _dialog(player)
    wave = dialog.wave
    dialog._start_song()
    _later(dialog, player, 1.0)
    _drag(wave, wave.x_of(12.0), wave.x_of(12.0))
    assert dialog.head() == pytest.approx(12.0, abs=0.05) and wave.playhead == pytest.approx(12.0, abs=0.05)
    assert player.songs == [0.0, pytest.approx(12.0, abs=0.05)] and dialog.running
    # The part picked stays where it was.
    assert dialog.selection() == (0.0, LIMIT_S)
    # Dragged, the song waits until it is let go, then goes on from there, once.
    _drag(wave, wave.x_of(8.0), wave.x_of(16.0))
    assert player.songs[-1] == pytest.approx(16.0, abs=0.05) and len(player.songs) == 3
    # Past the ends the playhead stops at them.
    _drag(wave, wave.x_of(8.0), -200)
    assert dialog.head() == 0.0
    # Paused, a press moves the playhead and nothing plays.
    dialog.pause_button.click()
    _drag(wave, wave.x_of(9.0), wave.x_of(9.0))
    assert dialog.head() == pytest.approx(9.0, abs=0.05) and not dialog.running and len(player.songs) == 4
    dialog.pause_button.click()
    assert player.songs[-1] == pytest.approx(9.0, abs=0.05)


def test_cut_takes_the_five_seconds_just_heard(qapp, player):
    dialog = _dialog(player)
    dialog._start_song()
    _later(dialog, player, 9.3)
    dialog.cut_button.click()
    start, length = dialog.selection()
    assert start == pytest.approx(4.3) and length == LIMIT_S and dialog.has_changes()
    # The song goes on.
    assert dialog.running and player.songs == [0.0] and player.stopped == 0
    # Before 5 s in, the first 5 s.
    dialog = _dialog(player)
    dialog._start_song()
    _later(dialog, player, 2.0)
    dialog.wave.set_selection(8.0, 2.0)
    dialog.cut_button.click()
    assert dialog.selection() == (0.0, LIMIT_S)
    # At the very end, the last 5 s; a shortened window is 5 s again.
    dialog = _dialog(player)
    dialog.wave.set_selection(3.0, 1.0)
    dialog._start_song()
    _later(dialog, player, 30.0)
    dialog.cut_button.click()
    assert dialog.selection() == (15.0, LIMIT_S)


@pytest.mark.parametrize("seconds", [180.0, 600.0])
def test_on_a_narrow_window_each_half_takes_its_edge_and_beyond_moves_the_playhead(qapp, player, seconds):
    """5 s of a 3 minute song is 15 pixels, of a 10 minute one under 5, its two grips one blob: its left half
    takes the left edge, its right half the right one, and a press just beyond them moves the playhead."""
    dialog = _dialog(player, seconds=seconds)
    wave = dialog.wave
    middle = seconds / 2
    left, right = wave.x_of(middle), wave.x_of(middle + LIMIT_S)
    centre = (left + right) / 2
    wave.set_selection(middle, LIMIT_S)
    _drag(wave, centre - 1, wave.x_of(middle + 3.0))
    start, length = dialog.selection()
    assert length < LIMIT_S and start + length == pytest.approx(middle + LIMIT_S)
    wave.set_selection(middle, LIMIT_S)
    _drag(wave, centre + 1, wave.x_of(middle + 2.0))
    start, length = dialog.selection()
    assert length < LIMIT_S and start == middle
    wave.set_selection(middle, LIMIT_S)
    _drag(wave, right + 9, right + 9)
    assert dialog.selection() == (middle, LIMIT_S) and dialog.head() == pytest.approx(wave.time_at(right + 9))


def test_inside_a_wide_window_a_press_moves_the_playhead_and_its_edges_are_still_taken(qapp, player):
    dialog = _dialog(player)
    wave = dialog.wave
    wave.set_selection(10.0, LIMIT_S)
    _drag(wave, wave.x_of(12.5), wave.x_of(16.0))
    assert dialog.selection() == (10.0, LIMIT_S) and dialog.head() == pytest.approx(16.0, abs=0.05)
    # Just outside an edge takes that edge.
    _drag(wave, wave.x_of(15.0) + 3, wave.x_of(14.0))
    start, length = dialog.selection()
    assert start == 10.0 and start + length == pytest.approx(14.0, abs=0.05)
    _drag(wave, wave.x_of(10.0) - 3, wave.x_of(11.0))
    start, length = dialog.selection()
    assert start == pytest.approx(11.0, abs=0.05) and start + length == pytest.approx(14.0, abs=0.05)


def test_the_right_edge_shortens_and_lengthens_within_the_limits(qapp, player):
    dialog = _dialog(player)
    wave = dialog.wave
    _drag(wave, wave.x_of(5.0), wave.x_of(3.0))
    assert dialog.selection()[0] == 0.0 and dialog.selection()[1] == pytest.approx(3.0, abs=0.05)
    # Never longer than 5 s, never shorter than half a second.
    _drag(wave, wave.x_of(3.0), wave.x_of(12.0))
    assert dialog.selection() == (0.0, LIMIT_S)
    _drag(wave, wave.x_of(5.0), wave.x_of(0.0))
    assert dialog.selection() == (0.0, MIN_S)


def test_the_left_edge_shortens_and_lengthens_within_the_limits(qapp, player):
    dialog = _dialog(player)
    wave = dialog.wave
    wave.set_selection(10.0, 5.0)
    _drag(wave, wave.x_of(10.0), wave.x_of(12.0))
    start, length = dialog.selection()
    assert start == pytest.approx(12.0, abs=0.05) and start + length == pytest.approx(15.0)
    # Pulled back past 5 s from its end it stops at 5 s; pulled on past its end, at half a second.
    _drag(wave, wave.x_of(12.0), wave.x_of(4.0))
    assert dialog.selection() == (10.0, LIMIT_S)
    _drag(wave, wave.x_of(10.0), wave.x_of(19.0))
    assert dialog.selection() == (14.5, MIN_S)


def test_the_left_edge_stops_at_the_start_of_the_sound(qapp, player):
    dialog = _dialog(player)
    wave = dialog.wave
    wave.set_selection(1.0, 3.0)
    _drag(wave, wave.x_of(1.0), -100)
    assert dialog.selection() == (0.0, 4.0)


def test_the_right_edge_stops_at_the_end_of_the_sound(qapp, player):
    dialog = _dialog(player)
    wave = dialog.wave
    wave.set_selection(17.0, 1.0)
    _drag(wave, wave.x_of(18.0), wave.width() + 100)
    assert dialog.selection() == (17.0, 3.0)


def test_the_arrow_keys_move_the_window_by_a_tenth(qapp, player):
    dialog = _dialog(player)
    wave = dialog.wave
    _key(wave, Qt.Key_Right)
    _key(wave, Qt.Key_Right)
    assert dialog.selection() == (0.2, LIMIT_S)
    _key(wave, Qt.Key_Left)
    assert dialog.selection() == (0.1, LIMIT_S)
    # Not before the start, nor past the end.
    for _ in range(5):
        _key(wave, Qt.Key_Left)
    assert dialog.selection() == (0.0, LIMIT_S)
    wave.set_selection(14.95, 5.0)
    _key(wave, Qt.Key_Right)
    assert dialog.selection() == (15.0, LIMIT_S)
    # With 试听 or 确定 focused they still move the window.
    _key(dialog.play_button, Qt.Key_Left)
    assert dialog.selection() == (14.9, LIMIT_S)
    _key(dialog.ok_button, Qt.Key_Left)
    assert dialog.selection() == (14.8, LIMIT_S)
    _key(dialog.cut_button, Qt.Key_Left)
    assert dialog.selection() == (14.7, LIMIT_S)


def test_the_nudge_buttons_move_the_window_by_a_tenth_and_repeat_while_held(qapp, player):
    dialog = _dialog(player)
    dialog._start_song()
    assert dialog.back_button.autoRepeat() and dialog.on_button.autoRepeat()
    dialog.on_button.click()
    dialog.on_button.click()
    assert dialog.selection() == (0.2, LIMIT_S)
    dialog.back_button.click()
    assert dialog.selection() == (0.1, LIMIT_S)
    # Not before the start, nor past the end; the song plays on.
    for _ in range(3):
        dialog.back_button.click()
    assert dialog.selection() == (0.0, LIMIT_S)
    dialog.wave.set_selection(14.95, LIMIT_S)
    dialog.on_button.click()
    assert dialog.selection() == (15.0, LIMIT_S)
    assert dialog.running and player.songs == [0.0]


def test_play_previews_the_part_picked_and_turns_into_stop(qapp, player):
    dialog = _dialog(player)
    dialog.wave.set_selection(6.2, 4.0)
    assert dialog.play_button.text() == "试听"
    dialog.play_button.click()
    assert player.played == [(6.2, 4.0)] and player.stopped == 0
    assert dialog.playing and dialog.play_button.text() == "停止"
    dialog.play_button.click()
    assert player.stopped == 1 and not dialog.playing and dialog.play_button.text() == "试听"
    assert player.played == [(6.2, 4.0)]


def test_moving_the_window_while_it_plays_stops_the_sound(qapp, player):
    dialog = _dialog(player)
    dialog.play_button.click()
    _key(dialog.wave, Qt.Key_Right)
    assert player.stopped == 1 and not dialog.playing and dialog.play_button.text() == "试听"
    # Moving it while nothing plays stops nothing.
    _key(dialog.wave, Qt.Key_Right)
    assert player.stopped == 1


def test_play_turns_back_once_the_part_has_played(qapp, player):
    dialog = _dialog(player)
    dialog.wave.set_selection(2.0, MIN_S)
    dialog.play_button.click()
    assert dialog.wave.trial == 2.0 and dialog._tick.isActive()
    _later(dialog, player, 0.3)
    assert dialog.playing and dialog.wave.trial == pytest.approx(2.3)
    _later(dialog, player, 0.3)
    # It ended by itself: nothing is cut short.
    assert not dialog.playing and dialog.play_button.text() == "试听" and player.stopped == 0
    assert dialog.wave.trial is None and not dialog._tick.isActive()


def test_the_timer_runs_the_trial_with_the_real_clock(qapp):
    """Without a clock of the test's own, time.monotonic and the dialog's timer end 试听 by themselves."""
    player = Player()
    dialog = SoundTrimDialog(_sound(20), RATE, "心动音乐.mp3", player.preview, player.stop)
    dialog.wave.set_selection(0.0, MIN_S)
    dialog.play_button.click()
    end = time.monotonic() + 3
    while dialog.playing and time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.01)
    assert not dialog.playing and player.stopped == 0


def test_trial_pauses_the_song_and_play_goes_on_from_the_playhead(qapp, player):
    dialog = _dialog(player)
    dialog._start_song()
    _later(dialog, player, 7.0)
    dialog.wave.set_selection(1.0, 3.0)
    dialog.play_button.click()
    assert not dialog.running and dialog.playing and player.stopped == 1 and player.played == [(1.0, 3.0)]
    assert dialog.pause_button.text() == "播放" and dialog.head() == pytest.approx(7.0)
    # The trial's mark moves through the part; the playhead stays.
    _later(dialog, player, 1.0)
    assert dialog.wave.trial == pytest.approx(2.0) and dialog.wave.playhead == pytest.approx(7.0)
    # 播放 cuts the trial short (the song takes over the sound) and goes on from the playhead.
    dialog.pause_button.click()
    assert not dialog.playing and dialog.running and player.songs == [0.0, pytest.approx(7.0)]
    assert dialog.play_button.text() == "试听"


def test_ok_gives_the_part_picked(qapp, player):
    dialog = _dialog(player)
    dialog.wave.set_selection(3.3, 4.2)
    dialog.play_button.click()
    ok = dialog.ok_button
    assert ok.text() == "确定" and ok.objectName() == "primary" and ok.isDefault()
    ok.click()
    assert dialog.result() == QDialog.Accepted
    assert dialog.selection() == (3.3, 4.2)
    # What played stops as it closes, and nothing plays after.
    assert player.stopped == 1 and player.played == [(3.3, 4.2)] and player.songs == []


def test_ok_stops_the_song_and_plays_nothing(qapp, player):
    dialog = _dialog(player)
    dialog._start_song()
    _later(dialog, player, 8.0)
    dialog.cut_button.click()
    dialog.ok_button.click()
    assert dialog.result() == QDialog.Accepted and dialog.selection() == (3.0, LIMIT_S)
    assert not dialog.running and not dialog._tick.isActive() and player.stopped == 1
    assert player.songs == [0.0] and player.played == []


def test_the_cross_and_esc_cancel(qapp, player):
    dialog = _dialog(player)
    dialog.play_button.click()
    dialog.close_button.click()
    assert dialog.result() == QDialog.Rejected and player.stopped == 1
    dialog = _dialog(player)
    dialog.wave.set_selection(4.0, 5.0)
    _key(dialog, Qt.Key_Escape)
    assert dialog.result() == QDialog.Rejected
    # A click outside the card would lose the part picked: the card shakes instead.
    dialog = _dialog(player)
    dialog.wave.set_selection(4.0, 5.0)
    dialog.click_outside()
    assert dialog.shaking() and dialog.result() != QDialog.Accepted


def test_a_sound_no_longer_than_the_limit_still_works(qapp, player):
    dialog = _dialog(player, seconds=3.0)
    assert dialog.selection() == (0.0, 3.0)
    _key(dialog.wave, Qt.Key_Right)
    assert dialog.selection() == (0.0, 3.0)
    wave = dialog.wave
    _drag(wave, wave.x_of(3.0), wave.x_of(2.0))
    assert dialog.selection()[1] == pytest.approx(2.0, abs=0.05)
    # A sound shorter than half a second is taken whole.
    tiny = _dialog(player, seconds=0.3)
    assert tiny.selection() == (0.0, 0.3)
    tiny.wave.set_selection(0.0, 0.1)
    assert tiny.selection() == (0.0, 0.3)


def test_another_limit(qapp, player):
    dialog = _dialog(player, limit_s=3.0)
    assert dialog.selection() == (0.0, 3.0)
    wave = dialog.wave
    _drag(wave, wave.x_of(3.0), wave.x_of(9.0))
    assert dialog.selection() == (0.0, 3.0)


def test_it_fits_a_short_screen_and_the_window(qapp, player):
    """1080p at 150% leaves 672 px: the card and its 确定 fit without scrolling, and it is no wider than the
    app's 900 px window."""
    dialog = _dialog(player, seconds=600.0)
    dialog.fit_height(SHORT)
    card = dialog.card
    width = max(card.minimumWidth(), min(card.maximumWidth(), card.sizeHint().width()))
    margins = dialog.layout().contentsMargins()
    assert dialog.scroll is None
    assert _height_for(card, width) + margins.top() + margins.bottom() <= SHORT - 8
    assert width + margins.left() + margins.right() <= 900


def test_a_long_name_is_cut_in_the_middle(qapp, player):
    name = "一首名字特别特别特别特别特别特别特别特别特别特别特别特别特别特别长的心动音乐.mp3"
    dialog = SoundTrimDialog(_sound(20), RATE, name, player.preview, player.stop)
    assert dialog.name.text() != name and dialog.name.text().endswith(".mp3") and dialog.name.toolTip() == name
    assert dialog.name.sizeHint().width() <= dialog.wave.width() + 8


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_sound_is_drawn_in_the_accent_and_reads_in_both_schemes(qapp, player, scheme):
    use_theme("蓝色", scheme)
    try:
        dialog = _dialog(player)
        wave = dialog.wave
        image = wave.grab().toImage()
        accent = THEME["accent_line"]
        assert contrast(accent, THEME["surface_alt"]) >= 3
        # The middle row across the window is the accent; outside it, not.
        ratio, row = image.devicePixelRatio(), image.height() // 2
        inside = image.pixelColor(round(wave.x_of(2.0) * ratio), row).name()
        outside = image.pixelColor(round(wave.x_of(12.0) * ratio), row).name()
        assert inside == accent and outside != accent
    finally:
        use_theme("蓝色", "light")


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_outside_the_window_is_plainly_dimmer_in_every_accent(qapp, player, scheme):
    """What does not play is drawn on a darker ground than the window, as plainly in the light scheme as in the
    dark one (the light one's accent wash and alt once matched, about 1.02:1)."""
    try:
        for name in THEMES:
            use_theme(name, scheme)
            dialog = _dialog(player)
            wave = dialog.wave
            image = wave.grab().toImage()
            # A row above the sound's bars.
            ratio, row = image.devicePixelRatio(), round(5 * image.devicePixelRatio())
            inside = image.pixelColor(round(wave.x_of(2.0) * ratio), row).name()
            outside = image.pixelColor(round(wave.x_of(12.0) * ratio), row).name()
            assert contrast(inside, outside) >= 1.2, (name, inside, outside)
            assert contrast(inside, THEME["accent_line"]) >= 3, name
    finally:
        use_theme("蓝色", "light")


def test_under_mute_nothing_plays_but_the_playhead_moves_and_cut_takes(qapp, player):
    dialog = _dialog(player, muted=True)
    for button in (dialog.play_button, dialog.pause_button):
        assert not button.isEnabled() and button.toolTip() == "已静音"
    dialog.show()
    try:
        assert player.songs == [] and not dialog.running
        dialog.toggle_preview()
        dialog.toggle_song()
        assert player.played == [] and player.songs == [] and not dialog.playing and not dialog.running
        # A press moves the playhead, and 截取 takes the 5 s up to it.
        wave = dialog.wave
        _drag(wave, wave.x_of(11.0), wave.x_of(11.0))
        assert dialog.head() == pytest.approx(11.0, abs=0.05) and player.songs == []
        dialog.cut_button.click()
        start, length = dialog.selection()
        assert start == pytest.approx(6.0, abs=0.05) and length == LIMIT_S
        # 确定 still keeps the part picked.
        dialog.wave.set_selection(3.0, 2.0)
        dialog.ok_button.click()
        assert dialog.result() == QDialog.Accepted and dialog.selection() == (3.0, 2.0)
    finally:
        dialog.reject()


def test_a_reason_the_song_cannot_play_shows_in_red(qapp, player):
    dialog = _dialog(player, play=lambda _at: "放不了，再试一次")
    dialog.toggle_song()
    assert not dialog.running and dialog.why.text() == "放不了，再试一次" and dialog.why.objectName() == "error"
