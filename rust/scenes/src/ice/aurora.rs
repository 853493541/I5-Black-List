//! The aurora, ported from ice.py's `_soft_aurora` and `_aurora`: three curtains of thin vertical
//! rays, bright at their lower hem and fading upward, cut into folds and finer rays by a horizontal
//! mask, each with a soft haze band and a glow along its hem. The numbers are worked out here per
//! frame; aurora.wgsl shades every pixel of the half-size picture they make.

use super::{blend, spectrum, WHITE};
use crate::draw::{ease_out, hex, win};

/// The aurora's colors, leaning on the deep blues.
const AURORA: [&str; 10] = ["#1f4fe0", "#2f7bff", "#46c6ff", "#7ff2e6", "#4fa6ff", "#6f86ff", "#9a7bff", "#c08bff", "#6f86ff", "#2f62f0"];
pub const RAYS: usize = 96;
const MASK: usize = 161;
/// Floats per curtain: a header of 8, hems and tops (97 each), 96 rays of 8, the mask, haze and hem glow (9 colors of 4).
pub const STRIDE: usize = 8 + 2 * (RAYS + 1) + RAYS * 8 + MASK + 2 * 36;
/// Floats before the curtains: width, curtain count, unused, unused.
pub const HEAD: usize = 4;

pub struct Aurora {
    /// The picture's size in pixels: half the scene's width and half the band's height, rounded.
    pub size: [u32; 2],
    /// How far down the band reaches, in the scene's pixels.
    pub band: f64,
    /// What aurora.wgsl reads.
    pub data: Vec<f32>,
    grow: f64,
}

fn premul(c: [f32; 3], a: f64) -> [f32; 4] {
    let a = a.clamp(0.0, 1.0) as f32;
    [c[0] * a, c[1] * a, c[2] * a, a]
}

impl Aurora {
    pub fn drawn(&self) -> bool {
        self.grow > 0.0
    }

    pub fn new(t: f64, width: f64, height: f64, u: f64, leave: f64) -> Self {
        let band = height.min(260.0 * u);
        let size = [(width / 2.0).round_ties_even().max(1.0) as u32, (band / 2.0).round_ties_even().max(1.0) as u32];
        let grow = ease_out(win(t, 0.15, 1.3));
        let mut data = vec![width as f32, 0.0, 0.0, 0.0];
        if grow <= 0.0 {
            return Self { size, band, data, grow };
        }
        let rise = 70.0 * u * leave;
        let fade = 1.0 - leave;
        // hem height, ray height, ripple, speed, phase, brightness, color offset
        let curtains = [(62.0, 130.0, 16.0, 0.9, 0.0, 0.78, 0.0), (92.0, 100.0, 11.0, -0.7, 2.2, 0.6, 0.33), (44.0, 160.0, 20.0, 0.5, 4.1, 0.55, 0.66)];
        let step = width / RAYS as f64;
        let title = width * 0.535;
        data[1] = curtains.len() as f32;
        for (hem, tall, ripple, speed, phase, bright, offset) in curtains {
            let hems: Vec<f64> = (0..=RAYS)
                .map(|i| {
                    let x = i as f64 * step;
                    let k = x / width;
                    let lift = 46.0 * u * (-((x - title) / (width * 0.11)).powi(2)).exp();
                    let y = hem * u - lift + ripple * u * ((k * 7.3 + t * speed + phase).sin() + 0.45 * (k * 17.1 - t * speed * 1.7 + phase * 2.0).sin());
                    y * (0.35 + 0.65 * grow) - rise
                })
                .collect();
            let tops: Vec<f64> = (0..=RAYS).map(|i| hems[i] - tall * u * (0.88 + 0.12 * ((i as f64 * step / width) * 5.0 + t + phase).sin())).collect();
            let a = bright * 1.25 * grow * fade;
            let layer = if a >= 0.02 { a.min(1.0) } else { 0.0 };
            let at = data.len();
            data.extend([layer as f32, (9.0 * u) as f32, step as f32, (40.0 * u) as f32, (26.0 * u) as f32, (2.5 * u) as f32, 0.0, 0.0]);
            data.extend(hems.iter().map(|&v| v as f32));
            data.extend(tops.iter().map(|&v| v as f32));
            for i in 0..RAYS {
                let k = (i as f64 * step + step / 2.0) / width;
                let color = spectrum(&AURORA, k * 1.3 + t * 0.16 + offset);
                let bright = blend(color, WHITE, 0.2);
                data.extend([color[0], color[1], color[2], (a * 0.38).min(1.0) as f32, bright[0], bright[1], bright[2], (a * 0.92).min(1.0) as f32]);
            }
            for s in 0..MASK {
                let k = s as f64 / 160.0;
                let folds = 0.5 + 0.5 * (k * 29.0 + t * 1.3 + phase).sin();
                let streaks = 0.5 + 0.5 * (k * 83.0 - t * 1.7 + phase * 3.0).sin();
                let strength = (0.25 + 0.75 * folds) * (0.45 + 0.55 * streaks.powi(2)) * (0.7 + 0.3 * (k * 11.0 - t * 0.8).sin());
                data.push(strength.clamp(0.0, 1.0) as f32);
            }
            for (lighten, alpha) in [(0.1, 0.16), (0.35, 0.22)] {
                for s in 0..9 {
                    let k = f64::from(s) / 8.0;
                    let color = blend(spectrum(&AURORA, k * 1.3 + t * 0.16 + offset), hex("#ffffff"), lighten);
                    data.extend(premul(color, alpha * bright * grow * fade));
                }
            }
            debug_assert_eq!(data.len() - at, STRIDE);
        }
        Self { size, band, data, grow }
    }
}

#[cfg(test)]
mod tests {
    use super::{Aurora, HEAD, STRIDE};

    #[test]
    fn three_curtains_once_it_grows() {
        let a = Aurora::new(0.1, 1920.0, 1080.0, 1.17, 0.0);
        assert!(!a.drawn());
        let b = Aurora::new(1.5, 1920.0, 1080.0, 1.17, 0.0);
        assert_eq!(b.data.len(), HEAD + 3 * STRIDE);
        assert_eq!(b.size, [960, 152]);
    }
}
