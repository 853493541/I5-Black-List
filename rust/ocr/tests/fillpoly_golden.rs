//! cv2.fillPoly's masks against the linked OpenCV's. OpenCV 4.6 draws some slanted quads a pixel differently from
//! the 4.10 the Python app runs, which moves box scores (README). FILLPOLY_GOLDEN names the fillpoly.json that
//! tools/rust_golden_ipp.py writes; without it the test says so and passes.

use opencv::core::{Mat, Point, Scalar, Vector, CV_8U};
use opencv::imgproc;
use opencv::prelude::*;
use serde_json::Value;

#[test]
fn fill_poly_matches_python() {
    let Ok(path) = std::env::var("FILLPOLY_GOLDEN") else {
        eprintln!("skipped: FILLPOLY_GOLDEN is not set");
        return;
    };
    let cases: Vec<Value> = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    let mut differ = Vec::new();
    for case in &cases {
        let poly: Vec<[i32; 2]> = serde_json::from_value(case["poly"].clone()).unwrap();
        let (h, w) = (case["h"].as_i64().unwrap() as i32, case["w"].as_i64().unwrap() as i32);
        let mut mask = Mat::zeros(h, w, CV_8U).unwrap().to_mat().unwrap();
        let points: Vector<Point> = poly.iter().map(|p| Point::new(p[0], p[1])).collect();
        let polys: Vector<Vector<Point>> = Vector::from_iter([points]);
        imgproc::fill_poly(&mut mask, &polys, Scalar::all(1.0), imgproc::LINE_8, 0, Point::default()).unwrap();
        let rows: Vec<i64> = (0..h).map(|r| (0..w).map(|c| *mask.at_2d::<u8>(r, c).unwrap() as i64).sum()).collect();
        let want: Vec<i64> = serde_json::from_value(case["rows"].clone()).unwrap();
        if rows != want {
            let (got, sum) = (rows.iter().sum::<i64>(), case["sum"].as_i64().unwrap());
            differ.push(format!("{poly:?}: {got} pixels, Python {sum}"));
        }
    }
    let version = opencv::core::get_version_string().unwrap();
    eprintln!("OpenCV {version}, IPP in use: {} ({})", opencv::core::use_ipp().unwrap(), opencv::core::get_ipp_version().unwrap());
    assert!(cases.len() >= 100, "only {} masks", cases.len());
    assert!(differ.is_empty(), "{} of {} masks differ on OpenCV {version}: {:?}", differ.len(), cases.len(), &differ[..differ.len().min(5)]);
}
