//! Debug: fillPoly on the integer polygons /tmp/fillpoly.json holds, against the masks cv2 4.10 drew for them.
use opencv::core::{Mat, Point, Scalar, Vector, CV_8U};
use opencv::prelude::*;

fn main() {
    let cases: Vec<serde_json::Value> = serde_json::from_str(&std::fs::read_to_string("/tmp/fillpoly.json").unwrap()).unwrap();
    let mut differ = 0;
    for case in &cases {
        let poly: Vec<[i32; 2]> = serde_json::from_value(case["poly"].clone()).unwrap();
        let (h, w) = (case["h"].as_i64().unwrap() as i32, case["w"].as_i64().unwrap() as i32);
        let mut mask = Mat::zeros(h, w, CV_8U).unwrap().to_mat().unwrap();
        let pts: Vector<Point> = poly.iter().map(|p| Point::new(p[0], p[1])).collect();
        let polys: Vector<Vector<Point>> = Vector::from_iter([pts]);
        opencv::imgproc::fill_poly(&mut mask, &polys, Scalar::all(1.0), opencv::imgproc::LINE_8, 0, Point::default()).unwrap();
        let sum = mask.data_bytes().unwrap().iter().map(|&v| v as i64).sum::<i64>();
        if sum != case["sum"].as_i64().unwrap() {
            differ += 1;
            if differ <= 3 {
                let rows: Vec<i64> = (0..h).map(|r| (0..w).map(|c| *mask.at_2d::<u8>(r, c).unwrap() as i64).sum()).collect();
                println!("poly {poly:?}: 4.6 sum {sum}, 4.10 sum {}\n  4.6  rows {rows:?}\n  4.10 rows {}", case["sum"], case["rows"]);
            }
        }
    }
    println!("{differ} of {} masks differ; opencv {}", cases.len(), opencv::core::get_version_string().unwrap());
}
