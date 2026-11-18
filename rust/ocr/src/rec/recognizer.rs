//! TextRecognizer of blacklist_detect/onnx_ocr.py: resize and normalise each line, pad a batch to its widest line,
//! run the model on ONNX Runtime, CTC-decode. Session settings as onnx_ocr.session().

use std::path::Path;

use opencv::core::{Mat, Size};
use opencv::imgproc;
use opencv::prelude::*;
use ort::environment::Environment;
use ort::logging::LogLevel;
use ort::session::Session;
use ort::value::Tensor;
use serde::Deserialize;

use super::prepare::bytes;
use super::{ctc, Read, Result};

/// Threads like paths.ocr_threads: one per physical core, 2 to 8, unless PADDLE_PDX_CPU_NUM_THREADS sets a count.
pub use common::paths::ocr_threads;

#[derive(Deserialize)]
struct Config {
    #[serde(rename = "PreProcess")]
    pre: PreProcess,
    #[serde(rename = "PostProcess")]
    post: PostProcess,
}

#[derive(Deserialize)]
struct PreProcess {
    transform_ops: Vec<serde_yaml::Mapping>,
}

#[derive(Deserialize)]
struct PostProcess {
    character_dict: Vec<String>,
}

#[derive(Deserialize)]
struct RecResize {
    image_shape: [usize; 3],
}

/// One recognition model (a folder with inference.onnx and inference.yml) and the batch size it reads in.
pub struct Recognizer {
    session: Session,
    image_shape: [usize; 3],
    characters: Vec<String>,
    batch_size: usize,
}

impl Recognizer {
    /// A recognizer on `environment` (ort::init_from(libonnxruntime)?.build()?, made once for the process).
    pub fn new(environment: &Environment, model_dir: &Path, batch_size: usize) -> Result<Self> {
        let config: Config = serde_yaml::from_reader(std::fs::File::open(model_dir.join("inference.yml"))?)?;
        let resize = config
            .pre
            .transform_ops
            .iter()
            .find_map(|op| op.get("RecResizeImg").cloned())
            .ok_or("inference.yml has no RecResizeImg")?;
        let resize: RecResize = serde_yaml::from_value(resize)?;
        let session = (|| -> ort::Result<Session> {
            Session::builder(environment)?
                .with_log_level(LogLevel::Error)?
                .with_intra_threads(ocr_threads())?
                .with_inter_threads(1)?
                .with_config_entry("session.intra_op.allow_spinning", "0")?
                .with_config_entry("session.set_denormal_as_zero", "1")?
                .commit_from_file(model_dir.join("inference.onnx"))
        })()?;
        Ok(Self { session, image_shape: resize.image_shape, characters: ctc::characters(&config.post.character_dict), batch_size })
    }

    /// Reads every line (BGR), in batches of the recognizer's size, in order.
    pub fn read(&mut self, images: &[Mat]) -> Result<Vec<Read>> {
        let mut out = Vec::with_capacity(images.len());
        for batch in images.chunks(self.batch_size.max(1)) {
            out.extend(self.read_batch(batch)?);
        }
        Ok(out)
    }

    /// read_batch: each line resized and normalised, padded with zeros on the right to the widest, run together.
    pub fn read_batch(&mut self, images: &[Mat]) -> Result<Vec<Read>> {
        if images.is_empty() {
            return Ok(Vec::new());
        }
        let lines = images.iter().map(|img| self.resize_norm(img)).collect::<Result<Vec<_>>>()?;
        let [channels, height, _] = self.image_shape;
        let widest = lines.iter().map(|(_, width)| *width).max().unwrap_or(0);
        let mut batch = vec![0f32; lines.len() * channels * height * widest];
        for (index, (data, width)) in lines.iter().enumerate() {
            for (row, src) in data.chunks_exact(*width).enumerate() {
                let start = (index * channels * height + row) * widest;
                batch[start..start + width].copy_from_slice(src);
            }
        }
        let input = Tensor::from_array((vec![lines.len(), channels, height, widest], batch))?;
        let outputs = self.session.run(ort::inputs![input])?;
        let (shape, preds) = outputs[0].try_extract_tensor::<f32>()?;
        let (steps, classes) = (shape[1] as usize, shape[2] as usize);
        Ok(ctc::decode(preds, steps, classes, &self.characters))
    }

    /// resize_norm (OCRReisizeNormImg): height 48, width by the line's own shape (at most 3200), values to [-1, 1],
    /// laid out CHW and padded with zeros to the line's width. Returns the data and that width.
    pub fn resize_norm(&self, img: &Mat) -> Result<(Vec<f32>, usize)> {
        let [channels, height, width] = self.image_shape;
        let (h, w) = (f64::from(img.rows()), f64::from(img.cols()));
        let max_wh_ratio = (width as f64 / height as f64).max(w / h);
        let mut width = (height as f64 * max_wh_ratio) as usize;
        let resized_w = if width > 3200 {
            width = 3200;
            3200
        } else {
            let wanted = (height as f64 * (w / h)).ceil();
            if wanted > width as f64 { width } else { wanted as usize }
        };
        let mut resized = Mat::default();
        imgproc::resize(img, &mut resized, Size::new(resized_w as i32, height as i32), 0.0, 0.0, imgproc::INTER_LINEAR)?;
        let pixels = bytes(&resized)?;
        let mut out = vec![0f32; channels * height * width];
        for c in 0..channels {
            for y in 0..height {
                for x in 0..resized_w {
                    let value = f32::from(pixels[(y * resized_w + x) * channels + c]) / 255.0;
                    out[(c * height + y) * width + x] = (value - 0.5) / 0.5;
                }
            }
        }
        Ok((out, width))
    }
}
