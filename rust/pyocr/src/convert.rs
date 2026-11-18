//! numpy uint8 H x W x C arrays to OpenCV Mats and back, byte for byte.

use numpy::{PyArray1, PyArray3, PyArrayMethods, PyReadonlyArray3, PyUntypedArrayMethods};
use opencv::core::{Mat, CV_8UC};
use opencv::prelude::*;
use pyo3::prelude::*;

use super::err;

/// A quad as Python lists: [[x, y], ...] four times.
pub type Poly = [[i32; 2]; 4];

pub fn mat_of(array: &PyReadonlyArray3<'_, u8>) -> PyResult<Mat> {
    let shape = array.shape();
    let (rows, cols, channels) = (shape[0] as i32, shape[1] as i32, shape[2] as i32);
    let data = array.as_slice().map(<[u8]>::to_vec).unwrap_or_else(|_| array.as_array().iter().copied().collect());
    ocr::rec::prepare::mat_from(rows, cols, CV_8UC(channels), &data).map_err(err)
}

pub fn array_of<'py>(py: Python<'py>, mat: &Mat) -> PyResult<Bound<'py, PyArray3<u8>>> {
    let (rows, cols, channels) = (mat.rows() as usize, mat.cols() as usize, mat.channels() as usize);
    let data = ocr::rec::prepare::bytes(mat).map_err(err)?;
    PyArray1::from_vec(py, data).reshape([rows, cols, channels])
}
