//! numpy's default_rng: SeedSequence, PCG64 (XSL-RR), and the draws the scene uses (random as
//! float32, uniform, normal and exponential by numpy's ziggurats), so the noise and the sparks come
//! out of the same seeds as the Python scene's.

const MULT: u128 = (0x2360_ed05_1fc6_5da4 << 64) | 0x4385_df64_9fcc_f645;

pub struct Rng {
    state: u128,
    inc: u128,
    half: Option<u32>,
}

fn hashmix(value: u32, hash: &mut u32) -> u32 {
    let mut v = value ^ *hash;
    *hash = hash.wrapping_mul(0x931e_8875);
    v = v.wrapping_mul(*hash);
    v ^ (v >> 16)
}

fn mixed(x: u32, y: u32) -> u32 {
    let r = 0xca01_f9dd_u32.wrapping_mul(x).wrapping_sub(0x4973_f715_u32.wrapping_mul(y));
    r ^ (r >> 16)
}

/// SeedSequence(seed).generate_state(8, uint32) for a seed under 2**32.
fn seed_words(seed: u32) -> [u32; 8] {
    let mut pool = [0u32; 4];
    let mut hash = 0x43b0_d7e5;
    for (i, slot) in pool.iter_mut().enumerate() {
        *slot = hashmix(if i == 0 { seed } else { 0 }, &mut hash);
    }
    for src in 0..4 {
        for dst in 0..4 {
            if src != dst {
                let h = hashmix(pool[src], &mut hash);
                pool[dst] = mixed(pool[dst], h);
            }
        }
    }
    let mut hash = 0x8b51_f9dd_u32;
    std::array::from_fn(|i| {
        let mut v = pool[i % 4] ^ hash;
        hash = hash.wrapping_mul(0x58f3_8ded);
        v = v.wrapping_mul(hash);
        v ^ (v >> 16)
    })
}

struct Zig {
    k: [u64; 256],
    w: [f64; 256],
    f: [f64; 256],
}

/// The ziggurat tables numpy ships, worked out from their constants (Marsaglia and Tsang).
fn ziggurat(r: f64, v: f64, bits: i32, normal: bool) -> Zig {
    let f = |x: f64| if normal { (-0.5 * x * x).exp() } else { (-x).exp() };
    let m = 2f64.powi(bits);
    let (mut d, mut t) = (r, r);
    let q = v / f(d);
    let mut z = Zig { k: [0; 256], w: [0.0; 256], f: [0.0; 256] };
    z.k[0] = (d / q * m) as u64;
    z.w[0] = q / m;
    z.w[255] = d / m;
    z.f[0] = 1.0;
    z.f[255] = f(d);
    for i in (1..255).rev() {
        d = if normal { (-2.0 * (v / d + f(d)).ln()).sqrt() } else { -(v / d + f(d)).ln() };
        z.k[i + 1] = (d / t * m) as u64;
        t = d;
        z.f[i] = f(d);
        z.w[i] = d / m;
    }
    z
}

const NOR_R: f64 = 3.654_152_885_361_008_8;
const EXP_R: f64 = 7.697_117_470_131_05;

thread_local! {
    static NOR: Zig = ziggurat(NOR_R, 0.004_928_673_233_99, 52, true);
    static EXP: Zig = ziggurat(EXP_R, 0.003_949_659_822_581_557_2, 53, false);
}

impl Rng {
    /// np.random.default_rng(seed).
    pub fn new(seed: u32) -> Self {
        let w = seed_words(seed);
        let word = |k: usize| u128::from(w[2 * k]) | (u128::from(w[2 * k + 1]) << 32);
        let (init, seq) = ((word(0) << 64) | word(1), (word(2) << 64) | word(3));
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
        (((s >> 64) as u64) ^ (s as u64)).rotate_right((s >> 122) as u32)
    }

    fn next_u32(&mut self) -> u32 {
        if let Some(h) = self.half.take() {
            return h;
        }
        let n = self.next_u64();
        self.half = Some((n >> 32) as u32);
        n as u32
    }

    pub fn double(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / 9_007_199_254_740_992.0)
    }

    /// rng.random(dtype=np.float32).
    pub fn float(&mut self) -> f32 {
        (self.next_u32() >> 8) as f32 * (1.0 / 16_777_216.0)
    }

    pub fn uniform(&mut self, lo: f64, hi: f64) -> f64 {
        lo + (hi - lo) * self.double()
    }

    pub fn normal(&mut self, mu: f64, sigma: f64) -> f64 {
        mu + sigma * self.std_normal()
    }

    pub fn exponential(&mut self, scale: f64) -> f64 {
        scale * self.std_exp()
    }

    fn std_normal(&mut self) -> f64 {
        loop {
            let mut r = self.next_u64();
            let idx = (r & 0xff) as usize;
            r >>= 8;
            let sign = r & 1;
            let rabs = (r >> 1) & 0x000f_ffff_ffff_ffff;
            let (k, w, fi, fo) = NOR.with(|z| (z.k[idx], z.w[idx], z.f[idx], if idx > 0 { z.f[idx - 1] } else { 0.0 }));
            let mut x = rabs as f64 * w;
            if sign == 1 {
                x = -x;
            }
            if rabs < k {
                return x;
            }
            if idx == 0 {
                loop {
                    let xx = -(1.0 / NOR_R) * (-self.double()).ln_1p();
                    let yy = -(-self.double()).ln_1p();
                    if yy + yy > xx * xx {
                        return if (rabs >> 8) & 1 == 1 { -(NOR_R + xx) } else { NOR_R + xx };
                    }
                }
            }
            if (fo - fi) * self.double() + fi < (-0.5 * x * x).exp() {
                return x;
            }
        }
    }

    fn std_exp(&mut self) -> f64 {
        loop {
            let mut r = self.next_u64() >> 3;
            let idx = (r & 0xff) as usize;
            r >>= 8;
            let (k, w, fi, fo) = EXP.with(|z| (z.k[idx], z.w[idx], z.f[idx], if idx > 0 { z.f[idx - 1] } else { 0.0 }));
            let x = r as f64 * w;
            if r < k {
                return x;
            }
            if idx == 0 {
                return EXP_R - (-self.double()).ln_1p();
            }
            if (fo - fi) * self.double() + fi < (-x).exp() {
                return x;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::Rng;

    /// np.random.default_rng(5): .random(3, dtype=np.float32), then .normal(0, 1, 3) and
    /// .exponential(1.0, 3) on a fresh default_rng(5) each.
    #[test]
    fn matches_numpy() {
        let mut r = Rng::new(5);
        let f: Vec<f32> = (0..3).map(|_| r.float()).collect();
        assert_eq!(f, FLOATS);
        let mut r = Rng::new(5);
        let n: Vec<f64> = (0..3).map(|_| r.normal(0.0, 1.0)).collect();
        assert_eq!(n, NORMALS);
        let mut r = Rng::new(5);
        let e: Vec<f64> = (0..3).map(|_| r.exponential(1.0)).collect();
        assert_eq!(e, EXPS);
        // 100,000 draws from default_rng(1) reach the ziggurats' tails and wedges: their sums.
        let mut r = Rng::new(1);
        let n: f64 = (0..100_000).map(|_| r.normal(0.0, 1.0)).sum();
        assert!((n + 459.057_204_287_578_43).abs() < 1e-7, "{n}");
        let mut r = Rng::new(1);
        let e: f64 = (0..100_000).map(|_| r.exponential(1.0)).sum();
        assert!((e - 99_599.582_674_443_62).abs() < 1e-6, "{e}");
    }

    const FLOATS: [f32; 3] = [0.670_790_02, 0.805_002_87, 0.022_653_162];
    const NORMALS: [f64; 3] = [-0.801_931_425_253_447_4, -1.324_358_995_628_145, -0.248_361_622_095_248_54];
    const EXPS: [f64; 3] = [1.986_669_976_012_444_2, 0.750_191_431_996_990_2, 1.301_353_901_598_428];
}
