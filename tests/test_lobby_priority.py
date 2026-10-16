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


def _lobby(*names: str, bad: str = "") -> CheckResult:
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    seats = [*names, bad] if bad else list(names)
    slots = [
        NameSlot(index, (100 * index, 100, 100 * index + 80, 130), name, name, False, 0.9, False)
        for index, name in enumerate(seats)
    ]
    hits = [Hit(len(names), bad, bad, "", False, "", ())] if bad else []
    return CheckResult(True, "", names=slots, hits=hits, button_box=button)


def _check(window, *names: str, bad: str = "") -> None:  # noqa: ANN001
    result = _lobby(*names, bad=bad)
    window._hide_panel_after_title()
    window._love_played = False
    window.music._last_lobby = frozenset()
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
    assert window.music._last_lobby == frozenset({"我", "路人甲", "路人乙"})
    window._hide_panel_after_title()
    window._love_played = False
    result = _lobby("路人甲", "路人乙")
    window._on_lobby_placed(result.button_box)
    window._show_panel(result)
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
