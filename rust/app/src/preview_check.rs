//! Hooks for the automatic preview check on GitHub's Windows runners (.github/workflows/rust-preview-check.yml,
//! docs/dev/preview-check.md). Neither opens a window nor makes a sound; both run before the app's own start.
//!
//! - `--shots <dir>`: every page and dialog drawn without a display, with ui_shots' made-up data, at the Windows
//!   scale in `BLACKLIST_DETECT_SCALE` (1.25 for 125 %, default 1.5), saved as `<dir>/<name>.png` under
//!   tools/ui_shots.py's names (page_记录, dlg_添加黑名单, ...), so the check can put each beside Python's.
//! - `--bench-check <dir> [<list>]`: every .jpg in `<dir>` read by one checker as a first check reads it (no spot kept),
//!   in code-point name order, a `FILE\t<file name>` line and then one line each on stdout
//!   (`<ms>\t<header 0/1>\t<seats flagged, comma-separated>\t<seat names, tab-separated>`), then `DONE`; the process waits for a line on stdin before it
//!   ends, so the harness can read its CPU time and memory first.

use std::cell::RefCell;
use std::io::BufRead;
use std::path::Path;
use std::rc::Rc;
use std::time::Instant;

use slint::platform::WindowEvent;

use crate::list::ListAction;
use crate::ui_app::MainUi;
use crate::ui_events::{Dialog, UiEvent};

/// The window, in logical pixels (ui_shots' --size), and the room the tallest dialogs get (672 at 150 %).
const SIZE: (f32, f32) = (900.0, 560.0);
const TALL: f32 = 672.0;

/// The scale `BLACKLIST_DETECT_SCALE` asks for (1.25, or 125), else 1.5.
pub fn scale() -> f32 {
    let asked = std::env::var("BLACKLIST_DETECT_SCALE").ok().and_then(|value| value.trim().parse::<f32>().ok());
    match asked {
        Some(value) if value > 4.0 => value / 100.0,
        Some(value) if value > 0.0 => value,
        _ => 1.5,
    }
}

pub fn shots(dir: &Path) -> Result<usize, Box<dyn std::error::Error>> {
    std::fs::create_dir_all(dir)?;
    let scale = scale();
    crate::shots::init();
    let mut seeded = seeded()?;
    seeded.likes = crate::history::tests_seed_likes();
    let root = seeded.root.clone();
    let store = Rc::new(RefCell::new(seeded));
    let ui = MainUi::new(store.clone(), "1.0.1")?;
    let mut saved = 0;
    for (page, name) in ["记录", "黑名单", "嘉宾", "设置_常规"].iter().enumerate() {
        ui.window.set_page(page as i32);
        ui.refresh();
        let picture = crate::shots::draw(&ui.window, SIZE, scale)?;
        crate::shots::save(&dir.join(format!("page_{name}.png")), &picture)?;
        saved += 1;
    }
    let has_guest = !store.borrow().likes.is_empty();
    let has_combo = !store.borrow().combos.is_empty();
    let has_entry = !store.borrow().entries.is_empty();
    let dialogs: Vec<(&str, Option<Dialog>, f32)> = vec![
        ("dlg_添加黑名单", Some(Dialog::AddName { tag: String::new() }), SIZE.1),
        ("dlg_编辑黑名单", has_entry.then_some(Dialog::EditName(0)), SIZE.1),
        ("dlg_批量导入", Some(Dialog::BatchAdd), SIZE.1),
        ("dlg_清空黑名单", None, SIZE.1),
        ("dlg_添加嘉宾", Some(Dialog::Guest(None)), TALL),
        ("dlg_编辑嘉宾", has_guest.then_some(Dialog::Guest(Some(0))), TALL),
        ("dlg_我的场景", Some(Dialog::EditMe), TALL),
        ("dlg_添加组合", Some(Dialog::Combo(None)), TALL),
        ("dlg_编辑组合", has_combo.then_some(Dialog::Combo(Some(0))), TALL),
        ("dlg_场景管理", Some(Dialog::SceneManager), TALL),
        ("dlg_显示说明", Some(Dialog::DisplayGuide), SIZE.1),
        ("dlg_直播模式说明", Some(Dialog::StreamGuide), SIZE.1),
        ("dlg_使用声明", Some(Dialog::Disclaimer), SIZE.1),
    ];
    for (name, dialog, height) in dialogs {
        let before = Rc::as_ptr(&crate::shots::newest());
        match dialog {
            Some(dialog) => ui.open(dialog),
            None if name == "dlg_清空黑名单" => {
                ui.bus.send(UiEvent::List(ListAction::AskClear));
                ui.pump();
            }
            None => {
                eprintln!("{name}: no data for it; skipped");
                continue;
            }
        }
        let window = crate::shots::newest();
        if Rc::as_ptr(&window) == before {
            eprintln!("{name}: no window opened; skipped");
            continue;
        }
        window.dispatch_event(WindowEvent::ScaleFactorChanged { scale_factor: scale });
        let picture = crate::shots::draw_window(&window, (SIZE.0 * scale).round() as u32, (height * scale).round() as u32);
        crate::shots::save(&dir.join(format!("{name}.png")), &picture)?;
        saved += 1;
    }
    let _ = std::fs::remove_dir_all(root);
    Ok(saved)
}

pub fn bench(dir: &Path, list: Option<&Path>) -> Result<(), Box<dyn std::error::Error>> {
    // A made-up 黑名单, one name a line (the check's own list, built on the runner; never shipped).
    let blacklist: Vec<lobby::Entry> = match list {
        Some(path) => std::fs::read_to_string(path)?
            .lines()
            .filter(|line| !line.trim().is_empty())
            .map(|name| lobby::Entry { name: name.to_string(), ..lobby::Entry::default() })
            .collect(),
        None => Vec::new(),
    };
    let mut images: Vec<_> = std::fs::read_dir(dir)?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.extension().is_some_and(|ext| ext.eq_ignore_ascii_case("jpg")))
        .collect();
    images.sort();
    let install = app::wiring::startup::install_root();
    let dirs = pipeline::ModelDirs::find(&app::wiring::startup::model_roots(install.as_deref())).ok_or("no OCR models")?;
    let env = pipeline::runtime(&app::wiring::engine::ort_library(install.as_deref())).map_err(|e| e.to_string())?;
    let mut checker = pipeline::Checker::new(env, &dirs, common::paths::ocr_threads()).map_err(|e| e.to_string())?;
    println!("READY\t{}", images.len());
    for image in images {
        let bytes = opencv::core::Vector::<u8>::from_slice(&std::fs::read(&image)?);
        let bgr = opencv::imgcodecs::imdecode(&bytes, opencv::imgcodecs::IMREAD_COLOR)?;
        let mut rgb = opencv::core::Mat::default();
        opencv::imgproc::cvt_color_def(&bgr, &mut rgb, opencv::imgproc::COLOR_BGR2RGB)?;
        checker.spot = None;
        println!("FILE\t{}", image.file_name().map(|name| name.to_string_lossy()).unwrap_or_default());
        let start = Instant::now();
        let result = checker.check(&[rgb], &blacklist, &[], None).map_err(|e| e.to_string())?;
        let ms = start.elapsed().as_secs_f64() * 1000.0;
        let names: Vec<String> = result.names.iter().map(|slot| slot.raw.replace(['\t', '\n'], " ")).collect();
        let hits: Vec<String> = result.hits.iter().map(|hit| hit.index.to_string()).collect();
        println!("{ms:.1}\t{}\t{}\t{}", u8::from(result.header_found), hits.join(","), names.join("\t"));
    }
    println!("DONE");
    let _ = std::io::stdin().lock().lines().next();
    Ok(())
}

/// ui_shots' "normal" data (list/render.rs's seeded, which only tests build): five 黑名单 and one check of the
/// made-up seats, in a data folder of its own.
fn seeded() -> Result<data::store::Store, Box<dyn std::error::Error>> {
    use data::store::scans::Seat;
    const SEATS: [&str; 12] =
        ["小林同学", "白日梦想家", "路过的猫", "一只团子", "夏天的风", "心动小鹿", "晚风吹过", "摸鱼大师", "示例坏人", "心动星星", "柠檬汽水", "棉花糖"];
    let root = std::env::temp_dir().join(format!("preview-check-shots-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir_all(&root)?;
    let mut store = data::store::Store::open(Some(root), data::store::Clock::default());
    let tags = |list: &[&str]| list.iter().map(|tag| tag.to_string()).collect::<Vec<_>>();
    for (name, own, reason) in [
        ("示例坏人", tags(&["炸房"]), "开局就退，三把了"),
        ("路过的捣蛋鬼", tags(&["场外", "挂机"]), "场外报点，还在频道里骂人"),
        ("一个名字特别特别长的玩家", tags(&["送人头"]), ""),
        ("夜猫子", tags(&[]), "约好的车不来"),
        ("小透明", tags(&["挂机"]), "全程挂机不动，一句话也不说，这是一段很长的原因，看看表格会不会把它截断"),
    ] {
        store.add(name, reason, &own).map_err(|e| format!("{e:?}"))?;
    }
    let seats: Vec<Seat> = SEATS
        .iter()
        .enumerate()
        .map(|(i, name)| Seat { seat: i as i64 + 1, name: name.to_string(), unclear: *name == "摸鱼大师" })
        .collect();
    store.add_scan(&seats, Some(0.31));
    Ok(store)
}
