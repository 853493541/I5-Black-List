//! 设置 and 环境测试's card drawn without a display (Slint's software renderer), as PNG, at a Windows scale.

use std::cell::RefCell;
use std::path::Path;
use std::rc::Rc;

use slint::platform::software_renderer::{MinimalSoftwareWindow, RepaintBufferType};
use slint::platform::{Platform, WindowAdapter, WindowEvent};
use slint::{ComponentHandle, PhysicalSize, Rgb8Pixel};

thread_local! {
    static LAST: RefCell<Option<Rc<MinimalSoftwareWindow>>> = const { RefCell::new(None) };
}

/// Every new component gets a window of its own; the last one made is the one drawn.
struct Headless;

impl Platform for Headless {
    fn create_window_adapter(&self) -> Result<Rc<dyn WindowAdapter>, slint::PlatformError> {
        let window = MinimalSoftwareWindow::new(RepaintBufferType::NewBuffer);
        LAST.with(|last| *last.borrow_mut() = Some(window.clone()));
        Ok(window)
    }
}

/// Once per process (Slint takes one platform); a no-op after.
pub fn init() {
    let _ = slint::platform::set_platform(Box::new(Headless));
}

/// The last component made, shown at `width` x `height` logical pixels times `scale`: its pixels (RGB) and size.
pub fn draw(component: &impl ComponentHandle, width: u32, height: u32, scale: f32) -> Result<(Vec<u8>, u32, u32), String> {
    let window = LAST.with(|last| last.borrow().clone()).ok_or("no window made")?;
    let (w, h) = ((width as f32 * scale).round() as u32, (height as f32 * scale).round() as u32);
    window.dispatch_event(WindowEvent::ScaleFactorChanged { scale_factor: scale });
    window.set_size(PhysicalSize::new(w, h));
    component.show().map_err(|e| e.to_string())?;
    window.request_redraw();
    let mut buffer = vec![Rgb8Pixel::new(0, 0, 0); (w * h) as usize];
    window.draw_if_needed(|renderer| {
        renderer.render(&mut buffer, w as usize);
    });
    component.hide().map_err(|e| e.to_string())?;
    Ok((buffer.iter().flat_map(|p| [p.r, p.g, p.b]).collect(), w, h))
}

pub fn save(path: &Path, rgb: &[u8], width: u32, height: u32) -> Result<(), String> {
    let file = std::io::BufWriter::new(std::fs::File::create(path).map_err(|e| e.to_string())?);
    let mut encoder = png::Encoder::new(file, width, height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    encoder.write_header().and_then(|mut w| w.write_image_data(rgb)).map_err(|e| e.to_string())
}
