//! 调试截图 (ui.py _save_debug): with settings.save_debug_frames on, each check's capture is kept as
//! <data folder>\debug\<YYYYmmdd-HHMMSS>.png, and only the newest 30 stay (DEBUG_KEEP).

use super::stubs::CheckError;
use super::worker::Screen;
use std::io;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use win::frame::Frame;

/// How many captures stay (ui.DEBUG_KEEP).
pub const KEEP: usize = 30;

/// Writes `frame` as `<dir>/<stamp>.png`, then drops all but the newest KEEP.
pub fn save(dir: &Path, frame: &Frame, stamp: &str) -> io::Result<PathBuf> {
    std::fs::create_dir_all(dir)?;
    let path = dir.join(format!("{stamp}.png"));
    let file = io::BufWriter::new(std::fs::File::create(&path)?);
    let mut encoder = png::Encoder::new(file, frame.width as u32, frame.height as u32);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    encoder.write_header().and_then(|mut writer| writer.write_image_data(&frame.rgb)).map_err(io::Error::other)?;
    prune(dir);
    Ok(path)
}

/// The oldest captures go, by name (the stamp sorts by time), until KEEP are left.
pub fn prune(dir: &Path) {
    let Ok(items) = std::fs::read_dir(dir) else { return };
    let mut pngs: Vec<PathBuf> = items.flatten().map(|item| item.path()).filter(|path| path.extension().is_some_and(|e| e == "png")).collect();
    pngs.sort();
    let extra = pngs.len().saturating_sub(KEEP);
    for old in &pngs[..extra] {
        let _ = std::fs::remove_file(old);
    }
}

/// The screen the worker checks, keeping each check's first capture while the flag is on.
pub struct DebugCapture<S> {
    pub inner: S,
    pub dir: PathBuf,
    pub on: Arc<AtomicBool>,
}

impl<S: Screen> Screen for DebugCapture<S> {
    fn displays(&mut self) -> Result<Vec<Frame>, CheckError> {
        let frames = self.inner.displays()?;
        if self.on.load(Ordering::Relaxed) {
            if let Some(frame) = frames.first() {
                let _ = save(&self.dir, frame, &chrono::Local::now().format("%Y%m%d-%H%M%S").to_string());
            }
        }
        Ok(frames)
    }

    /// The glance between checks (自动) is no check: nothing kept.
    fn top_band(&mut self) -> Result<Frame, CheckError> {
        self.inner.top_band()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Fake;

    impl Screen for Fake {
        fn displays(&mut self) -> Result<Vec<Frame>, CheckError> {
            Ok(vec![Frame { width: 2, height: 2, rgb: vec![200; 12] }])
        }
        fn top_band(&mut self) -> Result<Frame, CheckError> {
            Ok(Frame { width: 1, height: 1, rgb: vec![0; 3] })
        }
    }

    fn pngs(dir: &Path) -> Vec<String> {
        let mut names: Vec<String> = std::fs::read_dir(dir).map_or(Vec::new(), |items| {
            items.flatten().map(|item| item.file_name().to_string_lossy().into_owned()).collect()
        });
        names.sort();
        names
    }

    #[test]
    fn debug_frames_on_keeps_each_check_as_a_png() {
        let root = tempfile::tempdir().unwrap();
        let dir = root.path().join("debug");
        let mut screen = DebugCapture { inner: Fake, dir: dir.clone(), on: Arc::new(AtomicBool::new(true)) };
        screen.displays().unwrap();
        screen.top_band().unwrap();
        let names = pngs(&dir);
        assert_eq!(names.len(), 1, "{names:?}");
        assert_eq!(names[0].len(), "20261119-031500.png".len());
        assert!(std::fs::read(dir.join(&names[0])).unwrap().starts_with(b"\x89PNG"));
    }

    #[test]
    fn debug_frames_off_writes_nothing() {
        let root = tempfile::tempdir().unwrap();
        let dir = root.path().join("debug");
        let mut screen = DebugCapture { inner: Fake, dir: dir.clone(), on: Arc::new(AtomicBool::new(false)) };
        screen.displays().unwrap();
        assert!(!dir.exists());
    }

    #[test]
    fn debug_frames_keep_the_newest_thirty() {
        let root = tempfile::tempdir().unwrap();
        let dir = root.path().join("debug");
        std::fs::create_dir_all(&dir).unwrap();
        for i in 0..KEEP {
            std::fs::write(dir.join(format!("20250101-0000{i:02}.png")), b"old").unwrap();
        }
        save(&dir, &Frame { width: 1, height: 1, rgb: vec![1, 2, 3] }, "20261119-120000").unwrap();
        let names = pngs(&dir);
        assert_eq!(names.len(), KEEP);
        assert!(!names.contains(&"20250101-000000.png".to_string()), "the oldest went");
        assert_eq!(names.last().map(String::as_str), Some("20261119-120000.png"));
    }
}
