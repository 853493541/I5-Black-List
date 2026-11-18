fn main() {
    slint_build::compile("ui/all.slint").expect("ui/all.slint compiles");
    // The exe names its .pdb by file name only, not by the build machine's path (the .pdb ships as a CI artifact,
    // never with the app; a debugger finds it beside the dump or on a symbol path).
    if std::env::var("CARGO_CFG_TARGET_ENV").as_deref() == Ok("msvc") {
        println!("cargo:rustc-link-arg-bin=blacklist-detect=/PDBALTPATH:%_PDB%");
    }
}
