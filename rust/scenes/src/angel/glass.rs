//! The round window's pictures, per pixel (angel._rose_glass, _icon, _halo, _rays, light.noise): the
//! game's 流浪汉 and 愚人 icons in gold on a smoky veil, the light it spills and its burst of rays.

use super::pcg::Pcg64;
use super::px::{blur, glow, gradient, picture, pyround, rgb, shift, smooth, Grid, Pic};

pub const HONEY: &str = "#ffd98a";
const SACK: &[u8] = include_bytes!("../../../../blacklist_detect/assets/role_vagrant.png");
const HAT: &[u8] = include_bytes!("../../../../blacklist_detect/assets/role_fool.png");

/// An icon: which picture, the share of the window it fills, how wide a seam is, how polished.
pub struct Icon {
    pub png: &'static [u8],
    pub wide: f64,
    pub seam: f64,
    pub polish: f32,
}

pub const SACK_ICON: Icon = Icon { png: SACK, wide: 0.74, seam: 1.5, polish: 0.35 };
pub const HAT_ICON: Icon = Icon { png: HAT, wide: 0.7, seam: 2.0, polish: 1.0 };

/// The window's three pictures: the veil behind, the gold figure, where the gold shines.
pub struct Glass {
    pub back: Pic,
    pub figure: Pic,
    pub shine: Pic,
}

/// light.noise: smooth value noise, 0..1, octaves each half the size of the last.
pub fn noise(width: usize, height: usize, scale: f64, octaves: u32, seed: u32) -> Grid {
    let mut rnd = Pcg64::new(seed);
    let mut out = Grid::new(width, height);
    let (mut total, mut amp) = (0.0f64, 1.0f64);
    for octave in 0..octaves {
        let cell = (scale / f64::from(1u32 << octave)).max(2.0);
        let (gw, gh) = ((width as f64 / cell) as usize + 3, (height as f64 / cell) as usize + 3);
        let grid: Vec<f32> = (0..gw * gh).map(|_| rnd.random_f32()).collect();
        let along = |i: usize| {
            let f = i as f32 / cell as f32;
            let i0 = f as usize;
            let s = f - i0 as f32;
            (i0, s * s * (3.0 - 2.0 * s))
        };
        let xs: Vec<(usize, f32)> = (0..width).map(along).collect();
        for y in 0..height {
            let (y0, sy) = along(y);
            let row = |r: usize, x: usize| {
                let (x0, sx) = xs[x];
                grid[r * gw + x0] * (1.0 - sx) + grid[r * gw + x0 + 1] * sx
            };
            for x in 0..width {
                out.v[y * width + x] += (row(y0, x) * (1.0 - sy) + row(y0 + 1, x) * sy) * amp as f32;
            }
        }
        total += amp;
        amp *= 0.5;
    }
    out.map(|v| v / total as f32)
}

/// Catmull-Rom weights sampling a row of `size` pixels at `at`: four (column, weight) per sample.
fn cubic(at: &[f32], size: usize) -> Vec<[(usize, f32); 4]> {
    at.iter()
        .map(|&a| {
            let base = a.floor();
            let t = a - base;
            let w = [t * (t * (2.0 - t) - 1.0) / 2.0, (t * t * (3.0 * t - 5.0) + 2.0) / 2.0, t * (t * (4.0 - 3.0 * t) + 1.0) / 2.0, t * t * (t - 1.0) / 2.0];
            std::array::from_fn(|k| (((base as i64) + k as i64 - 1).clamp(0, size as i64 - 1) as usize, w[k]))
        })
        .collect()
}

/// down @ g @ across.T
fn resample(g: &Grid, down: &[[(usize, f32); 4]], across: &[[(usize, f32); 4]]) -> Grid {
    let tall: Vec<Vec<f32>> = down.iter().map(|taps| (0..g.w).map(|x| taps.iter().map(|&(r, w)| g.at(x, r) * w).sum()).collect()).collect();
    Grid::from_fn(across.len(), down.len(), |x, y| across[x].iter().map(|&(c, w)| tall[y][c] * w).sum())
}

/// angel._edge: where a smooth field is over half, with an antialiased edge a pixel wide.
fn edge(field: &Grid) -> Grid {
    let (gy, gx) = gradient(field);
    Grid::from_fn(field.w, field.h, |x, y| {
        let i = y * field.w + x;
        ((field.v[i] - 0.5) / gx.v[i].hypot(gy.v[i]).max(1e-4) + 0.5).clamp(0.0, 1.0)
    })
}

/// angel._close: dark gaps narrower than about 2r pixels filled in.
fn close(a: &Grid, r: f64) -> Grid {
    let k = r.ceil() as i64;
    let near: Vec<(i64, i64)> = (-k..=k).flat_map(|dy| (-k..=k).map(move |dx| (dy, dx))).filter(|&(dy, dx)| ((dx * dx + dy * dy) as f64) <= r * r).collect();
    let fold = |g: &Grid, grow: bool| {
        let moved: Vec<Grid> = near.iter().map(|&(dy, dx)| shift(g, dy, dx)).collect();
        Grid::from_fn(g.w, g.h, |x, y| {
            let vals = moved.iter().map(|m| m.at(x, y));
            if grow { vals.fold(f32::MIN, f32::max) } else { vals.fold(f32::MAX, f32::min) }
        })
    };
    fold(&fold(a, true), false)
}

/// angel._icon: how much of each of the n x n pixels the icon covers, seams filled; and its seams.
fn icon(icon: &Icon, n: usize) -> (Grid, Grid) {
    let img = image::load_from_memory(icon.png).map(|i| i.to_rgba8()).unwrap_or_default();
    let (w, h) = (img.width() as usize, img.height() as usize);
    let alpha = Grid::from_fn(w, h, |x, y| f32::from(img.get_pixel(x as u32, y as u32)[3]) / 255.0);
    let (mut x0, mut x1, mut y0, mut y1) = (usize::MAX, 0, usize::MAX, 0);
    for y in 0..h {
        for x in 0..w {
            if alpha.at(x, y) >= 0.5 {
                (x0, x1, y0, y1) = (x0.min(x), x1.max(x), y0.min(y), y1.max(y));
            }
        }
    }
    let per = ((x1 + 1 - x0) as f64 / (2.0 * icon.wide)) as f32;
    let at: Vec<f32> = (0..n).map(|i| ((i as f32 + 0.5) / n as f32 * 2.0 - 1.0) * per - 0.5).collect();
    let across = cubic(&at.iter().map(|a| a + (x0 + x1 + 1) as f32 / 2.0).collect::<Vec<_>>(), w);
    let down = cubic(&at.iter().map(|a| a + (y0 + y1 + 1) as f32 / 2.0).collect::<Vec<_>>(), h);
    let fill = close(&alpha, icon.seam).zip(&alpha, |c, a| c - a);
    let whole = alpha.zip(&fill, |a, f| a + f * smooth(0.2, 0.4, f));
    let cover = edge(&resample(&whole, &down, &across));
    let cut = edge(&resample(&alpha, &down, &across));
    let seams = cover.zip(&cut, |c, k| c * (1.0 - k));
    (cover, seams)
}

/// angel._rose_glass: the window, n pixels across, with the icon in gold in its middle.
pub fn rose_glass(radius: f64, scale: f64, u: f64, which: &Icon) -> Glass {
    let n = ((2.0 * radius * scale).ceil() as usize).max(8);
    let unit = |i: usize| (i as f32 + 0.5) / n as f32 * 2.0 - 1.0;
    let rho = Grid::from_fn(n, n, |x, y| unit(x).hypot(unit(y)));
    let px = u * scale;
    let polish = which.polish;
    let (cover, seams) = icon(which, n);
    let behind = blur(&cover, 14.0 * px).map(|b| (b * (0.9 + 0.4 * polish)).clamp(0.0, 1.0));
    let (dark, pale) = (rgb("#1c1308"), rgb("#ffe7aa"));
    let back = picture(
        n,
        n,
        |i| std::array::from_fn(|k| dark[k] + (pale[k] - dark[k]) * behind.v[i]),
        |i| (1.0 - smooth(0.985, 1.0, rho.v[i])) * (0.3 * (1.0 - 0.45 * smooth(0.35, 1.0, rho.v[i])) * (1.0 - behind.v[i]) + 0.55 * behind.v[i]),
    );
    let soft = blur(&cover, (2.4 * px).max(0.6));
    let shadow = shift(&soft, pyround(1.2 * px).max(1), pyround(0.8 * px).max(1)).zip(&cover, |s, c| s * (1.0 - c));
    let (dull, bright) = ((rgb("#d9b86e"), rgb("#b4893a")), (rgb("#ffd772"), rgb("#e3a42c")));
    let top: [f32; 3] = std::array::from_fn(|k| dull.0[k] + (bright.0[k] - dull.0[k]) * polish);
    let low: [f32; 3] = std::array::from_fn(|k| dull.1[k] + (bright.1[k] - dull.1[k]) * polish);
    let grain = noise(n, n, 5.0 * px, 3, 7);
    let groove = blur(&seams, (0.35 * px).max(0.5)).map(|g| (g * 1.6).clamp(0.0, 1.0));
    let gold: Vec<[f32; 3]> = (0..n * n)
        .map(|i| {
            let k = smooth(-0.6, 0.7, unit(i / n));
            let g = 1.0 + (grain.v[i] - 0.5) * (0.04 + 0.1 * (1.0 - polish));
            std::array::from_fn(|c| (top[c] + (low[c] - top[c]) * k) * (g * (1.0 - 0.4 * groove.v[i])))
        })
        .collect();
    let deep = rgb("#120b03");
    let figure = picture(
        n,
        n,
        |i| std::array::from_fn(|c| deep[c] + (gold[i][c] - deep[c]) * cover.v[i]),
        |i| cover.v[i] + (1.0 - cover.v[i]) * (0.34 * shadow.v[i]).clamp(0.0, 0.9),
    );
    let cream = rgb("#fff3cc");
    let shine = picture(n, n, |_| cream, |i| cover.v[i] * (0.6 + 0.4 * smooth(0.3, 0.9, (gold[i][0] + gold[i][1] + gold[i][2]) / 3.0)));
    Glass { back, figure, shine }
}

/// angel._halo: the light the window spills round itself, a quarter size, three radii across.
pub fn halo(radius: f64, scale: f64) -> Pic {
    let m = ((6.0 * radius * scale * 0.25).ceil() as usize).max(8);
    let honey = rgb(HONEY);
    let unit = |i: usize| (i as f32 + 0.5) / m as f32 * 2.0 - 1.0;
    glow(m, m, |i| {
        let d = unit(i % m).hypot(unit(i / m)) * 3.0;
        let spill = (-((d - 0.85).max(0.0) / 0.4).powi(2)).exp() * 0.6 + (-((d - 0.9).max(0.0) / 0.8).powi(2)).exp() * 0.25;
        honey.map(|c| c * spill * smooth(0.5, 1.0, d) * 0.75)
    })
}

/// angel._rays: the burst out of the window at the reveal, a third size, eight radii across.
pub fn rays(radius: f64, scale: f64) -> Pic {
    let m = ((8.0 * radius * scale / 3.0).ceil() as usize).max(8);
    let (honey, white) = (rgb(HONEY), rgb("#fffaf0"));
    let unit = |i: usize| (i as f32 + 0.5) / m as f32 * 2.0 - 1.0;
    glow(m, m, |i| {
        let (x, y) = (unit(i % m), unit(i / m));
        let (d, a) = (x.hypot(y) * 4.0, y.atan2(x));
        let long = (0.5 + 0.5 * (8.0 * a + 0.4).cos()).powi(10);
        let fine = (0.5 + 0.5 * (29.0 * a + 1.3).cos()).powi(6) * (0.55 + 0.45 * (11.0 * a + 2.0).cos()) + (0.5 + 0.5 * (47.0 * a).cos()).powi(8) * 0.6;
        let reach = 1.0 + 1.9 * long + 0.8 * (0.5 + 0.5 * (5.0 * a + 0.7).cos());
        let rays = (long + 0.7 * fine) * (-(d - 0.9).max(0.0) / (0.55 * reach)).exp() * smooth(0.75, 1.05, d) * (1.0 - smooth(3.4, 4.0, d));
        let soft = (-((d - 0.95).max(0.0) / 0.7).powi(2)).exp() * smooth(0.6, 1.0, d) * 0.45;
        let hot = (-(d - 1.0).max(0.0) / 0.6).exp();
        std::array::from_fn(|c| (honey[c] + (white[c] - honey[c]) * hot) * (rays * 1.1 + soft))
    })
}
