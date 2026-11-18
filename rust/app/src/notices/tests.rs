//! Parity with the Python app on golden.json (written by golden.py from the Python code itself), and
//! the timings of the corner cards and the toast.

use serde_json::Value;

use super::corner::*;
use super::glow;
use super::queue::{CornerNotice, Measure};
use super::toast::{self, Toast};
use super::update::{read_notes, Effect, State, UpdateDialog, UpdateOffer};
use data::update::Release;

fn golden() -> Value {
    serde_json::from_str(include_str!("golden.json")).expect("golden.json reads")
}

fn texts(value: &Value) -> Vec<String> {
    value.as_array().unwrap().iter().map(|v| v.as_str().unwrap().to_string()).collect()
}

fn hits_of(value: &Value) -> Vec<(String, Vec<String>)> {
    value.as_array().unwrap().iter().map(|pair| (pair[0].as_str().unwrap().to_string(), texts(&pair[1]))).collect()
}

#[test]
fn result_messages_match_python() {
    for case in golden()["messages"].as_array().unwrap() {
        let messages = result_messages(&hits_of(&case["hits"]), &texts(&case["likes"]), case["unclear"].as_u64().unwrap() as usize);
        let want = case["out"].as_array().unwrap();
        assert_eq!(messages.len(), want.len());
        for (got, want) in messages.iter().zip(want) {
            assert_eq!(got.kind.name(), want["kind"]);
            assert_eq!(got.title, want["title"]);
            assert_eq!(got.note, want["note"]);
            assert_eq!(got.more as u64, want["more"].as_u64().unwrap());
            let people: Vec<(String, Vec<String>)> = got.people.iter().map(|p| (p.name.clone(), p.tags.clone())).collect();
            assert_eq!(people, hits_of(&want["people"]));
        }
    }
}

#[test]
fn constants_match_python() {
    let t = &golden()["timings"];
    assert_eq!(t["NOTICE_MS"], NOTICE_MS);
    assert_eq!(t["CHECKING_MS"], CHECKING_MS);
    assert_eq!(t["_MARGIN"], MARGIN);
    assert_eq!(t["_GAP"], GAP);
    assert_eq!(t["_RISE"], RISE);
    assert_eq!(t["_RISE_MS"], RISE_MS);
    assert_eq!(t["_NEXT_MS"], NEXT_MS);
    assert_eq!(t["_TICK_MS"], TICK_MS);
    assert_eq!(t["RESTART_MS"], super::update::RESTART_MS);
}

#[test]
fn cards_stand_where_python_puts_them() {
    let g = golden();
    let a: Vec<i32> = g["area"].as_array().unwrap().iter().map(|v| v.as_i64().unwrap() as i32).collect();
    let area = Area { x: a[0], y: a[1], width: a[2], height: a[3] };
    for placed in g["placed"].as_array().unwrap() {
        let ints = |key: &str| -> Vec<i32> { placed[key].as_array().unwrap().iter().map(|v| v.as_i64().unwrap() as i32).collect() };
        let width = card_width(&ints("natural"));
        assert_eq!(width as i64, placed["width"].as_i64().unwrap());
        let spots: Vec<Vec<i32>> = places(Some(area), width, &ints("heights")).into_iter().map(|(x, y)| vec![x, y]).collect();
        let want: Vec<Vec<i32>> = placed["spots"].as_array().unwrap().iter().map(|s| vec![s[0].as_i64().unwrap() as i32, s[1].as_i64().unwrap() as i32]).collect();
        assert_eq!(spots, want);
    }
}

fn release(size: i64, base: &str, notes: &[&str]) -> Release {
    Release {
        version: "v9.9.9".into(),
        url: String::new(),
        sha256: String::new(),
        size,
        base: base.into(),
        notes: notes.iter().map(|n| n.to_string()).collect(),
        mirror: String::new(),
        mirrors: Vec::new(),
    }
}

fn same(dialog: &UpdateDialog, want: &Value, name: &str) {
    assert_eq!(dialog.title, want["title"], "{name}");
    assert_eq!(dialog.summary, want["summary"], "{name}");
    assert_eq!(dialog.notes.join("\n"), want["notes"], "{name}");
    assert_eq!(dialog.status, want["status"], "{name}");
    assert_eq!(dialog.bar.map(u64::from), want["bar"].as_u64(), "{name}");
    assert_eq!(dialog.close_visible, want["close"], "{name}");
    assert_eq!(dialog.band_visible, want["band"], "{name}");
    assert_eq!(dialog.band_visible && dialog.skip_visible, want["skip"], "{name}");
    assert_eq!(dialog.action, want["action"], "{name}");
}

#[test]
fn update_dialog_matches_python_state_by_state() {
    let g = golden();
    let current = g["version"].as_str().unwrap();
    let u = &g["updates"];
    let notes = ["花边铺满整个游戏", "卡片跟着游戏大小", "检查更快"];
    let mut d = UpdateDialog::new(&release(12_345_678, "v0.0.1", &notes), current, false);
    same(&d, &u["idle"], "idle");
    assert_eq!(d.start(None), Effect::StartDownload);
    same(&d, &u["downloading"], "downloading");
    d.progress(1, 3);
    same(&d, &u["progress_1_3"], "1/3");
    d.progress(5, 1000);
    same(&d, &u["progress_5_1000"], "5/1000");
    d.failed("下载失败，等会儿再试");
    same(&d, &u["failed"], "failed");
    assert_eq!(d.done(), Effect::RestartAfter(900));
    same(&d, &u["restarting"], "restarting");
    same(&UpdateDialog::new(&release(12_345_678, "v99.0.0", &notes), current, false), &u["full"], "full");
    same(&UpdateDialog::new(&release(12_345_678, "v0.0.1", &notes), current, true), &u["source"], "source");
    same(&UpdateDialog::new(&release(10, "v0.0.1", &[]), current, false), &u["tiny"], "tiny");
}

#[test]
fn update_dialog_buttons() {
    let notes = ["检查更快"];
    let mut d = UpdateDialog::new(&release(1, "v0.0.1", &notes), "v1.0.1", false);
    // The new version comes first: ×, Esc, 跳过 and a click outside do not close it.
    assert_eq!(d.reject(), Effect::None);
    assert_eq!(d.skip(), Effect::None);
    assert_eq!(d.click_outside(), Effect::Nudge);
    assert_eq!(d.start(Some("v9.9.9")), Effect::RestartAfter(900), "already staged: restart at once");
    assert!(d.busy());
    assert_eq!(d.start(None), Effect::None, "no second download while restarting");
    let mut d = UpdateDialog::new(&release(1, "v0.0.1", &notes), "v1.0.1", false);
    d.start(None);
    d.failed("x");
    assert_eq!(d.act(None), Effect::StartDownload, "重试");
    d.failed("x");
    assert_eq!(d.skip(), Effect::Close, "跳过");
    let mut full = UpdateDialog::new(&release(1, "v99.0.0", &notes), "v1.0.1", false);
    assert_eq!(full.state, State::Full);
    assert_eq!(full.act(None), Effect::OpenUrl(data::update::RELEASES_URL.into()));
    assert_eq!(full.start(None), Effect::None);
    let mut source = UpdateDialog::new(&release(1, "v0.0.1", &notes), "v1.0.1", true);
    assert_eq!(source.reject(), Effect::Close);
    assert_eq!(source.click_outside(), Effect::Close);
    assert_eq!(source.act(None), Effect::Close);
}

#[test]
fn offer_shows_three_lines_and_notes_read_like_release_py() {
    let offer = UpdateOffer::new(&release(1, "v0.0.1", &["一", "二", "三", "四"]));
    assert_eq!(offer.title, "发现新版本 v9.9.9");
    assert_eq!(offer.notes, ["· 一", "· 二", "· 三"]);
    assert_eq!(read_notes("- 花边更好看\n\n · 检查更快 \n• 卡片\n* 小改动\n"), ["花边更好看", "检查更快", "卡片", "小改动"]);
    let shipped = include_str!("../../../../build/notes/v1.0.1.txt");
    assert_eq!(read_notes(shipped), ["检查更快，检查时游戏更流畅"]);
}

#[test]
fn glow_rings_match_python() {
    for (size, want) in golden()["rings"].as_object().unwrap() {
        let (w, h) = size.split_once('x').unwrap();
        let rings = glow::rings(w.parse().unwrap(), h.parse().unwrap());
        let want = want.as_array().unwrap();
        assert_eq!(rings.len(), want.len(), "{size}");
        for (ring, want) in rings.iter().zip(want) {
            assert!((ring.pen - want[0].as_f64().unwrap()).abs() < 1e-9, "{size}");
            assert_eq!(ring.alpha as u64, want[1].as_u64().unwrap(), "{size}");
            assert!((ring.inset - want[2].as_f64().unwrap()).abs() < 1e-9, "{size}");
        }
    }
    assert!((glow::breath(0) - 1.0).abs() < 1e-9);
    assert!((glow::breath(1400) - glow::LOW).abs() < 1e-9);
    assert!((glow::fade(0.0, 1.0, glow::FADE_MS) - 1.0).abs() < 1e-9);
    assert_eq!(glow::sample_screen(), ((1800, 1012), (28.0, 26.0)), "Python rounds 1012.5 to even");
}

struct Fixed;

impl Measure for Fixed {
    fn natural_width(&self, message: &Message) -> i32 {
        200 + 10 * message.people.len() as i32
    }
    fn height(&self, message: &Message, _width: i32) -> i32 {
        60 + 31 * message.people.len() as i32
    }
}

const SCREEN: Option<Area> = Some(Area { x: 0, y: 0, width: 1920, height: 1040 });

#[test]
fn result_rises_and_goes_after_eight_seconds() {
    let mut n = CornerNotice::new();
    let hits = vec![("示例坏人".to_string(), vec!["炸房".to_string()])];
    n.show_result(1_000, &hits, &["心动小鹿".into()], 0, SCREEN, &Fixed);
    assert_eq!(n.kind, Some(Kind::Hit));
    let cards = n.cards();
    assert_eq!(cards[0].spot, (1920 - 20 - 300, 1040 - 20 - 91));
    assert_eq!(cards[1].spot.1, cards[0].spot.1 - GAP - 91);
    assert_eq!(cards[0].pos, (cards[0].spot.0, cards[0].spot.1 + RISE), "starts below its place");
    assert!(!cards[1].visible, "嘉宾 waits a moment");
    n.tick(1_000 + NEXT_MS - 10);
    assert!(!n.cards()[1].visible);
    n.tick(1_000 + NEXT_MS);
    assert!(n.cards()[1].visible);
    assert_eq!(n.cards()[1].pos.1, n.cards()[1].spot.1 + GAP - 2, "the one above rises less");
    n.tick(1_000 + RISE_MS + NEXT_MS);
    assert_eq!(n.cards()[0].pos, n.cards()[0].spot);
    n.tick(5_000);
    assert!((n.cards()[0].left.unwrap() - 0.5).abs() < 1e-6, "the foot line is half gone at 4 s of 8");
    n.tick(1_000 + NOTICE_MS - 1);
    assert!(n.visible());
    n.tick(1_000 + NOTICE_MS);
    assert!(!n.visible());
}

#[test]
fn hover_holds_the_cards_and_click_closes() {
    let mut n = CornerNotice::new();
    n.show_missing(0, SCREEN, &Fixed);
    n.tick(3_000);
    n.hover(3_000, true);
    n.tick(30_000);
    assert!(n.visible(), "held while the pointer is over it");
    assert_eq!(n.remaining(30_000), 5_000);
    n.hover(30_000, false);
    n.tick(34_999);
    assert!(n.visible());
    n.tick(35_000);
    assert!(!n.visible());
    n.show_error(40_000, "截图失败", SCREEN, &Fixed);
    assert_eq!(n.cards()[0].message.title, "检查失败");
    assert_eq!(n.cards()[0].message.note, "截图失败");
    n.click();
    assert!(!n.visible());
}

#[test]
fn checking_waits_twenty_seconds_and_the_result_takes_its_place() {
    let mut n = CornerNotice::new();
    n.show_checking(0, SCREEN, &Fixed);
    assert_eq!(n.cards()[0].left, None, "no foot line while checking");
    n.tick(400);
    assert!(n.cards()[0].spin > 3.0, "the ring turns 0.32 a tick");
    n.tick(19_999);
    assert!(n.visible());
    n.show_result(10_000, &[], &[], 2, SCREEN, &Fixed);
    let card = &n.cards()[0];
    assert_eq!(card.message.title, "未发现黑名单");
    assert_eq!(card.message.note, "2 人未识别");
    assert_eq!(card.pos, card.spot, "already up: no second rise");
    assert_eq!(card.left, Some(1.0));
    n.tick(10_000 + NOTICE_MS);
    assert!(!n.visible());
    let mut fresh = CornerNotice::new();
    fresh.show_checking(0, SCREEN, &Fixed);
    fresh.tick(CHECKING_MS);
    assert!(!fresh.visible());
}

#[test]
fn toast_fades_and_keeps_its_action_while_fading() {
    let mut t = Toast::new();
    let id = t.show_message(0, "已删除「夜猫子」", "撤销", toast::TOAST_MS);
    assert_eq!(id, 1);
    assert!((t.opacity(75) - 0.5).abs() < 1e-6);
    t.tick(150);
    assert_eq!(t.opacity(200), 1.0);
    t.tick(4_000);
    assert!(t.visible(), "fading out");
    t.tick(4_100);
    assert!(t.act(), "撤销 still works while it fades");
    assert!(!t.visible());
    t.show_message(5_000, "已删除", "撤销", 20_000);
    t.drop_action(5_100);
    assert!(!t.act(), "the list changed under it: no 撤销");
    t.show_message(6_000, "已保存", "", toast::TOAST_MS);
    assert!(!t.has_action());
    t.tick(10_000);
    t.tick(10_150);
    assert!(!t.visible());
    assert_eq!(toast::place((900, 560), (180, 40)), (360, 480, 180, 40));
    assert_eq!(toast::place((220, 560), (400, 40)), (10, 480, 200, 40));
}

#[test]
fn listed_counts_the_rest() {
    let people = |n: usize| (0..n).map(|i| Person { name: format!("示例坏人{i}"), tags: vec![] }).collect::<Vec<_>>();
    assert_eq!(listed(people(5)).1, 0);
    assert_eq!(listed(people(6)).0.len(), 4);
    assert_eq!(listed(people(6)).1, 2);
    assert_eq!(Kind::from_name("nope"), Kind::Missing);
    assert_eq!(Message::new(Kind::Hit, "x", "").more_line(), "");
}
