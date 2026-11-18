//! 环境测试's card (blacklist_detect/ui_setup.py `SetupCheck`): five steps, a bar that eases toward the step running,
//! 准备好了 when all pass, 环境测试没通过 with which step and why when one fails.

/// The steps, in order (ui_setup.STEPS).
pub const STEPS: [&str; 5] = ["屏幕截图", "识别功能", "识别测试", "自动检查", "手动检查"];
pub const RUNNING: &str = "正在测试环境";
pub const OK: &str = "准备好了";
pub const FAILED: &str = "环境测试没通过";
pub const CLOSE: &str = "关闭";
pub const RETRY: &str = "重试";
/// How long 准备好了 shows before the card fades (ms), and how long the fade takes.
pub const FADE_AFTER_MS: u64 = 1300;
pub const FADE_MS: u64 = 220;
/// The bar moves every 30 ms.
pub const TICK_MS: u64 = 30;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Step {
    Wait,
    Run,
    Ok,
    Fail,
}

impl Step {
    pub fn name(self) -> &'static str {
        match self {
            Step::Wait => "wait",
            Step::Run => "run",
            Step::Ok => "ok",
            Step::Fail => "fail",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum State {
    Idle,
    Running,
    Ok,
    Failed,
}

#[derive(Clone, Debug)]
pub struct SetupModel {
    pub state: State,
    pub steps: Vec<(Step, String)>,
    pub message: String,
    /// The bar as drawn, 0..=1, and where it eases to.
    pub value: f64,
    pub target: f64,
}

impl Default for SetupModel {
    fn default() -> Self {
        SetupModel { state: State::Idle, steps: vec![(Step::Wait, String::new()); STEPS.len()], message: String::new(), value: 0.0, target: 0.0 }
    }
}

impl SetupModel {
    pub fn heading(&self) -> &'static str {
        match self.state {
            State::Ok => OK,
            State::Failed => FAILED,
            _ => RUNNING,
        }
    }

    pub fn start(&mut self) {
        *self = SetupModel { state: State::Running, ..SetupModel::default() };
    }

    /// A step's state and its note ("12/12", "10.5 秒"); while a step runs the bar eases toward its end.
    pub fn step(&mut self, index: usize, step: Step, note: &str) {
        let Some(slot) = self.steps.get_mut(index) else { return };
        *slot = (step, note.to_string());
        let count = STEPS.len() as f64;
        match step {
            Step::Ok => self.target = self.target.max((index as f64 + 1.0) / count),
            Step::Run => self.target = self.target.max((index as f64 + 0.9) / count),
            _ => {}
        }
    }

    /// All passed: a full green bar; the app fades the card after [`FADE_AFTER_MS`] unless a report follows.
    pub fn succeed(&mut self) {
        self.state = State::Ok;
        self.target = 1.0;
    }

    pub fn fail(&mut self, index: usize, message: &str) {
        self.state = State::Failed;
        self.step(index, Step::Fail, "");
        self.message = message.to_string();
    }

    /// One tick: ease toward the target; a long step keeps creeping, never jumps back. False once it can stop.
    pub fn advance(&mut self) -> bool {
        let gap = self.target - self.value;
        let going = if gap > 0.0005 {
            self.value += (gap * 0.12).max(0.0015);
            true
        } else {
            !matches!(self.state, State::Ok | State::Failed)
        };
        self.value = self.value.min(self.target);
        going
    }

    /// The bar as Python's QProgressBar holds it, 0..=1000.
    pub fn bar(&self) -> i64 {
        (self.value * 1000.0).round() as i64
    }

    pub fn dismiss(&mut self) {
        self.state = State::Idle;
    }
}
