"""批量导入: read a pasted list into people, and say what each one does to the list.

Friends send lists as 名字（原因）, one per line, often copied out of a notes app:

    挖野菜养你吖（纯粹的傻逼）
    小小丑不会输，少主薇（狼能赢的送双排顾问）
    翻箱震慑是北城（讲了行为狼、轨迹狼、身份撞了，还给狼弃
    票，弱智来着）

The rules, line by line:

* 名字（原因）. A 原因 may run onto the next lines until its ）. The 标签 written in it
  are picked out; the 原因 itself is kept whole.
* Several names in front of one （原因） share it.
* A line without brackets is names, or one name with 标签 and 原因 after it:
  名字，标签，原因 · 名字：原因 · 名字-原因 · 名字 原因. A word that is a 标签, or holds one,
  starts the part after the name; until then each word is another name.
* A list number or bullet in front is not part of a name: 1. 1、 ① - •.
* A line with a date or a time is a chat's 谁 and 何时, not a player: its names start unchecked.
* A list copied with 复制名单 keeps its own 标签, even ones this list has not seen.
* A row copied from a spreadsheet or a Markdown table is 名字 then 原因, cell by cell; its
  header row (名字 · 原因) and the |---| under it are left out.
* ID：, 游戏名：, 昵称： and the like before a name are not part of it; 原因：, 理由：, 备注：
  mark where the 原因 starts.
* A line that is only 标签, such as 炸房：, heads the names under it, which all get those 标签,
  until the next such line. 【炸房】小明 小红 gives the names on that line the 标签.
* A line ending in ： with nothing after it, such as 以下是黑名单：, is a heading, not a name.
  A title such as 避雷名单（持续更新） is shown but left unchecked.
* Two English words with a space between them are one name: Lucky Star.

Nothing is dropped without a word. A line that does not look like a name, such as a
title, is kept but left unchecked. A name already on the list, or the start of one
(the game cuts names short), is merged into it instead of added twice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from blacklist_detect.match import clean_stored_name, fold
from blacklist_detect.model import Entry
from blacklist_detect.storage import _MAX_TAG, TAGS, is_shared, merge_reason, order_tags, parse_shared, tags_and_reason

# Longer than this is not a player name: the game's names are short.
NAME_MAX = 8
# A name this long or longer that starts another is the same person, cut short by the game.
_SAME_PREFIX = 4
_MAX_NAME = 64
_MAX_NOTE = 200

NEW = "new"
MERGE = "merge"
SAME = "same"
ODD = "odd"
# On the other list (黑名单 when importing into 嘉宾, and the other way round).
ELSEWHERE = "elsewhere"

_OPEN = "（"
_CLOSE = "）"
_BRACKETS = str.maketrans({"(": _OPEN, ")": _CLOSE, "【": _OPEN, "】": _CLOSE, "[": _OPEN, "]": _CLOSE})
# 1. 1、 1) ① - • in front of a line, or a number and a space.
_LIST_MARK = re.compile(r"^\s*(?:\d{1,3}\s*[.、．)）:：]\s*|[①-⑳]\s*[.、．)）:：]?\s*|\d{1,3}\s+(?=\S)|[-•·*●▪]\s*)")
# A date or a clock time: a line copied from a chat with who said it and when.
_STAMP = re.compile(r"\d{4}\s*[/.\-年]\s*\d{1,2}\s*[/.\-月]\s*\d{1,2}日?|\d{1,2}:\d{2}(?::\d{2})?")
_NAME_SPLIT = re.compile(r"[，,、；;/|\s]+")
# 名字：原因 and 名字-原因.
_NAME_NOTE = re.compile(r"^\s*([^:：\-—－~～\s，,、；;/|]+)\s*[:：\-—－~～]+\s*(.+)$")
# 其他：说明 in an old list is only the 原因.
_OTHER = re.compile(r"^其他[:：]?")
# Words before a name that say what it is, and words before a 原因.
_NAME_LABEL = re.compile(r"^(?:游戏\s*ID|ID|Id|id|游戏名|角色名|角色|昵称|名字|名称|玩家)\s*[:：]\s*")
_REASON_LABEL = re.compile(r"\s*[，,]?\s*(?:原因|理由|备注|说明)\s*[:：]\s*")
# A table's header cells.
_HEADER_CELLS = {"名字", "名称", "昵称", "id", "游戏名", "游戏id", "角色", "角色名", "玩家", "原因", "理由", "备注", "说明", "标签", "时间", "序号", "编号"}
_RULE_CELL = re.compile(r"^:?-{2,}:?$")
# Marks before a line that are not part of a name: emoji, arrows, symbols.
_DECOR = re.compile(r"^[\s\u2190-\u2bff\u2600-\u27bf\U0001F000-\U0001FAFF\uFE0F\u200d★☆◆◇■□▶►→⇒>*#@]+")
# A title over a list: shown, but not checked.
_TITLE = re.compile(r"名单|避雷|以下|汇总|整理|持续更新")
# 小明/小红/阿强 一起演: names joined by marks, then a space and what they did.
_JOINED_NAMES = re.compile(r"^(\S+[/、，,；;|]\S+)\s+(\S.*)$")
# A heading with no 标签: 以下是黑名单：, 避雷：, 其他：.
_HEADING_WORDS = re.compile(r"名单|避雷|以下|汇总|整理|其他|其它")
# Words a 原因 has and a name hardly does: 小红 送人头 is a name and what they did.
_REASON_WORDS = re.compile(
    "送人头|骂人|喷人|嘴臭|摆烂|秒退|傻逼|弱智|故意|不救|带节奏|白给|恶心|坑人|乱报|演戏|卖队友|搞心态|报点|不报|逃跑|退出"
)
# Two English words with a space between: one name.
_LATIN_SPACE = re.compile(r"(?<=[A-Za-z0-9]) (?=[A-Za-z0-9])")
# Not whitespace to the name splitter, so the space survives the split.
_KEEP_SPACE = "\ue000"


@dataclass
class ImportRow:
    """One person from a paste, and what importing them would do."""

    name: str
    tags: tuple[str, ...] = ()
    reason: str = ""
    status: str = NEW
    # The entry a MERGE or SAME row matches.
    target: int = -1
    checked: bool = True
    # Names the paste gave this person more than once, kept for the preview.
    also: list[str] = field(default_factory=list)


def _clean(name: str) -> str:
    return clean_stored_name(name.replace(_KEEP_SPACE, " "))[:_MAX_NAME]


def _split_names(text: str) -> list[str]:
    return [word for word in _NAME_SPLIT.split(_LATIN_SPACE.sub(_KEEP_SPACE, text)) if word]


def _tags_only(text: str, catalog: tuple[str, ...]) -> tuple[str, ...] | None:
    """The 标签 when text is nothing but 标签, else None."""
    words = [word for word in _NAME_SPLIT.split(text.strip(" :：")) if word]
    if words and all(word in catalog for word in words):
        return tuple(dict.fromkeys(words))
    return None


def _table_row(line: str) -> str | None:
    """A spreadsheet or Markdown row as 名字：原因; "" for a header or rule row; None if not a row."""
    if "\t" not in line and not line.strip().startswith("|"):
        return None
    cells = [cell.strip() for cell in re.split(r"[|\t]", line.strip().strip("|"))]
    cells = [cell for cell in cells if cell]
    if not cells or all(_RULE_CELL.match(cell) for cell in cells):
        return ""
    if all(cell.lower() in _HEADER_CELLS for cell in cells):
        return ""
    return cells[0] if len(cells) == 1 else f"{cells[0]}：{'，'.join(cells[1:])}"


def _sections(text: str, catalog: tuple[str, ...]) -> list[tuple[str, tuple[str, ...]]]:
    """The paste in blocks, each with the 标签 a heading line gives all the names in it."""
    blocks: list[tuple[str, tuple[str, ...]]] = []
    lines: list[str] = []
    heading: tuple[str, ...] = ()
    pending = ""

    def close() -> None:
        if lines:
            blocks.append(("\n".join(lines), heading))
            lines.clear()

    for raw in text.translate(_BRACKETS).splitlines():
        line = _LIST_MARK.sub("", _DECOR.sub("", raw), count=1).strip()
        row = _table_row(line)
        if row is not None:
            line = row
        line = _NAME_LABEL.sub("", line)
        if not line:
            lines.append("")
            continue
        named = _tags_only(line, catalog)
        if named is not None and (line.endswith((":", "：")) or len(_split_names(line.strip(" :："))) == len(named)):
            # 炸房： heads the names under it.
            close()
            heading = named
            continue
        if line.endswith((":", "：")) and _CLOSE not in line and _HEADING_WORDS.search(line):
            # 以下是黑名单： is a heading, with no 标签.
            close()
            heading = ()
            pending = ""
            continue
        if pending:
            line = pending + line
            pending = ""
        elif line.endswith((":", "：")) and _CLOSE not in line and len(line.rstrip(":： ")) <= NAME_MAX:
            # 小明： with the 原因 on the next line.
            pending = line
            continue
        if line.startswith(_OPEN) and _CLOSE in line:
            inside, rest = line[1:].split(_CLOSE, 1)
            lead = _tags_only(inside, catalog)
            if lead is not None and rest.strip():
                # 【炸房】小明 小红: the names on this line get the 标签.
                close()
                blocks.append((rest, tuple(dict.fromkeys([*heading, *lead]))))
                continue
        # 名字 原因：说明 is 名字：说明. Inside brackets the label is dropped where the 原因 is read.
        if _OPEN not in line:
            parts = _REASON_LABEL.split(line, maxsplit=1)
            if len(parts) == 2 and parts[0].strip():
                line = f"{parts[0].strip()}：{parts[1]}"
        lines.append(line)
    if pending:
        lines.append(pending)
    close()
    return blocks


def _width(name: str) -> float:
    """How much of the game's name room this takes: an English letter or digit is half a Chinese character."""
    return sum(0.5 if ch.isascii() else 1 for ch in name)


def _looks_odd(name: str) -> bool:
    return _width(name) > NAME_MAX or name.isdigit() or bool(_TITLE.search(name))


def _pieces(text: str) -> list[tuple[str, str | None, bool]]:
    """(names, 原因 or None) in the order the paste has them.

    A 原因 left open runs on only when a later line closes it before any new （ opens;
    otherwise it ends with its own line, and the lines after it are read as their own.
    """
    lines = text.translate(_BRACKETS).splitlines()
    pieces: list[tuple[str, str | None, bool]] = []
    index = 0
    while index < len(lines):
        rest = _LIST_MARK.sub("", lines[index], count=1)
        header = bool(_STAMP.search(rest))
        if header:
            rest = _STAMP.sub(" ", rest)
        index += 1
        while rest.strip():
            opening = rest.find(_OPEN)
            if opening < 0:
                pieces.append((rest, None, header))
                break
            names = rest[:opening]
            closing = rest.find(_CLOSE, opening + 1)
            if closing >= 0:
                note = rest[opening + 1 : closing]
                rest = _LIST_MARK.sub("", rest[closing + 1 :].lstrip("，,、；; "), count=1)
            else:
                note = rest[opening + 1 :]
                rest = ""
                # Look ahead for the ） that closes it.
                ahead = index
                while ahead < len(lines) and _OPEN not in lines[ahead] and _CLOSE not in lines[ahead]:
                    ahead += 1
                line = lines[ahead] if ahead < len(lines) else ""
                close_at = line.find(_CLOSE)
                open_at = line.find(_OPEN)
                if close_at >= 0 and (open_at < 0 or close_at < open_at):
                    note += "".join(lines[index:ahead]) + line[:close_at]
                    rest = line[close_at + 1 :]
                    index = ahead + 1
            if not names.strip(_CLOSE + " \t") and pieces and pieces[-1][1] is not None:
                # 名字（原因）（还有） is one person with a longer 原因.
                last_names, last_note, last_header = pieces[-1]
                pieces[-1] = (last_names, f"{last_note}，{note}", last_header)
                continue
            pieces.append((names, note, header))
    return pieces


def _read_plain(text: str, catalog: tuple[str, ...], pairs: bool = False) -> list[tuple[str, tuple[str, ...], str]]:
    """A line without brackets: names, or one name with 标签 and 原因 after it.

    名字 原因 with no 标签 in it is also two names. It is read as a name and its 原因 when the
    second word sounds like one (送人头), or when the paste's other such lines carry 标签 (pairs).
    """
    spaced = text.split()
    if len(spaced) == 2 and _clean(spaced[0]) and not any(tag in spaced[1] for tag in catalog):
        if pairs or _REASON_WORDS.search(spaced[1]):
            return [(_clean(spaced[0]), (), spaced[1][:_MAX_NOTE])]
    joined = _JOINED_NAMES.match(text.strip())
    if joined:
        tags, reason = tags_and_reason(joined.group(2), catalog)
        return [(_clean(name), tags, reason) for name in _split_names(joined.group(1)) if _clean(name)]
    matched = _NAME_NOTE.match(text)
    if matched and _clean(matched.group(1)):
        tags, reason = tags_and_reason(matched.group(2), catalog)
        return [(_clean(matched.group(1)), tags, reason)]
    words = _split_names(text.strip(_CLOSE))
    names: list[str] = []
    tags: list[str] = []
    notes: list[str] = []
    for word in words:
        detail = bool(tags or notes)
        if word in catalog:
            if word not in tags:
                tags.append(word)
        elif names and (detail or ":" in word or "：" in word or any(tag in word for tag in catalog) or _width(_clean(word)) > NAME_MAX):
            note = _OTHER.sub("", word).strip(":： ")
            if note:
                notes.append(note)
        else:
            names.append(word)
    reason = "，".join(notes)
    found, _kept = tags_and_reason(reason, catalog)
    picked = order_tags(list(dict.fromkeys([*tags, *found])), catalog)
    return [(_clean(name), picked, reason[:_MAX_NOTE]) for name in names if _clean(name)]


def _mostly_pairs(lines: list[str], catalog: tuple[str, ...]) -> bool:
    """Whether this paste is 名字 原因, line by line: most of its two-word lines carry a 标签."""
    two = [line.split() for line in lines if _OPEN not in line and len(line.split()) == 2]
    tagged = [words for words in two if any(tag in words[1] for tag in catalog)]
    return len(two) >= 2 and len(tagged) * 2 >= len(two)


def _read(text: str, catalog: tuple[str, ...]) -> list[tuple[str, tuple[str, ...], str, bool]]:
    """(name, 标签, 原因, from a chat header line) for every person, in the paste's order."""
    if is_shared(text):
        return [(name, tags, reason, False) for name, tags, reason in parse_shared(text)]
    people: list[tuple[str, tuple[str, ...], str, bool]] = []
    blocks = _sections(text or "", catalog)
    pairs = _mostly_pairs([line for block, _heading in blocks for line in block.splitlines()], catalog)
    for block, heading in blocks:
        found: list[tuple[str, tuple[str, ...], str, bool]] = []
        for names, note, header in _pieces(block):
            if note is None:
                found.extend((name, tags, reason, header) for name, tags, reason in _read_plain(names, catalog, pairs))
                continue
            tags, reason = tags_and_reason(_REASON_LABEL.sub("", note, count=1).strip(" :：，,"), catalog)
            for name in _split_names(names.strip(" :：-—－~～\t" + _CLOSE)):
                if _clean(name):
                    found.append((_clean(name), tags, reason, header))
        for name, tags, reason, header in found:
            merged = order_tags(list(dict.fromkeys([*heading, *tags])), catalog) if heading else tags
            people.append((name, merged, reason, header))
    return people


def read_paste(text: str, catalog: tuple[str, ...] = TAGS) -> list[tuple[str, tuple[str, ...], str]]:
    """Every person in a paste, as (name, 标签, 原因), in the paste's order."""
    return [(name, tags, reason) for name, tags, reason, _header in _read(text, catalog)]


def _find(name: str, entries: list[Entry]) -> int:
    """The entry this name is: the same name, or one of the two is the other cut short."""
    key = fold(name)
    for index, entry in enumerate(entries):
        if fold(entry.name) == key:
            return index
    for index, entry in enumerate(entries):
        other = fold(entry.name)
        short, long = sorted((key, other), key=len)
        if len(short) >= _SAME_PREFIX and long.startswith(short):
            return index
    return -1


def _adds_to(row: ImportRow, entry: Entry) -> bool:
    longer = len(fold(row.name)) > len(fold(entry.name))
    return bool(set(row.tags) - set(entry.tags)) or merge_reason(entry.reason, row.reason) != entry.reason or longer


def plan_import(
    text: str, entries: list[Entry], catalog: tuple[str, ...] = TAGS, elsewhere: list[Entry] = ()
) -> list[ImportRow]:
    """What 导入 would do with this paste: one row per person, checked if it changes the list.

    A name on the other list (elsewhere) is shown but unchecked: a player is on one list.
    """
    rows: list[ImportRow] = []
    by_key: dict[str, ImportRow] = {}
    headers: set[str] = set()
    for name, tags, reason, header in _read(text, catalog):
        key = fold(name)
        if not key:
            continue
        twin = by_key.get(key)
        if twin is not None:
            # The same person twice in one paste: one row with both 原因.
            twin.tags = order_tags(list(dict.fromkeys([*twin.tags, *tags])), catalog)
            twin.reason = merge_reason(twin.reason, reason)
            continue
        row = ImportRow(name, tuple(tags), reason[:_MAX_NOTE])
        by_key[key] = row
        rows.append(row)
        if header:
            headers.add(key)
    for row in rows:
        if _looks_odd(row.name) or fold(row.name) in headers:
            row.status, row.checked = ODD, False
            continue
        if any(fold(other.name) == fold(row.name) for other in elsewhere):
            row.status, row.checked = ELSEWHERE, False
            continue
        row.target = _find(row.name, entries)
        if row.target >= 0:
            changes = _adds_to(row, entries[row.target])
            row.status, row.checked = (MERGE, True) if changes else (SAME, False)
    return rows


# --- 标签 a pasted batch could use --------------------------------------------------------

# A phrase seen in this many 原因 or more is offered as a 标签.
SUGGEST_MIN_ROWS = 2
SUGGEST_LIMIT = 8
_SUGGEST_LONGEST = 6
# Words that carry no meaning on their own, and characters a phrase should not start or end on.
_FILLER = {
    "一直", "就是", "还是", "然后", "因为", "所以", "但是", "不是", "没有", "什么", "这个", "那个",
    "自己", "我们", "你们", "他们", "她们", "队友", "游戏", "一把", "一局", "这把", "上把", "开局",
    "知道", "不会", "不能", "可以", "真的", "感觉", "直接", "已经", "还有", "有点", "一样", "东西",
}
_EDGE = set("的了是就都也还在和我你他她它们很太又被把给着呢吧啊吗呀哦哈这那个一有")
# The game's own words: sides, roles, places, phases. A 原因 names them to say what happened
# (好人帮狼炸房, 跳银行), so many 原因 share them, but they say nothing about the player. Such a
# word, or a piece of one (银行 from 银行家), is never offered as a 标签; a phrase that holds one
# and says more (乱投票, 假跳侦探) still can be. From the 模仿者游戏模式 page of the BWIKI.
GAME_WORDS: tuple[str, ...] = (
    # Sides.
    "侦探团", "侦探阵营", "模仿者", "神秘客", "中立", "好人", "坏人", "狼人", "平民",
    # 侦探团.
    "侦探", "哨兵", "治安官", "猎人", "香料师", "锁匠", "银行家", "修士", "演说家", "拳击手", "灵媒",
    "学徒", "密探", "掮客", "药剂师", "巡林员", "执灯人", "评论家", "邮差", "牛仔", "昆虫学者",
    # 模仿者.
    "神偷", "千面人", "阴谋家", "烟火师", "怪盗", "催眠师", "地下医生", "处刑人", "指挥家",
    # 神秘客.
    "流浪汉", "送货员", "愚人", "棋手", "清洁工", "顾问", "降灵师", "导演",
    # Maps and places.
    "白沙街", "疯人院", "闪金石窟", "石窟", "庄园", "寝室", "祷告堂", "娱乐室", "电力室", "沐浴间", "餐厅",
    "花园", "盥洗室", "杂物间", "监控室", "暗道门", "电梯房", "宴会厅", "主卧", "客卧", "书房", "厨房",
    "花房", "起居室", "门廊", "回廊", "茶话室", "楼梯", "走廊", "办公区", "入户厅", "宿舍", "食堂",
    "通讯室", "熔炉房", "采矿区", "废墟", "会议室",
    # Phases and mechanics.
    "紧急会议", "开会", "发言", "投票", "弃票", "淘汰", "出局", "查验", "任务", "演绎", "破译", "发电",
    "电台", "监控", "密信", "货箱", "藏身柜", "摆钟", "吊灯", "迷雾", "复盘", "极速时刻", "落幕时刻",
    "身份", "技能",
    # This mode.
    "模仿者游戏", "模仿者狂欢", "推演成功", "案件还原", "狂欢",
)


def is_game_word(phrase: str) -> bool:
    """Whether a phrase is one of the game's own words, or a piece of one."""
    return any(phrase in word for word in GAME_WORDS)
_RUNS = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9]{2,}")


@dataclass
class TagSuggestion:
    """A phrase several 原因 share, offered as a 标签 for those records."""

    tag: str
    existing: bool
    # Indices, in the rows given, of the records that would get it.
    rows: tuple[int, ...]


def _phrases(reason: str) -> set[str]:
    found: set[str] = set()
    for run in _RUNS.findall(reason or ""):
        if run.isascii():
            found.add(run.lower())
            continue
        for size in range(2, min(_SUGGEST_LONGEST, len(run)) + 1):
            for start in range(len(run) - size + 1):
                phrase = run[start : start + size]
                if phrase[0] in _EDGE or phrase[-1] in _EDGE or phrase in _FILLER:
                    continue
                found.add(phrase)
    return found


def suggest_tags(
    rows: list[tuple[str, tuple[str, ...], str, int]], catalog: tuple[str, ...] = TAGS
) -> list[TagSuggestion]:
    """Phrases that turn up in the 原因 of several records, as 标签 to add to those records.

    rows are (name, 标签, 原因, target), as the import gives them. A phrase that is already a
    标签 is offered as that 标签, for the records that do not have it yet. A phrase that holds
    a 标签, or sits inside one, is left out: those records were tagged from it already. When a
    longer phrase covers the same records as a shorter one inside it, the longer one is kept,
    so 送人头 rather than 人头; when the shorter one covers more, it is kept instead.
    """
    seen: dict[str, set[int]] = {}
    for index, (_name, _tags, reason, _target) in enumerate(rows):
        for phrase in _phrases(reason):
            seen.setdefault(phrase, set()).add(index)
    known = [tag.lower() for tag in catalog]
    candidates: dict[str, set[int]] = {}
    for phrase, where in seen.items():
        if len(where) < SUGGEST_MIN_ROWS or len(phrase) > _MAX_TAG:
            continue
        if phrase not in known and any(tag in phrase or phrase in tag for tag in known):
            continue
        # The game's own words are not 标签, unless the player made one of them a 标签 already.
        if phrase not in known and is_game_word(phrase):
            continue
        lacking = {index for index in where if phrase not in (tag.lower() for tag in rows[index][1])}
        if len(lacking) >= SUGGEST_MIN_ROWS or (phrase in known and lacking):
            candidates[phrase] = lacking
    kept: dict[str, set[int]] = {}
    for phrase, where in candidates.items():
        covered = False
        for other, other_where in candidates.items():
            if other == phrase:
                continue
            # A longer phrase on the same records says it better; a shorter one on more records is the 标签.
            if phrase in other and other_where == where:
                covered = True
            elif other in phrase and len(other_where) > len(where) and where <= other_where:
                covered = True
            if covered:
                break
        if not covered:
            kept[phrase] = where
    ranked = sorted(kept.items(), key=lambda item: (-len(item[1]), -len(item[0]), item[0]))
    by_lower = {tag.lower(): tag for tag in catalog}
    return [
        TagSuggestion(tag=by_lower.get(phrase, phrase), existing=phrase in by_lower, rows=tuple(sorted(where)))
        for phrase, where in ranked[:SUGGEST_LIMIT]
    ]


def with_tags(
    rows: list[tuple[str, tuple[str, ...], str, int]], picked: list[TagSuggestion]
) -> list[tuple[str, tuple[str, ...], str, int]]:
    """The rows with the picked 标签 added to the records each one is for."""
    result = [list(row) for row in rows]
    for suggestion in picked:
        for index in suggestion.rows:
            tags = tuple(result[index][1])
            if suggestion.tag not in tags:
                result[index][1] = (*tags, suggestion.tag)
    return [(name, tuple(tags), reason, target) for name, tags, reason, target in result]
