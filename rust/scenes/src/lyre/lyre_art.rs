//! The lyre Der Frühling (斐林) shaded per pixel, its strummed aura and a ringing string (lyre.py's
//! _lyre_parts, _lyre_image, _aura, _string_glow). Drawn in the reference picture's pixels ("ref").

use super::img::{self, lerp3, noise, over, picture, relief, rgb, scale3, smooth, Color, Map, Pic, Rgb};
use super::raster::{cubic, ellipse, filled, quad, rect, rounded_rect, Canvas, Cap, Pt, Shape};
use super::sprites::local_light;
use super::wind::{bezier, normals};
use super::{ANEMO_TEAL, CX, CY, MINT, PINE, STRING_X, STRING_Y};

const WOOD: [(f32, &str); 6] = [(-0.2, "#4a2c20"), (0.15, "#6e4836"), (0.45, "#956450"), (0.7, "#a8765f"), (0.92, "#bf8e72"), (1.2, "#dcb298")];
const GOLD: [(f32, &str); 5] = [(-0.1, "#6a4e28"), (0.25, "#a8843f"), (0.55, "#d6b26c"), (0.85, "#f0d79e"), (1.15, "#fff6dc")];
const GEM: [(f32, &str); 4] = [(0.0, "#0a4a44"), (0.4, "#14897a"), (0.75, "#2fc0aa"), (1.05, "#b9f6e8")];
const LEAF: [(f32, &str); 4] = [(0.0, "#3a5428"), (0.4, "#62803f"), (0.75, "#8aa55a"), (1.05, "#bfd08d")];
const BRIDGE: [(f32, &str); 4] = [(0.0, "#5e4a30"), (0.45, "#9c875f"), (0.85, "#d2c196"), (1.15, "#f1e8cc")];
const OUTLINE: &str = "#2e1a12";
const OUTER: [Pt; 23] = [[80.0, 9.0], [82.0, 22.0], [84.0, 34.0], [86.0, 48.0], [86.0, 64.0], [83.0, 80.0], [79.0, 96.0], [74.0, 112.0], [69.0, 128.0],
    [64.0, 144.0], [59.0, 160.0], [55.0, 176.0], [51.0, 192.0], [49.0, 208.0], [48.0, 224.0], [49.0, 240.0], [51.0, 256.0], [56.0, 272.0],
    [64.0, 288.0], [76.0, 304.0], [93.0, 320.0], [107.0, 330.0], [121.0, 337.0]];
const INNER: [Pt; 20] = [[80.0, 9.0], [86.0, 19.0], [91.0, 28.0], [95.0, 37.0], [98.0, 47.0], [100.0, 58.0], [101.0, 70.0], [101.0, 84.0], [100.0, 98.0],
    [98.0, 112.0], [95.0, 128.0], [92.0, 144.0], [89.0, 160.0], [87.0, 176.0], [85.0, 192.0], [86.0, 206.0], [89.0, 219.0], [96.0, 229.0],
    [106.0, 234.0], [114.0, 235.0]];
const BLADE_TOP: [Pt; 6] = [[57.0, 220.0], [78.0, 231.0], [100.0, 245.0], [119.0, 260.0], [133.0, 276.0], [142.0, 294.0]];
const BLADE_LOW: [Pt; 9] = [[131.0, 290.0], [127.0, 285.0], [107.0, 304.0], [112.0, 276.0], [101.0, 267.0], [82.0, 295.0], [86.0, 256.0], [77.0, 248.0], [67.0, 238.0]];
const BLADE_SMALL: [Pt; 8] = [[149.0, 300.0], [131.0, 302.0], [114.0, 309.0], [128.0, 310.0], [134.0, 314.0], [141.0, 325.0], [143.0, 313.0], [148.0, 309.0]];
const LEAVES: [(Pt, Pt, Pt, f64); 3] = [([262.0, 196.0], [300.0, 170.0], [318.0, 112.0], 12.5), ([240.0, 178.0], [244.0, 160.0], [252.0, 140.0], 8.0),
    ([258.0, 236.0], [288.0, 228.0], [311.0, 213.0], 8.0)];
type Petal = (f64, f64, f64);
const LILIES: [(Pt, [Petal; 6]); 2] = [
    ([249.0, 183.0], [(-70.0, 46.0, 0.5), (-133.0, 42.0, 0.5), (0.0, 48.0, 0.55), (95.0, 38.0, 0.5), (41.0, 44.0, 0.58), (164.0, 52.0, 0.66)]),
    ([223.0, 236.0], [(-62.0, 36.0, 0.5), (-127.0, 38.0, 0.52), (131.0, 42.0, 0.55), (0.0, 48.0, 0.62), (190.0, 48.0, 0.66), (64.0, 66.0, 0.34)]),
];
const PEG_X: [f64; 7] = [129.3, 138.1, 146.9, 155.7, 164.5, 173.3, 182.1];

fn spline(points: &[Pt], n: usize) -> Vec<Pt> {
    let mut pts = vec![[points[0][0] * 2.0 - points[1][0], points[0][1] * 2.0 - points[1][1]]];
    pts.extend_from_slice(points);
    let (a, b) = (points[points.len() - 1], points[points.len() - 2]);
    pts.push([a[0] * 2.0 - b[0], a[1] * 2.0 - b[1]]);
    let mut out = Vec::new();
    for i in 1..pts.len() - 2 {
        let (p0, p1, p2, p3) = (pts[i - 1], pts[i], pts[i + 1], pts[i + 2]);
        for s in 0..n {
            let t = s as f64 / n as f64;
            out.push([0, 1].map(|k| 0.5 * (2.0 * p1[k] + (p2[k] - p0[k]) * t + (2.0 * p0[k] - 5.0 * p1[k] + 4.0 * p2[k] - p3[k]) * t * t + (3.0 * p1[k] - p0[k] - 3.0 * p2[k] + p3[k]) * t.powi(3))));
        }
    }
    out.push(pts[pts.len() - 2]);
    out
}

fn mirror(points: &[Pt]) -> Vec<Pt> {
    points.iter().map(|p| [2.0 * CX - p[0], p[1]]).collect()
}

fn rf(points: &[Pt]) -> Vec<Pt> {
    points.iter().map(|p| [p[0] - CX, p[1] - CY]).collect()
}

fn r(x: f64, y: f64) -> Pt {
    [x - CX, y - CY]
}

struct Parts {
    shapes: Vec<(&'static str, Shape)>,
    carving: Vec<Vec<Pt>>,
    faces: Vec<Vec<Pt>>,
}

fn parts() -> Parts {
    let (outer, inner) = (spline(&OUTER, 10), spline(&INNER, 10));
    let mut body: Vec<Pt> = outer.clone();
    body.extend(mirror(&outer).into_iter().rev());
    body.extend(mirror(&inner));
    body.extend([[196.0, 235.0], [191.0, 216.0], [119.0, 216.0], [114.0, 235.0]]);
    body.extend(inner.iter().rev());
    let rr = |x0: f64, y0: f64, x1: f64, y1: f64, k: f64| rounded_rect(x0 - CX, y0 - CY, x1 - CX, y1 - CY, k);
    let rod_poly = rf(&[[44.0, 52.0], [58.0, 46.5], [68.0, 46.0], [72.0, 48.5], [72.0, 56.0], [68.0, 58.0], [58.0, 57.5]]);
    let rod = Shape::winding(vec![rr(74.0, 46.5, 238.0, 57.5, 3.0), rod_poly, rect(238.0 - CX, 48.8 - CY, 241.0 - CX, 55.6 - CY)]);
    let star: Vec<Pt> = (0..16)
        .map(|i| {
            let a = (-90.0 + 22.5 * f64::from(i)).to_radians();
            let rad = if i % 2 == 1 { 12.5 } else { [31.0, 19.0, 22.0, 19.0, 34.0, 19.0, 22.0, 19.0][(i / 2) as usize] };
            r(155.0 + rad * a.cos(), 263.0 + rad * a.sin())
        })
        .collect();
    let gem_at = r(155.0, 263.0);
    let mut blade_main = spline(&BLADE_TOP, 8);
    blade_main.extend_from_slice(&BLADE_LOW);
    let mut blades = Vec::new();
    for pts in [blade_main, BLADE_SMALL.to_vec()] {
        blades.push(rf(&pts));
        blades.push(rf(&mirror(&pts)));
    }
    let top = spline(&BLADE_TOP, 8);
    let n = top.len();
    let mut facet_pts = top.clone();
    facet_pts.extend((0..n).rev().map(|i| {
        let s = (std::f64::consts::PI * i as f64 / (n - 1) as f64).sin().powf(0.7);
        [top[i][0] + s * 1.5, top[i][1] + s * 6.0]
    }));
    let facet = Shape::odd(vec![rf(&facet_pts), rf(&mirror(&facet_pts))]);
    let mut carving = Vec::new();
    for side in [1.0, -1.0] {
        let q = |x: f64, y: f64| r(CX + side * (x - CX), y);
        for (x0, y0, xm, ym, x1, y1) in [(92.0, 66.0, 99.0, 90.0, 92.0, 114.0), (75.0, 150.0, 86.0, 168.0, 70.0, 196.0)] {
            let mut loop_ = quad(q(x0, y0), q(xm + 4.0, ym), q(x1, y1), 16);
            loop_.extend(quad(q(x1, y1), q(xm - 6.0, ym), q(x0, y0), 16).into_iter().skip(1));
            carving.push(loop_);
            carving.push(quad(q(x0 + 0.5, y0 + 6.0), q(xm - 1.0, ym), q(x1, y1 - 5.0), 16));
        }
        let mut c = cubic(q(58.0, 232.0), q(64.0, 214.0), q(80.0, 214.0), q(78.0, 228.0), 16);
        c.extend(cubic(q(78.0, 228.0), q(76.0, 236.0), q(68.0, 234.0), q(70.0, 228.0), 16).into_iter().skip(1));
        carving.push(c);
        for (x1, y1) in [(84.0, 104.0), (100.0, 104.0)] {
            let mut s = quad(q(92.0, 92.0), q((92.0 + x1) / 2.0 + 3.0, (92.0 + y1) / 2.0 - 3.0), q(x1, y1), 12);
            s.extend(quad(q(x1, y1), q((92.0 + x1) / 2.0 - 3.0, (92.0 + y1) / 2.0 + 3.0), q(92.0, 92.0), 12).into_iter().skip(1));
            carving.push(s);
        }
    }
    let faces = [inner.clone(), mirror(&inner)].iter().map(|pts| rf(&pts[3..pts.len() - 3])).collect();
    let shapes = vec![
        ("body", Shape::odd(vec![rf(&body)])),
        ("foot", Shape::odd(vec![rect(120.0 - CX, 332.0 - CY, 190.0 - CX, 348.0 - CY)])),
        ("base", Shape::odd(vec![rr(108.0, 347.0, 202.0, 366.0, 3.0)])),
        ("bridge", Shape::odd(vec![rr(115.0, 206.5, 195.0, 216.0, 2.0)])),
        ("rod", rod),
        ("cap", Shape::odd(vec![{ let c = r(248.5, 52.2); ellipse(c[0], c[1], 8.5, 5.0, 48) }])),
        ("collars", Shape::odd([71.5, 233.5].iter().map(|&x| rr(x, 45.5, x + 5.0, 59.0, 1.5)).collect())),
        ("pegs", Shape::odd(PEG_X.iter().map(|&x| { let c = r(x, 41.2); ellipse(c[0], c[1], 2.8, 4.6, 32) }).collect())),
        ("setting", Shape::winding(vec![star, ellipse(gem_at[0], gem_at[1], 15.0, 18.5, 64)])),
        ("gem", Shape::odd(vec![ellipse(gem_at[0], gem_at[1], 10.5, 13.5, 64)])),
        ("blades", Shape::winding(blades)),
        ("facet", facet),
    ];
    Parts { shapes, carving, faces }
}

fn petal_points(ln: f64, a: f64, wf: f64) -> Vec<Pt> {
    let (d, n, w) = ([a.cos(), a.sin()], [-a.sin(), a.cos()], wf * ln);
    let p = |s: f64, t: f64| [d[0] * s * ln + n[0] * t * w, d[1] * s * ln + n[1] * t * w];
    let mut out = bezier([0.0, 0.0], p(0.12, 1.0), p(0.62, 0.7), p(1.0, 0.0), 24);
    out.extend(bezier(p(1.0, 0.0), p(0.62, -0.62), p(0.12, -1.0), [0.0, 0.0], 24).into_iter().skip(1));
    out
}

fn side(ppr: f64) -> usize {
    ((450.0 * ppr) as usize) / 2 * 2
}

pub fn lyre_image(angle: f64, ppr: f64, halo: bool) -> Pic {
    let p = parts();
    let size = side(ppr);
    let half = size as f64 / 2.0;
    let light = local_light(angle, 1.0);
    let get = |name: &str| p.shapes.iter().find(|s| s.0 == name).map(|s| s.1.clone()).unwrap_or_default();
    let fill = |s: &Shape| filled(&s.placed(half, half, ppr), size, size);
    let stroked = |lines: &[Vec<Pt>], width: f64, off: Pt| {
        let mut c = Canvas::new(size, size);
        let moved: Vec<Vec<Pt>> = lines.iter().map(|l| l.iter().map(|q| [half + off[0] * ppr + q[0] * ppr, half + off[1] * ppr + q[1] * ppr]).collect()).collect();
        for l in moved {
            c.stroke(&[l], width * ppr, Cap::Round, 1.0);
        }
        c.done()
    };
    let (pf, hf) = (ppr as f32, half as f32);
    let cxy = |i: usize| {
        let (x, y) = img::xy_of(size, i);
        ((x - hf) / pf + CX as f32, (y - hf) / pf + CY as f32)
    };
    let lit = |m: &Map, sigma: f64, gain: f32| relief(&m.blur(sigma * ppr).zip(m, |b, m| b * m * 10.0 * pf), gain, light);
    let edge = |m: &Map| m.blur(0.8 * ppr).zip(m, |b, m| (1.0 - b * 1.8).clamp(0.0, 1.0) * m);
    let rim = |m: &Map, sigma: f64, k: f32| m.blur(sigma * ppr).map(|v| (v * k).clamp(0.0, 1.0));
    let clip1 = |a: &Map, b: &Map| a.zip(b, |x, y| (x + y).clamp(0.0, 1.0));
    let m_body = clip1(&fill(&get("body")), &fill(&get("foot")));
    let (m_base, m_bridge, m_rod) = (fill(&get("base")), fill(&get("bridge")), fill(&get("rod")));
    let (m_collar, m_pegs, m_cap) = (fill(&get("collars")), fill(&get("pegs")), fill(&get("cap")));
    let (m_set, m_gem, m_blade) = (fill(&get("setting")), fill(&get("gem")), fill(&get("blades")));
    let whole = clip1(&clip1(&clip1(&m_body, &m_base), &clip1(&m_rod, &m_pegs)), &m_cap);
    let wood = |m: &Map, sigma: f64, k0: f32| {
        let (d, sp) = lit(m, sigma, 1.6);
        Color::from_fn(size, size, |i| {
            let (cx, cy) = cxy(i);
            let k = k0 - 0.2 + 1.12 * d.v[i] - 0.0012 * (cx - CX as f32) - 0.0009 * (cy - CY as f32);
            img::add3(img::ramp(&WOOD, k), [sp.v[i] * 0.1; 3])
        })
    };
    let gold = |m: &Map, sigma: f64, k0: f32| {
        let (d, sp) = lit(m, sigma, 1.4);
        let e = edge(m);
        Color::from_fn(size, size, |i| img::add3(scale3(img::ramp(&GOLD, k0 - 0.2 + 1.3 * d.v[i]), 1.0 - 0.25 * e.v[i]), [sp.v[i] * 0.3; 3]))
    };
    let grain = noise(size, size, 3.0 * ppr, 2, 5);
    let faces = stroked(&p.faces, 9.0, [0.0, 0.0]).blur(ppr);
    let carve = stroked(&p.carving, 1.0, [0.0, 0.0]);
    let carve_lit = stroked(&p.carving, 1.0, [0.8, 0.8]).zip(&carve, |a, c| a * (1.0 - c));
    let mut c_body = wood(&m_body, 1.7, 0.12);
    let pale_wood = rgb("#d8a98c");
    for (i, c) in c_body.v.iter_mut().enumerate() {
        let mb = m_body.v[i];
        let old = scale3(*c, (1.0 + 0.05 * (grain.v[i] - 0.5)) * (1.0 - 0.17 * faces.v[i] * mb));
        *c = [0, 1, 2].map(|k| old[k] * (1.0 - 0.3 * carve.v[i] * mb) + (pale_wood[k] - old[k]) * 0.4 * carve_lit.v[i] * mb);
    }
    let (c_base, c_rod, c_collar) = (wood(&m_base, 2.0, 0.12), wood(&m_rod, 1.6, 0.35), wood(&m_collar, 0.9, -0.15));
    let (mut c_blade, c_set, c_pegs, c_cap) = (gold(&m_blade, 1.3, 0.1), gold(&m_set, 1.4, 0.0), gold(&m_pegs, 0.8, 0.55), gold(&m_cap, 1.2, 0.4));
    let m_facet = fill(&get("facet")).zip(&m_blade, |a, b| a * b);
    let shine = rgb("#fff3d2");
    for (i, c) in c_blade.v.iter_mut().enumerate() {
        let old = *c;
        *c = [0, 1, 2].map(|k| old[k] * (1.0 - 0.14 * (1.0 - m_facet.v[i]) * m_blade.v[i]) + (shine[k] - old[k]) * 0.3 * m_facet.v[i]);
    }
    let (d_br, _) = lit(&m_bridge, 1.0, 1.4);
    let c_bridge = Color::from_fn(size, size, |i| img::ramp(&BRIDGE, -0.1 + 1.2 * d_br.v[i] - 0.5 * smooth(211.5, 216.0, cxy(i).1)));
    let dome = Map::from_fn(size, size, |x, y| {
        let (cx, cy) = ((x - hf) / pf + CX as f32, (y - hf) / pf + CY as f32);
        (1.0 - ((cx - 155.0) / 9.8).powi(2) - ((cy - 263.0) / 12.6).powi(2)).clamp(0.0, 1.0).sqrt() * 5.0 * pf
    });
    let (d_gem, sp_gem) = relief(&dome, 1.0, light);
    let c_gem = Color::from_fn(size, size, |i| {
        let (cx, cy) = cxy(i);
        let pool = (-((cx - 157.0).powi(2) + (cy - 268.0).powi(2)) / 25.0).exp();
        let c = img::add3(img::ramp(&GEM, 0.15 + 0.6 * d_gem.v[i] + 0.45 * pool), [sp_gem.v[i] * 0.5; 3]);
        let g = (-((cx - 151.5).powi(2) + (cy - 256.5).powi(2)) / 4.0).exp();
        c.map(|v| v + (1.0 - v) * g * 0.9)
    });
    let mut sc = Canvas::new(size, size);
    for x in STRING_X {
        sc.stroke(&[vec![[half + (x - CX) * ppr, half + (STRING_Y.0 - CY) * ppr], [half + (x - CX) * ppr, half + (STRING_Y.1 - CY) * ppr]]], 2.7 * ppr, Cap::Flat, 0.85);
    }
    let m_str = sc.done();
    let block = Map::from_fn(size, size, |x, y| {
        let (cx, cy) = ((x - hf) / pf + CX as f32, (y - hf) / pf + CY as f32);
        ((40.0 - (cx - 155.0).abs()) / 4.0).clamp(0.0, 1.0) * f32::from(u8::from(cy > STRING_Y.0 as f32 && cy < STRING_Y.1 as f32))
    })
    .blur(1.2 * ppr);
    let mut color = Color::new(size, size, [0.0; 3]);
    let mut alpha = Map::new(size, size, 0.0);
    let mut lay = |c: &dyn Fn(usize) -> Rgb, a: &Map| over(&mut color, &mut alpha, c, a);
    let flat = |hex: &str| { let c = rgb(hex); move |_: usize| c };
    if halo {
        let aura = Map::from_fn(size, size, |x, y| {
            let (cx, cy) = ((x - hf) / pf + CX as f32, (y - hf) / pf + CY as f32);
            (-(((cx - 155.0) / 60.0).powi(2) + ((cy - 132.0) / 95.0).powi(2)).powf(1.4)).exp() * 0.2
        });
        lay(&flat(ANEMO_TEAL), &aura);
        lay(&flat(MINT), &whole.blur(10.0 * ppr).map(|v| v * 0.22));
        lay(&flat(PINE), &whole.blur(5.0 * ppr).roll((6.0 * ppr) as i64, (5.0 * ppr) as i64).map(|v| v * 0.45));
    }
    lay(&flat("#2c8f7c"), &block.blur(6.0 * ppr).map(|v| v * 0.6));
    let spread = m_str.blur(2.2 * ppr);
    let top = spread.max().max(1e-3);
    let pale = rgb("#a7c9b9");
    lay(&|i| scale3(pale, 0.55 + 0.45 * spread.v[i] / top), &block.map(|v| v * 0.95));
    lay(&flat(OUTLINE), &rim(&whole, 0.9, 2.4).map(|v| v * 0.9));
    lay(&|i| c_body.v[i], &m_body);
    lay(&flat(OUTLINE), &rim(&m_base, 0.7, 2.2).map(|v| v * 0.8));
    lay(&|i| c_base.v[i], &m_base);
    let deco = clip1(&m_blade, &m_set);
    lay(&flat("#4a2a1c"), &deco.blur(1.2 * ppr).roll((1.5 * ppr) as i64, (1.2 * ppr) as i64).map(|v| v * 0.45));
    lay(&flat("#5a3a20"), &rim(&deco, 0.6, 2.2).map(|v| v * 0.75));
    lay(&|i| c_blade.v[i], &m_blade);
    lay(&|i| c_set.v[i], &m_set);
    lay(&flat("#3f2a14"), &rim(&m_gem, 0.5, 2.2).map(|v| v * 0.8));
    lay(&|i| c_gem.v[i], &m_gem);
    lay(&flat("#5a3a20"), &rim(&m_bridge, 0.6, 2.2).map(|v| v * 0.8));
    lay(&|i| c_bridge.v[i], &m_bridge);
    lay(&flat("#dcfff1"), &m_str.blur(1.2 * ppr).zip(&block, |s, b| (s * 1.3).clamp(0.0, 0.9) * b));
    lay(&flat("#e8fffa"), &m_str.zip(&block, |s, b| s * (b * 1.6).clamp(0.0, 1.0)));
    lay(&flat(OUTLINE), &rim(&m_rod, 0.7, 2.2).map(|v| v * 0.85));
    lay(&|i| c_rod.v[i], &m_rod);
    lay(&|i| scale3(c_collar.v[i], 0.85), &m_collar);
    lay(&flat("#5a3a20"), &rim(&m_cap, 0.6, 2.2).map(|v| v * 0.8));
    lay(&|i| c_cap.v[i], &m_cap);
    lay(&flat("#5a3a20"), &rim(&m_pegs, 0.6, 2.2).map(|v| v * 0.7));
    lay(&|i| c_pegs.v[i], &m_pegs);
    let vein = rgb("#c4d690");
    for (b, c, tip, wid) in LEAVES {
        let line = bezier(b, c, c, tip, 60);
        let ws: Vec<f64> = (0..60).map(|i| { let k = f64::from(i) / 59.0; wid * (std::f64::consts::PI * k.clamp(0.02, 1.0)).sin().powf(0.8) * (1.0 - k * 0.3) }).collect();
        let local = rf(&line);
        let nn = normals(&local);
        let mut strip: Vec<Pt> = local.iter().zip(&nn).zip(&ws).map(|((p, n), w)| [p[0] + n[0] * w / 2.0, p[1] + n[1] * w / 2.0]).collect();
        strip.extend(local.iter().zip(&nn).zip(&ws).rev().map(|((p, n), w)| [p[0] - n[0] * w / 2.0, p[1] - n[1] * w / 2.0]));
        let m_leaf = fill(&Shape::winding(vec![strip]));
        let (d, sp) = lit(&m_leaf, 1.6, 1.2);
        let rib = stroked(&[cubic(r(b[0], b[1]), r(c[0], c[1]), r(c[0], c[1]), r(tip[0], tip[1]), 24)], 0.7, [0.0, 0.0]);
        lay(&flat("#1f2a14"), &rim(&m_leaf, 0.6, 2.2).map(|v| v * 0.7));
        lay(&|i| lerp3(img::add3(img::ramp(&LEAF, -0.1 + 1.1 * d.v[i]), [sp.v[i] * 0.15; 3]), vein, 0.35 * rib.v[i]), &m_leaf);
    }
    let (shade_c, petal, cream) = (rgb("#c9c8a2"), rgb("#f7f4d8"), rgb("#e2e7b8"));
    for (seed, (at, shape)) in LILIES.iter().enumerate() {
        let (fx, fy) = (at[0], at[1]);
        let span = 48.0f32;
        for &(ang, ln, wf) in shape {
            let pts: Vec<Pt> = petal_points(ln, ang.to_radians(), wf).into_iter().map(|q| [q[0] + fx - CX, q[1] + fy - CY]).collect();
            let m = fill(&Shape::odd(vec![pts.clone()]));
            let (d, _) = lit(&m, 2.2, 0.9);
            let tip = [pts[pts.len() / 2][0] + CX, pts[pts.len() / 2][1] + CY];
            let mid = stroked(&[vec![r(fx, fy), r(fx + (tip[0] - fx) * 0.75, fy + (tip[1] - fy) * 0.75)]], 0.8, [0.0, 0.0]).blur(0.5 * ppr);
            let pc = |i: usize| {
                let (cx, cy) = cxy(i);
                let rr = (cx - fx as f32).hypot(cy - fy as f32) / span;
                let k = (0.25 + 0.8 * d.v[i]).clamp(0.0, 1.05);
                let c = img::add3(scale3(shade_c, 1.0 - k), scale3(petal, k));
                scale3(lerp3(c, cream, 0.45 * (1.0 - smooth(0.05, 0.35, rr))), 1.0 - 0.12 * mid.v[i])
            };
            lay(&flat("#20261a"), &rim(&m, 0.6, 2.2).zip(&m, |r, m| r * (1.0 - m) * 0.35));
            lay(&flat("#5d6448"), &rim(&m, 0.6, 2.0).map(|v| v * 0.75));
            lay(&pc, &m.map(|v| v * 0.995));
        }
        let gauss = |sx: f32, sy: f32, s: f32| Map::from_fn(size, size, |x, y| {
            let (cx, cy) = ((x - hf) / pf + CX as f32, (y - hf) / pf + CY as f32);
            (-((cx - sx).powi(2) + (cy - sy).powi(2)) / s.powi(2)).exp()
        });
        let (fx, fy) = (fx as f32, fy as f32);
        lay(&flat("#d9e2a0"), &gauss(fx, fy, 0.12 * span).map(|v| v * 0.8));
        for j in 0..5 {
            let a = (seed as f32 * 40.0 + 72.0 * j as f32).to_radians();
            let (sx, sy) = (fx + 0.075 * span * a.cos(), fy + 0.06 * span * a.sin());
            let dot = gauss(sx, sy, 0.042 * span);
            lay(&flat("#4a3a8a"), &dot.map(|v| (v * 1.6).clamp(0.0, 1.0) * 0.6));
            lay(&flat("#7f6ad0"), &dot.map(|v| (v * 1.4 - 0.15).clamp(0.0, 1.0)));
            lay(&flat("#cbbcf6"), &gauss(sx - 0.6, sy - 0.6, 0.022 * span).map(|v| v * 0.8));
        }
    }
    picture(&color, &alpha)
}

pub fn aura(ppr: f64) -> Pic {
    let size = side(ppr);
    let (hf, pf) = (size as f32 / 2.0, ppr as f32);
    let a = Map::from_fn(size, size, |x, y| {
        let (cx, cy) = ((x - hf) / pf + CX as f32, (y - hf) / pf + CY as f32);
        (-(((cx - 155.0) / 60.0).powi(2) + ((cy - 132.0) / 95.0).powi(2)).powf(1.4)).exp() * 0.22
    });
    picture(&Color::new(size, size, rgb(ANEMO_TEAL)), &a)
}

pub fn string_glow(ppr: f64) -> Pic {
    let len = (STRING_Y.1 - STRING_Y.0) as f32;
    let (w, h) = ((14.0 * ppr).ceil() as usize, ((STRING_Y.1 - STRING_Y.0 + 8.0) * ppr).ceil() as usize);
    let (glow, core, pf) = (rgb("#9ff5e0"), rgb("#f4fffa"), ppr as f32);
    let (c, a) = img::light_of(w, h, |i| {
        let (xs, ys) = img::xy_of(w, i);
        let (x, y) = ((xs + 0.5) / pf - 7.0, (ys + 0.5) / pf - 4.0);
        let along = smooth(0.0, 6.0, y) * smooth(0.0, 6.0, len - y);
        img::add3(scale3(glow, (-(x / 4.5).powi(2)).exp() * along * 0.6), scale3(core, (-(x / 1.6).powi(2)).exp() * along * 1.1))
    });
    picture(&c, &a)
}
