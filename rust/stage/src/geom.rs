//! Where a scene plays: love_scenes.Stage and the gap LoveBorder.play leaves round the button.

/// x, y, w, h in the border window's own points (QRectF's order).
pub type Rect = [f64; 4];
/// x, y.
pub type Pt = [f64; 2];

/// love_scenes.DESIGN: the lobby size the scenes were drawn at.
pub const DESIGN: [f64; 2] = [1635.0, 848.0];

/// Where a scene plays, in the border window's own points (love_scenes.Stage).
#[derive(Clone, Debug, PartialEq)]
pub struct Stage {
    pub width: f64,
    pub height: f64,
    /// The bottom area round the button and its marks, which stays bare.
    pub gap: Rect,
    /// The 嘉宾 heart beside the button.
    pub badge: Option<Pt>,
    /// The twelve players' names, where the check read them, when it did.
    pub seats: Vec<Rect>,
}

impl Stage {
    pub fn new(width: f64, height: f64, gap: Rect) -> Self {
        Self {
            width,
            height,
            gap,
            badge: None,
            seats: Vec::new(),
        }
    }

    pub fn unit(&self) -> f64 {
        (self.width / DESIGN[0]).min(self.height / DESIGN[1])
    }

    /// The twelve names: where the check read them, else where the lobby's layout puts them on a
    /// stage this size (the preview, the 场景 hotkey with no lobby seen).
    pub fn names(&self) -> Vec<Rect> {
        if !self.seats.is_empty() {
            return self.seats.clone();
        }
        let (w, h) = (self.width, self.height);
        lobby::NAME_BOXES
            .iter()
            .map(|&[left, top, right, bottom]| {
                [left * w, top * h, (right - left) * w, (bottom - top) * h]
            })
            .collect()
    }

    /// The heart badge, or where it would be: just right of the gap's middle.
    pub fn heart(&self) -> Pt {
        if let Some(badge) = self.badge {
            return badge;
        }
        let [x, y, w, _] = self.gap;
        [x + w / 2.0 + w * 0.33, y + 72.0 * self.unit()]
    }
}

/// A rectangle on the desktop in whole pixels, x, y, w, h (QRect).
pub type ScreenRect = [i32; 4];

/// What LoveBorder.play is given: the game's screen, the button and its marks to leave bare, the 嘉宾
/// heart and the names, all on the desktop.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Placement {
    pub area: ScreenRect,
    pub keep_clear: ScreenRect,
    pub badge: Option<[i32; 2]>,
    pub seats: Vec<Rect>,
}

impl Placement {
    /// The stage in the window's own points: the gap reaches 28 points either side of the button, 30
    /// above it, and down to the bottom of the game.
    pub fn stage(&self) -> Stage {
        let [ax, ay, aw, ah] = self.area;
        let [kx, ky, kw, _] = self.keep_clear;
        let (left, top) = (f64::from(kx - ax), f64::from(ky - ay));
        let gap = [
            left - 28.0,
            top - 30.0,
            f64::from(kw) + 56.0,
            f64::from(ah) - top + 30.0,
        ];
        let (ox, oy) = (f64::from(ax), f64::from(ay));
        Stage {
            width: f64::from(aw),
            height: f64::from(ah),
            gap,
            badge: self
                .badge
                .map(|[x, y]| [f64::from(x) - ox, f64::from(y) - oy]),
            seats: self
                .seats
                .iter()
                .map(|&[x, y, w, h]| [x - ox, y - oy, w, h])
                .collect(),
        }
    }
}

/// love_scenes.sample_stage: the fake-name sample lobby's stage, its button and the heart beside it.
pub fn sample_stage(width: f64, height: f64) -> Stage {
    let s = width / DESIGN[0];
    let keep = [549.0 * s, 749.0 * s, 556.0 * s, 94.0 * s];
    let gap = [
        keep[0] - 28.0 * s,
        keep[1] - 30.0 * s,
        keep[2] + 56.0 * s,
        height - keep[1] + 30.0 * s,
    ];
    Stage {
        width,
        height,
        gap,
        badge: Some([1052.0 * s, 796.0 * s]),
        seats: Vec::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn heart_sits_right_of_the_gap_middle() {
        let stage = Stage::new(1635.0, 848.0, [500.0, 700.0, 600.0, 148.0]);
        assert_eq!(stage.heart(), [500.0 + 300.0 + 198.0, 772.0]);
        assert_eq!(stage.names().len(), 12);
    }
}
