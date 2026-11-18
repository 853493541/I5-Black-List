//! Properties of the text normalising and the countdown and ready parsing.

use lobby::{
    countdown_in, fold, is_lobby_chrome, match_label, normalize_text, ready_in, split_ellipsis,
    strip_noise, with_game_ellipsis, Entry, MatchKind, NameLabel,
};
use proptest::prelude::*;

const NAME: &str = "[a-zA-Z0-9\u{4e00}-\u{9fa5}]{1,12}";

fn full_width(text: &str) -> String {
    text.chars()
        .map(|ch| {
            if ch.is_ascii_digit() {
                char::from_u32(ch as u32 - '0' as u32 + 0xFF10).unwrap()
            } else {
                ch
            }
        })
        .collect()
}

proptest! {
    #![proptest_config(ProptestConfig { rng_seed: proptest::test_runner::RngSeed::Fixed(0x1a5_10bb), ..ProptestConfig::default() })]

    #[test]
    fn normalize_is_idempotent_and_spaceless(text in "\\PC{0,24}") {
        let once = normalize_text(&text);
        prop_assert_eq!(normalize_text(&once), once.clone());
        prop_assert!(!once.chars().any(char::is_whitespace));
    }

    #[test]
    fn strip_noise_keeps_only_letters_and_numbers(text in "\\PC{0,24}") {
        let kept = strip_noise(&text);
        prop_assert_eq!(strip_noise(&kept), kept.clone());
        prop_assert!(kept.chars().all(|ch| !ch.is_whitespace() && !ch.is_ascii_punctuation()));
    }

    #[test]
    fn a_trailing_ellipsis_is_cut(name in NAME, tail in prop::sample::select(vec!["...", "…", "⋯", "。。", "··", ".", "。", "……", "..…"])) {
        prop_assert_eq!(split_ellipsis(&name), (name.clone(), false));
        prop_assert_eq!(split_ellipsis(&format!("{name}{tail}")), (name.clone(), true));
        prop_assert_eq!(with_game_ellipsis(&name, true), format!("{name}..."));
        prop_assert_eq!(with_game_ellipsis(&name, false), name);
    }

    #[test]
    fn fold_ignores_latin_case_and_marks(name in "[a-zA-Z0-9]{1,12}", mark in "[`'.,!~ -]{0,3}") {
        prop_assert_eq!(fold(&name.to_uppercase()), fold(&format!("{}{mark}", name.to_lowercase())));
    }

    #[test]
    fn countdown_reads_one_to_three_digits(seconds in 0u32..1000, colon in prop::sample::select(vec!["", ":", "："]),
                                           space in "[ \u{3000}]{0,2}", wide in any::<bool>()) {
        let number = if wide { full_width(&seconds.to_string()) } else { seconds.to_string() };
        let line = format!("倒计时{space}{colon}{space}{number}{space}秒");
        prop_assert_eq!(countdown_in(&line), Some(i64::from(seconds)));
        prop_assert_eq!(countdown_in(&format!("¥{line}")), Some(i64::from(seconds)));
        let chrome = is_lobby_chrome(&format!("倒计时{colon}{number}秒"));
        prop_assert!(chrome);
        prop_assert_eq!(countdown_in(&format!("倒计时{}秒", seconds + 1000)), None);
    }

    #[test]
    fn ready_reads_one_or_two_digits(count in 0u32..100, colon in prop::sample::select(vec!["", ":", "："]), space in " {0,2}") {
        prop_assert_eq!(ready_in(&format!("准备就绪{colon}{space}{count}{space}/{space}12")), Some(i64::from(count)));
        prop_assert_eq!(ready_in(&format!("准备就绪{colon}{}/12", count + 100)), None);
        prop_assert_eq!(ready_in(&format!("准备就绪{colon}{count}/11")), None);
    }

    #[test]
    fn a_listed_name_matches_itself_and_its_cut(name in "[a-z\u{4e00}-\u{9fa5}]{4,10}") {
        let entries = vec![Entry::named(name.clone()), Entry::named("示例坏人")];
        let label = NameLabel { raw: name.clone(), visible: name.clone(), ..NameLabel::default() };
        let found = match_label(&label, &entries);
        prop_assert_eq!(found.len(), 1);
        prop_assert_eq!(found[0].kind, MatchKind::Exact);
        let cut: String = name.chars().take(4).collect();
        let label = NameLabel { raw: format!("{cut}..."), visible: format!("{cut}..."), truncated: true, unclear: false };
        let found = match_label(&label, &entries);
        prop_assert!(found.iter().any(|item| item.index == 0));
    }
}

#[test]
fn chrome_and_unclear_lines_never_match() {
    let entries = vec![Entry::named("准备就绪"), Entry::named("心动小鹿")];
    for raw in [
        "准备就绪：11/12",
        "倒计时10秒",
        "推演成功",
        "模仿者狂欢（12人狂欢）",
    ] {
        let label = NameLabel {
            raw: raw.into(),
            visible: raw.into(),
            ..NameLabel::default()
        };
        assert!(match_label(&label, &entries).is_empty(), "{raw}");
    }
    let unclear = NameLabel {
        raw: "心动小鹿".into(),
        visible: "心动小鹿".into(),
        truncated: false,
        unclear: true,
    };
    assert!(match_label(&unclear, &entries).is_empty());
}
