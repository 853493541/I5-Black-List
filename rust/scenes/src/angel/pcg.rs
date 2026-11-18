//! numpy's default generator, `np.random.default_rng(seed)`: SeedSequence feeding PCG64, with its
//! float64 and float32 draws, so the scene's numpy noise comes out the same numbers.

const MULT: u128 = 0x2360_ED05_1FC6_5DA4_4385_DF64_9FCC_F645;

pub struct Pcg64 {
    state: u128,
    inc: u128,
    half: Option<u32>,
}

/// SeedSequence(seed).generate_state(4, uint64) for a seed under 2**32.
fn seed_words(seed: u32) -> [u64; 4] {
    const MULT_A: u32 = 0x931e_8875;
    const MULT_B: u32 = 0x58f3_8ded;
    let mut hash = 0x43b0_d7e5u32;
    let mut hashmix = |value: u32| {
        let mut v = value ^ hash;
        hash = hash.wrapping_mul(MULT_A);
        v = v.wrapping_mul(hash);
        v ^ (v >> 16)
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
    let mut hash = 0x8b51_f9ddu32;
    let mut words = [0u32; 8];
    for (i, w) in words.iter_mut().enumerate() {
        let mut v = pool[i % 4] ^ hash;
        hash = hash.wrapping_mul(MULT_B);
        v = v.wrapping_mul(hash);
        *w = v ^ (v >> 16);
    }
    std::array::from_fn(|i| u64::from(words[2 * i]) | (u64::from(words[2 * i + 1]) << 32))
}

impl Pcg64 {
    pub fn new(seed: u32) -> Self {
        let w = seed_words(seed);
        let init = (u128::from(w[0]) << 64) | u128::from(w[1]);
        let seq = (u128::from(w[2]) << 64) | u128::from(w[3]);
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
    pub fn random32(&mut self) -> f32 {
        (self.next_u32() >> 8) as f32 * (1.0 / 16_777_216.0)
    }
}

#[cfg(test)]
mod tests {
    use super::{seed_words, Pcg64};

    #[test]
    fn matches_numpy() {
        // np.random.SeedSequence(3).generate_state(4, np.uint64) and default_rng(3).random(3).
        assert_eq!(seed_words(3), [12467808127879573787, 12872254111863797241, 15240777121589344685, 1687800676579893007]);
        let mut r = Pcg64::new(3);
        assert_eq!([r.random(), r.random(), r.random()], [0.08564916714362436, 0.2368105065960997, 0.8012744652063969]);
        let mut r = Pcg64::new(7);
        assert_eq!([r.random32(), r.random32(), r.random32(), r.random32()], [0.944_904_9, 0.625_095_4, 0.684_179_9, 0.897_213_76]);
    }
}
