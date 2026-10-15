"""嘉宾 themes: each 嘉宾's own 特效, 组合 of 嘉宾, and which one a lobby gets."""

from blacklist_detect.guests import lobby_choice, members
from blacklist_detect.model import Combo, Entry
from blacklist_detect.storage import Store

# The list as saved: the last is the top.
LIKES = [Entry("小明", theme="cyber"), Entry("小红"), Entry("阿星", theme="angel"), Entry("新来的")]


def _present(*names: str) -> list[Entry]:
    return [like for like in LIKES if like.name in names]


def test_the_top_guest_with_a_theme_of_their_own_decides():
    # 阿星 is above 小明 on the list: 阿星's 天使.
    assert lobby_choice(LIKES, [], _present("小明", "阿星"), "classic") == "angel"
    # 新来的 is on top but picked none: the next one down with a theme decides.
    assert lobby_choice(LIKES, [], _present("新来的", "小明"), "classic") == "cyber"


def test_with_no_pick_a_lobby_gets_classic():
    # Nobody here picked a 特效 of their own, and no 组合 of theirs is all there: 经典, the default.
    assert lobby_choice(LIKES, [], _present("小红", "新来的"), "classic") == "classic"
    assert lobby_choice(LIKES, [Combo(("小明", "小红"), "equation")], _present("小红"), "classic") == "classic"
    assert lobby_choice(LIKES, [], [], "classic") == "classic"


def test_a_combination_wins_when_all_of_it_is_there_the_biggest_first():
    combos = [Combo(("小明", "小红"), "equation"), Combo(("小明", "小红", "阿星"), "fluffy"), Combo(("阿星", "新来的"), "neon")]
    # All of 小明 + 小红 there, with someone else too: theirs.
    assert lobby_choice(LIKES, combos, _present("小明", "小红", "新来的"), "classic") == "equation"
    # Two combinations fit; the bigger one wins.
    assert lobby_choice(LIKES, combos, _present("小明", "小红", "阿星"), "classic") == "fluffy"
    # Only part of a combination: the list decides.
    assert lobby_choice(LIKES, combos, _present("小明", "阿星"), "classic") == "angel"


def test_a_theme_this_version_does_not_play_is_passed_over():
    known = {"classic", "cyber"}.__contains__
    assert lobby_choice(LIKES, [], _present("小明", "阿星"), "classic", known) == "cyber", "阿星's angel is skipped"
    assert lobby_choice(LIKES, [Combo(("小明", "小红"), "gone")], _present("小明", "小红"), "classic", known) == "cyber"


def test_themes_combinations_and_the_order_are_saved(tmp_path):
    store = Store(tmp_path)
    store.add_like("小明", theme="cyber")
    store.add_like("小红")
    store.add_like("阿星", "星星", theme="angel")
    store.set_combos([Combo(("小明", "小红"), "equation")])
    again = Store(tmp_path)
    assert [(like.name, like.theme) for like in again.likes] == [("小明", "cyber"), ("小红", ""), ("阿星", "angel")]
    assert again.combos == [Combo(("小明", "小红"), "equation")]
    # 置顶 and dragging change the order, which decides between 嘉宾.
    assert again.move_like(0, 2)
    assert [like.name for like in Store(tmp_path).likes] == ["小红", "阿星", "小明"]
    # A new name for a 嘉宾 in a combination: the combination follows it.
    again.update_like(2, "小明明", "", "", "cyber")
    assert Store(tmp_path).combos == [Combo(("小明明", "小红"), "equation")]
    # Taken off the list, a 嘉宾 stays in their combination, which waits for them (撤销 brings them back).
    before = again.snapshot_likes()
    again.remove_like(0)
    assert members(again.combos[0], again.likes) == [("小明明", True), ("小红", False)]
    again.restore_likes(before)
    assert [like.theme for like in Store(tmp_path).likes] == ["", "angel", "cyber"]
    again.reset()
    assert Store(tmp_path).combos == []


def test_a_combination_of_fewer_than_two_or_with_no_theme_is_not_loaded(tmp_path):
    (tmp_path / "likes.json").write_text(
        '{"likes": [{"name": "小明"}], "combos": [{"names": ["小明"], "theme": "cyber"}, {"names": ["小明", "小红"], "theme": ""}]}',
        encoding="utf-8",
    )
    assert Store(tmp_path).combos == []
