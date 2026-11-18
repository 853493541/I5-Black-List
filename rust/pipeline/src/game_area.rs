//! game_area.py: where the game is drawn on screen, so the border and the glow fit it. `game_rect` is plain
//! arithmetic; the window questions are asked of Windows only (see `win32`), and elsewhere find nothing.

/// How far a window's top and bottom may be from where the lobby puts the game, in the game's height, for the window
/// to be the game's own.
pub const FIT: f64 = 0.04;

/// A rectangle in desktop pixels: left, top, right, bottom.
pub type ScreenRect = [i64; 4];

/// game_rect: the window under the lobby when it fits the lobby, else where the lobby puts it, inside that window.
pub fn game_rect(window: Option<ScreenRect>, estimate: Option<[f64; 4]>) -> Option<ScreenRect> {
    let Some([left, top, right, bottom]) = estimate else { return window };
    let height = bottom - top;
    if height <= 0.0 {
        return window;
    }
    let round = |v: f64| crate::image::py_round(v);
    let Some([w_left, w_top, w_right, w_bottom]) = window else {
        return Some([round(left), round(top), round(right), round(bottom)]);
    };
    let (w_left, w_top, w_right, w_bottom) = (w_left as f64, w_top as f64, w_right as f64, w_bottom as f64);
    if (w_top - top).abs() <= FIT * height
        && (w_bottom - bottom).abs() <= FIT * height
        && w_right - w_left <= right - left + 2.0 * FIT * height
    {
        return window;
    }
    let inside = [w_left.max(left), w_top.max(top), w_right.min(right), w_bottom.min(bottom)];
    if inside[2] - inside[0] < height / 2.0 || inside[3] - inside[1] < height / 2.0 {
        return window;
    }
    Some(inside.map(round))
}

#[cfg(windows)]
#[path = "win32.rs"]
mod win32;
#[cfg(windows)]
pub use win32::{exclusive_fullscreen, inner_rect_of, window_order, window_rect_at};

/// window_order: the top-level windows, front to back (none off Windows).
#[cfg(not(windows))]
pub fn window_order() -> Vec<isize> {
    Vec::new()
}

/// window_rect_at: the client area of what draws at (x, y), this app's windows passed over (none off Windows).
#[cfg(not(windows))]
pub fn window_rect_at(_x: i32, _y: i32, _order: &[isize], _innermost: bool) -> Option<ScreenRect> {
    None
}

/// inner_rect_of: the innermost window of hwnd's own that draws at (x, y) (none off Windows).
#[cfg(not(windows))]
pub fn inner_rect_of(_hwnd: isize, _x: i32, _y: i32) -> Option<ScreenRect> {
    None
}

/// exclusive_fullscreen: whether a Direct3D program holds the screen (never off Windows).
#[cfg(not(windows))]
pub fn exclusive_fullscreen() -> bool {
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_window_that_fits_the_lobby_is_the_game() {
        let estimate = Some([100.0, 50.0, 1700.0, 950.0]);
        assert_eq!(game_rect(Some([90, 40, 1710, 960]), estimate), Some([90, 40, 1710, 960]));
    }

    #[test]
    fn a_bigger_window_is_cut_to_the_lobby() {
        let estimate = Some([100.4, 50.5, 1700.5, 950.0]);
        assert_eq!(game_rect(Some([0, 0, 1920, 1080]), estimate), Some([100, 50, 1700, 950]));
    }

    #[test]
    fn without_a_window_the_estimate_is_rounded_and_without_an_estimate_the_window_stays() {
        assert_eq!(game_rect(None, Some([0.5, 1.5, 2.5, 3.5])), Some([0, 2, 2, 4]));
        assert_eq!(game_rect(Some([1, 2, 3, 4]), None), Some([1, 2, 3, 4]));
        assert_eq!(game_rect(Some([0, 0, 10, 10]), Some([500.0, 500.0, 900.0, 800.0])), Some([0, 0, 10, 10]));
        assert_eq!(game_rect(None, Some([0.0, 5.0, 10.0, 5.0])), None);
    }

    #[test]
    fn off_windows_nothing_is_found() {
        #[cfg(not(windows))]
        {
            assert!(window_order().is_empty());
            assert_eq!(window_rect_at(0, 0, &[], true), None);
            assert_eq!(inner_rect_of(1, 0, 0), None);
            assert!(!exclusive_fullscreen());
        }
    }
}
