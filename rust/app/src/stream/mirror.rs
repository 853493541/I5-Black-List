//! 直播画面's geometry (ui_stream.py `_place`, `_fit`, `to_window`): where the window sits and where the game
//! is drawn in it. Pure numbers; the window itself is ui/stream/mirror.slint, moved by the win package.

/// A rectangle in desktop pixels, as Qt's QRect: `right()` is `x + width - 1`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

impl Rect {
    pub const fn new(x: i32, y: i32, width: i32, height: i32) -> Self {
        Self { x, y, width, height }
    }

    pub fn is_empty(&self) -> bool {
        self.width <= 0 || self.height <= 0
    }

    /// Qt's `right()`: the last column inside.
    pub fn right(&self) -> i32 {
        self.x + self.width - 1
    }

    fn contains(&self, x: i32, y: i32) -> bool {
        x >= self.x && x <= self.right() && y >= self.y && y < self.y + self.height
    }

    fn center(&self) -> (i32, i32) {
        // Qt's QRect::center: (left + right) / 2, (top + bottom) / 2.
        ((2 * self.x + self.width - 1) / 2, (2 * self.y + self.height - 1) / 2)
    }
}

/// Where the window sits, each tried in turn until Windows would capture it there (`ui_stream.SPOTS`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Spot {
    /// Just right of every monitor.
    Off,
    /// Touching the rightmost screen by one pixel.
    Edge,
    /// On the game's screen, behind every window.
    On,
}

impl Spot {
    pub const ALL: [Spot; 3] = [Spot::Off, Spot::Edge, Spot::On];

    pub fn key(self) -> &'static str {
        match self {
            Spot::Off => "off",
            Spot::Edge => "edge",
            Spot::On => "on",
        }
    }

    /// For the log (`_WHERE`).
    pub fn words(self) -> &'static str {
        match self {
            Spot::Off => "off the screen",
            Spot::Edge => "at the screen's right edge",
            Spot::On => "on the screen, behind every window",
        }
    }

    /// The spots to try, in turn: on Windows 10 (build < 22000) never off the screen.
    pub fn to_try(windows_10: bool) -> &'static [Spot] {
        if windows_10 {
            &Spot::ALL[1..]
        } else {
            &Spot::ALL
        }
    }
}

/// The window's rectangle for `area` at `spot`: 16:9, as wide as area's screen (`_place`).
/// `screens` are the monitors; the first is the primary one.
pub fn place(area: Rect, spot: Spot, screens: &[Rect]) -> Rect {
    let fallback = Rect::new(0, 0, 1920, 1080);
    let (cx, cy) = area.center();
    let home = screens
        .iter()
        .find(|screen| screen.contains(cx, cy))
        .or_else(|| screens.first())
        .copied()
        .unwrap_or(fallback);
    let rightmost = screens.iter().copied().max_by_key(Rect::right).unwrap_or(home);
    let (x, y) = match spot {
        Spot::Off => (rightmost.right() + 64, home.y),
        Spot::Edge => (rightmost.right(), rightmost.y),
        Spot::On => (home.x, home.y),
    };
    Rect::new(x, y, home.width, round_half_even(f64::from(home.width) * 9.0 / 16.0) as i32)
}

/// Python's round(): halves to even.
fn round_half_even(value: f64) -> f64 {
    let rounded = value.round();
    if (value - value.trunc()).abs() == 0.5 && rounded % 2.0 != 0.0 {
        rounded - value.signum()
    } else {
        rounded
    }
}

/// Where 直播姬 has the game, read from its scene file (livehime package): the scale, where the game's
/// capture starts in this window, and where the game's window starts on the screen.
// stub: livehime
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Follows {
    pub scale: f64,
    pub start: (f64, f64),
    pub corner: (i32, i32),
}

/// The scale and offset that put `area` in a window of `size` (`_fit`): where 直播姬 has the game, or as
/// 直播姬 puts a new capture in a 16:9 canvas: as big as fits, centered.
pub fn fit(area: Rect, size: (i32, i32), follows: Option<Follows>) -> (f64, (f64, f64)) {
    if area.is_empty() {
        return (1.0, (0.0, 0.0));
    }
    if let Some(follows) = follows {
        let dx = f64::from(area.x - follows.corner.0) * follows.scale;
        let dy = f64::from(area.y - follows.corner.1) * follows.scale;
        return (follows.scale, (follows.start.0 + dx, follows.start.1 + dy));
    }
    let (w, h) = (f64::from(size.0), f64::from(size.1));
    let (aw, ah) = (f64::from(area.width), f64::from(area.height));
    let scale = (w / aw).min(h / ah);
    (scale, ((w - aw * scale) / 2.0, (h - ah * scale) / 2.0))
}

/// Where a point on the screen is drawn in the window (`to_window`).
pub fn to_window(point: (i32, i32), area: Rect, size: (i32, i32), follows: Option<Follows>) -> (f64, f64) {
    let (scale, offset) = fit(area, size, follows);
    (offset.0 + f64::from(point.0 - area.x) * scale, offset.1 + f64::from(point.1 - area.y) * scale)
}
