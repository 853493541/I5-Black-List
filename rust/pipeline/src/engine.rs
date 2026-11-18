//! The ONNX Runtime half of ocr_engine.OcrEngine on onnx_ocr's models: a full read, cut lines read as they are, the
//! lobby's own lines only, the tallest lines only, and the twelve name strips.

use std::path::Path;

use lobby::OcrLine;
use ocr::rec::names::clean;
use ocr::rec::{Read, Recognizer};
use ocr::{crop_by_polys, sort_boxes, Quad, TextDetector};
use opencv::core::Mat;
use opencv::prelude::*;
use ort::environment::Environment;

use crate::models::ModelDirs;
use crate::Result;

/// The 推演成功 glance reads only the tallest few title-shaped lines.
pub const TITLE_CANDIDATES: usize = 4;
/// Four characters measure about 3 to 3.5 times as wide as tall at any window size.
pub const TITLE_SHAPE: (f64, f64) = (2.0, 6.0);
/// Where the lobby's other lines sit, in the title's height (dy, from its top) and width (dx, from its middle).
pub const LOBBY_BANDS: [((f64, f64), f64); 2] = [((0.9, 2.3), 1.1), ((6.0, 7.4), 0.9)];
/// The check looks among more of the tallest lines than the glance.
pub const LOBBY_TITLE_CANDIDATES: usize = 8;
/// onnx_ocr.REC_SCORE_THRESH and LINE_BATCH.
const REC_SCORE_THRESH: f64 = 0.0;
const LINE_BATCH: usize = 16;
const NAME_BATCH: usize = 12;
/// Set to 1, the name reader (PP-OCRv6_medium_rec) reads every line too and the line model is not loaded.
pub const ONE_READER_ENV: &str = "BLACKLIST_DETECT_ONE_READER";

/// Whether BLACKLIST_DETECT_ONE_READER asks for the name reader on every line.
pub fn one_reader_wanted() -> bool {
    std::env::var(ONE_READER_ENV).is_ok_and(|value| value == "1")
}

/// The models a check reads with, loaded once.
pub struct Engine {
    det: TextDetector,
    /// The line model; None when the name reader reads every line.
    lines: Option<Recognizer>,
    names: Recognizer,
}

/// _as_box of a detected quad: its bounds.
pub fn quad_box(quad: &Quad) -> [f64; 4] {
    let xs = quad.iter().map(|p| f64::from(p[0]));
    let ys = quad.iter().map(|p| f64::from(p[1]));
    [
        xs.clone().fold(f64::INFINITY, f64::min),
        ys.clone().fold(f64::INFINITY, f64::min),
        xs.fold(f64::NEG_INFINITY, f64::max),
        ys.fold(f64::NEG_INFINITY, f64::max),
    ]
}

fn title_shaped(bbox: &[f64; 4]) -> Option<f64> {
    let (width, height) = (bbox[2] - bbox[0], bbox[3] - bbox[1]);
    (height > 0.0 && (TITLE_SHAPE.0..=TITLE_SHAPE.1).contains(&(width / height))).then_some(height)
}

impl Engine {
    /// The name reader reads every line too when BLACKLIST_DETECT_ONE_READER is 1 or the line model is the same folder.
    pub fn new(env: &Environment, dirs: &ModelDirs, threads: usize) -> Result<Self> {
        Self::with_readers(env, dirs, threads, one_reader_wanted() || dirs.rec == dirs.names)
    }

    /// As `new`, with `one_reader` saying whether the name reader reads every line.
    pub fn with_readers(env: &Environment, dirs: &ModelDirs, threads: usize, one_reader: bool) -> Result<Self> {
        let lines = if one_reader { None } else { Some(Recognizer::new(env, &dirs.rec, LINE_BATCH)?) };
        Ok(Self { det: TextDetector::new(env, &dirs.det, threads)?, lines, names: Recognizer::new(env, &dirs.names, NAME_BATCH)? })
    }

    /// Whether the name reader reads every line.
    pub fn one_reader(&self) -> bool {
        self.lines.is_none()
    }

    /// The reader of the lobby's own lines, in its line batches.
    fn lines(&mut self) -> &mut Recognizer {
        match self.lines.as_mut() {
            Some(lines) => lines,
            None => {
                self.names.set_batch_size(LINE_BATCH);
                &mut self.names
            }
        }
    }

    /// The models in these folders, by kind (see ModelDirs).
    pub fn open(env: &Environment, det: &Path, rec: &Path, names: &Path, threads: usize) -> Result<Self> {
        let dirs = ModelDirs { det: det.into(), rec: rec.into(), names: names.into() };
        Self::new(env, &dirs, threads)
    }

    /// Lines found and sorted into reading order, and each one cut out.
    fn found(&mut self, bgr: &Mat) -> Result<(Vec<Quad>, Vec<Mat>)> {
        let polys = sort_boxes(&self.det.detect(bgr)?.polys);
        if polys.is_empty() {
            return Ok((polys, Vec::new()));
        }
        let crops = crop_by_polys(bgr, &polys)?;
        Ok((polys, crops))
    }

    /// read_bgr (OnnxOcr.predict): every line, read narrowest first, kept in reading order.
    pub fn read_bgr(&mut self, bgr: &Mat) -> Result<Vec<OcrLine>> {
        let (polys, crops) = self.found(bgr)?;
        let pairs: Vec<(&Mat, &Quad)> = crops.iter().zip(&polys).filter(|(c, _)| !c.empty()).collect();
        let ratio = |m: &Mat| f64::from(m.cols()) / f64::from(m.rows());
        let mut order: Vec<usize> = (0..pairs.len()).collect();
        order.sort_by(|&a, &b| ratio(pairs[a].0).total_cmp(&ratio(pairs[b].0)));
        let batch: Vec<Mat> = order.iter().map(|&i| pairs[i].0.clone()).collect();
        let mut reads: Vec<Read> = vec![(String::new(), 0.0); pairs.len()];
        for (&slot, read) in order.iter().zip(self.lines().read(&batch)?) {
            reads[slot] = read;
        }
        Ok(pairs
            .iter()
            .zip(reads)
            .filter(|(_, (text, score))| *score >= REC_SCORE_THRESH && !text.trim().is_empty())
            .map(|((_, quad), (text, score))| OcrLine::new(text, score, quad_box(quad)))
            .collect())
    }

    /// read_crops: lines already cut out (BGR), read as they are.
    pub fn read_crops(&mut self, crops: &[Mat]) -> Result<Vec<Read>> {
        Ok(self.lines().read(crops)?.iter().map(clean).collect())
    }

    /// These lines read, by their index; one that reads as nothing is left out. In the order asked.
    fn read_some(&mut self, indexes: &[usize], boxes: &[[f64; 4]], crops: &[Mat]) -> Result<Vec<(usize, OcrLine)>> {
        let picked: Vec<usize> = indexes.iter().copied().filter(|&i| !crops[i].empty()).collect();
        if picked.is_empty() {
            return Ok(Vec::new());
        }
        let batch: Vec<Mat> = picked.iter().map(|&i| crops[i].clone()).collect();
        let reads = self.lines().read(&batch)?;
        Ok(picked
            .into_iter()
            .zip(reads.iter().map(clean))
            .filter(|(_, (text, score))| !text.is_empty() && *score >= REC_SCORE_THRESH)
            .map(|(i, (text, score))| (i, OcrLine::new(text, score, boxes[i])))
            .collect())
    }

    /// read_lobby_lines: 推演成功 from the tallest few lines, then only the lines where the lobby's header and 准备就绪
    /// sit under it. Empty when no title is among the tallest lines.
    pub fn read_lobby_lines(&mut self, bgr: &Mat) -> Result<Vec<OcrLine>> {
        let (polys, crops) = self.found(bgr)?;
        if polys.is_empty() {
            return Ok(Vec::new());
        }
        let boxes: Vec<[f64; 4]> = polys.iter().map(quad_box).collect();
        let mut shaped: Vec<(f64, usize)> =
            boxes.iter().enumerate().filter_map(|(i, b)| title_shaped(b).map(|h| (h, i))).collect();
        shaped.sort_by(|a, b| b.0.total_cmp(&a.0).then(b.1.cmp(&a.1)));
        let tall: Vec<usize> = shaped.iter().take(LOBBY_TITLE_CANDIDATES).map(|&(_, i)| i).collect();
        let tall_lines = self.read_some(&tall, &boxes, &crops)?;
        let titles: Vec<OcrLine> =
            tall_lines.iter().filter(|(_, l)| l.text.replace(' ', "").contains("推演成功")).map(|(_, l)| l.clone()).collect();
        if titles.is_empty() {
            return Ok(Vec::new());
        }
        let mut wanted: Vec<usize> = Vec::new();
        for title in &titles {
            let [left, top, right, bottom] = title.bbox;
            let (title_h, title_w, middle) = (bottom - top, right - left, (left + right) / 2.0);
            for (i, b) in boxes.iter().enumerate() {
                if *b == title.bbox {
                    continue;
                }
                let dy = ((b[1] + b[3]) / 2.0 - top) / title_h.max(1.0);
                let dx = ((b[0] + b[2]) / 2.0 - middle) / title_w.max(1.0);
                if LOBBY_BANDS.iter().any(|&((low, high), reach)| low <= dy && dy <= high && dx.abs() <= reach) {
                    wanted.push(i);
                }
            }
        }
        wanted.sort_unstable();
        wanted.dedup();
        let known = |i: &usize| tall_lines.iter().find(|(t, _)| t == i).map(|(_, l)| l.clone());
        let mut out = titles;
        out.extend(wanted.iter().filter_map(known));
        let rest: Vec<usize> = wanted.iter().copied().filter(|i| known(i).is_none()).collect();
        out.extend(self.read_some(&rest, &boxes, &crops)?.into_iter().map(|(_, l)| l));
        Ok(out)
    }

    /// read_tallest_lines: every line found, only the tallest `keep` title-shaped ones read.
    pub fn read_tallest_lines(&mut self, bgr: &Mat, keep: usize) -> Result<Vec<OcrLine>> {
        let (polys, crops) = self.found(bgr)?;
        let boxes: Vec<[f64; 4]> = polys.iter().map(quad_box).collect();
        let mut candidates: Vec<(f64, usize)> = (0..polys.len())
            .filter(|&i| !crops[i].empty())
            .filter_map(|i| title_shaped(&boxes[i]).map(|h| (h, i)))
            .collect();
        candidates.sort_by(|a, b| b.0.total_cmp(&a.0));
        let chosen: Vec<usize> = candidates.iter().take(keep).map(|&(_, i)| i).collect();
        Ok(self.read_some(&chosen, &boxes, &crops)?.into_iter().map(|(_, l)| l).collect())
    }

    /// read_names: every name strip (RGB) in one pass.
    pub fn read_names(&mut self, strips: &[Mat]) -> Result<Vec<Read>> {
        self.names.set_batch_size(NAME_BATCH);
        ocr::rec::read_names(&mut self.names, strips)
    }
}
