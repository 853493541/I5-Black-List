//! The scene's pictures, made once (claw.py's warm): the fog layers, the keep mask round the button,
//! the cloud over a name, the slashes with their frayed steps cleared near the button, and the notice.

use super::geom::{crescent, Affine};
use super::light::{blur, bloom, lerp3, load, mask, noise, picture, pyround, rgb, shrink, smooth, straight, Gray, Pic};

pub const FOG: &str = "#8fa3b8";
pub const FOG_DEEP: &str = "#55687d";
pub const LILAC: &str = "#c9b6ff";
pub const PURPLE: &str = "#8a5cff";
pub const CORE: &str = "#fbf8ff";
pub const SOFT: f64 = 0.5;
pub const LENGTH: f64 = 1100.0;
pub const THICK: f64 = 35.0;
pub const FRAYS: usize = 6;
const NOTICE_PAPER: [f64; 4] = [0.0, 335.0, 572.0, 416.0];
const NOTICE_WORDS: [f64; 4] = [585.0, 455.0, 1026.0, 177.0];
pub const NOTICE_HIGH: f64 = 42.0;

fn size(v: f64, least: f64) -> usize {
    pyround(v).max(least) as usize
}

/// _fog_layer: blue-grey haze at SOFT size, 1.16 times the stage, thick at the edges.
pub fn fog_layer(width: f64, height: f64, u: f64, seed: u32, strength: f32) -> Pic {
    let (w, h) = (size(width * SOFT * 1.16, 1.0), size(height * SOFT * 1.16, 1.0));
    let billows = noise(w, h, 120.0 * u * SOFT, 4, seed);
    let (deep, fog) = (rgb(FOG_DEEP), rgb(FOG));
    let density = |i: usize| {
        let nx = ((i % w) as f32 / w as f32 - 0.5) * 2.0;
        let ny = ((i / w) as f32 / h as f32 - 0.5) * 2.0;
        let edge = smooth(0.3, 1.1, (nx * nx * 0.8 + ny * ny).sqrt());
        ((0.18 + 1.1 * edge) * (0.6 + 0.7 * billows.v[i]) * strength).clamp(0.0, 1.0)
    };
    picture(w, h, |i| lerp3(deep, fog, smooth(0.35, 0.9, billows.v[i])), |i| density(i) * 0.96)
}

/// _away: none in the gap (x, y, w, h), easing to all over a soft edge round it.
pub fn away(gap: [f64; 4], x: f64, y: f64, u: f64) -> f32 {
    let dx = (gap[0] - x).max(x - gap[0] - gap[2]).max(0.0);
    let dy = (gap[1] - y).max(y - gap[1] - gap[3]).max(0.0);
    smooth(0.0, (95.0 * u) as f32, dx.hypot(dy) as f32).powf(0.8)
}

/// _keep: at SOFT size, 1 outside the gap, easing to 0 round it.
pub fn keep(width: f64, height: f64, gap: [f64; 4], u: f64) -> Pic {
    let (w, h) = (size(width * SOFT, 1.0), size(height * SOFT, 1.0));
    let a = |i: usize| away(gap, ((i % w) as f64 + 0.5) / SOFT, ((i / w) as f64 + 0.5) / SOFT, u);
    picture(w, h, |_| [1.0; 3], a)
}

/// _cloud: a puff of fog for one name, solid in the middle, wisps at the edge.
pub fn cloud(u: f64) -> Pic {
    let (w, h) = (size(220.0 * u, 8.0), size(90.0 * u, 8.0));
    let billows = noise(w, h, 26.0 * u, 3, 41);
    let (dark, light) = (rgb("#4b5d71"), rgb("#9fb1c4"));
    let density = |i: usize| {
        let nx = ((i % w) as f32 + 0.5) / w as f32 * 2.0 - 1.0;
        let ny = ((i / w) as f32 + 0.5) / h as f32 * 2.0 - 1.0;
        let core = smooth(0.82, 0.55, (nx.abs() * 0.95).max(ny.abs() * 1.15));
        let wisps = smooth(1.0, 0.6, (nx * nx + ny * ny).sqrt()) * (0.55 + 0.6 * billows.v[i]);
        core.max(wisps).clamp(0.0, 1.0)
    };
    picture(w, h, |i| lerp3(dark, light, smooth(0.3, 0.85, billows.v[i])), density)
}

/// _slash_sprite: one slash lit per pixel, white-hot core, lilac round it, a purple glow. Centred, along +x.
pub fn slash_sprite(length: f64, thick: f64, u: f64) -> Pic {
    let margin = 70.0 * u;
    let (w, h) = (size(length + margin * 2.0, 8.0), size(thick + margin * 2.0, 8.0));
    let shape = crescent(length, thick);
    let (cx, cy) = (w as f64 / 2.0, h as f64 / 2.0);
    let core = mask(w, h, &[shape.iter().map(|p| [p[0] + cx, p[1] + cy]).collect()]);
    let inner = mask(w, h, &[shape.iter().map(|p| [p[0] + cx, p[1] * 0.45 + cy]).collect()]);
    let sharp = (1.2 * u).max(1.0);
    let lit = bloom(&core, LILAC, &[(sharp * 1.5, 1.0), (6.0 * u, 0.9), (18.0 * u, 0.6), (40.0 * u, 0.45)], 0.6).floats();
    let (hot_c, purple) = (rgb(CORE), rgb(PURPLE));
    let colored: Vec<([f32; 3], f32)> = (0..w * h)
        .map(|i| {
            let hot = (inner.v[i] * 1.2).clamp(0.0, 1.0);
            let color = lerp3(straight(lit[i]), hot_c, hot);
            let alpha = lit[i][3].max(hot);
            let deep = (alpha - core.v[i]).clamp(0.0, 1.0);
            (lerp3(color, purple, 0.35 * deep), alpha)
        })
        .collect();
    picture(w, h, |i| colored[i].0, |i| colored[i].1)
}

/// _frayed: the slash a share k frayed away, its ends first, in wisps.
pub fn frayed(sprite: &Pic, k: f32, seed: u32) -> Pic {
    let (w, h) = (sprite.w, sprite.h);
    let px = sprite.floats();
    let grain = noise(w, h, 34.0, 2, 100 + seed);
    let keep = |i: usize| {
        let xs = (-1.0 + 2.0 * (i % w) as f64 / (w - 1) as f64).abs() as f32;
        smooth(-0.15, 0.45, (1.0 - k) * 1.25 - xs * 0.55 - (grain.v[i] - 0.5) * 0.8).clamp(0.0, 1.0) * (1.0 - 0.5 * k)
    };
    let out: Vec<[f32; 4]> = (0..w * h).map(|i| px[i].map(|c| c * keep(i))).collect();
    picture(w, h, |i| straight(out[i]), |i| out[i][3])
}

/// A slash as it lies at `place`: its pictures faded near the button and gone from there to its
/// bottom end, and how much of it shows along its length (65 steps, bottom end to top).
pub struct Slash {
    pub place: Affine,
    pub sprite: Pic,
    pub frayed: Vec<Pic>,
    pub along: Vec<f64>,
}

pub fn cleared(sprite: &Pic, frayed: &[Pic], place: Affine, gap: [f64; 4], u: f64) -> Slash {
    let half = LENGTH * u / 2.0;
    let line: Vec<f64> = (0..65).map(|i| -half + 2.0 * half * f64::from(i) / 64.0).collect();
    let near: Vec<f64> = line.iter().map(|&s| f64::from(away(gap, place.m11 * s + place.dx, place.m12 * s + place.dy, u))).collect();
    let mut along = near.clone();
    for i in (0..64).rev() {
        along[i] = along[i].min(along[i + 1]);
    }
    let (sw, sh) = (sprite.w, sprite.h);
    let interp = |x: f64| {
        if x <= line[0] {
            return along[0];
        }
        let step = line[1] - line[0];
        let j = (((x - line[0]) / step) as usize).min(63);
        let f = ((x - line[j]) / step).min(1.0);
        along[j] * (1.0 - f) + along[j + 1] * f
    };
    let col: Vec<f64> = (0..sw).map(|x| interp(x as f64 + 0.5 - sw as f64 / 2.0)).collect();
    let keep = Gray::from_fn(sw, sh, |xi, yi| {
        let (x, y) = (xi as f64 + 0.5 - sw as f64 / 2.0, yi as f64 + 0.5 - sh as f64 / 2.0);
        let a = away(gap, place.m11 * x + place.m21 * y + place.dx, place.m12 * x + place.m22 * y + place.dy, u);
        a.min(col[xi] as f32)
    });
    if keep.v.iter().all(|&k| k > 0.995) {
        return Slash { place, sprite: sprite.clone(), frayed: frayed.to_vec(), along };
    }
    let fade = |pic: &Pic| {
        let f = pic.floats();
        picture(pic.w, pic.h, |i| straight(f[i]), |i| f[i][3] * keep.v[i])
    };
    Slash { place, sprite: fade(sprite), frayed: frayed.iter().map(fade).collect(), along }
}

/// _place: where a slash lies, from the middle of its picture.
pub fn place(centre: [f64; 2], offset: f64, u: f64) -> Affine {
    Affine::default().translate(centre[0], centre[1]).rotate(-34.0).translate(-offset * 29.0 * u, offset * 106.0 * u).scale(1.0 - 0.08 * offset.abs(), 1.0)
}

/// _landing: the strike placed so the claw's middle is the screen's middle.
pub fn landing(width: f64, height: f64, u: f64, offsets: &[f64]) -> [f64; 2] {
    let shape = crescent(LENGTH * u, THICK * u);
    let mut b = [f64::MAX, f64::MAX, f64::MIN, f64::MIN];
    for &o in offsets {
        for p in shape.iter().map(|&p| place([0.0, 0.0], o, u).map(p)) {
            b = [b[0].min(p[0]), b[1].min(p[1]), b[2].max(p[0]), b[3].max(p[1])];
        }
    }
    [width * 0.5 - (b[0] + b[2]) / 2.0, height * 0.5 - (b[1] + b[3]) / 2.0]
}

/// _notice_art: the newspaper, the words, the words blurred and the dark band, at twice the size
/// they show, and where the paper and the words sit (x, y, w, h) from the words' right middle.
pub struct Notice {
    pub paper: Pic,
    pub words: Pic,
    pub soft: Pic,
    pub band: Pic,
    pub paper_box: [f64; 4],
    pub words_box: [f64; 4],
}

pub fn notice_art(u: f64, assets: &std::path::Path) -> Result<Notice, String> {
    let k = NOTICE_HIGH * u / NOTICE_WORDS[3];
    let (right, middle) = (NOTICE_WORDS[0] + NOTICE_WORDS[2], NOTICE_WORDS[1] + NOTICE_WORDS[3] / 2.0);
    let at = |b: [f64; 4]| [(b[0] - right) * k, (b[1] - middle) * k, b[2] * k, b[3] * k];
    let (paper_box, words_box) = (at(NOTICE_PAPER), at(NOTICE_WORDS));
    let fetch = |name: &str, b: [f64; 4]| -> Result<Pic, String> { Ok(shrink(&load(&assets.join(name))?, size(b[2] * 2.0, 1.0), size(b[3] * 2.0, 1.0))) };
    let (paper, words) = (fetch("orator_paper.png", paper_box)?, fetch("orator_words.png", words_box)?);
    let soft = blurred(&words, 5.0 * u * 2.0);
    let (bw, bh) = (pyround(words_box[2] * 1.3 + 90.0 * u) as usize, pyround(words_box[3] * 1.9) as usize);
    let band_a = |i: usize| {
        let (x, y) = ((i % bw) as f32 / bw as f32, (i / bw) as f32 / bh as f32);
        smooth(0.0, 0.35, x) * smooth(1.0, 0.85, x) * smooth(0.0, 0.3, y) * smooth(1.0, 0.7, y) * 0.62
    };
    let band = picture(bw, bh, |_| [0.0; 3], band_a);
    Ok(Notice { paper, words, soft, band, paper_box, words_box })
}

/// _blurred: a picture softened, its glow spread.
fn blurred(pic: &Pic, sigma: f64) -> Pic {
    let f = pic.floats();
    let chans: Vec<Gray> = (0..4).map(|c| blur(&Gray::from_fn(pic.w, pic.h, |x, y| f[y * pic.w + x][c]), sigma)).collect();
    let px = |i: usize| [chans[0].v[i], chans[1].v[i], chans[2].v[i], chans[3].v[i]];
    picture(pic.w, pic.h, |i| straight(px(i)), |i| (px(i)[3] * 1.3).clamp(0.0, 1.0))
}
