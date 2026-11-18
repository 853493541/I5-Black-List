//! The name strip made ready for the recognizer, as blacklist_detect/ocr_engine.py does it: prepare_name_line (the
//! name's own band, doubled, contrast raised, inverted) and prepare_name_line_plain (the whole strip at height 48,
//! sharpened). Both take the strip as RGB and return BGR, white text on dark turned to dark on white.

use opencv::core::{self, Mat, Scalar, Size};
use opencv::imgproc;
use opencv::prelude::*;

use super::Result;

/// The bytes of a Mat, row after row.
pub fn bytes(mat: &Mat) -> Result<Vec<u8>> {
    if mat.is_continuous() {
        Ok(mat.data_bytes()?.to_vec())
    } else {
        Ok(mat.try_clone()?.data_bytes()?.to_vec())
    }
}

/// A Mat of the given type holding `data`, row after row.
pub fn mat_from(rows: i32, cols: i32, typ: i32, data: &[u8]) -> Result<Mat> {
    let mut mat = Mat::new_rows_cols_with_default(rows, cols, typ, Scalar::all(0.0))?;
    mat.data_bytes_mut()?.copy_from_slice(data);
    Ok(mat)
}

/// _bottom_text_band: the rows of the name line. The portrait above it is bright too, so the first bright rows are
/// not the name: the last run of inked rows is, with runs above it at most 6 rows away.
pub fn bottom_text_band(rgb: &Mat) -> Result<Mat> {
    let (rows, cols) = (rgb.rows() as usize, rgb.cols() as usize);
    let data = bytes(rgb)?;
    let need = 4.max((cols as f64 * 0.03) as usize);
    let active: Vec<bool> = data
        .chunks_exact(cols * 3)
        .map(|row| row.as_chunks::<3>().0.iter().filter(|px| px[0].max(px[1]).max(px[2]) >= 150).count() > need)
        .collect();
    let mut groups: Vec<(usize, usize)> = Vec::new();
    let mut start = None;
    for (index, &on) in active.iter().enumerate() {
        match (on, start) {
            (true, None) => start = Some(index),
            (false, Some(begin)) => {
                if index - begin >= 3 {
                    groups.push((begin, index));
                }
                start = None;
            }
            _ => {}
        }
    }
    if let Some(begin) = start {
        if rows - begin >= 3 {
            groups.push((begin, rows));
        }
    }
    let Some(&(mut top, bottom)) = groups.last() else { return Ok(rgb.try_clone()?) };
    for &(begin, end) in groups[..groups.len() - 1].iter().rev() {
        if top as i64 - end as i64 <= 6 {
            top = begin;
        } else {
            break;
        }
    }
    let top = top.saturating_sub(8);
    let bottom = rows.min(bottom + 6);
    let band = Mat::roi(rgb, core::Rect::new(0, top as i32, cols as i32, (bottom - top) as i32))?;
    Ok(band.try_clone()?)
}

/// numpy.percentile with its default linear method, on a uint8 image.
pub fn percentile(values: &[u8], q: f64) -> f64 {
    let mut counts = [0usize; 256];
    for &v in values {
        counts[v as usize] += 1;
    }
    let nth = |k: usize| -> f64 {
        let mut seen = 0;
        for (value, &count) in counts.iter().enumerate() {
            seen += count;
            if seen > k {
                return value as f64;
            }
        }
        255.0
    };
    let n = values.len();
    let virtual_index = (n as f64 - 1.0) * (q / 100.0);
    let previous = virtual_index.floor();
    let gamma = virtual_index - previous;
    let a = nth(previous as usize);
    let b = nth((previous as usize + 1).min(n - 1));
    let diff = b - a;
    if gamma >= 0.5 {
        b - diff * (1.0 - gamma)
    } else {
        a + diff * gamma
    }
}

/// Stretches `gray` so `low_q`..`high_q` percentiles span 0..255 (float32, as numpy does it), inverts it, and puts
/// it back to three channels with a white border.
fn stretch_invert(gray: &Mat, low_q: f64, high_q: f64, border: [i32; 4]) -> Result<Mat> {
    let data = bytes(gray)?;
    let low = percentile(&data, low_q);
    let mut high = percentile(&data, high_q);
    if high <= low + 1.0 {
        high = low + 1.0;
    }
    let (low32, factor) = (low as f32, (255.0 / (high - low)) as f32);
    let inverted: Vec<u8> = data.iter().map(|&g| 255 - ((g as f32 - low32) * factor).clamp(0.0, 255.0) as u8).collect();
    let single = mat_from(gray.rows(), gray.cols(), core::CV_8UC1, &inverted)?;
    let mut bgr = Mat::default();
    imgproc::cvt_color_def(&single, &mut bgr, imgproc::COLOR_GRAY2BGR)?;
    let mut out = Mat::default();
    let [top, bottom, left, right] = border;
    core::copy_make_border(&bgr, &mut out, top, bottom, left, right, core::BORDER_CONSTANT, Scalar::all(255.0))?;
    Ok(out)
}

fn resize_cubic(rgb: &Mat, width: i32, height: i32) -> Result<Mat> {
    let mut out = Mat::default();
    imgproc::resize(rgb, &mut out, Size::new(width, height), 0.0, 0.0, imgproc::INTER_CUBIC)?;
    Ok(out)
}

fn gray_of(rgb: &Mat) -> Result<Mat> {
    let mut gray = Mat::default();
    imgproc::cvt_color_def(rgb, &mut gray, imgproc::COLOR_RGB2GRAY)?;
    Ok(gray)
}

/// prepare_name_line: tighten to the name line, enlarge twice, raise contrast. Returns BGR.
pub fn prepare_name_line(rgb: &Mat) -> Result<Mat> {
    let band = bottom_text_band(rgb)?;
    let enlarged = resize_cubic(&band, 1.max(band.cols() * 2), 1.max(band.rows() * 2))?;
    stretch_invert(&gray_of(&enlarged)?, 5.0, 98.0, [10, 10, 10, 10])
}

/// prepare_name_line_plain: the same strip at the recognizer's height, sharpened, without cutting a band out of it.
pub fn prepare_name_line_plain(rgb: &Mat) -> Result<Mat> {
    let (height, width) = (rgb.rows(), rgb.cols());
    if height < 2 || width < 2 {
        return prepare_name_line(rgb);
    }
    let target = 48;
    let scale = f64::from(target) / f64::from(height);
    let enlarged = resize_cubic(rgb, 1.max((f64::from(width) * scale).round_ties_even() as i32), target)?;
    let gray = gray_of(&enlarged)?;
    let mut blur = Mat::default();
    imgproc::gaussian_blur_def(&gray, &mut blur, Size::new(0, 0), 0.8)?;
    let mut sharp = Mat::default();
    core::add_weighted_def(&gray, 1.5, &blur, -0.5, 0.0, &mut sharp)?;
    stretch_invert(&sharp, 10.0, 97.0, [8, 8, 12, 12])
}

#[cfg(test)]
mod tests {
    use super::percentile;

    #[test]
    fn percentile_is_numpy_linear() {
        // numpy.percentile([0, 10, 20, 255], 5) == 1.5; ([0, 10, 20, 255], 98) == 240.9
        assert!((percentile(&[0, 10, 20, 255], 5.0) - 1.5).abs() < 1e-12);
        assert!((percentile(&[0, 10, 20, 255], 98.0) - 240.9).abs() < 1e-9);
    }
}
