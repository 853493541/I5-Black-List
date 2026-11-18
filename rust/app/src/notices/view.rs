//! Filling the Slint windows of ui/notices from the Rust state.

use std::rc::Rc;

use slint::{Color, ModelRc, SharedString, VecModel};

use super::corner::{Kind, Message};
use super::update::{UpdateDialog, UpdateOffer};
use crate::{NoticeLook, NoticePerson, NoticeWindow, ToastWindow, UpdateDialogWindow, UpdateOfferWindow};

/// `#rrggbb` as a Slint color.
pub fn color(hex: &str) -> Color {
    let value = u32::from_str_radix(hex.trim_start_matches('#'), 16).unwrap_or(0);
    Color::from_rgb_u8((value >> 16) as u8, (value >> 8) as u8, value as u8)
}

pub fn look(kind: Kind) -> NoticeLook {
    let look = kind.look();
    NoticeLook {
        top: color(look.top),
        bottom: color(look.bottom),
        edge: color(look.edge),
        ink: color(look.ink),
        soft: color(look.soft),
        accent: color(look.accent),
        badge_top: color(look.badge.0),
        badge_bottom: color(look.badge.1),
        mark: look.mark.into(),
        mark_ink: color(look.mark_ink),
    }
}

fn strings(lines: &[String]) -> ModelRc<SharedString> {
    ModelRc::from(Rc::new(VecModel::from(lines.iter().map(SharedString::from).collect::<Vec<_>>())))
}

/// Put one card's message on a notice window. `left` is the foot line (None for none).
pub fn fill_notice(window: &NoticeWindow, message: &Message, left: Option<f32>, spin: f32) {
    window.set_look(look(message.kind));
    window.set_kind(message.kind.name().into());
    window.set_title_text(message.title.as_str().into());
    window.set_note(message.note.as_str().into());
    let people: Vec<NoticePerson> = message
        .people
        .iter()
        .map(|person| NoticePerson { name: person.name.as_str().into(), tags: strings(Message::shown_tags(person)) })
        .collect();
    window.set_people(ModelRc::from(Rc::new(VecModel::from(people))));
    window.set_more(message.more_line().into());
    window.set_left(left.unwrap_or(-1.0));
    window.set_spin(spin);
}

pub fn fill_toast(window: &ToastWindow, text: &str, action: &str, dark: bool) {
    window.set_text(text.into());
    window.set_action(action.into());
    window.set_dark(dark);
}

pub fn fill_update(window: &UpdateDialogWindow, dialog: &UpdateDialog, dark: bool) {
    window.set_dark(dark);
    window.set_title_text(dialog.title.as_str().into());
    window.set_summary(dialog.summary.as_str().into());
    window.set_notes(strings(&dialog.notes));
    window.set_status(dialog.status.as_str().into());
    window.set_bar(dialog.bar.map_or(-1, |bar| bar as i32));
    window.set_close_visible(dialog.close_visible);
    window.set_band_visible(dialog.band_visible);
    window.set_skip_visible(dialog.skip_visible);
    window.set_action(dialog.action.as_str().into());
}

pub fn fill_offer(window: &UpdateOfferWindow, offer: &UpdateOffer, dark: bool) {
    window.set_dark(dark);
    window.set_title_text(offer.title.as_str().into());
    window.set_notes(strings(&offer.notes));
}
