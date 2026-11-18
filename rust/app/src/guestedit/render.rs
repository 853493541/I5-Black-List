//! Drawing the dialogs without a display, at their own size and scale 1.5 (a 150 % screen), through Slint's
//! software renderer, as src/headless.rs does for 设置. Each component gets a window of its own.

use std::path::Path;

use slint::platform::{WindowAdapter, WindowEvent};
use slint::{ComponentHandle, LogicalSize, PhysicalSize, Rgb8Pixel};

pub const SCALE: f32 = 1.5;

/// The windows made on this thread, the last one first to hand; set up once per thread (Slint's platform is per thread).
pub struct Renderer {
    _shared: (),
}

impl Renderer {
    pub fn new() -> Result<Self, Box<dyn std::error::Error>> {
        crate::shots::init();
        Ok(Renderer { _shared: () })
    }

    /// The component's window at `logical` size and SCALE, drawn; the pixels and their physical size.
    pub fn draw(&self, ui: &impl ComponentHandle, logical: LogicalSize) -> Result<(Vec<Rgb8Pixel>, PhysicalSize), Box<dyn std::error::Error>> {
        let window = crate::shots::newest();
        window.dispatch_event(WindowEvent::ScaleFactorChanged { scale_factor: SCALE });
        let size = logical.to_physical(SCALE);
        window.set_size(size);
        ui.show()?;
        window.request_redraw();
        let mut buffer = vec![Rgb8Pixel::new(0, 0, 0); (size.width * size.height) as usize];
        window.draw_if_needed(|renderer| {
            renderer.render(&mut buffer, size.width as usize);
        });
        ui.hide()?;
        Ok((buffer, size))
    }
}

pub fn save(path: &Path, buffer: &[Rgb8Pixel], size: PhysicalSize) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)?;
    }
    let file = std::io::BufWriter::new(std::fs::File::create(path)?);
    let mut encoder = png::Encoder::new(file, size.width, size.height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    let bytes: Vec<u8> = buffer.iter().flat_map(|pixel| [pixel.r, pixel.g, pixel.b]).collect();
    encoder.write_header()?.write_image_data(&bytes)?;
    Ok(())
}
