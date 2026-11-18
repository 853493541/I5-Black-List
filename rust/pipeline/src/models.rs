//! Finding the model folders, as ocr_engine.model_dirs and bundled_model do: BLACKLIST_DETECT_MODEL_DIR, then `models`
//! beside the app, then `models` in the working folder.

use std::path::{Path, PathBuf};

/// The name reader's model, looked for by its own folder name.
pub const NAME_MODEL: &str = "PP-OCRv6_medium_rec";
const MARKERS: [&str; 3] = ["inference.yml", "inference.json", "inference.pdmodel"];

/// The three model folders a check reads with: line detection, line recognition and the name reader.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ModelDirs {
    pub det: PathBuf,
    pub rec: PathBuf,
    pub names: PathBuf,
}

impl ModelDirs {
    /// The folders under the first root that has them, roots tried in order (see `search_roots`).
    pub fn find(roots: &[PathBuf]) -> Option<Self> {
        let (det, rec) = model_dirs(roots)?;
        let names = bundled_model(roots, NAME_MODEL)?;
        Some(Self { det, rec, names })
    }

    /// All three under one folder, as a test or a tool names it.
    pub fn under(root: &Path) -> Option<Self> {
        Self::find(&[root.to_path_buf()])
    }
}

/// Where the models are looked for: BLACKLIST_DETECT_MODEL_DIR, `models` beside the program, `models` here.
pub fn search_roots() -> Vec<PathBuf> {
    let mut roots = Vec::new();
    if let Some(env) = std::env::var_os("BLACKLIST_DETECT_MODEL_DIR").filter(|v| !v.is_empty()) {
        roots.push(PathBuf::from(env));
    }
    if let Some(dir) = std::env::current_exe().ok().and_then(|exe| exe.parent().map(Path::to_path_buf)) {
        roots.push(dir.join("models"));
    }
    if let Ok(cwd) = std::env::current_dir() {
        roots.push(cwd.join("models"));
    }
    roots
}

/// model_dirs: the detection and recognition folders of the first root that has both.
pub fn model_dirs(roots: &[PathBuf]) -> Option<(PathBuf, PathBuf)> {
    roots
        .iter()
        .filter(|root| root.is_dir())
        .find_map(|root| Some((find_model_dir(root, "det")?, find_model_dir(root, "rec")?)))
}

/// bundled_model: a folder of this name under the first root that has it.
pub fn bundled_model(roots: &[PathBuf], name: &str) -> Option<PathBuf> {
    roots.iter().map(|root| root.join(name)).find(|candidate| candidate.is_dir())
}

fn label(path: &Path) -> String {
    path.file_name().map(|name| name.to_string_lossy().to_lowercase()).unwrap_or_default()
}

/// _find_model_dir: the root itself when it is a model of this kind, else its first child (by name) with the kind
/// in its name and a model's files, or any files at all.
pub fn find_model_dir(root: &Path, kind: &str) -> Option<PathBuf> {
    if MARKERS.iter().any(|name| root.join(name).exists()) && label(root).contains(kind) {
        return Some(root.to_path_buf());
    }
    let mut children: Vec<PathBuf> = std::fs::read_dir(root).ok()?.filter_map(|e| e.ok().map(|e| e.path())).collect();
    children.sort();
    children.into_iter().find(|child| {
        if !child.is_dir() || !label(child).contains(kind) {
            return false;
        }
        MARKERS.iter().chain(&["inference.pdiparams"]).any(|name| child.join(name).exists())
            || std::fs::read_dir(child).map(|mut dir| dir.next().is_some()).unwrap_or(false)
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn folder(root: &Path, name: &str, file: &str) {
        std::fs::create_dir_all(root.join(name)).unwrap();
        std::fs::write(root.join(name).join(file), "x").unwrap();
    }

    #[test]
    fn finds_the_first_folder_of_each_kind_and_the_name_model() {
        let root = std::env::temp_dir().join(format!("pipeline-models-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        folder(&root, "PP-OCRv5_mobile_det", "inference.yml");
        folder(&root, "PP-OCRv6_medium_rec", "inference.yml");
        folder(&root, "PP-OCRv5_mobile_rec", "inference.onnx");
        folder(&root, "notes", "readme.txt");
        let dirs = ModelDirs::under(&root).unwrap();
        assert_eq!(dirs.det, root.join("PP-OCRv5_mobile_det"));
        assert_eq!(dirs.rec, root.join("PP-OCRv5_mobile_rec"));
        assert_eq!(dirs.names, root.join(NAME_MODEL));
        let missing = root.join("nothing");
        assert_eq!(ModelDirs::find(&[missing, root.clone()]).unwrap(), dirs);
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn a_model_folder_named_as_the_root_is_the_root() {
        let root = std::env::temp_dir().join(format!("pipeline-det-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        folder(&root, "my_det", "inference.yml");
        assert_eq!(find_model_dir(&root.join("my_det"), "det"), Some(root.join("my_det")));
        assert_eq!(find_model_dir(&root.join("my_det"), "rec"), None);
        std::fs::remove_dir_all(&root).unwrap();
    }
}
