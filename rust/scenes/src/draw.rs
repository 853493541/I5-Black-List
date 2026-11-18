//! What the scenes draw with, as love_scenes/draw.py has it: easing, colors, hearts and paths.

pub type Pt = [f64; 2];

pub fn clamp(x: f64) -> f64 {
    x.clamp(0.0, 1.0)
}

/// 0 before a, 1 after b, linear between.
pub fn win(t: f64, a: f64, b: f64) -> f64 {
    clamp((t - a) / (b - a))
}

pub fn ease_out(k: f64) -> f64 {
    1.0 - (1.0 - clamp(k)).powi(3)
}

pub fn ease_in(k: f64) -> f64 {
    clamp(k).powi(3)
}

pub fn ease_in_out(k: f64) -> f64 {
    let k = clamp(k);
    if k < 0.5 {
        4.0 * k.powi(3)
    } else {
        1.0 - (-2.0 * k + 2.0).powi(3) / 2.0
    }
}

/// A color as 0..1 floats from "#rrggbb".
pub fn hex(color: &str) -> [f32; 3] {
    let v = u32::from_str_radix(color.trim_start_matches('#'), 16).unwrap_or(0);
    [((v >> 16) & 255) as f32 / 255.0, ((v >> 8) & 255) as f32 / 255.0, (v & 255) as f32 / 255.0]
}

/// draw.mix: each channel rounded to a byte, as QColor keeps it.
pub fn mix(a: &str, b: &str, k: f64) -> [f32; 3] {
    let (ca, cb) = (hex(a), hex(b));
    let k = clamp(k) as f32;
    std::array::from_fn(|i| ((ca[i] * 255.0 + (cb[i] - ca[i]) * 255.0 * k).round()) / 255.0)
}

/// Points around a heart, size its width; 0 at the top cleft, going clockwise.
pub fn heart_points(cx: f64, cy: f64, size: f64, count: usize) -> Vec<Pt> {
    (0..count)
        .map(|i| {
            let a = i as f64 / count as f64 * std::f64::consts::TAU;
            let x = 16.0 * a.sin().powi(3);
            let y = 13.0 * a.cos() - 5.0 * (2.0 * a).cos() - 2.0 * (3.0 * a).cos() - (4.0 * a).cos();
            [cx + x * size / 34.0, cy - (y - 2.5) * size / 34.0]
        })
        .collect()
}

/// The first frac of a polyline, by length.
pub fn partial(points: &[Pt], frac: f64) -> Vec<Pt> {
    let frac = clamp(frac);
    if frac <= 0.0 || points.len() < 2 {
        return Vec::new();
    }
    let seg = |a: Pt, b: Pt| (b[0] - a[0]).hypot(b[1] - a[1]);
    let mut goal = points.windows(2).map(|w| seg(w[0], w[1])).sum::<f64>() * frac;
    let mut out = vec![points[0]];
    for w in points.windows(2) {
        let (a, b, len) = (w[0], w[1], seg(w[0], w[1]));
        if goal >= len {
            out.push(b);
            goal -= len;
            continue;
        }
        let k = if len > 0.0 { goal / len } else { 0.0 };
        out.push([a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k]);
        break;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn heart_starts_at_the_cleft_and_tip_is_halfway() {
        let ring = heart_points(0.0, 0.0, 34.0, 120);
        assert!((ring[0][0]).abs() < 1e-9 && (ring[0][1] + 2.5).abs() < 1e-9);
        assert!(ring[60][0].abs() < 1e-9 && ring[60][1] > 15.0);
    }

    #[test]
    fn partial_cuts_by_length() {
        let line = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]];
        assert_eq!(partial(&line, 0.25), vec![[0.0, 0.0], [5.0, 0.0]]);
        assert_eq!(partial(&line, 1.0).len(), 3);
        assert!(partial(&line, 0.0).is_empty());
    }

    #[test]
    fn mix_rounds_like_qcolor() {
        let c = mix("#f6d68a", "#ffffff", 0.6);
        assert_eq!(c.map(|v| (v * 255.0).round() as u8), [251, 239, 208]);
    }
}
