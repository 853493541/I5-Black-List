//! Runs every network run recorded by tools/size/ort_tract_dump.py on tract and compares it with ONNX Runtime's output.
//!
//!     ort-tract-probe <models dir> <cases dir>
//!
//! Per model: whether it loads, the runs, the largest output gap, the det map's pixels that cross the 0.3 threshold
//! differently, the rec time steps whose best character differs (a different text after CTC), and the seconds on
//! both engines. Counts only.

#[cfg(feature = "tract")]
mod probe {
    use std::collections::BTreeMap;
    use std::path::Path;
    use std::time::Instant;

    use tract_onnx::prelude::*;

    const MODELS: [&str; 3] = ["PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec", "PP-OCRv6_medium_rec"];

    #[derive(Default)]
    struct Stats {
        runs: usize,
        gap: f32,
        det_flips: usize,
        steps: usize,
        step_diff: usize,
        tract_s: f64,
        ort_s: f64,
        compile_s: f64,
    }

    fn floats(path: &Path) -> Vec<f32> {
        std::fs::read(path).unwrap().chunks_exact(4).map(|b| f32::from_le_bytes([b[0], b[1], b[2], b[3]])).collect()
    }

    fn argmax(row: &[f32]) -> usize {
        row.iter().enumerate().fold((0, f32::MIN), |best, (i, &v)| if v > best.1 { (i, v) } else { best }).0
    }

    type Plan = std::sync::Arc<TypedRunnableModel>;

    /// A plan for this model: one with symbolic shapes when tract can make it, else one per input shape.
    fn plan(models: &Path, name: &str, shape: Option<&[usize]>) -> TractResult<Plan> {
        let mut model = tract_onnx::onnx().model_for_path(models.join(name).join("inference.onnx"))?;
        if let Some(shape) = shape {
            model = model.with_input_fact(0, f32::fact(shape).into())?;
        }
        model.into_optimized()?.into_runnable()
    }

    pub fn main(models: &Path, cases: &Path) -> TractResult<()> {
        let mut symbolic = BTreeMap::new();
        // TRACT_PER_SHAPE=1: a plan per input shape for every model (tract optimizes best with concrete shapes).
        let per_shape_only = std::env::var("TRACT_PER_SHAPE").is_ok_and(|v| v == "1");
        for name in MODELS.iter().copied().filter(|_| !per_shape_only) {
            let started = Instant::now();
            match plan(models, name, None) {
                Ok(p) => {
                    println!("{name}: loads with symbolic shapes in {:.2} s", started.elapsed().as_secs_f64());
                    symbolic.insert(name.to_string(), p);
                }
                Err(err) => println!("{name}: no symbolic plan ({err}); one plan per input shape"),
            }
        }
        let mut per_shape: BTreeMap<(String, Vec<usize>), Plan> = BTreeMap::new();
        let mut stats: BTreeMap<String, Stats> = BTreeMap::new();
        let mut ids: Vec<usize> = std::fs::read_dir(cases)?
            .filter_map(|e| e.ok()?.file_name().to_str()?.strip_suffix(".json")?.parse().ok())
            .collect();
        ids.sort();
        for id in ids {
            let meta: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(cases.join(format!("{id}.json")))?)?;
            let model = meta["model"].as_str().unwrap().to_string();
            let dims = |key: &str| meta[key].as_array().unwrap().iter().map(|v| v.as_u64().unwrap() as usize).collect::<Vec<_>>();
            let (in_shape, out_shape) = (dims("input"), dims("output"));
            let s = stats.entry(model.clone()).or_default();
            let runnable = match symbolic.get(&model) {
                Some(p) => p.clone(),
                None => {
                    let key = (model.clone(), in_shape.clone());
                    if !per_shape.contains_key(&key) {
                        let started = Instant::now();
                        per_shape.insert(key.clone(), plan(models, &model, Some(&in_shape))?);
                        s.compile_s += started.elapsed().as_secs_f64();
                    }
                    per_shape[&key].clone()
                }
            };
            let input = tract_ndarray::ArrayD::from_shape_vec(in_shape, floats(&cases.join(format!("{id}.in.bin"))))?;
            let started = Instant::now();
            let out = runnable.run(tvec!(input.into_tensor().into()))?;
            s.tract_s += started.elapsed().as_secs_f64();
            s.ort_s += meta["ort_seconds"].as_f64().unwrap();
            s.runs += 1;
            let view = out[0].to_plain_array_view::<f32>()?;
            let have: Vec<f32> = view.iter().copied().collect();
            let want = floats(&cases.join(format!("{id}.out.bin")));
            assert_eq!(out[0].shape(), out_shape.as_slice(), "{model}: output shape");
            for (a, b) in want.iter().zip(&have) {
                s.gap = s.gap.max((a - b).abs());
            }
            if model.ends_with("_det") {
                s.det_flips += want.iter().zip(&have).filter(|(a, b)| (**a > 0.3) != (**b > 0.3)).count();
            } else {
                let classes = *out_shape.last().unwrap();
                for (a, b) in want.chunks(classes).zip(have.chunks(classes)) {
                    s.steps += 1;
                    s.step_diff += usize::from(argmax(a) != argmax(b));
                }
            }
        }
        for (model, s) in &stats {
            println!(
                "{model}: runs {}, worst gap {:.2e}, det pixels flipped {}, rec steps {} with a different best character {}, \
                 tract {:.2} s (+{:.2} s making per-shape plans), onnxruntime {:.2} s",
                s.runs, s.gap, s.det_flips, s.steps, s.step_diff, s.tract_s, s.compile_s, s.ort_s
            );
        }
        Ok(())
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    #[cfg(feature = "tract")]
    probe::main(std::path::Path::new(&args[1]), std::path::Path::new(&args[2])).unwrap();
    #[cfg(not(feature = "tract"))]
    println!("{} args, no tract", args.len());
}
