//! DBPostProcess of onnx_ocr.py: quad boxes, fast score, the Clipper unclip.

use opencv::core::{Mat, Point, Point2f, Rect, RotatedRect, Scalar, Vector, CV_32F, CV_8U};
use opencv::imgproc;
use opencv::prelude::*;

use crate::clip::offset_round;
use crate::Result;

/// A box's four corners, (x, y), as int16 like the Python app's dt_polys.
pub type Quad = [[i16; 2]; 4];

pub const MAX_CANDIDATES: usize = 1000;
pub const MIN_SIZE: f32 = 3.0;

/// The boxes (in the source image's pixels) and their scores, from the model's probability map `pred` (h x w).
pub fn db_boxes(pred: &[f32], h: usize, w: usize, shape: [f64; 4], thresh: f64, box_thresh: f64, unclip_ratio: f64)
    -> Result<(Vec<Quad>, Vec<f64>)> {
    let (src_h, src_w) = (shape[0], shape[1]);
    let (width_scale, height_scale) = (src_w / w as f64, src_h / h as f64);
    let thresh = thresh as f32;
    let bitmap: Vec<u8> = pred.iter().map(|&v| if v > thresh { 255 } else { 0 }).collect();
    let bitmap = Mat::new_rows_cols_with_data(h as i32, w as i32, &bitmap)?.try_clone()?;
    let pred_mat = Mat::new_rows_cols_with_data(h as i32, w as i32, pred)?.try_clone()?;
    let mut contours: Vector<Vector<Point>> = Vector::new();
    imgproc::find_contours(&bitmap, &mut contours, imgproc::RETR_LIST, imgproc::CHAIN_APPROX_SIMPLE, Point::default())?;
    let (mut boxes, mut scores) = (Vec::new(), Vec::new());
    for contour in contours.iter().take(MAX_CANDIDATES) {
        let (points, sside) = mini_box(&contour)?;
        if sside < MIN_SIZE {
            continue;
        }
        let score = box_score_fast(&pred_mat, &points)?;
        if box_thresh > score {
            continue;
        }
        let Some(expanded) = unclip(&points, unclip_ratio)? else { continue };
        let (corners, sside) = mini_box(&expanded)?;
        if sside < MIN_SIZE + 2.0 {
            continue;
        }
        let scale = |v: f32, by: f64, limit: f64| (v as f64 * by).round_ties_even().min(limit).max(0.0) as i16;
        boxes.push(corners.map(|p| [scale(p.x, width_scale, src_w), scale(p.y, height_scale, src_h)]));
        scores.push(score);
    }
    Ok((boxes, scores))
}

/// The minimum-area rectangle's corners in order (top left, top right, bottom right, bottom left) and its short side.
pub fn mini_box(contour: &Vector<Point>) -> Result<([Point2f; 4], f32)> {
    let rect = imgproc::min_area_rect(contour)?;
    Ok((ordered_corners(rect_points(&rect)?), rect.size.width.min(rect.size.height)))
}

pub(crate) fn rect_points(rect: &RotatedRect) -> Result<[Point2f; 4]> {
    let mut pts = [Point2f::default(); 4];
    rect.points(&mut pts)?;
    Ok(pts)
}

/// Four corners sorted by x (stably), put in order: top left, top right, bottom right, bottom left.
pub fn ordered_corners(points: [Point2f; 4]) -> [Point2f; 4] {
    let mut points = points;
    points.sort_by(|a, b| a.x.partial_cmp(&b.x).unwrap_or(std::cmp::Ordering::Equal));
    let (first, fourth) = if points[1].y > points[0].y { (0, 1) } else { (1, 0) };
    let (second, third) = if points[3].y > points[2].y { (2, 3) } else { (3, 2) };
    [points[first], points[second], points[third], points[fourth]]
}

/// The mean of `pred` inside the box, over the box's bounding rectangle.
pub fn box_score_fast(pred: &Mat, points: &[Point2f; 4]) -> Result<f64> {
    let (h, w) = (pred.rows(), pred.cols());
    let clamp = |v: f32, hi: i32| (v as i64).clamp(0, hi as i64) as i32;
    let fold = |pick: fn(&Point2f) -> f32, min: bool| {
        points.iter().map(pick).fold(if min { f32::INFINITY } else { f32::NEG_INFINITY }, if min { f32::min } else { f32::max })
    };
    let xmin = clamp(fold(|p| p.x, true).floor(), w - 1);
    let xmax = clamp(fold(|p| p.x, false).ceil(), w - 1);
    let ymin = clamp(fold(|p| p.y, true).floor(), h - 1);
    let ymax = clamp(fold(|p| p.y, false).ceil(), h - 1);
    let mut mask = Mat::zeros(ymax - ymin + 1, xmax - xmin + 1, CV_8U)?.to_mat()?;
    let shifted: Vector<Point> =
        points.iter().map(|p| Point::new((p.x - xmin as f32) as i32, (p.y - ymin as f32) as i32)).collect();
    let polys: Vector<Vector<Point>> = Vector::from_iter([shifted]);
    imgproc::fill_poly(&mut mask, &polys, Scalar::all(1.0), imgproc::LINE_8, 0, Point::default())?;
    let roi = Mat::roi(pred, Rect::new(xmin, ymin, xmax - xmin + 1, ymax - ymin + 1))?;
    debug_assert_eq!(roi.typ(), CV_32F);
    Ok(opencv::core::mean(&roi, &mask)?[0])
}

/// The box grown by area * ratio / perimeter with round joins, as pyclipper offsets it. None when nothing is left.
pub fn unclip(points: &[Point2f; 4], unclip_ratio: f64) -> Result<Option<Vector<Point>>> {
    let contour: Vector<Point2f> = Vector::from_iter(points.iter().copied());
    let distance = imgproc::contour_area(&contour, false)? * unclip_ratio / imgproc::arc_length(&contour, true)?;
    // pyclipper turns each float coordinate into an integer by truncation.
    let path: Vec<[i64; 2]> = points.iter().map(|p| [p.x as i64, p.y as i64]).collect();
    let paths = offset_round(&path, distance);
    // np.array(paths) keeps every path when they are the same length; ragged, onnx_ocr.py falls back to the first.
    let same = paths.iter().all(|p| p.len() == paths[0].len());
    let kept: Vec<[i64; 2]> = if same { paths.concat() } else { paths[0].clone() };
    if kept.is_empty() {
        return Ok(None);
    }
    Ok(Some(kept.iter().map(|p| Point::new(p[0] as i32, p[1] as i32)).collect()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn corners_come_in_reading_order() {
        let p = |x, y| Point2f::new(x, y);
        let got = ordered_corners([p(10.0, 0.0), p(0.0, 5.0), p(0.0, 0.0), p(10.0, 5.0)]);
        assert_eq!(got, [p(0.0, 0.0), p(10.0, 0.0), p(10.0, 5.0), p(0.0, 5.0)]);
    }

    #[test]
    fn unclip_grows_a_box_by_its_area_over_its_perimeter() {
        let p = |x, y| Point2f::new(x, y);
        let grown = unclip(&[p(10.0, 10.0), p(50.0, 10.0), p(50.0, 20.0), p(10.0, 20.0)], 1.5).unwrap().unwrap();
        let rect = imgproc::bounding_rect(&grown).unwrap();
        // distance = 400 * 1.5 / 100 = 6 on every side.
        assert_eq!((rect.x, rect.y, rect.width, rect.height), (4, 4, 53, 23));
    }

    #[test]
    fn a_tiny_blob_gives_no_box() {
        let mut pred = vec![0f32; 32 * 32];
        pred[5 * 32 + 5] = 0.9;
        let (boxes, scores) = db_boxes(&pred, 32, 32, [32.0, 32.0, 1.0, 1.0], 0.3, 0.6, 1.5).unwrap();
        assert!(boxes.is_empty() && scores.is_empty());
    }
}
