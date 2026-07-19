//! Hover: STATIC half (kind word + resolved declaration signature, read
//! off the real CST) plus the WO-120/D229 artifact-fed half over claim
//! lines (verdict + margin, or waiver/deferral/violation detail),
//! landed by reading the WO-114 calc book (`crate::artifacts`) instead
//! of the `registry_version`-keyed evidence cache WO-38 could not reach
//! -- see `crate::artifacts`'s module docs for why that path is now
//! open. A claim with no matching shipped row, or a workspace with no
//! `dist/calc/calc_book.json` at all, degrades to the same honest
//! "(no build artifacts)" tail every other hover already carries
//! (D111: never a guess, never invented).

use lsp_types::{Hover, HoverContents, MarkupContent, MarkupKind, Position};
use regolith_syntax::ast::{AstNode, Decl, Field, RequireClaim};
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::artifacts;
use crate::position::LineIndex;

/// Hover text for the declaration (or claim line) enclosing `position`,
/// if any. `root` is the workspace root, used to locate a shipped calc
/// book for the artifact-fed claim half; static hover needs no root.
#[must_use]
// frob:doc docs/modules/regolith-ls.md#hover
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn hover_at(
    text: &str,
    index: &LineIndex,
    position: Position,
    root: &camino::Utf8Path,
) -> Option<Hover> {
    let offset = index.offset(position);
    let path = camino::Utf8PathBuf::from("<ls>");
    let parse = regolith_syntax::parse(text, &path);
    let token = parse
        .syntax()
        .token_at_offset(rowan::TextSize::try_from(offset).ok()?)
        .right_biased()?;

    if let Some(field) = token.parent_ancestors().find_map(Field::cast) {
        if field
            .syntax()
            .ancestors()
            .any(|n| RequireClaim::can_cast(n.kind()))
        {
            let range = field.syntax().text_range();
            let claim_text = field.syntax().text().to_string();
            let value = claim_hover_value(root, field.name().as_str(), claim_text.trim());
            return Some(Hover {
                contents: HoverContents::Markup(MarkupContent {
                    kind: MarkupKind::Markdown,
                    value,
                }),
                range: Some(index.range(usize::from(range.start()), usize::from(range.end()))),
            });
        }
    }

    let decl = token.parent_ancestors().find_map(Decl::cast)?;
    let name = decl.name()?;
    let kind_word = decl.kind_keyword().map_or("declaration", keyword_label);
    let range = decl.syntax().text_range();
    let value = format!("**{kind_word} {name}**\n\n(no build artifacts)");
    Some(Hover {
        contents: HoverContents::Markup(MarkupContent {
            kind: MarkupKind::Markdown,
            value,
        }),
        range: Some(index.range(usize::from(range.start()), usize::from(range.end()))),
    })
}

/// Build a claim's hover body: try the shipped calc book by subject
/// name first, then by the claim's full source text (calc.py's
/// `claim_text` fallback -- an unnamed claim's `claim_name` IS its
/// reconstructed text), else the honest degraded tail.
fn claim_hover_value(root: &camino::Utf8Path, subject: &str, full_text: &str) -> String {
    let Some(book_path) = artifacts::find_calc_book_path(root) else {
        return format!("**claim** `{full_text}`\n\n(no build artifacts)");
    };
    let Some(book) = artifacts::load_calc_book(&book_path) else {
        return format!("**claim** `{full_text}`\n\n(no build artifacts -- calc book unreadable)");
    };
    let matched = artifacts::find_claim_row(&book, subject)
        .or_else(|| artifacts::find_claim_row(&book, full_text));
    match matched {
        Some((row, sheet)) => artifacts::render_claim_hover(row, sheet),
        None => format!(
            "**claim** `{full_text}`\n\n(no build artifacts -- not in the shipped calc book)"
        ),
    }
}

/// Same label table as `symbols::keyword_label` (kept local: hover's
/// label vocabulary may grow domain prose the outline never needs).
fn keyword_label(kind: SyntaxKind) -> &'static str {
    match kind {
        SyntaxKind::PartKw => "part",
        SyntaxKind::ProfileKw => "profile",
        SyntaxKind::InterfaceKw => "interface",
        SyntaxKind::MatingKw => "mating",
        SyntaxKind::AssemblyKw => "assembly",
        SyntaxKind::SystemKw => "system",
        SyntaxKind::QuantityKw => "quantity",
        SyntaxKind::SignatureKw => "signature",
        SyntaxKind::NamespaceKw => "namespace",
        SyntaxKind::ImportKw => "import",
        _ => "declaration",
    }
}

#[cfg(test)]
mod tests {
    use super::hover_at;
    use crate::position::LineIndex;
    use camino::Utf8PathBuf;
    use lsp_types::{HoverContents, MarkupContent};

    fn no_dist_root() -> Utf8PathBuf {
        // No `dist/calc/calc_book.json` here -- exercises the degraded
        // (no build artifacts) path deterministically. A FRESH unique
        // directory, never the shared temp dir itself: anything else
        // on the machine transiently creating `dist/calc/` under
        // /tmp flips the hover to the shipped-row path and fails this
        // test flakily (F162 -- it happened, once, mid-gate).
        let dir =
            std::env::temp_dir().join(format!("regolith-ls-hover-empty-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        Utf8PathBuf::from_path_buf(dir).unwrap()
    }

    // frob:tests crates/regolith-ls/src/hover.rs::hover_at kind="unit"
    #[test]
    fn hover_over_a_decl_name_shows_kind_and_no_artifacts_tail() {
        let text = "part Widget:\n    mass: 5 g\n";
        let index = LineIndex::new(text);
        let pos = index.position(text.find("Widget").unwrap());
        let root = no_dist_root();
        let hover = hover_at(text, &index, pos, &root).expect("hover over a decl name");
        let HoverContents::Markup(MarkupContent { value, .. }) = hover.contents else {
            panic!("expected markup contents");
        };
        assert!(value.contains("part Widget"));
        assert!(value.contains("(no build artifacts)"));
    }

    #[test]
    fn hover_outside_any_decl_is_none() {
        let text = "\n\n";
        let index = LineIndex::new(text);
        let root = no_dist_root();
        assert!(hover_at(text, &index, index.position(0), &root).is_none());
    }

    #[test]
    fn hover_over_a_claim_line_degrades_honestly_without_a_calc_book() {
        let text = "part Widget:\n    require Structural:\n        mass: < 5 kg\n";
        let index = LineIndex::new(text);
        let pos = index.position(text.find("mass").unwrap());
        let root = no_dist_root();
        let hover = hover_at(text, &index, pos, &root).expect("hover over a claim line");
        let HoverContents::Markup(MarkupContent { value, .. }) = hover.contents else {
            panic!("expected markup contents");
        };
        assert!(value.contains("claim"));
        assert!(value.contains("no build artifacts"));
    }

    #[test]
    fn hover_over_a_claim_line_reads_the_matching_shipped_row() {
        let dir =
            std::env::temp_dir().join(format!("regolith-ls-hover-claim-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(dir.join("dist").join("calc")).unwrap();
        std::fs::write(
            dir.join("dist").join("calc").join("calc_book.json"),
            r#"{
                "sheets": [{
                    "sheet_id": "mass::abc123def456",
                    "claim_name": "mass",
                    "claim_text": "mass < 5 kg",
                    "subject_anchor": "Widget",
                    "model_id": "std.mech.mass",
                    "model_version": "1",
                    "citation": "uncited built-in",
                    "solver": "closed-form",
                    "tier": "certified",
                    "margin": "1.8 kg",
                    "verdict": "PASS"
                }],
                "index": { "rows": [{
                    "claim_name": "mass",
                    "subject_anchor": "Widget",
                    "disposition": "calc_sheet",
                    "detail": "mass::abc123def456"
                }] }
            }"#,
        )
        .unwrap();

        let text = "part Widget:\n    require Structural:\n        mass: < 5 kg\n";
        let index = LineIndex::new(text);
        let pos = index.position(text.find("mass").unwrap());
        let hover = hover_at(text, &index, pos, &dir).expect("hover over a claim line");
        let HoverContents::Markup(MarkupContent { value, .. }) = hover.contents else {
            panic!("expected markup contents");
        };
        assert!(value.contains("PASS"), "expected verdict in {value:?}");
        assert!(value.contains("1.8 kg"), "expected margin in {value:?}");

        std::fs::remove_dir_all(&dir).ok();
    }
}
