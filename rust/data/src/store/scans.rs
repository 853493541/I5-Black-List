//! 记录: the lobbies checked, newest first (storage.py's history.json and the helpers that fold a lobby read twice).

use super::py::{self, cut, dict, int, py_str, truthy, Res};
use super::text::{clean_stored_name, fold, same_person, MAX_NAME};
use chrono::{DateTime, Datelike, FixedOffset, NaiveDateTime, Timelike};
use serde_json::{json, Value};

pub const MAX_SCANS: usize = 40;
const SAME_MATCH_COUNT: usize = 8;

#[derive(Debug, Clone, PartialEq)]
pub struct Seat {
    pub seat: i64,
    pub name: String,
    pub unclear: bool,
}

/// One check: when, how long it took (whatever was saved, kept as it was), and the seats read.
#[derive(Debug, Clone, PartialEq)]
pub struct Scan {
    pub at: String,
    pub elapsed: Value,
    pub names: Vec<Seat>,
}

impl Seat {
    /// storage._stored_seat, from a seat as a check gives it.
    pub fn stored(item: &Value) -> Res<Seat> {
        let map = dict(item)?;
        let get = |k: &str| map.get(k).cloned().unwrap_or(Value::Null);
        let name = get("name");
        Ok(Seat {
            seat: int(map.get("seat").unwrap_or(&json!(0)))?,
            name: cut(&if truthy(&name) { py_str(&name) } else { String::new() }, MAX_NAME),
            unclear: truthy(&get("unclear")),
        })
    }

    fn clear(&self) -> bool {
        !self.unclear && !py::strip(&self.name).is_empty()
    }

    fn to_value(&self) -> Value {
        json!({"seat": self.seat, "name": self.name, "unclear": self.unclear})
    }
}

impl Scan {
    pub fn to_value(&self) -> Value {
        json!({"at": self.at, "elapsed": self.elapsed, "names": self.names.iter().map(Seat::to_value).collect::<Vec<_>>()})
    }
}

/// history.json as Store.load reads it.
pub fn read(data: &Value) -> Res<Vec<Scan>> {
    let mut scans = Vec::new();
    for item in py::iter(dict(data)?.get("scans").unwrap_or(&json!([])))? {
        let item = dict(&item)?;
        let mut names = Vec::new();
        for seat in py::iter(item.get("names").unwrap_or(&json!([])))? {
            let seat = dict(&seat)?;
            let name = seat.get("name").map_or(String::new(), py_str);
            names.push(Seat {
                seat: int(seat.get("seat").unwrap_or(&json!(0)))?,
                name: cut(&name, MAX_NAME),
                unclear: seat.get("unclear").is_some_and(truthy),
            });
        }
        let at = item.get("at").map_or(String::new(), py_str);
        scans.push(Scan { at, elapsed: item.get("elapsed").cloned().unwrap_or(Value::Null), names });
    }
    Ok(scans)
}

pub fn to_value(scans: &[Scan]) -> Value {
    json!({"scans": scans.iter().take(MAX_SCANS).map(Scan::to_value).collect::<Vec<_>>()})
}

fn readable(names: &[Seat]) -> Vec<String> {
    names.iter().filter(|s| !s.unclear).map(|s| fold(&clean_stored_name(&s.name))).filter(|n| !n.is_empty()).collect()
}

fn shared(left: &[String], right: &[String]) -> usize {
    let mut pool = right.to_vec();
    let mut count = 0;
    for name in left {
        let at = pool.iter().position(|o| o == name).or_else(|| pool.iter().position(|o| same_person(name, o)));
        if let Some(at) = at {
            pool.remove(at);
            count += 1;
        }
    }
    count
}

/// storage._is_same_recording: the same lobby at another time, even with a few seats read differently.
pub fn same_recording(left: &[Seat], right: &[Seat]) -> bool {
    let (mut seen, mut other) = (readable(left), readable(right));
    if seen.is_empty() || other.is_empty() {
        return false;
    }
    if shared(&seen, &other) >= SAME_MATCH_COUNT {
        return true;
    }
    seen.sort();
    other.sort();
    seen == other
}

/// storage._collapse: a lobby saved twice is kept once, the newer.
pub fn collapse(scans: Vec<Scan>) -> Vec<Scan> {
    let mut kept: Vec<Scan> = Vec::new();
    for scan in scans {
        if !kept.iter().any(|k| same_recording(&scan.names, &k.names)) {
            kept.push(scan);
        }
    }
    kept
}

/// storage._fill_unclear: blank seats filled from a later read of the same lobby; None when nothing changes.
pub fn fill_unclear(existing: &[Seat], incoming: &[Seat]) -> Option<Vec<Seat>> {
    if existing.iter().all(Seat::clear) {
        return None;
    }
    let by_seat = |list: &[Seat]| {
        let mut map: Vec<(i64, Seat)> = Vec::new();
        for s in list {
            match map.iter_mut().find(|(k, _)| *k == s.seat) {
                Some(slot) => slot.1 = s.clone(),
                None => map.push((s.seat, s.clone())),
            }
        }
        map
    };
    let (old, new) = (by_seat(existing), by_seat(incoming));
    let find = |map: &[(i64, Seat)], k: i64| map.iter().find(|(s, _)| *s == k).map(|(_, v)| v.clone());
    for (seat, prev) in &old {
        let Some(next) = find(&new, *seat) else { continue };
        if !prev.clear() || !next.clear() {
            continue;
        }
        let (l, r) = (fold(&clean_stored_name(&prev.name)), fold(&clean_stored_name(&next.name)));
        if !l.is_empty() && !r.is_empty() && !same_person(&l, &r) {
            return None;
        }
    }
    let mut seats: Vec<i64> = old.iter().chain(new.iter()).map(|(k, _)| *k).collect();
    seats.sort_unstable();
    seats.dedup();
    let mut merged = Vec::new();
    let mut changed = false;
    for seat in seats {
        let (prev, next) = (find(&old, seat), find(&new, seat));
        match (prev, next) {
            (Some(p), _) if p.clear() => merged.push(p),
            (_, Some(n)) if n.clear() => {
                merged.push(n);
                changed = true;
            }
            (Some(p), _) => merged.push(p),
            (None, Some(n)) => merged.push(n),
            (None, None) => {}
        }
    }
    changed.then_some(merged)
}

/// datetime.fromisoformat for what the app writes (and the forms Python 3.11+ takes most often).
pub fn parse_at(stamp: &str, zone: FixedOffset) -> Option<DateTime<FixedOffset>> {
    if let Ok(t) = DateTime::parse_from_rfc3339(stamp) {
        return Some(t);
    }
    for form in ["%Y-%m-%dT%H:%M:%S%.f%:z", "%Y-%m-%d %H:%M:%S%.f%:z", "%Y-%m-%dT%H:%M%:z"] {
        if let Ok(t) = DateTime::parse_from_str(stamp, form) {
            return Some(t);
        }
    }
    for form in ["%Y-%m-%dT%H:%M:%S%.f", "%Y-%m-%d %H:%M:%S%.f", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"] {
        if let Ok(t) = NaiveDateTime::parse_from_str(stamp, form) {
            return t.and_local_timezone(zone).single();
        }
    }
    chrono::NaiveDate::parse_from_str(stamp, "%Y-%m-%d").ok()?.and_hms_opt(0, 0, 0)?.and_local_timezone(zone).single()
}

/// storage._same_clock_minute.
pub fn same_clock_minute(stamp: &str, now: DateTime<FixedOffset>) -> bool {
    let Some(then) = parse_at(stamp, *now.offset()) else { return false };
    let then = then.with_timezone(now.offset());
    (then.year(), then.month(), then.day(), then.hour(), then.minute()) == (now.year(), now.month(), now.day(), now.hour(), now.minute())
}

/// Store.add_scan on the list: "added", "refreshed", "filled" or "skipped", and whether to save.
pub fn add(scans: &mut Vec<Scan>, names: &[Seat], elapsed: Option<f64>, now: DateTime<FixedOffset>) -> &'static str {
    let record = Scan {
        at: now.format("%Y-%m-%dT%H:%M:%S%:z").to_string(),
        elapsed: elapsed.map_or(Value::Null, |e| py::float(py::round2(e))),
        names: names.to_vec(),
    };
    if let Some(first) = scans.first_mut() {
        if same_clock_minute(&first.at, now) {
            return match fill_unclear(&first.names, &record.names) {
                Some(merged) => {
                    first.names = merged;
                    "filled"
                }
                None => "skipped",
            };
        }
    }
    if !readable(&record.names).is_empty() {
        if let Some(at) = scans.iter().position(|s| same_recording(&record.names, &s.names)) {
            scans.remove(at);
            scans.insert(0, record);
            *scans = collapse(std::mem::take(scans));
            return "refreshed";
        }
    }
    scans.insert(0, record);
    scans.truncate(MAX_SCANS);
    "added"
}
