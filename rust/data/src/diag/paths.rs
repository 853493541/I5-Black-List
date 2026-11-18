//! paths.ocr_threads and paths.child_env: the OCR's thread count, and the environment a program the app
//! starts gets (OMP_NUM_THREADS left out: inherited, Paddle's 1 left the next copy's OCR on one core).

/// Set in this process for this process, wrong for a program it starts.
pub const NOT_INHERITED: [&str; 1] = ["OMP_NUM_THREADS"];
/// Intel OpenMP's marker that a copy of it is loaded.
pub const NOT_INHERITED_PREFIX: &str = "__KMP_REGISTERED_LIB_";

/// Threads the OCR reads names on: one per physical core, 2 to 8, as text (it goes into OMP_NUM_THREADS).
pub fn ocr_threads(cores: usize) -> String {
    cores.clamp(2, 8).to_string()
}

/// This process's environment for a program it starts, the next copy of the app above all: everything but
/// OMP_NUM_THREADS and Intel OpenMP's markers, in any letter case, in the order given.
pub fn child_env<I: IntoIterator<Item = (String, String)>>(vars: I) -> Vec<(String, String)> {
    vars.into_iter()
        .filter(|(key, _)| {
            let upper = key.to_uppercase();
            !NOT_INHERITED.contains(&upper.as_str()) && !upper.starts_with(NOT_INHERITED_PREFIX)
        })
        .collect()
}

/// What __main__ does to OMP_NUM_THREADS before anything else loads: the value the copy was started with
/// (paths.inherited_threads, kept for the log) and the value it sets for itself, [`ocr_threads`] of `cores`.
/// The app calls `std::env::set_var("OMP_NUM_THREADS", set)` with the second one, first thing in main.
pub fn start_threads(inherited: Option<String>, cores: usize) -> (Option<String>, String) {
    (inherited, ocr_threads(cores))
}
