//! The main window without a display: Slint's software renderer at a Windows scale, saved as PNG, and the
//! side-by-side pictures (Python left, Rust right) in rust/app/shots/shell/.

use std::path::{Path, PathBuf};

use slint::platform::{WindowAdapter, WindowEvent};
use slint::{ComponentHandle, PhysicalSize, Rgb8Pixel};

use super::{apply, Page, ShellModel, StreamState, Tone};
use crate::MainWindow;

type Error = Box<dyn std::error::Error>;

/// An RGB picture.
pub struct Picture {
    pub width: u32,
    pub height: u32,
    pub rgb: Vec<u8>,
}

/// The window as tools/ui_shots.py seeds it: the counts, 读不到游戏画面 (no game on a headless screen), 测试主播,
/// 检查 on Alt+F11 in 完整模式 and 手动.
pub fn demo_model() -> ShellModel {
    ShellModel {
        page: Page::History,
        blacklist_count: 5,
        guests_count: 3,
        status_text: "读不到游戏画面".into(),
        tone: Tone::Hit,
        status_key: String::new(),
        status_tip: String::new(),
        has_update: false,
        player_name: "测试主播".into(),
        safe_mode: false,
        auto_capture: false,
        hotkey: "Alt+F11".into(),
        hotkey_waiting: false,
        hotkey_note: String::new(),
        stream_on: false,
        stream: None,
        dark: false,
        version: "1.2.0".into(),
    }
}

/// One picture of the window: the model, the panel open or not, at `scale` (1.5 for Windows' 150%), `size` logical.
pub struct Shot {
    pub name: &'static str,
    pub model: ShellModel,
    pub panel_open: bool,
}

/// The shots ui_shots.py takes of the frame, by its file names (without the number).
pub fn shots() -> Vec<Shot> {
    let mut list = Vec::new();
    for page in Page::ALL {
        let name = ["page_记录", "page_黑名单", "page_嘉宾", "page_设置_常规"][page as usize];
        list.push(Shot { name, model: ShellModel { page, ..demo_model() }, panel_open: false });
    }
    list.push(Shot { name: "header_检查", model: demo_model(), panel_open: true });
    let streaming = ShellModel {
        stream_on: true,
        stream: Some(StreamState { words: "「直播画面」被游戏挡住了，置顶后切换一次直播姬场景".into(), ok: false }),
        ..demo_model()
    };
    list.push(Shot { name: "header_检查_直播模式", model: streaming, panel_open: true });
    list.push(Shot { name: "header_有更新", model: ShellModel { has_update: true, ..demo_model() }, panel_open: false });
    list
}

/// Draws one shot. The first call on a thread sets Slint's platform to this headless one.
pub fn draw(shot: &Shot, scale: f32, size: (u32, u32)) -> Result<Picture, Error> {
    crate::shots::init();
    let ui = MainWindow::new()?;
    let window = crate::shots::newest();
    apply(&ui, &shot.model);
    ui.set_panel_open(shot.panel_open);
    let (width, height) = ((size.0 as f32 * scale).round() as u32, (size.1 as f32 * scale).round() as u32);
    window.dispatch_event(WindowEvent::ScaleFactorChanged { scale_factor: scale });
    window.set_size(PhysicalSize::new(width, height));
    ui.show()?;
    window.request_redraw();
    let mut buffer = vec![Rgb8Pixel::new(0, 0, 0); (width * height) as usize];
    window.draw_if_needed(|renderer| {
        renderer.render(&mut buffer, width as usize);
    });
    ui.hide()?;
    let rgb = buffer.iter().flat_map(|pixel| [pixel.r, pixel.g, pixel.b]).collect();
    Ok(Picture { width, height, rgb })
}

pub fn save(path: &Path, picture: &Picture) -> Result<(), Error> {
    let file = std::io::BufWriter::new(std::fs::File::create(path)?);
    let mut encoder = png::Encoder::new(file, picture.width, picture.height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    encoder.write_header()?.write_image_data(&picture.rgb)?;
    Ok(())
}

/// Reads a PNG as RGB (ui_shots.py writes RGB or RGBA).
pub fn load(path: &Path) -> Result<Picture, Error> {
    let mut decoder = png::Decoder::new(std::io::BufReader::new(std::fs::File::open(path)?));
    decoder.set_transformations(png::Transformations::EXPAND | png::Transformations::STRIP_16);
    let mut reader = decoder.read_info()?;
    let mut data = vec![0; reader.output_buffer_size()];
    let info = reader.next_frame(&mut data)?;
    let channels = info.color_type.samples();
    let rgb = data[..info.buffer_size()]
        .chunks(channels)
        .flat_map(|px| if channels >= 3 { [px[0], px[1], px[2]] } else { [px[0], px[0], px[0]] })
        .collect();
    Ok(Picture { width: info.width, height: info.height, rgb })
}

/// Python on the left, Rust on the right, 16 px of gray between.
pub fn side_by_side(left: &Picture, right: &Picture) -> Picture {
    let gap = 16;
    let width = left.width + gap + right.width;
    let height = left.height.max(right.height);
    let mut rgb = vec![160u8; (width * height * 3) as usize];
    for (picture, x0) in [(left, 0), (right, left.width + gap)] {
        for y in 0..picture.height {
            let from = (y * picture.width * 3) as usize;
            let to = ((y * width + x0) * 3) as usize;
            let row = (picture.width * 3) as usize;
            rgb[to..to + row].copy_from_slice(&picture.rgb[from..from + row]);
        }
    }
    Picture { width, height, rgb }
}

/// Every shot at 150%, as `<dir>/<name>.png`; with `python` (a ui_shots.py folder) also `<dir>/<name>_side.png`.
pub fn render_all(dir: &Path, python: Option<&Path>) -> Result<Vec<PathBuf>, Error> {
    std::fs::create_dir_all(dir)?;
    let mut written = Vec::new();
    for shot in shots() {
        let picture = draw(&shot, 1.5, super::MIN_SIZE)?;
        let path = dir.join(format!("{}.png", shot.name));
        save(&path, &picture)?;
        written.push(path);
        let Some(python) = python else { continue };
        let suffix = format!("_{}.png", shot.name);
        let found = std::fs::read_dir(python)?
            .filter_map(Result::ok)
            .map(|entry| entry.path())
            .find(|path| path.file_name().and_then(|n| n.to_str()).is_some_and(|n| n.ends_with(&suffix)));
        if let Some(found) = found {
            let path = dir.join(format!("{}_side.png", shot.name));
            save(&path, &side_by_side(&load(&found)?, &picture))?;
            written.push(path);
        }
    }
    Ok(written)
}
