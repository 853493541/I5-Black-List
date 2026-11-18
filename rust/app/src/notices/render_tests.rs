//! Every notice window drawn without a display at scale 1.5, and the update dialog's fit in 672 px.
//! NOTICES_SHOTS=<dir> also saves the pictures there.

use slint::platform::software_renderer::MinimalSoftwareWindow;
use slint::ComponentHandle;

use super::corner::{result_messages, Message};
use super::queue::Measure;
use super::render::{draw, init, last_window, save, Picture};
use super::update::{UpdateDialog, UpdateOffer};
use super::view::{fill_notice, fill_offer, fill_toast, fill_update};
use crate::{NoticeWindow, ToastWindow, UpdateDialogWindow, UpdateOfferWindow};
use data::update::Release;

/// The usable height of a 1080p screen at 150 % (tests/test_dialog_fit.py).
const USABLE: f32 = 672.0;

fn keep(picture: &Picture, name: &str) {
    assert!(picture.width > 0 && picture.height > 0, "{name}");
    let first = picture.pixels[0];
    assert!(picture.pixels.iter().any(|p| *p != first), "{name} has something drawn");
    if let Ok(dir) = std::env::var("NOTICES_SHOTS") {
        save(picture, &std::path::Path::new(&dir).join(format!("{name}.png"))).expect("saved");
    }
}

/// The notice window measures its own words. Slint makes a card's optional parts (the note, the
/// names) only when it is drawn, so it is drawn once before it is measured.
struct Slint<'a>(&'a NoticeWindow, &'a MinimalSoftwareWindow);

impl Slint<'_> {
    fn settle(&self, message: &Message, width: f32) {
        fill_notice(self.0, message, Some(1.0), 0.0);
        self.0.set_card_width(width);
        draw(self.0, self.1, (width, 600.0));
    }
}

impl Measure for Slint<'_> {
    fn natural_width(&self, message: &Message) -> i32 {
        self.settle(message, 440.0);
        self.0.get_natural_width().round() as i32
    }
    fn height(&self, message: &Message, width: i32) -> i32 {
        self.settle(message, width as f32);
        self.0.get_natural_height().round() as i32
    }
}

#[test]
fn notice_cards_draw() {
    init();
    let ui = NoticeWindow::new().unwrap();
    let window = last_window();
    let hits = vec![("示例坏人".to_string(), vec!["炸房".to_string()])];
    let likes = vec!["心动小鹿".to_string(), "心动星星".to_string()];
    let mut all: Vec<(String, Message, Option<f32>)> = Vec::new();
    for (index, message) in result_messages(&hits, &likes, 1).into_iter().enumerate() {
        all.push((format!("notice_{index}"), message, Some(1.0)));
    }
    all.push(("notice_clear".into(), result_messages(&[], &[], 0).remove(0), Some(0.6)));
    all.push(("notice_checking".into(), Message::checking(), None));
    all.push(("notice_missing".into(), Message::missing(), Some(1.0)));
    all.push(("notice_error".into(), Message::error("截图失败，等会儿再试"), Some(1.0)));
    let many: Vec<(String, Vec<String>)> = (0..7).map(|i| (format!("示例坏人{i}"), vec!["炸房".into(), "挂机".into()])).collect();
    all.push(("notice_many".into(), result_messages(&many, &[], 0).remove(0), Some(1.0)));
    let measure = Slint(&ui, &window);
    for (name, message, left) in all {
        let width = measure.natural_width(&message).clamp(300, 440);
        let height = measure.height(&message, width);
        assert!(height >= 58, "{name} is at least its title tall: {height}");
        fill_notice(&ui, &message, left, 0.8);
        keep(&draw(&ui, &window, (width as f32, height as f32)), &name);
    }
}

#[test]
fn toast_draws() {
    init();
    let ui = ToastWindow::new().unwrap();
    let window = last_window();
    fill_toast(&ui, "已删除「夜猫子」", "撤销", false);
    keep(&draw(&ui, &window, (900.0, 560.0)), "toast");
    fill_toast(&ui, "已保存", "", true);
    keep(&draw(&ui, &window, (900.0, 560.0)), "toast_dark");
}

fn release(base: &str, notes: &[&str]) -> Release {
    Release {
        version: "v0.8.7".into(),
        url: String::new(),
        sha256: String::new(),
        size: 41_200_000,
        base: base.into(),
        notes: notes.iter().map(|n| n.to_string()).collect(),
        mirror: String::new(),
        mirrors: Vec::new(),
    }
}

const NOTES: [&str; 3] = ["花边铺满整个游戏", "卡片跟着游戏大小", "检查更快"];

#[test]
fn update_dialog_draws_in_every_state_and_fits() {
    init();
    let ui = UpdateDialogWindow::new().unwrap();
    let window = last_window();
    let mut downloading = UpdateDialog::new(&release("v0.8.0", &NOTES), "v0.8.6", false);
    downloading.start(None);
    downloading.progress(2, 5);
    let mut failed = UpdateDialog::new(&release("v0.8.0", &NOTES), "v0.8.6", false);
    failed.start(None);
    failed.failed("下载失败，等会儿再试");
    let mut restarting = UpdateDialog::new(&release("v0.8.0", &NOTES), "v0.8.6", false);
    restarting.done();
    let full = UpdateDialog::new(&release("v0.9.0", &NOTES), "v0.8.6", false);
    let source = UpdateDialog::new(&release("v0.8.0", &NOTES), "v0.8.6", true);
    // The longest notes a release may have: three lines, more than the rules allow, still fit.
    let long: Vec<String> = (0..12).map(|i| format!("第 {i} 条：检查更快，检查时游戏更流畅")).collect();
    let long_notes: Vec<&str> = long.iter().map(String::as_str).collect();
    let mut tall = UpdateDialog::new(&release("v0.9.0", &long_notes), "v0.8.6", false);
    tall.status = "这次要下载完整安装包，名单和设置不会丢".into();
    for (name, dialog) in [
        ("update_downloading", &downloading),
        ("update_failed", &failed),
        ("update_restarting", &restarting),
        ("update_full", &full),
        ("update_source", &source),
        ("update_tall", &tall),
    ] {
        fill_update(&ui, dialog, false);
        let picture = draw(&ui, &window, (900.0, 560.0));
        let height = ui.get_card_height();
        assert!(height <= USABLE, "{name}: {height} px is taller than {USABLE}");
        keep(&picture, name);
    }
    fill_update(&ui, &failed, true);
    keep(&draw(&ui, &window, (900.0, 560.0)), "update_failed_dark");
}

#[test]
fn update_offer_draws() {
    init();
    let ui = UpdateOfferWindow::new().unwrap();
    let window = last_window();
    fill_offer(&ui, &UpdateOffer::new(&release("v0.8.0", &NOTES)), false);
    let height = ui.window().size().height as f32 / ui.window().scale_factor();
    keep(&draw(&ui, &window, (340.0, height.max(160.0))), "update_offer");
}
