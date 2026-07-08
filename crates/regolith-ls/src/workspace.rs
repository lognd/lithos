//! Workspace root discovery (WO-38 deliverable 1): the nearest
//! `magnetite.toml` above the opened folder, else the opened folder
//! itself.

use camino::{Utf8Path, Utf8PathBuf};

/// The manifest file name that anchors a magnetite package -- this is a
/// filename literal, not a source-extension literal, so ground rule 6
/// (extensions live only in the registry) does not apply to it.
const MANIFEST: &str = "magnetite.toml";

/// Find the workspace root for `opened`: walk upward from `opened`
/// looking for `magnetite.toml`; if none is found anywhere up to the
/// filesystem root, `opened` itself is the root (deliverable 1).
#[must_use]
pub fn discover_root(opened: &Utf8Path) -> Utf8PathBuf {
    let mut dir = if opened.is_dir() {
        Some(opened.to_path_buf())
    } else {
        opened.parent().map(Utf8Path::to_path_buf)
    };
    while let Some(candidate) = dir {
        if candidate.join(MANIFEST).is_file() {
            return candidate;
        }
        dir = candidate.parent().map(Utf8Path::to_path_buf);
    }
    opened.to_path_buf()
}

#[cfg(test)]
mod tests {
    use super::discover_root;
    use camino::Utf8PathBuf;

    #[test]
    fn falls_back_to_opened_folder_when_no_manifest_found() {
        let dir = std::env::temp_dir().join(format!("regolith-ls-wsroot-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        let found = discover_root(&dir);
        assert_eq!(found, dir);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn finds_manifest_in_a_parent_directory() {
        let base = std::env::temp_dir().join(format!("regolith-ls-wsroot2-{}", std::process::id()));
        let base = Utf8PathBuf::from_path_buf(base).unwrap();
        let nested = base.join("src").join("deep");
        std::fs::create_dir_all(&nested).unwrap();
        std::fs::write(base.join("magnetite.toml"), "").unwrap();
        let found = discover_root(&nested);
        assert_eq!(found, base);
        std::fs::remove_dir_all(&base).ok();
    }
}
