//! 直播模式's marks (ui_stream.StreamMirror): the marks a check shows, copied into 直播画面 where they are over the
//! game, for 直播姬 to capture; on the screen too in 完整模式, only there in 基础模式.

use crate::stream::mirror::{fit, place, to_window, Rect as MirrorRect, Spot};
use crate::{MirrorMark, StreamMirrorWindow};
use app::wiring::marks::{look_of, ltrb, overlay_result};
use app::wiring::stubs::{CheckResult, Look, Overlay, Rect, Target};
use data::store::Store;
use slint::{ComponentHandle, Model, ModelRc, VecModel};
use std::cell::RefCell;
use std::rc::Rc;

pub struct WithStream {
    pub screen: Box<dyn Overlay>,
    store: Rc<RefCell<Store>>,
    window: Option<StreamMirrorWindow>,
    look: overlay::Look,
    face: Option<overlay::text::Face>,
}

impl WithStream {
    pub fn new(screen: Box<dyn Overlay>, store: Rc<RefCell<Store>>) -> WithStream {
        WithStream { screen, store, window: None, look: overlay::rose(), face: overlay::text::Face::system() }
    }

    fn streaming(&self) -> bool {
        !self.store.borrow().settings.stream_mode.is_empty()
    }

    /// The marks into 直播画面, scaled as 直播姬 shows a 16:9 capture of the game.
    fn mirror(&mut self, game: Rect, result: &CheckResult, look: Look) {
        let extras = overlay::Extras { checking: None, mine: look == Look::Liked && result.likes.is_empty() };
        let style = overlay::Style { look: &self.look, face: self.face.as_ref(), at: overlay::Moment::default(), ratio: 1.0 };
        // Never the card with the 黑名单 names: viewers see the marks, not who is on the list.
        let Some(frame) = overlay::render_without(&overlay_result(result), extras, ltrb(game), &style, &["hit_card"]) else { return self.hide_mirror() };
        let area = MirrorRect::new(game.x, game.y, game.w, game.h);
        let size = (game.w, game.w * 9 / 16);
        let (scale, _) = fit(area, size, None);
        let (x, y) = to_window((frame.x, frame.y), area, size, None);
        let (width, height) = (frame.pixmap.width(), frame.pixmap.height());
        let picture = slint::Image::from_rgba8(slint::SharedPixelBuffer::clone_from_slice(&straight(frame.pixmap.data()), width, height));
        let mark = MirrorMark {
            picture,
            x: x as f32,
            y: y as f32,
            width: (f64::from(width) * scale) as f32,
            height: (f64::from(height) * scale) as f32,
        };
        if self.window.is_none() {
            self.window = StreamMirrorWindow::new().ok();
        }
        let Some(window) = self.window.as_ref() else { return };
        window.set_marks(ModelRc::new(VecModel::from(vec![mark])));
        let spot = place(area, Spot::to_try(false)[0], &[area]);
        window.window().set_position(slint::PhysicalPosition::new(spot.x, spot.y));
        window.window().set_size(slint::PhysicalSize::new(size.0 as u32, size.1 as u32));
        let _ = window.show();
    }

    fn hide_mirror(&mut self) {
        if let Some(window) = self.window.as_ref() {
            if window.get_marks().row_count() > 0 {
                window.set_marks(ModelRc::default());
            }
        }
    }
}

/// tiny-skia's premultiplied RGBA as straight RGBA (Slint's images are straight).
pub fn straight(premultiplied: &[u8]) -> Vec<u8> {
    let mut out = premultiplied.to_vec();
    for pixel in out.as_chunks_mut::<4>().0 {
        let alpha = u32::from(pixel[3]);
        if alpha > 0 && alpha < 255 {
            for channel in &mut pixel[..3] {
                *channel = ((u32::from(*channel) * 255 + alpha / 2) / alpha).min(255) as u8;
            }
        }
    }
    out
}

impl Overlay for WithStream {
    fn dress(&mut self, scene: &str) {
        self.look = look_of(scene);
        self.screen.dress(scene);
    }
    fn tick(&mut self) {
        self.screen.tick();
    }
    fn checking(&mut self, button: Rect) {
        self.screen.checking(button);
    }
    fn follow(&mut self) {
        self.screen.follow();
    }
    fn show(&mut self, game_rect: Rect, result: &CheckResult, look: Look, target: Target) {
        if target == Target::Screen {
            self.screen.show(game_rect, result, look, target);
        }
        if self.streaming() {
            self.mirror(result.game_box.unwrap_or(game_rect), result, look);
        }
    }
    fn hide(&mut self) {
        self.screen.hide();
        self.hide_mirror();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn premultiplied_pixels_become_straight() {
        assert_eq!(straight(&[100, 50, 0, 128, 0, 0, 0, 0, 10, 20, 30, 255]), vec![199, 100, 0, 128, 0, 0, 0, 0, 10, 20, 30, 255]);
    }
}
