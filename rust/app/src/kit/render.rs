//! KitGallery drawn without a display, through Slint's software renderer, as RGB pixels.

use std::path::Path;
use std::rc::Rc;

use slint::platform::software_renderer::{MinimalSoftwareWindow, RepaintBufferType};
use slint::platform::{Platform, WindowAdapter};
use slint::{ComponentHandle, PhysicalSize, Rgb8Pixel};

struct Headless {
    window: Rc<MinimalSoftwareWindow>,
}

impl Platform for Headless {
    fn create_window_adapter(&self) -> Result<Rc<dyn WindowAdapter>, slint::PlatformError> {
        Ok(self.window.clone())
    }
}

/// A software window for this thread: Slint keeps one platform per thread.
pub fn window() -> Rc<MinimalSoftwareWindow> {
    let window = MinimalSoftwareWindow::new(RepaintBufferType::NewBuffer);
    // A second call on the same thread finds the platform set; the first window then serves.
    let _ = slint::platform::set_platform(Box::new(Headless { window: window.clone() }));
    window
}

/// Draw `ui` in `window` at `width` x `height` physical pixels, `scale` physical pixels per logical one.
pub fn draw(
    window: &MinimalSoftwareWindow,
    ui: &impl ComponentHandle,
    width: u32,
    height: u32,
    scale: f32,
) -> Result<Vec<Rgb8Pixel>, slint::PlatformError> {
    window.dispatch_event(slint::platform::WindowEvent::ScaleFactorChanged { scale_factor: scale });
    window.set_size(PhysicalSize::new(width, height));
    ui.show()?;
    window.request_redraw();
    let mut buffer = vec![Rgb8Pixel::new(0, 0, 0); (width * height) as usize];
    window.draw_if_needed(|renderer| {
        renderer.render(&mut buffer, width as usize);
    });
    Ok(buffer)
}

/// Save RGB pixels as a PNG.
pub fn save(path: &Path, buffer: &[Rgb8Pixel], width: u32, height: u32) -> Result<(), Box<dyn std::error::Error>> {
    let file = std::io::BufWriter::new(std::fs::File::create(path)?);
    let mut encoder = png::Encoder::new(file, width, height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    let bytes: Vec<u8> = buffer.iter().flat_map(|pixel| [pixel.r, pixel.g, pixel.b]).collect();
    encoder.write_header()?.write_image_data(&bytes)?;
    Ok(())
}
