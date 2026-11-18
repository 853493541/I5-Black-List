//! The marks over the game (ui_overlay through the overlay crate): the check's seats as the overlay draws them,
//! dressed in the look of the scene that greets the lobby.

use super::stubs::{CheckResult, MarkKind, Rect};

/// (left, top, right, bottom), as the overlay crate takes boxes.
pub fn ltrb(rect: Rect) -> [i32; 4] {
    [rect.x, rect.y, rect.x + rect.w, rect.y + rect.h]
}

/// The check in the overlay's terms.
pub fn overlay_result(result: &CheckResult) -> overlay::CheckResult {
    let seats = result
        .seats
        .iter()
        .map(|seat| overlay::Seat {
            name: seat.name.clone(),
            rect: ltrb(seat.rect),
            kind: match &seat.kind {
                MarkKind::Blacklist { tags } => overlay::SeatKind::Blacklist { tags: tags.clone() },
                MarkKind::Guest => overlay::SeatKind::Guest,
                MarkKind::None => overlay::SeatKind::None,
            },
        })
        .collect();
    overlay::CheckResult { seats, button_box: result.button_box.map(ltrb), game_box: result.game_box.map(ltrb) }
}

/// The look for the scene that greets the lobby: its own (LOOKS; 竖琴清风 and 演说家遇袭 draw their own marks), the
/// rose for none.
pub fn look_of(scene: &str) -> overlay::Look {
    if scene.is_empty() {
        overlay::rose()
    } else {
        scenes::look(scene, &stage::scene_own::assets_dir())
    }
}

/// The marks fade in over 120 ms (ui_overlay._fade_in, linear): the opacity `ms` after they showed, None once done.
pub const FADE_MS: u128 = 120;

pub fn fade_opacity(ms: u128) -> Option<u8> {
    (ms < FADE_MS).then(|| (ms * 255 / FADE_MS) as u8)
}

#[cfg(windows)]
pub use self::windows::ScreenMarks;

#[cfg(windows)]
mod windows {
    use super::super::stubs::{CheckResult, Look, Overlay, Rect, Target};
    use super::{fade_opacity, look_of, ltrb, overlay_result};
    use std::time::Instant;

    /// The layered window of marks, made at the first check that shows any.
    pub struct ScreenMarks {
        window: Option<overlay::window::Overlay>,
        look: overlay::Look,
        fading: Option<Instant>,
        /// The game's rect the marks were laid out for, a point inside the game, and the window found there.
        tracked: Option<([i32; 4], (i32, i32), [i64; 4])>,
        pub errors: Vec<String>,
    }

    /// The game's window at a point (game_area.window_rect_at, the innermost one).
    fn window_at((x, y): (i32, i32)) -> Option<[i64; 4]> {
        pipeline::game_area::window_rect_at(x, y, &pipeline::game_area::window_order(), true)
    }

    impl ScreenMarks {
        fn window(&mut self) -> Option<&mut overlay::window::Overlay> {
            if self.window.is_none() {
                match overlay::window::Overlay::new() {
                    Ok(window) => self.window = Some(window),
                    Err(error) => self.errors.push(format!("Overlay: no window: {error}")),
                }
            }
            self.window.as_mut()
        }
    }

    impl Default for ScreenMarks {
        fn default() -> Self {
            ScreenMarks { window: None, look: overlay::rose(), fading: None, tracked: None, errors: Vec::new() }
        }
    }

    impl Overlay for ScreenMarks {
        fn dress(&mut self, scene: &str) {
            self.look = look_of(scene);
        }

        fn show(&mut self, game_rect: Rect, result: &CheckResult, look: Look, target: Target) {
            if target != Target::Screen {
                self.hide();
                return;
            }
            let game = ltrb(result.game_box.unwrap_or(game_rect));
            let button = result.button_box.unwrap_or(game_rect);
            let inside = (button.x + button.w / 2, button.y + button.h / 2);
            self.tracked = window_at(inside).map(|found| (game, inside, found));
            let Some(window) = self.window() else { return };
            // 我's 场景 with nobody listed: the rose ring and badge alone.
            let extras = overlay::Extras { checking: None, mine: look == Look::Liked && result.likes.is_empty() };
            match window.show_faded(game, &overlay_result(result), &self.look, extras, 0) {
                Ok(shown) => self.fading = shown.then(Instant::now),
                Err(error) => self.errors.push(format!("Overlay: not shown: {error}")),
            }
        }

        fn checking(&mut self, button: Rect) {
            let Some(window) = self.window() else { return };
            let at = ltrb(button);
            if let Err(error) = window.show_checking(at, at, "检查中") {
                self.errors.push(format!("Overlay: 检查中 not shown: {error}"));
            }
            self.fading = None;
        }

        fn follow(&mut self) {
            let Some((game, inside, before)) = self.tracked else { return };
            let Some(now) = window_at(inside) else { return };
            let (dx, dy) = ((now[0] - before[0]) as i32, (now[1] - before[1]) as i32);
            if (dx, dy) == (0, 0) {
                return;
            }
            let moved = [game[0] + dx, game[1] + dy, game[2] + dx, game[3] + dy];
            self.tracked = Some((moved, (inside.0 + dx, inside.1 + dy), now));
            if let Some(window) = self.window.as_mut() {
                if let Err(error) = window.follow(moved) {
                    self.errors.push(format!("Overlay: not moved: {error}"));
                }
            }
        }

        fn tick(&mut self) {
            let (Some(since), Some(window)) = (self.fading, self.window.as_mut()) else { return };
            let opacity = fade_opacity(since.elapsed().as_millis());
            if opacity.is_none() {
                self.fading = None;
            }
            if let Err(error) = window.set_opacity(opacity.unwrap_or(255)) {
                self.errors.push(format!("Overlay: fade: {error}"));
            }
        }

        fn hide(&mut self) {
            self.fading = None;
            self.tracked = None;
            if let Some(window) = self.window.as_mut() {
                window.hide();
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::super::stubs::SeatMark;
    use super::*;

    #[test]
    fn seats_reach_the_overlay_as_boxes_with_their_marks() {
        let result = CheckResult {
            seats: vec![
                SeatMark { name: "示例坏人".into(), rect: Rect { x: 10, y: 20, w: 100, h: 30 }, kind: MarkKind::Blacklist { tags: vec!["挂机".into()] } },
                SeatMark { name: "小鹿".into(), rect: Rect { x: 10, y: 60, w: 100, h: 30 }, kind: MarkKind::Guest },
            ],
            button_box: Some(Rect { x: -1720, y: 300, w: 200, h: 40 }),
            ..CheckResult::default()
        };
        let shown = overlay_result(&result);
        assert_eq!(shown.button_box, Some([-1720, 300, -1520, 340]));
        assert_eq!(shown.game_box, None);
        assert_eq!(shown.seats[0].rect, [10, 20, 110, 50]);
        assert_eq!(shown.seats[0].kind, overlay::SeatKind::Blacklist { tags: vec!["挂机".into()] });
        assert_eq!(shown.seats[1].kind, overlay::SeatKind::Guest);
    }

    #[test]
    fn the_marks_fade_in_over_120_ms() {
        assert_eq!(fade_opacity(0), Some(0));
        assert_eq!(fade_opacity(60), Some(127));
        assert_eq!(fade_opacity(119), Some(252));
        assert_eq!(fade_opacity(120), None);
    }

    #[test]
    fn the_marks_wear_the_greeting_scenes_look() {
        assert_eq!(look_of("").key, overlay::rose().key);
        assert_eq!(look_of("ice").key, overlay::look_for("ice").key);
        assert!(look_of("lyre").marks.is_some(), "竖琴清风 draws its own marks");
    }
}
