//! Pixel work done by hand to match the Python app: PIL's gray thumbnail of the title (pipeline._thumb) and
//! layout.snap_button_box, which moves the guessed button box onto the pale button.

use lobby::PxBox;

/// A frame's pixels: RGB bytes row by row.
pub struct Pixels<'a> {
    pub data: &'a [u8],
    pub width: usize,
    pub height: usize,
}

impl Pixels<'_> {
    fn at(&self, x: usize, y: usize) -> [u8; 3] {
        let i = (y * self.width + x) * 3;
        [self.data[i], self.data[i + 1], self.data[i + 2]]
    }
}

const PRECISION: u32 = 22;

/// PIL's precompute_coeffs with the bilinear (triangle) filter, normalised to 8-bit fixed point.
fn coeffs(in_size: usize, out_size: usize) -> Vec<(usize, Vec<i64>)> {
    let scale = in_size as f64 / out_size as f64;
    let filterscale = scale.max(1.0);
    let support = filterscale;
    (0..out_size)
        .map(|xx| {
            let center = (xx as f64 + 0.5) * scale;
            let ss = 1.0 / filterscale;
            let xmin = ((center - support + 0.5) as i64).max(0) as usize;
            let xmax = ((center + support + 0.5) as i64).min(in_size as i64) as usize - xmin;
            let raw: Vec<f64> = (0..xmax)
                .map(|x| {
                    let t = (((x + xmin) as f64 - center + 0.5) * ss).abs();
                    if t < 1.0 { 1.0 - t } else { 0.0 }
                })
                .collect();
            let total: f64 = raw.iter().sum();
            let k = raw
                .iter()
                .map(|w| {
                    let w = if total != 0.0 { w / total } else { *w };
                    let fixed = w * f64::from(1u32 << PRECISION);
                    (if w < 0.0 { -0.5 + fixed } else { 0.5 + fixed }) as i64
                })
                .collect();
            (xmin, k)
        })
        .collect()
}

fn clip8(value: i64) -> u8 {
    (value >> PRECISION).clamp(0, 255) as u8
}

/// PIL's Image.resize(size, BILINEAR) of an 8-bit gray image: horizontal pass, then vertical.
pub fn resize_bilinear(gray: &[u8], width: usize, height: usize, out_w: usize, out_h: usize) -> Vec<u8> {
    let mut img = gray.to_vec();
    let mut w = width;
    if out_w != width {
        let ks = coeffs(width, out_w);
        let mut next = vec![0u8; out_w * height];
        for y in 0..height {
            for (x, (xmin, k)) in ks.iter().enumerate() {
                let sum: i64 = k.iter().enumerate().map(|(i, c)| i64::from(img[y * w + xmin + i]) * c).sum();
                next[y * out_w + x] = clip8((1 << (PRECISION - 1)) + sum);
            }
        }
        img = next;
        w = out_w;
    }
    if out_h != height {
        let ks = coeffs(height, out_h);
        let mut next = vec![0u8; w * out_h];
        for (y, (ymin, k)) in ks.iter().enumerate() {
            for x in 0..w {
                let sum: i64 = k.iter().enumerate().map(|(i, c)| i64::from(img[(ymin + i) * w + x]) * c).sum();
                next[y * w + x] = clip8((1 << (PRECISION - 1)) + sum);
            }
        }
        img = next;
    }
    img
}

/// PIL's convert("L"): ITU-R 601-2 luma in 16-bit fixed point.
pub fn luma(rgb: [u8; 3]) -> u8 {
    ((u32::from(rgb[0]) * 19595 + u32::from(rgb[1]) * 38470 + u32::from(rgb[2]) * 7471 + 0x8000) >> 16) as u8
}

/// _thumb: the box cut out (at least one pixel), gray, resized to `size`, as floats.
pub fn thumb(px: &Pixels, bbox: &[f64; 4], size: (usize, usize)) -> Vec<f32> {
    let [left, top, right, bottom] = bbox.map(crate::image::py_round);
    let clip = |v: i64, max: usize| v.clamp(0, max as i64) as usize;
    let (x0, x1) = (clip(left.max(0), px.width), clip(right.max(left + 1), px.width));
    let (y0, y1) = (clip(top.max(0), px.height), clip(bottom.max(top + 1), px.height));
    let (w, h) = (x1.saturating_sub(x0).max(1), y1.saturating_sub(y0).max(1));
    let gray: Vec<u8> = (0..h)
        .flat_map(|y| (0..w).map(move |x| (x, y)))
        .map(|(x, y)| luma(px.at((x0 + x).min(px.width - 1), (y0 + y).min(px.height - 1))))
        .collect();
    resize_bilinear(&gray, w, h, size.0, size.1).into_iter().map(f32::from).collect()
}

/// Mean absolute difference of two thumbnails.
pub fn mean_diff(a: &[f32], b: &[f32]) -> f64 {
    if a.len() != b.len() || a.is_empty() {
        return f64::INFINITY;
    }
    a.iter().zip(b).map(|(x, y)| f64::from((x - y).abs())).sum::<f64>() / a.len() as f64
}

/// numpy.percentile with linear interpolation.
fn percentile(values: &[i64], q: f64) -> f64 {
    let mut sorted = values.to_vec();
    sorted.sort_unstable();
    let pos = q / 100.0 * (sorted.len() - 1) as f64;
    let (lo, frac) = (pos.floor() as usize, pos - pos.floor());
    let hi = (lo + 1).min(sorted.len() - 1);
    let (a, b) = (sorted[lo] as f64, sorted[hi] as f64);
    a + (b - a) * frac
}

fn median(values: &[i64]) -> f64 {
    percentile(values, 50.0)
}

/// snap_button_box: the guessed 准备案件还原 box moved onto the pale button in this capture.
pub fn snap_button_box(px: &Pixels, predicted: Option<PxBox>) -> Option<PxBox> {
    let [left, top, right, bottom] = predicted?;
    let (width, height) = (right - left, bottom - top);
    if width < 8 || height < 8 {
        return predicted;
    }
    let pad_x = 16.max((width as f64 * 0.5) as i64);
    let pad_y = 16.max((height as f64 * 0.6) as i64);
    let x0 = (left - pad_x).max(0);
    let y0 = (top - pad_y).max(0);
    let x1 = (right + pad_x).min(px.width as i64);
    let y1 = (bottom + pad_y).min(px.height as i64);
    if x1 <= x0 || y1 <= y0 {
        return predicted;
    }
    let face: Vec<Vec<bool>> = (y0..y1)
        .map(|y| {
            (x0..x1)
                .map(|x| {
                    let p = px.at(x as usize, y as usize).map(i32::from);
                    let lum = f64::from(p[0] + p[1] + p[2]) / 3.0;
                    let spread = p.iter().max().unwrap() - p.iter().min().unwrap();
                    lum >= 118.0 && spread <= 52
                })
                .collect()
        })
        .collect();
    let counts: Vec<i64> = face.iter().map(|row| row.iter().filter(|&&f| f).count() as i64).collect();
    let most = *counts.iter().max()?;
    if (most as f64) < width as f64 * 0.45 {
        return predicted;
    }
    let core: Vec<usize> = (0..counts.len()).filter(|&r| counts[r] as f64 >= most as f64 * 0.80).collect();
    if core.len() < 3 {
        return predicted;
    }
    let run = |row: usize| -> Option<(i64, i64)> {
        let first = face[row].iter().position(|&f| f)?;
        let last = face[row].iter().rposition(|&f| f)?;
        Some((first as i64, last as i64))
    };
    let edges: Vec<(i64, i64)> = core.iter().filter_map(|&r| run(r)).collect();
    if edges.len() < 3 {
        return predicted;
    }
    let core_left = median(&edges.iter().map(|e| e.0).collect::<Vec<_>>()) as i64;
    let core_right = median(&edges.iter().map(|e| e.1).collect::<Vec<_>>()) as i64;
    let middle = (core_left + core_right) as f64 / 2.0;
    let min_run = (core_right - core_left) as f64 * 0.30;
    let overlaps = |row: usize| {
        run(row).is_some_and(|(a, b)| (b - a) as f64 >= min_run && a as f64 <= middle && middle <= b as f64)
    };
    let (mut top_index, mut bottom_index) = (core[0], core[core.len() - 1]);
    while top_index > 0 && overlaps(top_index - 1) {
        top_index -= 1;
    }
    while bottom_index < face.len() - 1 && overlaps(bottom_index + 1) {
        bottom_index += 1;
    }
    let straight_need = most as f64 - 8f64.max(width as f64 * 0.015);
    let straight: Vec<usize> = (top_index..=bottom_index).filter(|&r| counts[r] as f64 >= straight_need).collect();
    let rows = if straight.is_empty() { (top_index..=bottom_index).collect() } else { straight };
    let spans: Vec<(i64, i64)> = rows.iter().filter_map(|&r| run(r)).collect();
    if spans.is_empty() {
        return predicted;
    }
    let snapped_left = x0 + percentile(&spans.iter().map(|s| s.0).collect::<Vec<_>>(), 8.0) as i64;
    let snapped_right = x0 + percentile(&spans.iter().map(|s| s.1).collect::<Vec<_>>(), 92.0) as i64 + 1;
    let (snapped_top, snapped_bottom) = (y0 + top_index as i64, y0 + bottom_index as i64 + 1);
    if snapped_right <= snapped_left || snapped_bottom <= snapped_top {
        return predicted;
    }
    Some([snapped_left, snapped_top, snapped_right, snapped_bottom])
}
