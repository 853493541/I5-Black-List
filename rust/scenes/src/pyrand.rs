//! Python's `random.Random` (MT19937, seeded from an int), so a scene lays out its stars exactly as
//! the Python scene with the same seed does.

const N: usize = 624;
const M: usize = 397;

pub struct PyRandom {
    mt: [u32; N],
    index: usize,
    gauss_next: Option<f64>,
}

impl PyRandom {
    /// `random.Random(seed)` for a seed below 2**32.
    pub fn new(seed: u32) -> Self {
        let mut r = Self { mt: [0; N], index: N, gauss_next: None };
        r.init_by_array(&[seed]);
        r
    }

    fn init_genrand(&mut self, s: u32) {
        self.mt[0] = s;
        for i in 1..N {
            let prev = self.mt[i - 1];
            self.mt[i] = 1_812_433_253u32.wrapping_mul(prev ^ (prev >> 30)).wrapping_add(i as u32);
        }
        self.index = N;
    }

    fn init_by_array(&mut self, key: &[u32]) {
        self.init_genrand(19_650_218);
        let (mut i, mut j) = (1usize, 0usize);
        for _ in 0..N.max(key.len()) {
            let prev = self.mt[i - 1];
            self.mt[i] = (self.mt[i] ^ (prev ^ (prev >> 30)).wrapping_mul(1_664_525)).wrapping_add(key[j]).wrapping_add(j as u32);
            i += 1;
            j += 1;
            if i >= N {
                self.mt[0] = self.mt[N - 1];
                i = 1;
            }
            if j >= key.len() {
                j = 0;
            }
        }
        for _ in 0..N - 1 {
            let prev = self.mt[i - 1];
            self.mt[i] = (self.mt[i] ^ (prev ^ (prev >> 30)).wrapping_mul(1_566_083_941)).wrapping_sub(i as u32);
            i += 1;
            if i >= N {
                self.mt[0] = self.mt[N - 1];
                i = 1;
            }
        }
        self.mt[0] = 0x8000_0000;
    }

    fn twist(&mut self) {
        for i in 0..N {
            let y = (self.mt[i] & 0x8000_0000) | (self.mt[(i + 1) % N] & 0x7fff_ffff);
            let mut v = self.mt[(i + M) % N] ^ (y >> 1);
            if y & 1 != 0 {
                v ^= 0x9908_b0df;
            }
            self.mt[i] = v;
        }
        self.index = 0;
    }

    pub fn next_u32(&mut self) -> u32 {
        if self.index >= N {
            self.twist();
        }
        let mut y = self.mt[self.index];
        self.index += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c_5680;
        y ^= (y << 15) & 0xefc6_0000;
        y ^ (y >> 18)
    }

    /// `random()`: 53 bits in [0, 1).
    pub fn random(&mut self) -> f64 {
        let a = f64::from(self.next_u32() >> 5);
        let b = f64::from(self.next_u32() >> 6);
        (a * 67_108_864.0 + b) / 9_007_199_254_740_992.0
    }

    pub fn uniform(&mut self, a: f64, b: f64) -> f64 {
        a + (b - a) * self.random()
    }

    /// `_randbelow(n)` for n below 2**32, as `choice` uses it.
    pub fn below(&mut self, n: usize) -> usize {
        let k = usize::BITS - n.leading_zeros();
        loop {
            let r = (self.next_u32() >> (32 - k)) as usize;
            if r < n {
                return r;
            }
        }
    }

    pub fn choice<T: Copy>(&mut self, items: &[T]) -> T {
        items[self.below(items.len())]
    }

    pub fn gauss(&mut self, mu: f64, sigma: f64) -> f64 {
        let z = match self.gauss_next.take() {
            Some(z) => z,
            None => {
                let x2pi = self.random() * std::f64::consts::TAU;
                let g2rad = (-2.0 * (1.0 - self.random()).ln()).sqrt();
                self.gauss_next = Some(x2pi.sin() * g2rad);
                x2pi.cos() * g2rad
            }
        };
        mu + z * sigma
    }
}

#[cfg(test)]
mod tests {
    use super::PyRandom;

    #[test]
    fn matches_python() {
        // python3 -c "import random; r=random.Random(31); print([r.random() for _ in range(3)], r.uniform(2,5),
        //   r.choice('abcd'), r.gauss(0,1), r.gauss(0,1), r.getrandbits(32))"
        let mut r = PyRandom::new(31);
        assert_eq!(r.random(), 0.012_278_247_397_975_45);
        assert_eq!(r.random(), 0.112_398_861_080_235_78);
        assert_eq!(r.random(), 0.392_837_361_550_742_56);
        assert_eq!(r.uniform(2.0, 5.0), 4.051_592_820_359_801);
        assert_eq!(r.choice(&['a', 'b', 'c', 'd']), 'b');
        assert!((r.gauss(0.0, 1.0) - 1.177_935_660_534_487_5).abs() < 1e-12);
        assert!((r.gauss(0.0, 1.0) + 0.380_546_962_249_807_7).abs() < 1e-12);
        assert_eq!(r.next_u32(), 3_055_913_604);
    }
}
