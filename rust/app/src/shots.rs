//! The one headless Slint platform every picture and render test uses: Slint's software renderer into a buffer, no
//! display. Slint takes one platform per thread (`set_platform` says AlreadySet after that), so the areas share this
//! one instead of installing their own: [`init`] installs it on the calling thread once, every component made after
//! gets a window of its own, and [`newest`] hands out the last one made, to draw.

// Some binaries and test runs reach only part of it.
#![allow(dead_code)]

use std::cell::RefCell;
use std::path::Path;
use std::rc::Rc;

use slint::platform::software_renderer::{MinimalSoftwareWindow, RepaintBufferType};
use slint::platform::{Platform, WindowAdapter, WindowEvent};
use slint::{ComponentHandle, LogicalSize, PhysicalSize, Rgb8Pixel};

thread_local! {
    static NEWEST: RefCell<Option<Rc<MinimalSoftwareWindow>>> = const { RefCell::new(None) };
}

struct Headless;

impl Platform for Headless {
    fn create_window_adapter(&self) -> Result<Rc<dyn WindowAdapter>, slint::PlatformError> {
        let window = MinimalSoftwareWindow::new(RepaintBufferType::NewBuffer);
        NEWEST.with(|slot| *slot.borrow_mut() = Some(window.clone()));
        Ok(window)
    }
}

/// Installs the headless platform on this thread, once; later calls do nothing.
pub fn init() {
    match slint::platform::set_platform(Box::new(Headless)) {
        Ok(()) | Err(slint::platform::SetPlatformError::AlreadySet) => {}
        Err(error) => panic!("the headless platform: {error:?}"),
    }
}

/// The window of the component made last on this thread.
pub fn newest() -> Rc<MinimalSoftwareWindow> {
    NEWEST.with(|slot| slot.borrow().clone()).expect("a component was made after shots::init")
}

/// A drawn window: physical pixels, RGB.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Picture {
    pub width: u32,
    pub height: u32,
    pub rgb: Vec<u8>,
}

impl Picture {
    pub fn pixels(&self) -> Vec<Rgb8Pixel> {
        self.rgb.chunks(3).map(|c| Rgb8Pixel::new(c[0], c[1], c[2])).collect()
    }
}

/// Draws the component made last, `size` logical pixels at Windows scale `scale` (1.5 for 150 %).
pub fn draw(ui: &impl ComponentHandle, size: (f32, f32), scale: f32) -> Result<Picture, slint::PlatformError> {
    let window = newest();
    window.dispatch_event(WindowEvent::ScaleFactorChanged { scale_factor: scale });
    ui.window().set_size(LogicalSize::new(size.0, size.1));
    ui.show()?;
    let picture = draw_window(&window, (size.0 * scale).round() as u32, (size.1 * scale).round() as u32);
    ui.hide()?;
    Ok(picture)
}

/// Draws a window already shown at its physical size.
pub fn draw_window(window: &MinimalSoftwareWindow, width: u32, height: u32) -> Picture {
    window.set_size(PhysicalSize::new(width, height));
    window.request_redraw();
    let mut buffer = vec![Rgb8Pixel::new(0, 0, 0); (width * height) as usize];
    window.draw_if_needed(|renderer| {
        renderer.render(&mut buffer, width as usize);
    });
    let rgb = buffer.iter().flat_map(|pixel| [pixel.r, pixel.g, pixel.b]).collect();
    Picture { width, height, rgb }
}

/// Saves RGB pixels as PNG.
pub fn save_rgb(path: &Path, rgb: &[u8], width: u32, height: u32) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)?;
    }
    let file = std::io::BufWriter::new(std::fs::File::create(path)?);
    let mut encoder = png::Encoder::new(file, width, height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    encoder.write_header()?.write_image_data(rgb)?;
    Ok(())
}

/// Saves a picture as PNG.
pub fn save(path: &Path, picture: &Picture) -> Result<(), Box<dyn std::error::Error>> {
    save_rgb(path, &picture.rgb, picture.width, picture.height)
}
