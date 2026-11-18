//! KitGallery drawn without a display, through Slint's software renderer, as RGB pixels.

use std::path::Path;
use std::rc::Rc;

use slint::platform::software_renderer::MinimalSoftwareWindow;
use slint::platform::WindowAdapter;
use slint::{ComponentHandle, PhysicalSize, Rgb8Pixel};

/// The software window of the component made last on this thread (the shared headless platform's).
pub fn window() -> Rc<MinimalSoftwareWindow> {
    crate::shots::init();
    crate::shots::newest()
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
