//! The 场景 hotkey's quick play (ui.py play_quick_scene): the chosen 场景 at once, with no check, as a 嘉宾 lobby
//! would get it: the rose ring on 准备案件还原, the scene over the game, its music.

use super::flow::Flow;
use super::stubs::{CheckResult, Look, Rect, Stage, Target};

/// 准备案件还原 on a 16:9 game screen (love_scenes.sample_stage's button, at 1920 x 1080).
pub fn button_on(game: Rect) -> Rect {
    let (sx, sy) = (f64::from(game.w) / 1920.0, f64::from(game.h) / 1080.0);
    let at = |v: f64, s: f64| (v * s).round() as i32;
    Rect { x: game.x + at(549.0, sx), y: game.y + at(749.0, sy), w: at(556.0, sx), h: at(94.0, sy) }
}

impl Flow {
    /// Why the quick play plays nothing now (_quick_refusal): before 使用声明, and while a real lobby is checked or
    /// its marks show.
    pub fn quick_refusal(&self) -> Option<&'static str> {
        if !self.mode.disclaimer {
            Some("使用声明 not agreed to")
        } else if self.busy() {
            Some("a check runs")
        } else if self.marks_shown() {
            Some("a lobby's marks show")
        } else {
            None
        }
    }

    /// Plays `scene` over the last lobby's game, else over `screen` as a full-screen game; pressed again it starts
    /// over. True when it played.
    pub fn quick_play(&mut self, scene: &str, screen: Rect, now: f64) -> bool {
        if let Some(why) = self.quick_refusal() {
            self.log.push(format!("场景 hotkey: nothing played ({why})."));
            return false;
        }
        self.end_quick();
        let (game, button) = self.last_game.unwrap_or((screen, button_on(screen)));
        let marks = CheckResult { header_found: true, button_box: Some(button), game_box: Some(game), ..CheckResult::default() };
        self.ports.player.play_tune(scene);
        self.ports.overlay.dress(scene);
        self.ports.overlay.show(button, &marks, Look::Liked, Target::Screen);
        self.ports.scenes.play(scene, Stage { game, button, target: Target::Screen });
        self.quick_until = Some(now + stage::clock::duration(scene));
        self.log.push(format!("场景 hotkey: {scene} plays."));
        true
    }

    /// The quick play is over: its marks and scene come down.
    pub fn end_quick(&mut self) {
        if self.quick_until.take().is_some() {
            self.ports.overlay.hide();
            self.ports.scenes.stop();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_button_sits_where_the_lobby_puts_it_on_a_16_by_9_game() {
        assert_eq!(button_on(Rect { x: 0, y: 0, w: 1920, h: 1080 }), Rect { x: 549, y: 749, w: 556, h: 94 });
        assert_eq!(button_on(Rect { x: -2560, y: 0, w: 2560, h: 1440 }), Rect { x: -1828, y: 999, w: 741, h: 125 });
    }
}
