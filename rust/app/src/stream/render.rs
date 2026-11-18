//! The stream UI drawn without a display, the way src/headless.rs draws 设置: Slint's software renderer into a
//! buffer, at Windows scale 150 %, saved as PNG. For the side-by-side pictures in shots/stream/ and the tests.

use std::cell::RefCell;
use std::path::{Path, PathBuf};
use std::rc::Rc;

use slint::platform::software_renderer::{MinimalSoftwareWindow, RepaintBufferType};
use slint::platform::{Platform, WindowAdapter, WindowEvent};
use slint::{ComponentHandle, LogicalSize, Rgb8Pixel};

use super::{row_status, LivehimeState, SceneIssue, Tone};
use crate::{StreamGuideDialog, StreamPanelShot};

/// Windows scale 150 %, as tools/ui_shots.py --scale 150.
pub const SCALE: f32 = 1.5;

/// A platform that gives every new component a window of its own and keeps the newest to draw it.
struct Shots {
    newest: Rc<RefCell<Option<Rc<MinimalSoftwareWindow>>>>,
}

impl Platform for Shots {
    fn create_window_adapter(&self) -> Result<Rc<dyn WindowAdapter>, slint::PlatformError> {
        let window = MinimalSoftwareWindow::new(RepaintBufferType::NewBuffer);
        *self.newest.borrow_mut() = Some(window.clone());
        Ok(window)
    }
}

thread_local! {
    static NEWEST: Rc<RefCell<Option<Rc<MinimalSoftwareWindow>>>> = Rc::default();
}

fn install() -> Result<(), String> {
    use std::sync::OnceLock;
    static DONE: OnceLock<Result<(), String>> = OnceLock::new();
    DONE.get_or_init(|| {
        let newest = NEWEST.with(Rc::clone);
        slint::platform::set_platform(Box::new(Shots { newest })).map_err(|error| {
            format!("another renderer set Slint's platform first ({error:?}); draw the stream UI in its own process")
        })
    })
    .clone()
}

/// Draws the component just made, `size` logical pixels at SCALE, into `path`.
fn draw(ui: &impl ComponentHandle, size: (f32, f32), path: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let window = NEWEST.with(|newest| newest.borrow().clone()).ok_or("no window was made")?;
    window.dispatch_event(WindowEvent::ScaleFactorChanged { scale_factor: SCALE });
    ui.window().set_size(LogicalSize::new(size.0, size.1));
    ui.show()?;
    let (width, height) = ((size.0 * SCALE).round() as u32, (size.1 * SCALE).round() as u32);
    let mut buffer = vec![Rgb8Pixel::new(0, 0, 0); (width * height) as usize];
    window.request_redraw();
    window.draw_if_needed(|renderer| {
        renderer.render(&mut buffer, width as usize);
    });
    ui.hide()?;
    save(path, &buffer, width, height)
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

/// Every page and dialog of the stream UI, light and dark, into `dir`; the paths written.
pub fn render_all(dir: &Path) -> Result<Vec<PathBuf>, Box<dyn std::error::Error>> {
    install()?;
    std::fs::create_dir_all(dir)?;
    let mut written = Vec::new();
    let rows = [
        ("behind", true, LivehimeState::Found(SceneIssue::Behind)),
        ("ok", true, LivehimeState::Capturing),
        ("closed", true, LivehimeState::NotFound),
        ("off", false, LivehimeState::NotFound),
    ];
    for dark in [false, true] {
        let theme = if dark { "dark" } else { "light" };
        for (name, on, state) in &rows {
            let ui = StreamPanelShot::new()?;
            ui.set_dark(dark);
            ui.set_on(*on);
            let (words, tone) = row_status(*on, state).unwrap_or_default();
            ui.set_status(words.into());
            ui.set_tone_ok(tone == Tone::Ok);
            let path = dir.join(format!("slint-panel-{name}-{theme}.png"));
            draw(&ui, (444.0, 56.0), &path)?;
            written.push(path);
        }
        let ui = StreamGuideDialog::new()?;
        ui.set_dark(dark);
        let path = dir.join(format!("slint-guide-{theme}.png"));
        draw(&ui, (717.0, 446.0), &path)?;
        written.push(path);
    }
    Ok(written)
}
