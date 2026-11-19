//! The A/B bench of the preview builds (.github/workflows/rust-ab.yml, docs/dev/preview-check.md): the app's own
//! checker, built at each build's own commit and release profile, reading the lobby corpus with nothing else running.
//! Silent, no window.
//!
//! bench_check <dir> [<list>]
//! READY, then a cold pass: every .jpg in code-point name order as a first check reads it (the lobby spot reset), each
//! as `FILE\t<name>` and `<ms>\t<header 0/1>\t<seats marked>\t<seat names>`; then `PHASE\thot` and a hot pass: the frame
//! named by BENCH_HOT_FRAME (else the first) read BENCH_HOT times (default 20) with the spot kept, as a player's repeated
//! hotkey reads it; then DONE, and the process waits for a line on stdin so the harness can read its CPU time first.

use std::io::BufRead;
use std::path::Path;
use std::time::Instant;

fn read(path: &Path) -> Result<opencv::core::Mat, Box<dyn std::error::Error>> {
    let bytes = opencv::core::Vector::<u8>::from_slice(&std::fs::read(path)?);
    let bgr = opencv::imgcodecs::imdecode(&bytes, opencv::imgcodecs::IMREAD_COLOR)?;
    let mut rgb = opencv::core::Mat::default();
    opencv::imgproc::cvt_color_def(&bgr, &mut rgb, opencv::imgproc::COLOR_BGR2RGB)?;
    Ok(rgb)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let dir = Path::new(args.first().ok_or("bench_check <dir> [<list>]")?);
    let blacklist: Vec<lobby::Entry> = match args.get(1) {
        Some(path) => std::fs::read_to_string(path)?
            .lines()
            .filter(|line| !line.trim().is_empty())
            .map(|name| lobby::Entry { name: name.to_string(), ..lobby::Entry::default() })
            .collect(),
        None => Vec::new(),
    };
    let mut images: Vec<_> = std::fs::read_dir(dir)?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.extension().is_some_and(|ext| ext.eq_ignore_ascii_case("jpg")))
        .collect();
    images.sort_by(|a, b| a.file_name().cmp(&b.file_name()));
    let install = app::wiring::startup::install_root();
    let dirs = pipeline::ModelDirs::find(&app::wiring::startup::model_roots(install.as_deref())).ok_or("no OCR models")?;
    let env = pipeline::runtime(&app::wiring::engine::ort_library(install.as_deref())).map_err(|e| e.to_string())?;
    let mut checker = pipeline::Checker::new(env, &dirs, common::paths::ocr_threads()).map_err(|e| e.to_string())?;
    println!("READY\t{}\treaders {}", images.len(), if dirs.rec == dirs.names { 1 } else { 2 });
    let mut once = |checker: &mut pipeline::Checker, image: &Path, rgb: opencv::core::Mat| -> Result<(), Box<dyn std::error::Error>> {
        println!("FILE\t{}", image.file_name().map(|name| name.to_string_lossy()).unwrap_or_default());
        let start = Instant::now();
        let result = checker.check(&[rgb], &blacklist, &[], None).map_err(|e| e.to_string())?;
        let ms = start.elapsed().as_secs_f64() * 1000.0;
        let names: Vec<String> = result.names.iter().map(|slot| slot.raw.replace(['\t', '\n'], " ")).collect();
        let hits: Vec<String> = result.hits.iter().map(|hit| hit.index.to_string()).collect();
        println!("{ms:.1}\t{}\t{}\t{}", u8::from(result.header_found), hits.join(","), names.join("\t"));
        Ok(())
    };
    for image in &images {
        let rgb = read(image)?;
        checker.spot = None;
        once(&mut checker, image, rgb)?;
    }
    let hot: usize = std::env::var("BENCH_HOT").ok().and_then(|v| v.parse().ok()).unwrap_or(20);
    let wanted = std::env::var("BENCH_HOT_FRAME").ok();
    let frame = images
        .iter()
        .find(|path| wanted.as_deref().is_some_and(|name| path.file_name().is_some_and(|f| f.to_string_lossy() == name)))
        .or(images.first())
        .ok_or("no frames")?
        .clone();
    println!("PHASE\thot");
    checker.spot = None;
    for _ in 0..hot {
        once(&mut checker, &frame, read(&frame)?)?;
    }
    println!("DONE");
    let _ = std::io::stdin().lock().lines().next();
    Ok(())
}
