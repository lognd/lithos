//! The ONE `then:` claim-scope walk (WO-29 Q4(a) corrected, deliverable
//! 2; shared by 2/3/5 per the design corollary -- NO DUPLICATION,
//! AD-17). A `then:` scope holds the feature constructor lines
//! (`pilot = Bore(dia 28mm, ...)`, `mounts = PatternOf<CBore<M8>>(n=2,
//! ...)`) the mech corpus uses; the parser already structures each as a
//! [`SyntaxKind::CtorStmt`] whose value is a `CallExpr`/`InstExpr`
//! (`../design/23-lowering-output-surface.md` Q4(a) -- `parts:` orbit
//! lines instantiate sub-parts, NOT hole/bend geometry, and are NOT this
//! walk's job).
//!
//! This module is the single traversal over those constructor calls:
//! [`feature_calls_in_decl`] yields one [`FeatureCall`] per constructor
//! line inside any `then:` scope of a declaration. Deliverable 2's
//! entity projector (`entities.rs`) consumes it to materialize
//! `Hole`/`Bend` entities; a later feature-program emitter (deliverable
//! 3) reuses the SAME structured calls rather than re-walking the CST.

use regolith_syntax::ast::{AstNode, CtorStmt, Decl, Field, InstExpr};
use regolith_syntax::cst::SyntaxNode;
use regolith_syntax::syntax_kind::SyntaxKind;

/// One feature-constructor line lifted out of a `then:` claim scope.
///
/// Deterministic and CST-derived: the fields are exactly what the
/// grammar structured, never invented. `head` is the outermost
/// constructor spelling; for a `PatternOf<Inner...>(n=N, ...)` orbit,
/// `pattern_inner` carries the inner constructor spelling and `count`
/// carries the resolved `n=` multiplicity (an orbit of `count` identical
/// features). For a direct call `count` is 1 and `pattern_inner` is
/// `None`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FeatureCall {
    /// The ctor-statement name (the feature's local binding, e.g.
    /// `pilot`), used as the emitted entity's `origin`.
    pub binding: String,
    /// The outermost constructor head (`Bore`, `Bend`, `PatternOf`).
    pub head: String,
    /// For a `PatternOf<Inner...>` orbit, the inner constructor head
    /// (`CBore`, `Drill`, ...); `None` for a direct constructor call.
    pub pattern_inner: Option<String>,
    /// Orbit multiplicity: `n=N` for a `PatternOf`, else 1.
    pub count: usize,
    /// The raw argument text (inside the outermost `(...)`), the source
    /// of the well-known measure keys the projector extracts. Empty when
    /// the constructor took no argument list.
    pub args_text: String,
}

impl FeatureCall {
    /// The constructor whose kind decides the domain entity: the inner
    /// constructor for a `PatternOf` orbit, else the head itself.
    #[must_use]
    pub fn effective_constructor(&self) -> &str {
        self.pattern_inner.as_deref().unwrap_or(&self.head)
    }
}

/// Every feature-constructor call inside every `then:` scope OR stage
/// body of `decl`, in source order. hematite/05: a stage body's bare
/// constructor statement is its own claim scope (the corpus's
/// `stage formed: ... flange = Bend(...)` spelling, WO-28), so the walk
/// accepts a `StageStmt` ancestor as well as a `ThenScope` one. A
/// `CtorStmt` outside both (e.g. a cuprite combinational `=` line in a
/// behavior body) is NOT a feature line and is skipped; non-feature
/// constructor heads inside stages are dropped by the callers'
/// `EntityKind::from_constructor_word` filter, so widening the scope
/// admits no false features.
#[must_use]
pub fn feature_calls_in_decl(decl: &Decl) -> Vec<FeatureCall> {
    let mut out = Vec::new();
    for node in decl.syntax().descendants() {
        if node.kind() != SyntaxKind::CtorStmt {
            continue;
        }
        if !is_in_feature_scope(&node) {
            continue;
        }
        let Some(ctor) = CtorStmt::cast(node.clone()) else {
            continue;
        };
        let Some(value) = ctor.value() else { continue };
        // The full right-hand-side text (everything after the ctor `=`):
        // the parser structures `key=value` args but leaves the
        // label-positional `dia 28mm` form and any trailing flags in an
        // `OpaqueIsland` sibling, so the measure scan reads the whole RHS
        // rather than the (possibly truncated) `ArgList` node alone.
        let rhs_text = rhs_text_of(&node);
        if let Some(call) = feature_call_from_value(&ctor.name(), &value, rhs_text) {
            out.push(call);
        }
    }
    out
}

/// True when `node` sits inside a feature-emitting scope: a `then:`
/// scope or a stage body (see [`feature_calls_in_decl`]'s doc for why
/// both count).
fn is_in_feature_scope(node: &SyntaxNode) -> bool {
    node.ancestors()
        .any(|a| matches!(a.kind(), SyntaxKind::ThenScope | SyntaxKind::StageStmt))
}

/// One `connect:` block mating-instance line (WO-29 deliverable 5,
/// Q4(b)). A `connect:` body parses through the SAME shared stmt-block
/// grammar a `then:` scope does: `name: Ctor(a=.., b=.., ...)` is
/// already a structured [`SyntaxKind::Field`] whose value is a
/// `CallExpr`/`InstExpr` -- no new CST production was needed here
/// either (mirrors D125's finding for `then:` scopes exactly).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConnectCall {
    /// The connect instance's local binding (`mount`, `seat_xp`), used
    /// as the emitted `Mating::name`.
    pub binding: String,
    /// The mating-type head spelled (`PodMountMate`, `AxisMount`), or
    /// the orbit-zip verb (`pairwise`) for a `pairwise(a, b) by
    /// <Mating>` orbit connection.
    pub head: String,
    /// The raw text after the field's `:` (the call's argument list
    /// plus any trailing clause, e.g. `exposing pos: ...`).
    pub args_text: String,
}

/// Every mating-instance line inside every `connect:` block of `decl`,
/// in source order. A `Field` outside a `ConnectBlock` is not a connect
/// line and is skipped.
#[must_use]
pub fn connect_calls_in_decl(decl: &Decl) -> Vec<ConnectCall> {
    let mut out = Vec::new();
    for node in decl.syntax().descendants() {
        if node.kind() != SyntaxKind::Field {
            continue;
        }
        if !is_in_connect_block(&node) {
            continue;
        }
        let Some(field) = Field::cast(node.clone()) else {
            continue;
        };
        let Some(value) = field.value() else { continue };
        let Some(head) = leading_head(&value) else {
            continue;
        };
        let args_text = field_colon_rhs_text(&node);
        out.push(ConnectCall {
            binding: field.name(),
            head,
            args_text,
        });
    }
    out
}

/// True when `node` has a `ConnectBlock` ancestor.
fn is_in_connect_block(node: &SyntaxNode) -> bool {
    node.ancestors()
        .any(|a| a.kind() == SyntaxKind::ConnectBlock)
}

/// A `Field` node's text after its first `:` (name-value separator),
/// trimmed. Shared shape with `contracts.rs::field_rhs_text`, kept as
/// its own copy here since that helper takes an `ast::Field`, not a raw
/// `SyntaxNode` (the connect walk already has the node from the
/// `descendants()` scan).
fn field_colon_rhs_text(field_node: &SyntaxNode) -> String {
    let full = field_node.text().to_string();
    full.split_once(':')
        .map_or_else(String::new, |(_, rhs)| rhs.trim().to_string())
}

/// The ctor statement's right-hand-side text: everything after the
/// first `=` (the assignment operator; any `key=value` argument `=` is
/// necessarily later in the line). Trimmed.
fn rhs_text_of(ctor_node: &SyntaxNode) -> String {
    let full = ctor_node.text().to_string();
    full.split_once('=')
        .map_or_else(String::new, |(_, rhs)| rhs.trim().to_string())
}

/// Build a [`FeatureCall`] from a ctor statement's value node, or `None`
/// when the value is not a constructor call/instantiation (a bare
/// reference like `Ream(bore.wall)`'s refining alias still parses as a
/// call and is captured; a plain path value is not a feature).
fn feature_call_from_value(
    binding: &str,
    value: &SyntaxNode,
    args_text: String,
) -> Option<FeatureCall> {
    let head = leading_head(value)?;

    if head == "PatternOf" {
        let pattern_inner = pattern_inner_head(value);
        let count = extract_count(&args_text).unwrap_or(1);
        return Some(FeatureCall {
            binding: binding.to_string(),
            head,
            pattern_inner,
            count,
            args_text,
        });
    }

    Some(FeatureCall {
        binding: binding.to_string(),
        head,
        pattern_inner: None,
        count: 1,
        args_text,
    })
}

/// The outermost constructor head spelled in a value node: the head
/// `NameRef`/`Path` of a `CallExpr`/`InstExpr`, or the value's own name
/// when it is a bare `NameRef`/`Path`. `None` for a non-name value
/// (number, interval, ...).
fn leading_head(value: &SyntaxNode) -> Option<String> {
    match value.kind() {
        SyntaxKind::CallExpr | SyntaxKind::InstExpr => {
            // First child is the callee: a NameRef/Path, or a nested
            // InstExpr (a called generic, `PatternOf<...>(...)`).
            let child = value.children().next()?;
            match child.kind() {
                SyntaxKind::NameRef | SyntaxKind::Path => Some(name_text(&child)),
                SyntaxKind::InstExpr => InstExpr::cast(child).map(|i| i.head_name()),
                _ => first_name(value),
            }
        }
        SyntaxKind::NameRef | SyntaxKind::Path => Some(name_text(value)),
        _ => None,
    }
}

/// The inner constructor head of a `PatternOf<Inner...>` value: the
/// first `NameRef`/`Path` spelled inside the outermost `GenericArgs`
/// (`PatternOf<CBore<M8>>` -> `CBore`, `PatternOf<Drill(dia 2.5mm)>` ->
/// `Drill`). `None` when the instantiation carries no type argument.
fn pattern_inner_head(value: &SyntaxNode) -> Option<String> {
    let generic_args = value
        .descendants()
        .find(|n| n.kind() == SyntaxKind::GenericArgs)?;
    generic_args
        .descendants()
        .find(|n| matches!(n.kind(), SyntaxKind::NameRef | SyntaxKind::Path))
        .map(|n| name_text(&n))
}

/// The `n=N` orbit multiplicity in a `PatternOf` RHS text, if present.
/// Scans for the `n` keyword-argument (`n=4`, `n =4`, `n= 4`) as a
/// word-bounded label and parses the following non-negative integer.
/// `None` when no such argument is spelled (the caller defaults to 1 --
/// a single instance, never an invented count).
fn extract_count(args_text: &str) -> Option<usize> {
    let value = crate::claim_scope::keyword_value(args_text, "n")?;
    let digits: String = value.chars().take_while(char::is_ascii_digit).collect();
    digits.parse::<usize>().ok()
}

/// The value text of a `key = value` keyword argument found anywhere in
/// `text`, with `key` matched as a whole word (not a substring of a
/// longer identifier). Returns the value up to the next comma/paren,
/// trimmed. Shared by [`extract_count`] and the entity projector's
/// measure extraction so the two never disagree on argument parsing.
#[must_use]
pub fn keyword_value(text: &str, key: &str) -> Option<String> {
    let mut from = 0;
    while let Some(rel) = text[from..].find(key) {
        let start = from + rel;
        let end = start + key.len();
        // Left boundary: start of text or a non-identifier char.
        let left_ok = start == 0 || !text[..start].chars().next_back().is_some_and(is_ident_char);
        // Right side: optional ws, then `=`.
        let after = text[end..].trim_start();
        if left_ok {
            if let Some(rest) = after.strip_prefix('=') {
                let value: String = rest
                    .trim_start()
                    .chars()
                    .take_while(|c| *c != ',' && *c != ')' && *c != '(')
                    .collect();
                let value = value.trim().to_string();
                if !value.is_empty() {
                    return Some(value);
                }
            }
        }
        from = end;
    }
    None
}

/// The token following a whole-word positional label (`dia 28mm` ->
/// `28mm`): the label matched word-bounded, then the next
/// whitespace-delimited token (so `dia 28mm H7` yields `28mm`, dropping
/// the trailing tolerance class). `None` when the label is absent or is
/// immediately followed by `=` (a keyword arg, not a positional label).
#[must_use]
pub fn positional_value(text: &str, label: &str) -> Option<String> {
    let mut from = 0;
    while let Some(rel) = text[from..].find(label) {
        let start = from + rel;
        let end = start + label.len();
        let left_ok = start == 0 || !text[..start].chars().next_back().is_some_and(is_ident_char);
        let after = &text[end..];
        // Must be followed by whitespace (a label, not `dia=` and not a
        // longer identifier like `diameter`).
        let boundary_ok = after.starts_with(|c: char| c.is_ascii_whitespace());
        if left_ok && boundary_ok {
            if let Some(token) = after.split_whitespace().next() {
                let token = token.trim_end_matches([',', ')']);
                if !token.is_empty() {
                    return Some(token.to_string());
                }
            }
        }
        from = end;
    }
    None
}

/// True for an identifier continuation character (letters, digits, `_`).
fn is_ident_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_'
}

/// The dotted name text of a `NameRef`/`Path` node.
fn name_text(node: &SyntaxNode) -> String {
    node.children_with_tokens()
        .filter_map(regolith_syntax::cst::SyntaxElement::into_token)
        .filter(|t| matches!(t.kind(), SyntaxKind::Ident | SyntaxKind::Dot))
        .map(|t| t.text().to_string())
        .collect()
}

/// The first `NameRef`/`Path` name anywhere under `node` (a fallback for
/// an unusual callee shape).
fn first_name(node: &SyntaxNode) -> Option<String> {
    node.descendants()
        .find(|n| matches!(n.kind(), SyntaxKind::NameRef | SyntaxKind::Path))
        .map(|n| name_text(&n))
}
