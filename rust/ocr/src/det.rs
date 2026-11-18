//! TextDetector: the session, DetResizeForTest and NormalizeImage of onnx_ocr.py, then the DB post-process.

use std::path::Path;

use opencv::core::{Mat, Size, BORDER_CONSTANT};
use opencv::imgproc;
use opencv::prelude::*;
use ort::environment::Environment;
use ort::session::Session;
use ort::value::Tensor;

use crate::db::{db_boxes, Quad};
use crate::{Error, Result};

/// DET_PARAMS: the settings PaddleOCR 3.7 runs PP-OCRv5 with.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DetParams {
    pub limit_side_len: i32,
    pub limit_type: LimitType,
    pub thresh: f64,
    pub max_side_limit: i32,
    pub box_thresh: f64,
    pub unclip_ratio: f64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LimitType {
    Max,
    Min,
    ResizeLong,
}

pub const DET_PARAMS: DetParams = DetParams {
    limit_side_len: 64,
    limit_type: LimitType::Min,
    thresh: 0.3,
    max_side_limit: 4000,
    box_thresh: 0.6,
    unclip_ratio: 1.5,
};

/// One image's boxes (dt_polys) and their scores (dt_scores).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Detection {
    pub polys: Vec<Quad>,
    pub scores: Vec<f64>,
}

/// ONNX Runtime loaded from this library file (onnxruntime's libonnxruntime.so / onnxruntime.dll).
pub fn init_runtime(library: &Path) -> Result<Environment> {
    Ok(ort::init_from(library).map_err(|err| Error::Ort(err.to_string()))?.build()?)
}

/// paths.ocr_threads: one thread per core, 2 to 8.
pub use common::paths::ocr_threads_for as ocr_threads;

pub struct TextDetector {
    pub alpha: [f64; 3],
    pub beta: [f64; 3],
    session: Session,
}

impl TextDetector {
    /// The model in this folder (inference.onnx and inference.yml) on the CPU, reading on `threads` threads.
    pub fn new(env: &Environment, model_dir: &Path, threads: usize) -> Result<Self> {
        let (alpha, beta) = read_normalize(&model_dir.join("inference.yml"))?;
        let session = Session::builder(env)?
            .with_log_level(ort::logging::LogLevel::Error)?
            .with_intra_threads(threads)?
            .with_inter_threads(1)?
            // Between reads the threads sleep instead of spinning; denormals flushed, as onnx_ocr.session() sets.
            .with_config_entry("session.intra_op.allow_spinning", "0")?
            .with_config_entry("session.set_denormal_as_zero", "1")?
            .commit_from_file(crate::model_file(model_dir))?;
        Ok(Self { alpha, beta, session })
    }

    /// The boxes in a BGR image, with DET_PARAMS.
    pub fn detect(&mut self, image: &Mat) -> Result<Detection> {
        self.detect_with(image, &DET_PARAMS)
    }

    pub fn detect_with(&mut self, image: &Mat, params: &DetParams) -> Result<Detection> {
        let (pred, h, w, shape) = self.predict(image, params)?;
        let (polys, scores) = db_boxes(&pred, h, w, shape, params.thresh, params.box_thresh, params.unclip_ratio)?;
        Ok(Detection { polys, scores })
    }

    /// The model's probability map (h x w) for the image, and the [h, w, ratio_h, ratio_w] of its resize.
    pub fn predict(&mut self, image: &Mat, params: &DetParams) -> Result<(Vec<f32>, usize, usize, [f64; 4])> {
        let (resized, shape) = det_resize(image, params.limit_side_len, params.limit_type, params.max_side_limit)?;
        let (h, w) = (resized.rows() as usize, resized.cols() as usize);
        let input = Tensor::from_array(([1usize, 3, h, w], self.normalize(&resized)?))?;
        let outputs = self.session.run(ort::inputs![input])?;
        let (dims, pred) = outputs[0].try_extract_tensor::<f32>()?;
        let (ph, pw) = (dims[dims.len() - 2] as usize, dims[dims.len() - 1] as usize);
        Ok((pred.to_vec(), ph, pw, shape))
    }

    /// NormalizeImage in float32, then HWC to CHW: each channel times alpha plus beta.
    pub fn normalize(&self, img: &Mat) -> Result<Vec<f32>> {
        let (h, w) = (img.rows() as usize, img.cols() as usize);
        let continuous = if img.is_continuous() { img.clone() } else { img.try_clone()? };
        let bytes = continuous.data_bytes()?;
        let channels = continuous.channels() as usize;
        let mut out = vec![0f32; 3 * h * w];
        for c in 0..3 {
            let (alpha, beta) = (self.alpha[c] as f32, self.beta[c] as f32);
            let plane = &mut out[c * h * w..(c + 1) * h * w];
            for (i, value) in plane.iter_mut().enumerate() {
                let mut x = bytes[i * channels + c] as f32;
                x *= alpha;
                x += beta;
                *value = x;
            }
        }
        Ok(out)
    }
}

/// DetResizeForTest, resize type 0: sides to multiples of 32. Returns the image and [h, w, ratio_h, ratio_w].
pub fn det_resize(img: &Mat, limit_side_len: i32, limit_type: LimitType, max_side_limit: i32) -> Result<(Mat, [f64; 4])> {
    let (src_h, src_w) = (img.rows(), img.cols());
    let mut img = img.clone();
    if src_h + src_w < 64 {
        let mut padded = Mat::default();
        let (bottom, right) = ((32 - src_h).max(0), (32 - src_w).max(0));
        opencv::core::copy_make_border(&img, &mut padded, 0, bottom, 0, right, BORDER_CONSTANT, Default::default())?;
        img = padded;
    }
    let (h, w) = (img.rows() as f64, img.cols() as f64);
    let limit = limit_side_len as f64;
    let mut ratio = match limit_type {
        LimitType::Max if h.max(w) > limit => limit / h.max(w),
        LimitType::Min if h.min(w) < limit => limit / h.min(w),
        LimitType::ResizeLong => limit / h.max(w),
        _ => 1.0,
    };
    let (mut resize_h, mut resize_w) = ((h * ratio) as i64, (w * ratio) as i64);
    if resize_h.max(resize_w) > max_side_limit as i64 {
        ratio = max_side_limit as f64 / resize_h.max(resize_w) as f64;
        (resize_h, resize_w) = ((resize_h as f64 * ratio) as i64, (resize_w as f64 * ratio) as i64);
    }
    let to32 = |side: i64| (((side as f64 / 32.0).round_ties_even() as i64) * 32).max(32);
    let (resize_h, resize_w) = (to32(resize_h), to32(resize_w));
    if resize_h as f64 == h && resize_w as f64 == w {
        return Ok((img, [src_h as f64, src_w as f64, 1.0, 1.0]));
    }
    let mut out = Mat::default();
    let size = Size::new(resize_w as i32, resize_h as i32);
    imgproc::resize(&img, &mut out, size, 0.0, 0.0, imgproc::INTER_LINEAR)?;
    Ok((out, [src_h as f64, src_w as f64, resize_h as f64 / h, resize_w as f64 / w]))
}

/// alpha and beta of the model's NormalizeImage (inference.yml), as TextDetector.__init__ computes them.
fn read_normalize(yml: &Path) -> Result<([f64; 3], [f64; 3])> {
    let text = std::fs::read_to_string(yml).map_err(|err| Error::Config(format!("{}: {err}", yml.display())))?;
    let config: serde_yaml::Value = serde_yaml::from_str(&text).map_err(|err| Error::Config(err.to_string()))?;
    let ops = config["PreProcess"]["transform_ops"].as_sequence().ok_or(Error::Config("no transform_ops".into()))?;
    let normalize = ops
        .iter()
        .find_map(|op| op.get("NormalizeImage"))
        .ok_or(Error::Config("no NormalizeImage".into()))?;
    let scale = match &normalize["scale"] {
        serde_yaml::Value::Null => 1.0 / 255.0,
        serde_yaml::Value::String(text) => eval_ratio(text)?,
        value => value.as_f64().ok_or(Error::Config("scale".into()))?,
    };
    let list = |key: &str| -> Result<[f64; 3]> {
        let values: Vec<f64> = normalize[key].as_sequence().into_iter().flatten().filter_map(|v| v.as_f64()).collect();
        values.try_into().map_err(|_| Error::Config(format!("{key} is not 3 numbers")))
    };
    let (mean, std) = (list("mean")?, list("std")?);
    Ok((std::array::from_fn(|i| scale / std[i]), std::array::from_fn(|i| -mean[i] / std[i])))
}

/// "1./255." as Python evaluates it.
fn eval_ratio(text: &str) -> Result<f64> {
    let number = |part: &str| part.trim().parse::<f64>().map_err(|_| Error::Config(format!("scale {text:?}")));
    match text.split_once('/') {
        Some((top, bottom)) => Ok(number(top)? / number(bottom)?),
        None => number(text),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scale_reads_as_python_evaluates_it() {
        assert_eq!(eval_ratio("1./255.").unwrap(), 1.0 / 255.0);
        assert_eq!(eval_ratio("0.5").unwrap(), 0.5);
    }

    #[test]
    fn threads_stay_between_two_and_eight() {
        assert_eq!((ocr_threads(1), ocr_threads(6), ocr_threads(16)), (2, 6, 8));
    }

    #[test]
    fn sides_round_to_multiples_of_32_half_to_even() {
        for (rows, cols, want) in [(48, 100, [48.0, 100.0, 64.0 / 48.0, 128.0 / 100.0]), (16, 16, [16.0, 16.0, 2.0, 2.0])] {
            let img = Mat::new_rows_cols_with_default(rows, cols, opencv::core::CV_8UC3, Default::default()).unwrap();
            let (out, shape) = det_resize(&img, 64, LimitType::Min, 4000).unwrap();
            assert_eq!(shape, want);
            assert_eq!((out.rows() % 32, out.cols() % 32), (0, 0));
        }
    }
}
