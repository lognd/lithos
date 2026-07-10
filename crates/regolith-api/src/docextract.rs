//! Public-surface doc extraction (`regolith doc`, WO-41).
//!
//! Walks the typed CST (WO-05) over top-level declarations and
//! collects: the declaration kind/name, its leading `#` comment block
//! (D115 -- no new syntax; a comment attaches only when no blank line
//! separates it from the declaration), its structured fields, its
//! `require` claim groups, and its `budget` statements. Rendered as
//! JSON so the Python `regolith doc` command (the one renderer,
//! Python-side for this WO) never re-implements the grammar (NO
//! DUPLICATION) -- this module is the escalated facade accessor: the
//! existing `debug tokens|cst|ast` text dumps do not preserve comment
//! trivia or structured fields, so a real accessor was genuinely
//! needed (recorded in the design log per the WO-41 dispatch note).

use camino::Utf8Path;
use regolith_syntax::ast::{
    AstNode, BudgetStmt, Decl, Field, File, FlownetDecl, MediumDecl, RequireClaim, RequireDecl,
};
use regolith_syntax::cst::{SyntaxNode, SyntaxToken};
use regolith_syntax::syntax_kind::SyntaxKind;
use serde_json::{json, Value};

use crate::CoreError;

/// Extract the public-surface doc model of `path`'s source as a JSON
/// string (`{"decls": [...]}`, one entry per top-level declaration in
/// source order, including fluorite's `medium`/`flownet`/`require`
/// top-level forms alongside the shared `Decl` node).
///
/// # Errors
/// Returns [`CoreError`] if the source file cannot be read.
pub fn doc_extract(path: &Utf8Path) -> Result<String, CoreError> {
    let source = std::fs::read_to_string(path).map_err(|e| CoreError::Io {
        path: path.to_path_buf(),
        message: e.to_string(),
    })?;
    Ok(doc_extract_source(&source, path))
}

/// Same as [`doc_extract`] but over in-memory `source` text (the
/// filesystem-free half, so tests need no scratch files).
fn doc_extract_source(source: &str, path: &Utf8Path) -> String {
    let parse = regolith_syntax::parser::parse(source, &path.to_path_buf());
    let root = File::cast(parse.syntax()).expect("parser always emits a File root");

    let mut decls: Vec<Value> = Vec::new();
    for decl in root.decls() {
        decls.push(decl_json(&decl));
    }
    for medium in root.mediums() {
        decls.push(medium_json(&medium));
    }
    for flownet in root.flownets() {
        decls.push(flownet_json(&flownet));
    }
    for require in root.fluid_requires() {
        decls.push(require_decl_json(&require));
    }

    serde_json::to_string(&json!({ "decls": decls }))
        .expect("doc-extraction JSON is always representable")
}

/// The declaration-kind label for a `SyntaxKind` keyword token: its
/// debug spelling minus the trailing `Kw`, lower-cased
/// (`PartKw` -> `"part"`). Generic over the whole keyword set so a new
/// declaration keyword never needs a matching arm here.
fn kind_label(kind: SyntaxKind) -> String {
    format!("{kind:?}")
        .strip_suffix("Kw")
        .unwrap_or("decl")
        .to_ascii_lowercase()
}

/// Strip a leading `#` and at most one following space from one
/// comment token's text, preserving the rest verbatim (including any
/// non-ASCII user content -- extraction must not corrupt it).
fn strip_comment_marker(text: &str) -> String {
    let rest = text.strip_prefix('#').unwrap_or(text);
    rest.strip_prefix(' ').unwrap_or(rest).to_string()
}

/// Collect the leading doc-comment block immediately above `first`
/// (the declaration's first token): consecutive `# ...` lines with no
/// blank line between the last one and `first`, in source order.
/// `None` when there is no such block (D115: doc text is optional).
fn leading_doc_comment(first: &SyntaxToken) -> Option<String> {
    let mut lines: Vec<String> = Vec::new();
    let mut cur = first.prev_token();
    loop {
        match cur {
            Some(ref tok) if tok.kind() == SyntaxKind::Newline => {
                cur = tok.prev_token();
            }
            _ => break,
        }
        let mut candidate = cur.clone();
        if let Some(tok) = &candidate {
            if tok.kind() == SyntaxKind::Whitespace {
                candidate = tok.prev_token();
            }
        }
        match candidate {
            Some(tok) if tok.kind() == SyntaxKind::Comment => {
                lines.push(strip_comment_marker(tok.text()));
                cur = tok.prev_token();
            }
            _ => break,
        }
    }
    if lines.is_empty() {
        None
    } else {
        lines.reverse();
        Some(lines.join("\n"))
    }
}

/// The doc comment attached to `node`, if any (see
/// [`leading_doc_comment`]).
fn node_doc(node: &SyntaxNode) -> Option<String> {
    node.first_token().and_then(|t| leading_doc_comment(&t))
}

/// Render one `subject: predicate` [`Field`] as `(name, value_text)`.
///
/// Uses [`Field::full_value_text`], NOT `field.value().map(|v| v.text())`:
/// a labeled claim whose predicate continues past its first value-ish
/// child (e.g. `settle: settles(x, to=..deg,\n    within 3s after evt)`
/// -- the tolerance expression, then an `OpaqueIsland` catch-all for the
/// `within ... after ...` trailer) truncated at the first child under
/// the old `value()`-based rendering, silently dropping the closing
/// bracket and everything after it (found live in `regolith doc` output
/// on the cubesat corpus's `antenna.hema` `settle` claim, post-WO-90).
fn field_json(field: &Field) -> Value {
    json!({
        "name": field.name(),
        "value": field.full_value_text(),
    })
}

/// The first `Ident` token text of `node` -- the pattern
/// [`Decl::name`] uses, reused for [`RequireClaim`] group names (which
/// have no dedicated accessor: they carry no further structure this
/// WO needs beyond the group label).
fn first_ident_text(node: &SyntaxNode) -> Option<String> {
    node.children_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .find(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
}

fn claim_group_json(group: &RequireClaim) -> Value {
    json!({
        "group": first_ident_text(group.syntax()).unwrap_or_default(),
        "claims": group.claims().iter().map(field_json).collect::<Vec<_>>(),
    })
}

fn budget_json(budget: &BudgetStmt) -> Value {
    json!({
        "name": budget.name(),
        "value": budget.value().map(|v| v.text().to_string()).unwrap_or_default(),
    })
}

fn decl_json(decl: &Decl) -> Value {
    let kind = decl
        .kind_keyword()
        .map_or_else(|| "decl".to_string(), kind_label);
    let name = if decl.is_process() {
        decl.process_name()
    } else {
        decl.name()
    };
    json!({
        "kind": kind,
        "name": name.unwrap_or_default(),
        "doc": node_doc(decl.syntax()),
        "fields": decl.fields().iter().map(field_json).collect::<Vec<_>>(),
        "claims": decl.claims().iter().map(claim_group_json).collect::<Vec<_>>(),
        "budgets": decl.budgets().iter().map(budget_json).collect::<Vec<_>>(),
    })
}

fn medium_json(medium: &MediumDecl) -> Value {
    json!({
        "kind": "medium",
        "name": medium.name().unwrap_or_default(),
        "doc": node_doc(medium.syntax()),
        "fields": Vec::<Value>::new(),
        "claims": Vec::<Value>::new(),
        "budgets": Vec::<Value>::new(),
        "phase": medium.phase(),
    })
}

fn flownet_json(flownet: &FlownetDecl) -> Value {
    json!({
        "kind": "flownet",
        "name": flownet.name().unwrap_or_default(),
        "doc": node_doc(flownet.syntax()),
        "fields": flownet.fields().iter().map(field_json).collect::<Vec<_>>(),
        "claims": Vec::<Value>::new(),
        "budgets": Vec::<Value>::new(),
    })
}

fn require_decl_json(require: &RequireDecl) -> Value {
    json!({
        "kind": "require",
        "name": String::new(),
        "doc": node_doc(require.syntax()),
        "fields": Vec::<Value>::new(),
        "claims": [{
            "group": "",
            "claims": require.claims().iter().map(field_json).collect::<Vec<_>>(),
        }],
        "budgets": Vec::<Value>::new(),
    })
}

#[cfg(test)]
mod tests {
    use super::doc_extract_source;
    use camino::Utf8PathBuf;

    fn path() -> Utf8PathBuf {
        Utf8PathBuf::from("t.hema")
    }

    #[test]
    fn extracts_doc_comment_verbatim() {
        let src = "# A rail.\n# Second line.\npart Rail:\n    material: AL7075_T6\n";
        let out = doc_extract_source(src, &path());
        let value: serde_json::Value = serde_json::from_str(&out).expect("json");
        let decl = &value["decls"][0];
        assert_eq!(decl["kind"], "part");
        assert_eq!(decl["name"], "Rail");
        assert_eq!(decl["doc"], "A rail.\nSecond line.");
    }

    #[test]
    fn blank_line_detaches_comment() {
        let src = "# stray\n\npart Rail:\n    material: AL7075_T6\n";
        let out = doc_extract_source(src, &path());
        let value: serde_json::Value = serde_json::from_str(&out).expect("json");
        assert!(value["decls"][0]["doc"].is_null());
    }

    #[test]
    fn extraction_is_deterministic() {
        let src = "part Rail:\n    material: AL7075_T6\n\n    require Structural:\n        rail_stress: peak(x) < 1\n";
        let a = doc_extract_source(src, &path());
        let b = doc_extract_source(src, &path());
        assert_eq!(a, b);
        assert!(a.contains("rail_stress"));
    }

    /// Regression guard: a labeled claim field whose value continues
    /// past its first value-ish CST child (the `settles(x, to=..deg,\n
    /// within 3s after evt)` shape -- a typed tolerance expression, then
    /// an `OpaqueIsland` catch-all for the `within ... after ...`
    /// trailer) must render its FULL value, not truncate at the first
    /// child. Found live on the cubesat corpus's `antenna.hema` `settle`
    /// claim post-WO-90 (`Field::value()`'s "first value child" contract
    /// silently dropped the closing bracket and everything after it).
    #[test]
    fn labeled_claim_field_value_is_not_truncated_at_a_continuation() {
        let src = "part p:\n    require Deployment:\n        settle: settles(root.theta, to=90deg +- 2deg,\n            within 3s after release_event)\n";
        let out = doc_extract_source(src, &path());
        let value: serde_json::Value = serde_json::from_str(&out).expect("json");
        let claims = &value["decls"][0]["claims"][0]["claims"];
        let settle = claims
            .as_array()
            .expect("claims array")
            .iter()
            .find(|c| c["name"] == "settle")
            .expect("settle claim present");
        let text = settle["value"].as_str().expect("value string");
        assert!(
            text.contains("within 3s after release_event"),
            "settle value truncated: {text:?}"
        );
        assert!(
            text.trim_end().ends_with(')'),
            "settle value missing its closing paren: {text:?}"
        );
    }
}
