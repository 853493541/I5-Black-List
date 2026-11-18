//! importing.suggest_tags: phrases several 原因 share, offered as 标签 for those records.

use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::sync::LazyLock;

use regex::Regex;

use super::tags::MAX_TAG;
use super::text::{len, lower};

/// A phrase seen in this many 原因 or more is offered as a 标签.
pub const SUGGEST_MIN_ROWS: usize = 2;
pub const SUGGEST_LIMIT: usize = 8;
const SUGGEST_LONGEST: usize = 6;
const FILLER: [&str; 36] = [
    "一直", "就是", "还是", "然后", "因为", "所以", "但是", "不是", "没有", "什么", "这个", "那个", "自己", "我们", "你们", "他们", "她们",
    "队友", "游戏", "一把", "一局", "这把", "上把", "开局", "知道", "不会", "不能", "可以", "真的", "感觉", "直接", "已经", "还有", "有点",
    "一样", "东西",
];
const EDGE: &str = "的了是就都也还在和我你他她它们很太又被把给着呢吧啊吗呀哦哈这那个一有";

/// The game's own words: sides, roles, places, phases. Never offered as a 标签, nor any piece of one.
pub const GAME_WORDS: [&str; 115] = [
    "侦探团", "侦探阵营", "模仿者", "神秘客", "中立", "好人", "坏人", "狼人", "平民", "侦探", "哨兵", "治安官", "猎人", "香料师", "锁匠",
    "银行家", "修士", "演说家", "拳击手", "灵媒", "学徒", "密探", "掮客", "药剂师", "巡林员", "执灯人", "评论家", "邮差", "牛仔",
    "昆虫学者", "神偷", "千面人", "阴谋家", "烟火师", "怪盗", "催眠师", "地下医生", "处刑人", "指挥家", "流浪汉", "送货员", "愚人",
    "棋手", "清洁工", "顾问", "降灵师", "导演", "白沙街", "疯人院", "闪金石窟", "石窟", "庄园", "寝室", "祷告堂", "娱乐室", "电力室",
    "沐浴间", "餐厅", "花园", "盥洗室", "杂物间", "监控室", "暗道门", "电梯房", "宴会厅", "主卧", "客卧", "书房", "厨房", "花房",
    "起居室", "门廊", "回廊", "茶话室", "楼梯", "走廊", "办公区", "入户厅", "宿舍", "食堂", "通讯室", "熔炉房", "采矿区", "废墟",
    "会议室", "紧急会议", "开会", "发言", "投票", "弃票", "淘汰", "出局", "查验", "任务", "演绎", "破译", "发电", "电台", "监控",
    "密信", "货箱", "藏身柜", "摆钟", "吊灯", "迷雾", "复盘", "极速时刻", "落幕时刻", "身份", "技能", "模仿者游戏", "模仿者狂欢",
    "推演成功", "案件还原", "狂欢",
];

/// Whether a phrase is one of the game's own words, or a piece of one.
pub fn is_game_word(phrase: &str) -> bool {
    GAME_WORDS.iter().any(|word| word.contains(phrase))
}

static RUNS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[\x{4e00}-\x{9fff}]+|[A-Za-z0-9]{2,}").unwrap());

/// A record as the import gives it: name, 标签, 原因, target.
pub type Record = (String, Vec<String>, String, i64);

/// A phrase several 原因 share, offered as a 标签 for those records (indices into the rows given).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TagSuggestion {
    pub tag: String,
    pub existing: bool,
    pub rows: Vec<usize>,
}

fn phrases(reason: &str) -> BTreeSet<String> {
    let mut found = BTreeSet::new();
    for run in RUNS.find_iter(reason).map(|m| m.as_str()) {
        if run.is_ascii() {
            found.insert(lower(run));
            continue;
        }
        let chars: Vec<char> = run.chars().collect();
        for size in 2..=SUGGEST_LONGEST.min(chars.len()) {
            for start in 0..=chars.len() - size {
                let piece = &chars[start..start + size];
                let phrase: String = piece.iter().collect();
                if EDGE.contains(piece[0]) || EDGE.contains(piece[size - 1]) || FILLER.contains(&phrase.as_str()) {
                    continue;
                }
                found.insert(phrase);
            }
        }
    }
    found
}

/// Phrases that turn up in the 原因 of several records, as 标签 to add to those records.
pub fn suggest_tags(rows: &[Record], catalog: &[String]) -> Vec<TagSuggestion> {
    let mut seen: BTreeMap<String, BTreeSet<usize>> = BTreeMap::new();
    for (index, (_, _, reason, _)) in rows.iter().enumerate() {
        for phrase in phrases(reason) {
            seen.entry(phrase).or_default().insert(index);
        }
    }
    let known: Vec<String> = catalog.iter().map(|tag| lower(tag)).collect();
    let mut candidates: BTreeMap<String, BTreeSet<usize>> = BTreeMap::new();
    for (phrase, place) in &seen {
        if place.len() < SUGGEST_MIN_ROWS || len(phrase) > MAX_TAG {
            continue;
        }
        let is_known = known.contains(phrase);
        if !is_known && known.iter().any(|tag| tag.contains(phrase.as_str()) || phrase.contains(tag.as_str())) {
            continue;
        }
        // The game's own words are not 标签, unless the player made one of them a 标签 already.
        if !is_known && is_game_word(phrase) {
            continue;
        }
        let lacking: BTreeSet<usize> =
            place.iter().copied().filter(|&index| !rows[index].1.iter().any(|tag| lower(tag) == *phrase)).collect();
        if lacking.len() >= SUGGEST_MIN_ROWS || (is_known && !lacking.is_empty()) {
            candidates.insert(phrase.clone(), lacking);
        }
    }
    let mut kept: Vec<(&String, &BTreeSet<usize>)> = Vec::new();
    for (phrase, place) in &candidates {
        let covered = candidates.iter().any(|(other, other_place)| {
            // A longer phrase on the same records says it better; a shorter one on more records is the 标签.
            other != phrase
                && ((other.contains(phrase.as_str()) && other_place == place)
                    || (phrase.contains(other.as_str()) && other_place.len() > place.len() && place.is_subset(other_place)))
        });
        if !covered {
            kept.push((phrase, place));
        }
    }
    kept.sort_by(|a, b| b.1.len().cmp(&a.1.len()).then(len(b.0).cmp(&len(a.0))).then(a.0.cmp(b.0)));
    let mut by_lower: HashMap<String, &String> = HashMap::new();
    for tag in catalog {
        by_lower.insert(lower(tag), tag);
    }
    kept.into_iter()
        .take(SUGGEST_LIMIT)
        .map(|(phrase, place)| TagSuggestion {
            tag: by_lower.get(phrase).map_or_else(|| phrase.clone(), |tag| (*tag).clone()),
            existing: by_lower.contains_key(phrase),
            rows: place.iter().copied().collect(),
        })
        .collect()
}

/// The rows with the picked 标签 added to the records each one is for.
pub fn with_tags(rows: &[Record], picked: &[TagSuggestion]) -> Vec<Record> {
    let mut result = rows.to_vec();
    for suggestion in picked {
        for &index in &suggestion.rows {
            if !result[index].1.contains(&suggestion.tag) {
                result[index].1.push(suggestion.tag.clone());
            }
        }
    }
    result
}
