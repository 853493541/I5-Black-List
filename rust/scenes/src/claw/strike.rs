//! The strike and what comes with it: three slashes ripping down, the flash, the jolt, the burst and
//! the pink smoke; and the 演说家遇袭 notice sliding up top right.

use super::art::{LENGTH, LILAC, PURPLE};
use super::frame::Frame;
use super::light::Pt;
use super::{Claw, PINK, SLASHES};
use crate::draw::{clamp, ease_in, ease_out, win};

const GROW: f64 = 0.075;
const HOLD: f64 = 0.32;
const FRAY: f64 = 0.55;
const NOTICE_HOLD: f64 = 2.35;
const NOTICE_OUT: f64 = 0.45;
const NOTICE_SLIDE: f64 = 0.32;

pub fn ease_back(k: f64, s: f64) -> f64 {
    let k = clamp(k) - 1.0;
    1.0 + (s + 1.0) * k.powi(3) + s * k * k
}

/// The flash: at once, then gone in under a third of a second.
pub fn flash_level(age: f64) -> f64 {
    if !(0.0..=0.3).contains(&age) {
        return 0.0;
    }
    (1.0 - age / 0.3).powi(2)
}

/// The screen's jolt as the strike lands: a hard shake dying away.
pub fn jolt(age: f64, u: f64) -> Pt {
    if !(0.0..=0.35).contains(&age) {
        return [0.0, 0.0];
    }
    let fall = (-age * 14.0).exp();
    [14.0 * u * fall * (age * 95.0).sin(), 9.0 * u * fall * (age * 77.0).cos()]
}

/// One set of three slashes, the top one first: each rips down in GROW with a hot point leading it,
/// holds, then frays away.
pub fn strike(c: &Claw, p: &mut Frame, age: f64) {
    if age < 0.0 || age > 0.07 + GROW + HOLD + FRAY {
        return;
    }
    let (u, length) = (c.u, LENGTH * c.u);
    for (i, (&(offset, delay), slash)) in SLASHES.iter().zip(&c.slashes).enumerate() {
        let a = age - delay;
        if a < 0.0 {
            continue;
        }
        let (sw, sh) = (slash.sprite.w as f64, slash.sprite.h as f64);
        let size = (slash.sprite.w, slash.sprite.h);
        let grown = ease_out(clamp(a / GROW));
        p.save();
        p.tf = p.tf.then(slash.place);
        let bx = [-sw / 2.0, -sh / 2.0, sw, sh];
        if a < GROW {
            // The strike runs up to the right (+x), so its top end is at +x: it opens from there down.
            let tip = length / 2.0 - length * grown;
            let clip = [tip - 30.0 * u, -sh / 2.0, sw / 2.0 - tip + 30.0 * u, sh];
            p.image(c.tex.slashes[i], size, bx, Some(clip), None);
            let at = (1.0 - grown) * 64.0;
            let j = (at as usize).min(63);
            let shown = slash.along[j] + (slash.along[j + 1] - slash.along[j]) * (at - j as f64);
            p.soft_dot(tip, -2.0 * u, 46.0 * u, LILAC, 0.75 * shown);
            p.soft_dot(tip, -2.0 * u, 14.0 * u, "#ffffff", shown);
        } else if a < GROW + HOLD {
            p.opacity *= 0.9 + 0.1 * (a * 40.0 + offset).sin();
            p.image(c.tex.slashes[i], size, bx, None, None);
        } else {
            let k = clamp((a - GROW - HOLD) / FRAY);
            let step = ((k * 6.0) as usize).min(5);
            p.opacity *= 1.0 - ease_in(k) * 0.6;
            p.image(c.tex.frayed[i][step], size, bx, None, None);
        }
        p.restore();
    }
}

/// Where the strike lands: a burst of purple light and a white core.
pub fn impact(p: &mut Frame, age: f64, centre: Pt, u: f64) {
    if !(0.0..=0.6).contains(&age) {
        return;
    }
    let k = 1.0 - age / 0.6;
    p.soft_dot(centre[0], centre[1], 300.0 * u * (0.7 + 0.5 * (1.0 - k)), PURPLE, 0.45 * k);
    p.soft_dot(centre[0], centre[1], 90.0 * u, "#ffffff", 0.8 * k * k);
}

/// A puff of pink smoke thrown out from the strike, swelling and rising as it thins.
pub fn puff(p: &mut Frame, age: f64, centre: Pt, puff: &[[f64; 4]], u: f64) {
    if !(0.0..=1.2).contains(&age) {
        return;
    }
    for &[angle, reach, size, delay] in puff {
        let a = age - delay;
        if a <= 0.0 {
            continue;
        }
        let k = clamp(a);
        let out = ease_out(k);
        let x = centre[0] + angle.cos() * reach * out;
        let y = centre[1] + angle.sin() * reach * out * 0.6 - 40.0 * u * k;
        p.soft_dot(x, y, size * (0.6 + 0.9 * out), PINK, 0.32 * (1.0 - k).powf(1.4));
    }
}

/// 演说家遇袭 top right, as the game shows it: up from below, the newspaper tossed up wobbling, the
/// words coming into focus over the dark band; held; then it rises a little and is gone.
pub fn notice(c: &Claw, p: &mut Frame, age: f64, right_middle: Pt) {
    if age < 0.0 || age > NOTICE_HOLD + NOTICE_OUT {
        return;
    }
    let (u, n, tex) = (c.u, &c.notice, c.tex.notice);
    let leave = ease_in(win(age, NOTICE_HOLD, NOTICE_HOLD + NOTICE_OUT));
    let slide = 70.0 * u * (1.0 - ease_back(clamp(age / NOTICE_SLIDE), 1.4));
    p.save();
    p.tf = p.tf.translate(right_middle[0], right_middle[1] + slide - 10.0 * u * leave);
    p.opacity *= clamp(age / 0.1);
    let base = p.opacity;
    let focus = ease_out(win(age, 0.12, 0.34)) * (1.0 - leave);
    let wb = n.words_box;
    if focus > 0.0 {
        let (bw, bh) = (n.band.w as f64, n.band.h as f64);
        p.opacity = base * focus;
        p.image(tex[3], (n.band.w, n.band.h), [wb[0] + wb[2] - bw + 30.0 * u, wb[1] + wb[3] / 2.0 - bh / 2.0, bw, bh], None, None);
        p.opacity = base * (1.0 - focus) * (focus * 3.0).min(1.0);
        p.image(tex[2], (n.soft.w, n.soft.h), wb, None, None);
        p.opacity = base * focus;
        p.image(tex[1], (n.words.w, n.words.h), wb, None, None);
    }
    let rise = ease_out(clamp(age / 0.2));
    let settle = (age - 0.2).max(0.0);
    let turn = -16.0 * (1.0 - rise) + 7.0 * (-settle * 9.0).exp() * (settle * 30.0).sin();
    let alpha = clamp(age / 0.05) * (1.0 - leave);
    let pb = n.paper_box;
    let centre = [pb[0] + pb[2] / 2.0, pb[1] + pb[3] / 2.0];
    let ghosts: &[f64] = if rise < 1.0 { &[2.0, 1.0, 0.0] } else { &[0.0] };
    for &ghost in ghosts {
        p.save();
        p.opacity = base * alpha * if ghost == 0.0 { 1.0 } else { 0.22 / ghost };
        p.tf = p.tf.translate(centre[0], centre[1] + 40.0 * u * (1.0 - rise) + ghost * 9.0 * u * (1.0 - rise)).rotate(turn);
        p.image(tex[0], (n.paper.w, n.paper.h), [-pb[2] / 2.0, -pb[3] / 2.0, pb[2], pb[3]], None, None);
        p.restore();
    }
    p.restore();
}
