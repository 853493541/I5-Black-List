//! scenes: part of the Rust rewrite of 模仿者小工具 (see docs/dev/research/rust-plan-2026-11-18.md).
//!
//! The spike: 星河许愿 (blacklist_detect/love_scenes/stars.py) drawn on the graphics chip. A scene is
//! seeded exactly as the Python one (`pyrand` is Python's own generator), builds a list of shapes per
//! frame (`prim`), and `gpu` shades every pixel of every shape in WGSL.
#![forbid(unsafe_code)]

pub mod cyber;
pub mod angel;
pub mod draw;
pub mod equation;
pub mod fluffy;
pub mod lyre;
pub mod gpu;
pub mod ice;
pub mod prim;
pub mod render;
pub mod pyrand;
pub mod stars;
pub mod lace;
pub mod classic;
pub mod claw;
pub mod neon;

/// The overlay's look for a scene key: a scene that draws its own marks brings its look (lyre), the
/// rest are ui_overlay.LOOKS' (overlay::look_for).
pub fn look(key: &str) -> overlay::Look {
    match key {
        "lyre" => lyre::hook::look(),
        _ => overlay::look_for(key),
    }
}
