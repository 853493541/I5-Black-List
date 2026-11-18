//! 基础模式's result: the messages at the bottom right of the screen (blacklist_detect/ui_notice.py).
//!
//! Plain logic, no drawing: which cards a result makes, their words, where they stand, when they
//! rise in, when the second one follows, how long they stay, and the pause while the pointer is over
//! them. Time is passed in as milliseconds, so the timings are tested without a clock.

/// How long a result stays up.
pub const NOTICE_MS: u64 = 8_000;
/// 检查中 waits for the result, but never forever.
pub const CHECKING_MS: u64 = 20_000;
/// Names listed before the rest are counted.
pub const MAX_LINES: usize = 5;
/// From the corner of the screen, and between two messages.
pub const MARGIN: i32 = 20;
pub const GAP: i32 = 10;
pub const WIDTH: (i32, i32) = (300, 440);
/// A message rises this far as it comes in; the second one comes a moment after the first.
pub const RISE: i32 = 14;
pub const RISE_MS: u64 = 240;
pub const NEXT_MS: u64 = 110;
pub const TICK_MS: u64 = 40;
pub const BADGE: i32 = 30;
/// How far the 检查中 ring turns each tick.
pub const SPIN_STEP: f32 = 0.32;

/// What kind of news a card brings; it picks the card's colors and its badge.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Hit,
    Liked,
    Clear,
    Checking,
    Missing,
    Error,
}

/// A card's colors, as `#rrggbb`. The messages sit over the game, so they keep these in 浅色 and 深色.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Look {
    pub top: &'static str,
    pub bottom: &'static str,
    pub edge: &'static str,
    /// The title and the names.
    pub ink: &'static str,
    /// The lines under them.
    pub soft: &'static str,
    /// The badge's ring, the rule under the title, the line along the foot.
    pub accent: &'static str,
    pub badge: (&'static str, &'static str),
    /// What the badge shows: warning, heart, check, search, or spin.
    pub mark: &'static str,
    pub mark_ink: &'static str,
}

impl Kind {
    pub fn name(self) -> &'static str {
        match self {
            Kind::Hit => "hit",
            Kind::Liked => "liked",
            Kind::Clear => "clear",
            Kind::Checking => "checking",
            Kind::Missing => "missing",
            Kind::Error => "error",
        }
    }

    /// The kind a name stands for; an unknown one looks like `missing`, as `_LOOKS.get` falls back.
    pub fn from_name(name: &str) -> Kind {
        [Kind::Hit, Kind::Liked, Kind::Clear, Kind::Checking, Kind::Missing, Kind::Error]
            .into_iter()
            .find(|kind| kind.name() == name)
            .unwrap_or(Kind::Missing)
    }

    pub fn look(self) -> Look {
        let look = |top, bottom, edge, ink, soft, accent, badge, mark, mark_ink| Look { top, bottom, edge, ink, soft, accent, badge, mark, mark_ink };
        match self {
            Kind::Hit => look("#7a1620", "#4e0c13", "#c9a254", "#fff3e0", "#f1cfae", "#e4c47e", ("#d9434f", "#a8262f"), "warning", "#fff3e0"),
            Kind::Liked => look("#fff4f9", "#fadcec", "#e8a7bd", "#8a2d55", "#b0668a", "#f08ab4", ("#ff9cc4", "#e0558f"), "heart", "#ffffff"),
            Kind::Clear => look("#1e6843", "#123f29", "#c9a254", "#f0fff5", "#bfe3cb", "#e4c47e", ("#45c07d", "#2f9e5e"), "check", "#ffffff"),
            Kind::Checking => look("#302a24", "#1c1915", "#a07c36", "#fff3e0", "#d8c8a6", "#e4c47e", ("#3a3129", "#2a231d"), "spin", "#e4c47e"),
            Kind::Missing => look("#302a24", "#1c1915", "#a07c36", "#fff3e0", "#d8c8a6", "#e4c47e", ("#e4c47e", "#c9a254"), "search", "#2b1d08"),
            Kind::Error => look("#6a4314", "#3f280a", "#c9a254", "#fff3e0", "#f0d5a6", "#e4c47e", ("#e39b3b", "#b56e15"), "warning", "#fff3e0"),
        }
    }
}

/// One person on a card: the name and up to three of their tags.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Person {
    pub name: String,
    pub tags: Vec<String>,
}

/// One card: its look, a title, the line under it, and the people it lists.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Message {
    pub kind: Kind,
    pub title: String,
    pub note: String,
    pub people: Vec<Person>,
    pub more: usize,
}

impl Message {
    pub fn new(kind: Kind, title: &str, note: &str) -> Message {
        Message { kind, title: title.into(), note: note.into(), people: Vec::new(), more: 0 }
    }

    pub fn checking() -> Message {
        Message::new(Kind::Checking, "检查中…", "")
    }

    pub fn missing() -> Message {
        Message::new(Kind::Missing, "没有找到大厅", "进了「推演成功」大厅再按")
    }

    /// 检查失败, with what went wrong under it.
    pub fn error(detail: &str) -> Message {
        Message::new(Kind::Error, "检查失败", detail)
    }

    /// The tags shown beside a person: at most three.
    pub fn shown_tags(person: &Person) -> &[String] {
        &person.tags[..person.tags.len().min(3)]
    }

    /// 还有 N 人, under the names, when some are not listed.
    pub fn more_line(&self) -> String {
        if self.more > 0 {
            format!("还有 {} 人", self.more)
        } else {
            String::new()
        }
    }
}

/// The people a card lists, and how many more there are.
pub fn listed(people: Vec<Person>) -> (Vec<Person>, usize) {
    let total = people.len();
    let shown: Vec<Person> = if total <= MAX_LINES { people } else { people.into_iter().take(MAX_LINES - 1).collect() };
    let more = total - shown.len();
    (shown, more)
}

/// The messages for one checked lobby, the bottom one first: what was found, then 嘉宾.
pub fn result_messages(hits: &[(String, Vec<String>)], likes: &[String], unclear: usize) -> Vec<Message> {
    let missed = if unclear > 0 { format!("{unclear} 人未识别") } else { String::new() };
    let first = if hits.is_empty() {
        Message::new(Kind::Clear, "未发现黑名单", &missed)
    } else {
        let people = hits.iter().map(|(name, tags)| Person { name: name.clone(), tags: tags.clone() }).collect();
        let (people, more) = listed(people);
        Message { kind: Kind::Hit, title: format!("{} 名黑名单", hits.len()), note: missed, people, more }
    };
    if likes.is_empty() {
        return vec![first];
    }
    let (people, more) = listed(likes.iter().map(|name| Person { name: name.clone(), tags: Vec::new() }).collect());
    vec![first, Message { kind: Kind::Liked, title: "嘉宾".into(), note: String::new(), people, more }]
}

/// The kind of the whole result: 黑名单 first, then 嘉宾, then all clear.
pub fn result_kind(hits: usize, likes: usize) -> Kind {
    if hits > 0 {
        Kind::Hit
    } else if likes > 0 {
        Kind::Liked
    } else {
        Kind::Clear
    }
}

/// A screen's area for windows (without the taskbar), in logical pixels.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Area {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

/// The width every card of one result takes: the widest one's own, kept between 300 and 440.
pub fn card_width(natural: &[i32]) -> i32 {
    natural.iter().copied().max().unwrap_or(0).clamp(WIDTH.0, WIDTH.1)
}

/// Where each card stands, the bottom one first, as (x, y): stacked up from the area's bottom right.
pub fn places(area: Option<Area>, width: i32, heights: &[i32]) -> Vec<(i32, i32)> {
    let right = area.map_or(width + MARGIN, |a| a.x + a.width) - MARGIN;
    let mut bottom = area.map_or(400, |a| a.y + a.height) - MARGIN;
    heights
        .iter()
        .map(|height| {
            let spot = (right - width, bottom - height);
            bottom = spot.1 - GAP;
            spot
        })
        .collect()
}

/// Where a card starts its rise: a little below its place; the one above rises less, so it never
/// comes over the one under it.
pub fn rise_start(spot: (i32, i32), order: usize) -> (i32, i32) {
    (spot.0, spot.1 + if order == 0 { RISE } else { GAP - 2 })
}

/// Qt's OutCubic, which the rise follows.
pub fn out_cubic(t: f64) -> f64 {
    let t = t.clamp(0.0, 1.0) - 1.0;
    t * t * t + 1.0
}

/// Where a rising card is, `elapsed` ms after it began to rise (Qt rounds a QPoint's animation).
pub fn rise_at(start: (i32, i32), spot: (i32, i32), elapsed: u64) -> (i32, i32) {
    let share = out_cubic(elapsed as f64 / RISE_MS as f64);
    let step = |from: i32, to: i32| (from as f64 + (to - from) as f64 * share).round() as i32;
    (step(start.0, spot.0), step(start.1, spot.1))
}
