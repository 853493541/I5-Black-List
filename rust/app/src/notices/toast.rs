//! The toast (ui_kit.Toast): a short message at the bottom of a window, with an optional action such
//! as 撤销. It never takes the focus, fades in over 150 ms, and goes on its own after 4 s unless told
//! otherwise; the action keeps working while it fades out, and is dropped once it is gone.

/// How long a toast stays, unless told otherwise.
pub const TOAST_MS: u64 = 4_000;
/// Its fade in and out.
pub const FADE_MS: u64 = 150;
/// From the window's bottom edge, and the narrowest it gets.
pub const BOTTOM: i32 = 40;
pub const MIN_WIDTH: i32 = 200;
pub const SIDES: i32 = 48;

#[derive(Clone, Copy, Debug, PartialEq)]
enum Phase {
    Hidden,
    In(u64),
    Up,
    Out(u64, f32),
}

#[derive(Clone, Debug, PartialEq)]
pub struct Toast {
    pub text: String,
    /// The action's words; empty for none.
    pub action: String,
    phase: Phase,
    until: u64,
    /// Whether the action still does something (the app keeps the callback by this toast's id).
    armed: bool,
    /// Which message this is: the app's callback for the action is kept against it.
    pub id: u64,
}

impl Default for Toast {
    fn default() -> Self {
        Toast { text: String::new(), action: String::new(), phase: Phase::Hidden, until: 0, armed: false, id: 0 }
    }
}

impl Toast {
    pub fn new() -> Toast {
        Toast::default()
    }

    /// Show `text`, with `action` (or "" for none), for `ms`. Returns the new message's id.
    pub fn show_message(&mut self, now: u64, text: &str, action: &str, ms: u64) -> u64 {
        self.text = text.into();
        self.action = action.into();
        self.armed = !action.is_empty();
        self.phase = Phase::In(now);
        self.until = now + ms;
        self.id += 1;
        self.id
    }

    pub fn visible(&self) -> bool {
        self.phase != Phase::Hidden
    }

    /// Whether the action button is in view.
    pub fn has_action(&self) -> bool {
        !self.action.is_empty()
    }

    pub fn opacity(&self, now: u64) -> f32 {
        let share = |since: u64| (now.saturating_sub(since) as f32 / FADE_MS as f32).min(1.0);
        match self.phase {
            Phase::Hidden => 0.0,
            Phase::In(since) => share(since),
            Phase::Up => 1.0,
            Phase::Out(since, from) => from * (1.0 - share(since)),
        }
    }

    /// Start to go: it fades out, the action still working until it is gone.
    pub fn dismiss(&mut self, now: u64) {
        if !self.visible() {
            return;
        }
        let from = self.opacity(now);
        self.phase = Phase::Out(now, from);
    }

    /// The list changed under the message: its action would undo too much, so it goes at once.
    pub fn drop_action(&mut self, now: u64) {
        self.armed = false;
        self.dismiss(now);
    }

    /// The action was clicked: the toast goes at once. True when the app should run the action.
    pub fn act(&mut self) -> bool {
        let run = self.armed;
        self.armed = false;
        self.phase = Phase::Hidden;
        run
    }

    /// Move time on: the fade in ends, the time runs out, the fade out ends.
    pub fn tick(&mut self, now: u64) {
        match self.phase {
            Phase::In(since) if now >= since + FADE_MS => self.phase = Phase::Up,
            Phase::Out(since, _) if now >= since + FADE_MS => {
                self.phase = Phase::Hidden;
                self.armed = false;
                return;
            }
            _ => {}
        }
        if matches!(self.phase, Phase::In(_) | Phase::Up) && now >= self.until {
            self.dismiss(now);
        }
    }
}

/// Where the toast sits in a window of `host` size, given its own natural size: centred, 40 px
/// clear of the bottom edge, never wider than the window less 48 px (but at least 200).
pub fn place(host: (i32, i32), natural: (i32, i32)) -> (i32, i32, i32, i32) {
    let width = natural.0.min(MIN_WIDTH.max(host.0 - SIDES));
    ((host.0 - width).div_euclid(2), host.1 - natural.1 - BOTTOM, width, natural.1)
}
