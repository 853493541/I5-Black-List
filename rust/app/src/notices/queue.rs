//! The corner messages over time (ui_notice.CornerNotice): two cards at most, the result and 嘉宾
//! above it. The second rises in 110 ms after the first; both go after 8 s (检查中 after 20 s) or on
//! a click; the pointer over either holds them; a line along each foot runs down until they go.
//!
//! The view asks `tick(now)` every 40 ms while `visible()`, and draws what `cards()` says.

use super::corner::{card_width, places, rise_at, rise_start, Area, Kind, Message, CHECKING_MS, NEXT_MS, NOTICE_MS, RISE_MS, SPIN_STEP, TICK_MS};

/// How big a card is: the view measures its words.
pub trait Measure {
    /// The card's own width, before the 300 to 440 clamp.
    fn natural_width(&self, message: &Message) -> i32;
    /// Its height at that width.
    fn height(&self, message: &Message, width: i32) -> i32;
}

/// One card as the view draws it now.
#[derive(Clone, Debug, PartialEq)]
pub struct Card {
    pub message: Message,
    pub width: i32,
    pub height: i32,
    /// Its place when it has risen.
    pub spot: (i32, i32),
    /// Where it is now.
    pub pos: (i32, i32),
    pub visible: bool,
    /// How much of the line along the foot is left, 1 to 0; None while there is no line (检查中).
    pub left: Option<f32>,
    /// The 检查中 ring's turn, in radians.
    pub spin: f32,
    rise: Option<((i32, i32), u64)>,
}

#[derive(Debug, Default)]
pub struct CornerNotice {
    pub kind: Option<Kind>,
    cards: Vec<Card>,
    total: u64,
    left_ms: u64,
    clock: u64,
    paused: bool,
    /// The second card and when it comes in.
    waiting: Option<(usize, u64)>,
    last_tick: u64,
}

impl CornerNotice {
    pub fn new() -> CornerNotice {
        CornerNotice::default()
    }

    pub fn cards(&self) -> &[Card] {
        &self.cards
    }

    pub fn visible(&self) -> bool {
        self.cards.first().is_some_and(|card| card.visible)
    }

    /// Show these messages, the bottom one first, for `ms`. A card already up (检查中) takes the new
    /// message where it is, without rising again.
    pub fn show_messages(&mut self, now: u64, kind: Kind, messages: Vec<Message>, area: Option<Area>, measure: &dyn Measure, ms: u64) {
        self.kind = Some(kind);
        self.waiting = None;
        let width = card_width(&messages.iter().map(|m| measure.natural_width(m)).collect::<Vec<_>>());
        let heights: Vec<i32> = messages.iter().map(|m| measure.height(m, width)).collect();
        let spots = places(area, width, &heights);
        let mut cards = Vec::with_capacity(messages.len());
        for (order, message) in messages.into_iter().enumerate() {
            let was_up = self.cards.get(order).is_some_and(|card| card.visible);
            let left = if message.kind == Kind::Checking { None } else { Some(1.0) };
            let spin = self.cards.get(order).map_or(0.0, |card| card.spin);
            let spot = spots[order];
            let mut card = Card { message, width, height: heights[order], spot, pos: spot, visible: was_up, left, spin, rise: None };
            if !was_up {
                if order == 0 {
                    enter(&mut card, now, order);
                } else {
                    self.waiting = Some((order, now + NEXT_MS));
                }
            }
            cards.push(card);
        }
        self.cards = cards;
        self.total = ms;
        self.left_ms = ms;
        self.resume(now);
        self.last_tick = now;
    }

    pub fn show_checking(&mut self, now: u64, area: Option<Area>, measure: &dyn Measure) {
        self.show_messages(now, Kind::Checking, vec![Message::checking()], area, measure, CHECKING_MS);
    }

    pub fn show_result(&mut self, now: u64, hits: &[(String, Vec<String>)], likes: &[String], unclear: usize, area: Option<Area>, measure: &dyn Measure) {
        let messages = super::corner::result_messages(hits, likes, unclear);
        let kind = super::corner::result_kind(hits.len(), likes.len());
        self.show_messages(now, kind, messages, area, measure, NOTICE_MS);
    }

    pub fn show_missing(&mut self, now: u64, area: Option<Area>, measure: &dyn Measure) {
        self.show_messages(now, Kind::Missing, vec![Message::missing()], area, measure, NOTICE_MS);
    }

    /// 检查失败, and what went wrong under it.
    pub fn show_error(&mut self, now: u64, detail: &str, area: Option<Area>, measure: &dyn Measure) {
        self.show_messages(now, Kind::Error, vec![Message::error(detail)], area, measure, NOTICE_MS);
    }

    /// How long until they go, in ms.
    pub fn remaining(&self, now: u64) -> u64 {
        if self.paused {
            self.left_ms
        } else {
            self.left_ms.saturating_sub(now.saturating_sub(self.clock))
        }
    }

    pub fn paused(&self) -> bool {
        self.paused
    }

    fn resume(&mut self, now: u64) {
        self.paused = false;
        self.clock = now;
    }

    /// The pointer over a message holds them both until it leaves.
    pub fn hover(&mut self, now: u64, inside: bool) {
        if !self.visible() {
            return;
        }
        if inside && !self.paused {
            self.left_ms = self.remaining(now);
            self.paused = true;
        } else if !inside && self.paused {
            self.resume(now);
        }
    }

    /// A click on either card: both go.
    pub fn click(&mut self) {
        self.hide();
    }

    pub fn hide(&mut self) {
        self.waiting = None;
        self.paused = false;
        for card in &mut self.cards {
            card.visible = false;
            card.rise = None;
        }
    }

    /// Move time on: the time-out, the second card, the rises, the foot line and the ring.
    pub fn tick(&mut self, now: u64) {
        if !self.visible() {
            return;
        }
        // The time-out: QTimer starts at max(1, ms), so a time of 0 still shows for a moment.
        if !self.paused && now.saturating_sub(self.clock) >= self.left_ms.max(1) {
            self.hide();
            return;
        }
        if let Some((order, at)) = self.waiting {
            if now >= at {
                self.waiting = None;
                enter(&mut self.cards[order], at, order);
            }
        }
        let ticks = (now.saturating_sub(self.last_tick) / TICK_MS) as f32;
        if ticks > 0.0 {
            self.last_tick += ticks as u64 * TICK_MS;
        }
        let left = self.remaining(now) as f32 / self.total.max(1) as f32;
        for card in self.cards.iter_mut().filter(|card| card.visible) {
            if card.left.is_some() {
                card.left = Some(left);
            }
            if card.message.kind.look().mark == "spin" {
                card.spin += SPIN_STEP * ticks;
            }
            if let Some((start, since)) = card.rise {
                card.pos = rise_at(start, card.spot, now.saturating_sub(since));
                if now.saturating_sub(since) >= RISE_MS {
                    card.rise = None;
                }
            }
        }
    }
}

fn enter(card: &mut Card, now: u64, order: usize) {
    let start = rise_start(card.spot, order);
    card.pos = start;
    card.visible = true;
    card.rise = Some((start, now));
}
