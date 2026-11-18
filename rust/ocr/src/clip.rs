//! The thin FFI edge to Clipper 1 (6.4.2, the library pyclipper wraps): one polygon offset.
#![allow(unsafe_code)]

use clipper_sys::{
    free_polygons, offset, EndType_etClosedPolygon, JoinType_jtRound, Path, PolyType_ptSubject, Polygon, Polygons,
    Vertice,
};

/// pyclipper.PyclipperOffset's defaults.
const MITER_LIMIT: f64 = 2.0;
const ARC_TOLERANCE: f64 = 0.25;

/// PyclipperOffset().AddPath(points, JT_ROUND, ET_CLOSEDPOLYGON) then Execute(delta): the offset paths.
/// The points are integers already, as pyclipper truncates them.
pub fn offset_round(points: &[[i64; 2]], delta: f64) -> Vec<Vec<[i64; 2]>> {
    let mut vertices: Vec<Vertice> = points.to_vec();
    let mut path = Path { vertices: vertices.as_mut_ptr(), vertices_count: vertices.len(), closed: 1 };
    let mut polygon = Polygon { paths: &mut path, paths_count: 1, type_: PolyType_ptSubject };
    let input = Polygons { polygons: &mut polygon, polygons_count: 1 };
    // SAFETY: the input borrows live buffers for the call only; Clipper copies them. The output is owned by the
    // library, read whole into Rust vectors, then handed back to free_polygons once.
    unsafe {
        let out = offset(MITER_LIMIT, ARC_TOLERANCE, JoinType_jtRound, EndType_etClosedPolygon, input, delta);
        let mut paths = Vec::new();
        for polygon in std::slice::from_raw_parts(out.polygons, out.polygons_count) {
            for path in std::slice::from_raw_parts(polygon.paths, polygon.paths_count) {
                paths.push(std::slice::from_raw_parts(path.vertices, path.vertices_count).to_vec());
            }
        }
        free_polygons(out);
        paths
    }
}
