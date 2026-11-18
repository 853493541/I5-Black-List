//! The command line, as blacklist_detect/__main__.py reads it, for the app-wiring package to call from main.
//!
//! Start-up order (what runs before the window), as in Python:
//! 1. OMP_NUM_THREADS: the value the copy was started with is kept (paths.inherited_threads, for the log)
//!    and the copy sets its own, one per physical core, 2 to 8. Programs the app starts get
//!    `common::paths::child_env`, which leaves it out (an inherited 1 left the next copy's OCR on one core).
//! 2. Console windows of child programs are kept hidden (ocr_engine.silence_console_children; on Windows the
//!    Rust app starts children with CREATE_NO_WINDOW instead).
//! 3. [`parse`] the arguments (everything after the program's own path):
//!    - `check <image>`: read one image without opening the window; prints [`Check`]'s lines; exit 0 when the
//!      lobby's header was found, 1 when not or when reading failed (the error goes to stderr).
//!    - `download-models`: make sure the OCR models are here; prints [`DOWNLOAD_OK`], exit 0, else the error
//!      on stderr and exit 1. Any words after it are ignored.
//!    - anything else, words the app does not know included: the window, in the tray only when
//!      [`BACKGROUND`] is among them (autostart passes it). `check` with no image or more than one prints
//!      [`usage`] on stderr and exits 2; that is the only way the arguments are refused.
//! 4. The window's own start (single instance, logs, store, tray, hotkeys) is the app's, then on close the
//!    process ends at once with the window's exit code (single.exit_now).

/// The flag autostart puts on the command it registers (autostart.BACKGROUND): start in the tray.
pub const BACKGROUND: &str = "--background";
/// Exit code for arguments refused.
pub const USAGE_CODE: i32 = 2;
/// What `download-models` prints when the models are ready.
pub const DOWNLOAD_OK: &str = "PaddleOCR 中文模型已在本机可用。";

/// What the arguments ask for.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Command {
    /// The window; `background` starts it in the tray, without showing it.
    Window { background: bool },
    /// Read this image and print what it says.
    Check { image: String },
    /// Fetch or check the OCR models.
    DownloadModels,
}

/// Arguments refused: print [`usage`] on stderr and exit with [`USAGE_CODE`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct UsageError;

/// The usage line for `check`; `program` is how the user started the app ("python -m blacklist_detect" in Python).
pub fn usage(program: &str) -> String {
    format!("用法: {program} check <图片.png>")
}

/// The arguments after the program's own path, as __main__.main reads them: case matters, and only the first
/// word picks `check` or `download-models`.
pub fn parse<S: AsRef<str>>(args: &[S]) -> Result<Command, UsageError> {
    let args: Vec<&str> = args.iter().map(AsRef::as_ref).collect();
    match args.first().copied() {
        Some("check") if args.len() == 2 => Ok(Command::Check { image: args[1].to_string() }),
        Some("check") => Err(UsageError),
        Some("download-models") => Ok(Command::DownloadModels),
        _ => Ok(Command::Window { background: args.contains(&BACKGROUND) }),
    }
}

/// How one seat was read, for `check`'s lines.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SeatState {
    Unclear,
    Truncated,
    Whole,
}

impl SeatState {
    /// Unclear wins over truncated, as in _check_cli.
    pub fn of(unclear: bool, truncated: bool) -> SeatState {
        if unclear {
            SeatState::Unclear
        } else if truncated {
            SeatState::Truncated
        } else {
            SeatState::Whole
        }
    }

    pub fn words(self) -> &'static str {
        match self {
            SeatState::Unclear => "未识别",
            SeatState::Truncated => "截断",
            SeatState::Whole => "完整",
        }
    }
}

/// What `check` prints, from the check's result: its message, one line per seat, one per hit.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Check {
    pub message: String,
    /// (seat index from 0, state, confidence, the name as read).
    pub seats: Vec<(usize, SeatState, f64, String)>,
    pub hits: Vec<String>,
    pub header_found: bool,
}

impl Check {
    /// The lines `check` prints to stdout, in order.
    pub fn lines(&self) -> Vec<String> {
        let mut out = vec![self.message.clone()];
        out.extend(self.seats.iter().map(|(index, state, confidence, raw)| seat_line(*index, *state, *confidence, raw)));
        out.extend(self.hits.iter().cloned());
        out
    }

    pub fn exit_code(&self) -> i32 {
        if self.header_found {
            0
        } else {
            1
        }
    }
}

/// " 1  完整    0.99  示例坏人": seat number right-aligned in 2, the state padded to 4 characters.
pub fn seat_line(index: usize, state: SeatState, confidence: f64, raw: &str) -> String {
    format!("{:>2}  {:<4}  {confidence:.2}  {raw}", index + 1, state.words())
}
