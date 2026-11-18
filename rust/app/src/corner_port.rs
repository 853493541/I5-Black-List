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

    /// The screen's free area, where the cards rise.
    fn area() -> Option<crate::notices::corner::Area> {
        work_area().map(|(x, y, width, height)| crate::notices::corner::Area { x, y, width, height })
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
                    let fresh = !window.window().is_visible();
                    let _ = window.show();
                    if fresh {
                        float(window);
                    }
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
        match kind {
            NoticeKind::Checking => self.queue.show_checking(now, Self::area(), &measure),
            NoticeKind::Missing => self.queue.show_missing(now, Self::area(), &measure),
            NoticeKind::Failed(detail) => self.queue.show_error(now, &detail, Self::area(), &measure),
            NoticeKind::Result { unclear, .. } => {
                let (hits, likes) = std::mem::take(&mut self.people);
                self.queue.show_result(now, &hits, &likes, unclear, Self::area(), &measure);
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

/// Topmost, never taking the focus, out of the taskbar (ui_notice's window flags).
#[cfg(windows)]
fn float(window: &NoticeWindow) {
    use raw_window_handle::{HasWindowHandle, RawWindowHandle};
    if let Ok(handle) = window.window().window_handle().window_handle() {
        if let RawWindowHandle::Win32(handle) = handle.as_raw() {
            win::float::float_window(handle.hwnd.get());
        }
    }
}

#[cfg(not(windows))]
fn float(_window: &NoticeWindow) {}

#[cfg(windows)]
fn work_area() -> Option<(i32, i32, i32, i32)> {
    win::float::work_area()
}

#[cfg(not(windows))]
fn work_area() -> Option<(i32, i32, i32, i32)> {
    None
}
