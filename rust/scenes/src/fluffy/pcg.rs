//! numpy's default_rng(seed): SeedSequence seeding a PCG64, and `random(dtype=float32)`, so the
//! scene's noise, paper fibers and fur strands come out exactly as numpy draws them.

const INIT_A: u32 = 0x43b0_d7e5;
const MULT_A: u32 = 0x931e_8875;
const INIT_B: u32 = 0x8b51_f9dd;
const MULT_B: u32 = 0x58f3_8ded;
const MIX_MULT_L: u32 = 0xca01_f9dd;
const MIX_MULT_R: u32 = 0x4973_f715;
const PCG_MULT: u128 = 0x2360_ed05_1fc6_5da4_4385_df64_9fcc_f645;

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

/// SeedSequence(seed).generate_state(4, uint64) for a seed below 2^32.
fn seed_state(seed: u32) -> [u64; 4] {
    let entropy = [seed];
    let mut pool = [0u32; 4];
    let mut hash = INIT_A;
    for (i, slot) in pool.iter_mut().enumerate() {
        *slot = hashmix(entropy.get(i).copied().unwrap_or(0), &mut hash);
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
    let words: Vec<u32> = (0..8)
        .map(|i| {
            let mut v = pool[i % 4] ^ hash;
            hash = hash.wrapping_mul(MULT_B);
            v = v.wrapping_mul(hash);
            v ^ (v >> 16)
        })
        .collect();
    std::array::from_fn(|i| u64::from(words[2 * i]) | (u64::from(words[2 * i + 1]) << 32))
}

pub struct Rng {
    state: u128,
    inc: u128,
    half: Option<u32>,
}

impl Rng {
    /// np.random.default_rng(seed).
    pub fn new(seed: u32) -> Self {
        let v = seed_state(seed);
        let init = (u128::from(v[0]) << 64) | u128::from(v[1]);
        let seq = (u128::from(v[2]) << 64) | u128::from(v[3]);
        let mut rng = Self { state: 0, inc: (seq << 1) | 1, half: None };
        rng.step();
        rng.state = rng.state.wrapping_add(init);
        rng.step();
        rng
    }

    fn step(&mut self) {
        self.state = self.state.wrapping_mul(PCG_MULT).wrapping_add(self.inc);
    }

    pub fn next_u64(&mut self) -> u64 {
        self.step();
        let s = self.state;
        (((s >> 64) as u64) ^ (s as u64)).rotate_right((s >> 122) as u32)
    }

    fn next_u32(&mut self) -> u32 {
        if let Some(v) = self.half.take() {
            return v;
        }
        let v = self.next_u64();
        self.half = Some((v >> 32) as u32);
        v as u32
    }

    /// One `random(dtype=np.float32)` draw.
    pub fn f32(&mut self) -> f32 {
        (self.next_u32() >> 8) as f32 * (1.0 / 16_777_216.0)
    }

    /// `random((rows, cols), dtype=np.float32)`, row by row.
    pub fn grid(&mut self, rows: usize, cols: usize) -> Vec<f32> {
        (0..rows * cols).map(|_| self.f32()).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::Rng;

    #[test]
    fn draws_what_numpy_draws() {
        // np.random.default_rng(7).random(3, dtype=np.float32) and default_rng(21).bit_generator.random_raw()
        let mut r = Rng::new(7);
        let got: Vec<f32> = (0..3).map(|_| r.f32()).collect();
        assert_eq!(got, [0.944_904_9_f32, 0.625_095_4, 0.684_179_9]);
        assert_eq!(Rng::new(21).next_u64(), 14_409_076_252_388_976_754);
    }
}
