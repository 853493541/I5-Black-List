//! pyocr: the ocr crate's reader for Python (built with maturin), so the app's own check can run on it and
//! tools/engine_bench.py (engine `rust`) can prove every name reads as blacklist_detect/onnx_ocr.py reads it.
//!
//!     pyocr.init(path to libonnxruntime / onnxruntime.dll)    once per process
//!     Ocr(det_dir, rec_dir, threads).predict(bgr)             OnnxOcr.predict: {rec_texts, rec_scores, rec_polys, rec_boxes}
//!     Detector(det_dir, threads).detect(bgr)                  ([4x2 polys], [scores]): dt_polys, dt_scores
//!     sort_boxes(polys), crop_by_polys(bgr, polys)            the pipeline's sorting and straightened crops
//!     Recognizer(model_dir, batch_size).read([bgr])           [(text, score)]: TextRecognizer
//!     Recognizer.read_names([rgb])                            [(text, score)]: OcrEngine.read_names, preparation included
//!
//! Images are numpy uint8 arrays, H x W x 3, as OpenCV holds them. The sessions use the Python reader's settings:
//! threads as given (PADDLE_PDX_CPU_NUM_THREADS or paths.ocr_threads), denormals as zero, no spinning.
#![forbid(unsafe_code)]

mod convert;

use std::path::PathBuf;
use std::sync::OnceLock;

use numpy::{PyArray3, PyReadonlyArray3};
use ocr::rec::Read;
use ort::environment::Environment;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use convert::{array_of, mat_of, Poly};

static RUNTIME: OnceLock<Environment> = OnceLock::new();

fn err(error: impl std::fmt::Display) -> PyErr {
    PyRuntimeError::new_err(error.to_string())
}

fn runtime() -> PyResult<&'static Environment> {
    RUNTIME.get().ok_or_else(|| err("pyocr.init(<libonnxruntime path>) first"))
}

/// Loads ONNX Runtime from this library file; later calls keep the first.
#[pyfunction]
fn init(library: PathBuf) -> PyResult<()> {
    if RUNTIME.get().is_none() {
        let env = ocr::init_runtime(&library).map_err(err)?;
        let _ = RUNTIME.set(env);
    }
    Ok(())
}

fn polys_out(polys: &[ocr::Quad]) -> Vec<Poly> {
    polys.iter().map(|q| q.map(|p| [p[0] as i32, p[1] as i32])).collect()
}

fn polys_in(polys: Vec<Poly>) -> Vec<ocr::Quad> {
    polys.into_iter().map(|q| q.map(|p| [p[0] as i16, p[1] as i16])).collect()
}

#[pyfunction]
fn sort_boxes(polys: Vec<Poly>) -> Vec<Poly> {
    polys_out(&ocr::sort_boxes(&polys_in(polys)))
}

#[pyfunction]
fn crop_by_polys<'py>(py: Python<'py>, bgr: PyReadonlyArray3<'py, u8>, polys: Vec<Poly>) -> PyResult<Vec<Bound<'py, PyArray3<u8>>>> {
    let crops = ocr::crop_by_polys(&mat_of(&bgr)?, &polys_in(polys)).map_err(err)?;
    crops.iter().map(|crop| array_of(py, crop)).collect()
}

#[pyclass(unsendable)]
struct Detector(ocr::TextDetector);

#[pymethods]
impl Detector {
    #[new]
    fn new(model_dir: PathBuf, threads: usize) -> PyResult<Self> {
        Ok(Self(ocr::TextDetector::new(runtime()?, &model_dir, threads).map_err(err)?))
    }

    /// dt_polys and dt_scores of the BGR frame, with DET_PARAMS.
    fn detect(&mut self, bgr: PyReadonlyArray3<'_, u8>) -> PyResult<(Vec<Poly>, Vec<f64>)> {
        let found = self.0.detect(&mat_of(&bgr)?).map_err(err)?;
        Ok((polys_out(&found.polys), found.scores))
    }
}

#[pyclass(unsendable)]
struct Recognizer(ocr::rec::Recognizer);

#[pymethods]
impl Recognizer {
    /// Threads come from PADDLE_PDX_CPU_NUM_THREADS, else one per core (2 to 8), as onnx_ocr.session().
    #[new]
    fn new(model_dir: PathBuf, batch_size: usize) -> PyResult<Self> {
        Ok(Self(ocr::rec::Recognizer::new(runtime()?, &model_dir, batch_size).map_err(err)?))
    }

    /// TextRecognizer: every BGR line read, in batches, in order.
    fn read(&mut self, images: Vec<PyReadonlyArray3<'_, u8>>) -> PyResult<Vec<Read>> {
        let mats = images.iter().map(mat_of).collect::<PyResult<Vec<_>>>()?;
        self.0.read(&mats).map_err(err)
    }

    /// OcrEngine.read_names: each RGB name strip prepared, read, and read again plain when blank.
    fn read_names(&mut self, images: Vec<PyReadonlyArray3<'_, u8>>) -> PyResult<Vec<Read>> {
        let mats = images.iter().map(mat_of).collect::<PyResult<Vec<_>>>()?;
        ocr::rec::read_names(&mut self.0, &mats).map_err(err)
    }
}

#[pyclass(unsendable)]
struct Ocr(ocr::read::Ocr);

#[pymethods]
impl Ocr {
    #[new]
    fn new(det_dir: PathBuf, rec_dir: PathBuf, threads: usize) -> PyResult<Self> {
        Ok(Self(ocr::read::Ocr::new(runtime()?, &det_dir, &rec_dir, threads).map_err(err)?))
    }

    /// OnnxOcr.predict's one result: rec_texts, rec_scores, rec_polys (4 x 2) and rec_boxes.
    fn predict<'py>(&mut self, py: Python<'py>, bgr: PyReadonlyArray3<'py, u8>) -> PyResult<Bound<'py, PyDict>> {
        let lines = self.0.predict(&mat_of(&bgr)?).map_err(err)?;
        let out = PyDict::new(py);
        out.set_item("rec_texts", lines.iter().map(|l| l.text.clone()).collect::<Vec<_>>())?;
        out.set_item("rec_scores", lines.iter().map(|l| l.score).collect::<Vec<_>>())?;
        out.set_item("rec_polys", polys_out(&lines.iter().map(|l| l.poly).collect::<Vec<_>>()))?;
        out.set_item("rec_boxes", lines.iter().map(|l| l.bbox).collect::<Vec<_>>())?;
        Ok(out)
    }

    /// The line recognizer, for reading crops on their own (OcrEngine.read_crops and read_lobby_lines).
    fn read(&mut self, images: Vec<PyReadonlyArray3<'_, u8>>) -> PyResult<Vec<Read>> {
        let mats = images.iter().map(mat_of).collect::<PyResult<Vec<_>>>()?;
        self.0.rec.read(&mats).map_err(err)
    }

    fn detect(&mut self, bgr: PyReadonlyArray3<'_, u8>) -> PyResult<(Vec<Poly>, Vec<f64>)> {
        let found = self.0.det.detect(&mat_of(&bgr)?).map_err(err)?;
        Ok((polys_out(&found.polys), found.scores))
    }
}

#[pymodule]
fn pyocr(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(init, module)?)?;
    module.add_function(wrap_pyfunction!(sort_boxes, module)?)?;
    module.add_function(wrap_pyfunction!(crop_by_polys, module)?)?;
    module.add_class::<Detector>()?;
    module.add_class::<Recognizer>()?;
    module.add_class::<Ocr>()?;
    Ok(())
}
