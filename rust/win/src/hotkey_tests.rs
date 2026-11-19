use super::*;
use proptest::prelude::*;

#[test]
fn empty_hotkey_stays_unset() {
    assert_eq!(parse_hotkey(""), None);
    assert_eq!(parse_hotkey("   "), None);
    assert_eq!(parse_hotkey("Ctrl"), None);
}

#[test]
fn hotkey_canonical_form() {
    let spec = parse_hotkey("shift+ctrl+b").unwrap();
    assert_eq!(spec.display, "Ctrl+Shift+B");
    assert_eq!(spec.vk, 0x42);
    assert_eq!(spec.modifiers, vec![Modifier::Ctrl, Modifier::Shift]);
    assert_eq!(spec.win_modifiers(), MOD_NOREPEAT | MOD_CONTROL | MOD_SHIFT);
    let f8 = parse_hotkey("F8").unwrap();
    assert_eq!((f8.display.as_str(), f8.vk), ("F8", 0x77));
}

#[test]
fn two_keys_at_most() {
    assert_eq!(two_keys("Ctrl+Alt+F11"), "Ctrl+F11");
    assert_eq!(two_keys("Alt+Shift+K"), "Alt+K");
    assert_eq!(two_keys("Alt+1"), "Alt+1");
    assert_eq!(two_keys("F8"), "F8");
    assert_eq!(two_keys(""), "");
}

#[test]
fn keys_in_everyday_use_are_no_hotkey() {
    for text in [
        "A", "7", "Shift+A", "Shift+7", "Win+D", "Win+1", "Ctrl+C", "Ctrl+V", "Ctrl+X", "Ctrl+Z", "Ctrl+Y", "Ctrl+A", "Ctrl+S",
        "Alt+F4", "Ctrl+F4", "Shift+F10", "F12",
    ] {
        assert_eq!(parse_hotkey(text), None, "{text}");
    }
    assert!(everyday(&[Modifier::Shift], "Q") && everyday(&[Modifier::Ctrl], "V") && !everyday(&[Modifier::Ctrl], "K"));
    for text in ["Alt+1", "Alt+A", "Ctrl+K", "Ctrl+9", "Shift+F8", "Alt+F12", "F8", "Ctrl+Shift+C"] {
        assert!(parse_hotkey(text).is_some(), "{text}");
    }
}

/// tests/golden/hotkeys.tsv is written by blacklist_detect/hotkey.py itself: input, display, vk:modifiers, two_keys.
#[test]
fn matches_the_python_parser_on_its_own_golden_data() {
    let golden = include_str!("../tests/golden/hotkeys.tsv");
    let mut checked = 0;
    for line in golden.lines() {
        let cols: Vec<&str> = line.split('\t').collect();
        assert_eq!(cols.len(), 4, "{line:?}");
        let spec = parse_hotkey(cols[0]);
        let shown = spec.as_ref().map_or("-".to_string(), |s| s.display.clone());
        let codes = spec.as_ref().map_or("-".to_string(), |s| format!("{}:{}", s.vk, s.win_modifiers()));
        assert_eq!((shown.as_str(), codes.as_str(), two_keys(cols[0]).as_str()), (cols[1], cols[2], cols[3]), "{:?}", cols[0]);
        checked += 1;
    }
    assert!(checked > 500);
}

fn piece() -> impl Strategy<Value = String> {
    prop_oneof![
        prop::sample::select(vec!["Ctrl", "alt", "SHIFT", "win", "meta", "control", "super"]).prop_map(String::from),
        "[A-Za-z0-9]",
        (0u32..20).prop_map(|n| format!("f{n}")),
        ".{0,3}",
    ]
}

proptest! {
    #[test]
    fn never_panics(text in ".{0,20}") {
        let _ = parse_hotkey(&text);
        let _ = two_keys(&text);
    }

    #[test]
    fn display_is_a_fixed_point(parts in prop::collection::vec(piece(), 1..4)) {
        let text = parts.join("+");
        if let Some(spec) = parse_hotkey(&text) {
            prop_assert_eq!(parse_hotkey(&spec.display), Some(spec.clone()));
            prop_assert!(spec.win_modifiers() & MOD_NOREPEAT != 0);
            prop_assert!((0x30..=0x39).contains(&spec.vk) || (0x41..=0x5A).contains(&spec.vk) || (0x70..=0x7B).contains(&spec.vk));
            let shortened = two_keys(&text);
            let expected = if spec.modifiers.len() > 1 { shortened.split('+').count() == 2 } else { shortened == text };
            prop_assert!(expected, "two_keys({:?}) = {:?}", text, shortened);
        }
    }

    #[test]
    fn modifier_order_and_case_do_not_matter(key in "[A-Z]|F[1-9]", flags in 0u8..16) {
        let names = ["Ctrl", "Alt", "Shift", "Win"];
        let chosen: Vec<&str> = (0..4).filter(|i| flags & (1 << i) != 0).map(|i| names[i]).collect();
        let forward = format!("{}+{key}", chosen.join("+"));
        let backward = format!("{}+{}", chosen.iter().rev().map(|n| n.to_lowercase()).collect::<Vec<_>>().join("+"), key.to_lowercase());
        let (a, b) = if chosen.is_empty() { (parse_hotkey(&key), parse_hotkey(&key.to_lowercase())) } else { (parse_hotkey(&forward), parse_hotkey(&backward)) };
        prop_assert_eq!(a, b);
    }
}

#[test]
fn a_key_taken_in_the_box_follows_the_python_rules() {
    use Modifier::*;
    assert_eq!(take_key(Some("1"), &[Alt], "Alt+F12"), Ok("Alt+1".to_string()));
    assert_eq!(take_key(Some("F5"), &[], ""), Ok("F5".to_string()));
    assert_eq!(take_key(None, &[Alt], ""), Err("用字母、数字或 F1–F12"));
    assert_eq!(take_key(Some("1"), &[Ctrl, Alt], ""), Err("最多两个键，比如 Alt+1"));
    assert_eq!(take_key(Some("Q"), &[Shift], ""), Err("加上 Ctrl 或 Alt，比如 Alt+1"));
    assert_eq!(take_key(Some("C"), &[Ctrl], ""), Err("这是常用的键，换一个"));
    assert_eq!(take_key(Some("F12"), &[Alt], "Alt+F12"), Err("场景已在用这个键，换一个"));
}
