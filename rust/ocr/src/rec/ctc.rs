//! CTCLabelDecode as onnx_ocr.TextRecognizer.decode does it: the best character per step, repeats and blanks dropped,
//! the score the mean probability of the kept steps (numpy's float32 pairwise sum).

use super::Read;

/// The dictionary as inference.yml gives it, with CTC's blank first and a space last.
pub fn characters(dict: &[String]) -> Vec<String> {
    let mut out = Vec::with_capacity(dict.len() + 2);
    out.push("blank".to_string());
    out.extend(dict.iter().cloned());
    out.push(" ".to_string());
    out
}

/// Decodes `preds`, laid out [lines, steps, classes], into one read per line.
pub fn decode(preds: &[f32], steps: usize, classes: usize, characters: &[String]) -> Vec<Read> {
    preds
        .chunks_exact(steps * classes)
        .map(|line| {
            let best: Vec<(usize, f32)> = line.chunks_exact(classes).map(argmax).collect();
            let mut text = String::new();
            let mut kept = Vec::new();
            for (step, &(index, prob)) in best.iter().enumerate() {
                if index == 0 || (step > 0 && best[step - 1].0 == index) {
                    continue;
                }
                text.push_str(characters.get(index).map_or("", String::as_str));
                kept.push(prob);
            }
            let score = if kept.is_empty() { 0.0 } else { pairwise_sum(&kept) / kept.len() as f32 };
            (text, f64::from(score))
        })
        .collect()
}

/// numpy's argmax and max: the first index holding the largest value.
fn argmax(row: &[f32]) -> (usize, f32) {
    let mut best = (0, row[0]);
    for (index, &value) in row.iter().enumerate().skip(1) {
        if value > best.1 {
            best = (index, value);
        }
    }
    best
}

/// numpy's pairwise summation for float32 (numpy/_core/src/umath/loops_utils.h.src).
pub fn pairwise_sum(a: &[f32]) -> f32 {
    let n = a.len();
    if n < 8 {
        let mut res = -0.0f32;
        for &v in a {
            res += v;
        }
        res
    } else if n <= 128 {
        let mut r = [0f32; 8];
        r.copy_from_slice(&a[..8]);
        let mut i = 8;
        while i < n - (n % 8) {
            for j in 0..8 {
                r[j] += a[i + j];
            }
            i += 8;
        }
        let mut res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        for &v in &a[i..] {
            res += v;
        }
        res
    } else {
        let mut half = n / 2;
        half -= half % 8;
        pairwise_sum(&a[..half]) + pairwise_sum(&a[half..])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn repeats_and_blanks_drop() {
        let chars = characters(&["a".into(), "b".into()]);
        // steps: a a blank a b blank
        let rows = [[0.1, 0.8, 0.1, 0.0], [0.1, 0.6, 0.3, 0.0], [0.9, 0.05, 0.05, 0.0], [0.2, 0.7, 0.1, 0.0], [0.1, 0.1, 0.8, 0.0], [1.0, 0.0, 0.0, 0.0]];
        let preds: Vec<f32> = rows.iter().flatten().copied().collect();
        let out = decode(&preds, 6, 4, &chars);
        assert_eq!(out[0].0, "aab");
        assert!((out[0].1 - f64::from((0.8f32 + 0.7 + 0.8) / 3.0)).abs() < 1e-6);
    }

    #[test]
    fn all_blank_scores_zero() {
        let chars = characters(&["a".into()]);
        assert_eq!(decode(&[1.0, 0.0, 0.0], 1, 3, &chars), vec![(String::new(), 0.0)]);
    }
}
