//! 环境测试 (diagnostics.run_flow_test): the screen copied as a check copies it, the sample lobby laid in its
//! middle at a game window's size, then 自动检查 (a glance, then a check) and the hotkey three times, timed.

use super::engine::PipelineChecker;
use super::stubs::Checker;
use super::worker::Screen;
use data::diag::{FlowTest, LOBBY_SHARE, SAMPLE_NAMES};
use opencv::core::{Mat, Rect as CvRect, Size};
use opencv::prelude::*;
use std::path::Path;
use std::time::Instant;
use win::frame::Frame;

/// The sample lobby (assets/sample-lobby.jpg) as an RGB frame.
pub fn sample(assets: &Path) -> Option<Frame> {
    let bytes = std::fs::read(assets.join("sample-lobby.jpg")).ok()?;
    let bgr = opencv::imgcodecs::imdecode(&opencv::core::Vector::<u8>::from_slice(&bytes), opencv::imgcodecs::IMREAD_COLOR).ok()?;
    let mut rgb = Mat::default();
    opencv::imgproc::cvt_color_def(&bgr, &mut rgb, opencv::imgproc::COLOR_BGR2RGB).ok()?;
    Some(Frame { width: rgb.cols() as usize, height: rgb.rows() as usize, rgb: pipeline::image::pixels(&rgb).ok()? })
}

/// `lobby` scaled to LOBBY_SHARE of `screen` (Lanczos, as PIL) and pasted in its middle.
pub fn lay_in(screen: &Frame, lobby: &Frame) -> opencv::Result<Frame> {
    let mut out = pipeline::rgb_frame(screen.width as i32, screen.height as i32, &screen.rgb).map_err(cv)?;
    let small = pipeline::rgb_frame(lobby.width as i32, lobby.height as i32, &lobby.rgb).map_err(cv)?;
    let (w, h) = (screen.width as f64, screen.height as f64);
    let scale = (w * LOBBY_SHARE / lobby.width as f64).min(h * LOBBY_SHARE / lobby.height as f64);
    let size = Size::new((lobby.width as f64 * scale).round() as i32, (lobby.height as f64 * scale).round() as i32);
    let mut resized = Mat::default();
    opencv::imgproc::resize(&small, &mut resized, size, 0.0, 0.0, opencv::imgproc::INTER_LANCZOS4)?;
    let at = CvRect::new((screen.width as i32 - size.width) / 2, (screen.height as i32 - size.height) / 2, size.width, size.height);
    let mut target = Mat::roi_mut(&mut out, at)?;
    resized.copy_to(&mut target)?;
    Ok(Frame { width: screen.width, height: screen.height, rgb: pipeline::image::pixels(&out).map_err(cv)? })
}

fn cv(error: pipeline::Error) -> opencv::Error {
    opencv::Error::new(opencv::core::StsError, error.to_string())
}

fn timings(found: &pipeline::CheckResult) -> Vec<(String, f64)> {
    vec![("find".into(), found.timings.find), ("read".into(), found.timings.read)]
}

/// Runs the test (on a thread of its own: it takes seconds).
pub fn run(checker: &mut PipelineChecker, screen: &mut dyn Screen, lobby: &Frame, rounds: usize) -> FlowTest {
    let mut test = FlowTest::default();
    let started = Instant::now();
    let frames = match screen.displays() {
        Ok(frames) if !frames.is_empty() => frames,
        Ok(_) => return FlowTest { error: "无法截屏：没有屏幕".into(), ..test },
        Err(error) => return FlowTest { error: format!("无法截屏：{}", error.message), ..test },
    };
    test.capture = started.elapsed().as_secs_f64();
    test.screens = frames.len() as u32;
    test.size = (frames[0].width as u32, frames[0].height as u32);
    let laid = match lay_in(&frames[0], lobby) {
        Ok(laid) => laid,
        Err(error) => return FlowTest { error: format!("无法识别：{error}"), ..test },
    };
    let band_height = ((laid.height as f64 * win::frame::TITLE_BAND_FRACTION) as usize).max(1);
    let band = Frame { width: laid.width, height: band_height, rgb: laid.rgb[..laid.width * band_height * 3].to_vec() };
    checker.forget_spot();
    let started = Instant::now();
    match checker.glance(&band) {
        Ok(found) => test.glance_found = found,
        Err(error) => return FlowTest { error: format!("无法识别：{}", error.message), ..test },
    }
    test.glance = started.elapsed().as_secs_f64();
    let frame = std::slice::from_ref(&laid);
    let outcome = (|| {
        test.auto = timings(&checker.read_plain(frame)?);
        checker.forget_spot();
        for _ in 0..rounds {
            let started = Instant::now();
            let _ = screen.displays();
            let copy = started.elapsed().as_secs_f64();
            let found = checker.read_plain(frame)?;
            let mut run = vec![("capture".to_string(), copy)];
            run.extend(timings(&found));
            test.runs.push(run);
            test.right = right(&found);
        }
        Ok::<(), super::stubs::CheckError>(())
    })();
    if let Err(error) = outcome {
        test.error = format!("无法识别：{}", error.message);
    }
    checker.forget_spot();
    test
}

/// The sample's names read right, seat by seat.
pub fn right(found: &pipeline::CheckResult) -> u32 {
    found.names.iter().filter(|slot| SAMPLE_NAMES.get(slot.index).is_some_and(|name| slot.visible == *name)).count() as u32
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_sample_lies_in_the_middle_at_the_lobbys_share() {
        let screen = Frame { width: 100, height: 50, rgb: vec![0; 100 * 50 * 3] };
        let lobby = Frame { width: 10, height: 10, rgb: vec![255; 10 * 10 * 3] };
        let laid = lay_in(&screen, &lobby).unwrap();
        let at = |x: usize, y: usize| laid.rgb[(y * 100 + x) * 3];
        // 0.64 of 50 high: 32 x 32, from (34, 9).
        assert_eq!((at(50, 25), at(34, 9), at(65, 40)), (255, 255, 255));
        assert_eq!((at(33, 25), at(66, 25), at(50, 8), at(50, 41)), (0, 0, 0, 0));
    }

    #[test]
    fn no_screen_copy_is_said_in_the_report() {
        struct Blind;
        impl Screen for Blind {
            fn displays(&mut self) -> Result<Vec<Frame>, super::super::stubs::CheckError> {
                Err(super::super::stubs::CheckError { message: "没有权限".into(), models: false, plain: true })
            }
            fn top_band(&mut self) -> Result<Frame, super::super::stubs::CheckError> {
                self.displays().map(|mut frames| frames.remove(0))
            }
        }
        let mut checker = PipelineChecker::new("missing.dll".into(), None, 1, Default::default());
        let lobby = Frame { width: 1, height: 1, rgb: vec![0; 3] };
        let test = run(&mut checker, &mut Blind, &lobby, 3);
        assert_eq!(test.error, "无法截屏：没有权限");
    }
}
