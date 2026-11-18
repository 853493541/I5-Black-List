//! 经典, the default 嘉宾 welcome, ported from blacklist_detect/love_scenes/classic.py line for line:
//! the edges dim and a warm light falls from the top, a champagne-gold double frame draws itself round
//! the screen from the top middle with a spark at its head, brackets and diamonds in the corners,
//! parted round the button; 心动嘉宾 in gold in its top line with a sheen; gold motes drift up.
//!
//! The soft layers (numpy in Python) are worked out on the CPU in `soft` and laid on from an atlas;
//! the rest is shapes the chip shades per pixel (crate::lace's engine). The title's words come in as a
//! mask from the app's text engine (TitleMask): the only thing this scene does not draw itself.

pub mod soft;

use std::f64::consts::{PI, TAU};

use crate::draw::{clamp, ease_in, ease_in_out, ease_out, hex, partial, win, Pt};
use crate::lace::prim::{stops, Clip, Frame, Paint, Path, LOBBY, REFLECT};
use crate::pyrand::PyRandom;
use soft::{blur, picture, rgb, smooth, stroke_mask, title_art, Grid, TitleMask};

pub const DURATION: f64 = 4.4;
const CHAMPAGNE: &str = "#e9c987";
const LIGHT: &str = "#fff1cf";
const DEEP: &str = "#a9823d";
const SOFT: f64 = 0.5;
const INSET: f64 = 22.0;
const INNER: f64 = 6.0;
const BRACKET: f64 = 30.0;
const OUTER_DRAW: (f64, f64) = (0.2, 1.35);
const INNER_DRAW: (f64, f64) = (0.35, 1.5);
const TITLE_ROOM: f64 = 22.0;
const TITLE_IN: (f64, f64) = (0.55, 1.2);
const SHEEN: (f64, f64) = (1.55, 2.35);
const DESIGN: [f64; 2] = [1635.0, 848.0];
const WHITE: [f32; 3] = [1.0; 3];

type Rect = [f64; 4];

fn contains(r: Rect, p: Pt) -> bool {
    r[0] <= p[0] && p[0] <= r[0] + r[2] && r[1] <= p[1] && p[1] <= r[1] + r[3]
}

/// draw.gold_pen: champagne gold catching the light every so often along the line.
fn gold_pen(alpha: f64, span: f64) -> Paint {
    let list = stops(&[(0.0, "#b98a55", alpha), (0.45, "#e2c08d", alpha), (0.55, "#fbecd0", alpha), (1.0, "#e2c08d", alpha)]);
    Paint::Linear([0.0, 0.0], [span, span * 0.35], list)
}

/// A corner's bracket inside the double line: two short arms meeting at a step.
fn bracket(corner: Pt, sx: f64, sy: f64, u: f64) -> Path {
    let at = [corner[0] + sx * 14.0 * u, corner[1] + sy * 14.0 * u];
    let arm = BRACKET * u;
    let mut path = Path::new([at[0], at[1] + sy * arm]);
    path.line_to(at);
    path.line_to([at[0] + sx * arm, at[1]]);
    path.move_to([at[0] + sx * 6.0 * u, at[1] + sy * arm * 0.6]);
    path.line_to([at[0] + sx * 6.0 * u, at[1] + sy * 6.0 * u]);
    path.line_to([at[0] + sx * arm * 0.6, at[1] + sy * 6.0 * u]);
    path
}

/// A small gold diamond, lit from above, with a fine dark edge.
fn diamond(f: &mut Frame, at: Pt, r: f64, alpha: f64) {
    if alpha <= 0.01 || r <= 0.3 {
        return;
    }
    let mut path = Path::new([at[0], at[1] - r]);
    path.line_to([at[0] + r * 0.72, at[1]]);
    path.line_to([at[0], at[1] + r]);
    path.line_to([at[0] - r * 0.72, at[1]]);
    path.close();
    let fill = stops(&[(0.0, LIGHT, alpha), (0.5, CHAMPAGNE, alpha), (1.0, DEEP, alpha)]);
    f.poly(&path.subs[0], &Paint::Linear([at[0], at[1] - r], [at[0], at[1] + r], fill));
    f.stroke_path(&path, (r * 0.12).max(0.6), &Paint::Solid(hex("#3a2a10"), 0.55 * alpha), true, 0);
}

struct Half {
    points: Vec<Pt>,
    when: (f64, f64),
    thick: f64,
}

pub struct Classic {
    pub width: f64,
    pub height: f64,
    /// The bare area round the button, x, y, w, h.
    pub gap: Rect,
    u: f64,
    halves: Vec<Half>,
    corners: [(Pt, f64, f64, usize); 4],
    corners_at: [f64; 2],
    ends: [(Pt, f64); 2],
    /// The title's place in points and its size in the atlas.
    title_box: Rect,
    title_px: [f64; 2],
    /// x, y, rise, sway, phase, size, start.
    motes: Vec<[f64; 7]>,
    /// The soft pictures: hall | glow on the first row, title | shine below; width, height, RGBA.
    atlas: (u32, u32, Vec<u8>),
}

impl Classic {
    /// love_scenes.sample_stage(width, height): the sample lobby's button gap at this size.
    pub fn sample(width: f64, height: f64, title: &TitleMask) -> Self {
        let s = width / DESIGN[0];
        let keep = [549.0 * s, 749.0 * s, 556.0 * s, 94.0 * s];
        Self::new(width, height, [keep[0] - 28.0 * s, keep[1] - 30.0 * s, keep[2] + 56.0 * s, height - keep[1] + 30.0 * s], title)
    }

    pub fn new(width: f64, height: f64, gap: Rect, title: &TitleMask) -> Self {
        let u = (width / DESIGN[0]).min(height / DESIGN[1]);
        let mut rnd = PyRandom::new(23);
        let (title_w, title_h) = (title.w as f64 / 2.0, title.h as f64 / 2.0);
        let (inset, inner) = (INSET * u, INNER * u);
        let (top, bottom) = (inset, height - inset);
        let half = title_w / 2.0 + TITLE_ROOM * u;
        let middle = width / 2.0;
        let gap_l = (inset + 40.0 * u).max(gap[0] - 14.0 * u);
        let gap_r = (width - inset - 40.0 * u).min(gap[0] + gap[2] + 14.0 * u);
        let mut halves = Vec::new();
        for (side, x_end) in [(-1.0, gap_l), (1.0, gap_r)] {
            for (step, when, thick) in [(0.0, OUTER_DRAW, 1.6), (inner, INNER_DRAW, 0.8)] {
                let edge = if side < 0.0 { inset + step } else { width - inset - step };
                let points = vec![[middle + side * half, top + step], [edge, top + step], [edge, bottom - step], [x_end, bottom - step]];
                halves.push(Half { points, when, thick });
            }
        }
        let p = &halves[0].points;
        let seg = |i: usize| (p[i + 1][0] - p[i][0]).hypot(p[i + 1][1] - p[i][1]);
        let run = [seg(0), seg(0) + seg(1), seg(0) + seg(1) + seg(2)];
        let corners_at = [run[0] / run[2], run[1] / run[2]];
        let corners = [([inset, top], 1.0, 1.0, 0), ([width - inset, top], -1.0, 1.0, 0), ([inset, bottom], 1.0, -1.0, 1), ([width - inset, bottom], -1.0, -1.0, 1)];
        let ends = [([gap_l, bottom], -1.0), ([gap_r, bottom], 1.0)];
        let clear = [gap[0] - 60.0 * u, gap[1] - 60.0 * u, gap[2] + 120.0 * u, gap[3] + 60.0 * u];
        let mut motes = Vec::new();
        while motes.len() < 22 {
            let x = rnd.uniform(width * 0.08, width * 0.92);
            let y = rnd.uniform(height * 0.22, height * 0.92);
            if contains(clear, [x, y]) {
                continue;
            }
            let rise = rnd.uniform(10.0, 24.0) * u;
            let sway = rnd.uniform(5.0, 14.0) * u;
            let phase = rnd.uniform(0.0, TAU);
            motes.push([x, y, rise, sway, phase, rnd.uniform(1.8, 4.2) * u, rnd.uniform(0.7, 1.7)]);
        }
        let mut scene = Self {
            width,
            height,
            gap,
            u,
            halves,
            corners,
            corners_at,
            ends,
            title_box: [middle - title_w / 2.0, top - title_h / 2.0, title_w, title_h],
            title_px: [title.w as f64, title.h as f64],
            motes,
            atlas: (1, 1, vec![0; 4]),
        };
        scene.atlas = scene.make_atlas(title);
        scene
    }

    /// The soft pictures for the renderer's atlas: width, height, premultiplied RGBA.
    pub fn atlas(&self) -> (u32, u32, &[u8]) {
        (self.atlas.0, self.atlas.1, &self.atlas.2)
    }

    fn soft_size(&self) -> (usize, usize) {
        (((self.width * SOFT).round() as usize).max(1), ((self.height * SOFT).round() as usize).max(1))
    }

    fn make_atlas(&self, title: &TitleMask) -> (u32, u32, Vec<u8>) {
        let (w, h) = self.soft_size();
        let u = self.u;
        let g = self.gap;
        // How much may show: none over the button and its marks, all a little way off.
        let keep = Grid::from_fn(w, h, |x, y| {
            let (px, py) = ((x as f64 + 0.5) / SOFT, (y as f64 + 0.5) / SOFT);
            let dx = (g[0] - px).max(px - g[0] - g[2]).max(0.0);
            let dy = (g[1] - py).max(py - g[1] - g[3]).max(0.0);
            smooth(0.0, (90.0 * u) as f32, dx.hypot(dy) as f32).powf(0.8)
        });
        // The hall: the edges dimmed, a cone of warm light from just above the top middle.
        let (night, warm) = (rgb("#0a0e18"), rgb("#ffe7b0"));
        let mut hall_alpha = Grid::new(w, h);
        let mut hall_color = vec![[0.0f32; 3]; w * h];
        for y in 0..h {
            for x in 0..w {
                let (fx, fy) = (x as f32, y as f32);
                let (nx, ny) = ((fx / w as f32 - 0.5) * 2.0, (fy / h as f32 - 0.5) * 2.0);
                let dim = smooth(0.55, 1.3, (nx * nx * 0.75 + ny * ny).sqrt()) * 0.42;
                let spread = nx.abs() / ((fy / h as f32 + 0.12) * 1.1);
                let light = (1.0 - smooth(0.25, 1.0, spread)) * (1.0 - smooth(0.15, 0.95, fy / h as f32)) * 0.16;
                let alpha = dim + light * (1.0 - dim);
                let i = y * w + x;
                hall_color[i] = std::array::from_fn(|c| (night[c] * dim + warm[c] * light * (1.0 - dim)) / alpha.max(1e-4));
                hall_alpha.v[i] = alpha * keep.v[i];
            }
        }
        let hall = picture(w, h, |i| hall_color[i], &hall_alpha);
        // The frame's glow: its lines and brackets as a mask at SOFT size, blurred twice.
        let mut core = Grid::new(w, h);
        let scaled = |path: &Path| -> Vec<Vec<Pt>> { path.subs.iter().map(|s| s.iter().map(|p| [p[0] * SOFT, p[1] * SOFT]).collect()).collect() };
        for half in &self.halves {
            stroke_mask(&mut core, &scaled(&Path::lines(&half.points)), (half.thick * 2.2 * u).max(1.2) * SOFT);
        }
        for &(corner, sx, sy, _) in &self.corners {
            stroke_mask(&mut core, &scaled(&bracket(corner, sx, sy, u)), 1.6 * u * SOFT);
        }
        let (b1, b2) = (blur(&core, 5.0 * u * SOFT), blur(&core, 14.0 * u * SOFT));
        let glow_alpha = Grid::from_fn(w, h, |x, y| {
            let i = y * w + x;
            (b1.v[i] * 0.9 + b2.v[i] * 0.5).clamp(0.0, 1.0) * 0.75 * keep.v[i]
        });
        let glow = picture(w, h, |_| rgb("#ffd98f"), &glow_alpha);
        let (title_rgba, shine) = title_art(title, u, [rgb(DEEP), rgb(CHAMPAGNE), rgb(LIGHT)]);
        // Lay them out: hall | glow, then title | shine.
        let aw = (2 * w).max(2 * title.w);
        let ah = h + title.h;
        let mut atlas = vec![0u8; aw * ah * 4];
        let mut put = |src: &[u8], sw: usize, sh: usize, ox: usize, oy: usize| {
            for y in 0..sh {
                let to = ((oy + y) * aw + ox) * 4;
                atlas[to..to + sw * 4].copy_from_slice(&src[y * sw * 4..(y + 1) * sw * 4]);
            }
        };
        put(&hall, w, h, 0, 0);
        put(&glow, w, h, w, 0);
        put(&title_rgba, title.w, title.h, 0, h);
        put(&shine, title.w, title.h, title.w, h);
        (aw as u32, ah as u32, atlas)
    }

    /// Everything drawn at t seconds over the lobby, with the atlas from `atlas`.
    pub fn paint(&self, t: f64) -> Frame {
        let (width, height, u) = (self.width, self.height, self.u);
        let mut f = Frame::new();
        f.layer(LOBBY, [width, height], 1.0);
        let life = win(t, 0.0, 0.35) * (1.0 - ease_in(win(t, DURATION - 0.8, DURATION)));
        if life <= 0.0 {
            return f;
        }
        let (sw, sh) = self.soft_size();
        let (sw, sh) = (sw as f64, sh as f64);
        f.opacity = life * ease_out(win(t, 0.0, 0.7));
        f.image([0.0, 0.0, width, height], [0.0, 0.0, sw, sh], 1.0);
        f.opacity = life * ease_out(win(t, 1.0, 1.9)) * (0.85 + 0.15 * (t * 2.2).sin());
        f.image([0.0, 0.0, width, height], [sw, 0.0, sw, sh], 1.0);
        f.opacity = life;
        for half in &self.halves {
            let frac = ease_in_out(win(t, half.when.0, half.when.1));
            let drawn = partial(&half.points, frac);
            if drawn.len() < 2 {
                continue;
            }
            f.stroke_path(&Path::lines(&drawn), half.thick * u, &gold_pen(0.95, 180.0 * u), false, REFLECT);
            if half.thick > 1.0 && frac < 1.0 {
                let head = drawn[drawn.len() - 1];
                f.soft_dot(head[0], head[1], 18.0 * u, LIGHT, 0.7);
                f.star(head[0], head[1], 8.0 * u, WHITE, 0.95, 0.14);
            }
        }
        let frac = ease_in_out(win(t, OUTER_DRAW.0, OUTER_DRAW.1));
        for &(corner, sx, sy, which) in &self.corners {
            let k = clamp((frac - self.corners_at[which]) / 0.08);
            if k > 0.0 {
                f.opacity = life * k;
                f.stroke_path(&bracket(corner, sx, sy, u), 1.1 * u, &gold_pen(0.9, 60.0 * u), false, REFLECT);
                diamond(&mut f, corner, 5.5 * u * (0.6 + 0.4 * ease_out(k)), 1.0);
                f.opacity = life;
            }
        }
        for &(end, side) in &self.ends {
            let k = clamp((frac - 0.98) / 0.02);
            if k > 0.0 {
                diamond(&mut f, [end[0] - side * 5.0 * u, end[1]], 4.5 * u, k);
            }
        }
        self.title(&mut f, t, life);
        self.motes(&mut f, t);
        f
    }

    /// The title coming in, rising a little into place, a diamond either side; then a sheen across.
    fn title(&self, f: &mut Frame, t: f64, life: f64) {
        let u = self.u;
        let k = ease_out(win(t, TITLE_IN.0, TITLE_IN.1));
        if k <= 0.0 {
            return;
        }
        let (sh, [tw, th]) = (self.soft_size().1 as f64, self.title_px);
        f.opacity = life * k;
        let [x, y, w, h] = self.title_box;
        let place = [x, y + 6.0 * u * (1.0 - k), w, h];
        f.image(place, [0.0, sh, tw, th], 1.0);
        let centre = [place[0] + w / 2.0, place[1] + h / 2.0];
        for side in [-1.0, 1.0] {
            diamond(f, [centre[0] + side * (w / 2.0 - 4.0 * u), centre[1]], 4.0 * u, 1.0);
        }
        let sweep = win(t, SHEEN.0, SHEEN.1);
        if 0.0 < sweep && sweep < 1.0 {
            let middle = place[0] + w * (-0.15 + 1.3 * ease_in_out(sweep));
            for (half_width, strength) in [(22.0 * u, 0.35), (12.0 * u, 0.45), (5.0 * u, 0.6)] {
                f.clip = Clip::InRect([middle - half_width, place[1], half_width * 2.0, h]);
                f.opacity = life * k * strength * (PI * sweep).sin();
                f.image(place, [tw, sh, tw, th], 1.0);
            }
            f.clip = Clip::None;
        }
        f.opacity = life;
    }

    fn motes(&self, f: &mut Frame, t: f64) {
        let u = self.u;
        let g = self.gap;
        let clear = [g[0] - 40.0 * u, g[1] - 40.0 * u, g[2] + 80.0 * u, g[3] + 40.0 * u];
        for &[x0, y0, rise, sway, phase, size, start] in &self.motes {
            let a = ease_out(win(t, start, start + 0.7));
            if a <= 0.0 {
                continue;
            }
            let age = t - start;
            let (x, y) = (x0 + (age * 1.3 + phase).sin() * sway, y0 - rise * age);
            if contains(clear, [x, y]) {
                continue;
            }
            let twinkle = 0.55 + 0.45 * (age * 3.1 + phase * 2.0).sin();
            f.soft_dot(x, y, size * 3.2, CHAMPAGNE, 0.28 * a * twinkle);
            f.soft_dot(x, y, size, "#fffaf0", 0.85 * a * twinkle);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{Classic, TitleMask};

    fn mask() -> TitleMask {
        let (w, h) = (120, 40);
        let words = (0..w * h).map(|i| if (i % w) / 10 % 2 == 0 && (10..30).contains(&(i / w)) { 1.0 } else { 0.0 }).collect();
        TitleMask { w, h, words, text_height: 24.0 }
    }

    #[test]
    fn lays_out_the_same_every_time() {
        let (a, b) = (Classic::sample(1920.0, 1080.0, &mask()), Classic::sample(1920.0, 1080.0, &mask()));
        assert_eq!(a.motes.len(), 22);
        assert_eq!(a.motes[3][0].to_bits(), b.motes[3][0].to_bits());
        assert_eq!(a.atlas().2, b.atlas().2);
        assert_eq!(a.paint(1.0).prims.len(), b.paint(1.0).prims.len());
    }

    #[test]
    fn nothing_but_the_lobby_before_and_after() {
        let s = Classic::sample(1920.0, 1080.0, &mask());
        assert_eq!(s.paint(0.0).prims.len(), 1);
        assert_eq!(s.paint(super::DURATION).prims.len(), 1);
        assert!(s.paint(2.0).prims.len() > 40);
    }

    /// Every frame Python drew (py_frames.py) is matched to at least 53 dB PSNR; skipped without a
    /// Vulkan, Metal or DX12 adapter.
    #[test]
    fn matches_the_python_frames() {
        use crate::lace::{check, gpu::Renderer};
        let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let lobby = check::load(&dir.join("spike/lobby_1920.png")).unwrap();
        let Ok(mut gpu) = Renderer::new(1920, 1080, lobby.as_raw()) else { return };
        let img = image::open(dir.join("classic/title_mask.png")).unwrap().to_luma8();
        let text = std::fs::read_to_string(dir.join("classic/title.txt")).unwrap();
        let words = img.pixels().map(|p| f32::from(p[0]) / 255.0).collect();
        let title = TitleMask { w: img.width() as usize, h: img.height() as usize, words, text_height: text.trim().parse().unwrap() };
        let s = Classic::sample(1920.0, 1080.0, &title);
        let (w, h, atlas) = s.atlas();
        gpu.set_atlas(w, h, atlas);
        let frames: Vec<_> = [0.5, 1.5, 2.0, 3.0, 4.0].iter().map(|&t| (t, s.paint(t))).collect();
        let worst = check::worst_psnr(&gpu, &dir.join("classic"), &frames).unwrap();
        assert!(worst >= 53.0, "{worst:.1} dB");
    }
}
