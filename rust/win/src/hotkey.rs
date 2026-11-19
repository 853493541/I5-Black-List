//! Hotkey text as the settings store it ("Ctrl+Shift+F8"), parsed the way hotkey.py parses it.

pub const MOD_ALT: u32 = 0x0001;
pub const MOD_CONTROL: u32 = 0x0002;
pub const MOD_SHIFT: u32 = 0x0004;
pub const MOD_WIN: u32 = 0x0008;
pub const MOD_NOREPEAT: u32 = 0x4000;

/// The modifiers in the order the display text lists them.
const MODIFIER_ORDER: [Modifier; 4] = [Modifier::Ctrl, Modifier::Alt, Modifier::Shift, Modifier::Win];

/// Shortcuts every program, or Windows, has: copying, pasting, undoing, saving, finding, closing.
const EVERYDAY_LETTERS: &str = "ACFNOPSTVWXYZ";
const EVERYDAY_OTHERS: [&str; 3] = ["Alt+F4", "Ctrl+F4", "Shift+F10"];

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Modifier {
    Ctrl,
    Alt,
    Shift,
    Win,
}

impl Modifier {
    pub fn name(self) -> &'static str {
        match self {
            Modifier::Ctrl => "Ctrl",
            Modifier::Alt => "Alt",
            Modifier::Shift => "Shift",
            Modifier::Win => "Win",
        }
    }

    fn flag(self) -> u32 {
        match self {
            Modifier::Ctrl => MOD_CONTROL,
            Modifier::Alt => MOD_ALT,
            Modifier::Shift => MOD_SHIFT,
            Modifier::Win => MOD_WIN,
        }
    }

    fn from_text(text: &str) -> Option<Modifier> {
        match text.to_lowercase().as_str() {
            "ctrl" | "control" => Some(Modifier::Ctrl),
            "alt" => Some(Modifier::Alt),
            "shift" => Some(Modifier::Shift),
            "win" | "meta" | "super" => Some(Modifier::Win),
            _ => None,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct HotkeySpec {
    pub display: String,
    pub modifiers: Vec<Modifier>,
    pub key: String,
    pub vk: u32,
}

impl HotkeySpec {
    /// The fsModifiers RegisterHotKey takes, MOD_NOREPEAT always set.
    pub fn win_modifiers(&self) -> u32 {
        self.modifiers.iter().fold(MOD_NOREPEAT, |flags, m| flags | m.flag())
    }
}

/// A letter, a digit, or F1-F12, in its canonical form.
fn canonical_key(part: &str) -> Option<String> {
    let token = part.trim();
    let mut chars = token.chars();
    if let (Some(c), None) = (chars.next(), chars.next()) {
        if c.is_ascii_alphanumeric() {
            return Some(c.to_ascii_uppercase().to_string());
        }
    }
    let upper = token.to_uppercase();
    let digits = upper.strip_prefix('F')?;
    if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let trimmed = digits.trim_start_matches('0');
    let number: u32 = if trimmed.is_empty() { 0 } else if trimmed.len() > 2 { return None } else { trimmed.parse().ok()? };
    (1..=12).contains(&number).then(|| format!("F{number}"))
}

fn vk_code(key: &str) -> u32 {
    let first = key.as_bytes()[0];
    if key.len() == 1 && first.is_ascii_uppercase() {
        return 0x41 + u32::from(first - b'A');
    }
    if key.len() == 1 && first.is_ascii_digit() {
        return 0x30 + u32::from(first - b'0');
    }
    let number: u32 = key[1..].parse().unwrap_or(1);
    0x70 + number - 1
}

fn joined(modifiers: &[Modifier], key: &str) -> String {
    modifiers.iter().map(|m| m.name()).chain(std::iter::once(key)).collect::<Vec<_>>().join("+")
}

/// Whether a key is one people use everywhere, which a hotkey would take from every program: a letter or
/// a number alone or with Shift (typing), Win with one (Windows' own), or a shortcut every program has.
pub fn everyday(modifiers: &[Modifier], key: &str) -> bool {
    if key.chars().count() == 1 && matches!(modifiers, [] | [Modifier::Shift] | [Modifier::Win]) {
        return true;
    }
    let text = joined(modifiers, key);
    if let Some(letter) = text.strip_prefix("Ctrl+") {
        if letter.len() == 1 && EVERYDAY_LETTERS.contains(letter) {
            return true;
        }
    }
    EVERYDAY_OTHERS.contains(&text.as_str())
}

/// Parse "Ctrl+Shift+F8". Empty means the hotkey is not set; a key in everyday use is none either.
pub fn parse_hotkey(text: &str) -> Option<HotkeySpec> {
    let raw = text.trim();
    if raw.is_empty() {
        return None;
    }
    let mut modifiers: Vec<Modifier> = Vec::new();
    let mut key: Option<String> = None;
    for part in raw.split('+') {
        let piece = part.trim();
        if piece.is_empty() {
            return None;
        }
        if let Some(modifier) = Modifier::from_text(piece) {
            if !modifiers.contains(&modifier) {
                modifiers.push(modifier);
            }
            continue;
        }
        if key.is_some() {
            return None;
        }
        key = Some(canonical_key(piece)?);
    }
    let key = key?;
    let ordered: Vec<Modifier> = MODIFIER_ORDER.into_iter().filter(|m| modifiers.contains(m)).collect();
    // Windows keeps F12 alone for its debugger: RegisterHotKey refuses it on every PC.
    if key == "F12" && ordered.is_empty() {
        return None;
    }
    if everyday(&ordered, &key) {
        return None;
    }
    Some(HotkeySpec { display: joined(&ordered, &key), vk: vk_code(&key), modifiers: ordered, key })
}

/// A hotkey of two keys at most: a longer one keeps its key and its first modifier
/// (Ctrl+Alt+F11 -> Ctrl+F11); anything else is returned as it is.
pub fn two_keys(text: &str) -> String {
    match parse_hotkey(text) {
        Some(spec) if spec.modifiers.len() > 1 => format!("{}+{}", spec.modifiers[0].name(), spec.key),
        _ => text.to_string(),
    }
}

/// A key pressed in the hotkey box (MainWindow._take_hotkey): the hotkey it makes, as 设置 spells it, or the note that
/// says what is wrong with it. `key` is A-Z, 0-9 or F1-F12 (anything else: None); `other` is the 场景 hotkey, which
/// 检查 never shares.
pub fn take_key(key: Option<&str>, modifiers: &[Modifier], other: &str) -> Result<String, &'static str> {
    let Some(key) = key else { return Err("用字母、数字或 F1–F12") };
    if modifiers.len() > 1 {
        // Two keys at most: short to press mid-game, and short to read.
        return Err("最多两个键，比如 Alt+1");
    }
    if key.chars().count() == 1 && matches!(modifiers, [] | [Modifier::Shift]) {
        // Typing it anywhere would press it.
        return Err("加上 Ctrl 或 Alt，比如 Alt+1");
    }
    if everyday(modifiers, key) {
        return Err("这是常用的键，换一个");
    }
    let Some(spec) = parse_hotkey(&joined(modifiers, key)) else { return Err("这个键用不了，换一个") };
    if parse_hotkey(other).is_some_and(|other| other.display == spec.display) {
        return Err("场景已在用这个键，换一个");
    }
    Ok(spec.display)
}

#[cfg(test)]
#[path = "hotkey_tests.rs"]
mod tests;
