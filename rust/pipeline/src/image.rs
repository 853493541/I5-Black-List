//! The picture work of pipeline.py, ocr_engine.py and layout.snap_button_box on an RGB frame (an 8-bit,
//! 3-channel OpenCV Mat in RGB order, as the Python app holds its numpy frames).

use lobby::{OcrLine, PxBox};
use opencv::core::{Mat, Rect, Size};
use opencv::imgproc;
use opencv::prelude::*;

use crate::Result;

/// Python's round(): halves to even.
pub fn py_round(value: f64) -> i64 {
    value.round_ties_even() as i64
}

/// A frame from tightly packed RGB bytes, row by row.
pub fn rgb_frame(width: i32, height: i32, rgb: &[u8]) -> Result<Mat> {
    if width <= 0 || height <= 0 || rgb.len() != width as usize * height as usize * 3 {
        return Err(format!("{} bytes are not {width}x{height} RGB", rgb.len()).into());
    }
    let mut mat = Mat::new_rows_cols_with_default(height, width, opencv::core::CV_8UC3, 0.into())?;
    mat.data_bytes_mut()?.copy_from_slice(rgb);
    Ok(mat)
}

/// rgb[y0:y1, x0:x1] as its own Mat, the range clipped to the frame as numpy clips a slice.
pub fn slice(rgb: &Mat, x0: i64, y0: i64, x1: i64, y1: i64) -> Result<Mat> {
    let (w, h) = (rgb.cols() as i64, rgb.rows() as i64);
    let clip = |v: i64, max: i64| if v < 0 { (v + max).max(0) } else { v.min(max) };
    let (x0, x1, y0, y1) = (clip(x0, w), clip(x1, w), clip(y0, h), clip(y1, h));
    if x1 <= x0 || y1 <= y0 {
        return Ok(Mat::default());
    }
    Ok(Mat::roi(rgb, Rect::new(x0 as i32, y0 as i32, (x1 - x0) as i32, (y1 - y0) as i32))?.try_clone()?)
}

/// rgb_to_bgr.
pub fn to_bgr(rgb: &Mat) -> Result<Mat> {
    if rgb.empty() {
        return Ok(Mat::default());
    }
    let mut out = Mat::default();
    imgproc::cvt_color_def(rgb, &mut out, imgproc::COLOR_RGB2BGR)?;
    Ok(out)
}

/// downscale_rgb: at most `max_width` wide (INTER_AREA), and the factor that maps its boxes back.
pub fn downscale(rgb: &Mat, max_width: i32) -> Result<(Mat, f64)> {
    let (width, height) = (rgb.cols(), rgb.rows());
    if width <= max_width {
        return Ok((rgb.clone(), 1.0));
    }
    let scale = f64::from(max_width) / f64::from(width);
    let new_w = py_round(f64::from(width) * scale).max(1) as i32;
    let new_h = py_round(f64::from(height) * scale).max(1) as i32;
    let mut small = Mat::default();
    imgproc::resize(rgb, &mut small, Size::new(new_w, new_h), 0.0, 0.0, imgproc::INTER_AREA)?;
    Ok((small, 1.0 / scale))
}

/// scale_lines.
pub fn scale_lines(lines: Vec<OcrLine>, factor: f64) -> Vec<OcrLine> {
    if factor == 1.0 {
        return lines;
    }
    lines.into_iter().map(|line| OcrLine::new(line.text, line.confidence, line.bbox.map(|v| v * factor))).collect()
}

/// A name strip cut for reading (_crop), in RGB.
pub fn name_crop(rgb: &Mat, bbox: &PxBox, scale: f64) -> Result<Mat> {
    let [left, top, right, bottom] = *bbox;
    let pad_x = py_round(14.0 * scale).max(4);
    let pad_top = py_round(3.0 * scale).max(1);
    let pad_bottom = py_round(8.0 * scale).max(2);
    let (width, height) = (rgb.cols() as i64, rgb.rows() as i64);
    let (l, r) = ((left - pad_x).max(0), (right + pad_x).min(width));
    let (t, b) = ((top - pad_top).max(0), (bottom + pad_bottom).min(height));
    slice(rgb, l, t, r, b)
}

/// A text line cut out with a little room round it (_cut), as BGR.
pub fn line_cut(rgb: &Mat, bbox: &[f64; 4]) -> Result<Mat> {
    let [left, top, right, bottom] = *bbox;
    let pad = 0.15 * (bottom - top);
    let (width, height) = (rgb.cols() as i64, rgb.rows() as i64);
    let x0 = ((left - pad) as i64).max(0);
    let x1 = ((right + pad) as i64).min(width);
    let y0 = ((top - pad) as i64).max(0);
    let y1 = ((bottom + pad) as i64).min(height);
    to_bgr(&slice(rgb, x0, y0, x1, y1)?)
}

/// The pixels of an RGB Mat, row by row.
pub fn pixels(rgb: &Mat) -> Result<Vec<u8>> {
    let mat = if rgb.is_continuous() { rgb.clone() } else { rgb.try_clone()? };
    Ok(mat.data_bytes()?.to_vec())
}
