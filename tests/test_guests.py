"""嘉宾 themes: each 嘉宾's own 场景, 组合 of 嘉宾, and which one a lobby gets."""

from blacklist_detect.guests import lobby_choice, members
from blacklist_detect.model import ANY_SCENE, Combo, Entry, Scenes
from blacklist_detect.storage import Store


def _one(key: str) -> Scenes:
    return Scenes((key,))


# The list as saved: the last is the top.
LIKES = [Entry("小明", scenes=_one("cyber")), Entry("小红"), Entry("阿星", scenes=_one("angel")), Entry("新来的")]


def _present(*names: str) -> list[Entry]:
    return [like for like in LIKES if like.name in names]


def test_the_top_guest_with_scenes_of_their_own_decides():
    # 阿星 is above 小明 on the list: 阿星's 天使.
    assert lobby_choice(LIKES, [], _present("小明", "阿星"), "classic") == "angel"
    # 新来的 is on top but on 随机: the next one down with one ticked decides.
    assert lobby_choice(LIKES, [], _present("新来的", "小明"), "classic") == "cyber"


def test_with_everyone_on_random_a_lobby_gets_any_scene():
    # Everyone here on 随机, and no 组合 of theirs is all there: any scene.
    assert lobby_choice(LIKES, [], _present("小红", "新来的"), "classic") == "random"
    assert lobby_choice(LIKES, [Combo(("小明", "小红"), _one("equation"))], _present("小红"), "classic") == "random"
    # No 嘉宾 at all: the default.
    assert lobby_choice(LIKES, [], [], "classic") == "classic"


def test_a_combination_wins_when_all_of_it_is_there_the_biggest_first():
    combos = [
        Combo(("小明", "小红"), _one("equation")),
        Combo(("小明", "小红", "阿星"), _one("fluffy")),
        Combo(("阿星", "新来的"), _one("neon")),
    ]
    # All of 小明 + 小红 there, with someone else too: theirs.
    assert lobby_choice(LIKES, combos, _present("小明", "小红", "新来的"), "classic") == "equation"
    # Two combinations fit; the bigger one wins.
    assert lobby_choice(LIKES, combos, _present("小明", "小红", "阿星"), "classic") == "fluffy"
    # Only part of a combination: the list decides.
    assert lobby_choice(LIKES, combos, _present("小明", "阿星"), "classic") == "angel"


def test_a_scene_this_version_does_not_play_is_passed_over():
    known = {"classic", "cyber"}.__contains__
    assert lobby_choice(LIKES, [], _present("小明", "阿星"), "classic", known) == "cyber", "阿星's angel is skipped"
    # A 组合 left with none of its scenes still wins, as one on 随机: any scene.
    assert lobby_choice(LIKES, [Combo(("小明", "小红"), _one("gone"))], _present("小明", "小红"), "classic", known) == "random"


def test_random_no_scene_and_ticked_are_three_choices():
    random_with_ticks = Scenes(("cyber",), random=True)
    likes = [Entry("小明", scenes=_one("cyber")), Entry("小红", scenes=random_with_ticks), Entry("阿星", scenes=Scenes())]
    present = likes
    assert Scenes().off and not ANY_SCENE.off and not random_with_ticks.off and not _one("cyber").off
    # 阿星, on top, is on 不放: the next in line decides. 小红 is on 随机, its tick kept but not used: a lower 嘉宾
    # with one ticked beats it.
    assert lobby_choice(likes, [], present, "classic") == "cyber"
    assert lobby_choice(likes, [], present[1:], "classic") == "random"
    # Every one there on 不放: none.
    assert lobby_choice(likes, [], present[2:], "classic") == "off"
    # A 组合 on 不放 is skipped; on 随机 it wins with any scene, whatever it has ticked.
    combo = ("小明", "小红")
    assert lobby_choice(likes, [Combo(combo, Scenes())], present[:2], "classic") == "cyber"
    assert lobby_choice(likes, [Combo(combo, random_with_ticks)], present[:2], "classic") == "random"
    assert lobby_choice(likes, [Combo(combo, Scenes(("angel", "ice")))], present[:2], "classic") == ("angel", "ice")


def test_random_with_ticks_this_version_lacks_is_still_random():
    known = {"classic", "cyber"}.__contains__
    likes = [Entry("小明", scenes=_one("cyber")), Entry("小红", scenes=Scenes(("gone",), random=True))]
    assert lobby_choice(likes, [], likes[1:], "classic", known) == "random"
    assert lobby_choice(likes, [], likes, "classic", known) == "cyber"
    # Ticks only, none of them played by this version: as if on 随机.
    assert lobby_choice([Entry("小红", scenes=_one("gone"))], [], [Entry("小红")], "classic", known) == "random"


def test_scenes_combinations_and_the_order_are_saved(tmp_path):
    store = Store(tmp_path)
    store.add_like("小明", scenes=_one("cyber"))
    store.add_like("小红")
    store.add_like("阿星", "星星", scenes=_one("angel"))
    store.set_combos([Combo(("小明", "小红"), _one("equation"))])
    again = Store(tmp_path)
    assert [(like.name, like.scenes) for like in again.likes] == [("小明", _one("cyber")), ("小红", ANY_SCENE), ("阿星", _one("angel"))]
    assert again.combos == [Combo(("小明", "小红"), _one("equation"))]
    # 置顶 and dragging change the order, which decides between 嘉宾.
    assert again.move_like(0, 2)
    assert [like.name for like in Store(tmp_path).likes] == ["小红", "阿星", "小明"]
    # A new name for a 嘉宾 in a combination: the combination follows it.
    again.update_like(2, "小明明", "", "", _one("cyber"))
    assert Store(tmp_path).combos == [Combo(("小明明", "小红"), _one("equation"))]
    # Taken off the list, a 嘉宾 stays in their combination, which waits for them (撤销 brings them back).
    before = again.snapshot_likes()
    again.remove_like(0)
    assert members(again.combos[0], again.likes) == [("小明明", True), ("小红", False)]
    again.restore_likes(before)
    assert [like.scenes for like in Store(tmp_path).likes] == [ANY_SCENE, _one("angel"), _one("cyber")]
    again.reset()
    assert Store(tmp_path).combos == []


def test_a_combination_of_fewer_than_two_is_not_loaded(tmp_path):
    (tmp_path / "likes.json").write_text(
        '{"likes": [{"name": "小明"}], "combos": [{"names": ["小明"], "theme": "cyber"}, {"names": ["小明", "小红"], "theme": ""}]}',
        encoding="utf-8",
    )
    # One with no theme of its own (none saved so before) is on 随机 now.
    assert Store(tmp_path).combos == [Combo(("小明", "小红"), ANY_SCENE)]
