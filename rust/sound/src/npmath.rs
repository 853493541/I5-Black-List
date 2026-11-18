//! The few numpy routines the Python sound code leans on, written to give numpy's own results: its pairwise sum
//! (np.sum, np.mean), np.interp, np.linspace and np.rint, so the samples written match the Python app's.

/// numpy's pairwise summation of float64 (`pairwise_sum_DOUBLE`), as np.sum and np.mean add up an array.
pub fn pairwise_sum(a: &[f64]) -> f64 {
    const BLOCK: usize = 128;
    let n = a.len();
    if n < 8 {
        return a.iter().fold(0.0, |sum, v| sum + v);
    }
    if n <= BLOCK {
        let mut r = [0.0f64; 8];
        r.copy_from_slice(&a[..8]);
        let mut i = 8;
        while i < n - n % 8 {
            for (j, acc) in r.iter_mut().enumerate() {
                *acc += a[i + j];
            }
            i += 8;
        }
        let mut res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        for v in &a[i..] {
            res += v;
        }
        return res;
    }
    let mut half = n / 2;
    half -= half % 8;
    pairwise_sum(&a[..half]) + pairwise_sum(&a[half..])
}

/// np.mean of float64.
pub fn mean(a: &[f64]) -> f64 {
    if a.is_empty() {
        return f64::NAN;
    }
    pairwise_sum(a) / a.len() as f64
}

/// np.interp(x, xp, fp) for increasing xp: fp's ends past xp's ends, straight lines between.
pub fn interp(x: f64, xp: &[f64], fp: &[f64]) -> f64 {
    let last = xp.len() - 1;
    if x <= xp[0] {
        return fp[0];
    }
    if x >= xp[last] {
        return fp[last];
    }
    // The last j with xp[j] <= x.
    let j = xp.partition_point(|&v| v <= x) - 1;
    if xp[j] == x {
        return fp[j];
    }
    let slope = (fp[j + 1] - fp[j]) / (xp[j + 1] - xp[j]);
    slope * (x - xp[j]) + fp[j]
}

/// np.interp where xp is 0, 1, 2, ... (fp's index): no search needed.
pub fn interp_unit(x: f64, fp: &[f64]) -> f64 {
    let last = fp.len() - 1;
    if x <= 0.0 {
        return fp[0];
    }
    if x >= last as f64 {
        return fp[last];
    }
    let j = x.floor() as usize;
    if j as f64 == x {
        return fp[j];
    }
    (fp[j + 1] - fp[j]) * (x - j as f64) + fp[j]
}

/// np.linspace(start, stop, num, endpoint).
pub fn linspace(start: f64, stop: f64, num: usize, endpoint: bool) -> Vec<f64> {
    if num == 0 {
        return Vec::new();
    }
    let div = if endpoint { num - 1 } else { num };
    let delta = stop - start;
    let mut out: Vec<f64> = if div == 0 {
        (0..num).map(|i| i as f64 * delta + start).collect()
    } else {
        let step = delta / div as f64;
        if step == 0.0 {
            (0..num).map(|i| i as f64 / div as f64 * delta + start).collect()
        } else {
            (0..num).map(|i| i as f64 * step + start).collect()
        }
    };
    if endpoint && num > 1 {
        out[num - 1] = stop;
    }
    out
}

/// np.clip(np.rint(v), -32768, 32767) as int16.
pub fn to_i16(v: f64) -> i16 {
    v.round_ties_even().clamp(-32768.0, 32767.0) as i16
}

/// The same in float32, as numpy does it on a float32 array.
pub fn to_i16_f32(v: f32) -> i16 {
    v.round_ties_even().clamp(-32768.0, 32767.0) as i16
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn linspace_matches_numpy_ends() {
        assert_eq!(linspace(1.0, 0.0, 5, true), vec![1.0, 0.75, 0.5, 0.25, 0.0]);
        assert_eq!(linspace(0.0, 1.0, 4, false), vec![0.0, 0.25, 0.5, 0.75]);
        assert_eq!(linspace(0.0, 1.0, 1, true), vec![0.0]);
    }

    #[test]
    fn interp_holds_its_ends() {
        let xp = [0.5, 1.5, 2.5];
        let fp = [1.0, 0.0, 1.0];
        assert_eq!(interp(0.0, &xp, &fp), 1.0);
        assert_eq!(interp(1.0, &xp, &fp), 0.5);
        assert_eq!(interp(3.0, &xp, &fp), 1.0);
        assert_eq!(interp_unit(1.25, &[0.0, 4.0, 8.0]), 5.0);
    }

    #[test]
    fn rint_rounds_half_to_even() {
        assert_eq!(to_i16(2.5), 2);
        assert_eq!(to_i16(-2.5), -2);
        assert_eq!(to_i16(40000.0), 32767);
        assert_eq!(pairwise_sum(&[1.0; 1000]), 1000.0);
    }
}
