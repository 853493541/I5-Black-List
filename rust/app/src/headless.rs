//! Drawing the window without a display: Slint's software renderer into a buffer, saved as PNG.

use std::path::Path;
use std::rc::Rc;

use slint::platform::software_renderer::{MinimalSoftwareWindow, RepaintBufferType};
use slint::platform::{Platform, WindowAdapter};
use slint::{ComponentHandle, PhysicalSize, Rgb8Pixel};

use crate::SettingsWindow;

const WIDTH: u32 = 900;
const HEIGHT: u32 = 560;

struct Headless {
    window: Rc<MinimalSoftwareWindow>,
}

impl Platform for Headless {
    fn create_window_adapter(&self) -> Result<Rc<dyn WindowAdapter>, slint::PlatformError> {
        Ok(self.window.clone())
    }
}

/// slint-light.png and slint-dark.png in `dir`, 设置 › 常规 at 900 x 560.
pub fn render_all(dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
    std::fs::create_dir_all(dir)?;
    let window = MinimalSoftwareWindow::new(RepaintBufferType::NewBuffer);
    slint::platform::set_platform(Box::new(Headless { window: window.clone() }))
        .map_err(|error| format!("{error:?}"))?;
    let ui = SettingsWindow::new()?;
    window.set_size(PhysicalSize::new(WIDTH, HEIGHT));
    ui.show()?;
    for (name, dark) in [("light", false), ("dark", true)] {
        ui.set_dark(dark);
        window.request_redraw();
        let mut buffer = vec![Rgb8Pixel::new(0, 0, 0); (WIDTH * HEIGHT) as usize];
        window.draw_if_needed(|renderer| {
            renderer.render(&mut buffer, WIDTH as usize);
        });
        save(&dir.join(format!("slint-{name}.png")), &buffer)?;
    }
    ui.hide()?;
    Ok(())
}

fn save(path: &Path, buffer: &[Rgb8Pixel]) -> Result<(), Box<dyn std::error::Error>> {
    let file = std::io::BufWriter::new(std::fs::File::create(path)?);
    let mut encoder = png::Encoder::new(file, WIDTH, HEIGHT);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    let bytes: Vec<u8> = buffer.iter().flat_map(|pixel| [pixel.r, pixel.g, pixel.b]).collect();
    encoder.write_header()?.write_image_data(&bytes)?;
    Ok(())
}
