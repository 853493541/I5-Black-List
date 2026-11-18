//! 选择片段's data, for the UI package that draws it (ui_sound_trim.Waveform, SoundTrimDialog's rules) and the
//! bars that move while a sound plays (ui_soundwave.SoundWave.levels). No drawing here.

/// The longest part a 场景's sound keeps, the shortest the window can be made, and an arrow key's step.
pub const LIMIT_S: f64 = 5.0;
pub const MIN_S: f64 = 0.5;
pub const NUDGE_S: f64 = 0.1;
/// The strip: its size, the room left and right of the sound, and how near an edge a press takes that edge.
pub const STRIP_W: f64 = 560.0;
pub const STRIP_H: f64 = 104.0;
pub const INSET: f64 = 8.0;
pub const GRIP: f64 = 7.0;
/// The bars beside a ▶ while it plays: how many, their room, a bar's width, a frame each this many ms.
pub const WAVE_BARS: usize = 5;
pub const WAVE_W: f64 = 30.0;
pub const WAVE_H: f64 = 18.0;
pub const WAVE_BAR_W: f64 = 3.6;
pub const WAVE_FRAME_MS: u64 = 40;

/// A moment of the sound as minutes and seconds to a tenth: 0:12.3.
pub fn clock(seconds: f64) -> String {
    let tenths = (seconds * 10.0).round_ties_even().max(0.0) as i64;
    format!("{}:{:04.1}", tenths / 600, (tenths % 600) as f64 / 10.0)
}

/// The loudest sample in each of `columns` equal stretches of the sound, 0 to 32768 (np.maximum.reduceat: a
/// stretch whose start is not before the next one's is that one sample).
pub fn peaks(samples: &[i16], columns: usize) -> Vec<f64> {
    let count = samples.len();
    if count == 0 || columns == 0 {
        return vec![0.0; columns];
    }
    let starts: Vec<usize> = (0..columns).map(|i| (i * count / columns).min(count - 1)).collect();
    (0..columns)
        .map(|i| {
            let from = starts[i];
            let to = match starts.get(i + 1) {
                Some(&next) if next > from => next,
                Some(_) => from + 1,
                None => count,
            };
            samples[from..to].iter().map(|&s| i32::from(s).abs()).max().unwrap_or(0) as f64
        })
        .collect()
}

/// Each column's height, 0 to 1, as the strip draws it: a quiet sound is not blown up past 1000.
pub fn strip_heights(samples: &[i16], columns: usize) -> Vec<f64> {
    let found = peaks(samples, columns);
    let top = found.iter().copied().fold(0.0f64, f64::max).max(1000.0);
    found.into_iter().map(|p| p / top).collect()
}

/// What a press on the strip takes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Grip {
    Left,
    Right,
    /// The playhead.
    Seek,
}

/// The window over the part that plays, in seconds, kept within its rules (ui_sound_trim.Waveform).
#[derive(Debug, Clone, PartialEq)]
pub struct Trim {
    pub duration: f64,
    pub limit: f64,
    pub shortest: f64,
    pub start: f64,
    pub length: f64,
    /// The strip's width in pixels (its x_of and time_at).
    pub width: f64,
}

impl Trim {
    pub fn new(samples: usize, rate: u32, limit_s: f64) -> Self {
        let duration = if rate > 0 { samples as f64 / f64::from(rate) } else { 0.0 };
        let limit = limit_s.min(duration);
        Self { duration, limit, shortest: MIN_S.min(limit), start: 0.0, length: limit, width: STRIP_W }
    }

    /// The part picked, to the millisecond, as the dialog hands it on.
    pub fn selection(&self) -> (f64, f64) {
        let ms = |v: f64| format!("{v:.3}").parse::<f64>().unwrap_or(v);
        (ms(self.start), ms(self.length))
    }

    /// The window from start, length long, kept within limit, the shortest and the sound's ends. Whether it moved.
    pub fn set_selection(&mut self, start: f64, length: f64) -> bool {
        let length = length.max(self.shortest).min(self.limit);
        let start = start.max(0.0).min(self.duration - length);
        if (start, length) == (self.start, self.length) {
            return false;
        }
        (self.start, self.length) = (start, length);
        true
    }

    /// ◀ ▶ and ← →.
    pub fn nudge(&mut self, seconds: f64) -> bool {
        self.set_selection(self.start + seconds, self.length)
    }

    /// 截取: the limit seconds just heard, up to the playhead.
    pub fn cut(&mut self, head: f64) -> bool {
        self.set_selection(head - self.limit, self.limit)
    }

    pub fn x_of(&self, seconds: f64) -> f64 {
        let wide = self.width - 2.0 * INSET;
        INSET + if self.duration > 0.0 { seconds / self.duration * wide } else { 0.0 }
    }

    pub fn time_at(&self, x: f64) -> f64 {
        let wide = self.width - 2.0 * INSET;
        ((x - INSET) / wide * self.duration).max(0.0).min(self.duration)
    }

    /// What a press at x takes: an edge of the window (GRIP either side, no further in than its middle), else the playhead.
    pub fn grip_at(&self, x: f64) -> Grip {
        let (left, right) = (self.x_of(self.start), self.x_of(self.start + self.length));
        let centre = (left + right) / 2.0;
        if left - GRIP <= x && x <= (left + GRIP).min(centre) {
            Grip::Left
        } else if centre.max(right - GRIP) <= x && x <= right + GRIP {
            Grip::Right
        } else {
            Grip::Seek
        }
    }

    /// An edge held and dragged to x. Seek is the caller's (the playhead goes to time_at(x)).
    pub fn drag(&mut self, grip: Grip, x: f64) -> bool {
        let at = self.time_at(x);
        let end = self.start + self.length;
        match grip {
            Grip::Left => {
                let start = at.max(end - self.limit).max(0.0).min(end - self.shortest);
                self.set_selection(start, end - start)
            }
            Grip::Right => {
                let end = at.max(self.start + self.shortest).min(self.start + self.limit).min(self.duration);
                self.set_selection(self.start, end - self.start)
            }
            Grip::Seek => false,
        }
    }
}

/// Each bar's height at t seconds, 0.2 to 1 of the room: two slow waves on each, out of step with its neighbours.
pub fn wave_levels(t: f64) -> [f64; WAVE_BARS] {
    let mut out = [0.0; WAVE_BARS];
    for (bar, level) in out.iter_mut().enumerate() {
        let b = bar as f64;
        let wave = 0.55 * (t * (7.0 + 1.3 * b) + b * 1.9).sin() + 0.45 * (t * (11.0 - 0.9 * b) + b * 0.7).sin();
        *level = 0.2 + 0.8 * (0.5 + 0.5 * wave);
    }
    out
}
