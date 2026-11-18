//! 选择片段's strip as ui_sound_trim.Waveform works it: the window over the part picked, kept within the limit,
//! the shortest part and the sound's ends; where a press lands; and the clock under it. The sound itself (its
//! samples, playing it) is the sound package's; this takes its peaks.

/// The longest part a 场景's sound keeps, the shortest the window can be made, and an arrow key's step.
pub const LIMIT_S: f64 = 5.0;
pub const MIN_S: f64 = 0.5;
pub const NUDGE_S: f64 = 0.1;
/// The strip's size, the room either side of the sound, and how near an edge a press takes it.
pub const W: f64 = 560.0;
pub const INSET: f64 = 8.0;
pub const GRIP: f64 = 7.0;

// stub: sound (the sound package gives the peaks of the decoded file)
/// The loudest sample in each of `columns` equal stretches of the sound, 0 to 32768 (ui_sound_trim.peaks).
pub fn peaks(samples: &[i16], columns: usize) -> Vec<f32> {
    let count = samples.len();
    if count == 0 {
        return vec![0.0; columns];
    }
    let starts: Vec<usize> = (0..columns)
        .map(|column| (column * count / columns).min(count - 1))
        .collect();
    (0..columns)
        .map(|column| {
            let from = starts[column];
            // reduceat: a stretch whose next start is not past it is that one sample.
            let to = starts
                .get(column + 1)
                .copied()
                .filter(|&next| next > from)
                .unwrap_or(if column + 1 == columns {
                    count
                } else {
                    from + 1
                });
            let part = &samples[from..to];
            let high = part.iter().copied().max().unwrap_or(0) as i32;
            let low = part.iter().copied().min().unwrap_or(0) as i32;
            high.max(-low) as f32
        })
        .collect()
}

/// The peaks as the strip draws them: a quiet file as big as a loud one, 0 to 1.
pub fn scaled(found: &[f32]) -> Vec<f32> {
    let top = found.iter().copied().fold(0.0f32, f32::max).max(1000.0);
    found.iter().map(|value| value / top).collect()
}

/// A moment of the sound as minutes and seconds to a tenth: 0:12.3.
pub fn clock(seconds: f64) -> String {
    let tenths = (seconds * 10.0).round_ties_even().max(0.0) as i64;
    format!("{}:{:04.1}", tenths / 600, (tenths % 600) as f64 / 10.0)
}

/// What a press took.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Part {
    Left,
    Right,
    Seek,
}

/// The strip's state: the sound's length, the window, and the playhead, in seconds.
#[derive(Clone, Debug, PartialEq)]
pub struct Strip {
    pub duration: f64,
    pub limit: f64,
    pub shortest: f64,
    pub start: f64,
    pub length: f64,
    pub playhead: f64,
}

impl Strip {
    pub fn new(duration: f64, limit_s: f64) -> Self {
        let limit = limit_s.min(duration);
        Strip {
            duration,
            limit,
            shortest: MIN_S.min(limit),
            start: 0.0,
            length: limit,
            playhead: 0.0,
        }
    }

    /// The window from start, length long, kept within the limit, the shortest and the sound's ends. True
    /// when it moved.
    pub fn set_selection(&mut self, start: f64, length: f64) -> bool {
        let length = length.max(self.shortest).min(self.limit);
        let start = start.max(0.0).min(self.duration - length);
        if (start, length) == (self.start, self.length) {
            return false;
        }
        (self.start, self.length) = (start, length);
        true
    }

    pub fn nudge(&mut self, seconds: f64) -> bool {
        self.set_selection(self.start + seconds, self.length)
    }

    pub fn x_of(&self, seconds: f64) -> f64 {
        INSET
            + if self.duration > 0.0 {
                seconds / self.duration * (W - 2.0 * INSET)
            } else {
                0.0
            }
    }

    pub fn time_at(&self, x: f64) -> f64 {
        ((x - INSET) / (W - 2.0 * INSET) * self.duration).clamp(0.0, self.duration)
    }

    /// What a press at x takes: an edge of the window (each reaching GRIP either side, but no further in than
    /// the window's middle), or else the playhead.
    pub fn part(&self, x: f64) -> Part {
        let (left, right) = (self.x_of(self.start), self.x_of(self.start + self.length));
        let centre = (left + right) / 2.0;
        if left - GRIP <= x && x <= (left + GRIP).min(centre) {
            Part::Left
        } else if (right - GRIP).max(centre) <= x && x <= right + GRIP {
            Part::Right
        } else {
            Part::Seek
        }
    }

    /// A drag of `part` to x: an edge resizes the window from its other end; the playhead goes there.
    pub fn drag(&mut self, part: Part, x: f64) {
        let at = self.time_at(x);
        let end = self.start + self.length;
        match part {
            Part::Left => {
                let start = at.max(end - self.limit).max(0.0).min(end - self.shortest);
                self.set_selection(start, end - start);
            }
            Part::Right => {
                let end = at
                    .max(self.start + self.shortest)
                    .min(self.start + self.limit)
                    .min(self.duration);
                self.set_selection(self.start, end - self.start);
            }
            Part::Seek => self.playhead = at,
        }
    }
}
