//! Importing never panics, whatever is pasted: any text, and text built from the marks the reader looks at.

use data::import::{default_catalog, plan_import, read_paste, suggest_tags, with_tags, Entry};
use proptest::prelude::*;

// The characters the reader treats specially, so random pastes hit its branches often.
const MARKS: &[&str] = &[
    "（", "）", "(", ")", "【", "】", "[", "]", "，", ",", "、", "；", ";", "/", "|", "\t", " ", "　", "\n", "\r\n", "\r", "\u{2028}",
    "\x1c", "：", ":", "-", "—", "～", "1.", "12 ", "①", "•", "★", "😀", "\u{fe0f}", "\u{feff}", "#模仿者小工具 黑名单 2人", "原因：",
    "理由：", "ID：", "炸房", "挂机", "贴脸", "演员", "送人头", "以下是名单：", "避雷", "其他：", "2026/10/12", "20:13:45", "示例坏人",
    "心动小鹿", "心动星星", "Lucky Star", "ß", "İ", "…", "...", "|---|", "名字\t原因", "\u{e000}", "\u{200d}", "²", "ｓｈｉ",
];

fn paste() -> impl Strategy<Value = String> {
    prop::collection::vec(prop::sample::select(MARKS), 0..40).prop_map(|parts| parts.concat())
}

fn entries() -> Vec<Entry> {
    vec![Entry::new("示例坏人", "炸房", &["炸房"]), Entry::new("心动小鹿大王", "", &[]), Entry::new("LuckyStar", "", &["演员"])]
}

fn exercise(text: &str) {
    let mut catalog = default_catalog();
    catalog.push("演员".into());
    let read = read_paste(text, &catalog);
    let rows = plan_import(text, &entries(), &catalog, &[Entry::new("心动星星", "", &[])]);
    assert!(rows.len() <= read.len());
    for row in &rows {
        assert!(!row.name.is_empty());
        assert!(row.target < entries().len() as i64);
        assert!(row.reason.chars().count() <= 200);
    }
    let records: Vec<_> = rows.iter().map(|r| (r.name.clone(), r.tags.clone(), r.reason.clone(), r.target)).collect();
    let found = suggest_tags(&records, &catalog);
    assert!(found.len() <= 8);
    with_tags(&records, &found);
}

proptest! {
    #![proptest_config(ProptestConfig { cases: 2000, rng_seed: proptest::test_runner::RngSeed::Fixed(20261118), ..ProptestConfig::default() })]

    #[test]
    fn any_text_never_panics(text in any::<String>()) {
        exercise(&text);
    }

    #[test]
    fn pastes_of_marks_never_panic(text in paste()) {
        exercise(&text);
    }
}
