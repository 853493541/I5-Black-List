//! numpy's default generator, `np.random.default_rng(seed)`: SeedSequence feeding PCG64 (XSL-RR 128/64),
//! so the noise and grain of 竖琴清风 are the very numbers the Python scene draws.

const MULT: u128 = 0x2360_ed05_1fc6_5da4_4385_df64_9fcc_f645;

pub struct Pcg64 {
    state: u128,
    inc: u128,
    half: Option<u32>,
}

/// SeedSequence(seed).generate_state(4, uint64), as numpy works it out.
fn seed_state(seed: u64) -> [u64; 4] {
    const INIT_A: u32 = 0x43b0_d7e5;
    const MULT_A: u32 = 0x931e_8875;
    const INIT_B: u32 = 0x8b51_f9dd;
    const MULT_B: u32 = 0x58f3_8ded;
    let mut entropy = vec![seed as u32];
    if seed >> 32 != 0 {
        entropy.push((seed >> 32) as u32);
    }
    let mut hash_const = INIT_A;
    let mut hashmix = |value: u32| {
        let mut v = value ^ hash_const;
        hash_const = hash_const.wrapping_mul(MULT_A);
        v = v.wrapping_mul(hash_const);
        v ^ (v >> 16)
    };
    let mix = |x: u32, y: u32| {
        let r = 0xca01_f9ddu32.wrapping_mul(x).wrapping_sub(0x4973_f715u32.wrapping_mul(y));
        r ^ (r >> 16)
    };
    let mut pool = [0u32; 4];
    for (i, slot) in pool.iter_mut().enumerate() {
        *slot = hashmix(entropy.get(i).copied().unwrap_or(0));
    }
    for src in 0..4 {
        for dst in 0..4 {
            if src != dst {
                let h = hashmix(pool[src]);
                pool[dst] = mix(pool[dst], h);
            }
        }
    }
    for &e in entropy.iter().skip(4) {
        for dst in 0..4 {
            let h = hashmix(e);
            pool[dst] = mix(pool[dst], h);
        }
    }
    let mut hash_b = INIT_B;
    let mut words = [0u32; 8];
    for (i, word) in words.iter_mut().enumerate() {
        let mut v = pool[i % 4] ^ hash_b;
        hash_b = hash_b.wrapping_mul(MULT_B);
        v = v.wrapping_mul(hash_b);
        *word = v ^ (v >> 16);
    }
    let mut out = [0u64; 4];
    for (i, o) in out.iter_mut().enumerate() {
        *o = u64::from(words[2 * i]) | (u64::from(words[2 * i + 1]) << 32);
    }
    out
}

impl Pcg64 {
    pub fn new(seed: u64) -> Self {
        let s = seed_state(seed);
        let initstate = (u128::from(s[0]) << 64) | u128::from(s[1]);
        let initseq = (u128::from(s[2]) << 64) | u128::from(s[3]);
        let mut rng = Self { state: 0, inc: (initseq << 1) | 1, half: None };
        rng.step();
        rng.state = rng.state.wrapping_add(initstate);
        rng.step();
        rng
    }

    fn step(&mut self) {
        self.state = self.state.wrapping_mul(MULT).wrapping_add(self.inc);
    }

    pub fn next_u64(&mut self) -> u64 {
        self.step();
        let rot = (self.state >> 122) as u32;
        let xored = ((self.state >> 64) as u64) ^ (self.state as u64);
        xored.rotate_right(rot)
    }

    pub fn next_u32(&mut self) -> u32 {
        if let Some(h) = self.half.take() {
            return h;
        }
        let v = self.next_u64();
        self.half = Some((v >> 32) as u32);
        v as u32
    }

    /// `rng.random(dtype=np.float32)`.
    pub fn f32(&mut self) -> f32 {
        (self.next_u32() >> 8) as f32 * (1.0 / 16_777_216.0)
    }

    /// `rng.random()` (float64).
    pub fn f64(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / 9_007_199_254_740_992.0)
    }

    pub fn f32s(&mut self, n: usize) -> Vec<f32> {
        (0..n).map(|_| self.f32()).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::Pcg64;

    #[test]
    fn matches_numpy() {
        // np.random.default_rng(5).random(3) and np.random.default_rng(0).random(2, dtype=np.float32)
        let mut a = Pcg64::new(5);
        let got: Vec<f64> = (0..3).map(|_| a.f64()).collect();
        let want = [0.805_002_923_745_380_2, 0.807_940_789_736_493_7, 0.515_325_561_042_142];
        for (g, w) in got.iter().zip(want) {
            assert!((g - w).abs() < 1e-15, "{got:?}");
        }
        let mut b = Pcg64::new(0);
        let got: Vec<f32> = (0..2).map(|_| b.f32()).collect();
        assert!((Pcg64::new((1 << 33) + 7).f64() - 0.277_970_282_193_581).abs() < 1e-15);
        assert!((got[0] - 0.850_624_2).abs() < 1e-6 && (got[1] - 0.636_961_6).abs() < 1e-6, "{got:?}");
    }
}
