//! Frame geometry and pixels for the desktop copy (capture.py), pure so it is tested everywhere.

/// The match-found title sits in the upper part of the lobby; the watch copies only that band.
pub const TITLE_BAND_FRACTION: f64 = 0.40;

/// The virtual screen: every monitor's union, in screen pixels (GetSystemMetrics 76-79).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct VirtualScreen {
    pub left: i32,
    pub top: i32,
    pub width: i32,
    pub height: i32,
}

impl VirtualScreen {
    /// The rows a copy of `fraction` of the desktop takes, as capture.py rounds them; None for an empty screen.
    pub fn band_height(&self, fraction: f64) -> Option<i32> {
        if self.width <= 0 || self.height <= 0 {
            return None;
        }
        let fraction = if fraction.is_nan() { 1.0 } else { fraction.clamp(0.05, 1.0) };
        let rows = round_half_even(f64::from(self.height) * fraction) as i32;
        Some(rows.max(1).min(self.height))
    }

    /// A screen point in the frame's own pixels (the frame starts at the virtual screen's top-left).
    pub fn to_frame(&self, x: i32, y: i32) -> (i32, i32) {
        (x - self.left, y - self.top)
    }
}

/// Python's round(): halves go to the even neighbour.
pub fn round_half_even(value: f64) -> f64 {
    let rounded = value.round();
    if (value - value.trunc()).abs() == 0.5 && rounded % 2.0 != 0.0 {
        rounded - value.signum()
    } else {
        rounded
    }
}

/// One RGB copy of the desktop, row by row, 3 bytes a pixel.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Frame {
    pub width: usize,
    pub height: usize,
    pub rgb: Vec<u8>,
}

impl Frame {
    /// A frame from GDI's top-down 32-bit BGRA rows.
    pub fn from_bgra(width: usize, height: usize, bgra: &[u8]) -> Frame {
        let rgb = bgra.chunks_exact(4).take(width * height).flat_map(|p| [p[2], p[1], p[0]]).collect();
        Frame { width, height, rgb }
    }

    pub fn pixel(&self, x: usize, y: usize) -> [u8; 3] {
        let at = (y * self.width + x) * 3;
        [self.rgb[at], self.rgb[at + 1], self.rgb[at + 2]]
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    #[test]
    fn top_band_is_the_upper_part_of_the_desktop() {
        let screen = VirtualScreen { left: -1920, top: 0, width: 3840, height: 1080 };
        assert_eq!(screen.band_height(TITLE_BAND_FRACTION), Some(432));
        assert_eq!(screen.band_height(1.0), Some(1080));
        assert_eq!(screen.band_height(0.0), Some(54));
        assert_eq!(screen.band_height(7.0), Some(1080));
        assert_eq!(VirtualScreen { width: 0, ..screen }.band_height(0.4), None);
        assert_eq!(screen.to_frame(-1920, 5), (0, 5));
    }

    #[test]
    fn rounding_matches_python() {
        // round(2.5) == 2, round(3.5) == 4, round(0.5) == 0 in Python.
        assert_eq!((round_half_even(2.5), round_half_even(3.5), round_half_even(0.5), round_half_even(2.4)), (2.0, 4.0, 0.0, 2.0));
        // 1.25 rows of 0.05: round(25 * 0.05) == 1.
        let small = VirtualScreen { left: 0, top: 0, width: 4, height: 25 };
        assert_eq!(small.band_height(0.05), Some(1));
    }

    #[test]
    fn bgra_becomes_rgb() {
        let frame = Frame::from_bgra(2, 1, &[1, 2, 3, 255, 10, 20, 30, 0]);
        assert_eq!(frame.rgb, vec![3, 2, 1, 30, 20, 10]);
        assert_eq!(frame.pixel(1, 0), [30, 20, 10]);
    }

    proptest! {
        #[test]
        fn band_stays_inside_the_screen(height in 1i32..10_000, fraction in -2.0f64..3.0) {
            let screen = VirtualScreen { left: 0, top: 0, width: 10, height };
            let rows = screen.band_height(fraction).unwrap();
            prop_assert!(rows >= 1 && rows <= height);
        }

        #[test]
        fn bgra_keeps_every_pixel(width in 1usize..16, height in 1usize..16, seed in any::<u8>()) {
            let bgra: Vec<u8> = (0..width * height * 4).map(|i| (i as u8).wrapping_mul(seed)).collect();
            let frame = Frame::from_bgra(width, height, &bgra);
            prop_assert_eq!(frame.rgb.len(), width * height * 3);
            let last = width * height - 1;
            prop_assert_eq!(frame.pixel(last % width, last / width), [bgra[last * 4 + 2], bgra[last * 4 + 1], bgra[last * 4]]);
        }
    }
}
