//! The still a preview opens on: the scene's poster (build/theme_posters.py draws them), 经典's for one this version
//! does not have.
// stub: stage. The stage package feeds live frames into the dialogs' `frame` later; until then, and for the still a
// dialog opens on, the poster from blacklist_detect/assets/posters. The app's packaging decides where they ship.

use std::path::PathBuf;

use slint::Image;

use super::{known, shown, SCENES};

/// Where the posters are: BLACKLIST_DETECT_POSTERS, else the Python app's assets beside this checkout.
pub fn folder() -> PathBuf {
    std::env::var_os("BLACKLIST_DETECT_POSTERS")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../blacklist_detect/assets/posters"))
}

/// The scene's poster; an empty image when it cannot be read.
pub fn poster(key: &str) -> Image {
    let key = if known(shown(key)) { shown(key) } else { SCENES[0].0 };
    Image::load_from_path(&folder().join(format!("{key}.jpg"))).unwrap_or_default()
}
