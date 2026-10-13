"""批量导入: how a paste is read, and what importing it does to the list."""

from blacklist_detect.importing import MERGE, NEW, ODD, SAME, plan_import, read_paste
from blacklist_detect.model import Entry
from blacklist_detect.storage import Store

# As a friend sent it: a title, 名字（原因） per line, two names sharing one 原因,
# and a 原因 that runs onto the next line.
FRIEND = """这游戏有这么多神人吗
挖野菜养你吖（纯粹的傻逼）
名辅导可乐（弱智）
好知知这就来帮（好人帮狼炸房）
西西zo（挂机占麦）
争胜学姐（好人炸房）
小小丑不会输，少主薇（狼能赢的送双排顾问）
翻箱震慑是北城（讲了行为狼、轨迹狼、身份撞了，还给狼弃
票，弱智来着）
我们应该谈谈（侦探团胡编乱造视野发言）
侦探团里有傻福（挂机划水）
馒头不要钱（玩密探乱贴人双倒）
何事秋风悲情雪（发言就一行字差的要死然后被踩就骂人）
腐草为萤zzz（狼刀红名，炸房）
木木又成秒倒鱼（点了中下坑拉铃顺出的局说抢不过所以做任务去了）
岁岁安谏（点了中下坑的局猎人做任务发呆）
车窗外面徘徊h（狼刀红名，炸房）
无形不累物（发言不好行为不好，被裸点了还破防说人顺直）
誘之（轨迹差表水差被踩就情绪贴脸）"""


def _people(text: str) -> dict[str, tuple[tuple[str, ...], str]]:
    return {name: (tags, reason) for name, tags, reason in read_paste(text)}


def test_a_friends_list_reads_every_person():
    people = _people(FRIEND)
    assert len(people) == 19
    assert people["挖野菜养你吖"] == ((), "纯粹的傻逼")
    assert people["好知知这就来帮"] == (("炸房",), "好人帮狼炸房")
    assert people["西西zo"] == (("挂机",), "挂机占麦")
    assert people["誘之"] == (("贴脸",), "轨迹差表水差被踩就情绪贴脸")
    # Two names in front of one 原因 share it.
    assert people["小小丑不会输"] == people["少主薇"] == ((), "狼能赢的送双排顾问")
    # A 原因 broken onto the next line is still one 原因.
    assert people["翻箱震慑是北城"] == ((), "讲了行为狼、轨迹狼、身份撞了，还给狼弃票，弱智来着")
    # The title is kept, so nothing is lost without a word, but it is not checked.
    rows = {row.name: row for row in plan_import(FRIEND, [])}
    assert rows["这游戏有这么多神人吗"].status == ODD and rows["这游戏有这么多神人吗"].checked is False
    assert sum(row.checked for row in rows.values()) == 18


def test_half_width_brackets_and_marks_before_them_read_the_same():
    same = _people(FRIEND.replace("（", "(").replace("）", ")"))
    assert same == _people(FRIEND)
    assert _people("挖野菜养你吖 （纯粹的傻逼）\n名辅导可乐：（弱智）\n小明【炸房】") == {
        "挖野菜养你吖": ((), "纯粹的傻逼"),
        "名辅导可乐": ((), "弱智"),
        "小明": (("炸房",), ""),
    }


def test_no_line_is_dropped():
    # A name without a 原因 between the others.
    assert list(_people("小明（开局就炸房）\n路过的小红\n小刚")) == ["小明", "路过的小红", "小刚"]
    # A bracket never closed keeps its 原因, and the lines after it are their own.
    assert _people("名辅导可乐（弱智\n路人甲\n小刚（挂机）") == {
        "名辅导可乐": ((), "弱智"),
        "路人甲": ((), ""),
        "小刚": (("挂机",), ""),
    }
    assert _people("挖野菜养你吖（纯粹的傻逼）\n名辅导可乐（弱智") == {
        "挖野菜养你吖": ((), "纯粹的傻逼"),
        "名辅导可乐": ((), "弱智"),
    }


def test_list_numbers_and_bullets_are_not_names():
    assert list(_people("1. 小明（骂人）\n2、小红\n3) 小刚 挂机\n④ 小强\n- 小李\n• 小王")) == [
        "小明",
        "小红",
        "小刚",
        "小强",
        "小李",
        "小王",
    ]
    # A name may start with digits.
    assert list(_people("1314小明\n520")) == ["1314小明", "520"]


def test_lines_without_brackets():
    assert _people("小明 小红 小刚") == {"小明": ((), ""), "小红": ((), ""), "小刚": ((), "")}
    # A 标签, or a word holding one, is about the name in front of it.
    assert _people("小明 炸房\n小红 开局就挂机") == {"小明": (("炸房",), ""), "小红": (("挂机",), "开局就挂机")}
    assert _people("小明：开局就炸房\n小红-挂机") == {"小明": (("炸房",), "开局就炸房"), "小红": (("挂机",), "")}
    assert _people("名字一，炸房，贴脸，他做了坏事\n甲，其他:开黑") == {
        "名字一": (("炸房", "贴脸"), "他做了坏事"),
        "甲": ((), "开黑"),
    }
    # A 原因 with a comma in it stays one 原因.
    assert _people("小明，炸房，开局就炸，还骂人") == {"小明": (("炸房",), "开局就炸，还骂人")}


def test_a_copied_list_keeps_its_own_tags():
    text = "#黑名单检测 名单 2人\n小明，炸房，原因：开局就炸\n小红，演员"
    assert _people(text) == {"小明": (("炸房",), "开局就炸"), "小红": (("演员",), "")}


def test_a_name_twice_in_one_paste_is_one_person():
    rows = plan_import("小明（炸房）\n小明（还骂人）", [])
    assert [(row.name, row.tags, row.reason) for row in rows] == [("小明", ("炸房",), "还骂人")]


def test_names_already_on_the_list_merge():
    entries = [Entry("挖野菜养你吖", "纯粹的傻逼"), Entry("小猫爆锤大王", "", ("挂机",)), Entry("名辅导可乐")]
    rows = {row.name: row for row in plan_import("挖野菜养你吖（纯粹的傻逼）\n名辅导可乐（弱智）\n小猫爆锤（炸房）\n挖野菜（另一个人）\n新来的（挂机）", entries)}
    # Nothing new: shown, but left unchecked.
    assert (rows["挖野菜养你吖"].status, rows["挖野菜养你吖"].checked) == (SAME, False)
    assert (rows["名辅导可乐"].status, rows["名辅导可乐"].target) == (MERGE, 2)
    # The game cuts names short: four characters or more that start a listed name are that name.
    assert (rows["小猫爆锤"].status, rows["小猫爆锤"].target) == (MERGE, 1)
    # Three are too few to say so.
    assert rows["挖野菜"].status == NEW
    assert rows["新来的"].status == NEW and rows["新来的"].checked


def test_longer_than_a_name_or_only_digits_is_unchecked():
    rows = {row.name: row for row in plan_import("一二三四五六七八\n一二三四五六七八九\n2026", [])}
    assert rows["一二三四五六七八"].status == NEW
    assert rows["一二三四五六七八九"].status == ODD and not rows["一二三四五六七八九"].checked
    assert rows["2026"].status == ODD


def test_a_copied_chat_keeps_its_speakers_unchecked():
    chat = "张三 2026/10/10 21:03:11\n小明 开局就炸房\n李四 21:04\n小红（挂机）"
    rows = {row.name: row for row in plan_import(chat, [])}
    assert list(rows) == ["张三", "小明", "李四", "小红"]
    assert rows["张三"].status == ODD and rows["李四"].status == ODD
    assert rows["小明"].checked and rows["小明"].reason == "开局就炸房"
    assert rows["小红"].checked


def test_importing_adds_new_names_and_merges_the_rest(tmp_path):
    store = Store(tmp_path)
    store.add("名辅导可乐", reason="发言差", tags=("挂机",))
    store.add("小猫爆锤", reason="")
    rows = plan_import("名辅导可乐（弱智，炸房）\n小猫爆锤大王（贴脸）\n新来的（挂机）", store.entries, store.tag_catalog())
    chosen = [(row.name, row.tags, row.reason, row.target if row.status in (MERGE, SAME) else -1) for row in rows if row.checked]
    assert store.import_rows(chosen) == (1, 2)
    saved = {entry.name: (entry.tags, entry.reason) for entry in Store(tmp_path).entries}
    # Its 标签 grow, and the new 原因 joins the old one.
    assert saved["名辅导可乐"] == (("炸房", "挂机"), "发言差；弱智，炸房")
    # The list had the name cut short; it now has it in full.
    # A 原因 that is only a 标签 is the 标签.
    assert saved["小猫爆锤大王"] == (("贴脸",), "")
    assert saved["新来的"] == (("挂机",), "")
    assert len(saved) == 3
    # The same paste again changes nothing.
    again = plan_import("名辅导可乐（弱智，炸房）\n新来的（挂机）", store.entries, store.tag_catalog())
    assert all(row.status == SAME and not row.checked for row in again)


SHARED_REASONS = [
    ("小明", (), "开局送人头，还骂人", -1),
    ("小红", (), "又送人头了", -1),
    ("阿强", ("挂机",), "送人头还挂机", -1),
    ("丁丁", (), "一直演，演员", -1),
    ("戊戊", (), "演员，开局就演", -1),
    ("庚庚", (), "骂人", -1),
]


def test_a_phrase_in_several_reasons_is_offered_as_a_tag():
    from blacklist_detect.importing import suggest_tags

    found = {s.tag: (s.existing, s.rows) for s in suggest_tags(SHARED_REASONS, ("炸房", "挂机"))}
    # 送人头 rather than 人头 or 送人: the longer phrase covers the same records.
    assert found["送人头"] == (False, (0, 1, 2))
    assert found["演员"] == (False, (3, 4))
    assert found["骂人"] == (False, (0, 5))
    # Words that mean nothing alone, and phrases seen once, are not offered.
    assert "开局" not in found and "一直" not in found and "人头" not in found
    assert all(len(rows) >= 2 for _existing, rows in found.values())


def test_a_phrase_that_is_already_a_tag_is_offered_as_that_tag():
    from blacklist_detect.importing import suggest_tags, with_tags

    rows = [("甲", (), "演员一个", -1), ("乙", (), "纯演员", -1), ("丙", ("演员",), "又是演员", -1)]
    found = suggest_tags(rows, ("炸房", "演员"))
    assert [(s.tag, s.existing, s.rows) for s in found] == [("演员", True, (0, 1))]
    # A phrase holding a tag the records already got from it is not offered again.
    assert suggest_tags([("甲", ("炸房",), "又炸房了", -1), ("乙", ("炸房",), "炸房狗", -1)], ("炸房",)) == []
    tagged = with_tags(rows, found)
    assert [r[1] for r in tagged] == [("演员",), ("演员",), ("演员",)]


GAME_REASONS = [
    ("甲", (), "好人帮狼炸房，跳银行", -1),
    ("乙", (), "跳银行骗好人，中立还乱投票", -1),
    ("丙", (), "侦探团里乱投票，一直报假身份", -1),
    ("丁", (), "神秘客顾问，开会挂机", -1),
    ("戊", (), "疯人院里挂机，开会不发言", -1),
    ("己", (), "假跳侦探，银行家被他害死", -1),
    ("庚", (), "假跳侦探带节奏，紧急会议乱说", -1),
]


def test_the_games_own_words_are_never_offered_as_tags():
    """好人, 侦探团, 银行 and the like name what happened in the game, not what the player did."""
    from blacklist_detect.importing import GAME_WORDS, is_game_word, suggest_tags

    found = {s.tag for s in suggest_tags(GAME_REASONS, ("炸房", "挂机"))}
    for word in ("好人", "银行", "银行家", "侦探", "侦探团", "中立", "神秘客", "顾问", "开会", "发言", "身份", "会议"):
        assert word not in found, word
    # What the player did still comes through, also when it holds a game word.
    assert "乱投票" in found and "假跳侦探" in found and "跳银行" in found
    # A piece of a game word is one too: 银行 from 银行家, 侦探 from 侦探团.
    assert is_game_word("银行") and is_game_word("探团") and not is_game_word("送人头")
    assert all(not is_game_word(tag) for tag in ("炸房", "贴脸", "挂机", "场外", "不尊重底牌", "演员", "送人头", "骂人"))
    assert len(GAME_WORDS) == len(set(GAME_WORDS))


def test_a_game_word_the_player_made_a_tag_is_still_offered():
    from blacklist_detect.importing import suggest_tags

    rows = [("甲", (), "又是好人", -1), ("乙", (), "全是好人", -1)]
    assert [s.tag for s in suggest_tags(rows, ("好人",))] == ["好人"]
