//! love_scenes/light.py: light worked out per pixel once, on the CPU, and turned into pictures the
//! chip lays on every frame. The same box blurs and the same glow curve, in f32 as numpy has them.

/// A premultiplied RGBA8 picture.
#[derive(Clone, Default)]
pub struct Image {
    pub w: usize,
    pub h: usize,
    pub rgba: Vec<u8>,
}

/// QColor's redF, greenF, blueF of "#rrggbb".
pub fn rgb(color: &str) -> [f32; 3] {
    crate::draw::hex(color)
}

/// Python's round(): halves to even.
pub fn round_even(x: f64) -> f64 {
    x.round_ties_even()
}

/// light.blur: three box blurs along each axis, radius round(sigma * 0.9), edges repeated.
pub fn blur(a: &[f32], w: usize, h: usize, sigma: f64) -> Vec<f32> {
    let r = round_even(sigma * 0.9).max(1.0) as i64;
    let n = (2 * r + 1) as f32;
    let mut out = a.to_vec();
    let mut line = Vec::new();
    for axis in 0..2 {
        let (len, lines) = if axis == 0 { (h, w) } else { (w, h) };
        let at = |i: usize, j: usize| if axis == 0 { j * w + i } else { i * w + j };
        for _ in 0..3 {
            for i in 0..lines {
                line.clear();
                line.extend((0..len).map(|j| out[at(i, j)]));
                // Running sum over the window i - r ..= i + r, clamped at the ends.
                let get = |k: i64| line[k.clamp(0, len as i64 - 1) as usize];
                let mut sum: f32 = (-r..=r).map(get).sum();
                for j in 0..len {
                    out[at(i, j)] = sum / n;
                    let j = j as i64;
                    sum += get(j + r + 1) - get(j - r);
                }
            }
        }
    }
    out
}

/// light.glow: light (may run over 1) as a picture that adds it over what is under.
pub fn glow(light: &[[f32; 3]], w: usize, h: usize) -> Image {
    let mut rgba = Vec::with_capacity(w * h * 4);
    for l in light {
        let l = l.map(|v| v.max(0.0));
        let over = (l[0].max(l[1]).max(l[2]) - 1.0).max(0.0);
        let l = l.map(|v| v + over * 0.6);
        let alpha = l[0].max(l[1]).max(l[2]).clamp(0.0, 1.0);
        let byte = |v: f32| (v * 255.0 + 0.5) as u8;
        for c in l {
            let color = (c.clamp(0.0, 1.0) / alpha.max(1e-4)).clamp(0.0, 1.0);
            rgba.push(byte(color * alpha));
        }
        rgba.push(byte(alpha));
    }
    Image { w, h, rgba }
}

/// light.bloom: a lit line, its core burning white and the tint spreading round it.
pub fn bloom(core: &[f32], w: usize, h: usize, tint: &str, spread: &[(f64, f32)], white: f32) -> Image {
    let color = rgb(tint);
    let mut halo = vec![0f32; w * h];
    for &(sigma, strength) in spread {
        for (o, b) in halo.iter_mut().zip(blur(core, w, h, sigma)) {
            *o += b * strength;
        }
    }
    let light: Vec<[f32; 3]> = halo.iter().zip(core).map(|(&a, &c)| std::array::from_fn(|i| a * color[i] + c.powf(1.5) * (color[i] * 0.5 + white * 0.7))).collect();
    glow(&light, w, h)
}

/// The chalk glow round an equation's letters (mask at half size): two blurs, tinted.
pub fn halo(shape: &[f32], w: usize, h: usize, px: f64, tint: &str) -> Image {
    let soft = super::SOFT;
    let (a, b) = (blur(shape, w, h, px * soft * 0.1), blur(shape, w, h, px * soft * 0.4));
    let color = rgb(tint);
    let light: Vec<[f32; 3]> = a.iter().zip(&b).map(|(&a, &b)| color.map(|c| (a * 0.9 + b * 0.75) * c)).collect();
    glow(&light, w, h)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blur_keeps_the_total_and_spreads() {
        let mut a = vec![0f32; 21 * 21];
        a[10 * 21 + 10] = 1.0;
        let b = blur(&a, 21, 21, 2.0);
        let total: f32 = b.iter().sum();
        assert!((total - 1.0).abs() < 1e-4, "{total}");
        assert!(b[10 * 21 + 10] < 0.2 && b[10 * 21 + 12] > 0.0);
    }

    #[test]
    fn glow_goes_white_when_over_bright() {
        let img = glow(&[[2.0, 0.5, 0.5], [0.0, 0.0, 0.0]], 2, 1);
        assert_eq!(&img.rgba[0..4], &[255, 255, 255, 255]);
        assert_eq!(&img.rgba[4..8], &[0, 0, 0, 0]);
    }
}
