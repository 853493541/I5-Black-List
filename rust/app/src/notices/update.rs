//! 正在更新 (ui_update.UpdateDialog) and 发现新版本 (the card under 有更新 in the header), as plain
//! state: what each shows, and what the app must do when a button is pressed or the download reports.
//!
//! The new version comes first: no ×, no Esc and no click outside close the dialog. If the download
//! fails, 重试 tries again and 跳过 goes on with this version. A release that needs the full package
//! says so, with 前往下载 and 跳过. A copy run from source cannot update: 知道了, and × closes it.

use data::update::Release;

/// How long 更新完成，正在重启… shows before the app closes.
pub const RESTART_MS: u64 = 900;
/// The dialog's card is at least this wide.
pub const MIN_WIDTH: i32 = 460;
/// The 发现新版本 card's width, and how many lines of notes it shows.
pub const OFFER_WIDTH: i32 = 300;
pub const OFFER_LINES: usize = 3;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum State {
    Idle,
    Source,
    Full,
    Downloading,
    Restarting,
    Failed,
}

/// What the app does after a button or a report. The app-wiring package carries these out.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Effect {
    None,
    /// Download the release into `<data>/updates` and stage it (data::update::fetch::download, stage).
    StartDownload,
    /// Open the releases page in the browser (前往下载).
    OpenUrl(String),
    /// Close the dialog: 跳过, 知道了 or × (only from source). The app goes on with this version.
    Close,
    /// Close the app after this many ms and start the launcher into the update.
    RestartAfter(u64),
    /// A click outside that does not close it: the card gives a small shake.
    Nudge,
}

/// The update dialog's words and what is in view.
#[derive(Clone, Debug, PartialEq)]
pub struct UpdateDialog {
    pub state: State,
    pub title: String,
    pub summary: String,
    /// The update notes as written in build/notes/<version>.txt, one `· line` each.
    pub notes: Vec<String>,
    pub status: String,
    /// The progress bar, 0 to 1000, when it is in view.
    pub bar: Option<u32>,
    pub close_visible: bool,
    /// The footer band with 跳过 and the action.
    pub band_visible: bool,
    pub skip_visible: bool,
    pub action: String,
    version: String,
}

/// `· line` for each line of notes.
pub fn note_lines(notes: &[String]) -> Vec<String> {
    notes.iter().map(|line| format!("· {line}")).collect()
}

/// Python's round(): halves go to the even neighbour.
fn py_round(value: f64) -> i64 {
    value.round_ties_even() as i64
}

impl UpdateDialog {
    /// `current` is this app's version; `from_source` is a copy with no launcher to restart into.
    pub fn new(release: &Release, current: &str, from_source: bool) -> UpdateDialog {
        let needs_full = release.needs_full(current);
        let full = needs_full || from_source;
        let size = (release.size as f64 / 1e6).max(0.1);
        let mut dialog = UpdateDialog {
            state: State::Idle,
            title: if full { format!("发现新版本 {}", release.version) } else { format!("正在更新到 {}", release.version) },
            summary: if full { format!("当前版本 {current}") } else { format!("当前版本 {current} · {size:.1} MB") },
            notes: note_lines(&release.notes),
            status: String::new(),
            bar: None,
            close_visible: false,
            band_visible: true,
            skip_visible: true,
            action: "重试".into(),
            version: release.version.clone(),
        };
        if from_source {
            dialog.close_visible = true;
            dialog.state = State::Source;
            dialog.status = "源码运行时不能更新".into();
            dialog.skip_visible = false;
            dialog.action = "知道了".into();
        } else if needs_full {
            dialog.state = State::Full;
            dialog.status = "这次要下载完整安装包，名单和设置不会丢".into();
            dialog.action = "前往下载".into();
        } else {
            dialog.band_visible = false;
        }
        dialog
    }

    pub fn version(&self) -> &str {
        &self.version
    }

    /// Download now. `staged` is the version already in update.new: then restart at once.
    pub fn start(&mut self, staged: Option<&str>) -> Effect {
        if matches!(self.state, State::Source | State::Full | State::Downloading | State::Restarting) {
            return Effect::None;
        }
        if staged == Some(self.version.as_str()) {
            return self.done();
        }
        self.state = State::Downloading;
        self.close_visible = false;
        self.band_visible = false;
        self.bar = Some(0);
        self.status = "下载中 0%".into();
        Effect::StartDownload
    }

    pub fn busy(&self) -> bool {
        matches!(self.state, State::Downloading | State::Restarting)
    }

    pub fn progress(&mut self, got: u64, total: u64) {
        let share = got as f64 / total.max(1) as f64;
        self.bar = Some(py_round(1000.0 * share) as u32);
        self.status = format!("下载中 {}%", py_round(100.0 * share));
    }

    pub fn done(&mut self) -> Effect {
        self.state = State::Restarting;
        self.close_visible = false;
        self.band_visible = false;
        self.bar = Some(1000);
        self.status = "更新完成，正在重启…".into();
        Effect::RestartAfter(RESTART_MS)
    }

    pub fn failed(&mut self, message: &str) {
        self.state = State::Failed;
        self.bar = None;
        self.status = message.into();
        self.band_visible = true;
        self.action = "重试".into();
    }

    /// × or Esc: only a copy from source closes.
    pub fn reject(&mut self) -> Effect {
        if self.state == State::Source {
            Effect::Close
        } else {
            Effect::None
        }
    }

    pub fn skip(&mut self) -> Effect {
        if matches!(self.state, State::Failed | State::Full) {
            Effect::Close
        } else {
            Effect::None
        }
    }

    pub fn click_outside(&mut self) -> Effect {
        if self.state == State::Source {
            Effect::Close
        } else {
            Effect::Nudge
        }
    }

    /// The main button: 前往下载, 重试 or 知道了.
    pub fn act(&mut self, staged: Option<&str>) -> Effect {
        match self.state {
            State::Full => Effect::OpenUrl(data::update::RELEASES_URL.into()),
            State::Failed => self.start(staged),
            _ => Effect::Close,
        }
    }
}

/// 发现新版本: the card that opens under 有更新 in the header the first time a version is found.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct UpdateOffer {
    pub title: String,
    /// At most three lines of notes, `· line` each.
    pub notes: Vec<String>,
    pub later: &'static str,
    pub now: &'static str,
}

impl UpdateOffer {
    pub fn new(release: &Release) -> UpdateOffer {
        let shown = &release.notes[..release.notes.len().min(OFFER_LINES)];
        UpdateOffer { title: format!("发现新版本 {}", release.version), notes: note_lines(shown), later: "稍后", now: "立即更新" }
    }
}

/// The update notes in build/notes/<version>.txt as build/release.py reads them: each line trimmed,
/// a leading `-`, `·`, `•`, `*` or space dropped, blank lines left out.
pub fn read_notes(text: &str) -> Vec<String> {
    text.lines()
        .map(|line| line.trim().trim_start_matches(['-', '·', '•', '*', ' ']).trim())
        .filter(|line| !line.is_empty())
        .map(String::from)
        .collect()
}
