//! The 嘉宾 page drawn without a display, as src/headless.rs draws 设置: Slint's software renderer into a buffer, saved
//! as PNG at 900 x 560 logical pixels times `scale`.

use std::path::Path;
use std::rc::Rc;

use slint::platform::software_renderer::{MinimalSoftwareWindow, RepaintBufferType};
use slint::platform::{Platform, WindowAdapter};
use slint::{ComponentHandle, PhysicalSize, Rgb8Pixel};

use super::model::Page;
use super::view::apply;
use crate::GuestsPreview;

pub const WIDTH: u32 = 900;
pub const HEIGHT: u32 = 560;

struct Headless {
    window: Rc<MinimalSoftwareWindow>,
}

impl Platform for Headless {
    fn create_window_adapter(&self) -> Result<Rc<dyn WindowAdapter>, slint::PlatformError> {
        Ok(self.window.clone())
    }
}

/// Draws each (file name, page, dark) into `dir` as `<name>.png`; returns each picture's pixels as RGB bytes.
pub fn render(dir: &Path, scale: f32, pages: &[(&str, Page, bool)]) -> Result<Vec<Vec<u8>>, Box<dyn std::error::Error>> {
    std::fs::create_dir_all(dir)?;
    let window = MinimalSoftwareWindow::new(RepaintBufferType::NewBuffer);
    // One platform per thread: a second call on the same thread finds it set and draws into a window of its own.
    slint::platform::set_platform(Box::new(Headless { window: window.clone() })).map_err(|error| format!("{error:?}"))?;
    let ui = GuestsPreview::new()?;
    let (width, height) = ((WIDTH as f32 * scale) as u32, (HEIGHT as f32 * scale) as u32);
    window.dispatch_event(slint::platform::WindowEvent::ScaleFactorChanged { scale_factor: scale });
    window.set_size(PhysicalSize::new(width, height));
    ui.show()?;
    let mut pictures = Vec::new();
    for (name, page, dark) in pages {
        ui.set_dark(*dark);
        apply(&ui, page);
        window.request_redraw();
        let mut buffer = vec![Rgb8Pixel::new(0, 0, 0); (width * height) as usize];
        window.draw_if_needed(|renderer| {
            renderer.render(&mut buffer, width as usize);
        });
        let bytes: Vec<u8> = buffer.iter().flat_map(|pixel| [pixel.r, pixel.g, pixel.b]).collect();
        save(&dir.join(format!("{name}.png")), width, height, &bytes)?;
        pictures.push(bytes);
    }
    ui.hide()?;
    Ok(pictures)
}

pub fn save(path: &Path, width: u32, height: u32, rgb: &[u8]) -> Result<(), Box<dyn std::error::Error>> {
    let file = std::io::BufWriter::new(std::fs::File::create(path)?);
    let mut encoder = png::Encoder::new(file, width, height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    encoder.write_header()?.write_image_data(rgb)?;
    Ok(())
}
