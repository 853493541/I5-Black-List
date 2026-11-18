//! numpy's default_rng(seed): SeedSequence feeding PCG64 (XSL-RR 128/64), with the draws the neon
//! scene makes: random() as float64 and float32, and uniform. The same numbers as numpy for the same seed.

const MULT: u128 = 0x2360_ed05_1fc6_5da4_4385_df64_9fcc_f645;

pub struct Rng {
    state: u128,
    inc: u128,
    /// numpy's PCG64 hands out a 64-bit draw in two 32-bit halves, low half first.
    half: Option<u32>,
}

/// numpy.random.SeedSequence(seed).generate_state(4, uint64) for a seed below 2**32.
fn seed_state(seed: u32) -> [u64; 4] {
    const INIT_A: u32 = 0x43b0_d7e5;
    const MULT_A: u32 = 0x931e_8875;
    const INIT_B: u32 = 0x8b51_f9dd;
    const MULT_B: u32 = 0x58f3_8ded;
    let mut hash_const = INIT_A;
    let mut hashmix = |mut value: u32| {
        value ^= hash_const;
        hash_const = hash_const.wrapping_mul(MULT_A);
        value = value.wrapping_mul(hash_const);
        value ^ (value >> 16)
    };
    let mix = |x: u32, y: u32| {
        let r = 0xca01_f9ddu32.wrapping_mul(x).wrapping_sub(0x4973_f715u32.wrapping_mul(y));
        r ^ (r >> 16)
    };
    let mut pool = [0u32; 4];
    for (i, slot) in pool.iter_mut().enumerate() {
        *slot = hashmix(if i == 0 { seed } else { 0 });
    }
    for src in 0..4 {
        for dst in 0..4 {
            if src != dst {
                let h = hashmix(pool[src]);
                pool[dst] = mix(pool[dst], h);
            }
        }
    }
    let mut hash_const = INIT_B;
    let words: Vec<u32> = (0..8)
        .map(|i| {
            let mut v = pool[i % 4] ^ hash_const;
            hash_const = hash_const.wrapping_mul(MULT_B);
            v = v.wrapping_mul(hash_const);
            v ^ (v >> 16)
        })
        .collect();
    std::array::from_fn(|i| u64::from(words[2 * i]) | (u64::from(words[2 * i + 1]) << 32))
}

impl Rng {
    pub fn new(seed: u32) -> Self {
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
        let s = self.state;
        let xored = ((s >> 64) as u64) ^ (s as u64);
        xored.rotate_right((s >> 122) as u32)
    }

    pub fn next_u32(&mut self) -> u32 {
        if let Some(h) = self.half.take() {
            return h;
        }
        let v = self.next_u64();
        self.half = Some((v >> 32) as u32);
        v as u32
    }

    /// rng.random(): a float64 in [0, 1).
    pub fn random(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / 9_007_199_254_740_992.0)
    }

    /// rng.random(dtype=np.float32).
    pub fn random_f32(&mut self) -> f32 {
        (self.next_u32() >> 8) as f32 * (1.0 / 16_777_216.0)
    }

    /// rng.uniform(lo, hi, n).
    pub fn uniform(&mut self, lo: f64, hi: f64, n: usize) -> Vec<f64> {
        (0..n).map(|_| lo + (hi - lo) * self.random()).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::Rng;

    #[test]
    fn matches_numpy() {
        // numpy.random.default_rng(31).random() and .random(dtype=np.float32) twice after it.
        let mut r = Rng::new(31);
        assert_eq!(super::seed_state(31)[0], 11_917_523_879_341_755_967);
        assert_eq!(r.random(), 0.903_171_810_914_860_4);
        assert_eq!(r.random_f32(), 0.493_322_134_017_944_34);
        assert_eq!(r.random_f32(), 0.067_678_213_119_506_84);
        assert_eq!(r.random(), 0.672_730_814_100_364_2);
    }
}
