//! The flow's corner message on the real cards (ui_notice.CornerNotice): the queue in notices::queue, one
//! NoticeWindow per card, measured by a hidden card of its own.

use crate::notices::corner::Message;
use crate::notices::queue::{CornerNotice, Measure};
use crate::notices::view::fill_notice;
use crate::NoticeWindow;
use app::wiring::stubs::{CheckResult, Notice, NoticeKind, SeatMark};
use slint::ComponentHandle;
use std::time::Instant;

/// A hidden card that says how big a message makes it.
struct Measurer(NoticeWindow);

impl Measure for Measurer {
    fn natural_width(&self, message: &Message) -> i32 {
        fill_notice(&self.0, message, None, 0.0);
        self.0.get_natural_width().round() as i32
    }
    fn height(&self, message: &Message, width: i32) -> i32 {
        fill_notice(&self.0, message, None, 0.0);
        self.0.set_card_width(width as f32);
        self.0.get_natural_height().round() as i32
    }
}

pub struct CornerPort {
    queue: CornerNotice,
    windows: Vec<NoticeWindow>,
    measurer: Option<Measurer>,
    started: Instant,
    /// The 黑名单 players (name, tags) and 嘉宾 of the result about to be shown.
    people: (Vec<(String, Vec<String>)>, Vec<String>),
}

impl CornerPort {
    pub fn new() -> CornerPort {
        CornerPort { queue: CornerNotice::new(), windows: Vec::new(), measurer: None, started: Instant::now(), people: Default::default() }
    }

    fn now(&self) -> u64 {
        self.started.elapsed().as_millis() as u64
    }

    fn draw(&mut self) {
        let cards = self.queue.cards().to_vec();
        while self.windows.len() < cards.len() {
            match NoticeWindow::new() {
                Ok(window) => self.windows.push(window),
                Err(_) => return,
            }
        }
        for (index, window) in self.windows.iter().enumerate() {
            match cards.get(index).filter(|card| card.visible) {
                Some(card) => {
                    fill_notice(window, &card.message, card.left, card.spin);
                    window.set_card_width(card.width as f32);
                    window.window().set_position(slint::LogicalPosition::new(card.pos.0 as f32, card.pos.1 as f32));
                    let _ = window.show();
                }
                None => {
                    let _ = window.hide();
                }
            }
        }
    }
}

impl Notice for CornerPort {
    fn people(&mut self, result: &CheckResult, likes: &[String]) {
        let hits = result.seats.iter().filter_map(|SeatMark { name, kind, .. }| match kind {
            app::wiring::stubs::MarkKind::Blacklist { tags } => Some((name.clone(), tags.clone())),
            _ => None,
        });
        self.people = (hits.collect(), likes.to_vec());
    }

    fn show(&mut self, kind: NoticeKind) {
        if self.measurer.is_none() {
            self.measurer = NoticeWindow::new().ok().map(Measurer);
        }
        let Some(measure) = self.measurer.take() else { return };
        let now = self.now();
        // The screen's work area is the cards' own default until the win crate gives it (None: the primary's).
        match kind {
            NoticeKind::Checking => self.queue.show_checking(now, None, &measure),
            NoticeKind::Missing => self.queue.show_missing(now, None, &measure),
            NoticeKind::Failed(detail) => self.queue.show_error(now, &detail, None, &measure),
            NoticeKind::Result { unclear, .. } => {
                let (hits, likes) = std::mem::take(&mut self.people);
                self.queue.show_result(now, &hits, &likes, unclear, None, &measure);
            }
        }
        self.measurer = Some(measure);
        self.draw();
    }

    fn hide(&mut self) {
        self.queue.hide();
        self.draw();
    }

    fn tick(&mut self) {
        if self.queue.visible() || self.windows.iter().any(|window| window.window().is_visible()) {
            let now = self.now();
            self.queue.tick(now);
            self.draw();
        }
    }
}
