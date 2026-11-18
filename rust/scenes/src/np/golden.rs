//! numpy's own numbers, as the six per-scene ports checked them before they were folded into this one.

use super::{seed_state, Pcg64};

#[test]
fn seeds_and_raw_draws() {
    // np.random.SeedSequence(3).generate_state(4, np.uint64); default_rng(21).bit_generator.random_raw().
    assert_eq!(seed_state(3), [12467808127879573787, 12872254111863797241, 15240777121589344685, 1687800676579893007]);
    assert_eq!(Pcg64::new(21u64).next_u64(), 14_409_076_252_388_976_754);
    // A seed past 2**32 is two words of entropy: default_rng(2**33 + 7).random().
    assert!((Pcg64::new((1u64 << 33) + 7).random() - 0.277_970_282_193_581).abs() < 1e-15);
}

#[test]
fn float64_and_float32() {
    let mut r = Pcg64::new(3u64);
    assert_eq!([r.random(), r.random(), r.random()], [0.08564916714362436, 0.2368105065960997, 0.8012744652063969]);
    let mut r = Pcg64::new(7u64);
    assert_eq!([0; 3].map(|_| r.random()), [0.625_095_466_604_667, 0.897_213_800_969_575_5, 0.775_685_690_245_193_5]);
    let mut r = Pcg64::new(7u64);
    assert_eq!([0; 4].map(|_| r.random_f32()), [0.944_904_9, 0.625_095_4, 0.684_179_9, 0.897_213_76]);
    let mut r = Pcg64::new(19u64);
    assert_eq!(r.f32s(5), [0.589_040_1, 0.420_378_74, 0.356_689_57, 0.925_869_3, 0.379_037_62]);
    let mut r = Pcg64::new(5u64);
    let want = [0.805_002_923_745_380_2, 0.807_940_789_736_493_7, 0.515_325_561_042_142];
    assert!([0; 3].map(|_| r.random()).iter().zip(want).all(|(g, w)| (g - w).abs() < 1e-15));
    let got = Pcg64::new(5u64).f32s(3);
    assert_eq!(got.iter().map(|&v| f64::from(v)).collect::<Vec<_>>(), [0.670_790_016_651_153_6, 0.805_002_868_175_506_6, 0.022_653_162_479_400_635]);
}

#[test]
fn normal_and_exponential() {
    // default_rng(5).normal(0, 1, 3) and .exponential(1.0, 3), each on a fresh generator; numpy's own
    // tables, so exact to the last bits or nearly.
    let mut r = Pcg64::new(5u64);
    let want = [-0.801_931_425_253_447_4, -1.324_358_995_628_145, -0.248_361_622_095_248_54];
    assert!(want.iter().all(|w| (r.normal() - w).abs() < 1e-12));
    let mut r = Pcg64::new(5u64);
    let want = [1.986_669_976_012_444_2, 0.750_191_431_996_990_2, 1.301_353_901_598_428];
    assert!(want.iter().all(|w| (r.exponential() - w).abs() < 1e-12));
    // 100,000 draws from default_rng(1) reach the ziggurats' tails and wedges: their sums.
    let mut r = Pcg64::new(1u64);
    let n: f64 = (0..100_000).map(|_| r.normal()).sum();
    assert!((n + 459.057_204_287_578_43).abs() < 1e-6, "{n}");
    let mut r = Pcg64::new(1u64);
    let e: f64 = (0..100_000).map(|_| r.exponential()).sum();
    assert!((e - 99_599.582_674_443_62).abs() < 1e-5, "{e}");
}
