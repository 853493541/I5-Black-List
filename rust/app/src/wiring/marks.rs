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

/// The look for the scene that greets the lobby: its own (LOOKS), the rose for none.
pub fn look_of(scene: &str) -> overlay::Look {
    if scene.is_empty() {
        overlay::rose()
    } else {
        overlay::look_for(scene)
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
        pub errors: Vec<String>,
    }

    impl Default for ScreenMarks {
        fn default() -> Self {
            ScreenMarks { window: None, look: overlay::rose(), fading: None, errors: Vec::new() }
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
            if self.window.is_none() {
                match overlay::window::Overlay::new() {
                    Ok(window) => self.window = Some(window),
                    Err(error) => return self.errors.push(format!("Overlay: no window: {error}")),
                }
            }
            let Some(window) = self.window.as_mut() else { return };
            let game = ltrb(result.game_box.unwrap_or(game_rect));
            // 我's 场景 with nobody listed: the rose ring and badge alone.
            let extras = overlay::Extras { checking: None, mine: look == Look::Liked && result.likes.is_empty() };
            match window.show_faded(game, &overlay_result(result), &self.look, extras, 0) {
                Ok(shown) => self.fading = shown.then(Instant::now),
                Err(error) => self.errors.push(format!("Overlay: not shown: {error}")),
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
    }
}
