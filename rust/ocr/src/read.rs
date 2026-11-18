//! OnnxOcr.predict of blacklist_detect/onnx_ocr.py: every line of a frame, found, sorted, straightened, read narrowest
//! first in batches of LINE_BATCH, and given back in reading order with their boxes. rust/pyocr exposes it to Python, and
//! tools/rust_golden_ocr_parity.py proves it reads every line as the Python reader does.

use std::path::Path;

use opencv::core::Mat;
use opencv::prelude::*;
use ort::environment::Environment;

use crate::crop::{crop_by_polys, sort_boxes};
use crate::db::Quad;
use crate::det::{TextDetector, DET_PARAMS};
use crate::rec::{Read, Recognizer, Result};

/// The pipeline's recognition batch (onnx_ocr.LINE_BATCH).
pub const LINE_BATCH: usize = 16;
/// REC_SCORE_THRESH: every read is kept.
pub const REC_SCORE_THRESH: f64 = 0.0;

/// One line of OnnxOcr.predict: rec_texts, rec_scores, rec_polys and rec_boxes ([x0, y0, x1, y1]) at one index.
#[derive(Clone, Debug, PartialEq)]
pub struct Line {
    pub text: String,
    pub score: f64,
    pub poly: Quad,
    pub bbox: [i32; 4],
}

/// The two models of the line reader: PP-OCRv5_mobile_det and PP-OCRv5_mobile_rec.
pub struct Ocr {
    pub det: TextDetector,
    pub rec: Recognizer,
}

impl Ocr {
    pub fn new(env: &Environment, det_dir: &Path, rec_dir: &Path, threads: usize) -> Result<Self> {
        Ok(Self { det: TextDetector::new(env, det_dir, threads)?, rec: Recognizer::new(env, rec_dir, LINE_BATCH)? })
    }

    /// Every line of the BGR frame, as OnnxOcr.predict reads it.
    pub fn predict(&mut self, bgr: &Mat) -> Result<Vec<Line>> {
        let found = self.det.detect_with(bgr, &DET_PARAMS)?;
        let polys = sort_boxes(&found.polys);
        if polys.is_empty() {
            return Ok(Vec::new());
        }
        let pairs: Vec<(Mat, Quad)> = crop_by_polys(bgr, &polys)?
            .into_iter()
            .zip(polys)
            .filter(|(crop, _)| !crop.empty() && crop.rows() > 0 && crop.cols() > 0)
            .collect();
        let shapes: Vec<(i32, i32)> = pairs.iter().map(|(crop, _)| (crop.rows(), crop.cols())).collect();
        let order = narrowest_first(&shapes);
        let ordered: Vec<Mat> = order.iter().map(|&i| pairs[i].0.clone()).collect();
        let mut reads: Vec<Read> = vec![(String::new(), 0.0); pairs.len()];
        for (&slot, read) in order.iter().zip(self.rec.read(&ordered)?) {
            reads[slot] = read;
        }
        Ok(pairs
            .into_iter()
            .zip(reads)
            .filter(|(_, (_, score))| *score >= REC_SCORE_THRESH)
            .map(|((_, poly), (text, score))| Line { text, score, poly, bbox: bbox(&poly) })
            .collect())
    }
}

/// Indexes of the crops ((rows, cols) each) by width over height, narrowest first; ties keep their order (sorted()).
pub fn narrowest_first(shapes: &[(i32, i32)]) -> Vec<usize> {
    let mut order: Vec<usize> = (0..shapes.len()).collect();
    let ratio = |i: usize| shapes[i].1 as f64 / shapes[i].0 as f64;
    order.sort_by(|&a, &b| ratio(a).total_cmp(&ratio(b)));
    order
}

/// rec_boxes: the poly's [min x, min y, max x, max y].
pub fn bbox(poly: &Quad) -> [i32; 4] {
    let xs = poly.iter().map(|p| p[0] as i32);
    let ys = poly.iter().map(|p| p[1] as i32);
    [xs.clone().min().unwrap_or(0), ys.clone().min().unwrap_or(0), xs.max().unwrap_or(0), ys.max().unwrap_or(0)]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn narrowest_first_is_stable() {
        // ratios 4, 2, 4, 0.5: the two 4s keep their order.
        assert_eq!(narrowest_first(&[(10, 40), (10, 20), (5, 20), (20, 10)]), vec![3, 1, 0, 2]);
        assert!(narrowest_first(&[]).is_empty());
    }

    #[test]
    fn bbox_spans_the_quad() {
        assert_eq!(bbox(&[[5, 2], [30, 1], [31, 12], [4, 13]]), [4, 1, 31, 13]);
    }
}
