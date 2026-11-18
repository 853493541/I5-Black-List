//! FlowTest: 环境测试's timings and its report (diagnostics.FlowTest), word for word.

/// What the bundled sample lobby says, seat by seat: made-up names, read right on a working PC.
pub const SAMPLE_NAMES: [&str; 12] =
    ["小林同学", "白日梦想家", "路过的猫", "一只团子", "夏天的风", "心动小鹿", "晚风吹过", "摸鱼大师", "示例坏人", "心动星星", "柠檬汽水", "棉花糖"];

/// A hotkey check, warm, in seconds: up to the first is fine, up to the second slow, beyond very slow.
pub const SPEED_FINE: f64 = 3.0;
pub const SPEED_SLOW: f64 = 6.0;
/// Steps the report names: (key, words).
pub const STEPS: [(&str, &str); 4] = [("capture", "截屏"), ("glance", "发现大厅"), ("find", "找名单"), ("read", "读名字")];
/// How wide the sample lobby is laid on the screen copy: a game window, not the whole screen.
pub const LOBBY_SHARE: f64 = 0.64;

/// One check's steps in the order they ran: (key, seconds). Keys are those of [`STEPS`].
pub type Run = Vec<(String, f64)>;

fn words(key: &str) -> &str {
    STEPS.iter().find(|(k, _)| *k == key).map_or(key, |(_, w)| w)
}

fn total(run: &[(String, f64)]) -> f64 {
    py_sum(run.iter().map(|(_, v)| *v))
}

/// Python's sum() of floats (3.12 and later): Neumaier's compensated sum, so 0.04 + 0.1 + 1.0 is 1.14 as
/// Python prints it, not 1.1400000000000001.
pub fn py_sum(values: impl IntoIterator<Item = f64>) -> f64 {
    let (mut sum, mut c) = (0.0_f64, 0.0_f64);
    for x in values {
        let t = sum + x;
        c += if sum.abs() >= x.abs() { (sum - t) + x } else { (x - t) + sum };
        sum = t;
    }
    if c != 0.0 && c.is_finite() {
        sum += c;
    }
    sum
}

/// 环境测试's timings: the two ways a check starts, each step, on the sample lobby laid in the real
/// screen copy. 自动检查: a glance at the top of the screen, then the lobby found and read. The hotkey:
/// the screen copied, then found and read; three times, the first searching for the lobby.
#[derive(Debug, Clone, PartialEq)]
pub struct FlowTest {
    pub size: (u32, u32),
    pub screens: u32,
    pub device: String,
    pub capture: f64,
    pub glance: f64,
    pub glance_found: bool,
    pub auto: Run,
    pub runs: Vec<Run>,
    pub right: u32,
    pub error: String,
    pub cpu_busy: Option<f64>,
    pub cpu_own: Option<f64>,
    pub power: String,
}

impl Default for FlowTest {
    fn default() -> Self {
        FlowTest {
            size: (0, 0),
            screens: 1,
            device: "cpu".into(),
            capture: 0.0,
            glance: 0.0,
            glance_found: false,
            auto: Vec::new(),
            runs: Vec::new(),
            right: 0,
            error: String::new(),
            cpu_busy: None,
            cpu_own: None,
            power: String::new(),
        }
    }
}

impl FlowTest {
    /// A warm hotkey check, step by step: the middle of the later runs (by total; ties keep their order).
    pub fn hotkey(&self) -> Run {
        let warm = if self.runs.len() > 1 { &self.runs[1..] } else { &self.runs[..] };
        if warm.is_empty() {
            return Vec::new();
        }
        let mut ordered: Vec<&Run> = warm.iter().collect();
        ordered.sort_by(|a, b| total(a).total_cmp(&total(b)));
        ordered[ordered.len() / 2].clone()
    }

    pub fn hotkey_total(&self) -> f64 {
        total(&self.hotkey())
    }

    pub fn auto_total(&self) -> f64 {
        self.glance + total(&self.auto)
    }

    pub fn first_total(&self) -> f64 {
        self.runs.first().map_or(0.0, |run| total(run))
    }

    pub fn verdict(&self) -> &'static str {
        let seconds = self.hotkey_total();
        if seconds <= SPEED_FINE {
            "正常"
        } else if seconds <= SPEED_SLOW {
            "有点慢"
        } else {
            "很慢"
        }
    }

    /// Why it took as long as it did, in plain words, the biggest reason first.
    pub fn causes(&self) -> Vec<String> {
        if !self.error.is_empty() {
            return vec![self.error.clone()];
        }
        let mut out = Vec::new();
        if let (Some(busy), Some(own)) = (self.cpu_busy, self.cpu_own) {
            let others = busy - own;
            if others >= 40.0 {
                out.push(format!("电脑很忙：CPU 用了 {busy:.0}%，其中别的程序占 {others:.0}%（比如游戏），关掉一些会更快"));
            }
        }
        if self.power.contains("battery") {
            out.push("笔记本在用电池，接上电源会更快".into());
        }
        let steps = self.hotkey();
        if !steps.is_empty() && self.verdict() != "正常" {
            // max() in Python keeps the first of equal values.
            let slowest = steps.iter().skip(1).fold(&steps[0], |best, step| if step.1 > best.1 { step } else { best });
            out.push(format!("最慢的一步是「{}」：{:.1} 秒", words(&slowest.0), slowest.1));
        }
        let (first, warm) = (self.first_total(), self.hotkey_total());
        if !self.runs.is_empty() && first > 1.5 * warm.max(0.1) && first > 1.0 {
            out.push(format!("第一次检查要先找大厅（{first:.1} 秒）；窗口不动，之后每次约 {warm:.1} 秒"));
        }
        out
    }

    /// The report for the log and the export, with the numbers behind it.
    pub fn text(&self) -> String {
        if !self.error.is_empty() {
            return format!("环境测试：没完成，{}", self.error);
        }
        let warm = self.hotkey_total();
        let steps: Vec<String> = self.hotkey().iter().map(|(k, v)| format!("{} {v:.2}", words(k))).collect();
        let auto: String = self.auto.iter().map(|(k, v)| format!(" + {} {v:.2}", words(k))).collect();
        let runs: Vec<String> = self.runs.iter().map(|run| format!("{:.2}", total(run))).collect();
        let screens = if self.screens != 1 { format!("，{} 块", self.screens) } else { String::new() };
        let mut lines = vec![
            format!("环境测试：检查一次约 {warm:.1} 秒，{}", self.verdict()),
            format!("  手动检查（快捷键）：{warm:.2} s = {}", steps.join(" + ")),
            format!("  自动检查：{:.2} s = 发现大厅 {:.2}{auto}", self.auto_total(), self.glance),
            format!("  每次手动检查：{} s", runs.join(", ")),
            format!("  示例大厅的 12 个名字读对 {} 个；识别用 {}；屏幕 {}x{}{screens}", self.right, self.device, self.size.0, self.size.1),
        ];
        if let Some(busy) = self.cpu_busy {
            let power = if self.power.is_empty() { String::new() } else { format!("；{}", self.power) };
            lines.push(format!("  CPU {busy:.0}%（本工具 {:.0}%）{power}", self.cpu_own.unwrap_or(0.0)));
        }
        lines.extend(self.causes().into_iter().map(|cause| format!("  · {cause}")));
        lines.join("\n")
    }
}
