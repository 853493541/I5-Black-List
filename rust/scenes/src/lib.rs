//! scenes: part of the Rust rewrite of 模仿者小工具 (see docs/dev/research/rust-plan-2026-11-18.md).
//!
//! The spike: 星河许愿 (blacklist_detect/love_scenes/stars.py) drawn on the graphics chip. A scene is
//! seeded exactly as the Python one (`pyrand` is Python's own generator), builds a list of shapes per
//! frame (`prim`), and `gpu` shades every pixel of every shape in WGSL.
#![forbid(unsafe_code)]

pub mod draw;
pub mod equation;
pub mod gpu;
pub mod ice;
pub mod prim;
pub mod pyrand;
pub mod stars;
