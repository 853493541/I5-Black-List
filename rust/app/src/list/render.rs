//! The 黑名单 page drawn without a display, with the made-up lists tools/ui_shots.py seeds (normal, empty, stress),
//! for the side-by-side pictures in rust/app/shots/list/ and the test that every state renders.

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

use chrono::{Duration, Local};
use data::store::scans::{Scan, Seat};
use data::store::{Clock, Store};
use slint::platform::software_renderer::MinimalSoftwareWindow;
use slint::platform::WindowAdapter;
use slint::{ComponentHandle, PhysicalSize, Rgb8Pixel};
use serde_json::json;

use super::bind::Page;
use crate::ListWindow;

/// tools/ui_shots.py's seats: made-up names only.
pub const SEATS: [&str; 12] =
    ["小林同学", "白日梦想家", "路过的猫", "一只团子", "夏天的风", "心动小鹿", "晚风吹过", "摸鱼大师", "示例坏人", "心动星星", "柠檬汽水", "棉花糖"];

/// The page's logical size inside the 900 x 560 window: the window less the header and the page margins.
pub const SIZE: (u32, u32) = (900, 501);

/// A data folder of its own, seeded the way ui_shots._seed seeds `data` ("normal", "empty" or "stress").
pub fn seeded(data: &str) -> Store {
    static NEXT: AtomicUsize = AtomicUsize::new(0);
    let number = NEXT.fetch_add(1, Ordering::Relaxed);
    let root: PathBuf = std::env::temp_dir().join(format!("list-shots-{}-{number}-{data}", std::process::id()));
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir_all(&root).expect("a data folder");
    let mut store = Store::open(Some(root), Clock::default());
    if data == "empty" {
        return store;
    }
    let tags = |list: &[&str]| list.iter().map(|tag| tag.to_string()).collect::<Vec<_>>();
    for (name, own, reason) in [
        ("示例坏人", tags(&["炸房"]), "开局就退，三把了"),
        ("路过的捣蛋鬼", tags(&["场外", "挂机"]), "场外报点，还在频道里骂人"),
        ("一个名字特别特别长的玩家", tags(&["送人头"]), ""),
        ("夜猫子", tags(&[]), "约好的车不来"),
        ("小透明", tags(&["挂机"]), "全程挂机不动，一句话也不说，这是一段很长的原因，看看表格会不会把它截断"),
    ] {
        store.add(name, reason, &own).expect("add");
    }
    let seats: Vec<Seat> = SEATS
        .iter()
        .enumerate()
        .map(|(i, name)| Seat { seat: i as i64 + 1, name: name.to_string(), unclear: *name == "摸鱼大师" })
        .collect();
    store.add_scan(&seats, Some(0.31));
    if data == "stress" {
        store.add_custom_tag("不尊重底牌还骂人");
        for number in 1..124 {
            let name = if number % 9 != 0 { format!("测试玩家{number:03}") } else { format!("一个名字特别长的测试玩家{number:03}") };
            let own = if number % 3 == 0 {
                tags(&[])
            } else if number % 7 == 0 {
                tags(&["炸房", "挂机", "不尊重底牌还骂人"])
            } else {
                tags(&["场外"])
            };
            let reason = if number % 4 == 0 { "原因写得很长很长，看看在表格里会不会把别的列挤歪" } else { "" };
            store.add(&name, reason, &own).expect("add");
        }
        let now = Local::now().fixed_offset();
        store.scans = (0..40)
            .map(|index: i64| Scan {
                at: (now - Duration::hours(index * 7) - Duration::minutes(index * 3)).format("%Y-%m-%dT%H:%M:%S%:z").to_string(),
                elapsed: json!(0.3),
                names: (0..12)
                    .map(|i: i64| {
                        let read = (i + index) % 5 != 0;
                        Seat { seat: i + 1, name: if read { format!("测试玩家{:03}", i + 1) } else { String::new() }, unclear: !read }
                    })
                    .collect(),
            })
            .collect();
    }
    store
}

/// Draw the page for each of `cases` (data, dark) into `dir`/rust-<data>[-dark].png at `scale`; the picture sizes.
pub fn render(dir: &Path, cases: &[(&str, bool)], scale: f32) -> Result<Vec<(u32, u32)>, Box<dyn std::error::Error>> {
    std::fs::create_dir_all(dir)?;
    crate::shots::init();
    let (width, height) = ((SIZE.0 as f32 * scale) as u32, (SIZE.1 as f32 * scale) as u32);
    let mut sizes = Vec::new();
    for (data, dark) in cases {
        let ui = ListWindow::new()?;
        let window = crate::shots::newest();
        window.dispatch_event(slint::platform::WindowEvent::ScaleFactorChanged { scale_factor: scale });
        window.set_size(PhysicalSize::new(width, height));
        ui.set_dark(*dark);
        ui.show()?;
        let store = seeded(data);
        let page = Page::new(&ui);
        // Twice: the first lays the table out, so the second knows its width for the columns and the +N pills.
        page.refresh(&ui, &store);
        draw(&window, width, height);
        page.refresh(&ui, &store);
        let buffer = draw(&window, width, height);
        let name = format!("rust-{data}{}.png", if *dark { "-dark" } else { "" });
        save(&dir.join(name), &buffer, width, height)?;
        sizes.push((width, height));
        ui.hide()?;
        let _ = std::fs::remove_dir_all(&store.root);
    }
    Ok(sizes)
}

fn draw(window: &MinimalSoftwareWindow, width: u32, height: u32) -> Vec<Rgb8Pixel> {
    window.request_redraw();
    let mut buffer = vec![Rgb8Pixel::new(0, 0, 0); (width * height) as usize];
    window.draw_if_needed(|renderer| {
        renderer.render(&mut buffer, width as usize);
    });
    buffer
}

fn save(path: &Path, buffer: &[Rgb8Pixel], width: u32, height: u32) -> Result<(), Box<dyn std::error::Error>> {
    let file = std::io::BufWriter::new(std::fs::File::create(path)?);
    let mut encoder = png::Encoder::new(file, width, height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    let bytes: Vec<u8> = buffer.iter().flat_map(|pixel| [pixel.r, pixel.g, pixel.b]).collect();
    encoder.write_header()?.write_image_data(&bytes)?;
    Ok(())
}
