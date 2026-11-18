//! What storage.py leans on from Python itself, over JSON values: `str()`, truth, iterating, `int()`, `round()`, and
//! `json.dumps(..., ensure_ascii=False, indent=2)` to the byte.

use serde_json::{Map, Value};

/// A file that does not read as the Python app expects: storage.py's `except (OSError, ValueError, AttributeError,
/// TypeError)`, which sets the file aside.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Bad(pub String);

impl std::fmt::Display for Bad {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for Bad {}

pub type Res<T> = Result<T, Bad>;

pub fn bad<T>(why: &str) -> Res<T> {
    Err(Bad(why.to_string()))
}

/// `value.get(key)`: only a dict has it (AttributeError otherwise).
pub fn dict(value: &Value) -> Res<&Map<String, Value>> {
    value.as_object().ok_or_else(|| Bad("not a dict".into()))
}

/// Python's truth of a JSON value.
pub fn truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// `for x in value`: a list's items, a string's characters, a dict's keys; anything else is a TypeError.
pub fn iter(value: &Value) -> Res<Vec<Value>> {
    match value {
        Value::Array(a) => Ok(a.clone()),
        Value::String(s) => Ok(s.chars().map(|c| Value::String(c.to_string())).collect()),
        Value::Object(o) => Ok(o.keys().map(|k| Value::String(k.clone())).collect()),
        _ => bad("not iterable"),
    }
}

/// `str(value)`.
pub fn py_str(value: &Value) -> String {
    match value {
        Value::String(s) => s.clone(),
        other => repr(other),
    }
}

/// `repr(value)` of what json.loads returns.
pub fn repr(value: &Value) -> String {
    match value {
        Value::Null => "None".into(),
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        Value::Number(n) => number(n),
        Value::String(s) => repr_str(s),
        Value::Array(a) => format!("[{}]", a.iter().map(repr).collect::<Vec<_>>().join(", ")),
        Value::Object(o) => {
            let items: Vec<String> = o.iter().map(|(k, v)| format!("{}: {}", repr_str(k), repr(v))).collect();
            format!("{{{}}}", items.join(", "))
        }
    }
}

fn repr_str(s: &str) -> String {
    let quote = if s.contains('\'') && !s.contains('"') { '"' } else { '\'' };
    let mut out = String::from(quote);
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if (c as u32) < 0x20 || c as u32 == 0x7f => out.push_str(&format!("\\x{:02x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}

fn number(n: &serde_json::Number) -> String {
    if let Some(i) = n.as_i64() {
        i.to_string()
    } else if let Some(u) = n.as_u64() {
        u.to_string()
    } else {
        float_repr(n.as_f64().unwrap_or(0.0))
    }
}

/// `repr(float)`: the shortest digits that read back the same, fixed from 1e-4 up to 1e16, else with an exponent.
pub fn float_repr(f: f64) -> String {
    if f.is_nan() {
        return "NaN".into();
    }
    if f.is_infinite() {
        return if f > 0.0 { "Infinity".into() } else { "-Infinity".into() };
    }
    let sci = format!("{f:e}");
    let (mantissa, exp) = sci.split_once('e').unwrap_or((&sci, "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    if (-4..16).contains(&exp) {
        let fixed = format!("{f}");
        if fixed.contains('.') { fixed } else { format!("{fixed}.0") }
    } else {
        format!("{mantissa}e{}{:02}", if exp < 0 { '-' } else { '+' }, exp.abs())
    }
}

/// A number as Python sees it: an int (bool counts) or a float. None for anything else.
pub fn num(value: &Value) -> Option<f64> {
    match value {
        Value::Bool(b) => Some(f64::from(u8::from(*b))),
        Value::Number(n) => n.as_f64(),
        _ => None,
    }
}

/// `isinstance(value, int) and not isinstance(value, bool)`.
pub fn plain_int(value: &Value) -> Option<i64> {
    value.as_i64()
}

/// `int(value)`: an int or bool as it is, a float cut toward 0, a string of digits (spaces and single underscores
/// allowed, as Python takes them). Anything else is a ValueError or TypeError.
pub fn int(value: &Value) -> Res<i64> {
    match value {
        Value::Bool(b) => Ok(i64::from(*b)),
        Value::Number(n) => match n.as_i64() {
            Some(i) => Ok(i),
            None => n.as_f64().filter(|f| f.is_finite()).map(|f| f.trunc() as i64).ok_or_else(|| Bad("int".into())),
        },
        Value::String(s) => int_text(s).ok_or_else(|| Bad("int".into())),
        _ => bad("int"),
    }
}

fn int_text(s: &str) -> Option<i64> {
    let t = strip(s);
    let (neg, digits) = match t.strip_prefix('-') {
        Some(rest) => (true, rest),
        None => (false, t.strip_prefix('+').unwrap_or(t)),
    };
    if digits.is_empty() || digits.starts_with('_') || digits.ends_with('_') || digits.contains("__") {
        return None;
    }
    let plain: String = digits.chars().filter(|c| *c != '_').collect();
    if !plain.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }
    let n: i64 = plain.parse().ok()?;
    Some(if neg { -n } else { n })
}

/// `round(x)`: to the nearest int, a half to the even one.
pub fn round_even(x: f64) -> f64 {
    x.round_ties_even()
}

/// `round(x, 2)`, correctly rounded as Python does it, through the exact decimal.
pub fn round2(x: f64) -> f64 {
    format!("{x:.2}").parse().unwrap_or(x)
}

/// `str.isspace()` for one character.
pub fn is_space(c: char) -> bool {
    c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c)
}

/// `str.strip()`.
pub fn strip(s: &str) -> &str {
    s.trim_matches(is_space)
}

/// `s[:n]`, in characters.
pub fn cut(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

/// `json.dumps(value, ensure_ascii=False, indent=2)`, with the line ending Path.write_text gives (CRLF on Windows).
pub fn dumps(value: &Value) -> String {
    let mut out = String::new();
    write(value, 0, &mut out);
    if cfg!(windows) { out.replace('\n', "\r\n") } else { out }
}

fn write(value: &Value, depth: usize, out: &mut String) {
    let pad = |d: usize, out: &mut String| {
        out.push('\n');
        out.push_str(&"  ".repeat(d));
    };
    match value {
        Value::Array(a) if a.is_empty() => out.push_str("[]"),
        Value::Object(o) if o.is_empty() => out.push_str("{}"),
        Value::Array(a) => {
            out.push('[');
            for (i, item) in a.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                pad(depth + 1, out);
                write(item, depth + 1, out);
            }
            pad(depth, out);
            out.push(']');
        }
        Value::Object(o) => {
            out.push('{');
            for (i, (k, v)) in o.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                pad(depth + 1, out);
                string(k, out);
                out.push_str(": ");
                write(v, depth + 1, out);
            }
            pad(depth, out);
            out.push('}');
        }
        Value::String(s) => string(s, out),
        Value::Null => out.push_str("null"),
        Value::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Value::Number(n) => out.push_str(&number(n)),
    }
}

fn string(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}

/// `json.loads(path.read_text(encoding="utf-8-sig"))`.
pub fn loads(bytes: &[u8]) -> Res<Value> {
    let bytes = bytes.strip_prefix(b"\xef\xbb\xbf").unwrap_or(bytes);
    let text = std::str::from_utf8(bytes).map_err(|e| Bad(e.to_string()))?;
    serde_json::from_str(text).map_err(|e| Bad(e.to_string()))
}

/// A float as json.dumps writes it (`1` saved as seconds is `1.0`).
pub fn float(f: f64) -> Value {
    serde_json::Number::from_f64(f).map_or(Value::Null, Value::Number)
}
