//! Parity with the Python dialogs on golden.tsv, which rust/app/shots/dialogs/golden.py writes with the Python
//! app's own code: 添加 / 编辑's name check, 直播模式's masked names, and 选择片段's clock, peaks and strip.

use super::models::{flow, masked_name, name_chips, name_problem, pill_width};
use super::trim::{clock, peaks, Part, Strip, LIMIT_S};
use data::store::text::fold;

const GOLDEN: &str = include_str!("golden.tsv");

fn cases(kind: &str) -> Vec<Vec<&'static str>> {
    let found: Vec<Vec<&str>> = GOLDEN
        .lines()
        .map(|line| line.split('\t').collect::<Vec<_>>())
        .filter(|fields| fields[0] == kind)
        .collect();
    assert!(!found.is_empty(), "no {kind} cases");
    found
}

fn number(text: &str) -> f64 {
    text.parse().expect("a number")
}

fn close(a: f64, b: f64) -> bool {
    (a - b).abs() < 1e-9
}

#[test]
fn the_name_check_says_what_python_says() {
    let taken = vec![fold("示例坏人")];
    for case in cases("name") {
        assert_eq!(name_problem(case[1], &taken), case[2], "{:?}", case[1]);
    }
}

#[test]
fn masked_names_match() {
    for case in cases("mask") {
        assert_eq!(masked_name(case[1]), case[2]);
    }
}

#[test]
fn the_clock_matches() {
    for case in cases("clock") {
        assert_eq!(clock(number(case[1])), case[2], "{}", case[1]);
    }
}

#[test]
fn peaks_match() {
    for case in cases("peaks") {
        let samples: Vec<i16> = case[1]
            .split(' ')
            .map(|value| value.parse().expect("a sample"))
            .collect();
        let columns: usize = case[2].parse().expect("columns");
        let want: Vec<f32> = case[3]
            .split(' ')
            .map(|value| value.parse().expect("a peak"))
            .collect();
        assert_eq!(
            peaks(&samples, columns),
            want,
            "{} samples in {columns}",
            samples.len()
        );
    }
}

#[test]
fn the_window_is_kept_where_python_keeps_it() {
    for case in cases("select") {
        let mut strip = Strip::new(20.0, LIMIT_S);
        strip.set_selection(number(case[1]), number(case[2]));
        assert!(
            close(strip.start, number(case[3])) && close(strip.length, number(case[4])),
            "{case:?}: {strip:?}"
        );
    }
}

#[test]
fn a_press_takes_what_python_takes() {
    let mut strip = Strip::new(20.0, LIMIT_S);
    strip.set_selection(4.0, 2.0);
    for case in cases("part") {
        let x = number(case[1]);
        let part = match case[2] {
            "left" => Part::Left,
            "right" => Part::Right,
            _ => Part::Seek,
        };
        assert_eq!(strip.part(x), part, "x {x}");
        assert!(close(strip.time_at(x), number(case[3])), "time_at {x}");
        assert!(close(strip.x_of(x / 28.0), number(case[4])), "x_of {x}");
    }
}

#[test]
fn dragging_an_edge_keeps_the_limits() {
    let mut strip = Strip::new(20.0, LIMIT_S);
    strip.set_selection(4.0, 2.0);
    // The left edge far left: the window grows to the limit, its end staying put.
    strip.drag(Part::Left, 8.0);
    assert!(
        close(strip.start, 1.0) && close(strip.length, 5.0),
        "{strip:?}"
    );
    // The right edge onto the left one: the shortest part is kept.
    strip.drag(Part::Right, strip.x_of(1.0));
    assert!(close(strip.length, 0.5), "{strip:?}");
    strip.drag(Part::Seek, strip.x_of(12.0));
    assert!(close(strip.playhead, 12.0));
    assert!(strip.nudge(0.1) && close(strip.start, 1.1));
}

#[test]
fn pills_flow_into_lines_that_fit() {
    let catalog: Vec<String> = [
        "炸房",
        "贴脸",
        "挂机",
        "场外",
        "不尊重底牌",
        "送人头",
        "开局就退",
        "骂人",
    ]
    .map(String::from)
    .to_vec();
    let chips = name_chips(&catalog, &["场外".to_string(), "自定义".to_string()]);
    // The record's own first (in catalog order, then its others), then the rest of the catalog, off.
    assert_eq!(chips[0], ("场外".to_string(), true));
    assert_eq!(chips[1], ("自定义".to_string(), true));
    assert_eq!(chips[2], ("炸房".to_string(), false));
    let lines = flow(&chips, 200.0);
    assert!(lines.len() > 1);
    for line in &lines {
        let wide: f32 = line.iter().map(|(tag, _)| pill_width(tag)).sum::<f32>()
            + 8.0 * (line.len() - 1) as f32;
        assert!(wide <= 200.0 || line.len() == 1, "{line:?}");
    }
    assert_eq!(lines.iter().map(Vec::len).sum::<usize>(), chips.len());
}
