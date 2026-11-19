//! Whether a scene's pixels reached the screen: the desktop copied before the scene and while it plays, against
//! the frame the scene drew (premultiplied BGRA, the window's size). A swap chain that presents nothing (a hybrid
//! laptop's chips, a composition the desktop drops) leaves the screen as it was.

/// A frame needs this many solid pixels (alpha 200 and up, unlike what was under them) to tell; fewer while fading in.
pub const MIN_SOLID: usize = 500;
/// Below this share of its solid pixels on screen, the scene is not seen.
pub const SHOWN: f64 = 0.3;
/// A channel this far apart is a change.
const STEP: i32 = 24;

/// The share of the frame's solid pixels that changed on screen; None when the frame has too few to tell.
pub fn shown_share(before: &[u8], after: &[u8], frame: &[u8]) -> Option<f64> {
    let (mut solid, mut changed) = (0usize, 0usize);
    for ((b, a), f) in before.chunks_exact(4).zip(after.chunks_exact(4)).zip(frame.chunks_exact(4)) {
        if f[3] < 200 {
            continue;
        }
        let keep = 255 - i32::from(f[3]);
        let differs = (0..3).any(|i| (i32::from(f[i]) + i32::from(b[i]) * keep / 255 - i32::from(b[i])).abs() > STEP);
        if !differs {
            continue;
        }
        solid += 1;
        if (0..3).any(|i| (i32::from(a[i]) - i32::from(b[i])).abs() > STEP) {
            changed += 1;
        }
    }
    (solid >= MIN_SOLID).then(|| changed as f64 / solid as f64)
}

/// RGBA and BGRA swapped in place (a swap chain in Rgba8Unorm against GDI's BGRA).
pub fn swap_red_blue(px: &mut [u8]) {
    for p in px.chunks_exact_mut(4) {
        p.swap(0, 2);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fill(n: usize, p: [u8; 4]) -> Vec<u8> {
        p.repeat(n)
    }

    #[test]
    fn a_scene_on_screen_is_seen_and_one_that_presents_nothing_is_not() {
        let n = 2000;
        let before = fill(n, [20, 40, 60, 255]);
        let frame = fill(n, [200, 100, 250, 255]);
        let after = frame.clone();
        assert_eq!(shown_share(&before, &after, &frame), Some(1.0));
        assert_eq!(shown_share(&before, &before, &frame), Some(0.0));
    }

    #[test]
    fn a_frame_still_fading_in_cannot_tell() {
        let n = 2000;
        let before = fill(n, [20, 40, 60, 255]);
        let frame = fill(n, [10, 10, 10, 40]);
        assert_eq!(shown_share(&before, &before, &frame), None);
        // Solid but the same colour as the game under it: nothing to tell either.
        let same = fill(n, [20, 40, 60, 255]);
        assert_eq!(shown_share(&before, &before, &same), None);
    }

    #[test]
    fn red_and_blue_swap() {
        let mut px = vec![1, 2, 3, 4, 5, 6, 7, 8];
        swap_red_blue(&mut px);
        assert_eq!(px, vec![3, 2, 1, 4, 7, 6, 5, 8]);
    }
}
