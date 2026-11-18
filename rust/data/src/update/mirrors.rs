//! Where to fetch from, and the route that worked last (mirrors.json beside the settings), as
//! updater.mirrors() and updater._remember() keep them. The folder is passed in: app_dir() in the app.

use std::path::Path;

use serde_json::Value;

use super::{good_mirror, py, MIRRORS, MIRROR_FILE};

/// What mirrors.json says: the one that worked last (None until something has), and the listed ones.
fn saved(folder: &Path) -> (Option<String>, Vec<String>) {
    let Some(saved) = std::fs::read(folder.join(MIRROR_FILE))
        .ok()
        .and_then(|bytes| String::from_utf8(bytes).ok())
        .and_then(|text| serde_json::from_str::<Value>(&text).ok())
    else {
        return (None, Vec::new());
    };
    // `"preferred" in saved` then saved["preferred"]: only a dict gets this far without raising.
    let Some(map) = saved.as_object() else { return (None, Vec::new()) };
    let preferred = map.get("preferred").map(|value| py::str_of(value).unwrap_or_default());
    let listed = match map.get("listed") {
        None => Vec::new(),
        Some(value) => py::iter_of(value)
            .and_then(|items| items.iter().map(py::str_of).collect::<Option<Vec<_>>>())
            .unwrap_or_default(),
    };
    (preferred, listed)
}

/// Where to try, in order: the one that worked last, MIRRORS as listed, then any a release named.
pub fn mirrors(folder: &Path) -> Vec<String> {
    let mut order: Vec<String> = MIRRORS.iter().map(|prefix| prefix.to_string()).collect();
    let (preferred, listed) = saved(folder);
    for prefix in listed {
        if good_mirror(&prefix) && !order.contains(&prefix) {
            order.push(prefix);
        }
    }
    if let Some(preferred) = preferred.filter(|prefix| good_mirror(prefix)) {
        if let Some(at) = order.iter().position(|prefix| *prefix == preferred) {
            order.remove(at);
            order.insert(0, preferred);
        }
    }
    order
}

/// Remember the route that worked, and the proxies a release named (or keep the ones already listed).
/// A file that cannot be written is let go, as updater._remember does.
pub fn remember(folder: &Path, preferred: &str, listed: &[String]) {
    let path = folder.join(MIRROR_FILE);
    let listed: Vec<String> = if listed.is_empty() {
        std::fs::read(&path)
            .ok()
            .and_then(|bytes| String::from_utf8(bytes).ok())
            .and_then(|text| serde_json::from_str::<Value>(&text).ok())
            .and_then(|saved| {
                // Python keeps the raw items; a non-string one would make _good_mirror raise. Left out here.
                let items = py::iter_of(saved.as_object()?.get("listed").unwrap_or(&Value::Array(Vec::new())))?;
                Some(items.into_iter().filter_map(|item| item.as_str().map(str::to_owned)).collect())
            })
            .unwrap_or_default()
    } else {
        listed.to_vec()
    };
    let kept: Vec<String> = listed.iter().filter(|item| good_mirror(item)).map(|item| quoted(item)).collect();
    let text = format!("{{\"preferred\": {}, \"listed\": [{}]}}", quoted(preferred), kept.join(", "));
    if std::fs::create_dir_all(folder).is_ok() {
        let _ = std::fs::write(&path, text);
    }
}

/// json.dumps of a string with ensure_ascii=False.
pub(crate) fn quoted(text: &str) -> String {
    let mut out = String::from("\"");
    for c in text.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\x08' => out.push_str("\\b"),
            '\x0c' => out.push_str("\\f"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}
