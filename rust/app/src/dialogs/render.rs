//! Every dialog drawn without a display, with made-up data at its tallest: each must draw, and each card must fit
//! 672 px of usable height (1080p at 150 %) with its buttons in view, as tests/test_dialog_fit.py asks of the
//! Python ones. With DIALOG_SHOTS=<dir> the pictures are saved there at scale 1.5 (rust/app/shots/dialogs).

use std::cell::RefCell;
use std::path::Path;
use std::rc::Rc;

use data::import::{ImportRow, Status, TagSuggestion};
use slint::platform::software_renderer::{MinimalSoftwareWindow, RepaintBufferType};
use slint::platform::{Platform, WindowAdapter, WindowEvent};
use slint::{ComponentHandle, ModelRc, PhysicalSize, Rgb8Pixel, VecModel};

use super::models::{self, NAME_TAG_ROOM};
use super::trim::{self, Strip};
use crate::*;

/// The room Windows leaves on 1080p at 150 %, and the card's shadow above and below it (Modal's margins).
const SHORT: f32 = 672.0;
const SHADOW: f32 = 44.0;
const SCALE: f32 = 1.5;

thread_local! {
    static LAST: RefCell<Option<Rc<MinimalSoftwareWindow>>> = const { RefCell::new(None) };
}

struct Headless;

impl Platform for Headless {
    fn create_window_adapter(&self) -> Result<Rc<dyn WindowAdapter>, slint::PlatformError> {
        let window = MinimalSoftwareWindow::new(RepaintBufferType::NewBuffer);
        LAST.with(|last| *last.borrow_mut() = Some(window.clone()));
        Ok(window)
    }
}

/// Draw the dialog's window at 900 x 560 logical (taller if its card needs it), save it when asked, and return
/// its card's height with the shadow.
fn draw(ui: &impl ComponentHandle, card: f32, name: &str) -> f32 {
    let window = LAST.with(|last| last.borrow().clone()).expect("a window");
    window.dispatch_event(WindowEvent::ScaleFactorChanged { scale_factor: SCALE });
    let tall = 560.0f32.max(card + SHADOW);
    let size = PhysicalSize::new((900.0 * SCALE) as u32, (tall * SCALE).round() as u32);
    window.set_size(size);
    ui.show().expect("shown");
    let mut buffer = vec![Rgb8Pixel::new(0, 0, 0); (size.width * size.height) as usize];
    window.request_redraw();
    let drawn = window.draw_if_needed(|renderer| {
        renderer.render(&mut buffer, size.width as usize);
    });
    assert!(drawn, "{name} drew nothing");
    assert!(buffer.iter().any(|pixel| *pixel != buffer[0]), "{name} is blank");
    if let Ok(dir) = std::env::var("DIALOG_SHOTS") {
        save(&Path::new(&dir).join(format!("{name}.png")), &buffer, size).expect("saved");
    }
    ui.hide().expect("hidden");
    card + SHADOW
}

fn save(path: &Path, buffer: &[Rgb8Pixel], size: PhysicalSize) -> Result<(), Box<dyn std::error::Error>> {
    std::fs::create_dir_all(path.parent().expect("a folder"))?;
    let file = std::io::BufWriter::new(std::fs::File::create(path)?);
    let mut encoder = png::Encoder::new(file, size.width, size.height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    let bytes: Vec<u8> = buffer.iter().flat_map(|pixel| [pixel.r, pixel.g, pixel.b]).collect();
    encoder.write_header()?.write_image_data(&bytes)?;
    Ok(())
}

fn strings(items: &[&str]) -> Vec<String> {
    items.iter().map(|item| item.to_string()).collect()
}

fn row(name: &str, tags: &[&str], reason: &str, status: Status) -> ImportRow {
    let checked = !matches!(status, Status::Same | Status::Odd | Status::Elsewhere);
    ImportRow { name: name.into(), tags: strings(tags), reason: reason.into(), status, target: -1, checked }
}

fn add_name(edit: bool, tall: bool) -> f32 {
    let ui = AddNameDialog::new().expect("built");
    let mut catalog = strings(&["炸房", "贴脸", "挂机", "场外", "不尊重底牌", "送人头"]);
    if tall {
        catalog.extend(strings(&["开局就退", "骂人", "演员", "秒倒", "不救人", "乱标点", "卡模型", "挂机很久"]));
        ui.set_name_error("已经在黑名单里了".into());
    }
    let tags = if edit { strings(&["挂机", "场外"]) } else { Vec::new() };
    ui.set_tag_lines(models::tag_lines(&models::name_chips(&catalog, &tags), NAME_TAG_ROOM));
    if edit {
        ui.set_heading("编辑".into());
        ui.set_allow_delete(true);
        ui.set_name("路过的捣蛋鬼".into());
        ui.set_detail("场外报点，还在频道里骂人".into());
    }
    let name = match (edit, tall) {
        (_, true) => "add-tall",
        (true, _) => "edit",
        _ => "add",
    };
    draw(&ui, ui.get_card_height(), name)
}

fn batch(rows: &[ImportRow], name: &str) -> f32 {
    let ui = BatchAddDialog::new().expect("built");
    ui.set_text("示例坏人（炸房，开局就退）\n路过的捣蛋鬼 场外\n心动星星".into());
    ui.set_rows(models::preview_rows(rows));
    ui.set_count(models::checked_count(rows));
    if rows.is_empty() {
        ui.set_error("没有读到名字".into());
    }
    draw(&ui, ui.get_card_height(), name)
}

fn suggest(people: usize) -> f32 {
    let ui = TagSuggestDialog::new().expect("built");
    let suggestions = vec![
        TagSuggestion { tag: "开局就退".into(), existing: false, rows: vec![0, 1] },
        TagSuggestion { tag: "炸房".into(), existing: true, rows: vec![0] },
    ];
    let names = ["示例坏人", "路过的捣蛋鬼", "心动小鹿", "心动星星", "一起开黑的朋友", "柠檬汽水", "夏天的风", "一只团子"];
    let records: Vec<data::import::Record> = names[..people]
        .iter()
        .enumerate()
        .map(|(index, name)| (name.to_string(), if index == 0 { strings(&["炸房"]) } else { Vec::new() }, "开局就退".into(), -1))
        .collect();
    let on = strings(&["开局就退", "炸房"]);
    ui.set_new_tags(models::suggestion_lines(&suggestions, &on, false));
    ui.set_old_tags(models::suggestion_lines(&suggestions, &on, true));
    ui.set_people(models::people_rows(&records, &suggestions, &on));
    draw(&ui, ui.get_card_height(), if people > 6 { "suggest-tall" } else { "suggest" })
}

fn flow() -> f32 {
    let ui = FlowReportDialog::new().expect("built");
    let step = |key: &str, words: &str, seconds: f64| (key.to_string(), words.to_string(), seconds);
    let hotkey = [step("capture", "截屏", 0.07), step("find", "找名单", 0.04), step("read", "读名字", 0.06)];
    let auto = [step("glance", "发现大厅", 0.12), step("capture", "截屏", 0.08), step("find", "找名单", 0.05), step("read", "读名字", 0.07)];
    let bars = vec![models::flow_bar("手动检查（快捷键）", &hotkey, 0.32), models::flow_bar("自动检查", &auto, 0.32)];
    ui.set_headline("检查一次约 0.2 秒，正常".into());
    ui.set_bars(ModelRc::new(VecModel::from(bars)));
    ui.set_facts("识别用 显卡 · 屏幕 3840×2160 · CPU 21%（本工具 4%） · 示例名字读对 11/12".into());
    ui.set_causes("· 屏幕很大，截屏和找名单要多花时间\n· 别的程序占用了不少 CPU".into());
    draw(&ui, ui.get_card_height(), "flow")
}

fn sound_trim() -> f32 {
    let ui = SoundTrimDialog::new().expect("built");
    let samples: Vec<i16> = (0..20 * 44100)
        .map(|i| {
            let t = i as f64 / 44100.0;
            ((t * 2.0 * std::f64::consts::PI * 3.0).sin() * (t * 2.0 * std::f64::consts::PI * 440.0).sin() * 12000.0) as i16
        })
        .collect();
    let strip = Strip::new(20.0, trim::LIMIT_S);
    let found = trim::scaled(&trim::peaks(&samples, (trim::W - 2.0 * trim::INSET) as usize));
    ui.set_file_name("心动音乐.mp3".into());
    ui.set_peaks(ModelRc::new(VecModel::from(found)));
    ui.set_duration(strip.duration as f32);
    ui.set_start(strip.start as f32);
    ui.set_length(strip.length as f32);
    ui.set_playhead(0.2);
    ui.set_running(true);
    ui.set_where(format!("{} / {}", trim::clock(0.2), trim::clock(strip.duration)).into());
    draw(&ui, ui.get_card_height(), "trim")
}

#[test]
fn every_dialog_draws_and_fits_a_short_screen_with_its_buttons() {
    let _ = slint::platform::set_platform(Box::new(Headless));
    let mut heights: Vec<(&str, f32)> = vec![
        ("add", add_name(false, false)),
        ("edit", add_name(true, false)),
        ("add-tall", add_name(false, true)),
        ("batch-empty", batch(&[], "batch-empty")),
    ];
    let mut rows = vec![
        row("示例坏人", &["炸房"], "开局就退", Status::New),
        row("路过的捣蛋鬼", &["场外"], "", Status::Merge),
        row("心动星星", &[], "", Status::Elsewhere),
    ];
    heights.push(("batch", batch(&rows, "batch")));
    rows.extend((0..30).map(|n| row(&format!("示例坏人{n}"), &["挂机", "场外"], "很长很长的一段原因", Status::Odd)));
    heights.push(("batch-tall", batch(&rows, "batch-tall")));
    heights.push(("suggest", suggest(2)));
    heights.push(("suggest-tall", suggest(8)));
    let confirm = ConfirmDialog::new().expect("built");
    confirm.set_heading("清空黑名单".into());
    confirm.set_body("黑名单里的 3 人都会删掉。可以在 设置 › 恢复备份 里找回。".into());
    confirm.set_confirm("清空".into());
    heights.push(("confirm", draw(&confirm, confirm.get_card_height(), "confirm")));
    let disclaimer = DisclaimerDialog::new().expect("built");
    heights.push(("disclaimer", draw(&disclaimer, disclaimer.get_card_height(), "disclaimer")));
    let guide = GuideDialog::new().expect("built");
    guide.set_how("在「推演成功」大厅按 Alt+1 检查".into());
    heights.push(("guide", draw(&guide, guide.get_card_height(), "guide")));
    for which in ["display", "stream"] {
        let pictures = PictureGuideDialog::new().expect("built");
        pictures.set_which(which.into());
        heights.push((which, draw(&pictures, pictures.get_card_height(), which)));
    }
    heights.push(("flow", flow()));
    heights.push(("trim", sound_trim()));
    let wave = SoundWaveView::new().expect("built");
    draw(&wave, 0.0, "soundwave");
    for (name, height) in heights {
        // A card is at least its title and its footer; all of it, buttons included, within the screen.
        assert!(height > SHADOW + 100.0, "{name} has no card: {height}");
        assert!(height <= SHORT - 8.0, "{name} is {height} px tall with its shadow, past {}", SHORT - 8.0);
    }
}
