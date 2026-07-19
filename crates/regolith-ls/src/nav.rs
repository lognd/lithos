//! Navigation + editing (WO-38 deliverable 6): go-to-definition,
//! references, and resolution-checked rename over the real CST.
//!
//! Scope note (honest, per the WO-38 dispatch report): this is name-
//! text identifier resolution over `Decl` headers and `Ident` tokens,
//! not a full scoped semantic resolver (`regolith-sem` exposes an
//! entity DB and query engine, not a name->declaration lookup table a
//! language server can drive directly). Within one file this is exact
//! (each `Decl` owns one header name). Across files it walks `import`
//! declarations to the files they name, restricting cross-file search
//! to files actually reachable through imports (the charter's "import
//! reach" scope for rename), never a workspace-wide grep. Rename
//! REFUSES (returns `RenameOutcome::Ambiguous`) whenever more than one
//! reachable file defines the same name, per the WO's ambiguity
//! discipline (INV-18 applied to tooling) -- it never applies a
//! partial edit.

use camino::{Utf8Path, Utf8PathBuf};
use lsp_types::{Position, TextEdit};
use regolith_syntax::ast::{AstNode, Decl, File};
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::diagnostics::file_uri;
use crate::position::LineIndex;

/// One occurrence of an identifier: which file, and its byte range.
#[derive(Debug, Clone)]
// frob:doc docs/modules/regolith-ls.md#nav
pub struct Occurrence {
    /// The file the occurrence was found in.
    pub file: Utf8PathBuf,
    /// The occurrence's byte range within that file.
    pub range: (usize, usize),
}

/// The identifier token text and byte range at `position` in `text`,
/// if the cursor sits on an `Ident` token.
#[must_use]
// frob:doc docs/modules/regolith-ls.md#nav
pub fn identifier_at(
    text: &str,
    index: &LineIndex,
    position: Position,
) -> Option<(String, (usize, usize))> {
    let offset = index.offset(position);
    let path = Utf8PathBuf::from("<ls>");
    let parse = regolith_syntax::parse(text, &path);
    let token = parse
        .syntax()
        .token_at_offset(rowan::TextSize::try_from(offset).ok()?)
        .right_biased()?;
    if token.kind() != SyntaxKind::Ident {
        return None;
    }
    let range = token.text_range();
    Some((
        token.text().to_string(),
        (usize::from(range.start()), usize::from(range.end())),
    ))
}

/// Every top-level `Decl` header name occurrence in `text` matching
/// `name` -- the "definition" set for that name in this file.
fn definitions_in_text(text: &str, name: &str, file: &Utf8Path) -> Vec<Occurrence> {
    let path = Utf8PathBuf::from("<ls>");
    let parse = regolith_syntax::parse(text, &path);
    parse
        .syntax()
        .children()
        .filter_map(Decl::cast)
        .filter_map(|decl| {
            let decl_name = decl.name()?;
            if decl_name != name {
                return None;
            }
            let token = decl
                .syntax()
                .children_with_tokens()
                .filter_map(rowan::NodeOrToken::into_token)
                .find(|t| t.kind() == SyntaxKind::Ident)?;
            let range = token.text_range();
            Some(Occurrence {
                file: file.to_path_buf(),
                range: (usize::from(range.start()), usize::from(range.end())),
            })
        })
        .collect()
}

/// Every `Ident` token occurrence matching `name` in `text` (definitions
/// and uses both -- "references" per LSP semantics includes the decl).
fn references_in_text(text: &str, name: &str, file: &Utf8Path) -> Vec<Occurrence> {
    let path = Utf8PathBuf::from("<ls>");
    let parse = regolith_syntax::parse(text, &path);
    parse
        .syntax()
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .filter(|t| t.kind() == SyntaxKind::Ident && t.text() == name)
        .map(|t| {
            let range = t.text_range();
            Occurrence {
                file: file.to_path_buf(),
                range: (usize::from(range.start()), usize::from(range.end())),
            }
        })
        .collect()
}

/// The set of files reachable from `root_file`: itself, plus every file
/// named by an `import` declaration resolved against the workspace root,
/// restricted to registered source extensions (never a hard-coded
/// extension list -- `regolith_syntax::language_for_extension`).
fn reachable_files(workspace_root: &Utf8Path, root_file: &Utf8Path) -> Vec<Utf8PathBuf> {
    let mut seen = vec![root_file.to_path_buf()];
    let Ok(text) = std::fs::read_to_string(root_file) else {
        return seen;
    };
    let path = Utf8PathBuf::from("<ls>");
    let parse = regolith_syntax::parse(&text, &path);
    let Some(file) = File::cast(parse.syntax()) else {
        return seen;
    };
    for import in file.imports() {
        // `import` statements parse as `ImportStmt`, not `Decl` (they
        // have a header line only, no body) -- pull the imported path's
        // first `Ident` token directly rather than going through
        // `Decl::name` (which does not apply here).
        let Some(imported) = import
            .syntax()
            .children_with_tokens()
            .filter_map(rowan::NodeOrToken::into_token)
            .find(|t| t.kind() == SyntaxKind::Ident)
            .map(|t| t.text().to_string())
        else {
            continue;
        };
        // The imported name is a dotted/slash package path segment; the
        // best-effort resolution this pass supports is: find a source
        // file anywhere under the workspace root whose stem matches the
        // last path segment. A full magnetite-aware resolver is out of
        // this WO's reach (see the module doc note).
        let segment = imported.rsplit(['.', '/']).next().unwrap_or(&imported);
        if let Some(found) = find_source_file_by_stem(workspace_root, segment) {
            if !seen.contains(&found) {
                seen.push(found);
            }
        }
    }
    seen
}

/// Walk `root` looking for a registered source file whose stem equals
/// `stem`. Best-effort, bounded workspace search (corpus-sized trees).
fn find_source_file_by_stem(root: &Utf8Path, stem: &str) -> Option<Utf8PathBuf> {
    for entry in walk_files(root) {
        if entry.file_stem() == Some(stem) {
            let ext = entry.extension()?;
            if regolith_syntax::language_for_extension(ext).is_some() {
                return Some(entry);
            }
        }
    }
    None
}

/// Every registered-extension source file under `root`, depth-first,
/// skipping hidden/build directories.
fn walk_files(root: &Utf8Path) -> Vec<Utf8PathBuf> {
    let mut out = Vec::new();
    let Ok(entries) = std::fs::read_dir(root) else {
        return out;
    };
    for entry in entries.flatten() {
        let Ok(p) = Utf8PathBuf::from_path_buf(entry.path()) else {
            continue;
        };
        let name = p.file_name().unwrap_or_default();
        if name.starts_with('.') || name == "target" {
            continue;
        }
        if p.is_dir() {
            out.extend(walk_files(&p));
        } else if let Some(ext) = p.extension() {
            if regolith_syntax::language_for_extension(ext).is_some() {
                out.push(p);
            }
        }
    }
    out
}

/// Go to definition: every reachable file's definition occurrences of
/// the identifier at `position` in `file` (usually one; empty if the
/// name is unresolved).
#[must_use]
// frob:doc docs/modules/regolith-ls.md#nav
pub fn definitions(
    workspace_root: &Utf8Path,
    file: &Utf8Path,
    text: &str,
    index: &LineIndex,
    position: Position,
) -> Vec<Occurrence> {
    let Some((name, _)) = identifier_at(text, index, position) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for candidate in reachable_files(workspace_root, file) {
        let candidate_text = if candidate == file {
            text.to_string()
        } else {
            std::fs::read_to_string(&candidate).unwrap_or_default()
        };
        out.extend(definitions_in_text(&candidate_text, &name, &candidate));
    }
    out
}

/// Find-references: every occurrence of the identifier at `position`
/// across every reachable file.
#[must_use]
// frob:doc docs/modules/regolith-ls.md#nav
pub fn references(
    workspace_root: &Utf8Path,
    file: &Utf8Path,
    text: &str,
    index: &LineIndex,
    position: Position,
) -> Vec<Occurrence> {
    let Some((name, _)) = identifier_at(text, index, position) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for candidate in reachable_files(workspace_root, file) {
        let candidate_text = if candidate == file {
            text.to_string()
        } else {
            std::fs::read_to_string(&candidate).unwrap_or_default()
        };
        out.extend(references_in_text(&candidate_text, &name, &candidate));
    }
    out
}

/// The result of a rename attempt: either the full set of edits (one
/// `TextEdit` per occurrence, grouped by file) or a refusal naming why
/// (never a partial rename -- INV-18 discipline applied to tooling).
// frob:doc docs/modules/regolith-ls.md#nav
pub enum RenameOutcome {
    /// A safe, unambiguous set of edits, grouped by file.
    Edits(Vec<(Utf8PathBuf, Vec<TextEdit>)>),
    /// More than one reachable file defines the name; refused.
    Ambiguous {
        /// Human-readable refusal reason, surfaced to the client.
        reason: String,
    },
    /// No renamable identifier at the requested position.
    NotFound,
}

/// Resolution-checked rename: refuses when more than one reachable file
/// defines the identifier at `position` (an ambiguous name has no safe
/// single rename target).
#[must_use]
// frob:doc docs/modules/regolith-ls.md#nav
pub fn rename(
    workspace_root: &Utf8Path,
    file: &Utf8Path,
    text: &str,
    index: &LineIndex,
    position: Position,
    new_name: &str,
) -> RenameOutcome {
    let Some((name, _)) = identifier_at(text, index, position) else {
        return RenameOutcome::NotFound;
    };
    let files = reachable_files(workspace_root, file);
    let mut definition_count = 0usize;
    let mut per_file: Vec<(Utf8PathBuf, Vec<Occurrence>)> = Vec::new();
    for candidate in &files {
        let candidate_text = if candidate == file {
            text.to_string()
        } else {
            std::fs::read_to_string(candidate).unwrap_or_default()
        };
        definition_count += definitions_in_text(&candidate_text, &name, candidate).len();
        let refs = references_in_text(&candidate_text, &name, candidate);
        if !refs.is_empty() {
            per_file.push((candidate.clone(), refs));
        }
    }
    if definition_count == 0 {
        return RenameOutcome::NotFound;
    }
    if definition_count > 1 {
        return RenameOutcome::Ambiguous {
            reason: format!(
                "'{name}' is defined in {definition_count} reachable files; refusing to rename ambiguously"
            ),
        };
    }
    let mut edits = Vec::new();
    for (candidate, occurrences) in per_file {
        let candidate_text = if candidate == file {
            text.to_string()
        } else {
            std::fs::read_to_string(&candidate).unwrap_or_default()
        };
        let candidate_index = LineIndex::new(&candidate_text);
        let file_edits = occurrences
            .into_iter()
            .map(|occ| TextEdit {
                range: candidate_index.range(occ.range.0, occ.range.1),
                new_text: new_name.to_string(),
            })
            .collect();
        edits.push((candidate, file_edits));
    }
    RenameOutcome::Edits(edits)
}

/// Convert an [`Occurrence`] list into LSP `Location`s (definitions/
/// references responses need `Url` + `Range`, not raw byte ranges).
#[must_use]
// frob:doc docs/modules/regolith-ls.md#nav
pub fn occurrences_to_locations(occurrences: Vec<Occurrence>) -> Vec<lsp_types::Location> {
    occurrences
        .into_iter()
        .filter_map(|occ| {
            let uri = file_uri(&occ.file)?;
            let text = std::fs::read_to_string(&occ.file).ok()?;
            let index = LineIndex::new(&text);
            Some(lsp_types::Location {
                uri,
                range: index.range(occ.range.0, occ.range.1),
            })
        })
        .collect()
}

/// Convert a [`RenameOutcome`]'s edits into an LSP `WorkspaceEdit`. The
/// caller has already handled `Ambiguous`/`NotFound` (they carry no
/// edit).
#[must_use]
// frob:doc docs/modules/regolith-ls.md#nav
pub fn edits_to_workspace_edit(
    edits: Vec<(Utf8PathBuf, Vec<TextEdit>)>,
) -> lsp_types::WorkspaceEdit {
    let mut changes = std::collections::HashMap::new();
    for (file, file_edits) in edits {
        if let Some(uri) = file_uri(&file) {
            changes.insert(uri, file_edits);
        }
    }
    lsp_types::WorkspaceEdit {
        changes: Some(changes),
        document_changes: None,
        change_annotations: None,
    }
}

#[cfg(test)]
mod tests {
    use super::{
        definitions, identifier_at, occurrences_to_locations, references, rename, RenameOutcome,
    };
    use crate::position::LineIndex;
    use camino::Utf8PathBuf;
    use lsp_types::Position;

    fn scratch_dir(name: &str) -> Utf8PathBuf {
        let dir =
            std::env::temp_dir().join(format!("regolith-ls-nav-{name}-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).ok();
        dir
    }

    // frob:tests crates/regolith-ls/src/nav.rs::identifier_at kind="unit"
    #[test]
    fn identifier_at_a_decl_name_is_found() {
        let text = "part Widget:\n    mass: 5 g\n";
        let index = LineIndex::new(text);
        let pos = index.position(text.find("Widget").unwrap());
        let (name, _) = identifier_at(text, &index, pos).expect("ident at Widget");
        assert_eq!(name, "Widget");
    }

    // frob:tests crates/regolith-ls/src/nav.rs::definitions kind="unit"
    // frob:tests crates/regolith-ls/src/nav.rs::occurrences_to_locations kind="unit"
    #[test]
    fn definitions_finds_the_single_decl_header() {
        let dir = scratch_dir("defs");
        let file = dir.join("widget.hema");
        let text = "part Widget:\n    mass: 5 g\n";
        std::fs::write(&file, text).unwrap();
        let index = LineIndex::new(text);
        let pos = index.position(text.find("Widget").unwrap());
        let defs = definitions(&dir, &file, text, &index, pos);
        assert_eq!(defs.len(), 1);
        let locs = occurrences_to_locations(defs);
        assert_eq!(locs.len(), 1);
        std::fs::remove_dir_all(&dir).ok();
    }

    // frob:tests crates/regolith-ls/src/nav.rs::references kind="unit"
    #[test]
    fn references_finds_every_occurrence_in_file() {
        let dir = scratch_dir("refs");
        let file = dir.join("widget.hema");
        let text = "part Widget:\n    mass: 5 g\nassembly Uses:\n    part Widget\n";
        std::fs::write(&file, text).unwrap();
        let index = LineIndex::new(text);
        let pos = index.position(text.find("Widget").unwrap());
        let refs = references(&dir, &file, text, &index, pos);
        assert!(refs.len() >= 2);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn rename_refuses_when_ambiguous_across_files() {
        let dir = scratch_dir("ambig");
        let a = dir.join("a.hema");
        let b = dir.join("b.hema");
        std::fs::write(&a, "part Widget:\n    mass: 5 g\nimport b\n").unwrap();
        std::fs::write(&b, "part Widget:\n    mass: 6 g\n").unwrap();
        let text = std::fs::read_to_string(&a).unwrap();
        let index = LineIndex::new(&text);
        let pos = index.position(text.find("Widget").unwrap());
        let outcome = rename(&dir, &a, &text, &index, pos, "Gadget");
        assert!(matches!(outcome, RenameOutcome::Ambiguous { .. }));
        std::fs::remove_dir_all(&dir).ok();
    }

    // frob:tests crates/regolith-ls/src/nav.rs::rename kind="unit"
    // frob:tests crates/regolith-ls/src/nav.rs::edits_to_workspace_edit kind="unit"
    #[test]
    fn rename_produces_edits_for_the_unambiguous_case() {
        let dir = scratch_dir("solo");
        let file = dir.join("widget.hema");
        let text = "part Widget:\n    mass: 5 g\nassembly Uses:\n    part Widget\n";
        std::fs::write(&file, text).unwrap();
        let index = LineIndex::new(text);
        let pos = index.position(text.find("Widget").unwrap());
        let outcome = rename(&dir, &file, text, &index, pos, "Gadget");
        match outcome {
            RenameOutcome::Edits(edits) => {
                assert_eq!(edits.len(), 1);
                assert!(edits[0].1.len() >= 2);
            }
            _ => panic!("expected an unambiguous single-file rename"),
        }
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn rename_of_unknown_name_is_not_found() {
        let dir = scratch_dir("missing");
        let file = dir.join("widget.hema");
        let text = "part Widget:\n    mass: 5 g\n";
        std::fs::write(&file, text).unwrap();
        let index = LineIndex::new(text);
        let outcome = rename(&dir, &file, text, &index, Position::new(5, 0), "Gadget");
        assert!(matches!(outcome, RenameOutcome::NotFound));
        std::fs::remove_dir_all(&dir).ok();
    }
}
