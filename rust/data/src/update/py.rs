//! The few Python behaviours updater.py leans on, so the port accepts and rejects exactly what it does:
//! str() and int() and float() of a JSON value, iterating one, str.strip(), and base64.b64decode().

use serde_json::Value;

/// Python's str(): what str() of the value json.loads gave would say. None for a list or a dict
/// (their repr is never a valid version, address or hash; noted in the port's report).
pub fn str_of(value: &Value) -> Option<String> {
    Some(match value {
        Value::String(text) => text.clone(),
        Value::Null => "None".into(),
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        Value::Number(number) => match (number.as_i64(), number.as_u64(), number.as_f64()) {
            (Some(int), _, _) => int.to_string(),
            (_, Some(int), _) => int.to_string(),
            (_, _, Some(float)) => float_repr(float),
            _ => number.to_string(),
        },
        Value::Array(_) | Value::Object(_) => return None,
    })
}

/// Python's repr() of a float: the shortest round trip, with ".0" on whole numbers.
pub fn float_repr(float: f64) -> String {
    if float.is_finite() && float.fract() == 0.0 && float.abs() < 1e16 {
        format!("{float:.1}")
    } else {
        format!("{float}")
    }
}

/// `for item in value`: a list's items, a string's characters, a dict's keys. None where Python raises.
pub fn iter_of(value: &Value) -> Option<Vec<Value>> {
    match value {
        Value::Array(items) => Some(items.clone()),
        Value::String(text) => Some(text.chars().map(|c| Value::String(c.to_string())).collect()),
        Value::Object(map) => Some(map.keys().map(|key| Value::String(key.clone())).collect()),
        _ => None,
    }
}

/// Python's int() of a JSON value: ints as they are, floats cut toward zero, bools as 0/1, strings parsed.
pub fn int_of(value: &Value) -> Option<i64> {
    match value {
        Value::Bool(flag) => Some(i64::from(*flag)),
        Value::Number(number) => number.as_i64().or_else(|| {
            let float = number.as_f64()?;
            (float.is_finite() && float.abs() < 9.2e18).then_some(float.trunc() as i64)
        }),
        Value::String(text) => parse_int(text),
        _ => None,
    }
}

/// Python's float() of a JSON value.
pub fn float_of(value: &Value) -> Option<f64> {
    match value {
        Value::Bool(flag) => Some(f64::from(u8::from(*flag))),
        Value::Number(number) => number.as_f64(),
        Value::String(text) => {
            let text = strip(text).replace('_', "");
            match text.to_ascii_lowercase().trim_start_matches(['+', '-']) {
                "inf" | "infinity" | "nan" => None,
                _ => text.parse().ok(),
            }
        }
        _ => None,
    }
}

/// int("…"): surrounding whitespace, one sign, digits with single underscores between them.
pub fn parse_int(text: &str) -> Option<i64> {
    let text = strip(text);
    let (negative, digits) = match text.as_bytes().first() {
        Some(b'-') => (true, &text[1..]),
        Some(b'+') => (false, &text[1..]),
        _ => (false, text),
    };
    if digits.is_empty() || digits.starts_with('_') || digits.ends_with('_') || digits.contains("__") {
        return None;
    }
    let mut number: i64 = 0;
    for c in digits.chars().filter(|c| *c != '_') {
        // ASCII and fullwidth digits; Python takes every Unicode decimal digit (noted in the report).
        let digit = c.to_digit(10).or_else(|| ('０'..='９').contains(&c).then(|| c as u32 - '０' as u32))?;
        number = number.checked_mul(10)?.checked_add(i64::from(digit))?;
    }
    Some(if negative { -number } else { number })
}

/// Python's str.strip(): Unicode whitespace, and the four separators (\x1c-\x1f) Python counts too.
pub fn strip(text: &str) -> &str {
    text.trim_matches(|c: char| c.is_whitespace() || ('\x1c'..='\x1f').contains(&c))
}

/// base64.b64decode(text) without validate: CPython 3.12's binascii.a2b_base64 (the app's runtime), step for step. Characters
/// outside the alphabet are skipped, a complete padding ends the data, and a broken end is an error.
pub fn b64decode(text: &str) -> Option<Vec<u8>> {
    if !text.is_ascii() {
        return None;
    }
    let mut out = Vec::new();
    let (mut quad, mut left, mut pads) = (0u8, 0u32, 0u32);
    for byte in text.bytes() {
        if byte == b'=' {
            // `quad_pos >= 2 && quad_pos + ++pads >= 4`: padding counts only once two characters are in.
            if quad >= 2 {
                pads += 1;
            }
            if quad >= 2 && u32::from(quad) + pads >= 4 {
                return Some(out);
            }
            continue;
        }
        let Some(six) = sextet(byte) else { continue };
        match quad {
            0 => {
                left = six;
                quad = 1;
            }
            1 => {
                out.push(((left << 2) | (six >> 4)) as u8);
                left = six & 0x0f;
                quad = 2;
            }
            2 => {
                out.push(((left << 4) | (six >> 2)) as u8);
                left = six & 0x03;
                quad = 3;
            }
            _ => {
                out.push(((left << 6) | six) as u8);
                quad = 0;
            }
        }
    }
    (quad == 0).then_some(out)
}

fn sextet(byte: u8) -> Option<u32> {
    Some(u32::from(match byte {
        b'A'..=b'Z' => byte - b'A',
        b'a'..=b'z' => byte - b'a' + 26,
        b'0'..=b'9' => byte - b'0' + 52,
        b'+' => 62,
        b'/' => 63,
        _ => return None,
    }))
}
