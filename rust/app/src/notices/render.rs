//! Drawing the notices without a display, at Windows scale 150 %, through Slint's software renderer.
//! Each test thread gets a platform of its own (Slint keeps it per thread).

use std::path::Path;
use std::rc::Rc;

use slint::platform::software_renderer::MinimalSoftwareWindow;
use slint::platform::{WindowAdapter, WindowEvent};
use slint::{ComponentHandle, LogicalSize, Rgb8Pixel};

pub const SCALE: f32 = 1.5;

/// Set this thread's platform once; call before making any window.
pub fn init() {
    crate::shots::init();
}

/// The software window behind the component made last on this thread.
pub fn last_window() -> Rc<MinimalSoftwareWindow> {
    let window = crate::shots::newest();
    window.dispatch_event(WindowEvent::ScaleFactorChanged { scale_factor: SCALE });
    window
}

/// A picture: its size in physical pixels and its pixels.
pub struct Picture {
    pub width: u32,
    pub height: u32,
    pub pixels: Vec<Rgb8Pixel>,
}

/// Draw `ui` at `size` logical pixels (the scale makes it 1.5 times as many physical ones).
pub fn draw(ui: &impl ComponentHandle, window: &MinimalSoftwareWindow, size: (f32, f32)) -> Picture {
    window.set_size(LogicalSize::new(size.0, size.1));
    ui.show().expect("shown");
    let physical = window.size();
    let (width, height) = (physical.width, physical.height);
    let mut pixels = vec![Rgb8Pixel::new(0, 0, 0); (width * height) as usize];
    window.request_redraw();
    window.draw_if_needed(|renderer| {
        renderer.render(&mut pixels, width as usize);
    });
    ui.hide().expect("hidden");
    Picture { width, height, pixels }
}

pub fn save(picture: &Picture, path: &Path) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)?;
    }
    let file = std::io::BufWriter::new(std::fs::File::create(path)?);
    let mut encoder = png::Encoder::new(file, picture.width, picture.height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    let bytes: Vec<u8> = picture.pixels.iter().flat_map(|pixel| [pixel.r, pixel.g, pixel.b]).collect();
    encoder.write_header()?.write_image_data(&bytes)?;
    Ok(())
}
