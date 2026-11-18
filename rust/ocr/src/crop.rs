//! The OCR pipeline's SortQuadBoxes and CropByPolys of onnx_ocr.py.

use opencv::core::{Mat, Point, Point2f, Scalar, Size, Vector, BORDER_REPLICATE, DECOMP_LU, ROTATE_90_COUNTERCLOCKWISE};
use opencv::imgproc;
use opencv::prelude::*;

use crate::db::{ordered_corners, rect_points, Quad};
use crate::Result;

/// Top to bottom, then left to right within 10 px of height.
pub fn sort_boxes(polys: &[Quad]) -> Vec<Quad> {
    let mut boxes = polys.to_vec();
    boxes.sort_by_key(|b| (b[0][1], b[0][0]));
    for i in 0..boxes.len().saturating_sub(1) {
        for j in (0..=i).rev() {
            if (boxes[j + 1][0][1] as i32 - boxes[j][0][1] as i32).abs() < 10 && boxes[j + 1][0][0] < boxes[j][0][0] {
                boxes.swap(j, j + 1);
            } else {
                break;
            }
        }
    }
    boxes
}

/// Each box's minimum-area rectangle, straightened out of the BGR image.
pub fn crop_by_polys(img: &Mat, polys: &[Quad]) -> Result<Vec<Mat>> {
    polys
        .iter()
        .map(|poly| {
            let points: Vector<Point> = poly.iter().map(|p| Point::new(p[0] as i32, p[1] as i32)).collect();
            rotate_crop(img, &ordered_corners(rect_points(&imgproc::min_area_rect(&points)?)?))
        })
        .collect()
}

/// The quad warped to an upright rectangle (bicubic, edges replicated); tall crops turned a quarter left.
pub fn rotate_crop(img: &Mat, points: &[Point2f; 4]) -> Result<Mat> {
    // np.linalg.norm on float32 points: the sum of squares and its root in float32.
    let norm = |a: Point2f, b: Point2f| {
        let (dx, dy) = (a.x - b.x, a.y - b.y);
        (dx * dx + dy * dy).sqrt()
    };
    let width = norm(points[0], points[1]).max(norm(points[2], points[3])) as i32;
    let height = norm(points[0], points[3]).max(norm(points[1], points[2])) as i32;
    let (wf, hf) = (width as f32, height as f32);
    let src: Vector<Point2f> = Vector::from_iter(points.iter().copied());
    let dst: Vector<Point2f> =
        Vector::from_iter([Point2f::new(0.0, 0.0), Point2f::new(wf, 0.0), Point2f::new(wf, hf), Point2f::new(0.0, hf)]);
    let matrix = imgproc::get_perspective_transform(&src, &dst, DECOMP_LU)?;
    let mut crop = Mat::default();
    let size = Size::new(width, height);
    imgproc::warp_perspective(img, &mut crop, &matrix, size, imgproc::INTER_CUBIC, BORDER_REPLICATE, Scalar::default())?;
    if crop.rows() as f64 / crop.cols() as f64 >= 1.5 {
        let mut turned = Mat::default();
        opencv::core::rotate(&crop, &mut turned, ROTATE_90_COUNTERCLOCKWISE)?;
        crop = turned;
    }
    Ok(crop)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn quad(x: i16, y: i16) -> Quad {
        [[x, y], [x + 20, y], [x + 20, y + 8], [x, y + 8]]
    }

    #[test]
    fn boxes_read_top_to_bottom_then_left_to_right_within_ten_pixels() {
        let got = sort_boxes(&[quad(50, 3), quad(10, 40), quad(5, 0), quad(80, 12)]);
        assert_eq!(got, vec![quad(5, 0), quad(50, 3), quad(80, 12), quad(10, 40)]);
    }

    #[test]
    fn a_tall_crop_turns_a_quarter_left() {
        let img = Mat::new_rows_cols_with_default(100, 100, opencv::core::CV_8UC3, Scalar::all(7.0)).unwrap();
        let crops = crop_by_polys(&img, &[[[10, 10], [20, 10], [20, 60], [10, 60]]]).unwrap();
        assert_eq!((crops[0].rows(), crops[0].cols()), (10, 50));
    }
}
