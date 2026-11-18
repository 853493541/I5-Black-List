//! numpy's `np.random.default_rng(seed)`: a SeedSequence feeding PCG64 (XSL-RR 128/64), and its
//! float32 draws, so the noise the Python scene seeds comes out the same here.

const INIT_A: u32 = 0x43b0_d7e5;
const MULT_A: u32 = 0x931e_8875;
const INIT_B: u32 = 0x8b51_f9dd;
const MULT_B: u32 = 0x58f3_8ded;
const MIX_MULT_L: u32 = 0xca01_f9dd;
const MIX_MULT_R: u32 = 0x4973_f715;
const MULT: u128 = 0x2360_ed05_1fc6_5da4_4385_df64_9fcc_f645;

fn hashmix(value: u32, hash: &mut u32) -> u32 {
    let mut v = value ^ *hash;
    *hash = hash.wrapping_mul(MULT_A);
    v = v.wrapping_mul(*hash);
    v ^ (v >> 16)
}

fn mix(x: u32, y: u32) -> u32 {
    let r = MIX_MULT_L.wrapping_mul(x).wrapping_sub(MIX_MULT_R.wrapping_mul(y));
    r ^ (r >> 16)
}

/// SeedSequence(seed).generate_state(4, uint64) for a seed below 2**32.
fn seed_state(seed: u32) -> [u64; 4] {
    let mut pool = [0u32; 4];
    let mut hash = INIT_A;
    for (i, slot) in pool.iter_mut().enumerate() {
        *slot = hashmix(if i == 0 { seed } else { 0 }, &mut hash);
    }
    for src in 0..4 {
        for dst in 0..4 {
            if src != dst {
                let h = hashmix(pool[src], &mut hash);
                pool[dst] = mix(pool[dst], h);
            }
        }
    }
    let mut hash = INIT_B;
    let mut words = [0u32; 8];
    for (i, w) in words.iter_mut().enumerate() {
        let mut v = pool[i % 4] ^ hash;
        hash = hash.wrapping_mul(MULT_B);
        v = v.wrapping_mul(hash);
        *w = v ^ (v >> 16);
    }
    std::array::from_fn(|i| u64::from(words[2 * i]) | (u64::from(words[2 * i + 1]) << 32))
}

pub struct Pcg64 {
    state: u128,
    inc: u128,
    half: Option<u32>,
}

impl Pcg64 {
    /// np.random.default_rng(seed).
    pub fn new(seed: u32) -> Self {
        let s = seed_state(seed);
        let init = (u128::from(s[0]) << 64) | u128::from(s[1]);
        let seq = (u128::from(s[2]) << 64) | u128::from(s[3]);
        let mut rng = Self { state: 0, inc: (seq << 1) | 1, half: None };
        rng.step();
        rng.state = rng.state.wrapping_add(init);
        rng.step();
        rng
    }

    fn step(&mut self) {
        self.state = self.state.wrapping_mul(MULT).wrapping_add(self.inc);
    }

    pub fn next_u64(&mut self) -> u64 {
        self.step();
        let s = self.state;
        ((s >> 64) as u64 ^ s as u64).rotate_right((s >> 122) as u32)
    }

    fn next_u32(&mut self) -> u32 {
        if let Some(v) = self.half.take() {
            return v;
        }
        let v = self.next_u64();
        self.half = Some((v >> 32) as u32);
        v as u32
    }

    /// rng.random(dtype=np.float32).
    pub fn f32(&mut self) -> f32 {
        (self.next_u32() >> 8) as f32 * (1.0 / 16_777_216.0)
    }

    /// rng.random() (float64).
    pub fn f64(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / 9_007_199_254_740_992.0)
    }
}

#[cfg(test)]
mod tests {
    use super::Pcg64;

    #[test]
    fn matches_numpy_default_rng() {
        // np.random.default_rng(19).random(4, dtype=np.float32), then one more.
        let mut r = Pcg64::new(19);
        let got: Vec<f32> = (0..5).map(|_| r.f32()).collect();
        assert_eq!(got, [0.589_040_1, 0.420_378_74, 0.356_689_57, 0.925_869_3, 0.379_037_62]);
        // np.random.default_rng(7).random(3).
        let mut r = Pcg64::new(7);
        let got: Vec<f64> = (0..3).map(|_| r.f64()).collect();
        assert_eq!(got, [0.625_095_466_604_667, 0.897_213_800_969_575_5, 0.775_685_690_245_193_5]);
    }
}
