"""Which 场景 a lobby gets: its 组合, else its top 嘉宾, a 黑名单 player there too or not; else 我's, unless a
黑名单 player is there. And what the marks and the music do for each."""

from pathlib import Path

import pytest

from blacklist_detect.guests import lobby_scene
from blacklist_detect.model import ANY_SCENE, Combo, Entry, Scenes

OFF = Scenes()


def _one(key: str) -> Scenes:
    return Scenes((key,))


# The list as saved: the last is the top.
LIKES = [
    Entry("小明", scenes=_one("cyber")),
    Entry("小红"),
    Entry("阿星", scenes=_one("angel")),
    Entry("不要场景的人", scenes=OFF),
]
COMBOS = [Combo(("小明", "小红"), _one("lace"))]


def _present(*names: str) -> list[Entry]:
    return [like for like in LIKES if like.name in names]


# Choosing one -------------------------------------------------------------------------------------


@pytest.mark.parametrize("blacklisted", [False, True])
def test_a_combination_there_decides_with_a_blacklist_player_or_not(blacklisted):
    assert lobby_scene(LIKES, COMBOS, _present("小明", "小红"), _one("ice"), blacklisted) == ("combo", "lace")
    # On 不放, the next in line: 小明's own.
    combos = [Combo(("小明", "小红"), OFF)]
    assert lobby_scene(LIKES, combos, _present("小明", "小红"), _one("ice"), blacklisted) == ("guest", "cyber")


@pytest.mark.parametrize("blacklisted", [False, True])
def test_the_top_guest_with_a_scene_decides_with_a_blacklist_player_or_not(blacklisted):
    assert lobby_scene(LIKES, [], _present("小明", "阿星"), _one("ice"), blacklisted) == ("guest", "angel")
    # 小红 is above 小明 but on 随机: 小明's ticked one wins.
    assert lobby_scene(LIKES, [], _present("小明", "小红"), _one("ice"), blacklisted) == ("guest", "cyber")
    assert lobby_scene(LIKES, [], _present("小红"), _one("ice"), blacklisted) == ("guest", "random")


def test_guests_all_on_no_scene_and_no_blacklist_player_fall_through_to_me():
    here = _present("不要场景的人")
    assert lobby_scene(LIKES, [], here, _one("ice"), False) == ("me", "ice")
    assert lobby_scene(LIKES, [], here, ANY_SCENE, False) == ("me", "random")
    assert lobby_scene(LIKES, [], here, OFF, False) == ("", "off")
    # A 组合 on 不放 as well.
    likes = [Entry("甲", scenes=OFF), Entry("乙", scenes=OFF)]
    assert lobby_scene(likes, [Combo(("甲", "乙"), OFF)], likes, Scenes(("ice", "stars")), False) == ("me", ("ice", "stars"))


@pytest.mark.parametrize("present", [[], ["不要场景的人"]])
def test_a_blacklist_player_with_no_scene_asked_for_gets_none(present):
    assert lobby_scene(LIKES, COMBOS, _present(*present), _one("ice"), True) == ("", "off")
    assert lobby_scene(LIKES, COMBOS, _present(*present), ANY_SCENE, True) == ("", "off")


def test_nobody_listed_gets_mine_or_none():
    assert lobby_scene(LIKES, COMBOS, [], _one("ice"), False) == ("me", "ice")
    assert lobby_scene(LIKES, COMBOS, [], ANY_SCENE, False) == ("me", "random")
    # 随机 keeps its ticks but plays any.
    assert lobby_scene(LIKES, COMBOS, [], Scenes(("ice",), True), False) == ("me", "random")
    assert lobby_scene(LIKES, COMBOS, [], Scenes(("ice", "stars")), False) == ("me", ("ice", "stars"))
    assert lobby_scene(LIKES, COMBOS, [], OFF, False) == ("", "off")


def test_mine_ticked_that_this_version_does_not_have_is_as_if_on_random():
    def known(key: str) -> bool:
        return key != "gone"

    assert lobby_scene([], [], [], Scenes(("gone", "ice")), False, known) == ("me", "ice")
    assert lobby_scene([], [], [], _one("gone"), False, known) == ("me", "random")


# The window ---------------------------------------------------------------------------------------

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect.pipeline import CheckResult, Hit, NameSlot  # noqa: E402


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect.ui import MainWindow
    from blacklist_detect.ui_music import ThemeMusic

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    made = MainWindow()
    # The marks over the game: 完整模式 and 自动检查, agreed to once.
    made.store.consented = ["full", "auto"]
    made._on_display_mode("full")
    made._on_auto_mode("auto")
    made._watch_timer.stop()
    made.store.disclaimer_accepted = True
    tunes: list = []
    made.music = ThemeMusic(play=tunes.append, sounds=made.store.scene_sound)
    made.tunes = tunes
    made._live_check = True
    yield made
    made.notice.hide()
    made.love.stop()
    made.alert.stop()
    made.close()


def _lobby(*names: str, bad: str = "", unclear: int = 0) -> CheckResult:
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    seats = [*names, bad] if bad else list(names)
    slots = [
        NameSlot(index, (100 * index, 100, 100 * index + 80, 130), name, name, False, 0.9, False)
        for index, name in enumerate(seats)
    ]
    slots += [
        NameSlot(index, (100 * index, 100, 100 * index + 80, 130), "", "", False, 0.1, True)
        for index in range(len(seats), len(seats) + unclear)
    ]
    hits = [Hit(len(names), bad, bad, "", False, "", ())] if bad else []
    return CheckResult(True, "", names=slots, hits=hits, button_box=button)


def _check(window, *names: str, bad: str = "") -> None:  # noqa: ANN001
    window.music._last_lobby = frozenset()
    window.music._last_mine_at = float("-inf")
    _again(window, *names, bad=bad)


def _again(window, *names: str, bad: str = "", unclear: int = 0) -> None:  # noqa: ANN001
    """The lobby checked as a new check would: the music remembers the last one."""
    result = _lobby(*names, bad=bad, unclear=unclear)
    window._hide_panel_after_title()
    window._love_played = False
    window._on_lobby_placed(result.button_box)
    window._show_panel(result)


def _sounds(window) -> list[str]:  # noqa: ANN001
    return [Path(tune).name for tune in window.tunes if tune]


def test_a_lobby_with_nobody_listed_plays_mine_with_the_scene_marks_and_no_card(window):
    from blacklist_detect.ui_overlay import love_look

    window.store.set_me(_one("ice"))
    _check(window, "路人甲", "路人乙")
    assert window._lobby_who == "me" and window.love.playing() and window.love.scene == "ice"
    assert window.panel.mode == "liked" and window.clear_mark.isVisible() and window.clear_mark.heart
    assert not window.like_card.isVisible() and not window.hit_card.isVisible() and not window.alert.isVisible()
    assert all(mark.look is love_look("ice") for mark in (window.panel, window.clear_mark))
    assert _sounds(window) == ["theme-ice.wav"]
    # 直播画面 gets the ring and the badge, as for the 场景 hotkey.
    assert window.panel in window.stream._marks() and window.clear_mark in window.stream._marks()
    # The same players checked again within the minute: no second time.
    assert window.music._last_mine == frozenset({"路人甲", "路人乙"})
    _again(window, "路人甲", "路人乙")
    assert window.love.playing() and _sounds(window) == ["theme-ice.wav"]
    assert "我 ice" in window.settings_line()


def test_guests_all_on_no_scene_fall_through_to_mine_and_keep_their_card(window):
    window.store.add_like("小明", scenes=OFF)
    window.store.set_me(_one("ice"))
    _check(window, "小明", "路人甲")
    assert window._lobby_who == "me" and window.love.scene == "ice" and window.love.playing()
    assert window.panel.mode == "liked" and window.like_card.isVisible()


def test_a_lobby_with_nobody_listed_and_me_on_no_scene_is_as_before(window):
    assert window.store.me.off, "我 starts on 不放"
    _check(window, "路人甲", "路人乙")
    assert window.panel.mode == "clear" and window.clear_mark.isVisible() and not window.clear_mark.heart
    assert not window.love.playing() and not window.like_card.isVisible() and not _sounds(window)
    assert "我 不放" in window.settings_line()


def test_a_blacklist_player_with_a_guest_plays_the_guests_scene_over_the_glow(window):
    from blacklist_detect.ui_overlay import love_look

    window.store.add_like("小明", scenes=_one("ice"))
    window.store.set_me(_one("stars"))
    _check(window, "小明", bad="坏人")
    assert window._lobby_who == "guest" and window.love.playing() and window.love.scene == "ice"
    assert window.panel.mode == "both" and window.panel.look is love_look("ice")
    assert window.hit_card.isVisible() and window.like_card.isVisible() and window.alert.isVisible()
    assert not window.clear_mark.isVisible()
    cover = window.panel.cover_geometry()
    assert window.like_card.x() + window.like_card.width() <= cover.x() and window.hit_card.x() >= cover.x() + cover.width()
    # Parted round the cover and both cards.
    gap = window.love._gap.translated(window.love.x(), window.love.y())
    for mark in (window.panel.cover_geometry(), window.hit_card.geometry(), window.like_card.geometry()):
        assert gap.contains(mark.toRectF())
    assert _sounds(window) == ["theme-ice.wav"]
    # 直播画面 copies the marks, the glow and the 场景 over it, and never the 黑名单 card.
    window._set_stream_mode(True)
    _check(window, "小明", bad="坏人")
    assert window.stream._borders() == [window.love] and window.stream._glow() is window.alert
    assert window.hit_card not in window.stream._marks() and window.like_card in window.stream._marks()
    window._hide_panel_after_title()
    window._set_stream_mode(False)


def test_a_blacklist_player_alone_is_as_before_whatever_mine_is(window):
    window.store.set_me(_one("ice"))
    _check(window, "路人甲", bad="坏人")
    assert window._lobby_who == "" and window.panel.mode == "hit" and window.hit_card.isVisible() and window.alert.isVisible()
    assert not window.love.playing() and not window.like_card.isVisible() and not _sounds(window)
    # A 嘉宾 on 不放 there too: the red and rose ring, their card, and still no 场景.
    window.store.add_like("小明", scenes=OFF)
    _check(window, "小明", bad="坏人")
    assert window.panel.mode == "both" and window.like_card.isVisible()
    assert not window.love.playing() and not _sounds(window)


def test_in_safe_mode_the_corner_message_and_the_scenes_music_even_with_a_blacklist_player(window):
    window._on_display_mode("safe")
    window.store.add_like("小明", scenes=_one("ice"))
    _check(window, "小明", bad="坏人")
    assert window.notice.kind == "hit" and window.panel.isHidden() and not window.love.playing()
    assert _sounds(window) == ["theme-ice.wav"]
    # 我's too, with nobody listed.
    window.store.set_me(_one("stars"))
    _check(window, "路人甲")
    assert window.notice.kind == "clear" and _sounds(window)[-1] == "theme-stars.wav"


def test_mine_hears_a_lobby_once_a_minute_however_its_names_read():
    from blacklist_detect.ui_music import SAME_LOBBY_S, ThemeMusic

    clock = [0.0]
    played: list = []
    music = ThemeMusic(play=played.append, clock=lambda: clock[0])
    assert music.mine(["甲", "乙", "丙", "丁"], "ice")
    # Checked again, a player joined, one misread, one unclear, none read at all: the same lobby.
    for names in (["甲", "乙", "丙", "丁"], ["甲", "乙", "丙", "丁", "戊"], ["甲", "乙", "丙", "己"], ["甲", "乙", "丙"], []):
        assert not music.mine(names, "ice"), names
    assert not music.mine(["甲", "乙"], "ice")
    # Mostly other players: a new lobby.
    assert music.mine(["子", "丑", "寅", "卯"], "ice")
    clock[0] += SAME_LOBBY_S
    assert music.mine(["子", "丑", "寅", "卯"], "ice")
    assert len([tune for tune in played if tune]) == 3


def test_a_lobby_greeted_by_mine_plays_its_music_once_as_players_join_or_read_differently(window):
    clock = [0.0]
    window.music._clock = lambda: clock[0]
    window.store.set_me(_one("ice"))
    _check(window, "路人甲", "路人乙", "路人丙", "路人丁")
    assert _sounds(window) == ["theme-ice.wav"]
    _again(window, "路人甲", "路人乙", "路人丙", "路人丁")
    _again(window, "路人甲", "路人乙", "路人丙", "路人丁", "路人戊")
    _again(window, "路人甲", "路人乙", "路人丙", "路人己")
    _again(window, "路人甲", "路人乙", "路人丙", unclear=1)
    assert window.love.playing() and _sounds(window) == ["theme-ice.wav"]
    _again(window, "小子", "小丑", "小寅", "小卯")
    assert _sounds(window) == ["theme-ice.wav"] * 2
    clock[0] += 61
    _again(window, "小子", "小丑", "小寅", "小卯")
    assert _sounds(window) == ["theme-ice.wav"] * 3


def test_a_blacklist_player_read_as_a_guest_too_is_only_the_warning(window):
    window.store.add_like("坏人", scenes=_one("ice"))
    window.store.set_me(_one("stars"))
    _check(window, "路人", bad="坏人")
    assert window._lobby_who == "" and window.panel.mode == "hit" and window.hit_card.isVisible()
    assert not window.love.playing() and not window.like_card.isVisible() and not _sounds(window)
    # Another 嘉宾 there decides as usual, and a 组合 with the 黑名单 player is not in the lobby.
    window.store.add_like("小明", scenes=_one("angel"))
    window.store.set_combos([Combo(("小明", "坏人"), _one("lace"))])
    _check(window, "小明", bad="坏人")
    assert window._lobby_who == "guest" and window.love.scene == "angel" and window.love.playing()
    assert [like.name for like in window._likes_in(_lobby("小明", bad="坏人"))] == ["小明"]
    assert window.panel.mode == "both" and window.like_card.isVisible() and _sounds(window) == ["wedding-bells.wav"]


def test_a_scene_beside_a_blacklist_player_never_plays_over_their_name(window):
    from dataclasses import replace

    window.store.add_like("小明", scenes=_one("claw"))
    _check(window, "小明", "路人", bad="坏人")
    assert window.love.playing() and window.love.scene == "claw"
    every = window._seats_of(replace(_lobby("小明", "路人", bad="坏人"), hits=[]))
    assert len(every) == 3 and window._lobby_seats == every[:2] and len(window.love._seats) == 2
    _check(window, "小明", "路人", "路人乙")
    assert window._lobby_seats == every and len(window.love._seats) == 3


def _recheck(window, *names: str, unclear: int = 0) -> None:  # noqa: ANN001
    """The hotkey pressed again over the lobby still marked: _start, then the new reading."""
    window.worker.request = lambda fn, kind="check": True
    assert window._start(lambda: None, live=True)
    window._show_panel(_lobby(*names, unclear=unclear))


def test_checked_again_with_a_guest_read_now_the_guests_scene_greets_it_not_mine(window):
    from blacklist_detect.ui_overlay import love_look

    window.store.set_me(_one("ice"))
    window.store.add_like("小明", scenes=_one("cyber"))
    _check(window, "路人甲", "路人乙")
    assert window._lobby_who == "me" and window.love.scene == "ice" and _sounds(window) == ["theme-ice.wav"]
    _recheck(window, "小明", "路人乙")
    assert window._lobby_who == "guest" and window.love.playing() and window.love.scene == "cyber"
    assert all(mark.look is love_look("cyber") for mark in (window.panel, window.clear_mark, window.like_card))
    assert _sounds(window) == ["theme-ice.wav", "theme-cyber.wav"]
    # 小明 unclear the time after: 我's again, and never the 嘉宾's tune as 我's.
    _recheck(window, "路人乙", unclear=1)
    assert window._lobby_who == "me" and window.love.scene == "ice" and window.panel.look is love_look("ice")
    assert _sounds(window) == ["theme-ice.wav", "theme-cyber.wav"]


def test_checked_again_with_the_whole_combination_read_now_its_scene_greets_it(window):
    from blacklist_detect.ui_music import TUNES

    window.store.add_like("小红")
    window.store.add_like("小明", scenes=_one("cyber"))
    window.store.set_combos([Combo(("小明", "小红"), _one("lace"))])
    _check(window, "小明", "路人")
    assert window._lobby_who == "guest" and window.love.scene == "cyber"
    _recheck(window, "小明", "小红")
    assert window._lobby_who == "combo" and window.love.playing() and window.love.scene == "lace"
    assert _sounds(window) == ["theme-cyber.wav", TUNES["lace"].name]


def test_a_press_while_a_check_or_a_glance_runs_leaves_the_result_shown(window):
    window.store.add_like("小明", scenes=_one("cyber"))
    _check(window, "小明", bad="坏人")
    marks = (window.panel, window.hit_card, window.like_card, window.alert)
    assert all(mark.isVisible() for mark in marks) and window.love.playing() and window.panel.mode == "both"
    window.worker.running_job = True
    try:
        assert not window._start(lambda: None, live=True)
    finally:
        window.worker.running_job = False
    assert all(mark.isVisible() for mark in marks) and window.love.playing() and window.panel.mode == "both"


def test_the_same_guest_checked_again_keeps_the_one_scene_it_had(window):
    from blacklist_detect.ui_overlay import love_look

    window.store.add_like("小明", scenes=ANY_SCENE)
    _check(window, "小明", "路人")
    played = window.love.scene
    assert window.love.playing() and len(_sounds(window)) <= 1
    heard = list(window.tunes)
    for _ in range(3):
        _recheck(window, "小明", "路人")
        assert not window.love.playing() and window.love.pick() == played and window.panel.look is love_look(played)
    assert window.tunes == heard
