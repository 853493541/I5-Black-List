"""Match rules: exact, prefix, short prefix, and lobby chrome."""

from blacklist_detect.match import NameLabel, clean_stored_name, match_label, split_ellipsis
from blacklist_detect.model import Entry


def _label(raw: str, truncated: bool | None = None) -> NameLabel:
    visible, found = split_ellipsis(raw)
    if truncated is None:
        truncated = found
    return NameLabel(raw=raw, visible=visible, truncated=truncated)


def test_exact_chinese_name():
    hits = match_label(_label("罪玥吉尔曼"), [Entry("罪玥吉尔曼", reason="代打")])
    assert len(hits) == 1
    assert hits[0].kind == "exact"
    assert hits[0].entry.reason == "代打"


def test_first_four_characters_match_a_longer_name():
    hits = match_label(_label("罪玥吉尔曼"), [Entry("罪玥吉尔曼猫")])
    assert len(hits) == 1
    assert hits[0].kind == "prefix"


def test_latin_case_and_fullwidth_are_the_same_name():
    hits = match_label(_label("EluElu"), [Entry("eluelu")])
    assert len(hits) == 1
    hits = match_label(_label("ｇｉｆｄｓｄ"), [Entry("gifdsd")])
    assert len(hits) == 1
    assert clean_stored_name("ｇｉｆｄｓｄ") == "gifdsd"


def test_a_trailing_dot_is_the_cutoff_mark():
    two = _label("无害虎皮..")
    one = _label("小猫爆锤.")
    assert two.truncated and two.visible == "无害虎皮"
    assert one.truncated and one.visible == "小猫爆锤"
    assert len(match_label(two, [Entry("无害虎皮猫")])) == 1


def test_game_ellipsis_stays_visible_and_matches_the_full_name():
    from blacklist_detect.match import with_game_ellipsis

    shown = with_game_ellipsis("你好我是", True)
    assert shown == "你好我是..."
    hits = match_label(
        NameLabel(raw="你好我是...", visible=shown, truncated=True),
        [Entry("你好我是油锅")],
    )
    assert len(hits) == 1
    assert hits[0].entry.name == "你好我是油锅"
    assert hits[0].kind == "prefix"


def test_prefix_of_four_characters():
    hits = match_label(_label("无害虎皮…"), [Entry("无害虎皮猫")])
    assert len(hits) == 1
    assert hits[0].kind == "prefix"
    assert hits[0].truncated


def test_prefix_lists_every_shared_start():
    entries = [Entry("无害虎皮猫"), Entry("无害虎皮犬")]
    hits = match_label(_label("无害虎皮…"), entries)
    assert [hit.entry.name for hit in hits] == ["无害虎皮猫", "无害虎皮犬"]


def test_prefix_does_not_match_the_middle():
    hits = match_label(_label("贝尔又…"), [Entry("坎贝尔又来了")])
    assert hits == []


def test_too_short_prefix_is_ignored():
    label = _label("无害…")
    assert len(label.visible) < 4
    assert match_label(label, [Entry("无害虎皮猫")]) == []


def test_a_backtick_in_the_middle_is_ignored():
    hits = match_label(_label("无`害虎皮"), [Entry("无害虎皮猫")])
    assert len(hits) == 1
    assert hits[0].kind == "prefix"


def test_seat_numbers():
    from blacklist_detect.match import format_hit, seat_number

    assert seat_number(0) == 1
    assert seat_number(6) == 7
    assert format_hit(0, "无害虎皮", True, "无害虎皮猫", "") == "画面是「无害虎皮」，黑名单里有「无害虎皮猫」"
    assert "号" not in format_hit(6, "谁想救人", False, "谁想救人", "")


def test_saved_visible_text_matches_a_cutoff_exactly():
    hits = match_label(_label("无害虎皮…"), [Entry("无害虎皮")])
    assert len(hits) == 1
    assert hits[0].kind == "exact"


def test_ready_line_is_not_a_name():
    entries = [Entry("准备就绪"), Entry("准备就绪：11/12"), Entry("罪玥吉尔曼")]
    for raw in ("准备就绪", "准备就绪：11/12", "准备就绪:8/12", "准备案件还原"):
        assert match_label(_label(raw), entries) == []
    assert match_label(_label("罪玥吉尔曼"), entries)[0].entry.name == "罪玥吉尔曼"


def test_unclear_read_does_not_match():
    label = NameLabel(raw="罪玥吉尔曼", visible="罪玥吉尔曼", truncated=False, unclear=True)
    assert match_label(label, [Entry("罪玥吉尔曼")]) == []
