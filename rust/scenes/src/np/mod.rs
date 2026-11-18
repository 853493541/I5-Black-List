//! numpy's default_rng(seed), the one port every scene draws from: SeedSequence feeding PCG64 (XSL-RR
//! 128/64), and the draws the scenes make: random() as float64 and float32, uniform, and the standard
//! normal and exponential by numpy's ziggurats (`zig`, its tables as numpy ships them). The same numbers
//! as numpy for the same seed.

mod zig;

const MULT: u128 = 0x2360_ed05_1fc6_5da4_4385_df64_9fcc_f645;

pub struct Pcg64 {
    state: u128,
    inc: u128,
    /// numpy's PCG64 hands out a 64-bit draw in two 32-bit halves, low half first.
    half: Option<u32>,
}

/// numpy.random.SeedSequence(seed).generate_state(4, uint64) for a seed below 2**64 (one or two words of
/// entropy, low word first).
fn seed_state(seed: u64) -> [u64; 4] {
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
        let word = match i {
            0 => seed as u32,
            1 => (seed >> 32) as u32,
            _ => 0,
        };
        *slot = hashmix(word);
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

/// The name some scenes know it by.
pub type Rng = Pcg64;

impl Pcg64 {
    pub fn new(seed: impl Into<u64>) -> Self {
        let s = seed_state(seed.into());
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

    /// rng.standard_normal(): numpy's ziggurat.
    #[allow(clippy::excessive_precision)]
    pub fn normal(&mut self) -> f64 {
        const R: f64 = 3.654_152_885_361_008_8;
        const INV_R: f64 = 0.273_661_237_329_758_3;
        let f = |i: usize| f64::from_bits(zig::FI[i]);
        loop {
            let mut r = self.next_u64();
            let idx = (r & 0xff) as usize;
            r >>= 8;
            let sign = r & 1;
            let rabs = (r >> 1) & 0x000f_ffff_ffff_ffff;
            let mut x = rabs as f64 * f64::from_bits(zig::WI[idx]);
            if sign == 1 {
                x = -x;
            }
            if rabs < zig::KI[idx] {
                return x;
            }
            if idx == 0 {
                loop {
                    let xx = -INV_R * (-self.random()).ln_1p();
                    let yy = -(-self.random()).ln_1p();
                    if yy + yy > xx * xx {
                        return if (rabs >> 8) & 1 == 1 { -(R + xx) } else { R + xx };
                    }
                }
            }
            if (f(idx - 1) - f(idx)) * self.random() + f(idx) < (-0.5 * x * x).exp() {
                return x;
            }
        }
    }

    /// rng.standard_exponential(): numpy's ziggurat.
    pub fn exponential(&mut self) -> f64 {
        const R: f64 = 7.697_117_470_131_05;
        let f = |i: usize| f64::from_bits(zig::FE[i]);
        loop {
            let ri = self.next_u64() >> 3;
            let idx = (ri & 0xff) as usize;
            let ri = ri >> 8;
            let x = ri as f64 * f64::from_bits(zig::WE[idx]);
            if ri < zig::KE[idx] {
                return x;
            }
            if idx == 0 {
                return R - (-self.random()).ln_1p();
            }
            if (f(idx - 1) - f(idx)) * self.random() + f(idx) < (-x).exp() {
                return x;
            }
        }
    }

    /// rng.uniform(lo, hi, n).
    /// rng.uniform(lo, hi): one float64.
    pub fn uniform(&mut self, lo: f64, hi: f64) -> f64 {
        lo + (hi - lo) * self.random()
    }

    /// rng.random(n, dtype=float32).
    pub fn f32s(&mut self, n: usize) -> Vec<f32> {
        (0..n).map(|_| self.random_f32()).collect()
    }

    /// rng.random((rows, cols), dtype=float32), row by row.
    pub fn grid(&mut self, rows: usize, cols: usize) -> Vec<f32> {
        self.f32s(rows * cols)
    }

    /// rng.uniform(lo, hi, n).
    pub fn uniforms(&mut self, lo: f64, hi: f64, n: usize) -> Vec<f64> {
        (0..n).map(|_| lo + (hi - lo) * self.random()).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::Rng;

    #[test]
    #[allow(clippy::excessive_precision)]
    fn matches_numpy() {
        // numpy.random.default_rng(31).random() and .random(dtype=np.float32) twice after it.
        let mut r = Rng::new(31u64);
        assert_eq!(super::seed_state(31)[0], 11_917_523_879_341_755_967);
        assert_eq!(r.random(), 0.903_171_810_914_860_4);
        assert_eq!(r.random_f32(), 0.493_322_134_017_944_34);
        assert_eq!(r.random_f32(), 0.067_678_213_119_506_84);
        assert_eq!(r.random(), 0.672_730_814_100_364_2);
    }

    #[test]
    fn normal_and_exponential_match_numpy() {
        // default_rng(5): normal(0, 1, 3), exponential(1, 3), then the last of normal(0, 1, 2000).
        let mut r = Rng::new(5u64);
        let n: Vec<f64> = (0..3).map(|_| r.normal()).collect();
        assert_eq!(n, [-0.801_931_425_253_447_4, -1.324_358_995_628_145, -0.248_361_622_095_248_54]);
        let e: Vec<f64> = (0..3).map(|_| r.exponential()).collect();
        assert_eq!(e, [0.529_428_055_368_942_2, 0.030_152_687_278_632_78, 0.433_925_237_674_943_1]);
        let last = (0..2000).map(|_| r.normal()).last();
        assert_eq!(last, Some(-0.439_412_119_943_975_1));
    }
}

#[cfg(test)]
#[path = "golden.rs"]
mod golden;
