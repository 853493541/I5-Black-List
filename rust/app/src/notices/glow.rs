//! The red glow round the game's screen while a lobby with 黑名单 players is shown (ui_alert.py), and
//! the sample lobby as a whole 16:9 game screen (ui_demo.py), as numbers: the overlay draws them.
//!
//! The glow comes in from every edge, a little over a twentieth of the shorter side deep, and
//! breathes slowly (opacity 1 to 0.68 and back over 2.8 s) while the result is up. It fades in and
//! out over 260 ms. Clicks pass through it.

use std::f64::consts::PI;

/// The glow's red, its alpha at the very edge, and how deep it reaches as a share of the shorter side.
pub const RED: (u8, u8, u8) = (225, 38, 52);
pub const EDGE_ALPHA: f64 = 150.0;
pub const DEPTH: f64 = 0.055;
/// The slow breath: from full to this opacity and back, over this long.
pub const LOW: f64 = 0.68;
pub const BREATH_MS: u64 = 2_800;
pub const FADE_MS: u64 = 260;

/// One ring of the glow: a rectangle inset this far, drawn with a pen this wide in this alpha.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Ring {
    pub inset: f64,
    pub pen: f64,
    pub alpha: u8,
}

/// The rings that make the glow on a `width` by `height` area, outermost first (paint_glow).
pub fn rings(width: f64, height: f64) -> Vec<Ring> {
    let depth = (width.min(height) * DEPTH).max(24.0);
    let steps = ((depth / 2.0).round_ties_even() as usize).max(12);
    (0..steps)
        .map(|step| {
            let fade = (1.0 - step as f64 / steps as f64).powf(2.2);
            Ring { inset: depth * step as f64 / steps as f64, pen: depth / steps as f64 + 0.6, alpha: (EDGE_ALPHA * fade).round_ties_even() as u8 }
        })
        .collect()
}

/// Qt's InOutSine.
fn in_out_sine(t: f64) -> f64 {
    -((PI * t).cos() - 1.0) / 2.0
}

/// Qt's OutCubic.
fn out_cubic(t: f64) -> f64 {
    let t = t - 1.0;
    t * t * t + 1.0
}

/// The window's opacity `ms` into the breath: 1, down to 0.68 halfway, back to 1, over and over.
pub fn breath(ms: u64) -> f64 {
    let t = in_out_sine((ms % BREATH_MS) as f64 / BREATH_MS as f64);
    if t <= 0.5 {
        1.0 + (LOW - 1.0) * (t / 0.5)
    } else {
        LOW + (1.0 - LOW) * ((t - 0.5) / 0.5)
    }
}

/// The opacity `ms` into a fade from `from` to `to`.
pub fn fade(from: f64, to: f64, ms: u64) -> f64 {
    from + (to - from) * out_cubic((ms as f64 / FADE_MS as f64).min(1.0))
}

/// The sample lobby (assets/sample-lobby.jpg, made-up names) and where it lies on a whole 16:9 game
/// screen: from (-56, -52) to (3544, 1973) in the crop's pixels, the rest in the lobby's dark edge.
pub const SCREEN_IN_CROP: (i32, i32, i32, i32) = (-56, -52, 3544, 1973);
pub const EDGE: (u8, u8, u8) = (12, 16, 23);
/// 准备案件还原 on that whole screen, in fractions of it: left, top, right, bottom.
pub const BUTTON: (f64, f64, f64, f64) = (0.430, 0.776, 0.572, 0.846);
/// The whole screen is built at half size.
pub const SCALE: f64 = 0.5;

/// The whole sample screen's size, and where the crop goes on it (x, y), at half size.
pub fn sample_screen() -> ((u32, u32), (f64, f64)) {
    let (left, top, right, bottom) = SCREEN_IN_CROP;
    let size = (((right - left) as f64 * SCALE).round_ties_even() as u32, ((bottom - top) as f64 * SCALE).round_ties_even() as u32);
    (size, (-left as f64 * SCALE, -top as f64 * SCALE))
}

/// 准备案件还原 on a whole screen of `width` by `height`: x, y, width, height.
pub fn button_on(width: f64, height: f64) -> (f64, f64, f64, f64) {
    let (left, top, right, bottom) = BUTTON;
    (left * width, top * height, (right - left) * width, (bottom - top) * height)
}
